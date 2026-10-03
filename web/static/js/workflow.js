/**
 * Content Pipeline Pro - Windows 11 Fluent Pipeline Workflow Studio
 * Vertical Split-Screen Architecture with Live Inspector & Illuminated Connectors
 */

class WorkflowManager {
  constructor() {
    this.selectedNodeKey = 'transform';
    this.activePhase = 0;

    this.nodes = [
      { key: 'input', id: 'node-input', wireBefore: null, wireAfter: 'wire-1-2', phase: 0 },
      { key: 'extract', id: 'node-extract', wireBefore: 'wire-1-2', wireAfter: 'wire-2-3', phase: 1 },
      { key: 'transform', id: 'node-transform', wireBefore: 'wire-2-3', wireAfter: 'wire-3-4', phase: 2 },
      { key: 'images', id: 'node-images', wireBefore: 'wire-3-4', wireAfter: 'wire-4-5', phase: 3 },
      { key: 'render', id: 'node-render', wireBefore: 'wire-4-5', wireAfter: 'wire-5-6', phase: 4 },
      { key: 'compile', id: 'node-compile', wireBefore: 'wire-5-6', wireAfter: 'wire-6-7', phase: 5 },
      { key: 'publish', id: 'node-publish', wireBefore: 'wire-6-7', wireAfter: null, phase: 6 }
    ];

    this.nodeDetails = {
      'input': {
        badge: 'Step 1 • Ingestion Trigger',
        title: 'Content Input & Ingestion Queue',
        subtitle: 'Source Feeds, CSV Uploads & Cloud Leasing',
        description: 'Ingests target article URLs from the local queue, CSV batch spreadsheets, or Cloud Firestore lease pool with SQLite WAL idempotent checkpointing.',
        specs: [
          { label: 'Source Ingestion:', value: 'Interactive URL, CSV Batch, Firestore' },
          { label: 'Fault Recovery:', value: 'Idempotent per-article SQLite WAL cache' },
          { label: 'Execution Mode:', value: 'Online REST API or Offline Bundles' },
          { label: 'Concurrency:', value: 'Single-thread worker with pause/resume' }
        ],
        input: 'Target article URLs, batch CSV file, or Firestore collection',
        output: 'Normalized article task items in pipeline queue'
      },
      'extract': {
        badge: 'Step 2 • Phase 1',
        title: 'DOM Web Extractor',
        subtitle: 'newspaper4k & BeautifulSoup4 Structured Scraper',
        description: 'Extracts full article body, section headers (H2/H3), author details, publication date, and metadata while stripping ads, sidebars, and scripts.',
        specs: [
          { label: 'Primary Engine:', value: 'newspaper4k' },
          { label: 'Fallback Scraper:', value: 'BeautifulSoup4 Heuristic Scraper' },
          { label: 'Spoof Headers:', value: 'Windows 11 Chrome Desktop User-Agent' },
          { label: 'Content Sanitizer:', value: 'Removes navbars, ads, trackers & boilerpipe' }
        ],
        input: 'Target web article HTTP / HTTPS URL',
        output: 'Raw HTML, extracted text body, H2 list, author & meta tags'
      },
      'transform': {
        badge: 'Step 3 • Phase 2',
        title: 'AI Content Transformation',
        subtitle: 'Gemini 2.5 Flash + Skills Injection Engine',
        description: 'Transforms extracted article content into an authoritative, highly engaging article infused with active SEO, GEO, and AEO skill directives.',
        specs: [
          { label: 'Active LLM:', value: 'Google Gemini 2.5 Flash' },
          { label: 'Format Preset:', value: 'Hybrid (Narrative + Structured Lists)' },
          { label: 'Skills Injected:', value: 'SEO Copywriting, GEO v1.0, AEO v1.0' },
          { label: 'Fault Recovery:', value: 'Auto regex JSON bracket repair & healing' }
        ],
        input: 'Raw article text, extracted H2 headings, metadata',
        output: 'Structured sections JSON, FAQ schema, SEO meta title & description'
      },
      'images': {
        badge: 'Step 4 • Phase 3',
        title: 'Image Synthesis & Pinterest Pins',
        subtitle: 'Multi-Engine Generation & Pin Engine',
        description: 'Generates high-definition featured images and vertical 1000x1500 Pinterest marketing pins via Pollinations AI, Google Imagen, or Colab GPU SDXL.',
        specs: [
          { label: 'Image Engine:', value: 'Pollinations AI (Fallback: Imagen / Colab)' },
          { label: 'Featured Aspect:', value: 'Landscape 16:9 (1200x675)' },
          { label: 'Pinterest Pin:', value: 'Vertical 2:3 (1000x1500)' },
          { label: 'Master Prompts:', value: 'Global aesthetic prefix & negative prompts' }
        ],
        input: 'Transformed section image prompts, article title, keywords',
        output: 'Raw PNG/JPEG images saved to output/<slug>/'
      },
      'render': {
        badge: 'Step 5 • Phase 4',
        title: 'OpenCV Typography Overlay',
        subtitle: 'Word-Wrap Drop Shadows & Gradient Dark Scrims',
        description: 'Overlays article titles and category badges onto images with word-wrapped drop shadows and gradient dark scrims for maximum legibility.',
        specs: [
          { label: 'Rendering Core:', value: 'OpenCV & Pillow (PIL)' },
          { label: 'Gradient Scrim:', value: 'Dynamic linear bottom darkening band' },
          { label: 'Typography:', value: 'Segoe UI Variable / Arial HD metrics' },
          { label: 'Output Format:', value: 'WebP compressed for fast web delivery' }
        ],
        input: 'Raw synthesized image, article headline, category badge',
        output: 'Rendered featured image WebP with typography overlay'
      },
      'compile': {
        badge: 'Step 6 • Phase 5',
        title: 'Standalone HTML5 Compiler',
        subtitle: 'Semantic Document & Schema.org JSON-LD',
        description: 'Compiles clean, responsive semantic HTML5 documents embedded with Schema.org JSON-LD Article and FAQPage structures.',
        specs: [
          { label: 'Document Format:', value: 'HTML5 Semantic + Modern Responsive Grid' },
          { label: 'Structured Data:', value: 'Schema.org Article & FAQPage JSON-LD' },
          { label: 'Asset Linking:', value: 'Self-contained relative WebP assets' },
          { label: 'Output Path:', value: 'output/<slug>/final_output.html' }
        ],
        input: 'Transformed sections JSON, rendered images, metadata',
        output: 'Self-contained final_output.html in article directory'
      },
      'publish': {
        badge: 'Step 7 • Phase 6',
        title: 'Gutenberg WordPress Publisher',
        subtitle: 'WordPress REST API & Native Gutenberg Blocks',
        description: 'Publishes completed articles to WordPress via REST API with native Gutenberg comment blocks, featured media upload, and Rank Math SEO sync.',
        specs: [
          { label: 'API Protocol:', value: 'WordPress REST API v2 (App Passwords)' },
          { label: 'Block Syntax:', value: '<!-- wp:paragraph -->, <!-- wp:heading -->' },
          { label: 'SEO Integration:', value: 'Rank Math REST Meta (Focus Keyword & Description)' },
          { label: 'Default Status:', value: 'Draft / Publish / Pending Review' }
        ],
        input: 'Compiled HTML document, featured media, SEO metadata',
        output: 'Published WordPress Post ID & Live Permalink'
      }
    };

    this.init();
  }

  init() {
    this.setupNodeClicks();
    this.setupToolbarButtons();
    this.selectNode('transform');
  }

  setupNodeClicks() {
    const cards = document.querySelectorAll('.pipeline-step-card');
    cards.forEach((card) => {
      card.addEventListener('click', () => {
        const nodeKey = card.dataset.node;
        if (nodeKey) {
          this.selectNode(nodeKey);
        }
      });
    });
  }

  selectNode(nodeKey) {
    const details = this.nodeDetails[nodeKey];
    if (!details) return;

    this.selectedNodeKey = nodeKey;

    // Highlight active card
    document.querySelectorAll('.pipeline-step-card').forEach((c) => {
      c.classList.remove('active-selected');
    });

    const targetCard = document.querySelector(`.pipeline-step-card[data-node="${nodeKey}"]`);
    if (targetCard) {
      targetCard.classList.add('active-selected');
    }

    // Populate Inspector
    const badgeEl = document.getElementById('inspector-step-badge');
    const titleEl = document.getElementById('inspector-title');
    const subtitleEl = document.getElementById('inspector-subtitle');
    const descEl = document.getElementById('inspector-desc');
    const specsEl = document.getElementById('inspector-specs');
    const inEl = document.getElementById('inspector-input-val');
    const outEl = document.getElementById('inspector-output-val');

    if (badgeEl) badgeEl.textContent = details.badge;
    if (titleEl) titleEl.textContent = details.title;
    if (subtitleEl) subtitleEl.textContent = details.subtitle;
    if (descEl) descEl.textContent = details.description;

    if (specsEl) {
      let specsHtml = '';
      details.specs.forEach((s) => {
        specsHtml += `
          <div class="spec-row">
            <span class="spec-label">${s.label}</span>
            <span class="spec-val">${s.value}</span>
          </div>
        `;
      });
      specsEl.innerHTML = specsHtml;
    }

    if (inEl) inEl.textContent = details.input;
    if (outEl) outEl.textContent = details.output;
  }

  setupToolbarButtons() {
    const runBtn = document.getElementById('workflow-run-btn');
    if (runBtn) {
      runBtn.addEventListener('click', async () => {
        try {
          const res = await fetch('/api/pipeline/start', { method: 'POST' });
          const data = await res.json();
          if (data.ok || data.status === 'success') {
            if (window.fluentApp) {
              window.fluentApp.showToast('Workflow Started', 'Pipeline execution triggered from Studio.', 'success');
            }
          } else {
            if (window.fluentApp) {
              window.fluentApp.showToast('Notice', data.error || data.message || 'Already running.', 'info');
            }
          }
        } catch (e) {
          if (window.fluentApp) {
            window.fluentApp.showToast('Error', e.message, 'error');
          }
        }
      });
    }

    const resetBtn = document.getElementById('workflow-reset-btn');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        this.resetCanvas();
        if (window.fluentApp) {
          window.fluentApp.showToast('Studio Reset', 'Visual status indicators reset.', 'info');
        }
      });
    }
  }

  drawConnectors() {
    // Retained for backward-compatibility with app.js view switcher
    this.refreshWires();
  }

  refreshWires() {
    const phaseNumber = this.activePhase;

    this.nodes.forEach((node, idx) => {
      if (!node.wireBefore) return;
      const wireEl = document.getElementById(node.wireBefore);
      if (!wireEl) return;

      wireEl.classList.remove('wire-active', 'wire-completed');

      if (node.phase === phaseNumber) {
        wireEl.classList.add('wire-active');
      } else if (node.phase < phaseNumber) {
        wireEl.classList.add('wire-completed');
      }
    });
  }

  updateFromProgress(status) {
    const phaseNumber = parseInt(status.phase || 0, 10);
    this.activePhase = phaseNumber;

    this.nodes.forEach((node) => {
      const cardEl = document.getElementById(node.id);
      if (!cardEl) return;

      const pill = cardEl.querySelector('.step-status-pill');
      const pillText = pill ? pill.querySelector('.pill-text') : null;

      cardEl.classList.remove('node-running', 'node-completed', 'node-error');
      if (pill) {
        pill.className = 'step-status-pill';
      }

      if (status.state === 'error' && node.phase === phaseNumber) {
        cardEl.classList.add('node-error');
        if (pill) pill.classList.add('status-error');
        if (pillText) pillText.textContent = 'Failed';
      } else if (status.state === 'running' && node.phase === phaseNumber) {
        cardEl.classList.add('node-running');
        if (pill) pill.classList.add('status-active');
        if (pillText) pillText.textContent = 'Running...';
      } else if (node.phase < phaseNumber || status.state === 'completed') {
        cardEl.classList.add('node-completed');
        if (pill) pill.classList.add('status-completed');
        if (pillText) pillText.textContent = 'Completed';
      } else {
        if (pill) pill.classList.add('status-idle');
        if (pillText) pillText.textContent = 'Idle';
      }
    });

    this.refreshWires();
  }

  resetCanvas() {
    this.activePhase = 0;
    this.nodes.forEach((node) => {
      const cardEl = document.getElementById(node.id);
      if (!cardEl) return;
      cardEl.classList.remove('node-running', 'node-completed', 'node-error');

      const pill = cardEl.querySelector('.step-status-pill');
      const pillText = pill ? pill.querySelector('.pill-text') : null;
      if (pill) {
        pill.className = 'step-status-pill';
        if (node.key === 'input') {
          pill.classList.add('status-ready');
          if (pillText) pillText.textContent = 'Ready';
        } else {
          pill.classList.add('status-idle');
          if (pillText) pillText.textContent = 'Idle';
        }
      }
    });

    // Reset wires
    document.querySelectorAll('.pipeline-wire').forEach((w) => {
      w.classList.remove('wire-active', 'wire-completed');
    });

    this.selectNode('input');
  }
}

// Global initialization
document.addEventListener('DOMContentLoaded', () => {
  window.workflowManager = new WorkflowManager();
});
