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
};

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
};

function safeNumber(value) {
  return value == null ? 0 : value;
}

function formatValue(value) {
  return new Intl.NumberFormat("en-AU", {
    maximumFractionDigits: value >= 1000 ? 0 : 2,
  }).format(value);
}

function buildOverview(payload) {
  const heroTitle = document.getElementById("hero-title");
  const heroSubtitle = document.getElementById("hero-subtitle");
  const windowPill = document.getElementById("window-pill");
  const generatedPill = document.getElementById("generated-pill");
  const coveragePill = document.getElementById("coverage-pill");
  const coverageGrid = document.getElementById("hero-coverage");
  const heroRail = document.getElementById("hero-rail");
  const heroSpotlight = document.getElementById("hero-spotlight");

  heroTitle.textContent = payload.meta.project_title;
  heroSubtitle.textContent = payload.meta.subtitle;
  windowPill.textContent = `Window: ${payload.meta.data_window.start} to ${payload.meta.data_window.end}`;
  generatedPill.textContent = `Generated: ${payload.meta.generated_at_utc}`;
  coveragePill.textContent = `${payload.meta.coverage.quarters_in_scope} quarters in scope`;

  const stats = [
    ["Export release months", payload.meta.coverage.export_release_months],
    ["Production release folders", payload.meta.coverage.production_release_folders],
    ["Clean export rows", payload.meta.coverage.clean_export_rows],
    ["Clean production rows", payload.meta.coverage.clean_production_rows],
  ];

  coverageGrid.innerHTML = stats
    .map(
      ([label, value]) => `
        <div class="mini-stat">
          <span class="mini-stat__label">${label}</span>
          <span class="mini-stat__value">${formatValue(value)}</span>
        </div>
      `
    )
    .join("");

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
  ];

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
  `;

  heroSpotlight.innerHTML = `
    <div class="panel__label">Process Spotlight</div>
    <h3 class="hero-panel__spotlight-title"></h3>
    <p class="hero-panel__spotlight-copy"></p>
    <a class="hero-panel__spotlight-link" href="#sources">Jump to section</a>
  `;

  const spotlightTitle = heroSpotlight.querySelector(".hero-panel__spotlight-title");
  const spotlightCopy = heroSpotlight.querySelector(".hero-panel__spotlight-copy");
  const spotlightLink = heroSpotlight.querySelector(".hero-panel__spotlight-link");
  const stepButtons = Array.from(heroRail.querySelectorAll(".rail-step"));

  const setHeroStep = (index) => {
    state.heroStepIndex = index;
    const step = miniPipeline[index];
    stepButtons.forEach((button, buttonIndex) => {
      button.classList.toggle("is-active", buttonIndex === index);
    });
    spotlightTitle.textContent = step.label;
    spotlightCopy.textContent = step.detail;
    spotlightLink.textContent = `Jump to ${step.targetLabel}`;
    spotlightLink.setAttribute("href", step.target);
  };

  const stopHeroStepAutoplay = () => {
    if (state.heroStepTimer) {
      window.clearInterval(state.heroStepTimer);
      state.heroStepTimer = null;
    }
  };

  const startHeroStepAutoplay = () => {
    stopHeroStepAutoplay();
    state.heroStepTimer = window.setInterval(() => {
      const nextIndex = (state.heroStepIndex + 1) % miniPipeline.length;
      setHeroStep(nextIndex);
    }, 4200);
  };

  stepButtons.forEach((button, index) => {
    button.addEventListener("click", () => {
      setHeroStep(index);
      const target = document.querySelector(button.dataset.target);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      startHeroStepAutoplay();
    });
    button.addEventListener("mouseenter", stopHeroStepAutoplay);
    button.addEventListener("mouseleave", startHeroStepAutoplay);
  });

  heroSpotlight.addEventListener("mouseenter", stopHeroStepAutoplay);
  heroSpotlight.addEventListener("mouseleave", startHeroStepAutoplay);

  setHeroStep(0);
  startHeroStepAutoplay();
}

function buildKpis(payload) {
  const kpiGrid = document.getElementById("kpi-grid");
  const accentMap = {
    copper: "var(--copper)",
    moss: "var(--moss)",
    navy: "var(--navy)",
    olive: "var(--olive)",
  };

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
    .join("");
}

function updateReportStage(index) {
  const slides = state.payload.reportSlides;
  const stage = document.getElementById("report-stage");
  const image = document.getElementById("report-image");
  const title = document.getElementById("report-title");
  const caption = document.getElementById("report-caption");
  const dots = document.querySelectorAll(".report-dot");
  const thumbs = document.querySelectorAll(".report-thumb");
  const counter = document.getElementById("report-counter");
  const progressBar = document.getElementById("report-progress-bar");
  const item = slides[index];

  stage.classList.add("is-transitioning");
  image.src = item.image;
  image.alt = item.title;
  title.textContent = item.title;
  caption.textContent = item.caption;
  counter.textContent = `${String(index + 1).padStart(2, "0")} / ${String(slides.length).padStart(2, "0")}`;

  dots.forEach((dot, dotIndex) => {
    dot.classList.toggle("is-active", dotIndex === index);
  });
  thumbs.forEach((thumb, thumbIndex) => {
    thumb.classList.toggle("is-active", thumbIndex === index);
  });

  if (progressBar) {
    progressBar.style.animation = "none";
    progressBar.offsetHeight;
    progressBar.style.animation = "";
  }

  window.setTimeout(() => {
    stage.classList.remove("is-transitioning");
  }, 220);
}

function startReportAutoplay() {
  stopReportAutoplay();
  const stage = document.getElementById("report-stage");
  stage.classList.add("is-autoplaying");
  state.reportTimer = window.setInterval(() => {
    state.reportIndex = (state.reportIndex + 1) % state.payload.reportSlides.length;
    updateReportStage(state.reportIndex);
  }, 6500);
}

function stopReportAutoplay() {
  if (state.reportTimer) {
    window.clearInterval(state.reportTimer);
    state.reportTimer = null;
  }
  const stage = document.getElementById("report-stage");
  if (stage) {
    stage.classList.remove("is-autoplaying");
  }
}

function buildReportCarousel(payload) {
  const dotsWrap = document.getElementById("report-dots");
  const stage = document.getElementById("report-stage");
  const thumbsWrap = document.getElementById("report-thumbs");
  const image = document.getElementById("report-image");
  const zoomButton = document.getElementById("report-zoom");
  const lightbox = document.getElementById("report-lightbox");
  const lightboxImage = document.getElementById("lightbox-image");
  const lightboxTitle = document.getElementById("lightbox-title");
  const lightboxBackdrop = document.getElementById("lightbox-backdrop");
  const lightboxClose = document.getElementById("lightbox-close");
  let touchStartX = null;

  dotsWrap.innerHTML = payload.reportSlides
    .map(
      (_, index) =>
        `<button class="report-dot ${index === 0 ? "is-active" : ""}" data-index="${index}" type="button" aria-label="View report ${index + 1}"></button>`
    )
    .join("");

  thumbsWrap.innerHTML = payload.reportSlides
    .map(
      (slide, index) => `
        <button class="report-thumb ${index === 0 ? "is-active" : ""}" data-index="${index}" type="button" aria-label="Open ${slide.title}">
          <img src="${slide.image}" alt="${slide.title}" loading="lazy" />
          <span class="report-thumb__caption">${slide.title}</span>
        </button>
      `
    )
    .join("");

  dotsWrap.querySelectorAll(".report-dot").forEach((dot) => {
    dot.addEventListener("click", () => {
      state.reportIndex = Number(dot.dataset.index);
      updateReportStage(state.reportIndex);
      startReportAutoplay();
    });
  });

  thumbsWrap.querySelectorAll(".report-thumb").forEach((thumb) => {
    thumb.addEventListener("click", () => {
      state.reportIndex = Number(thumb.dataset.index);
      updateReportStage(state.reportIndex);
      startReportAutoplay();
    });
  });

  document.getElementById("report-prev").addEventListener("click", () => {
    state.reportIndex =
      (state.reportIndex - 1 + payload.reportSlides.length) % payload.reportSlides.length;
    updateReportStage(state.reportIndex);
    startReportAutoplay();
  });

  document.getElementById("report-next").addEventListener("click", () => {
    state.reportIndex = (state.reportIndex + 1) % payload.reportSlides.length;
    updateReportStage(state.reportIndex);
    startReportAutoplay();
  });

  stage.addEventListener("mouseenter", stopReportAutoplay);
  stage.addEventListener("mouseleave", startReportAutoplay);
  stage.addEventListener("touchstart", (event) => {
    touchStartX = event.changedTouches[0].clientX;
    stopReportAutoplay();
  }, { passive: true });
  stage.addEventListener("touchend", (event) => {
    if (touchStartX == null) {
      return;
    }
    const touchEndX = event.changedTouches[0].clientX;
    const deltaX = touchEndX - touchStartX;
    touchStartX = null;

    if (Math.abs(deltaX) > 40) {
      if (deltaX < 0) {
        state.reportIndex = (state.reportIndex + 1) % payload.reportSlides.length;
      } else {
        state.reportIndex =
          (state.reportIndex - 1 + payload.reportSlides.length) % payload.reportSlides.length;
      }
      updateReportStage(state.reportIndex);
    }
    startReportAutoplay();
  }, { passive: true });

  const openLightbox = () => {
    const activeSlide = payload.reportSlides[state.reportIndex];
    lightboxImage.src = activeSlide.image;
    lightboxImage.alt = activeSlide.title;
    lightboxTitle.textContent = activeSlide.title;
    lightbox.classList.add("is-open");
    lightbox.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  };

  const closeLightbox = () => {
    lightbox.classList.remove("is-open");
    lightbox.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  };

  image.addEventListener("click", openLightbox);
  zoomButton.addEventListener("click", openLightbox);
  lightboxBackdrop.addEventListener("click", closeLightbox);
  lightboxClose.addEventListener("click", closeLightbox);
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && lightbox.classList.contains("is-open")) {
      closeLightbox();
    }
  });

  updateReportStage(0);
  startReportAutoplay();
}

function chartBaseOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 900,
      easing: "easeOutCubic",
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
            return formatValue(value);
          },
        },
        grid: { color: COLORS.grid },
      },
    },
  };
}

function buildCharts(payload) {
  const productionLabels = payload.analytics.productionTrend.map((item) => item.label);
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
            tension: 0.28,
          },
          {
            label: "Lamb",
            data: payload.analytics.productionTrend.map((item) => safeNumber(item.lamb)),
            borderColor: COLORS.lamb,
            backgroundColor: "rgba(124, 154, 87, 0.16)",
            pointRadius: 4,
            tension: 0.28,
          },
        ],
      },
      options: chartBaseOptions(),
    }
  );

  const exportsLabels = payload.analytics.exportsTrend.map((item) => item.label);
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
          tension: 0.24,
        },
        {
          label: "Lamb",
          data: payload.analytics.exportsTrend.map((item) => safeNumber(item.lamb)),
          borderColor: COLORS.lamb,
          backgroundColor: "rgba(124, 154, 87, 0.14)",
          pointRadius: 3,
          tension: 0.24,
        },
      ],
    },
    options: chartBaseOptions(),
  });

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
  });

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
        plugins: {
          ...chartBaseOptions().plugins,
          legend: { display: false },
        },
      },
    }
  );

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
  });

  updateDestinationChart(state.destinationProduct);
}

function updateDestinationChart(product) {
  const chart = state.charts.destinations;
  const data = state.payload.analytics.topDestinations[product];
  chart.data.labels = data.map((item) => item.destination);
  chart.data.datasets[0].data = data.map((item) => item.tonnes);
  chart.data.datasets[0].backgroundColor = product === "beef" ? COLORS.beef : COLORS.lamb;
  chart.update();
}

function buildDestinationToggle() {
  const buttons = document.querySelectorAll("#destination-toggle .segmented__button");
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      buttons.forEach((item) => item.classList.remove("is-active"));
      button.classList.add("is-active");
      state.destinationProduct = button.dataset.product;
      updateDestinationChart(state.destinationProduct);
    });
  });
}

function buildSources(payload) {
  const sourceGrid = document.getElementById("source-grid");
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
    .join("");
}

function renderPipelineDetail(node) {
  const detail = document.getElementById("pipeline-detail");
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
  `;
}

function setActivePipeline(index) {
  state.pipelineIndex = index;
  const nodes = document.querySelectorAll(".pipeline-node");
  nodes.forEach((nodeEl, nodeIndex) => {
    nodeEl.classList.toggle("is-active", nodeIndex === index);
  });
  renderPipelineDetail(state.payload.pipeline.nodes[index]);
}

function startPipelineAutoplay() {
  stopPipelineAutoplay();
  state.pipelineTimer = window.setInterval(() => {
    state.pipelineIndex = (state.pipelineIndex + 1) % state.payload.pipeline.nodes.length;
    setActivePipeline(state.pipelineIndex);
  }, 5200);
}

function stopPipelineAutoplay() {
  if (state.pipelineTimer) {
    window.clearInterval(state.pipelineTimer);
    state.pipelineTimer = null;
  }
}

function buildPipeline(payload) {
  const pipelineMap = document.getElementById("pipeline-map");
  document.getElementById("pipeline-summary").textContent = payload.pipeline.summary;

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
    .join("");

  pipelineMap.querySelectorAll(".pipeline-node").forEach((node) => {
    node.addEventListener("click", () => {
      setActivePipeline(Number(node.dataset.index));
      startPipelineAutoplay();
    });
    node.addEventListener("mouseenter", stopPipelineAutoplay);
    node.addEventListener("mouseleave", startPipelineAutoplay);
  });

  setActivePipeline(0);
  startPipelineAutoplay();
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
    .join("");
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
    .join("");
}

function buildRevealObserver() {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.16 }
  );

  document.querySelectorAll(".reveal").forEach((element) => {
    observer.observe(element);
  });
}

async function loadDashboard() {
  const response = await fetch("./data/dashboard_data.json");
  if (!response.ok) {
    throw new Error(`Failed to load dashboard data: ${response.status}`);
  }

  state.payload = await response.json();
  buildOverview(state.payload);
  buildKpis(state.payload);
  buildReportCarousel(state.payload);
  buildCharts(state.payload);
  buildDestinationToggle();
  buildSources(state.payload);
  buildPipeline(state.payload);
  buildRules(state.payload);
  buildArtifacts(state.payload);
  buildRevealObserver();
}

window.addEventListener("DOMContentLoaded", () => {
  loadDashboard().catch((error) => {
    console.error(error);
    document.body.insertAdjacentHTML(
      "beforeend",
      `<div style="position:fixed;bottom:16px;left:16px;padding:12px 16px;border-radius:12px;background:#7a2e2e;color:white;z-index:50;">Dashboard failed to load data.</div>`
    );
  });
});
