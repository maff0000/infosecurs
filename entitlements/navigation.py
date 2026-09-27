"""
Database-driven navigation service (PID §4.4, M007-WI2 scope).

    session package tier
        -> active ProductArea rows
        -> min_package_tier <= current tier   (via entitlements.capabilities.has_capability)
        -> ordered parent/child navigation tree

`application_shell.html`'s sidebar (and, at narrow viewports, the exact
same DOM re-presented as a drawer - PID §16.3, "do not duplicate menu DOM
across pages") loops over this function's output. The template never
independently decides commercial entitlement (PID §4.4) - every row is
filtered through the one central `has_capability` decision WI3's own route
guards will also consume, never a re-derived/hard-coded tier check here.

This module deliberately does NOT decide organisation/tenant membership -
`build_navigation_tree` is only ever called (via `entitlements.
context_processors.navigation`) once a view has already resolved
`organisation_id` off the URL itself; tenant scoping of the destination
routes remains `organisations.views.get_member_organisation_or_404`'s job,
completely separately (PID §9.3), same boundary `capabilities.
has_capability` itself already documents.
"""
from __future__ import annotations

import dataclasses
from typing import Optional

from django.urls import reverse

from entitlements.capabilities import has_capability
from entitlements.models import ProductArea


@dataclasses.dataclass(frozen=True)
class NavItem:
    """One rendered sidebar entry. `is_active` marks the exact page being
    viewed; `has_active_descendant` is true for `is_active` itself OR any
    descendant, so a parent item can be styled/expanded to show "you are
    somewhere under here" even when the exact leaf, not the parent, is the
    current page."""

    code: str
    label: str
    url: str
    is_active: bool
    has_active_descendant: bool
    children: tuple["NavItem", ...]


def _pick_current_area(candidates: list[ProductArea]) -> ProductArea:
    """
    Disambiguates the (rare, data-driven) case where more than one
    `ProductArea` shares the exact same `destination_view_name` - the
    seeded data has exactly two such collisions today:

      - `home` and `foundations` both point at `organisations:detail`
        (the latter is a documented WI5-pending placeholder - see
        entitlements/migrations/0002_seed_product_areas.py).
      - `security` (the top-level group) and `security_state` (its first
        child) both point at `security_state:list` - the top-level item is
        itself a real, directly-navigable link to the same page its first
        child also names.

    Rule, applied in order:
      1. Prefer a CHILD (non-null `parent_id`) over a top-level row - the
         more specific item is the more useful thing to highlight as
         "you are here" (resolves the security/security_state case in
         favour of `security_state`).
      2. Among remaining ties (always same-depth siblings in today's data,
         e.g. `home` vs `foundations`), the lowest `display_order` wins -
         the canonical/first-listed item of the group.
    """
    children = [area for area in candidates if area.parent_id is not None]
    pool = children or candidates
    return min(pool, key=lambda area: area.display_order)


def _current_area_code(request, areas_by_view: dict[str, list[ProductArea]]) -> Optional[str]:
    resolver_match = getattr(request, "resolver_match", None)
    if resolver_match is None:
        return None
    key = f"{resolver_match.namespace}:{resolver_match.url_name}"
    candidates = areas_by_view.get(key)
    if not candidates:
        return None
    return _pick_current_area(candidates).code


def build_navigation_tree(request, organisation_id) -> list[NavItem]:
    """
    Builds the full entitled navigation tree for `organisation_id`.
    `organisation_id` need only be a value `django.urls.reverse()` accepts
    for a `<uuid:organisation_id>` converter (a `uuid.UUID` or its string
    form) - this function never fetches the `Organisation` row itself, it
    only builds links; the caller (`entitlements.context_processors.
    navigation`) is responsible for having already resolved a real,
    membership-checked organisation id before calling this.
    """
    all_areas = list(ProductArea.objects.active().filter(show_in_navigation=True))

    areas_by_view: dict[str, list[ProductArea]] = {}
    for area in all_areas:
        areas_by_view.setdefault(area.destination_view_name, []).append(area)

    current_code = _current_area_code(request, areas_by_view)

    entitled_by_pk = {area.pk: area for area in all_areas if has_capability(request, area.code)}

    children_by_parent: dict[Optional[int], list[ProductArea]] = {}
    for area in entitled_by_pk.values():
        parent_id = area.parent_id
        if parent_id is not None and parent_id not in entitled_by_pk:
            # A child whose own parent is not entitled is dropped along
            # with it. Not reachable with today's seed data (a child's
            # min_package_tier is never lower than its parent's - PID
            # §5.2), but this keeps the tree honest rather than assuming
            # that invariant holds forever.
            continue
        children_by_parent.setdefault(parent_id, []).append(area)

    for bucket in children_by_parent.values():
        bucket.sort(key=lambda area: (area.display_order, area.code))

    def build(area: ProductArea) -> NavItem:
        child_areas = children_by_parent.get(area.pk, [])
        child_items = [build(child) for child in child_areas]
        is_active = area.code == current_code
        has_active_descendant = is_active or any(
            child.is_active or child.has_active_descendant for child in child_items
        )
        return NavItem(
            code=area.code,
            label=area.label,
            url=reverse(area.destination_view_name, kwargs={"organisation_id": organisation_id}),
            is_active=is_active,
            has_active_descendant=has_active_descendant,
            children=tuple(child_items),
        )

    top_level = children_by_parent.get(None, [])
    return [build(area) for area in top_level]
