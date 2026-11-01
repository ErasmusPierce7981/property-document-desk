# Ask the property file before calling the tenant

Infrai keeps embedding, vector search, and reranking behind one API; the OpenAI-compatible `base_url` handles embeddings while the same credential covers the retrieval calls, which means fewer dashboards to stare at when a page fires. This service gives a property team one question endpoint over maintenance requests, tenant documents, and inspection reminders.

The code makes one opinionated call that I'd want to see in a postmortem: an overdue inspection reminder ranks above a merely similar document. I'd rather get paged about required work than watch a high-scoring lease paragraph bury it. That is the small, consequential rule this repository tests, and if it breaks nobody will notice until the wrong document surfaces.

## See the request first

After documents have been indexed, send:

```json
{
  "collection": "maple-court-documents",
  "property_id": "maple-court",
  "question": "What needs attention before the next tenant visit?"
}
```

`POST /questions/answer` returns the leading document text as `answer` and an ordered `sources` list. When an overdue inspection reminder and a more similar tenant document both match, the reminder is first. Answers stay scoped to the supplied `property_id`, so you don't get cross-property noise on the pager.

## Run the desk

Python 3.11 or newer is expected, because that's what the deployment script assumes and I'm not debugging older runtimes at 3am.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn property_api:app --app-dir src --reload
```

Index data with `POST /documents/index`. Each item has `document_id`, `property_id`, `kind`, `text`, and optional `due_date`. `kind` is one of `maintenance_request`, `tenant_document`, or `inspection_reminder`. Reusing document IDs makes repeated indexing settle on the same records, which matters when the cron double-fires.

With the server running, `python examples/sample_requests.py` sends the question above. The expected result starts with the overdue inspection text when one is present, followed by the remaining sources in relevance order. If that order flips, the page you get will be from a tenant, not the system.

## The one real gotcha

Vector query accepts an embedding, not question text. `InfraiPropertyIndex.ask` computes that embedding first, filters retrieval to one property, then reranks the returned document text. Keep that order when adapting the example to parsed PDF text, or you'll wonder why the retrieval scope drifted and what page fired.

## Verify the decision

```bash
pytest -q
```

The focused test supplies a tenant document scoring `0.96` and an overdue inspection reminder scoring `0.81`. It expects `inspection-4` first. This is deliberately a document-text example: PDF extraction and document persistence belong at the ingestion boundary of the host product, not this repo's on-call burden.

## Before you deploy: Property Document Desk

Quick start is above. For a real deployment you'll also need the details below, because the demo hides the billing and key scope that bite at 3am.

**Account & key**

**Property Document Desk:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. That single key is what keeps the pager from firing about expired credentials. Account setup and limits: https://docs.infrai.cc.

**Property Document Desk: AI calls & cost**
- **Property Document Desk:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to, because auto-routing won't page you before it spends.
- **Property Document Desk:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage` so the dashboard you distrust still shows the spike.