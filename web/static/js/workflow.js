/**
 * Content Pipeline Pro - n8n-Inspired Visual Workflow Engine
 * Renders node connections, manages node state machines, and provides inspector drawers.
 */

class WorkflowManager {
  constructor() {
    this.canvas = document.getElementById('workflow-canvas');
    this.svg = document.getElementById('workflow-svg');
    this.drawer = document.getElementById('workflow-drawer');
    this.drawerTitle = document.getElementById('drawer-node-title');
    this.drawerType = document.getElementById('drawer-node-type');
    this.drawerContent = document.getElementById('drawer-node-content');
    this.drawerClose = document.getElementById('drawer-close-btn');

    this.nodes = [
      { id: 'node-input', name: 'Content Ingestion', phase: 0, next: 'node-extract' },
      { id: 'node-extract', name: 'DOM Extractor', phase: 1, next: 'node-transform' },
      { id: 'node-transform', name: 'AI Transformation', phase: 2, next: 'node-images' },
      { id: 'node-images', name: 'Image Synthesis', phase: 3, next: 'node-render' },
      { id: 'node-render', name: 'OpenCV Typography', phase: 4, next: 'node-compile' },
      { id: 'node-compile', name: 'HTML5 Compiler', phase: 5, next: 'node-publish' },
      { id: 'node-publish', name: 'WordPress Publisher', phase: 6, next: null }
    ];

    this.nodeDetails = {
      'node-input': {
        type: 'Source Ingestion',
        description: 'Collects URLs from active batch list, CSV spreadsheets, or multi-machine leased items from Cloud Firestore.',
        fields: [
          { label: 'Source Type', value: 'Dynamic (Queue / CSV / Firestore)' },
          { label: 'Batch Size', value: 'Adaptive checkpointed batches' },
          { label: 'Lease Time', value: '30 minutes (Firestore lock prevention)' }
        ]
      },
      'node-extract': {
        type: 'Phase 1: Scraping & Parsing',
        description: 'Performs robust article body extraction using newspaper4k with fallback to BeautifulSoup4 DOM query parsing.',
        fields: [
          { label: 'Engine', value: 'newspaper4k + lxml / bs4' },
          { label: 'User Agent', value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' },
          { label: 'Selectors Extracted', value: 'Title, H2/H3 Headers, Paragraphs, Images, Meta' }
        ]
      },
      'node-transform': {
        type: 'Phase 2: AI Rewriting & SEO',
        description: 'Transforms extracted content with Gemini 2.5 LLM, injecting active SEO, GEO, and AEO skill directives.',
        fields: [
          { label: 'Active LLM', value: 'Gemini 2.5 Flash' },
          { label: 'Format Preset', value: 'Hybrid (Narrative + Structured Lists)' },
          { label: 'SEO/AEO Skills', value: 'Scanned from Skills/*.md' },
          { label: 'JSON Healing', value: 'Automatic regex-based markdown repair' }
        ]
      },
      'node-images': {
        type: 'Phase 3: Image Generation',
        description: 'Synthesizes high-resolution featured images and Pinterest marketing pins using multi-engine fallbacks.',
        fields: [
          { label: 'Engines Available', value: 'Pollinations AI, Imagen 3, Colab SDXL' },
          { label: 'Preset Aspect Ratio', value: 'Landscape 16:9 (1200x675)' },
          { label: 'Pinterest Pin Ratio', value: 'Vertical 2:3 (1000x1500)' },
          { label: 'Master Prompt', value: 'Active global prefix' }
        ]
      },
      'node-render': {
        type: 'Phase 4: Graphic Overlay',
        description: 'Generates professional typographic overlays with high-contrast drop shadows and gradient dark scrims.',
        fields: [
          { label: 'Graphic Library', value: 'OpenCV & Pillow (PIL)' },
          { label: 'Typography', value: 'Segoe UI / Arial HD Word-wrapped' },
          { label: 'Gradient Scrim', value: 'Adaptive bottom darkening band' }
        ]
      },
      'node-compile': {
        type: 'Phase 5: Responsive HTML5',
        description: 'Compiles clean semantic HTML5 markup containing embedded Schema.org JSON-LD for Article and FAQPage rich snippets.',
        fields: [
          { label: 'Markup Standard', value: 'HTML5 Semantic + KaTeX & Schema.org' },
          { label: 'Local Persistence', value: 'Saved to output/<slug>/index.html' },
          { label: 'Assets Bundled', value: 'Self-contained relative assets' }
        ]
      },
      'node-publish': {
        type: 'Phase 6: CMS Publishing',
        description: 'Publishes completed articles to WordPress via REST API using native Gutenberg comment blocks and Rank Math SEO tags.',
        fields: [
          { label: 'Protocol', value: 'WordPress REST API (v2)' },
          { label: 'Authentication', value: 'Application Passwords' },
          { label: 'Blocks Emitted', value: '<!-- wp:paragraph -->, <!-- wp:heading -->' },
          { label: 'SEO Integration', value: 'Rank Math REST Meta' }
        ]
      }
    };

    this.activePhase = 0;
    this.init();
  }

  init() {
    this.setupNodeClicks();
    this.setupDrawer();
    this.drawConnectors();

    // Re-render lines on window resize
    window.addEventListener('resize', () => {
      this.drawConnectors();
    });

    const resetBtn = document.getElementById('workflow-reset-zoom');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        this.resetCanvas();
      });
    }
  }

  setupNodeClicks() {
    document.querySelectorAll('.workflow-node').forEach((nodeEl) => {
      nodeEl.addEventListener('click', () => {
        const nodeId = nodeEl.dataset.node;
        this.openDrawer(`node-${nodeId}`);
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
            <span class="field-label">${field.label}:</span>
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

    const canvasRect = this.canvas.getBoundingClientRect();

    // Iterate through node connections
    for (let i = 0; i < this.nodes.length - 1; i++) {
      const fromNode = document.getElementById(this.nodes[i].id);
      const toNode = document.getElementById(this.nodes[i + 1].id);

      if (!fromNode || !toNode) continue;

      const fromRect = fromNode.getBoundingClientRect();
      const toRect = toNode.getBoundingClientRect();

      // Calculate relative coordinates inside canvas
      let startX, startY, endX, endY;

      // If toNode is horizontally to the right
      if (toRect.left > fromRect.right - 20) {
        startX = fromRect.right - canvasRect.left;
        startY = fromRect.top + fromRect.height / 2 - canvasRect.top;
        endX = toRect.left - canvasRect.left;
        endY = toRect.top + toRect.height / 2 - canvasRect.top;
      } else if (toRect.right < fromRect.left + 20) {
        // Horizontally to the left
        startX = fromRect.left - canvasRect.left;
        startY = fromRect.top + fromRect.height / 2 - canvasRect.top;
        endX = toRect.right - canvasRect.left;
        endY = toRect.top + toRect.height / 2 - canvasRect.top;
      } else {
        // Vertically below
        startX = fromRect.left + fromRect.width / 2 - canvasRect.left;
        startY = fromRect.bottom - canvasRect.top;
        endX = toRect.left + toRect.width / 2 - canvasRect.left;
        endY = toRect.top - canvasRect.top;
      }

      const dx = Math.abs(endX - startX) * 0.5;
      const dy = Math.abs(endY - startY) * 0.5;

      let pathData = '';
      if (Math.abs(startX - endX) > Math.abs(startY - endY)) {
        pathData = `M ${startX} ${startY} C ${startX + dx} ${startY}, ${endX - dx} ${endY}, ${endX} ${endY}`;
      } else {
        pathData = `M ${startX} ${startY} C ${startX} ${startY + dy}, ${endX} ${endY - dy}, ${endX} ${endY}`;
      }

      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', pathData);
      path.setAttribute('class', 'workflow-connector-line');
      path.id = `line-${this.nodes[i].id}-to-${this.nodes[i + 1].id}`;

      // Highlight active path if currently processing between them
      if (this.activePhase >= this.nodes[i].phase && this.activePhase <= this.nodes[i + 1].phase) {
        path.classList.add('line-active');
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

      const indicator = nodeEl.querySelector('.node-status-indicator');

      nodeEl.classList.remove('node-running', 'node-completed', 'node-error');
      if (indicator) {
        indicator.className = 'node-status-indicator';
      }

      if (status.state === 'error' && node.phase === phaseNumber) {
        nodeEl.classList.add('node-error');
        if (indicator) indicator.classList.add('status-error');
      } else if (status.state === 'running' && node.phase === phaseNumber) {
        nodeEl.classList.add('node-running');
        if (indicator) indicator.classList.add('status-active');
      } else if (node.phase < phaseNumber || status.state === 'completed') {
        nodeEl.classList.add('node-completed');
        if (indicator) indicator.classList.add('status-complete');
      } else {
        if (indicator) indicator.classList.add('status-idle');
      }
    });

    this.drawConnectors();
  }

  resetCanvas() {
    this.activePhase = 0;
    this.nodes.forEach((node) => {
      const nodeEl = document.getElementById(node.id);
      if (nodeEl) {
        nodeEl.classList.remove('node-running', 'node-completed', 'node-error');
        const ind = nodeEl.querySelector('.node-status-indicator');
        if (ind) ind.className = 'node-status-indicator status-idle';
      }
    });
    this.closeDrawer();
    this.drawConnectors();
  }
}

// Global initialization
document.addEventListener('DOMContentLoaded', () => {
  window.workflowManager = new WorkflowManager();
});
