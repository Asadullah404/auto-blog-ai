/**
 * Content Pipeline Pro - n8n-Inspired Visual Workflow Engine
 * Features:
 * - Authentic n8n node cards with input/output connection handles
 * - Smooth cubic Bézier wires with active animated pulse flow
 * - Interactive node dragging with dynamic real-time wire following
 * - Canvas panning and multi-level zoom controls
 * - Slide-out parameter inspector drawer
 */

class WorkflowManager {
  constructor() {
    this.container = document.getElementById('workflow-container');
    this.canvas = document.getElementById('workflow-canvas');
    this.svg = document.getElementById('workflow-svg');
    this.drawer = document.getElementById('workflow-drawer');
    this.drawerTitle = document.getElementById('drawer-node-title');
    this.drawerType = document.getElementById('drawer-node-type');
    this.drawerContent = document.getElementById('drawer-node-content');
    this.drawerClose = document.getElementById('drawer-close-btn');

    this.nodes = [
      { id: 'node-input', name: '1. Content Input', phase: 0, next: 'node-extract' },
      { id: 'node-extract', name: '2. DOM Extractor', phase: 1, next: 'node-transform' },
      { id: 'node-transform', name: '3. AI Transform', phase: 2, next: 'node-images' },
      { id: 'node-images', name: '4. Image Synthesis', phase: 3, next: 'node-render' },
      { id: 'node-render', name: '5. OpenCV Typo', phase: 4, next: 'node-compile' },
      { id: 'node-compile', name: '6. HTML5 Compiler', phase: 5, next: 'node-publish' },
      { id: 'node-publish', name: '7. Gutenberg Publish', phase: 6, next: null }
    ];

    this.nodeDetails = {
      'node-input': {
        type: 'Source Ingestion (Trigger)',
        description: 'Ingests URLs from active queue, CSV batch spreadsheets, or Cloud Firestore lease pool.',
        fields: [
          { label: 'Source Modes', value: 'Queue / CSV Upload / Firestore Leasing' },
          { label: 'Batch Sizing', value: 'Auto-chunked with SQLite WAL checkpoints' },
          { label: 'Fault Recovery', value: 'Idempotent per-article checkpoint caching' }
        ]
      },
      'node-extract': {
        type: 'Phase 1: Structured DOM Extractor',
        description: 'Extracts full article body, titles, section headers, author, and metadata.',
        fields: [
          { label: 'Extractor Core', value: 'newspaper4k + BeautifulSoup4 DOM fallbacks' },
          { label: 'User Agent', value: 'Desktop Windows 11 Chrome Spoofing' },
          { label: 'Cleaners', value: 'Ad-stripping, script removal, boilerpipe heuristic' }
        ]
      },
      'node-transform': {
        type: 'Phase 2: AI Rewriting & SEO Engine',
        description: 'Transforms raw web content into authoritative articles infused with active SEO, GEO, and AEO skill directives.',
        fields: [
          { label: 'Active LLM', value: 'Google Gemini 2.5 Flash' },
          { label: 'Article Format', value: 'Hybrid (Narrative + Bulleted Key Points)' },
          { label: 'Skills Injected', value: 'SEO Copywriting v3.0, GEO v1.0, AEO v1.0' },
          { label: 'Schema Synthesis', value: 'Generates FAQ Q&A and Article Metadata' }
        ]
      },
      'node-images': {
        type: 'Phase 3: Multi-Engine Image Synthesis',
        description: 'Generates high-definition featured images and vertical 1000x1500 Pinterest marketing pins.',
        fields: [
          { label: 'Active Engine', value: 'Pollinations AI (Fallback: Google Imagen / Colab SDXL)' },
          { label: 'Preset Aspect Ratio', value: 'Landscape 16:9 (1200x675)' },
          { label: 'Pinterest Pin', value: 'Vertical 2:3 (1000x1500) with custom style' },
          { label: 'Master Prompt', value: 'Active aesthetic global prefix' }
        ]
      },
      'node-render': {
        type: 'Phase 4: OpenCV Typography Overlay',
        description: 'Overlays article titles and category badges onto images with word-wrapped drop shadows and gradient dark scrims.',
        fields: [
          { label: 'Rendering Core', value: 'OpenCV & Pillow (PIL)' },
          { label: 'Typography', value: 'Segoe UI Variable / Arial HD font metrics' },
          { label: 'Gradient Scrim', value: 'Smooth linear bottom darkening band' }
        ]
      },
      'node-compile': {
        type: 'Phase 5: Responsive HTML5 Document',
        description: 'Compiles clean, responsive semantic HTML5 documents embedded with Schema.org JSON-LD Article and FAQPage structures.',
        fields: [
          { label: 'Standard', value: 'HTML5 Semantic + Schema.org JSON-LD' },
          { label: 'Output File', value: 'output/<slug>/final_output.html' },
          { label: 'Assets', value: 'Self-contained relative WebP assets' }
        ]
      },
      'node-publish': {
        type: 'Phase 6: Gutenberg WordPress Publisher',
        description: 'Publishes completed articles to WordPress via REST API with native Gutenberg comment blocks and Rank Math SEO sync.',
        fields: [
          { label: 'Protocol', value: 'WordPress REST API (v2)' },
          { label: 'Block Syntax', value: '<!-- wp:paragraph -->, <!-- wp:heading -->' },
          { label: 'SEO Integration', value: 'Rank Math REST Meta (Focus Keyword + Description)' }
        ]
      }
    };

    this.activePhase = 0;
    this.zoomLevel = 1.0;
    this.isDraggingNode = false;
    this.isPanning = false;
    this.panStartX = 0;
    this.panStartY = 0;
    this.scrollStartX = 0;
    this.scrollStartY = 0;

    this.init();
  }

  init() {
    this.setupNodeInteraction();
    this.setupDrawer();
    this.setupZoomControls();
    this.setupCanvasPanning();
    this.setupRunButton();

    // Initial render of connectors
    setTimeout(() => {
      this.drawConnectors();
    }, 100);

    // Re-draw when window resizes
    window.addEventListener('resize', () => {
      this.drawConnectors();
    });
  }

  setupRunButton() {
    const runBtn = document.getElementById('workflow-run-btn');
    if (runBtn) {
      runBtn.addEventListener('click', async () => {
        try {
          const res = await fetch('/api/pipeline/start', { method: 'POST' });
          const data = await res.json();
          if (data.ok || data.status === 'success') {
            if (window.fluentApp) window.fluentApp.showToast('Workflow Started', 'Pipeline execution triggered from n8n canvas.', 'success');
          } else {
            if (window.fluentApp) window.fluentApp.showToast('Notice', data.error || data.message || 'Already running.', 'info');
          }
        } catch (e) {
          if (window.fluentApp) window.fluentApp.showToast('Error', e.message, 'error');
        }
      });
    }

    const resetBtn = document.getElementById('workflow-reset-btn');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        if (this.container) {
          this.container.scrollTo({ left: 0, top: 0, behavior: 'smooth' });
        }
        this.setZoom(1.0);
      });
    }
  }

  setupZoomControls() {
    const zoomIn = document.getElementById('wf-zoom-in');
    const zoomOut = document.getElementById('wf-zoom-out');
    const fitView = document.getElementById('wf-fit-view');

    if (zoomIn) zoomIn.addEventListener('click', () => this.setZoom(this.zoomLevel + 0.15));
    if (zoomOut) zoomOut.addEventListener('click', () => this.setZoom(this.zoomLevel - 0.15));
    if (fitView) {
      fitView.addEventListener('click', () => {
        // Calculate fit scale
        if (this.container && this.canvas) {
          const containerWidth = this.container.clientWidth;
          const scale = Math.max(0.45, Math.min(1.0, (containerWidth - 60) / 2320));
          this.setZoom(scale);
          this.container.scrollTo({ left: 0, top: 0, behavior: 'smooth' });
        }
      });
    }
  }

  setZoom(val) {
    this.zoomLevel = Math.max(0.5, Math.min(1.5, Math.round(val * 100) / 100));
    if (this.canvas) {
      this.canvas.style.transform = `scale(${this.zoomLevel})`;
    }
    const label = document.getElementById('wf-zoom-level');
    if (label) {
      label.textContent = `${Math.round(this.zoomLevel * 100)}%`;
    }
    this.drawConnectors();
  }

  setupCanvasPanning() {
    if (!this.container) return;

    this.container.addEventListener('mousedown', (e) => {
      // Don't pan if clicking inside a node or button
      if (e.target.closest('.workflow-node') || e.target.closest('.workflow-hud') || e.target.closest('.workflow-drawer')) {
        return;
      }
      this.isPanning = true;
      this.panStartX = e.clientX;
      this.panStartY = e.clientY;
      this.scrollStartX = this.container.scrollLeft;
      this.scrollStartY = this.container.scrollTop;
      this.container.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
      if (!this.isPanning) return;
      const dx = e.clientX - this.panStartX;
      const dy = e.clientY - this.panStartY;
      this.container.scrollLeft = this.scrollStartX - dx;
      this.container.scrollTop = this.scrollStartY - dy;
    });

    window.addEventListener('mouseup', () => {
      if (this.isPanning) {
        this.isPanning = false;
        if (this.container) this.container.style.cursor = 'default';
      }
    });
  }

  setupNodeInteraction() {
    const nodeEls = document.querySelectorAll('.workflow-node');

    nodeEls.forEach((nodeEl) => {
      let isDragging = false;
      let startX = 0, startY = 0;
      let origLeft = 0, origTop = 0;
      let hasMoved = false;

      nodeEl.addEventListener('mousedown', (e) => {
        if (e.target.closest('.node-port')) return;
        isDragging = true;
        hasMoved = false;
        startX = e.clientX;
        startY = e.clientY;
        origLeft = nodeEl.offsetLeft;
        origTop = nodeEl.offsetTop;
        nodeEl.classList.add('dragging');
        e.stopPropagation();
      });

      window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        const dx = (e.clientX - startX) / this.zoomLevel;
        const dy = (e.clientY - startY) / this.zoomLevel;

        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
          hasMoved = true;
        }

        const newLeft = Math.max(10, Math.min(2040, origLeft + dx));
        const newTop = Math.max(20, Math.min(420, origTop + dy));

        nodeEl.style.left = `${newLeft}px`;
        nodeEl.style.top = `${newTop}px`;

        this.drawConnectors();
      });

      window.addEventListener('mouseup', () => {
        if (isDragging) {
          isDragging = false;
          nodeEl.classList.remove('dragging');
          if (!hasMoved) {
            // It was a click, open drawer!
            const nodeId = nodeEl.dataset.node;
            this.openDrawer(`node-${nodeId}`);
          }
        }
      });
    });
  }

  setupDrawer() {
    if (this.drawerClose) {
      this.drawerClose.addEventListener('click', () => {
        this.closeDrawer();
      });
    }
  }

  openDrawer(nodeId) {
    const details = this.nodeDetails[nodeId];
    if (!details) return;

    if (this.drawerTitle) this.drawerTitle.textContent = details.type;
    if (this.drawerType) this.drawerType.textContent = details.description;

    if (this.drawerContent) {
      let html = `<div class="drawer-fields">`;
      details.fields.forEach((field) => {
        html += `
          <div class="drawer-field-item">
            <span class="field-label">${field.label}</span>
            <span class="field-value">${field.value}</span>
          </div>
        `;
      });
      html += `</div>`;
      this.drawerContent.innerHTML = html;
    }

    if (this.drawer) {
      this.drawer.classList.add('open');
    }
  }

  closeDrawer() {
    if (this.drawer) {
      this.drawer.classList.remove('open');
    }
  }

  drawConnectors() {
    if (!this.svg || !this.canvas) return;

    // Clear existing paths
    this.svg.innerHTML = '';

    for (let i = 0; i < this.nodes.length - 1; i++) {
      const fromNode = document.getElementById(this.nodes[i].id);
      const toNode = document.getElementById(this.nodes[i + 1].id);

      if (!fromNode || !toNode) continue;

      // Coordinates relative to .workflow-canvas using offset properties
      const startX = fromNode.offsetLeft + fromNode.offsetWidth;
      const startY = fromNode.offsetTop + (fromNode.offsetHeight / 2);

      const endX = toNode.offsetLeft;
      const endY = toNode.offsetTop + (toNode.offsetHeight / 2);

      // Smooth horizontal cubic Bézier curve
      const dx = Math.max(50, Math.abs(endX - startX) * 0.52);

      const pathData = `M ${startX} ${startY} C ${startX + dx} ${startY}, ${endX - dx} ${endY}, ${endX} ${endY}`;

      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', pathData);
      path.setAttribute('class', 'workflow-connector-line');
      path.id = `line-${this.nodes[i].id}-to-${this.nodes[i + 1].id}`;

      // Status-based wire highlighting
      if (this.activePhase === this.nodes[i + 1].phase) {
        path.classList.add('line-active');
      } else if (this.nodes[i + 1].phase < this.activePhase) {
        path.classList.add('line-completed');
      }

      this.svg.appendChild(path);
    }
  }

  updateFromProgress(status) {
    const phaseNumber = parseInt(status.phase || 0, 10);
    this.activePhase = phaseNumber;

    this.nodes.forEach((node) => {
      const nodeEl = document.getElementById(node.id);
      if (!nodeEl) return;

      const pill = nodeEl.querySelector('.node-status-pill');
      const pillText = pill ? pill.querySelector('.pill-text') : null;

      nodeEl.classList.remove('node-running', 'node-completed', 'node-error');
      if (pill) {
        pill.className = 'node-status-pill';
      }

      if (status.state === 'error' && node.phase === phaseNumber) {
        nodeEl.classList.add('node-error');
        if (pill) pill.classList.add('status-error');
        if (pillText) pillText.textContent = 'Failed';
      } else if (status.state === 'running' && node.phase === phaseNumber) {
        nodeEl.classList.add('node-running');
        if (pill) pill.classList.add('status-active');
        if (pillText) pillText.textContent = 'Running...';
      } else if (node.phase < phaseNumber || status.state === 'completed') {
        nodeEl.classList.add('node-completed');
        if (pill) pill.classList.add('status-complete');
        if (pillText) pillText.textContent = 'Success';
      } else {
        if (pill) pill.classList.add('status-idle');
        if (pillText) pillText.textContent = 'Idle';
      }
    });

    this.drawConnectors();
  }

  resetCanvas() {
    this.activePhase = 0;
    this.setZoom(1.0);
    if (this.container) {
      this.container.scrollTo({ left: 0, top: 0, behavior: 'smooth' });
    }
    this.drawConnectors();
  }
}

// Global initialization
document.addEventListener('DOMContentLoaded', () => {
  window.workflowManager = new WorkflowManager();
});
