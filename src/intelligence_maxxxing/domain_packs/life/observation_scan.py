"""Complete paginated observation scan for experiment evidence (Stage 3.1)."""

from __future__ import annotations

from typing import Any

from intelligence_maxxxing.application.ports import ObservationListFilters, ProjectedObservation

PAGE_SIZE = 500


def scan_all_life_observations(
    projections: Any,
    *,
    owner_id: str,
    application_id: str,
    max_global_position: int | None = None,
) -> list[ProjectedObservation]:
    """Page through all life observations until exhausted.

    Never treats a single page as the full cohort. When max_global_position is
    set, rows with higher positions are dropped (evidence cutoff freeze).
    """
    out: list[ProjectedObservation] = []
    after: int | None = None
    while True:
        page = list(
            projections.list_observations(
                owner_id,
                application_id,
                ObservationListFilters(
                    domain_pack="life",
                    after_position=after,
                    limit=PAGE_SIZE,
                ),
            )
        )
        if not page:
            break
        for row in page:
            if max_global_position is not None and row.global_position > max_global_position:
                continue
            out.append(row)
        after = page[-1].global_position
        if len(page) < PAGE_SIZE:
            break
    return out
