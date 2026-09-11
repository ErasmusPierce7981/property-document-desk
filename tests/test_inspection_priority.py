from datetime import date

from inspection_priority import SearchHit, prioritize_inspection_reminders


def test_overdue_inspection_reminder_precedes_more_similar_tenant_document() -> None:
    hits = [
        SearchHit("lease-7", "tenant_document", "The lease mentions annual access.", 0.96),
        SearchHit(
            "inspection-4",
            "inspection_reminder",
            "Boiler inspection was due yesterday.",
            0.81,
            date(2026, 1, 9),
        ),
        SearchHit("repair-2", "maintenance_request", "The boiler is making noise.", 0.90),
    ]

    ordered = prioritize_inspection_reminders(hits, today=date(2026, 1, 10))

    assert [hit.document_id for hit in ordered] == ["inspection-4", "lease-7", "repair-2"]
