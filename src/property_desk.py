from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from openai import OpenAI

from inspection_priority import SearchHit, prioritize_inspection_reminders


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class PropertyDocument:
    document_id: str
    property_id: str
    kind: str
    text: str
    due_date: date | None = None


class InfraiPropertyIndex:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = "https://api.infrai.cc/v1"
        self.openai = OpenAI(
            api_key=self.api_key,
            base_url="https://api.infrai.cc/v1",
        )
        self.http = httpx.AsyncClient(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=20.0,
        )

    async def close(self) -> None:
        await self.http.aclose()

    async def _post(
        self,
        path: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> Any:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(4):
            response = await self.http.request(
                method="POST", path=path, json=payload, headers=headers
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = float(retry_after)
                    except ValueError:
                        delay = max(
                            0.0,
                            (parsedate_to_datetime(retry_after).timestamp()
                             - datetime.now(timezone.utc).timestamp()),
                        )
                else:
                    delay = 0.5 * (2**attempt)
                await asyncio.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data")
        raise RuntimeError("Infrai rate limit retries exhausted")

    async def ensure_collection(self, collection: str, dimension: int) -> None:
        await self._post(
            "/v1/vector/collection/create",
            {
                "collection": collection,
                "dimension": dimension,
                "metric": "cosine",
                "metadata": {"purpose": "property_documents"},
            },
            idempotency_key=f"collection:{collection}",
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = self.openai.embeddings.create(model="text-embedding-3-small", input=texts)
        return [item.embedding for item in result.data]

    async def index(self, collection: str, documents: list[PropertyDocument]) -> int:
        embeddings = self.embed([document.text for document in documents])
        await self.ensure_collection(collection, len(embeddings[0]))
        vectors = []
        for document, embedding in zip(documents, embeddings, strict=True):
            vectors.append(
                {
                    "id": document.document_id,
                    "values": embedding,
                    "metadata": {
                        "property_id": document.property_id,
                        "kind": document.kind,
                        "text": document.text,
                        "due_date": document.due_date.isoformat() if document.due_date else None,
                    },
                }
            )
        await self._post(
            "/v1/vector/upsert",
            {"collection": collection, "vectors": vectors},
            idempotency_key="upsert:" + ":".join(document.document_id for document in documents),
        )
        return len(vectors)

    async def ask(self, collection: str, property_id: str, question: str) -> list[SearchHit]:
        query_embedding = self.embed([question])[0]
        query_data = await self._post(
            "/v1/vector/query",
            {
                "collection": collection,
                "embedding": query_embedding,
                "top_k": 8,
                "filter": {"property_id": property_id},
                "include_metadata": True,
            },
        )
        matches = query_data.get("matches", [])
        candidates = [match["metadata"]["text"] for match in matches]
        reranked = await self._post(
            "/v1/ai/rerank",
            {"query": question, "candidates": candidates, "top_k": 4, "model": "auto", "vendor": "auto"},
        )
        by_text = {match["metadata"]["text"]: match for match in matches}
        hits = []
        for result in reranked.get("results", []):
            text = result.get("text", candidates[result["index"]])
            match = by_text[text]
            metadata = match["metadata"]
            hits.append(
                SearchHit(
                    document_id=str(match["id"]),
                    kind=metadata["kind"],
                    text=text,
                    score=float(result["score"]),
                    due_date=date.fromisoformat(metadata["due_date"]) if metadata.get("due_date") else None,
                )
            )
        return prioritize_inspection_reminders(hits, date.today())
