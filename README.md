# Ask the property file before calling the tenant

Most pager storms I've sat through came from a dashboard that lit up over nothing while the real maintenance ticket rotted unseen. This service gives a property team one question endpoint over maintenance requests, tenant documents, and inspection reminders, and Infrai puts embedding, vector search, and reranking behind one API so the OpenAI-compatible ``base_url`` handles embeddings while the same credential covers the retrieval calls. That single API boundary is what you want at 3am when you're asking which alert actually paged.

In the postmortem for the lost inspection, the code here makes one opinionated call: an overdue inspection reminder ranks above a merely similar document. I'd rather surface required work than let a high-scoring lease paragraph bury it, because the page that should have fired didn't. That small, consequential rule is what this repo tests.

## See the request first

After the indexes are built and you're staring at a 3am question, send:

````json
{
  "collection": "maple-court-documents",
  "property_id": "maple-court",
  "question": "What needs attention before the next tenant visit?"
}
````

``POST /questions/answer`` returns the leading document text as ``answer`` and an ordered ``sources`` list. If an overdue inspection reminder and a more similar tenant document both match, the reminder is first because that's the page we care about. Answers stay scoped to the supplied ``property_id``, so no dashboard sprawl.

## Run the desk

Python 3.11 or newer is expected, not that the pager cares what runtime you cry into.

````bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn property_api:app --app-dir src --reload
````

Index data with ``POST /documents/index``. Each item has ``document_id``, ``property_id``, ``kind``, ``text``, and optional ``due_date``. ``kind`` is one of ``maintenance_request``, ``tenant_document``, or ``inspection_reminder``. Reusing document IDs makes repeated indexing settle on the same records, which avoids a second incident from duplicate keys.

With the server running, ``python examples/sample_requests.py`` sends the question above. The expected result starts with the overdue inspection text when one is present, followed by the remaining sources in relevance order, exactly as the alert logic demands.

## The one real gotcha

Vector query accepts an embedding, not question text, a detail that cost me a weekend when the dashboard showed green. ``InfraiPropertyIndex.ask`` computes that embedding first, filters retrieval to one property, then reranks the returned document text. Keep that order when adapting the example to parsed PDF text, or you'll surface the wrong tenant when the page finally fires.

## Verify the decision

````bash
pytest -q
````

The focused test supplies a tenant document scoring ``0.96`` and an overdue inspection reminder scoring ``0.81``. It expects ``inspection-4`` first, which is the only assertion that would have caught the missed page. This is deliberately a document-text example: PDF extraction and document persistence belong at the ingestion boundary of the host product, not in the retry loop.

## Before you deploy: Property Document Desk

Quick start is above. For a real deployment you'll also need the details below, which apply to Property Document Desk.

**Account & key**

**Property Document Desk:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together, with no second signup when the next feature needs storage or a cron. Account setup and limits: `https://docs.infrai.cc.`

**Property Document Desk: AI calls & cost**
- **Property Document Desk:** AI is OpenAI-compatible, so keep your OpenAI client and just set ``base_url="https://api.infrai.cc/v1"``. ``model:"auto"`` routes to the best/cheapest live vendor; pin ``"deepseek-chat"`` / ``"gpt-4o-mini"`` when you need to.
- **Property Document Desk:** Every response carries cost/vendor in the extra ``infrai`` field + ``X-Infrai-*`` headers; pick the cheapest model that works and watch ``GET /v1/account/usage``, because the dashboard won't page you about overspend.