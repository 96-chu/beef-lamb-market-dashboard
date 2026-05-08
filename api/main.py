from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.agent.openai_agent import (
    AgentError,
    answer_question,
    build_chart_suggestion,
    build_report_markdown,
)
from src.agent.providers import ProviderError, create_provider
from src.agent.sql_tools import SQLToolError, ensure_database, get_schema, run_sql_query
from src.load.load_to_sqlite import DEFAULT_DB_PATH


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2_000)
    row_limit: int = Field(default=100, ge=1, le=500)
    include_report: bool = False


class SQLRequest(BaseModel):
    sql: str = Field(..., min_length=1, max_length=8_000)
    row_limit: int = Field(default=100, ge=1, le=500)


class ReportRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2_000)
    answer: str = Field(default="", max_length=10_000)
    sql: str | None = Field(default=None, max_length=8_000)
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = Field(default=0, ge=0)
    truncated: bool = False
    chart_suggestion: dict[str, Any] | None = None


class SchemaResponse(BaseModel):
    database_path: str
    dialect: str
    tables: list[dict[str, Any]]
    join_guide: list[str]
    business_glossary: list[dict[str, str]]
    query_rules: list[str]


def parse_cors_origins() -> list[str]:
    origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5273,http://127.0.0.1:5273,http://localhost:8000",
    )
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


app = FastAPI(
    title="Beef & Lamb Market AI Agent API",
    version="0.1.0",
    description="Natural-language-to-SQL API for the Australian beef and lamb market dashboard.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    ensure_database(DEFAULT_DB_PATH)


@app.get("/api/health")
def health() -> dict[str, Any]:
    db_path = ensure_database(DEFAULT_DB_PATH)
    try:
        provider_status = create_provider().status()
    except ProviderError as exc:
        provider_status = {
            "provider": os.getenv("AI_PROVIDER", "groq"),
            "model": os.getenv("AI_MODEL"),
            "configured": False,
            "available": False,
            "detail": str(exc),
        }

    return {
        "status": "ok",
        "database_path": str(db_path),
        **provider_status,
        "groq_configured": bool(os.getenv("GROQ_API_KEY")),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
    }


@app.get("/api/schema", response_model=SchemaResponse)
def schema(include_samples: bool = False) -> dict[str, Any]:
    return get_schema(include_samples=include_samples)


@app.post("/api/sql")
def sql_query(request: SQLRequest) -> dict[str, Any]:
    try:
        result = run_sql_query(request.sql, row_limit=request.row_limit)
        chart_suggestion = build_chart_suggestion(result)
        result["chart_suggestion"] = chart_suggestion
        result["report_markdown"] = build_report_markdown(
            "Direct SQL query",
            f"SQL returned {result['row_count']} rows in {result['elapsed_ms']} ms.",
            result,
            chart_suggestion,
        )
        return result
    except SQLToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except sqlite_error_tuple() as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat")
def chat(request: QuestionRequest) -> dict[str, Any]:
    try:
        return answer_question(
            request.question,
            row_limit=request.row_limit,
            include_report=request.include_report,
        )
    except AgentError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SQLToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/report")
def report(request: ReportRequest) -> dict[str, Any]:
    query_result = {
        "sql": request.sql,
        "columns": request.columns,
        "rows": request.rows,
        "row_count": request.row_count or len(request.rows),
        "truncated": request.truncated,
    }
    chart_suggestion = request.chart_suggestion or build_chart_suggestion(query_result)
    return {
        "report_markdown": build_report_markdown(
            request.question,
            request.answer,
            query_result,
            chart_suggestion,
        ),
        "chart_suggestion": chart_suggestion,
    }


def sqlite_error_tuple() -> tuple[type[Exception], ...]:
    import sqlite3

    return (sqlite3.DatabaseError,)
