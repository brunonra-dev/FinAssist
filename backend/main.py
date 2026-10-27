from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

import database
import gemini


class Question(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    question: str = Field(min_length=1, max_length=2000)


class Source(BaseModel):
    id: int
    document: str
    title: str
    section: str
    content: str


class Answer(BaseModel):
    answer: str
    sources: list[Source]
    model: str | None


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.reindex_documents()
    yield


app = FastAPI(title="FinAssist", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask", response_model=Answer)
def ask(question: Question):
    sources = database.search(question.question)
    if not sources:
        return {"answer": gemini.NO_INFORMATION, "sources": [], "model": None}
    try:
        return gemini.answer_question(question.question, sources)
    except gemini.GeminiError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None
