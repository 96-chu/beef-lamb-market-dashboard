from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from src.agent.providers import ProviderError, ProviderToolCall, ToolOutput, create_provider
from src.agent.sql_tools import SQLToolError, get_schema, run_sql_query


MAX_TOOL_TURNS = 5

SYSTEM_PROMPT = """
You are an Australian beef and lamb market data analyst.

Your job:
- Convert the user's natural-language question into safe SQLite analysis.
- Call get_schema before writing SQL unless the schema is already visible.
- Call run_sql_query for the final SQL. Do not invent numeric values.
- Prefer vw_latest_kpis, vw_quarterly_market, vw_top_destinations_annual,
  vw_forecast_base_annual, and vw_market_insights when they fit.
- The only available tools are get_schema and run_sql_query. Database views
  such as vw_latest_kpis are not tools. To use a view, call run_sql_query with
  SELECT columns FROM that view.
- For latest KPI questions, call run_sql_query with:
  SELECT product, period, value, unit
  FROM vw_latest_kpis
  ORDER BY product, metric
- Use fact_exports for monthly export destination questions.
- Use fact_production with state = 'Australia' for national production questions.
- Return a concise business answer, then mention the SQL logic in plain English.
- If the result is chartable, include a short chart recommendation in prose.

Safety:
- Only use read-only SELECT/WITH SQL.
- Aggregate before returning detailed rows.
- If a question cannot be answered from the schema, say what is missing.
""".strip()


class AgentError(RuntimeError):
    """Raised when the selected AI-backed agent cannot complete a request."""


OpenAIAgentError = AgentError


@dataclass
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    output_preview: Any
    status: str


VIEW_SQL_SHORTCUTS = {
    "vw_latest_kpis": (
        "SELECT metric, product, period, value, unit "
        "FROM vw_latest_kpis "
        "ORDER BY product, metric"
    ),
    "vw_quarterly_market": (
        "SELECT quarter, product, exports_tonnes, production_tonnes, export_share_pct "
        "FROM vw_quarterly_market "
        "ORDER BY quarter, product"
    ),
    "vw_top_destinations_annual": (
        "SELECT year, product, destination, tonnes, destination_rank "
        "FROM vw_top_destinations_annual "
        "ORDER BY year DESC, product, destination_rank"
    ),
    "vw_forecast_base_annual": (
        "SELECT forecast_year, product, target_metric, forecast_value, unit "
        "FROM vw_forecast_base_annual "
        "ORDER BY forecast_year, product, target_metric"
    ),
    "vw_market_insights": (
        "SELECT category, metric, product, period, business_signal, recommendation, narrative "
        "FROM vw_market_insights "
        "ORDER BY sort_order"
    ),
}


def output_preview(output: dict[str, Any]) -> Any:
    if "rows" in output:
        return {
            "columns": output.get("columns", []),
            "row_count": output.get("row_count", 0),
            "truncated": output.get("truncated", False),
            "rows": output.get("rows", [])[:3],
        }
    if "tables" in output:
        return {
            "table_count": len(output.get("tables", [])),
            "tables": [
                {
                    "name": table.get("name"),
                    "type": table.get("type"),
                    "row_count": table.get("row_count"),
                }
                for table in output.get("tables", [])[:8]
            ],
        }
    return output


def execute_tool(
    name: str,
    arguments: dict[str, Any],
    row_limit: int,
) -> dict[str, Any]:
    if name == "get_schema":
        return get_schema(include_samples=bool(arguments.get("include_samples", False)))
    if name == "run_sql_query":
        requested_limit = int(arguments.get("row_limit") or row_limit)
        return run_sql_query(arguments["sql"], row_limit=min(requested_limit, row_limit))
    raise SQLToolError(f"Unknown tool: {name}")


def strip_json_code_fence(content: str) -> str:
    clean = content.strip()
    if clean.startswith("```"):
        lines = clean.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        clean = "\n".join(lines).strip()
    return clean


def parse_pseudo_tool_call(content: str, row_limit: int) -> ProviderToolCall | None:
    """
    Some small local models return a JSON-like tool request as plain text.

    Example observed from Llama 3.1 8B:
    {"name": "vw_latest_kpis", "parameters": {}}

    Database views are not tools, so this maps common view-name requests to a
    read-only run_sql_query call instead of treating the JSON as a final answer.
    """
    if not content:
        return None
    try:
        payload = json.loads(strip_json_code_fence(content))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    name = payload.get("name") or payload.get("tool") or payload.get("function")
    arguments = (
        payload.get("arguments")
        or payload.get("parameters")
        or payload.get("args")
        or {}
    )
    if not isinstance(name, str):
        return None
    if not isinstance(arguments, dict):
        arguments = {}

    if name in {"get_schema", "run_sql_query"}:
        if name == "run_sql_query" and "row_limit" not in arguments:
            arguments["row_limit"] = row_limit
        return ProviderToolCall(name=name, arguments=arguments)

    if name in VIEW_SQL_SHORTCUTS:
        return ProviderToolCall(
            name="run_sql_query",
            arguments={
                "sql": VIEW_SQL_SHORTCUTS[name],
                "row_limit": row_limit,
            },
        )

    return None


def format_measure(value: Any, unit: str | None = None) -> str:
    if isinstance(value, (int, float)):
        value_text = f"{value:,.0f}" if abs(value) >= 1000 else f"{value:,.2f}"
    else:
        value_text = str(value)
    if unit == "%":
        return f"{value_text}%"
    return f"{value_text} {unit}".strip() if unit else value_text


def build_default_answer(query_result: dict[str, Any] | None) -> str:
    if not query_result or not query_result.get("rows"):
        return "No rows were returned for this question."

    rows = query_result["rows"]
    columns = query_result.get("columns", [])
    column_set = set(columns)
    if {"business_signal", "recommendation"}.issubset(column_set):
        signals = []
        for row in rows[:5]:
            metric = str(row.get("metric", "signal")).replace("_", " ")
            product = str(row.get("product", "market")).title()
            change = row.get("change_pct")
            change_text = (
                f" ({change:,.1f}% change)" if isinstance(change, (int, float)) else ""
            )
            signals.append(f"{product} {metric}{change_text}: {row.get('business_signal')}")
        return "Strongest market signals: " + " ".join(signals)

    if {"metric", "product", "period", "value", "unit"}.issubset(set(columns)):
        lines = []
        for row in rows:
            metric = str(row.get("metric", "")).replace("_", " ")
            product = str(row.get("product", "")).title()
            lines.append(
                f"{product} {metric} was {format_measure(row.get('value'), row.get('unit'))} for {row.get('period')}."
            )
        return " ".join(lines)

    if {"destination", "tonnes"}.issubset(column_set):
        product = str(rows[0].get("product", "market")).title()
        year = rows[0].get("year")
        start_year = rows[0].get("start_year")
        end_year = rows[0].get("end_year")
        period_text = ""
        if year:
            period_text = f" in {year}"
        elif start_year and end_year:
            period_text = f" from {start_year} to {end_year}"
        leaders = [
            f"{row.get('destination')} ({format_measure(row.get('tonnes'), 'tonnes')})"
            for row in rows[:5]
        ]
        return (
            f"The leading {product.lower()} export destinations"
            + period_text
            + " were "
            + ", ".join(leaders)
            + f". The result returned {query_result.get('row_count', len(rows))} ranked destinations."
        )

    if {"quarter", "exports_tonnes", "production_tonnes", "export_share_pct"}.issubset(column_set):
        product = str(rows[0].get("product", "market")).title()
        latest = rows[-1]
        return (
            f"For {product.lower()}, the latest quarter in the result is {latest.get('quarter')}: "
            f"exports were {format_measure(latest.get('exports_tonnes'), 'tonnes')}, "
            f"production was {format_measure(latest.get('production_tonnes'), 'tonnes')}, "
            f"and export share was {format_measure(latest.get('export_share_pct'), '%')}. "
            f"The query returned {query_result.get('row_count', len(rows))} quarterly observations."
        )

    if {"forecast_year", "product", "target_metric", "forecast_value", "unit"}.issubset(column_set):
        highlights = []
        for row in rows[:6]:
            product = str(row.get("product", "market")).title()
            metric = str(row.get("target_metric", "forecast")).replace("_", " ")
            highlights.append(
                f"{product} {metric} is forecast at "
                f"{format_measure(row.get('forecast_value'), row.get('unit'))} in {row.get('forecast_year')}"
            )
        return "Forecast base case: " + "; ".join(highlights) + "."

    preview_lines = []
    for row in rows[:6]:
        parts = [f"{column}: {row.get(column)}" for column in columns[:5]]
        preview_lines.append("; ".join(parts))

    return (
        f"The query returned {query_result.get('row_count', len(rows))} rows. "
        "Key result preview: "
        + " | ".join(preview_lines)
    )


def build_progress_steps(
    tool_call_records: list[ToolCallRecord],
    query_result: dict[str, Any] | None,
) -> list[dict[str, str]]:
    steps = [
        {
            "label": "Provider selected",
            "status": "complete",
            "detail": "The configured AI provider accepted the request.",
        }
    ]
    for record in tool_call_records:
        if record.name == "get_schema":
            detail = "Schema, glossary, and join guide were loaded."
        elif record.name == "run_sql_query":
            sql = record.arguments.get("sql", "")
            detail = sql[:160] + ("..." if len(sql) > 160 else "")
        else:
            detail = f"{record.name} was requested."
        steps.append(
            {
                "label": record.name,
                "status": "complete" if record.status == "ok" else "error",
                "detail": detail,
            }
        )
    if query_result:
        steps.append(
            {
                "label": "Result summarised",
                "status": "complete",
                "detail": f"{query_result.get('row_count', 0)} rows returned.",
            }
        )
    return steps


def build_agent_response(
    question: str,
    answer: str,
    query_result: dict[str, Any] | None,
    tool_call_records: list[ToolCallRecord],
    provider_name: str,
    model: str,
    include_report: bool = True,
) -> dict[str, Any]:
    chart_suggestion = build_chart_suggestion(query_result)
    response = {
        "question": question,
        "answer": answer,
        "sql": query_result.get("sql") if query_result else None,
        "columns": query_result.get("columns", []) if query_result else [],
        "rows": query_result.get("rows", []) if query_result else [],
        "row_count": query_result.get("row_count", 0) if query_result else 0,
        "truncated": query_result.get("truncated", False) if query_result else False,
        "chart_suggestion": chart_suggestion,
        "report_markdown": "",
        "report_pending": bool((not include_report) and query_result),
        "tool_calls": [record.__dict__ for record in tool_call_records],
        "progress_steps": build_progress_steps(tool_call_records, query_result),
        "provider": provider_name,
        "model": model,
    }
    if include_report:
        response["report_markdown"] = build_report_markdown(
            question,
            answer,
            query_result,
            chart_suggestion,
        )
        response["report_pending"] = False
    return response


def latest_kpi_sql_for_question(question: str) -> str | None:
    text = question.lower()
    required_groups = [
        ["latest", "current", "recent"],
        ["beef"],
        ["lamb"],
        ["export"],
        ["production"],
        ["kpi", "key performance", "snapshot"],
    ]
    if all(any(token in text for token in group) for group in required_groups):
        return VIEW_SQL_SHORTCUTS["vw_latest_kpis"]
    return None


def extract_years(question: str) -> list[int]:
    years = [int(year) for year in re.findall(r"\b(20\d{2})\b", question)]
    return sorted(set(years))


def shortcut_sql_for_question(question: str) -> str | None:
    latest_sql = latest_kpi_sql_for_question(question)
    if latest_sql:
        return latest_sql

    text = question.lower()
    if (
        "top" in text
        and "destination" in text
        and "export" in text
        and ("beef" in text or "lamb" in text)
    ):
        product = "lamb" if "lamb" in text and "beef" not in text else "beef"
        years = extract_years(question)
        if len(years) >= 2:
            start_year = min(years)
            end_year = max(years)
            return (
                "SELECT product, destination, MIN(year) AS start_year, "
                "MAX(year) AS end_year, SUM(tonnes) AS tonnes "
                "FROM fact_exports "
                f"WHERE product = '{product}' AND year BETWEEN {start_year} AND {end_year} "
                "GROUP BY product, destination "
                "ORDER BY tonnes DESC "
                "LIMIT 10"
            )
        year = years[0] if len(years) == 1 else None
        where = [f"product = '{product}'"]
        if year:
            where.append(f"year = {year}")
        return (
            "SELECT year, product, destination, tonnes, destination_rank "
            "FROM vw_top_destinations_annual "
            f"WHERE {' AND '.join(where)} "
            "ORDER BY year DESC, destination_rank "
            "LIMIT 10"
        )

    if (
        "quarter" in text
        and "export" in text
        and "production" in text
        and ("share" in text or "versus" in text or "compare" in text)
    ):
        product_clause = ""
        if "beef" in text and "lamb" not in text:
            product_clause = "WHERE product = 'beef' "
        elif "lamb" in text and "beef" not in text:
            product_clause = "WHERE product = 'lamb' "
        return (
            "SELECT quarter, product, exports_tonnes, production_tonnes, export_share_pct "
            "FROM vw_quarterly_market "
            f"{product_clause}"
            "ORDER BY quarter, product"
        )

    if "insight" in text and ("growth" in text or "signal" in text or "strongest" in text):
        return (
            "SELECT category, metric, product, period, value, comparison_value, "
            "change_value, change_pct, unit, direction, business_signal, recommendation "
            "FROM vw_market_insights "
            "WHERE direction LIKE '%growth%' OR COALESCE(change_pct, 0) > 0 "
            "ORDER BY COALESCE(change_pct, 0) DESC, ABS(COALESCE(change_value, 0)) DESC "
            "LIMIT 10"
        )

    if "forecast" in text:
        product_clause = ""
        if "beef" in text and "lamb" not in text:
            product_clause = "WHERE product = 'beef' "
        elif "lamb" in text and "beef" not in text:
            product_clause = "WHERE product = 'lamb' "
        return (
            "SELECT forecast_year, product, target_metric, forecast_value, unit "
            "FROM vw_forecast_base_annual "
            f"{product_clause}"
            "ORDER BY forecast_year, product, target_metric"
        )

    return None


def build_chart_suggestion(query_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not query_result or not query_result.get("rows"):
        return None

    columns = query_result.get("columns", [])
    rows = query_result.get("rows", [])
    numeric_columns = []
    categorical_columns = []

    for column in columns:
        values = [row.get(column) for row in rows if row.get(column) is not None]
        if values and all(isinstance(value, (int, float)) for value in values[:20]):
            numeric_columns.append(column)
        else:
            categorical_columns.append(column)

    if not numeric_columns:
        return None

    time_candidates = [
        column
        for column in categorical_columns + numeric_columns
        if any(token in column.lower() for token in ["date", "month", "quarter", "year", "period"])
    ]
    y_axis = next(
        (column for column in numeric_columns if column not in time_candidates),
        numeric_columns[0],
    )
    category_candidates = [
        column
        for column in categorical_columns
        if len({row.get(column) for row in rows if row.get(column) is not None}) > 1
    ]
    varying_time_candidates = [
        column
        for column in time_candidates
        if len({row.get(column) for row in rows if row.get(column) is not None}) > 1
    ]

    if varying_time_candidates:
        x_axis = varying_time_candidates[0]
        return {
            "chart_type": "line",
            "title": f"{y_axis.replace('_', ' ').title()} over {x_axis.replace('_', ' ')}",
            "x_axis": x_axis,
            "y_axis": y_axis,
            "series": next((col for col in categorical_columns if col != x_axis), None),
            "reason": "The result includes a time-like field and a numeric measure.",
        }

    if category_candidates:
        x_axis = next(
            (
                column
                for column in category_candidates
                if column.lower() not in {"product", "scenario", "unit"}
            ),
            category_candidates[0],
        )
        return {
            "chart_type": "bar",
            "title": f"{y_axis.replace('_', ' ').title()} by {x_axis.replace('_', ' ')}",
            "x_axis": x_axis,
            "y_axis": y_axis,
            "series": next(
                (
                    col
                    for col in category_candidates
                    if col != x_axis and col.lower() not in {"unit"}
                ),
                None,
            ),
            "reason": "The result compares a numeric measure across categories.",
        }

    return {
        "chart_type": "table",
        "title": "Data table",
        "x_axis": None,
        "y_axis": y_axis,
        "series": None,
        "reason": "The result is numeric but does not include a clear category or time field.",
    }


def build_report_markdown(
    question: str,
    answer: str,
    query_result: dict[str, Any] | None,
    chart_suggestion: dict[str, Any] | None,
) -> str:
    lines = [
        "# Beef & Lamb Market Business Report",
        "",
        "## Business Question",
        question,
        "",
        "## Executive Summary",
        answer.strip() or "No narrative summary was returned.",
    ]

    if query_result and query_result.get("rows"):
        lines.extend(["", "## KPI Snapshot"])
        for row in query_result["rows"][:8]:
            if {"quarter", "exports_tonnes", "production_tonnes", "export_share_pct"}.issubset(row):
                product = str(row.get("product", "Market")).title()
                lines.append(
                    f"- **{product} {row.get('quarter')}**: exports "
                    f"{format_measure(row.get('exports_tonnes'), 'tonnes')}, production "
                    f"{format_measure(row.get('production_tonnes'), 'tonnes')}, export share "
                    f"{format_measure(row.get('export_share_pct'), '%')}."
                )
                continue

            if {"destination", "tonnes"}.issubset(row):
                product = str(row.get("product", "Market")).title()
                rank = row.get("destination_rank")
                rank_text = f"rank {rank}, " if rank is not None else ""
                period = row.get("year") or (
                    f"{row.get('start_year')} to {row.get('end_year')}"
                    if row.get("start_year") and row.get("end_year")
                    else "the selected period"
                )
                lines.append(
                    f"- **{product} destination - {row.get('destination')}**: "
                    f"{rank_text}{format_measure(row.get('tonnes'), 'tonnes')} in {period}."
                )
                continue

            if {"business_signal", "recommendation"}.issubset(row):
                product = str(row.get("product", "Market")).title()
                metric = str(row.get("metric", "signal")).replace("_", " ")
                change = row.get("change_pct")
                change_text = (
                    f", {format_measure(change, '%')} change" if isinstance(change, (int, float)) else ""
                )
                lines.append(
                    f"- **{product} {metric}**: {row.get('business_signal')}{change_text}. "
                    f"Action: {row.get('recommendation')}"
                )
                continue

            product = str(row.get("product", "Market")).title()
            metric = str(row.get("metric", row.get("target_metric", "value"))).replace("_", " ")
            period = (
                row.get("period")
                or row.get("quarter")
                or row.get("year")
                or row.get("forecast_year")
                or "current period"
            )
            value = row.get("value", row.get("tonnes", row.get("forecast_value")))
            unit = row.get("unit") or "tonnes"
            lines.append(f"- **{product} {metric}**: {format_measure(value, unit)} in {period}.")

    lines.extend(
        [
            "",
            "## Commercial Interpretation",
            "- Export demand should be read against production capacity because shipment momentum without supply support can tighten allocation pressure.",
            "- Beef currently has a much larger absolute volume base than lamb, so small percentage movements can still represent material tonnage changes.",
            "- Lamb production and export signals should be monitored together because quarterly supply movement can quickly affect export availability.",
            "",
            "## Risks And Watch Points",
            "- Destination concentration can amplify volatility if a top buyer changes demand, pricing, or market-access conditions.",
            "- Production is quarterly while exports are monthly, so near-term export movements may lead or lag supply-side confirmation.",
            "- The analysis is based on the processed reporting window and should be refreshed when new ABS or DAFF releases arrive.",
            "",
            "## Recommended Actions",
            "- Track beef and lamb export volumes against the latest production quarter before making capacity or market-allocation decisions.",
            "- Review top destinations for the product with the largest export movement to separate broad demand growth from destination mix shift.",
            "- Use the next data refresh to confirm whether the latest KPI position is a one-period movement or part of a sustained trend.",
        ]
    )

    if query_result and query_result.get("sql"):
        lines.extend(
            [
                "",
                "## Data Query Used",
                "```sql",
                query_result["sql"],
                "```",
            ]
        )

    if chart_suggestion:
        lines.extend(
            [
                "",
                "## Chart Recommendation",
                (
                    f"Use a {chart_suggestion['chart_type']} chart: "
                    f"{chart_suggestion['title']}. {chart_suggestion['reason']}"
                ),
            ]
        )

    if query_result:
        lines.extend(
            [
                "",
                "## Data Coverage",
                f"Returned {query_result.get('row_count', 0)} rows"
                + ("; result was truncated." if query_result.get("truncated") else "."),
            ]
        )

    return "\n".join(lines)


def answer_question(
    question: str,
    row_limit: int = 100,
    include_report: bool = True,
) -> dict[str, Any]:
    provider = create_provider()
    direct_sql = shortcut_sql_for_question(question)
    if direct_sql:
        query_result = run_sql_query(direct_sql, row_limit=row_limit)
        tool_call_records = [
            ToolCallRecord(
                name="run_sql_query",
                arguments={"sql": direct_sql, "row_limit": row_limit},
                output_preview=output_preview(query_result),
                status="ok",
            )
        ]
        return build_agent_response(
            question=question,
            answer=build_default_answer(query_result),
            query_result=query_result,
            tool_call_records=tool_call_records,
            provider_name=provider.name,
            model=provider.model,
            include_report=include_report,
        )

    try:
        conversation = provider.start(SYSTEM_PROMPT, question)
    except ProviderError as exc:
        raise AgentError(str(exc)) from exc

    tool_call_records: list[ToolCallRecord] = []
    last_query_result: dict[str, Any] | None = None
    tool_outputs: list[ToolOutput] | None = None

    for _ in range(MAX_TOOL_TURNS):
        try:
            provider_response = conversation.next(tool_outputs)
        except ProviderError as exc:
            raise AgentError(str(exc)) from exc

        tool_calls = provider_response.tool_calls
        if not tool_calls:
            pseudo_tool_call = parse_pseudo_tool_call(provider_response.content, row_limit)
            if pseudo_tool_call:
                tool_calls = [pseudo_tool_call]

        if not tool_calls:
            answer = provider_response.content or build_default_answer(last_query_result)
            return build_agent_response(
                question=question,
                answer=answer,
                query_result=last_query_result,
                tool_call_records=tool_call_records,
                provider_name=provider.name,
                model=provider.model,
                include_report=include_report,
            )

        tool_outputs = []
        for call in tool_calls:
            name = call.name
            arguments = call.arguments
            try:
                output = execute_tool(name, arguments, row_limit=row_limit)
                status = "ok"
                if name == "run_sql_query" and "rows" in output:
                    last_query_result = output
            except Exception as exc:  # The model receives the tool error and can recover.
                output = {"error": str(exc)}
                status = "error"

            tool_call_records.append(
                ToolCallRecord(
                    name=name,
                    arguments=arguments,
                    output_preview=output_preview(output),
                    status=status,
                )
            )
            tool_outputs.append(
                ToolOutput(
                    name=name,
                    call_id=call.call_id,
                    content=json.dumps(output, ensure_ascii=False, default=str),
                )
            )

        if provider.name in {"ollama", "groq"} and last_query_result:
            answer = build_default_answer(last_query_result)
            return build_agent_response(
                question=question,
                answer=answer,
                query_result=last_query_result,
                tool_call_records=tool_call_records,
                provider_name=provider.name,
                model=provider.model,
                include_report=include_report,
            )

    raise AgentError("The agent did not finish after the maximum tool turns.")
