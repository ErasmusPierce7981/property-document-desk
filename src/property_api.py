from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from property_desk import InfraiError, InfraiPropertyIndex, PropertyDocument


class DocumentInput(BaseModel):
    document_id: str = Field(min_length=1)
    property_id: str = Field(min_length=1)
    kind: Literal["maintenance_request", "tenant_document", "inspection_reminder"]
    text: str = Field(min_length=1)
    due_date: date | None = None


class IndexRequest(BaseModel):
    collection: str = Field(min_length=1)
    documents: list[DocumentInput] = Field(min_length=1)


class QuestionRequest(BaseModel):
    collection: str = Field(min_length=1)
    property_id: str = Field(min_length=1)
    question: str = Field(min_length=1)


class AnswerSource(BaseModel):
    document_id: str
    kind: str
    text: str
    score: float
    due_date: date | None


class QuestionAnswer(BaseModel):
    answer: str
    sources: list[AnswerSource]


app = FastAPI(title="Property Document Desk")


@app.exception_handler(InfraiError)
async def infrai_error_handler(_request: Request, exc: InfraiError) -> JSONResponse:
    status = exc.status_code if 400 <= exc.status_code < 500 else 502
    return JSONResponse(
        status_code=status,
        content={"detail": {"code": exc.code, "message": str(exc)}},
    )


@app.post("/documents/index")
async def index_documents(body: IndexRequest) -> dict[str, int]:
    index = InfraiPropertyIndex()
    try:
        documents = [PropertyDocument(**item.model_dump()) for item in body.documents]
        return {"indexed": await index.index(body.collection, documents)}
    finally:
        await index.close()


@app.post("/questions/answer", response_model=QuestionAnswer)
async def answer_question(body: QuestionRequest) -> QuestionAnswer:
    index = InfraiPropertyIndex()
    try:
        hits = await index.ask(body.collection, body.property_id, body.question)
        sources = [AnswerSource(**hit.__dict__) for hit in hits]
        answer = hits[0].text if hits else "No matching property document was found."
        return QuestionAnswer(answer=answer, sources=sources)
    finally:
        await index.close()
