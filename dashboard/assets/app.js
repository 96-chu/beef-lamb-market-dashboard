const state = {
  payload: null,
  reportIndex: 0,
  reportTimer: null,
  heroStepIndex: 0,
  heroStepTimer: null,
  pipelineIndex: 0,
  pipelineTimer: null,
  destinationProduct: "beef",
  charts: {},
}

const COLORS = {
  beef: "#b56144",
  lamb: "#7c9a57",
  mutton: "#d09b43",
  navy: "#4f738d",
  olive: "#698754",
  sand: "#e8dac1",
  text: "#f4efe4",
  muted: "rgba(244, 239, 228, 0.72)",
  grid: "rgba(255,255,255,0.12)",
}

const MARKET_META = [
  { match: ["USA East"], label: "USA East", code: "US" },
  { match: ["USA West"], label: "USA West", code: "US" },
  { match: ["Canada East"], label: "Canada East", code: "CA" },
  { match: ["Canada West"], label: "Canada West", code: "CA" },
  { match: ["United Kingdom"], label: "United Kingdom", code: "UK" },
  { match: ["South Korea"], label: "South Korea", code: "KR" },
  { match: ["Papua New Guinea"], label: "Papua New Guinea", code: "PG" },
  { match: ["Saudi Arabia"], label: "Saudi Arabia", code: "SA" },
  { match: ["New Zealand"], label: "New Zealand", code: "NZ" },
  { match: ["South Africa"], label: "South Africa", code: "ZA" },
  { match: ["Pacific Islands"], label: "Pacific Islands", code: "PI" },
  { match: ["Philippines"], label: "Philippines", code: "PH" },
  { match: ["Indonesia"], label: "Indonesia", code: "ID" },
  { match: ["Thailand"], label: "Thailand", code: "TH" },
  { match: ["Malaysia"], label: "Malaysia", code: "MY" },
  { match: ["Singapore"], label: "Singapore", code: "SG" },
  { match: ["Hong Kong"], label: "Hong Kong", code: "HK" },
  { match: ["Taiwan"], label: "Taiwan", code: "TW" },
  { match: ["China"], label: "China", code: "CN" },
  { match: ["Japan"], label: "Japan", code: "JP" },
  { match: ["Dubai"], label: "Dubai", code: "AE" },
  { match: ["Qatar"], label: "Qatar", code: "QA" },
  { match: ["Kuwait"], label: "Kuwait", code: "KW" },
  { match: ["Jordan"], label: "Jordan", code: "JO" },
  { match: ["Iran"], label: "Iran", code: "IR" },
  { match: ["Bahrain"], label: "Bahrain", code: "BH" },
]

// Keep null or missing chart values from breaking arithmetic or Chart.js rendering.
function safeNumber(value) {
  return value == null ? 0 : value
}

function formatValue(value) {
  return new Intl.NumberFormat("en-AU", {
    maximumFractionDigits: value >= 1000 ? 0 : 2,
  }).format(value)
}

function formatUnitValue(value, unit) {
  if (value == null || Number.isNaN(Number(value))) {
    return "n/a"
  }
  if (unit === "percent") {
    return `${Number(value).toFixed(1)}%`
  }
  if (unit === "percentage_points") {
    return `${Number(value).toFixed(1)} pts`
  }
  if (unit === "tonnes") {
    return `${formatValue(Number(value))} tonnes`
  }
  return formatValue(Number(value))
}

function formatShortTonnes(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "n/a"
  }
  return formatValue(Number(value))
}

function getDirectionMeta(direction) {
  const labels = {
    strong_growth: "Strong growth",
    growth: "Growth",
    rising: "Rising",
    high_concentration: "High concentration",
    balanced: "Balanced",
    stable: "Stable",
    decline: "Decline",
    strong_decline: "Strong decline",
    falling: "Falling",
    not_available: "Not available",
  }
  const positive = ["strong_growth", "growth", "rising"]
  const negative = ["strong_decline", "decline", "falling"]
  const risk = ["high_concentration"]
  const neutral = ["balanced", "stable"]

  if (positive.includes(direction)) {
    return { label: labels[direction], icon: "↑", tone: "positive" }
  }
  if (negative.includes(direction)) {
    return { label: labels[direction], icon: "↓", tone: "negative" }
  }
  if (risk.includes(direction)) {
    return { label: labels[direction], icon: "!", tone: "risk" }
  }
  if (neutral.includes(direction)) {
    return { label: labels[direction], icon: "•", tone: "neutral" }
  }
  return { label: labels[direction] || direction.replace(/_/g, " "), icon: "•", tone: "neutral" }
}

function getMarketMeta(item) {
  if (!item.title.includes("Destination")) {
    return null
  }

  if (item.title.includes("Destination concentration")) {
    return { label: "Top 4 markets", code: "T4" }
  }

  const source = `${item.businessSignal} ${item.narrative}`
  return MARKET_META.find((market) =>
    market.match.some((token) => source.includes(token))
  ) || null
}

function getRevealRoot(target) {
  if (!target) {
    return null
  }

  return target.classList.contains("reveal")
    ? target
    : target.closest(".reveal")
}

function revealElement(target) {
  const revealRoot = getRevealRoot(target)
  if (revealRoot) {
    revealRoot.classList.add("is-visible")
  }
}

function buildOverview(payload) {
  const heroTitle = document.getElementById("hero-title")
  const heroSubtitle = document.getElementById("hero-subtitle")
  const windowPill = document.getElementById("window-pill")
  const generatedPill = document.getElementById("generated-pill")
  const coveragePill = document.getElementById("coverage-pill")
  const coverageGrid = document.getElementById("hero-coverage")
  const heroRail = document.getElementById("hero-rail")
  const heroSpotlight = document.getElementById("hero-spotlight")

  heroTitle.textContent = payload.meta.project_title
  heroSubtitle.textContent = payload.meta.subtitle
  windowPill.textContent = `Window: ${payload.meta.data_window.start} to ${payload.meta.data_window.end}`
  generatedPill.textContent = `Generated: ${payload.meta.generated_at_utc}`
  coveragePill.textContent = `${payload.meta.coverage.quarters_in_scope} quarters in scope`

  const stats = [
    ["Export release months", payload.meta.coverage.export_release_months],
    ["Production release folders", payload.meta.coverage.production_release_folders],
    ["Clean export rows", payload.meta.coverage.clean_export_rows],
    ["Clean production rows", payload.meta.coverage.clean_production_rows],
  ]

  coverageGrid.innerHTML = stats
    .map(
      ([label, value]) => `
        <div class="mini-stat">
          <span class="mini-stat__label">${label}</span>
          <span class="mini-stat__value">${formatValue(value)}</span>
        </div>
      `
    )
    .join("")

  const miniPipeline = [
    {
      index: "01",
      label: "Source Intake",
      meta: "ABS quarterly releases and DAFF monthly destination reports",
      detail:
        "Folder-based release storage preserves the raw lineage for every production and export update before any transformations are applied.",
      target: "#sources",
      targetLabel: "Sources",
    },
    {
      index: "02",
      label: "Cleaning",
      meta: "Deduplicate overlapping releases and standardize business fields",
      detail:
        "The cleaning layer keeps only ABS Original series, removes DAFF subtotal destinations, and resolves overlapping release history using latest-release logic.",
      target: "#pipeline",
      targetLabel: "Pipeline",
    },
    {
      index: "03",
      label: "Aggregation",
      meta: "Build quarterly exports and compact market summary tables",
      detail:
        "Monthly export flows are rolled into quarterly totals, then merged with Australia-level production and slaughter signals for a business reporting layer.",
      target: "#reports",
      targetLabel: "Reports",
    },
    {
      index: "04",
      label: "Static Delivery",
      meta: "Package JSON, charts, and dashboard assets for GitHub Pages",
      detail:
        "The final dashboard ships as a static site with exported JSON, pre-rendered report images, and interactive front-end charts.",
      target: "#controls",
      targetLabel: "Controls",
    },
  ]

  heroRail.innerHTML = `
    <div class="rail-line"></div>
    ${miniPipeline
      .map(
        (step, index) => `
          <button class="rail-step ${index === 0 ? "is-active" : ""}" data-index="${index}" data-target="${step.target}" type="button">
            <span class="rail-step__index">${step.index}</span>
            <div class="rail-node"></div>
            <div class="rail-step__content">
              <div class="rail-step__label">${step.label}</div>
              <div class="rail-step__meta">${step.meta}</div>
            </div>
            <span class="rail-step__target">${step.targetLabel}</span>
          </button>
        `
      )
      .join("")}
  `

  heroSpotlight.innerHTML = `
    <div class="panel__label">Process Spotlight</div>
    <h3 class="hero-panel__spotlight-title"></h3>
    <p class="hero-panel__spotlight-copy"></p>
    <a class="hero-panel__spotlight-link" href="#sources">Jump to section</a>
  `

  const spotlightTitle = heroSpotlight.querySelector(".hero-panel__spotlight-title")
  const spotlightCopy = heroSpotlight.querySelector(".hero-panel__spotlight-copy")
  const spotlightLink = heroSpotlight.querySelector(".hero-panel__spotlight-link")
  const stepButtons = Array.from(heroRail.querySelectorAll(".rail-step"))

  const setHeroStep = (index) => {
    state.heroStepIndex = index
    const step = miniPipeline[index]
    stepButtons.forEach((button, buttonIndex) => {
      button.classList.toggle("is-active", buttonIndex === index)
    })
    spotlightTitle.textContent = step.label
    spotlightCopy.textContent = step.detail
    spotlightLink.textContent = `Jump to ${step.targetLabel}`
    spotlightLink.setAttribute("href", step.target)
  }

  const stopHeroStepAutoplay = () => {
    if (state.heroStepTimer) {
      window.clearInterval(state.heroStepTimer)
      state.heroStepTimer = null
    }
  }

  const startHeroStepAutoplay = () => {
    stopHeroStepAutoplay()
    state.heroStepTimer = window.setInterval(() => {
      const nextIndex = (state.heroStepIndex + 1) % miniPipeline.length
      setHeroStep(nextIndex)
    }, 4200)
  }

  stepButtons.forEach((button, index) => {
    button.addEventListener("click", () => {
      setHeroStep(index)
      const target = document.querySelector(button.dataset.target)
      if (target) {
        revealElement(target)
        target.scrollIntoView({ behavior: "smooth", block: "start" })
      }
      startHeroStepAutoplay()
    })
    button.addEventListener("mouseenter", stopHeroStepAutoplay)
    button.addEventListener("mouseleave", startHeroStepAutoplay)
  })

  heroSpotlight.addEventListener("mouseenter", stopHeroStepAutoplay)
  heroSpotlight.addEventListener("mouseleave", startHeroStepAutoplay)

  setHeroStep(0)
  startHeroStepAutoplay()
}

function buildKpis(payload) {
  const kpiGrid = document.getElementById("kpi-grid")
  const accentMap = {
    copper: "var(--copper)",
    moss: "var(--moss)",
    navy: "var(--navy)",
    olive: "var(--olive)",
  }

  kpiGrid.innerHTML = payload.kpis
    .map(
      (item) => `
        <article class="kpi-card" style="--accent: ${accentMap[item.accent] || "var(--sand)"}">
          <div class="panel__label">Latest Observation</div>
          <div class="kpi-card__label">${item.label}</div>
          <div class="kpi-card__value">${formatValue(item.value)}</div>
          <div class="kpi-card__meta">${item.unit} | ${item.period}</div>
        </article>
      `
    )
    .join("")
}

function updateReportStage(index) {
  const slides = state.payload.reportSlides
  const stage = document.getElementById("report-stage")
  const image = document.getElementById("report-image")
  const title = document.getElementById("report-title")
  const caption = document.getElementById("report-caption")
  const dots = document.querySelectorAll(".report-dot")
  const thumbs = document.querySelectorAll(".report-thumb")
  const counter = document.getElementById("report-counter")
  const progressBar = document.getElementById("report-progress-bar")
  const item = slides[index]

  stage.classList.add("is-transitioning")
  image.src = item.image
  image.alt = item.title
  title.textContent = item.title
  caption.textContent = item.caption
  counter.textContent = `${String(index + 1).padStart(2, "0")} / ${String(slides.length).padStart(2, "0")}`

  dots.forEach((dot, dotIndex) => {
    dot.classList.toggle("is-active", dotIndex === index)
  })
  thumbs.forEach((thumb, thumbIndex) => {
    thumb.classList.toggle("is-active", thumbIndex === index)
  })

  if (progressBar) {
    progressBar.style.animation = "none"
    progressBar.offsetHeight
    progressBar.style.animation = ""
  }

  window.setTimeout(() => {
    stage.classList.remove("is-transitioning")
  }, 220)
}

function startReportAutoplay() {
  stopReportAutoplay()
  const stage = document.getElementById("report-stage")
  stage.classList.add("is-autoplaying")
  state.reportTimer = window.setInterval(() => {
    state.reportIndex = (state.reportIndex + 1) % state.payload.reportSlides.length
    updateReportStage(state.reportIndex)
  }, 6500)
}

function stopReportAutoplay() {
  if (state.reportTimer) {
    window.clearInterval(state.reportTimer)
    state.reportTimer = null
  }
  const stage = document.getElementById("report-stage")
  if (stage) {
    stage.classList.remove("is-autoplaying")
  }
}

function buildReportCarousel(payload) {
  const dotsWrap = document.getElementById("report-dots")
  const stage = document.getElementById("report-stage")
  const thumbsWrap = document.getElementById("report-thumbs")
  const image = document.getElementById("report-image")
  const zoomButton = document.getElementById("report-zoom")
  const lightbox = document.getElementById("report-lightbox")
  const lightboxImage = document.getElementById("lightbox-image")
  const lightboxTitle = document.getElementById("lightbox-title")
  const lightboxBackdrop = document.getElementById("lightbox-backdrop")
  const lightboxClose = document.getElementById("lightbox-close")
  let touchStartX = null

  dotsWrap.innerHTML = payload.reportSlides
    .map(
      (_, index) =>
        `<button class="report-dot ${index === 0 ? "is-active" : ""}" data-index="${index}" type="button" aria-label="View report ${index + 1}"></button>`
    )
    .join("")

  thumbsWrap.innerHTML = payload.reportSlides
    .map(
      (slide, index) => `
        <button class="report-thumb ${index === 0 ? "is-active" : ""}" data-index="${index}" type="button" aria-label="Open ${slide.title}">
          <img src="${slide.image}" alt="${slide.title}" loading="lazy" />
          <span class="report-thumb__caption">${slide.title}</span>
        </button>
      `
    )
    .join("")

  dotsWrap.querySelectorAll(".report-dot").forEach((dot) => {
    dot.addEventListener("click", () => {
      state.reportIndex = Number(dot.dataset.index)
      updateReportStage(state.reportIndex)
      startReportAutoplay()
    })
  })

  thumbsWrap.querySelectorAll(".report-thumb").forEach((thumb) => {
    thumb.addEventListener("click", () => {
      state.reportIndex = Number(thumb.dataset.index)
      updateReportStage(state.reportIndex)
      startReportAutoplay()
    })
  })

  document.getElementById("report-prev").addEventListener("click", () => {
    state.reportIndex =
      (state.reportIndex - 1 + payload.reportSlides.length) % payload.reportSlides.length
    updateReportStage(state.reportIndex)
    startReportAutoplay()
  })

  document.getElementById("report-next").addEventListener("click", () => {
    state.reportIndex = (state.reportIndex + 1) % payload.reportSlides.length
    updateReportStage(state.reportIndex)
    startReportAutoplay()
  })

  stage.addEventListener("mouseenter", stopReportAutoplay)
  stage.addEventListener("mouseleave", startReportAutoplay)
  stage.addEventListener("touchstart", (event) => {
    touchStartX = event.changedTouches[0].clientX
    stopReportAutoplay()
  }, { passive: true })
  stage.addEventListener("touchend", (event) => {
    if (touchStartX == null) {
      return
    }
    const touchEndX = event.changedTouches[0].clientX
    const deltaX = touchEndX - touchStartX
    touchStartX = null

    if (Math.abs(deltaX) > 40) {
      if (deltaX < 0) {
        state.reportIndex = (state.reportIndex + 1) % payload.reportSlides.length
      } else {
        state.reportIndex =
          (state.reportIndex - 1 + payload.reportSlides.length) % payload.reportSlides.length
      }
      updateReportStage(state.reportIndex)
    }
    startReportAutoplay()
  }, { passive: true })

  const openLightbox = () => {
    const activeSlide = payload.reportSlides[state.reportIndex]
    lightboxImage.src = activeSlide.image
    lightboxImage.alt = activeSlide.title
    lightboxTitle.textContent = activeSlide.title
    lightbox.classList.add("is-open")
    lightbox.setAttribute("aria-hidden", "false")
    document.body.style.overflow = "hidden"
  }

  const closeLightbox = () => {
    lightbox.classList.remove("is-open")
    lightbox.setAttribute("aria-hidden", "true")
    document.body.style.overflow = ""
  }

  image.addEventListener("click", openLightbox)
  zoomButton.addEventListener("click", openLightbox)
  lightboxBackdrop.addEventListener("click", closeLightbox)
  lightboxClose.addEventListener("click", closeLightbox)
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && lightbox.classList.contains("is-open")) {
      closeLightbox()
    }
  })

  updateReportStage(0)
  startReportAutoplay()
}

function buildBusinessReport(payload) {
  const report = payload.businessReport
  if (!report) {
    return
  }

  document.getElementById("business-report-title").textContent = report.title
  document.getElementById("business-report-subtitle").textContent = report.subtitle
  document.getElementById("forecast-title").textContent = `${report.forecast.year} baseline outlook`
  document.getElementById("forecast-model").textContent = report.forecast.model
  document.getElementById("forecast-method-note").textContent = report.forecast.methodNote

  document.getElementById("business-summary").innerHTML = report.executiveSummary
    .map((point) => `<li>${point}</li>`)
    .join("")

  document.getElementById("forecast-cards").innerHTML = report.forecast.annualBaseCards
    .map(
      (item) => `
        <div class="forecast-metric forecast-metric--${item.product}">
          <span class="forecast-metric__label">${item.label}</span>
          <span class="forecast-metric__value">${item.valueLabel}</span>
          <span class="forecast-metric__period">${item.period} | base case</span>
        </div>
      `
    )
    .join("")

  document.getElementById("business-insight-grid").innerHTML = report.keyFindings
    .map((item) => {
      const direction = getDirectionMeta(item.direction)
      const market = getMarketMeta(item)
      return `
        <article class="insight-card ${market ? "insight-card--market" : ""} insight-card--${direction.tone} insight-card--${item.direction}">
          ${
            market
              ? `<div class="market-watermark" aria-hidden="true">${market.code}</div>`
              : ""
          }
          <div class="insight-card__topline">
            <span class="panel__label">${item.category}</span>
            <span class="direction-pill direction-pill--${direction.tone}">
              <span class="direction-pill__icon">${direction.icon}</span>
              <span>${direction.label}</span>
            </span>
          </div>
          ${
            market
              ? `<div class="market-badge">
                  <span class="market-badge__icon">${market.code}</span>
                  <span class="market-badge__text">${market.label}</span>
                </div>`
              : ""
          }
          <h3>${item.title}</h3>
          <div class="insight-card__metric">
            <span>${item.valueLabel}</span>
            ${
              item.changeLabel && item.changeLabel !== "not available"
                ? `<small>${item.changeLabel}</small>`
                : ""
            }
          </div>
          <p>${item.narrative}</p>
          <div class="insight-card__action">${item.recommendation}</div>
        </article>
      `
    })
    .join("")

  const scenarioRows = report.forecast.scenarioSummary
  // The mobile layout turns each row into a stacked card, so each value cell
  // needs its own label for small screens.
  document.getElementById("forecast-scenario-table").innerHTML = `
    <thead>
      <tr>
        <th>Product</th>
        <th>Conservative exports</th>
        <th>Base exports</th>
        <th>High exports</th>
        <th>Base export share</th>
      </tr>
    </thead>
    <tbody>
      ${scenarioRows
        .map(
          (item) => `
            <tr>
              <td data-label="Product">${item.label}</td>
              <td data-label="Conservative exports">${formatUnitValue(item.exports.conservative, "tonnes")}</td>
              <td data-label="Base exports">${formatUnitValue(item.exports.base, "tonnes")}</td>
              <td data-label="High exports">${formatUnitValue(item.exports.high, "tonnes")}</td>
              <td data-label="Base export share">${formatUnitValue(item.exportShare.base, "percent")}</td>
            </tr>
          `
        )
        .join("")}
    </tbody>
  `

  const forecastCanvas = document.getElementById("forecast-scenario-chart")
  state.charts.forecast = new Chart(forecastCanvas, {
    type: "bar",
    data: {
      labels: scenarioRows.map((item) => item.label),
      datasets: [
        {
          label: "Conservative",
          data: scenarioRows.map((item) => item.exports.conservative),
          backgroundColor: "rgba(215, 200, 173, 0.58)",
          borderRadius: 8,
        },
        {
          label: "Base",
          data: scenarioRows.map((item) => item.exports.base),
          backgroundColor: COLORS.beef,
          borderRadius: 8,
        },
        {
          label: "High",
          data: scenarioRows.map((item) => item.exports.high),
          backgroundColor: COLORS.lamb,
          borderRadius: 8,
        },
      ],
    },
    options: {
      ...chartBaseOptions(),
      plugins: {
        ...chartBaseOptions().plugins,
        tooltip: {
          ...chartBaseOptions().plugins.tooltip,
          callbacks: {
            label(context) {
              return `${context.dataset.label}: ${formatShortTonnes(context.raw)} tonnes`
            },
          },
        },
      },
    },
  })

  document.getElementById("impact-grid").innerHTML = report.impactFactors
    .map(
      (item) => `
        <article class="impact-card">
          <div class="panel__label">${item.pressure}</div>
          <h3>${item.factor}</h3>
          <p>${item.businessImpact}</p>
          <div class="impact-card__forecast">${item.forecastUse}</div>
          <div class="watch-list">
            ${item.watchMetrics.map((metric) => `<span>${metric}</span>`).join("")}
          </div>
        </article>
      `
    )
    .join("")

  document.getElementById("recommendation-list").innerHTML = report.recommendations
    .map((point) => `<li>${point}</li>`)
    .join("")

  document.getElementById("forecast-limitations").innerHTML = report.limitations
    .map((point) => `<li>${point}</li>`)
    .join("")
}

function chartBaseOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: "index",
      intersect: false,
      axis: "x",
    },
    hover: {
      mode: "index",
      intersect: false,
    },
    events: ["mousemove", "mouseout", "click", "touchstart", "touchmove"],
    animation: {
      duration: 900,
      easing: "easeOutCubic",
    },
    elements: {
      point: {
        hoverRadius: 7,
        hitRadius: 18,
      },
      line: {
        borderWidth: 2.5,
      },
    },
    plugins: {
      legend: {
        labels: {
          color: COLORS.text,
          font: {
            family: "IBM Plex Sans",
          },
        },
      },
      tooltip: {
        backgroundColor: "rgba(10, 15, 16, 0.92)",
        titleColor: COLORS.text,
        bodyColor: COLORS.text,
        borderColor: "rgba(255,255,255,0.08)",
        borderWidth: 1,
        padding: 12,
        callbacks: {
          label(context) {
            let value = context.raw
            if (context.chart && context.chart.options.indexAxis === "y" && context.parsed && context.parsed.x != null) {
              value = context.parsed.x
            } else if (context.parsed && context.parsed.y != null) {
              value = context.parsed.y
            } else if (context.parsed && context.parsed.x != null) {
              value = context.parsed.x
            }
            return `${context.dataset.label}: ${formatShortTonnes(value)} tonnes`
          },
        },
      },
    },
    scales: {
      x: {
        ticks: { color: COLORS.muted },
        grid: { color: "rgba(255,255,255,0.04)" },
      },
      y: {
        ticks: {
          color: COLORS.muted,
          callback(value) {
            return formatValue(value)
          },
        },
        grid: { color: COLORS.grid },
      },
    },
  }
}

function buildCharts(payload) {
  const productionLabels = payload.analytics.productionTrend.map((item) => item.label)
  state.charts.production = new Chart(
    document.getElementById("production-trend-chart"),
    {
      type: "line",
      data: {
        labels: productionLabels,
        datasets: [
          {
            label: "Beef",
            data: payload.analytics.productionTrend.map((item) => safeNumber(item.beef)),
            borderColor: COLORS.beef,
            backgroundColor: "rgba(181, 97, 68, 0.16)",
            pointRadius: 4,
            pointHoverRadius: 7,
            pointHitRadius: 18,
            tension: 0.28,
          },
          {
            label: "Lamb",
            data: payload.analytics.productionTrend.map((item) => safeNumber(item.lamb)),
            borderColor: COLORS.lamb,
            backgroundColor: "rgba(124, 154, 87, 0.16)",
            pointRadius: 4,
            pointHoverRadius: 7,
            pointHitRadius: 18,
            tension: 0.28,
          },
        ],
      },
      options: chartBaseOptions(),
    }
  )

  const exportsLabels = payload.analytics.exportsTrend.map((item) => item.label)
  state.charts.exports = new Chart(document.getElementById("exports-trend-chart"), {
    type: "line",
    data: {
      labels: exportsLabels,
      datasets: [
        {
          label: "Beef",
          data: payload.analytics.exportsTrend.map((item) => safeNumber(item.beef)),
          borderColor: COLORS.beef,
          backgroundColor: "rgba(181, 97, 68, 0.14)",
          pointRadius: 3,
          pointHoverRadius: 7,
          pointHitRadius: 18,
          tension: 0.24,
        },
        {
          label: "Lamb",
          data: payload.analytics.exportsTrend.map((item) => safeNumber(item.lamb)),
          borderColor: COLORS.lamb,
          backgroundColor: "rgba(124, 154, 87, 0.14)",
          pointRadius: 3,
          pointHoverRadius: 7,
          pointHitRadius: 18,
          tension: 0.24,
        },
      ],
    },
    options: chartBaseOptions(),
  })

  state.charts.mix = new Chart(document.getElementById("mix-chart"), {
    type: "bar",
    data: {
      labels: payload.analytics.exportMix.map((item) => item.label),
      datasets: [
        {
          label: "Beef",
          data: payload.analytics.exportMix.map((item) => safeNumber(item.beef)),
          backgroundColor: COLORS.beef,
        },
        {
          label: "Lamb",
          data: payload.analytics.exportMix.map((item) => safeNumber(item.lamb)),
          backgroundColor: COLORS.lamb,
        },
        {
          label: "Mutton",
          data: payload.analytics.exportMix.map((item) => safeNumber(item.mutton)),
          backgroundColor: COLORS.mutton,
        },
      ],
    },
    options: {
      ...chartBaseOptions(),
      scales: {
        x: { stacked: true, ticks: { color: COLORS.muted }, grid: { color: "rgba(255,255,255,0.04)" } },
        y: { stacked: true, ticks: { color: COLORS.muted, callback: (value) => formatValue(value) }, grid: { color: COLORS.grid } },
      },
    },
  })

  state.charts.destinations = new Chart(
    document.getElementById("destinations-chart"),
    {
      type: "bar",
      data: {
        labels: [],
        datasets: [
          {
            label: "Tonnes",
            data: [],
            backgroundColor: COLORS.beef,
            borderRadius: 10,
          },
        ],
      },
      options: {
        ...chartBaseOptions(),
        indexAxis: "y",
        interaction: {
          mode: "index",
          intersect: false,
          axis: "y",
        },
        hover: {
          mode: "index",
          intersect: false,
          axis: "y",
        },
        plugins: {
          ...chartBaseOptions().plugins,
          legend: { display: false },
        },
        scales: {
          x: {
            ticks: {
              color: COLORS.muted,
              callback(value) {
                return formatValue(value)
              },
            },
            grid: { color: "rgba(255,255,255,0.04)" },
          },
          y: {
            type: "category",
            ticks: {
              color: COLORS.muted,
              autoSkip: false,
              callback(value) {
                const destinationChart = state.charts.destinations
                const labels = destinationChart ? destinationChart.data.labels : []
                return labels[value] || this.getLabelForValue(value)
              },
            },
            grid: { color: COLORS.grid },
          },
        },
      },
    }
  )

  state.charts.comparison = new Chart(document.getElementById("comparison-chart"), {
    type: "bar",
    data: {
      labels: payload.analytics.productionVsExports.map((item) => item.label),
      datasets: [
        {
          label: "Beef Production",
          data: payload.analytics.productionVsExports.map((item) => safeNumber(item.beef_production)),
          backgroundColor: COLORS.navy,
          borderRadius: 8,
        },
        {
          label: "Beef Exports",
          data: payload.analytics.productionVsExports.map((item) => safeNumber(item.beef_exports)),
          backgroundColor: COLORS.beef,
          borderRadius: 8,
        },
        {
          label: "Lamb Production",
          data: payload.analytics.productionVsExports.map((item) => safeNumber(item.lamb_production)),
          backgroundColor: COLORS.olive,
          borderRadius: 8,
        },
        {
          label: "Lamb Exports",
          data: payload.analytics.productionVsExports.map((item) => safeNumber(item.lamb_exports)),
          backgroundColor: COLORS.lamb,
          borderRadius: 8,
        },
      ],
    },
    options: chartBaseOptions(),
  })

  updateDestinationChart(state.destinationProduct)
}

function updateDestinationChart(product) {
  const chart = state.charts.destinations
  const data = state.payload.analytics.topDestinations[product]
  const labels = data.map((item) => item.destination)
  chart.data.labels = labels
  chart.data.datasets[0].data = data.map((item) => item.tonnes)
  chart.data.datasets[0].backgroundColor = product === "beef" ? COLORS.beef : COLORS.lamb
  chart.options.scales.y.ticks.callback = (value, index) =>
    labels[value] || labels[index] || ""
  chart.update()
}

function buildDestinationToggle() {
  const buttons = document.querySelectorAll("#destination-toggle .segmented__button")
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      buttons.forEach((item) => item.classList.remove("is-active"))
      button.classList.add("is-active")
      state.destinationProduct = button.dataset.product
      updateDestinationChart(state.destinationProduct)
    })
  })
}

function updateSeriesFilter(chartKey, series) {
  const chart = state.charts[chartKey]
  if (!chart) {
    return
  }

  chart.data.datasets.forEach((dataset, index) => {
    const datasetKey = dataset.label.toLowerCase()
    chart.setDatasetVisibility(index, series === "both" || datasetKey === series)
  })
  chart.update()
}

function buildSeriesToggles() {
  document.querySelectorAll(".chart-series-toggle").forEach((toggle) => {
    const buttons = toggle.querySelectorAll(".segmented__button")
    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        buttons.forEach((item) => item.classList.remove("is-active"))
        button.classList.add("is-active")
        updateSeriesFilter(toggle.dataset.chart, button.dataset.series)
      })
    })
  })
}

function buildSources(payload) {
  const sourceGrid = document.getElementById("source-grid")
  sourceGrid.innerHTML = payload.sources
    .map(
      (item) => `
        <article class="panel source-card">
          <div class="panel__label">${item.type}</div>
          <h3>${item.title}</h3>
          <p>${item.scope}</p>
          <div class="source-card__meta">${item.raw_files.join("<br />")}</div>
          <div class="detail-card__block">
            <div class="panel__label">Processing Logic</div>
            <ul class="detail-list">
              ${item.logic.map((point) => `<li>${point}</li>`).join("")}
            </ul>
          </div>
          <div class="detail-card__block">
            <div class="panel__label">Outputs</div>
            <ul class="detail-list">
              ${item.outputs.map((point) => `<li><code>${point}</code></li>`).join("")}
            </ul>
          </div>
        </article>
      `
    )
    .join("")
}

function renderPipelineDetail(node) {
  const detail = document.getElementById("pipeline-detail")
  detail.innerHTML = `
    <article class="detail-card">
      <div class="panel__label">${node.eyebrow}</div>
      <h3>${node.title}</h3>
      <p>${node.why}</p>
      <div class="detail-card__block">
        <div class="panel__label">Technology</div>
        <div class="pill-row">
          ${node.tech.map((item) => `<span class="tech-pill">${item}</span>`).join("")}
        </div>
      </div>
      <div class="detail-card__block">
        <div class="panel__label">Input</div>
        <ul class="detail-list">
          ${node.input.map((item) => `<li>${item}</li>`).join("")}
        </ul>
      </div>
      <div class="detail-card__block">
        <div class="panel__label">Logic</div>
        <ul class="detail-list">
          ${node.logic.map((item) => `<li>${item}</li>`).join("")}
        </ul>
      </div>
      <div class="detail-card__block">
        <div class="panel__label">Output</div>
        <ul class="detail-list">
          ${node.output.map((item) => `<li><code>${item}</code></li>`).join("")}
        </ul>
      </div>
    </article>
  `
}

function setActivePipeline(index) {
  state.pipelineIndex = index
  const nodes = document.querySelectorAll(".pipeline-node")
  nodes.forEach((nodeEl, nodeIndex) => {
    nodeEl.classList.toggle("is-active", nodeIndex === index)
  })
  renderPipelineDetail(state.payload.pipeline.nodes[index])
}

function startPipelineAutoplay() {
  stopPipelineAutoplay()
  state.pipelineTimer = window.setInterval(() => {
    state.pipelineIndex = (state.pipelineIndex + 1) % state.payload.pipeline.nodes.length
    setActivePipeline(state.pipelineIndex)
  }, 5200)
}

function stopPipelineAutoplay() {
  if (state.pipelineTimer) {
    window.clearInterval(state.pipelineTimer)
    state.pipelineTimer = null
  }
}

function buildPipeline(payload) {
  const pipelineMap = document.getElementById("pipeline-map")
  document.getElementById("pipeline-summary").textContent = payload.pipeline.summary

  pipelineMap.innerHTML = payload.pipeline.nodes
    .map(
      (node, index) => `
        <button class="pipeline-node ${index === 0 ? "is-active" : ""}" data-index="${index}" type="button">
          <div class="panel__label">${node.eyebrow}</div>
          <div class="pipeline-node__title">${node.title}</div>
          <div class="pipeline-node__why">${node.why}</div>
        </button>
      `
    )
    .join("")

  pipelineMap.querySelectorAll(".pipeline-node").forEach((node) => {
    node.addEventListener("click", () => {
      setActivePipeline(Number(node.dataset.index))
      startPipelineAutoplay()
    })
    node.addEventListener("mouseenter", stopPipelineAutoplay)
    node.addEventListener("mouseleave", startPipelineAutoplay)
  })

  setActivePipeline(0)
  startPipelineAutoplay()
}

function buildRules(payload) {
  document.getElementById("quality-rules").innerHTML = payload.qualityRules
    .map(
      (rule, index) => `
        <div class="rule-item">
          <div class="rule-index">${index + 1}</div>
          <div>${rule}</div>
        </div>
      `
    )
    .join("")
}

function buildArtifacts(payload) {
  document.getElementById("artifact-list").innerHTML = payload.artifacts
    .map(
      (item) => `
        <article class="artifact-card panel">
          <div class="panel__label">Artifact</div>
          <h3>${item.label}</h3>
          <p>${item.description}</p>
          <div class="artifact-card__path">${item.path}</div>
        </article>
      `
    )
    .join("")
}

function buildRevealObserver() {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible")
          observer.unobserve(entry.target)
        }
      })
    },
    { threshold: 0.16 }
  )

  document.querySelectorAll(".reveal").forEach((element) => {
    observer.observe(element)
  })
}

// Handle direct hash navigation on first load, which can otherwise land on a
// still-hidden `.reveal` section before the observer fires on mobile.
function revealHashTarget() {
  if (!window.location.hash) {
    return
  }

  const target = document.querySelector(window.location.hash)
  revealElement(target)
}

// Keep anchor-driven navigation visible immediately, even on narrow viewports
// where sticky headers and reveal timing make blank sections more noticeable.
function bindAnchorVisibility() {
  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener("click", () => {
      const hash = link.getAttribute("href")
      if (!hash || hash === "#") {
        return
      }

      const target = document.querySelector(hash)
      revealElement(target)
    })
  })

  window.addEventListener("hashchange", revealHashTarget)
}

async function loadDashboard() {
  const response = await fetch("/data/dashboard_data.json")
  if (!response.ok) {
    throw new Error(`Failed to load dashboard data: ${response.status}`)
  }

  state.payload = await response.json()
  buildOverview(state.payload)
  buildKpis(state.payload)
  buildReportCarousel(state.payload)
  buildBusinessReport(state.payload)
  buildCharts(state.payload)
  buildSeriesToggles()
  buildDestinationToggle()
  buildSources(state.payload)
  buildPipeline(state.payload)
  buildRules(state.payload)
  buildArtifacts(state.payload)
  buildRevealObserver()
  bindAnchorVisibility()
  revealHashTarget()
}

window.addEventListener("DOMContentLoaded", () => {
  loadDashboard().catch((error) => {
    console.error(error)
    document.body.insertAdjacentHTML(
      "beforeend",
      `<div style="position:fixed;bottom:16px;left:16px;padding:12px 16px;border-radius:12px;background:#7a2e2e;color:white;z-index:50;">Dashboard failed to load data.</div>`
    )
  })
})
