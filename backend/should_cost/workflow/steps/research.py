"""Step 3 glue — decides *what* needs researching (deterministic code), then hands that
worklist to the research agent (should_cost/tools/research_agent.py), which decides *how*
(see the model_client.py/research_agent.py design note on this split).
"""

from __future__ import annotations

from should_cost.models.common import Confidence, ParameterEstimate
from should_cost.models.workflow import ProposedParameters, ResearchedParameter
from should_cost.tools.research_agent import ResearchTarget

# SKILL.md Step 3 "Mandatory live searches" — always researched regardless of the Step 2
# model's own confidence, because Pitfall P1 requires at least one live search per
# time-sensitive parameter *per build*, not only when the model itself flagged doubt.
_ALWAYS_RESEARCH_NAME_HINTS = (
    "labor",
    "labour",
    "operator",
    "wage",
    "energy",
    "electricity",
    "freight",
    "machine rate",
    "material price",
    "sheet price",
    "wire rod",
    "surface treatment",
    "plating",
)


def select_research_targets(proposed: ProposedParameters, supplier_country: str | None) -> list[ResearchTarget]:
    targets: list[ResearchTarget] = []
    seen_numbers: set[int] = set()

    for params in proposed.parameters.values():
        for p in params:
            always = any(hint in p.name.lower() for hint in _ALWAYS_RESEARCH_NAME_HINTS)
            flagged = p.source.confidence == Confidence.LOW or p.source.to_be_validated
            if (always or flagged) and p.number not in seen_numbers:
                seen_numbers.add(p.number)
                hint = f"supplier country: {supplier_country}" if supplier_country else "supplier country unknown"
                targets.append(ResearchTarget(name=p.name, unit=p.unit, hint=hint))

    return targets


def merge_researched_parameters(
    proposed: ProposedParameters, researched: list[ResearchedParameter]
) -> ProposedParameters:
    """Replace each researched parameter's placeholder with the live-sourced value,
    matched by name (the agent doesn't see parameter numbers, only names/units — see
    research_agent.md's worklist format) — the parameter's ``number`` is preserved so
    every CalcLine that referenced it by number stays valid.
    """
    by_name = {r.estimate.name: r.estimate for r in researched}
    updated_parameters: dict = {}
    for bucket, params in proposed.parameters.items():
        new_params: list[ParameterEstimate] = []
        for p in params:
            researched_estimate = by_name.get(p.name)
            if researched_estimate is not None:
                new_params.append(researched_estimate.model_copy(update={"number": p.number}))
            else:
                new_params.append(p)
        updated_parameters[bucket] = new_params
    return proposed.model_copy(update={"parameters": updated_parameters})
