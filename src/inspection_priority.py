from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SearchHit:
    document_id: str
    kind: str
    text: str
    score: float
    due_date: date | None = None


def prioritize_inspection_reminders(hits: list[SearchHit], today: date) -> list[SearchHit]:
    """Put overdue inspection work first, then retain relevance order."""
    return sorted(
        hits,
        key=lambda hit: (
            not (
                hit.kind == "inspection_reminder"
                and hit.due_date is not None
                and hit.due_date < today
            ),
            -hit.score,
        ),
    )

