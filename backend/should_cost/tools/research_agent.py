"""Step 3 — the tool-using research agent. The only step that gets tool access.

Tools:
- ``web_search``: the Microsoft Agent Framework hosted web-search tool
  (``client.get_web_search_tool()``, Bing grounding via Azure AI Foundry) when
  ``SEARCH_PROVIDER=hosted``, or a Tavily-backed function tool when
  ``SEARCH_PROVIDER=tavily``.
- ``fetch_page``: a plain function tool — fetches a URL and returns text + a best-effort
  publication date, so the agent can confirm a result before citing it.
- ``submit_parameter``: a plain function tool that appends to this run's result list —
  this is how the agent "returns" its findings instead of a single structured response,
  since it may need to submit many parameters across one run.

Startup self-test: the Microsoft docs are inconsistent about hosted web-search support
across Foundry model providers, so ``run_search_self_test`` makes one real search call
with whatever ``SEARCH_PROVIDER`` is configured and raises at startup if it fails —
should_cost/main.py calls this during the app lifespan, not lazily on first job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

import httpx
from agent_framework import Agent, ChatOptions
from agent_framework_foundry import FoundryChatClient

from should_cost.config import SearchProvider, Settings
from should_cost.models.common import Confidence, Source
from should_cost.models.workflow import ResearchedParameter
from should_cost.tools.model_client import _load_prompt, _shared_hard_rules

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class SearchSelfTestError(RuntimeError):
    """Raised at startup when the configured SEARCH_PROVIDER cannot actually search."""


@dataclass
class ResearchTarget:
    """One worklist item built by workflow/steps/research.py's select_research_targets()."""

    name: str
    unit: str
    hint: str = ""


@dataclass
class _ResearchSession:
    """Holds this run's state for the plain-function tools below (a closure over a list,
    rather than module-level global state, so concurrent jobs never share a collector).
    """

    collected: list[ResearchedParameter] = field(default_factory=list)

    def submit_parameter(
        self,
        name: str,
        low: float,
        base: float,
        high: float,
        unit: str,
        source_name: str,
        url: str | None,
        source_date: str,
        confidence: str,
        is_compound_constituent: bool = False,
        marked_to_be_validated: bool = False,
    ) -> str:
        """Submit one researched Low/Base/High parameter with its source.

        Args:
            name: Parameter name, matching a worklist item.
            low: Low scenario value.
            base: Base (most likely) value.
            high: High scenario value.
            unit: Unit, e.g. 'EUR/kg', 'EUR/h', '%'.
            source_name: Named source, e.g. 'Eurostat lc_lci_lev', 'Freightos FBX11'.
            url: Source URL. Must be a real URL you fetched, or None if marked_to_be_validated.
            source_date: Vintage/date of the source, e.g. '2025', 'November 2026'.
            confidence: One of 'high', 'medium', 'low'.
            is_compound_constituent: True if this is one constituent of a decomposed material.
            marked_to_be_validated: True if no verifiable source was found — url must be None.
        """
        if not marked_to_be_validated and not url:
            raise ValueError(
                f"submit_parameter({name!r}): a non-'to be validated' parameter must have a real URL. "
                "Never fabricate a citation — call again with marked_to_be_validated=True instead."
            )
        estimate_source = Source(
            name=source_name,
            url=url,
            vintage=source_date,
            confidence=Confidence(confidence),
            is_internal=False,
            to_be_validated=marked_to_be_validated,
        )
        from should_cost.models.common import ParameterEstimate

        self.collected.append(
            ResearchedParameter(
                estimate=ParameterEstimate(name=name, unit=unit, low=low, base=base, high=high, source=estimate_source),
                is_compound_constituent=is_compound_constituent,
                marked_to_be_validated=marked_to_be_validated,
            )
        )
        return f"Recorded {name!r} = {base} {unit} (source: {source_name})"


_PUBLISHED_DATE_RE = re.compile(
    r'"datePublished"\s*:\s*"([^"]+)"|property=["\']article:published_time["\']\s+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


async def fetch_page(url: str) -> str:
    """Fetch a URL and return its visible text plus a best-effort publication date.

    Args:
        url: The page URL to fetch.
    """
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": "should-cost-research-agent/1.0"})
        response.raise_for_status()
        html = response.text

    date_match = _PUBLISHED_DATE_RE.search(html)
    published = next((g for g in (date_match.groups() if date_match else ()) if g), None)

    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()[:8000]

    header = f"[fetched {url}" + (f", published {published}" if published else "") + "]\n"
    return header + text


def build_tavily_search_tool(api_key: str):
    async def web_search(query: str) -> str:
        """Search the web and return the top results with titles, URLs, and snippets.

        Args:
            query: The search query.
        """
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                TAVILY_SEARCH_URL,
                json={"api_key": api_key, "query": query, "max_results": 5, "include_answer": False},
            )
            response.raise_for_status()
            body = response.json()
        lines = []
        for item in body.get("results", []):
            lines.append(f"- {item.get('title', '')} | {item.get('url', '')}\n  {item.get('content', '')[:300]}")
        return "\n".join(lines) or "No results."

    return web_search


def _build_web_search_tool(settings: Settings, chat_client: FoundryChatClient):
    if settings.search_provider == SearchProvider.HOSTED:
        return chat_client.get_web_search_tool()
    assert settings.tavily_api_key
    return build_tavily_search_tool(settings.tavily_api_key)


def build_research_agent(settings: Settings, chat_client: FoundryChatClient) -> tuple[Agent, _ResearchSession]:
    session = _ResearchSession()
    instructions = _shared_hard_rules() + "\n\n" + _load_prompt("research_agent.md")
    agent = Agent(
        client=chat_client,
        instructions=instructions,
        tools=[
            _build_web_search_tool(settings, chat_client),
            fetch_page,
            session.submit_parameter,
        ],
        name="should_cost_research_agent",
    )
    return agent, session


async def run_research(
    settings: Settings, chat_client: FoundryChatClient, targets: list[ResearchTarget]
) -> list[ResearchedParameter]:
    """Run Step 3 for one worklist. Returns one ResearchedParameter per
    ``submit_parameter`` call the agent made; the caller (workflow/steps/research.py)
    checks that every worklist item got a submission and treats any gap as a step-level
    failure, not a silently incomplete result.
    """
    agent, session = build_research_agent(settings, chat_client)
    worklist_text = "\n".join(f"- {t.name} ({t.unit}){f' — {t.hint}' if t.hint else ''}" for t in targets)
    async with agent:
        await agent.run(
            f"Research the following parameters and call submit_parameter for each:\n{worklist_text}",
            options=ChatOptions(tool_choice="auto"),
        )
    return session.collected


async def run_search_self_test(settings: Settings, chat_client: FoundryChatClient) -> str:
    """Run one real search with the configured provider; raise with a clear message if it
    fails, rather than discovering at the first real job that hosted search silently
    doesn't work for this model/provider combination (the Microsoft docs are inconsistent
    on hosted web-search support across Foundry model providers).
    """
    tool = _build_web_search_tool(settings, chat_client)
    probe_agent = Agent(
        client=chat_client,
        instructions="You are a connectivity probe. Call the web search tool once for the given query, "
        "then reply with the single word OK.",
        tools=[tool],
    )
    try:
        async with probe_agent:
            await probe_agent.run("Search for: Eurostat industrial electricity price 2025")
    except Exception as exc:  # noqa: BLE001 - deliberately broad: this is a startup gate
        raise SearchSelfTestError(
            f"SEARCH_PROVIDER={settings.search_provider.value} self-test failed: {exc}. "
            "If hosted, confirm a Bing grounding connection is configured on the Foundry "
            "project (see docs/design.md); if tavily, confirm TAVILY_API_KEY is valid."
        ) from exc
    return settings.search_provider.value
