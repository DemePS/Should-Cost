"""Authentication stub — v1 has no sign-in.

See docs/auth-later.md for the Entra ID rollout plan and why the insertion points below
are shaped the way they are: ``current_user`` is the single FastAPI dependency every
mutating route takes, and swapping its implementation (plus flipping AUTH_ENABLED) is
meant to be the entire backend-side change needed to add sign-in later — no route
signatures should need to change.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header

from should_cost.config import get_settings


@dataclass(frozen=True)
class CurrentUser:
    """Whoever is making the request. ``id`` becomes ``Job.requested_by``.

    In v1 (AUTH_ENABLED=false) this is always the anonymous placeholder below — there is
    no real identity, no group allowlist check, nothing to bypass. It exists as a type so
    routes can already depend on "the caller" without knowing yet whether that caller is
    real.
    """

    id: str
    display_name: str


ANONYMOUS_USER = CurrentUser(id="anonymous", display_name="Anonymous (no sign-in in v1)")


async def current_user(
    x_should_cost_user: str | None = Header(default=None, include_in_schema=False),
) -> CurrentUser:
    """FastAPI dependency returning the current caller.

    v1 (AUTH_ENABLED=false, the only supported value today): always returns
    ``ANONYMOUS_USER`` — every request is allowed, regardless of ``X-Should-Cost-User``.
    The header is accepted-but-ignored so the frontend can already send a human-readable
    name (e.g. from a future Entra claim) without the stub rejecting it.

    Later (AUTH_ENABLED=true): this function is where an Entra ID token would be
    validated and checked against a group allowlist — see docs/auth-later.md for the
    exact change. No caller of this dependency needs to change.
    """
    settings = get_settings()
    if not settings.auth_enabled:
        return ANONYMOUS_USER
    # Placeholder for the Entra ID rollout — see docs/auth-later.md.
    raise NotImplementedError(
        "AUTH_ENABLED=true has no implementation yet; see docs/auth-later.md"
    )
