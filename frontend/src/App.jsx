import {
  Activity,
  BarChart3,
  Bot,
  Database,
  FileText,
  History,
  Play,
  Send,
  Sparkles,
  Table2,
} from "lucide-react"
import {
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js"
import { useEffect, useMemo, useRef, useState } from "react"

Chart.register(
  BarController,
  BarElement,
  CategoryScale,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  Tooltip
)

const API_BASE = import.meta.env.VITE_API_BASE_URL || ""

const EXAMPLES = [
  "What are the latest beef and lamb export and production KPIs?",
  "Show the top 10 beef export destinations in 2025.",
  "Compare quarterly beef exports versus production and export share.",
  "Which market insights show the strongest growth signals?",
]

const DIRECT_SQL =
  "SELECT product, period, value, unit FROM vw_latest_kpis ORDER BY product, metric"

const RUNNING_STEPS = [
  "Preparing request",
  "Checking schema context",
  "Calling the selected model",
  "Running approved SQL tools",
  "Summarising result",
]

const REPORT_STEPS = [...RUNNING_STEPS, "Drafting business report"]

function providerStatusLabel(health) {
  if (!health) {
    return "Checking provider"
  }
  if (health.provider === "ollama") {
    return health.available ? "Ollama ready" : "Ollama unavailable"
  }
  if (health.provider === "groq") {
    return health.available ? "Groq ready" : "Groq key needed"
  }
  if (health.provider === "openai") {
    return health.available ? "OpenAI ready" : "OpenAI key needed"
  }
  return health.available ? "Provider ready" : "Provider unavailable"
}

function formatValue(value) {
  if (typeof value === "number") {
    return new Intl.NumberFormat("en-AU", {
      maximumFractionDigits: Math.abs(value) >= 1000 ? 0 : 2,
    }).format(value)
  }
  if (value == null) {
    return "n/a"
  }
  return String(value)
}

async function apiFetch(path, options) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed with ${response.status}`)
  }
  return payload
}

function parseMarkdown(markdown) {
  const lines = (markdown || "").split("\n")
  const blocks = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]
    if (!line.trim()) {
      index += 1
      continue
    }

    if (line.startsWith("```")) {
      const language = line.replace("```", "").trim()
      const codeLines = []
      index += 1
      while (index < lines.length && !lines[index].startsWith("```")) {
        codeLines.push(lines[index])
        index += 1
      }
      blocks.push({ type: "code", language, text: codeLines.join("\n") })
      index += 1
      continue
    }

    if (line.startsWith("# ")) {
      blocks.push({ type: "h1", text: line.replace(/^#\s+/, "") })
      index += 1
      continue
    }

    if (line.startsWith("## ")) {
      blocks.push({ type: "h2", text: line.replace(/^##\s+/, "") })
      index += 1
      continue
    }

    if (line.startsWith("### ")) {
      blocks.push({ type: "h3", text: line.replace(/^###\s+/, "") })
      index += 1
      continue
    }

    if (line.startsWith("- ")) {
      const items = []
      while (index < lines.length && lines[index].startsWith("- ")) {
        items.push(lines[index].replace(/^-\s+/, ""))
        index += 1
      }
      blocks.push({ type: "ul", items })
      continue
    }

    const paragraph = [line]
    index += 1
    while (
      index < lines.length &&
      lines[index].trim() &&
      !lines[index].startsWith("#") &&
      !lines[index].startsWith("- ") &&
      !lines[index].startsWith("```")
    ) {
      paragraph.push(lines[index])
      index += 1
    }
    blocks.push({ type: "p", text: paragraph.join(" ") })
  }

  return blocks
}

function renderInlineMarkdown(text) {
  const parts = String(text).split(/(\*\*[^*]+\*\*)/g)
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>
    }
    return part
  })
}

function MarkdownReport({ markdown, loading }) {
  const blocks = useMemo(() => parseMarkdown(markdown), [markdown])

  if (loading) {
    return (
      <div className="report-loading" aria-live="polite">
        <div className="loader-ring" />
        <div>
          <strong>Generating business report</strong>
          <span>Executive narrative, risks, actions, and data coverage are being prepared.</span>
        </div>
        <div className="report-skeleton">
          <span />
          <span />
          <span />
        </div>
      </div>
    )
  }

  if (!blocks.length) {
    return (
      <div className="empty-state">
        <FileText size={20} />
        <span>The rendered report will appear here.</span>
      </div>
    )
  }

  return (
    <div className="report-render">
      {blocks.map((block, index) => {
        const key = `${block.type}-${index}`
        if (block.type === "h1") {
          return <h1 key={key}>{renderInlineMarkdown(block.text)}</h1>
        }
        if (block.type === "h2") {
          return <h2 key={key}>{renderInlineMarkdown(block.text)}</h2>
        }
        if (block.type === "h3") {
          return <h3 key={key}>{renderInlineMarkdown(block.text)}</h3>
        }
        if (block.type === "ul") {
          return (
            <ul key={key}>
              {block.items.map((item, itemIndex) => (
                <li key={`${item}-${itemIndex}`}>{renderInlineMarkdown(item)}</li>
              ))}
            </ul>
          )
        }
        if (block.type === "code") {
          return (
            <pre className="report-code" key={key}>
              <code>{block.text}</code>
            </pre>
          )
        }
        return <p key={key}>{renderInlineMarkdown(block.text)}</p>
      })}
    </div>
  )
}

function AgentProgress({ loading, progressValue, result, mode, phase }) {
  const completedSteps = result?.progress_steps || []
  const shouldShow = loading || completedSteps.length > 0
  if (!shouldShow) {
    return null
  }

  const steps = phase === "report" ? REPORT_STEPS : RUNNING_STEPS
  const runningStepIndex = Math.min(
    steps.length - 1,
    Math.floor((progressValue / 100) * steps.length)
  )
  const title = loading
    ? phase === "report"
      ? "Report is being drafted"
      : mode === "agent"
      ? "Agent is working"
      : "SQL tool is running"
    : "Process trace"

  return (
    <section className="progress-panel" aria-live="polite">
      <div className="progress-panel__header">
        <div>
          <div className="panel-label">Progress</div>
          <h2>{title}</h2>
        </div>
        <span className="pill">{loading ? `${progressValue}%` : "complete"}</span>
      </div>
      {loading && (
        <>
          <div className="progress-bar" role="progressbar" aria-valuenow={progressValue} aria-valuemin="0" aria-valuemax="100">
            <span style={{ width: `${progressValue}%` }} />
          </div>
          <ol className="progress-steps">
            {steps.map((step, index) => (
              <li
                className={
                  index < runningStepIndex
                    ? "is-complete"
                    : index === runningStepIndex
                      ? "is-active"
                      : ""
                }
                key={step}
              >
                {step}
              </li>
            ))}
          </ol>
          <p>
            Controls are temporarily locked to prevent duplicate requests while the
            current task finishes.
          </p>
        </>
      )}
      {!loading && completedSteps.length > 0 && (
        <ol className="progress-steps progress-steps--compact">
          {completedSteps.map((step, index) => (
            <li className={step.status === "error" ? "is-error" : "is-complete"} key={`${step.label}-${index}`}>
              <span>{step.label}</span>
              {step.detail && <small>{step.detail}</small>}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

function SuggestedChart({ result }) {
  const canvasRef = useRef(null)
  const chartRef = useRef(null)
  const suggestion = result?.chart_suggestion
  const rows = result?.rows || []

  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.destroy()
      chartRef.current = null
    }
    if (!canvasRef.current || !suggestion || rows.length === 0) {
      return undefined
    }

    const xAxis = suggestion.x_axis
    const yAxis = suggestion.y_axis
    if (!xAxis || !yAxis) {
      return undefined
    }

    const labels = [...new Set(rows.map((row) => row[xAxis]))]
    const seriesKey = suggestion.series
    const seriesValues = seriesKey
      ? [...new Set(rows.map((row) => row[seriesKey] || "Value"))]
      : ["Value"]
    const palette = ["#d06d4f", "#69a971", "#e1b654", "#6fa7c8", "#c287d8"]
    const datasets = seriesValues.map((seriesValue, index) => ({
      label: String(seriesValue),
      data: labels.map((label) => {
        const match = rows.find(
          (row) =>
            row[xAxis] === label &&
            (!seriesKey || (row[seriesKey] || "Value") === seriesValue)
        )
        return Number(match?.[yAxis] || 0)
      }),
      borderColor: palette[index % palette.length],
      backgroundColor: `${palette[index % palette.length]}99`,
      borderWidth: 2,
      tension: 0.28,
    }))

    chartRef.current = new Chart(canvasRef.current, {
      type: suggestion.chart_type === "line" ? "line" : "bar",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: { color: "#f4efe4" },
          },
          tooltip: {
            callbacks: {
              label: (context) => `${context.dataset.label}: ${formatValue(context.parsed.y)}`,
            },
          },
        },
        scales: {
          x: {
            ticks: { color: "#c8c0b1" },
            grid: { color: "rgba(255,255,255,0.08)" },
          },
          y: {
            ticks: {
              color: "#c8c0b1",
              callback: (value) => formatValue(Number(value)),
            },
            grid: { color: "rgba(255,255,255,0.08)" },
          },
        },
      },
    })

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy()
        chartRef.current = null
      }
    }
  }, [rows, suggestion])

  if (!suggestion) {
    return (
      <div className="empty-state">
        <BarChart3 size={20} />
        <span>Ask a question that returns numeric data to receive a chart suggestion.</span>
      </div>
    )
  }

  return (
    <div className="chart-block">
      <div className="chart-block__header">
        <div>
          <div className="panel-label">Chart Suggestion</div>
          <h3>{suggestion.title}</h3>
        </div>
        <span className="pill">{suggestion.chart_type}</span>
      </div>
      <div className="chart-canvas">
        <canvas ref={canvasRef} />
      </div>
      <p>{suggestion.reason}</p>
    </div>
  )
}

function ResultTable({ result }) {
  const columns = result?.columns || []
  const rows = result?.rows || []

  if (!rows.length) {
    return (
      <div className="empty-state">
        <Table2 size={20} />
        <span>No rows returned yet.</span>
      </div>
    )
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${index}-${JSON.stringify(row)}`}>
              {columns.map((column) => (
                <td key={column}>{formatValue(row[column])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SchemaPanel({ schema }) {
  const views = useMemo(
    () => (schema?.tables || []).filter((table) => table.type === "view"),
    [schema]
  )
  const tables = useMemo(
    () => (schema?.tables || []).filter((table) => table.type === "table"),
    [schema]
  )

  return (
    <aside className="side-panel">
      <div className="panel-heading">
        <Database size={18} />
        <div>
          <div className="panel-label">SQLite Layer</div>
          <h2>Schema</h2>
        </div>
      </div>
      <div className="schema-list">
        {[...views, ...tables].map((table) => (
          <details key={table.name} open={table.type === "view"}>
            <summary>
              <span>{table.name}</span>
              <small>{table.type}</small>
            </summary>
            <p>{table.description || "No description available."}</p>
            <div className="column-list">
              {table.columns.slice(0, 8).map((column) => (
                <span key={column.name}>
                  {column.name}
                  <small>{column.type || "ANY"}</small>
                </span>
              ))}
            </div>
          </details>
        ))}
      </div>
    </aside>
  )
}

function QuestionComposer({
  activeMode,
  loading,
  question,
  setQuestion,
  sqlText,
  setSqlText,
  submitQuestion,
  runDirectSql,
}) {
  return (
    <section className="composer-shell">
      {activeMode === "agent" ? (
        <form className="composer-box" onSubmit={submitQuestion}>
          <label htmlFor="question-input">Ask the market database</label>
          <div className="composer-row">
            <textarea
              id="question-input"
              value={question}
              disabled={loading}
              onChange={(event) => setQuestion(event.target.value)}
              rows={2}
            />
            <button
              className="primary-button"
              disabled={loading}
              onClick={submitQuestion}
              type="button"
            >
              <Send size={16} />
              {loading ? "Running" : "Ask"}
            </button>
          </div>
          <div className="example-row example-row--compact">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                disabled={loading}
                type="button"
                onClick={() => setQuestion(example)}
              >
                {example}
              </button>
            ))}
          </div>
        </form>
      ) : (
        <form className="composer-box" onSubmit={runDirectSql}>
          <label htmlFor="sql-input">Run read-only SQL</label>
          <div className="composer-row">
            <textarea
              id="sql-input"
              className="code-input"
              value={sqlText}
              disabled={loading}
              onChange={(event) => setSqlText(event.target.value)}
              rows={2}
            />
            <button
              className="primary-button"
              disabled={loading}
              onClick={runDirectSql}
              type="button"
            >
              <Play size={16} />
              {loading ? "Running" : "Run"}
            </button>
          </div>
        </form>
      )}
    </section>
  )
}

export default function App() {
  const [question, setQuestion] = useState(EXAMPLES[0])
  const [sqlText, setSqlText] = useState(DIRECT_SQL)
  const [result, setResult] = useState(null)
  const [sqlResult, setSqlResult] = useState(null)
  const [historyItems, setHistoryItems] = useState([])
  const [activeHistoryId, setActiveHistoryId] = useState(null)
  const [schema, setSchema] = useState(null)
  const [health, setHealth] = useState(null)
  const [activeMode, setActiveMode] = useState("agent")
  const [agentLoading, setAgentLoading] = useState(false)
  const [sqlLoading, setSqlLoading] = useState(false)
  const [reportLoading, setReportLoading] = useState(false)
  const [progressValue, setProgressValue] = useState(0)
  const [error, setError] = useState("")
  const loading = agentLoading || sqlLoading || reportLoading
  const activePhase = reportLoading ? "report" : sqlLoading ? "sql" : "agent"

  useEffect(() => {
    Promise.all([
      apiFetch("/api/health"),
      apiFetch("/api/schema"),
    ])
      .then(([healthPayload, schemaPayload]) => {
        setHealth(healthPayload)
        setSchema(schemaPayload)
      })
      .catch((fetchError) => setError(fetchError.message))
  }, [])

  useEffect(() => {
    if (!loading) {
      return undefined
    }

    setProgressValue(8)
    const timer = window.setInterval(() => {
      setProgressValue((current) => {
        if (current >= 92) {
          return current
        }
        return Math.min(92, current + 7)
      })
    }, 700)

    return () => window.clearInterval(timer)
  }, [loading])

  async function loadReportForResult(basePayload, historyId) {
    setReportLoading(true)
    setProgressValue((current) => Math.max(current, 78))
    try {
      const minimumVisibleDelay = new Promise((resolve) => {
        window.setTimeout(resolve, 1200)
      })
      const [reportPayload] = await Promise.all([
        apiFetch("/api/report", {
          method: "POST",
          body: JSON.stringify({
            question: basePayload.question || question,
            answer: basePayload.answer || "",
            sql: basePayload.sql,
            columns: basePayload.columns || [],
            rows: basePayload.rows || [],
            row_count: basePayload.row_count || 0,
            truncated: Boolean(basePayload.truncated),
            chart_suggestion: basePayload.chart_suggestion,
          }),
        }),
        minimumVisibleDelay,
      ])
      const enrichedPayload = {
        ...basePayload,
        ...reportPayload,
        report_pending: false,
      }
      setResult(enrichedPayload)
      setHistoryItems((items) =>
        items.map((item) =>
          item.id === historyId ? { ...item, result: enrichedPayload } : item
        )
      )
    } catch (reportError) {
      setError(`Report generation failed: ${reportError.message}`)
      setResult((current) =>
        current ? { ...current, report_pending: false } : current
      )
      setHistoryItems((items) =>
        items.map((item) =>
          item.id === historyId
            ? { ...item, result: { ...item.result, report_pending: false } }
            : item
        )
      )
    } finally {
      setProgressValue(100)
      setReportLoading(false)
    }
  }

  async function submitQuestion(event) {
    event.preventDefault()
    if (loading) {
      return
    }
    setAgentLoading(true)
    setError("")
    setResult(null)
    setSqlResult(null)
    setActiveHistoryId(null)
    try {
      const payload = await apiFetch("/api/chat", {
        method: "POST",
        body: JSON.stringify({ question, row_limit: 120, include_report: false }),
      })
      setResult(payload)
      const historyItem = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        mode: "agent",
        question,
        result: payload,
        createdAt: new Date().toLocaleString(),
      }
      setHistoryItems((items) => [historyItem, ...items].slice(0, 12))
      setActiveHistoryId(historyItem.id)
      setAgentLoading(false)
      await loadReportForResult(payload, historyItem.id)
    } catch (submitError) {
      setError(submitError.message)
    } finally {
      setProgressValue(100)
      setAgentLoading(false)
    }
  }

  async function runDirectSql(event) {
    event.preventDefault()
    if (loading) {
      return
    }
    setSqlLoading(true)
    setError("")
    setResult(null)
    setSqlResult(null)
    setActiveHistoryId(null)
    try {
      const payload = await apiFetch("/api/sql", {
        method: "POST",
        body: JSON.stringify({ sql: sqlText, row_limit: 120 }),
      })
      setSqlResult(payload)
      const historyItem = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        mode: "sql",
        question: sqlText,
        result: payload,
        createdAt: new Date().toLocaleString(),
      }
      setHistoryItems((items) => [historyItem, ...items].slice(0, 12))
      setActiveHistoryId(historyItem.id)
    } catch (submitError) {
      setError(submitError.message)
    } finally {
      setProgressValue(100)
      setSqlLoading(false)
    }
  }

  const activeHistory = historyItems.find((item) => item.id === activeHistoryId)
  const visibleResult = activeHistory
    ? activeHistory.result
    : activeMode === "agent"
      ? result
      : sqlResult
  const visibleMode = activeHistory?.mode || activeMode

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">
            <Bot size={20} />
          </span>
          <div>
            <div className="panel-label">Australian Market Intelligence</div>
            <h1>Beef & Lamb AI Agent</h1>
          </div>
        </div>
        <div className="status-row">
          <span className={`status-dot ${health?.available ? "is-live" : ""}`} />
          <span>{providerStatusLabel(health)}</span>
          <span className="pill">{health?.provider || "groq"}</span>
          <span className="pill">{health?.model || "llama-3.1-8b-instant"}</span>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          <Activity size={18} />
          <span>{error}</span>
        </div>
      )}

      <section className="workspace">
        <div className="main-panel" aria-busy={loading}>
          <div className="mode-tabs">
            <button
              className={activeMode === "agent" ? "is-active" : ""}
              disabled={loading}
              type="button"
              onClick={() => setActiveMode("agent")}
            >
              <Sparkles size={16} />
              Natural Language
            </button>
            <button
              className={activeMode === "sql" ? "is-active" : ""}
              disabled={loading}
              type="button"
              onClick={() => setActiveMode("sql")}
            >
              <Database size={16} />
              SQL Tool
            </button>
          </div>

          {historyItems.length > 0 && (
            <section className="history-panel">
              <div className="history-panel__header">
                <div>
                  <div className="panel-label">History</div>
                  <h2>Previous questions</h2>
                </div>
                <History size={18} />
              </div>
              <div className="history-list">
                {historyItems.map((item) => (
                  <button
                    className={item.id === activeHistoryId ? "is-active" : ""}
                    disabled={loading}
                    key={item.id}
                    type="button"
                    onClick={() => {
                      setActiveHistoryId(item.id)
                      setActiveMode(item.mode)
                      if (item.mode === "agent") {
                        setQuestion(item.question)
                      } else {
                        setSqlText(item.question)
                      }
                    }}
                  >
                    <span>{item.question}</span>
                    <small>{item.mode.toUpperCase()} · {item.createdAt}</small>
                  </button>
                ))}
              </div>
            </section>
          )}

          <AgentProgress
            loading={loading}
            progressValue={progressValue}
            result={visibleResult}
            mode={activeMode}
            phase={activePhase}
          />

          <section className="answer-grid">
            <article className="answer-card answer-card--summary">
              <div className="panel-heading">
                <Sparkles size={18} />
                <div>
                  <div className="panel-label">Result Summary</div>
                  <h2>Answer</h2>
                </div>
              </div>
              <p className="answer-text">
                {visibleMode === "agent"
                  ? visibleResult?.answer || "The agent response will appear here."
                  : visibleResult
                    ? `SQL returned ${visibleResult.row_count} rows in ${visibleResult.elapsed_ms} ms.`
                    : "Run a direct SQL query to inspect the database."}
              </p>
              {visibleResult?.sql && (
                <pre className="sql-block"><code>{visibleResult.sql}</code></pre>
              )}
            </article>

            <article className="answer-card">
              <SuggestedChart result={visibleResult} />
            </article>
          </section>

          <section className="answer-card">
            <div className="panel-heading">
              <Table2 size={18} />
              <div>
                <div className="panel-label">Data Preview</div>
                <h2>Rows</h2>
              </div>
            </div>
            <ResultTable result={visibleResult} />
          </section>

          {visibleMode === "agent" && (
            <section className="answer-card">
              <div className="panel-heading">
                <FileText size={18} />
                <div>
                  <div className="panel-label">Generated Report</div>
                  <h2>Report</h2>
                </div>
              </div>
              <MarkdownReport
                loading={reportLoading && Boolean(visibleResult?.report_pending)}
                markdown={visibleResult?.report_markdown}
              />
            </section>
          )}
        </div>

        <SchemaPanel schema={schema} />
      </section>

      <QuestionComposer
        activeMode={activeMode}
        loading={loading}
        question={question}
        setQuestion={setQuestion}
        sqlText={sqlText}
        setSqlText={setSqlText}
        submitQuestion={submitQuestion}
        runDirectSql={runDirectSql}
      />
    </main>
  )
}
