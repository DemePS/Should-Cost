"""The model-call layer: a plain chat client for three calls, and a tool-using Agent for
propose_parameters (Step 2) — updated to use tools after review surfaced that
hand-written CalcLine formulas were a real bug source (see should_cost/tools/
process_formulas.py's docstring). extract_part_facts, pre_build_reasoning and
write_insights stay bare structured calls — they have nothing a typed tool would help
with (see docs/design.md §5). Each function here builds the messages for one call,
passes the relevant Pydantic model as the ``response_format`` of a ``ChatOptions``, and
returns the already-validated, already-parsed model instance from ``response.value`` —
Agent Framework handles the structured-output request and the parse/validate step; this
module's job is only to assemble the right prompt + context (and, for propose_parameters,
tools) per call.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from agent_framework import Agent, ChatOptions, Message
from agent_framework_foundry import FoundryChatClient
from pydantic import BaseModel

from should_cost.config import Settings
from should_cost.models.workflow import Insights, PartFacts, PreBuildReasoning, ProposedParameters
from should_cost.tools.foundry_credentials import build_foundry_credential
from should_cost.tools.process_formulas import (
    build_lot_based_setup_cost_calc_line,
    build_nesting_yield_material_calc_lines,
)

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


@lru_cache(maxsize=None)
def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _shared_hard_rules() -> str:
    return _load_prompt("_shared_hard_rules.md")


def _messages(system_text: str, user_text: str) -> list[Message]:
    return [Message("system", [system_text]), Message("user", [user_text])]


def build_chat_client(settings: Settings) -> FoundryChatClient:
    """One client per call site is fine per the SDK's own concurrency note ("one client
    instance can be shared by concurrent asynchronous calls... each call must use its own
    Agent/AgentSession/messages/options") — callers (workflow steps) are expected to reuse
    a single client across a job's calls rather than constructing one per call.
    """
    credential = build_foundry_credential(settings)
    return FoundryChatClient(
        project_endpoint=settings.azure_ai_foundry_endpoint,
        model=settings.model_deployment,
        credential=credential,
    )


async def _structured_call(client: FoundryChatClient, *, system_text: str, user_text: str, response_format: type[BaseModel]):
    messages = _messages(system_text, user_text)
    response = await client.get_response(messages, options=ChatOptions(response_format=response_format))
    return response.value


async def extract_part_facts(
    client: FoundryChatClient, *, document_text: str, ppe_context: str
) -> PartFacts:
    """Step 1."""
    return await _structured_call(
        client,
        system_text=_load_prompt("extract_part_facts.md"),
        user_text=(
            "PPE / spend context (do not override Volume/Spend/Price from documents):\n"
            f"{ppe_context}\n\n"
            f"Retrieved document text:\n{document_text}"
        ),
        response_format=PartFacts,
    )


async def pre_build_reasoning(
    client: FoundryChatClient,
    *,
    component_label: str,
    part_facts: PartFacts,
    bucket_inputs_reference: str,
) -> PreBuildReasoning:
    """Step 1.5 — called before propose_parameters; its ComplexityFlags decide (in code,
    not here) whether Step 2.5 runs before the parameter call below.
    """
    return await _structured_call(
        client,
        system_text=_shared_hard_rules() + "\n\n" + _load_prompt("propose_parameters.md"),
        user_text=(
            f"Component: {component_label}\n\n"
            f"Step 1 facts (JSON):\n{part_facts.model_dump_json(indent=2)}\n\n"
            f"Reference — bucket_inputs_by_process.md:\n{bucket_inputs_reference}\n\n"
            "Produce the Pre-Build Reasoning block only. Do not propose parameters yet."
        ),
        response_format=PreBuildReasoning,
    )


async def propose_parameters(
    client: FoundryChatClient,
    *,
    component_label: str,
    part_facts: PartFacts,
    pre_build: PreBuildReasoning,
    bucket_inputs_reference: str,
    benchmarks_reference: str,
    deep_dive_summary: str | None,
) -> ProposedParameters:
    """Step 2 (and folds in the Step 2.5 deep-dive summary, if one was produced).

    Tool-using, not a bare structured call: ``build_nesting_yield_material_calc_lines``
    and ``build_lot_based_setup_cost_calc_line`` (process_formulas.py) are hardcoded,
    correct-by-construction CalcLine builders for the two costing_accuracy_rules.md
    rules that give an exact literal formula. The model calls these for the materials/
    processes they cover and still constructs CalcLine JSON by hand (ref/sum/expr) for
    everything else — see propose_parameters.md for when each applies. Agent.run with
    both ``tools=`` and a ``response_format`` runs the full tool loop and then validates
    the final answer against ProposedParameters, same mechanism as the research agent.
    """
    deep_dive_block = f"\n\nStep 2.5 deep-dive summary:\n{deep_dive_summary}" if deep_dive_summary else ""
    instructions = _shared_hard_rules() + "\n\n" + _load_prompt("propose_parameters.md")
    user_text = (
        f"Component: {component_label}\n\n"
        f"Step 1 facts (JSON):\n{part_facts.model_dump_json(indent=2)}\n\n"
        f"Pre-Build Reasoning (JSON):\n{pre_build.model_dump_json(indent=2)}\n\n"
        f"Reference — bucket_inputs_by_process.md:\n{bucket_inputs_reference}\n\n"
        f"Reference — benchmarks.md:\n{benchmarks_reference}"
        f"{deep_dive_block}\n\n"
        "Produce the full Step 2 parameter proposal now."
    )
    agent = Agent(
        client=client,
        instructions=instructions,
        tools=[build_nesting_yield_material_calc_lines, build_lot_based_setup_cost_calc_line],
        name="should_cost_propose_parameters_agent",
    )
    async with agent:
        response = await agent.run(user_text, options=ChatOptions(response_format=ProposedParameters))
    return response.value


async def write_insights(
    client: FoundryChatClient,
    *,
    component_label: str,
    language: str,
    cost_build_summary: str,
    sanity_gate_summary: str,
    parameters_summary: str,
) -> Insights:
    """Steps 5.5 + 6 — only called once the sanity gate is GREEN or YELLOW."""
    return await _structured_call(
        client,
        system_text=_shared_hard_rules() + "\n\n" + _load_prompt("write_insights.md"),
        user_text=(
            f"Component: {component_label}\nLanguage: {language}\n\n"
            f"Cost build:\n{cost_build_summary}\n\n"
            f"Sanity gate result:\n{sanity_gate_summary}\n\n"
            f"Parameters (with sources):\n{parameters_summary}"
        ),
        response_format=Insights,
    )
