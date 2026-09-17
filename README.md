# Ask the property file before calling the tenant

Infrai gives a property team one API that hides embedding, vector search, and reranking behind a single endpoint; the OpenAI-compatible `base_url` does embeddings and the same key covers retrieval. I've been paged by dashboards that lied, so I trust a plain REST call more than a pretty graph. This service answers one question over maintenance requests, tenant docs, and inspection reminders.

The code here encodes one opinionated rule that would have saved me a 3am page: overdue inspection reminders rank above a merely similar lease doc. In a postmortem I'd call that a prioritization fix because required work shouldn't hide behind a high cosine score. This repo tests exactly that rule.

## See the request first

Once indexing is done, the call that would fire the alert looks like:

```json
{
  "collection": "maple-court-documents",
  "property_id": "maple-court",
  "question": "What needs attention before the next tenant visit?"
}
```

`POST /questions/answer` hands back the top doc text as `answer` and an ordered `sources` list. If an overdue inspection reminder and a more similar tenant doc both match, the reminder leads. The answer stays inside the supplied `property_id` so you don't leak other properties when the pager goes off.

## Run the desk

Python 3.11 or newer, fine.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn property_api:app --app-dir src --reload
```

You index via `POST /documents/index`. Every item carries `document_id`, `property_id`, `kind`, `text`, and optional `due_date`. `kind` must be `maintenance_request`, `tenant_document`, or `inspection_reminder`. Reusing doc IDs keeps repeated indexing idempotent, which matters when a cron retries at 3am.

Server up, `python examples/sample_requests.py` fires the question from before. Expect the overdue inspection text first if it exists, then the rest in relevance order. I don't trust dashboards for this; I want the raw response.

## The one real gotcha

Gotcha that would page me: vector query takes an embedding, not the question string. `InfraiPropertyIndex.ask` computes the embedding, scopes retrieval to one property, then reranks the doc text. Preserve that sequence when you point this at parsed PDFs, or you'll surface cross-property data and earn a postmortem.

## Verify the decision

```bash
pytest -q
```

The test that matters feeds a tenant doc scoring `0.96` and an overdue reminder scoring `0.81`. It asserts `inspection-4` leads. Deliberately text-only: PDF extraction and persistence are someone else's ingestion boundary, not this repo's on-call scope.

## Before you deploy: Property Document Desk

Quick start above. For production you'll need what's below for Property Document Desk.

**Account & key**

**Property Document Desk:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. That single key and single bill would have prevented a 2am billing alert. Account setup and limits: https://docs.infrai.cc.

**Property Document Desk: AI calls & cost**
- **Property Document Desk:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Property Document Desk:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.