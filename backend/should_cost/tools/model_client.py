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
from typing import Any

from agent_framework import Agent, BaseChatClient, ChatOptions, Message
from pydantic import BaseModel

from should_cost.config import ModelProvider, Settings
from should_cost.models.workflow import Insights, PartFacts, PreBuildReasoning, ProposedParameters
from should_cost.tools.foundry_credentials import build_foundry_credential
from should_cost.tools.process_formulas import (
    build_batch_setup_cost_calc_line,
    build_cnc_machining_calc_line,
    build_cycle_time_machine_conversion_calc_line,
    build_electronics_assembly_calc_lines,
    build_extrusion_conversion_calc_lines,
    build_forging_conversion_calc_line,
    build_lot_based_setup_cost_calc_line,
    build_nesting_yield_material_calc_lines,
    build_stamping_conversion_calc_line,
    build_welded_assembly_calc_line,
)

# Every process_formulas.py tool — see that module's own table for which rule/process
# family each one covers. Passed as a block so propose_parameters always offers the full
# set; the prompt (propose_parameters.md) tells the model which one applies to a given
# process, falling back to generic CalcLine construction for anything none of these cover.
PROCESS_FORMULA_TOOLS = [
    build_nesting_yield_material_calc_lines,
    build_lot_based_setup_cost_calc_line,
    build_cycle_time_machine_conversion_calc_line,
    build_batch_setup_cost_calc_line,
    build_cnc_machining_calc_line,
    build_stamping_conversion_calc_line,
    build_extrusion_conversion_calc_lines,
    build_forging_conversion_calc_line,
    build_electronics_assembly_calc_lines,
    build_welded_assembly_calc_line,
]

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


@lru_cache(maxsize=None)
def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _shared_hard_rules() -> str:
    return _load_prompt("_shared_hard_rules.md")


def _messages(system_text: str, user_text: str) -> list[Message]:
    return [Message("system", [system_text]), Message("user", [user_text])]


def build_chat_client(settings: Settings) -> BaseChatClient:
    """One client per call site is fine per the SDK's own concurrency note ("one client
    instance can be shared by concurrent asynchronous calls... each call must use its own
    Agent/AgentSession/messages/options") — callers (workflow steps) are expected to reuse
    a single client across a job's calls rather than constructing one per call.

    Picks the client class for ``settings.model_provider``; every call site above this
    (extract_part_facts, propose_parameters, ...) and the research agent only depend on
    the common ``BaseChatClient``/``Agent`` interface, never on a provider-specific type.
    """
    if settings.model_provider is ModelProvider.ANTHROPIC:
        from agent_framework.anthropic import AnthropicClient

        assert settings.anthropic_api_key
        return AnthropicClient(api_key=settings.anthropic_api_key, model=settings.model_deployment)

    if settings.model_provider is ModelProvider.DEEPSEEK:
        from agent_framework.openai import OpenAIChatClient

        assert settings.deepseek_api_key
        return OpenAIChatClient(
            model=settings.model_deployment,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )

    from agent_framework_foundry import FoundryChatClient

    credential = build_foundry_credential(settings)
    return FoundryChatClient(
        project_endpoint=settings.azure_ai_foundry_endpoint,
        model=settings.model_deployment,
        credential=credential,
    )


# DeepSeek's Responses-API-compatible endpoint rejects the standard OpenAI strict-mode
# JSON schema shape every Optional/"X | None" field produces (`{"anyOf": [{"type": X},
# {"type": "null"}]}`) with "Invalid json schema: field `anyOf`: missing field `type`" —
# confirmed against the live API. strict=False avoids it (also confirmed live); the cost
# is that agent_framework no longer auto-parses the response into the Pydantic model
# (Mapping-shaped response_format only gets json.loads'd — see agent_framework._types
# ._parse_structured_response_value), so _structured_call and propose_parameters below
# validate the raw dict into the model themselves in that case.
def _wire_response_format(response_format: type[BaseModel], settings: Settings) -> type[BaseModel] | dict[str, Any]:
    if settings.model_provider is not ModelProvider.DEEPSEEK:
        return response_format
    return {
        "type": "json_schema",
        "json_schema": {
            "name": response_format.__name__,
            "schema": response_format.model_json_schema(),
            "strict": False,
        },
    }


# DeepSeek's OpenAI-Responses-compatible endpoint doesn't honor previous_response_id
# conversation chaining (confirmed live, isolated to a single local-function-tool call
# with no response_format involved): agent_framework_openai relies on that chaining to
# avoid resending the whole conversation between a local function tool's call and its
# output, so round 2 sends only the function_call_output and DeepSeek replies "No tool
# call found for tool output with call_id ..." — it never received the matching
# function_call (the client assumed the server already had it via previous_response_id).
# ChatOptions(store=False) makes the client resend full history every turn instead of
# relying on that chaining, which avoids it. Only matters for calls with local function
# tools (propose_parameters, the research agent); DeepSeek's own hosted tools (e.g.
# deepseek_web_search) are resolved server-side in one round trip and are unaffected.
def _local_tool_call_options(settings: Settings, response_format: type[BaseModel] | dict[str, Any]) -> ChatOptions:
    if settings.model_provider is ModelProvider.DEEPSEEK:
        return ChatOptions(response_format=response_format, store=False)
    return ChatOptions(response_format=response_format)


async def _structured_call(
    client: BaseChatClient, *, system_text: str, user_text: str, response_format: type[BaseModel], settings: Settings
):
    messages = _messages(system_text, user_text)
    wire_format = _wire_response_format(response_format, settings)
    response = await client.get_response(messages, options=ChatOptions(response_format=wire_format))
    if isinstance(wire_format, dict):
        return response_format.model_validate(response.value)
    return response.value


async def extract_part_facts(
    client: BaseChatClient, *, document_text: str, ppe_context: str, settings: Settings
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
        settings=settings,
    )


async def pre_build_reasoning(
    client: BaseChatClient,
    *,
    component_label: str,
    part_facts: PartFacts,
    bucket_inputs_reference: str,
    settings: Settings,
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
        settings=settings,
    )


async def propose_parameters(
    client: BaseChatClient,
    *,
    component_label: str,
    part_facts: PartFacts,
    pre_build: PreBuildReasoning,
    bucket_inputs_reference: str,
    benchmarks_reference: str,
    deep_dive_summary: str | None,
    settings: Settings,
) -> ProposedParameters:
    """Step 2 (and folds in the Step 2.5 deep-dive summary, if one was produced).

    Tool-using, not a bare structured call: ``PROCESS_FORMULA_TOOLS`` (process_formulas.py)
    are ten hardcoded, correct-by-construction CalcLine builders — one per
    costing_accuracy_rules.md rule with an exact literal formula (Rule 1, Rule 2) and one
    per process family in bucket_inputs_by_process.md (thermoforming/injection-moulding/
    die-casting share one cycle-time formula; CNC; stamping; extrusion; forging;
    electronics; welded-subassembly Layer 2). The model calls whichever tool matches the
    process it identified, and still constructs CalcLine JSON by hand (ref/sum/expr) for
    anything none of the ten cover — see propose_parameters.md for when each applies.
    Agent.run with both ``tools=`` and a ``response_format`` runs the full tool loop and
    then validates the final answer against ProposedParameters, same mechanism as the
    research agent.
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
    wire_format = _wire_response_format(ProposedParameters, settings)
    agent = Agent(
        client=client,
        instructions=instructions,
        tools=PROCESS_FORMULA_TOOLS,
        name="should_cost",
    )
    async with agent:
        response = await agent.run(user_text, options=_local_tool_call_options(settings, wire_format))
    if isinstance(wire_format, dict):
        return ProposedParameters.model_validate(response.value)
    return response.value


async def write_insights(
    client: BaseChatClient,
    *,
    component_label: str,
    language: str,
    cost_build_summary: str,
    sanity_gate_summary: str,
    parameters_summary: str,
    settings: Settings,
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
        settings=settings,
    )
