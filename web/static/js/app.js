/**
 * Content Pipeline Pro - Master Windows 11 Desktop Application Controller
 * Handles view routing, theme switching, REST API interactions, modals, and toasts.
 */

class FluentApp {
  constructor() {
    this.currentView = 'view-dashboard';
    this.settings = {};
    this.init();
  }

  async init() {
    this.setupTheme();
    this.setupNavigation();
    this.setupModals();
    this.setupPipelineControls();
    this.setupQueue();
    this.setupArticles();
    this.setupVisuals();
    this.setupSkills();
    this.setupWordPress();
    this.setupSettings();
    this.setupConsole();

    // Initial data load
    await this.loadSettings();
    await this.refreshDashboardStats();
    await this.loadQueue();
    await this.loadArticles();
    await this.loadSkills();

    // Periodic lightweight status ping
    setInterval(() => this.pollPipelineStatus(), 3000);
  }

  // =========================================================================
  // THEME MANAGEMENT (WINDOWS 11 DARK / LIGHT)
  // =========================================================================
  setupTheme() {
    const themeBtn = document.getElementById('theme-toggle-btn');
    const savedTheme = localStorage.getItem('fluent_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);

    if (themeBtn) {
      themeBtn.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('fluent_theme', next);
        this.showToast('Theme Changed', `Switched to ${next} mode`, 'info');
      });
    }

    const refreshBtn = document.getElementById('quick-refresh-btn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => {
        this.refreshAllData();
        this.showToast('System Refreshed', 'Refreshed status, queue, and articles.', 'success');
      });
    }
  }

  // =========================================================================
  // NAVIGATION ROUTER
  // =========================================================================
  setupNavigation() {
    const navItems = document.querySelectorAll('.fluent-sidebar .nav-item');
    navItems.forEach((item) => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const targetViewId = item.dataset.target;
        if (targetViewId) {
          this.switchView(targetViewId, item);
        }
      });
    });

    // Handle deep-linking via URL hash
    window.addEventListener('hashchange', () => {
      const hash = window.location.hash.replace('#', '');
      const targetNav = document.querySelector(`.nav-item[href="#${hash}"]`);
      if (targetNav && targetNav.dataset.target) {
        this.switchView(targetNav.dataset.target, targetNav);
      }
    });

    // Check initial hash
    if (window.location.hash) {
      const hash = window.location.hash.replace('#', '');
      const targetNav = document.querySelector(`.nav-item[href="#${hash}"]`);
      if (targetNav && targetNav.dataset.target) {
        this.switchView(targetNav.dataset.target, targetNav);
      }
    }
  }

  switchView(viewId, activeNavItem = null) {
    // Hide all views
    document.querySelectorAll('.fluent-view').forEach((view) => {
      view.classList.remove('active');
    });

    // Show target view
    const target = document.getElementById(viewId);
    if (target) {
      target.classList.add('active');
      this.currentView = viewId;
    }

    // Update active state in sidebar
    if (activeNavItem) {
      document.querySelectorAll('.fluent-sidebar .nav-item').forEach((item) => {
        item.classList.remove('active');
      });
      activeNavItem.classList.add('active');
    }

    // Canvas redrawing when switching to workflow view
    if (viewId === 'view-workflow' && window.workflowManager) {
      setTimeout(() => {
        window.workflowManager.drawConnectors();
      }, 50);
    }
  }

  // =========================================================================
  // TOAST NOTIFICATIONS (WINDOWS 11 FLUENT STYLE)
  // =========================================================================
  showToast(title, message, type = 'info', duration = 4000) {
    const container = document.getElementById('fluent-toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `fluent-toast toast-${type}`;
    toast.innerHTML = `
      <div class="toast-indicator"></div>
      <div class="toast-body">
        <div class="toast-title">${this.escapeHtml(title)}</div>
        <div class="toast-message">${this.escapeHtml(message)}</div>
      </div>
      <button class="toast-close">&times;</button>
    `;

    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.addEventListener('click', () => {
      toast.classList.add('hiding');
      setTimeout(() => toast.remove(), 250);
    });

    container.appendChild(toast);

    if (duration > 0) {
      setTimeout(() => {
        if (toast.parentNode) {
          toast.classList.add('hiding');
          setTimeout(() => toast.remove(), 250);
        }
      }, duration);
    }
  }

  // =========================================================================
  // MODALS MANAGEMENT
  // =========================================================================
  setupModals() {
    // Article Preview Modal Close
    const previewClose = document.getElementById('modal-preview-close');
    const previewModal = document.getElementById('modal-article-preview');
    if (previewClose && previewModal) {
      previewClose.addEventListener('click', () => {
        previewModal.classList.remove('open');
        document.getElementById('preview-iframe').src = 'about:blank';
      });
      previewModal.querySelector('.modal-backdrop').addEventListener('click', () => {
        previewModal.classList.remove('open');
        document.getElementById('preview-iframe').src = 'about:blank';
      });
    }

    // Add Skill Modal
    const skillModal = document.getElementById('modal-add-skill');
    const skillOpenBtn = document.getElementById('btn-create-skill-modal');
    const skillCloseBtn = document.getElementById('modal-skill-close');
    const skillCancelBtn = document.getElementById('modal-skill-cancel');

    if (skillModal) {
      if (skillOpenBtn) skillOpenBtn.addEventListener('click', () => skillModal.classList.add('open'));
      if (skillCloseBtn) skillCloseBtn.addEventListener('click', () => skillModal.classList.remove('open'));
      if (skillCancelBtn) skillCancelBtn.addEventListener('click', () => skillModal.classList.remove('open'));
      skillModal.querySelector('.modal-backdrop').addEventListener('click', () => skillModal.classList.remove('open'));
    }

    // Single URL Run Modal
    const singleModal = document.getElementById('modal-single-run');
    const singleOpenBtn = document.getElementById('btn-quick-run-modal');
    const singleCloseBtn = document.getElementById('modal-single-close');
    const singleCancelBtn = document.getElementById('modal-single-cancel');

    if (singleModal) {
      if (singleOpenBtn) singleOpenBtn.addEventListener('click', () => singleModal.classList.add('open'));
      if (singleCloseBtn) singleCloseBtn.addEventListener('click', () => singleModal.classList.remove('open'));
      if (singleCancelBtn) singleCancelBtn.addEventListener('click', () => singleModal.classList.remove('open'));
      singleModal.querySelector('.modal-backdrop').addEventListener('click', () => singleModal.classList.remove('open'));
    }
  }

  // =========================================================================
  // PIPELINE ORCHESTRATION CONTROLS
  // =========================================================================
  setupPipelineControls() {
    const btnStart = document.getElementById('btn-start-pipeline');
    const btnPause = document.getElementById('btn-pause-pipeline');
    const btnStop = document.getElementById('btn-stop-pipeline');
    const btnSingleStart = document.getElementById('modal-single-start');

    if (btnStart) {
      btnStart.addEventListener('click', async () => {
        try {
          const res = await fetch('/api/pipeline/start', { method: 'POST' });
          const data = await res.json();
          if (data.status === 'success') {
            this.showToast('Pipeline Started', data.message || 'Worker thread started.', 'success');
          } else {
            this.showToast('Start Error', data.message || 'Could not start pipeline.', 'error');
          }
        } catch (err) {
          this.showToast('Network Error', err.message, 'error');
        }
      });
    }

    if (btnPause) {
      btnPause.addEventListener('click', async () => {
        try {
          const currentText = btnPause.querySelector('span').textContent;
          const endpoint = currentText.toLowerCase().includes('resume') ? '/api/pipeline/resume' : '/api/pipeline/pause';
          const res = await fetch(endpoint, { method: 'POST' });
          const data = await res.json();
          this.showToast('Pipeline State', data.message, 'info');
        } catch (err) {
          this.showToast('Network Error', err.message, 'error');
        }
      });
    }

    if (btnStop) {
      btnStop.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to stop the active pipeline? Current checkpoints will be preserved.')) return;
        try {
          const res = await fetch('/api/pipeline/stop', { method: 'POST' });
          const data = await res.json();
          this.showToast('Pipeline Stopped', data.message, 'warning');
        } catch (err) {
          this.showToast('Network Error', err.message, 'error');
        }
      });
    }

    if (btnSingleStart) {
      btnSingleStart.addEventListener('click', async () => {
        const urlInput = document.getElementById('single-run-url');
        const publishWp = document.getElementById('single-run-publish-wp').checked;
        const formatSelect = document.getElementById('single-run-format');
        const articleFormat = formatSelect ? formatSelect.value : 'hybrid';
        const targetUrl = urlInput.value.trim();

        if (!targetUrl) {
          this.showToast('Missing URL', 'Please enter a valid target URL.', 'warning');
          return;
        }

        try {
          btnSingleStart.disabled = true;
          btnSingleStart.textContent = 'Processing...';

          const res = await fetch('/api/pipeline/run-single', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: targetUrl, publish_wp: publishWp, article_format: articleFormat })
          });

          const data = await res.json();
          if (data.status === 'success') {
            this.showToast('Article Completed', `Generated: ${data.title || 'Success'}`, 'success');
            document.getElementById('modal-single-run').classList.remove('open');
            urlInput.value = '';
            await this.loadArticles();
          } else {
            this.showToast('Processing Failed', data.message || 'Error executing pipeline.', 'error');
          }
        } catch (err) {
          this.showToast('Error', err.message, 'error');
        } finally {
          btnSingleStart.disabled = false;
          btnSingleStart.textContent = 'Launch Processing';
        }
      });
    }
  }

  async pollPipelineStatus() {
    try {
      const res = await fetch('/api/pipeline/status');
      if (!res.ok) return;
      const status = await res.json();
      if (window.sseClient) {
        window.sseClient.handleProgressUpdate(status);
      }
    } catch (e) {
      // Ignore background network polling error
    }
  }

  // =========================================================================
  // QUEUE & INGESTION
  // =========================================================================
  setupQueue() {
    const btnAddUrl = document.getElementById('btn-add-queue-url');
    const btnUploadCsv = document.getElementById('btn-upload-csv');
    const csvFileInput = document.getElementById('csv-file-input');
    const btnSyncFirestore = document.getElementById('btn-sync-firestore');
    const btnClearQueue = document.getElementById('btn-clear-queue');
    const btnExportBundle = document.getElementById('btn-export-bundle');
    const btnImportBundle = document.getElementById('btn-import-bundle');
    const bundleFileInput = document.getElementById('bundle-file-input');

    if (btnAddUrl) {
      btnAddUrl.addEventListener('click', async () => {
        const url = prompt('Enter target article URL to add to pipeline queue:');
        if (!url || !url.trim()) return;

        try {
          const res = await fetch('/api/queue/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url.trim() })
          });
          const data = await res.json();
          if (data.ok || data.status === 'success') {
            this.showToast('URL Queued', data.message || `Added ${data.url || 'URL'} to queue.`, 'success');
            await this.loadQueue();
          } else {
            this.showToast('Error', data.message || data.error || 'Failed to add URL.', 'error');
          }
        } catch (err) {
          this.showToast('Network Error', err.message, 'error');
        }
      });
    }

    if (btnUploadCsv && csvFileInput) {
      btnUploadCsv.addEventListener('click', () => csvFileInput.click());
      csvFileInput.addEventListener('change', async () => {
        if (!csvFileInput.files.length) return;
        const formData = new FormData();
        formData.append('file', csvFileInput.files[0]);

        try {
          const res = await fetch('/api/queue/upload-csv', {
            method: 'POST',
            body: formData
          });
          const data = await res.json();
          if (data.status === 'success') {
            this.showToast('CSV Uploaded', `Imported ${data.count || 0} URLs into queue.`, 'success');
            await this.loadQueue();
          } else {
            this.showToast('Upload Failed', data.message, 'error');
          }
        } catch (err) {
          this.showToast('Error', err.message, 'error');
        } finally {
          csvFileInput.value = '';
        }
      });
    }

    if (btnSyncFirestore) {
      btnSyncFirestore.addEventListener('click', async () => {
        try {
          btnSyncFirestore.disabled = true;
          const res = await fetch('/api/queue/sync-firestore', { method: 'POST' });
          const data = await res.json();
          if (data.status === 'success') {
            this.showToast('Firestore Synced', data.message || 'Queued articles synced.', 'success');
            await this.loadQueue();
          } else {
            this.showToast('Sync Failed', data.message, 'error');
          }
        } catch (err) {
          this.showToast('Error', err.message, 'error');
        } finally {
          btnSyncFirestore.disabled = false;
        }
      });
    }

    if (btnClearQueue) {
      btnClearQueue.addEventListener('click', async () => {
        if (!confirm('Clear all pending items from the active queue?')) return;
        try {
          const res = await fetch('/api/queue', { method: 'DELETE' });
          const data = await res.json();
          this.showToast('Queue Cleared', data.message, 'info');
          await this.loadQueue();
        } catch (err) {
          this.showToast('Error', err.message, 'error');
        }
      });
    }

    if (btnExportBundle) {
      btnExportBundle.addEventListener('click', () => {
        window.location.href = '/api/queue/export-bundle';
      });
    }

    if (btnImportBundle && bundleFileInput) {
      btnImportBundle.addEventListener('click', () => bundleFileInput.click());
      bundleFileInput.addEventListener('change', async () => {
        if (!bundleFileInput.files.length) return;
        const formData = new FormData();
        formData.append('bundle', bundleFileInput.files[0]);

        try {
          const res = await fetch('/api/queue/import-bundle', {
            method: 'POST',
            body: formData
          });
          const data = await res.json();
          if (data.status === 'success') {
            this.showToast('Bundle Imported', data.message, 'success');
            await this.loadQueue();
          } else {
            this.showToast('Import Failed', data.message, 'error');
          }
        } catch (err) {
          this.showToast('Error', err.message, 'error');
        } finally {
          bundleFileInput.value = '';
        }
      });
    }
  }

  async loadQueue() {
    try {
      const res = await fetch('/api/queue');
      if (!res.ok) return;
      const data = await res.json();
      const items = data.links || data.items || [];

      const tbody = document.getElementById('queue-table-body');
      const badgeCount = document.getElementById('queue-count-badge');
      const statQueue = document.getElementById('stat-queue-count');

      if (badgeCount) badgeCount.textContent = items.length;
      if (statQueue) statQueue.textContent = items.length;

      if (!tbody) return;

      if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="table-empty">No URLs in active queue. Add a URL or upload a CSV file above.</td></tr>`;
        return;
      }

      let html = '';
      items.forEach((item, idx) => {
        html += `
          <tr>
            <td>${idx + 1}</td>
            <td style="max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              <strong>${this.escapeHtml(item.url || '')}</strong>
            </td>
            <td>
              <span class="fluent-badge badge-${(item.status || 'pending').toLowerCase()}">${item.status || 'Pending'}</span>
            </td>
            <td>${item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Today'}</td>
            <td style="text-align: right;">
              <button class="table-action-btn" onclick="window.fluentApp.removeQueueItem(${idx})" title="Remove item">&times;</button>
            </td>
          </tr>
        `;
      });
      tbody.innerHTML = html;
    } catch (e) {
      console.error('Error loading queue:', e);
    }
  }

  async removeQueueItem(index) {
    try {
      const res = await fetch(`/api/queue/${index}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.status === 'success') {
        this.showToast('Item Removed', 'Removed item from queue.', 'info');
        await this.loadQueue();
      }
    } catch (e) {
      this.showToast('Error', e.message, 'error');
    }
  }

  // =========================================================================
  // ARTICLES CATALOG
  // =========================================================================
  setupArticles() {
    const refreshBtn = document.getElementById('btn-refresh-articles');
    const openFolderBtn = document.getElementById('btn-open-output-folder');
    const quickOpenBtn = document.getElementById('quick-open-output');

    if (refreshBtn) refreshBtn.addEventListener('click', () => this.loadArticles());

    const openFolder = async () => {
      try {
        await fetch('/api/articles/open-folder', { method: 'POST' });
        this.showToast('Folder Opened', 'Opened output directory in Windows Explorer.', 'info');
      } catch (e) {
        this.showToast('Error', e.message, 'error');
      }
    };

    if (openFolderBtn) openFolderBtn.addEventListener('click', openFolder);
    if (quickOpenBtn) quickOpenBtn.addEventListener('click', openFolder);
  }

  async loadArticles() {
    try {
      const res = await fetch('/api/articles');
      if (!res.ok) return;
      const data = await res.json();
      const articles = data.articles || [];

      const grid = document.getElementById('articles-grid');
      const statArticles = document.getElementById('stat-total-articles');
      if (statArticles) statArticles.textContent = articles.length;

      if (!grid) return;

      if (articles.length === 0) {
        grid.innerHTML = `<div class="articles-empty"><p>No articles generated yet. Run the pipeline to compile your first article.</p></div>`;
        return;
      }

      let html = '';
      articles.forEach((art) => {
        const thumbUrl = art.featured_image ? `/api/articles/${art.folder}/image` : '/static/assets/placeholder.jpg';
        html += `
          <div class="fluent-card article-card">
            <div class="article-thumb" style="background-image: url('${thumbUrl}');">
              <span class="article-category-badge">${this.escapeHtml(art.category || 'Article')}</span>
            </div>
            <div class="article-content">
              <h4 class="article-title">${this.escapeHtml(art.title || art.folder)}</h4>
              <div class="article-meta">
                <span>${art.word_count || 0} words</span>
                <span>•</span>
                <span>${art.created_at || 'Compiled'}</span>
              </div>
              <div class="article-card-actions">
                <button class="fluent-btn btn-sm btn-outline" onclick="window.fluentApp.previewArticle('${art.folder}', '${this.escapeHtml(art.title || '')}')">Preview HTML</button>
                <button class="fluent-btn btn-sm btn-accent" onclick="window.fluentApp.publishArticle('${art.folder}')">Publish to WP</button>
              </div>
            </div>
          </div>
        `;
      });
      grid.innerHTML = html;
    } catch (e) {
      console.error('Error loading articles:', e);
    }
  }

  previewArticle(folder, title) {
    const modal = document.getElementById('modal-article-preview');
    const iframe = document.getElementById('preview-iframe');
    const titleEl = document.getElementById('preview-article-title');

    if (titleEl) titleEl.textContent = title || 'Article Preview';
    if (iframe) iframe.src = `/api/articles/${folder}/html`;
    if (modal) modal.classList.add('open');
  }

  async publishArticle(folder) {
    try {
      this.showToast('Publishing...', `Sending ${folder} to WordPress`, 'info');
      const res = await fetch('/api/wordpress/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder: folder })
      });
      const data = await res.json();
      if (data.status === 'success') {
        this.showToast('Published!', data.message || 'Article published to WordPress.', 'success');
      } else {
        this.showToast('Publish Error', data.message, 'error');
      }
    } catch (e) {
      this.showToast('Error', e.message, 'error');
    }
  }

  // =========================================================================
  // VISUAL STUDIO & PROMPT ENHANCER
  // =========================================================================
  setupVisuals() {
    // 1. Article Resolution Custom Toggle
    const resSelect = document.getElementById('visual-resolution');
    const customResGroup = document.getElementById('visual-custom-res-group');
    if (resSelect && customResGroup) {
      resSelect.addEventListener('change', () => {
        customResGroup.style.display = resSelect.value === 'custom' ? 'grid' : 'none';
      });
    }

    // 2. Feature Resolution Custom Toggle
    const featResSelect = document.getElementById('visual-feature-resolution');
    const customFeatResGroup = document.getElementById('visual-custom-feature-res-group');
    if (featResSelect && customFeatResGroup) {
      featResSelect.addEventListener('change', () => {
        customFeatResGroup.style.display = featResSelect.value === 'custom' ? 'grid' : 'none';
      });
    }

    // 3. Visual Art Style Custom Prompt Toggle
    const styleSelect = document.getElementById('visual-style');
    const customStyleGroup = document.getElementById('visual-custom-style-group');
    if (styleSelect && customStyleGroup) {
      styleSelect.addEventListener('change', () => {
        customStyleGroup.style.display = styleSelect.value === 'custom' ? 'block' : 'none';
      });
    }

    // 4. Content Format Help Text & Sync
    const formatSelect = document.getElementById('visual-article-format');
    const formatHelp = document.getElementById('visual-format-help');
    const formatDescMap = {
      hybrid: 'Rich explanatory paragraphs followed by an actionable key takeaways / bullet list.',
      point_wise: 'Concise context introduction followed by 4–6 scannable bullet points and takeaways.',
      paragraphs: 'Traditional in-depth narrative paragraphs (2–4 comprehensive paragraphs per section).',
      subheadings: 'Main H2 sections divided into 2–3 H3 subheadings with focused explanations.'
    };
    if (formatSelect) {
      formatSelect.addEventListener('change', () => {
        if (formatHelp && formatDescMap[formatSelect.value]) {
          formatHelp.textContent = formatDescMap[formatSelect.value];
        }
        const settingFmt = document.getElementById('setting-article-format');
        if (settingFmt) settingFmt.value = formatSelect.value;
        const singleFmt = document.getElementById('single-run-format');
        if (singleFmt) singleFmt.value = formatSelect.value;
      });
    }

    // 5. Save Visual Settings Handler
    const btnSave = document.getElementById('btn-save-visual-settings');
    if (btnSave) {
      btnSave.addEventListener('click', async () => {
        // Resolve section image resolution
        let sectionRes = resSelect ? resSelect.value : 'landscape_16_9';
        if (sectionRes === 'custom') {
          const w = parseInt(document.getElementById('visual-custom-res-w').value, 10) || 1200;
          const h = parseInt(document.getElementById('visual-custom-res-h').value, 10) || 675;
          sectionRes = `${w}x${h}`;
        }

        // Resolve featured image resolution
        let featRes = featResSelect ? featResSelect.value : 'landscape_16_9';
        if (featRes === 'custom') {
          const fw = parseInt(document.getElementById('visual-custom-feat-w').value, 10) || 1200;
          const fh = parseInt(document.getElementById('visual-custom-feat-h').value, 10) || 630;
          featRes = `${fw}x${fh}`;
        }

        const payload = {
          image_engine: document.getElementById('visual-engine').value,
          image_resolution: sectionRes,
          image_resolution_preset: sectionRes,
          feature_resolution: featRes,
          image_type: styleSelect ? styleSelect.value : 'photo',
          visual_style: styleSelect ? styleSelect.value : 'photo',
          image_type_custom: document.getElementById('visual-custom-style-prompt') ? document.getElementById('visual-custom-style-prompt').value.trim() : '',
          image_type_prompt: document.getElementById('visual-image-type').value.trim(),
          master_image_prompt: document.getElementById('visual-master-prompt').value.trim(),
          negative_prompt: document.getElementById('visual-negative-prompt').value.trim(),

          // Featured Image & Title Writer (OpenCV)
          feature_image_master_prompt: document.getElementById('visual-feature-master-prompt') ? document.getElementById('visual-feature-master-prompt').value.trim() : '',
          feature_text_overlay: document.getElementById('visual-feature-text-overlay') ? document.getElementById('visual-feature-text-overlay').checked : true,
          heading_text_overlay: document.getElementById('visual-heading-text-overlay') ? document.getElementById('visual-heading-text-overlay').checked : false,
          render_font_family: document.getElementById('visual-font-family') ? document.getElementById('visual-font-family').value : 'arial.ttf',
          render_header_font_size: parseInt(document.getElementById('visual-font-size') ? document.getElementById('visual-font-size').value : 48, 10) || 48,
          render_scrim_enabled: document.getElementById('visual-scrim-enabled') ? document.getElementById('visual-scrim-enabled').checked : true,

          // Content Format & Master Text
          article_format: formatSelect ? formatSelect.value : 'hybrid',
          master_text_prompt: document.getElementById('visual-master-text-prompt') ? document.getElementById('visual-master-text-prompt').value.trim() : '',

          // Pinterest Pin Settings
          generate_pinterest_pin: document.getElementById('visual-pinterest-enabled').checked,
          pinterest_pin_style: document.getElementById('visual-pin-style').value,
          master_pin_prompt: document.getElementById('visual-master-pin-prompt').value.trim()
        };

        try {
          const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          const data = await res.json();
          if (data.status === 'success' || data.ok) {
            this.showToast('Visual Settings Saved', 'Image resolutions, custom styles, featured hero and title writer updated.', 'success');
            await this.loadSettings();
          } else {
            this.showToast('Save Error', data.message || 'Could not save settings.', 'error');
          }
        } catch (e) {
          this.showToast('Error', e.message, 'error');
        }
      });
    }
  }

  // =========================================================================
  // AI SKILLS ENGINE (SEO / GEO / AEO)
  // =========================================================================
  setupSkills() {
    const refreshBtn = document.getElementById('btn-refresh-skills');
    const saveSkillBtn = document.getElementById('modal-skill-save');

    if (refreshBtn) refreshBtn.addEventListener('click', () => this.loadSkills());

    if (saveSkillBtn) {
      saveSkillBtn.addEventListener('click', async () => {
        const title = document.getElementById('skill-form-title').value.trim();
        const filename = document.getElementById('skill-form-filename').value.trim();
        const category = document.getElementById('skill-form-category').value;
        const content = document.getElementById('skill-form-content').value.trim();

        if (!title || !filename || !content) {
          this.showToast('Incomplete Skill', 'Title, filename, and markdown content are required.', 'warning');
          return;
        }

        try {
          const res = await fetch('/api/skills', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, filename, category, content })
          });
          const data = await res.json();
          if (data.status === 'success') {
            this.showToast('Skill Created', `Saved ${filename} to Skills/ folder.`, 'success');
            document.getElementById('modal-add-skill').classList.remove('open');
            await this.loadSkills();
          } else {
            this.showToast('Error', data.message, 'error');
          }
        } catch (e) {
          this.showToast('Error', e.message, 'error');
        }
      });
    }
  }

  async loadSkills() {
    try {
      const res = await fetch('/api/skills');
      if (!res.ok) return;
      const data = await res.json();
      const skills = data.skills || [];

      const grid = document.getElementById('skills-grid');
      const statSkills = document.getElementById('stat-active-skills');

      const activeCount = skills.filter((s) => s.enabled).length;
      if (statSkills) statSkills.textContent = activeCount;

      if (!grid) return;

      let html = '';
      skills.forEach((skill) => {
        html += `
          <div class="fluent-card skill-card">
            <div class="skill-header">
              <div>
                <span class="skill-category-badge badge-${skill.category.toLowerCase()}">${skill.category.toUpperCase()}</span>
                <h4 class="skill-title">${this.escapeHtml(skill.title)}</h4>
                <span class="skill-filename">${this.escapeHtml(skill.filename)}</span>
              </div>
              <label class="fluent-switch">
                <input type="checkbox" ${skill.enabled ? 'checked' : ''} onchange="window.fluentApp.toggleSkill('${skill.filename}', this.checked)">
                <span class="fluent-slider"></span>
              </label>
            </div>
            <p class="skill-snippet">${this.escapeHtml(skill.snippet || 'Markdown directive for LLM transformation')}</p>
          </div>
        `;
      });
      grid.innerHTML = html;
    } catch (e) {
      console.error('Error loading skills:', e);
    }
  }

  async toggleSkill(filename, enabled) {
    try {
      const res = await fetch(`/api/skills/${filename}/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      const data = await res.json();
      if (data.status === 'success') {
        this.showToast('Skill Toggled', `${filename} is now ${enabled ? 'active' : 'disabled'}.`, 'info');
        await this.loadSkills();
      }
    } catch (e) {
      this.showToast('Error', e.message, 'error');
    }
  }

  // =========================================================================
  // WORDPRESS HUB
  // =========================================================================
  setupWordPress() {
    const btnTest = document.getElementById('btn-test-wp-conn');
    const btnSave = document.getElementById('btn-save-wp-settings');
    const quickTestBtn = document.getElementById('quick-test-wp');

    const testConnection = async () => {
      const statusBox = document.getElementById('wp-connection-status');
      const statusText = document.getElementById('wp-status-text');

      statusText.textContent = 'Testing REST API connection and authentication...';
      try {
        const res = await fetch('/api/wordpress/test-connection', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
          statusBox.className = 'wp-connection-status conn-success';
          statusText.textContent = `Connected successfully! Site: ${data.site_name || 'WordPress'} (v${data.version || 'REST'})`;
          this.showToast('Connection Verified', 'WordPress REST API is accessible.', 'success');
        } else {
          statusBox.className = 'wp-connection-status conn-error';
          statusText.textContent = `Connection failed: ${data.message}`;
          this.showToast('Connection Failed', data.message, 'error');
        }
      } catch (e) {
        statusBox.className = 'wp-connection-status conn-error';
        statusText.textContent = `Network error: ${e.message}`;
        this.showToast('Connection Error', e.message, 'error');
      }
    };

    if (btnTest) btnTest.addEventListener('click', testConnection);
    if (quickTestBtn) quickTestBtn.addEventListener('click', testConnection);

    if (btnSave) {
      btnSave.addEventListener('click', async () => {
        const payload = {
          wordpress_url: document.getElementById('wp-site-url').value.trim(),
          wordpress_username: document.getElementById('wp-username').value.trim(),
          wordpress_app_password: document.getElementById('wp-app-password').value.trim(),
          wordpress_post_status: document.getElementById('wp-post-status').value,
          wordpress_default_category: parseInt(document.getElementById('wp-category-id').value, 10) || 1,
          wordpress_author_id: parseInt(document.getElementById('wp-author-id').value, 10) || 1,
          rank_math_sync: document.getElementById('wp-rank-math-sync').checked
        };

        try {
          const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          const data = await res.json();
          if (data.status === 'success') {
            this.showToast('WordPress Config Saved', 'WordPress settings saved.', 'success');
          }
        } catch (e) {
          this.showToast('Error', e.message, 'error');
        }
      });
    }
  }

  // =========================================================================
  // SETTINGS PANEL
  // =========================================================================
  setupSettings() {
    // Settings subnav tabs
    const tabs = document.querySelectorAll('.settings-tab-btn');
    tabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        tabs.forEach((t) => t.classList.remove('active'));
        tab.classList.add('active');

        const targetId = tab.dataset.tab;
        document.querySelectorAll('.settings-tab-panel').forEach((panel) => {
          panel.classList.remove('active');
        });
        const activePanel = document.getElementById(targetId);
        if (activePanel) activePanel.classList.add('active');
      });
    });

    const btnSaveAll = document.getElementById('btn-save-all-settings');
    if (btnSaveAll) {
      btnSaveAll.addEventListener('click', async () => {
        const payload = {
          execution_mode: document.getElementById('setting-execution-mode').value,
          output_dir: document.getElementById('setting-output-dir').value.trim(),
          auto_launch_browser: document.getElementById('setting-auto-browser').checked,
          gemini_api_key: document.getElementById('setting-gemini-key').value.trim(),
          gemini_model: document.getElementById('setting-gemini-model').value,
          article_format: document.getElementById('setting-article-format').value,
          master_text_prompt: document.getElementById('setting-master-text-prompt').value.trim(),
          custom_gpu_endpoint: document.getElementById('setting-gpu-url').value.trim(),
          custom_gpu_token: document.getElementById('setting-gpu-token').value.trim(),
          firebase_api_key: document.getElementById('setting-firebase-key').value.trim(),
          firestore_project_id: document.getElementById('setting-firestore-project').value.trim(),
          firestore_collection: document.getElementById('setting-firestore-collection').value.trim(),
          firebase_email: document.getElementById('setting-firebase-email').value.trim(),
          firebase_password: document.getElementById('setting-firebase-password').value.trim(),
          render_font_family: document.getElementById('setting-font-family').value,
          render_header_font_size: parseInt(document.getElementById('setting-font-size').value, 10) || 48,
          render_scrim_enabled: document.getElementById('setting-render-scrim').checked
        };

        try {
          const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          const data = await res.json();
          if (data.status === 'success') {
            this.showToast('Settings Saved', 'All preferences saved to pipeline_config.json.', 'success');
          }
        } catch (e) {
          this.showToast('Error', e.message, 'error');
        }
      });
    }
  }

  async loadSettings() {
    try {
      const res = await fetch('/api/settings');
      if (!res.ok) return;
      const data = await res.json();
      const cfg = data.settings || data;
      this.settings = cfg;

      // ── Populate Visual Studio: Engine, Resolution, Style ──
      if (document.getElementById('visual-engine')) {
        document.getElementById('visual-engine').value = cfg.image_engine || 'pollinations';
      }

      // Section Resolution & Custom Dimensions
      const sectionRes = cfg.image_resolution || cfg.image_resolution_preset || 'landscape_16_9';
      const knownSectionPresets = ['landscape_16_9', 'square_1_1', 'portrait_4_5', 'vertical_9_16', 'banner_3_1'];
      const resSelect = document.getElementById('visual-resolution');
      const customResGroup = document.getElementById('visual-custom-res-group');
      if (resSelect) {
        if (knownSectionPresets.includes(sectionRes)) {
          resSelect.value = sectionRes;
          if (customResGroup) customResGroup.style.display = 'none';
        } else if (sectionRes.includes('x') || sectionRes.includes('X')) {
          resSelect.value = 'custom';
          if (customResGroup) customResGroup.style.display = 'grid';
          const parts = sectionRes.toLowerCase().split('x');
          if (document.getElementById('visual-custom-res-w')) document.getElementById('visual-custom-res-w').value = parts[0] || 1200;
          if (document.getElementById('visual-custom-res-h')) document.getElementById('visual-custom-res-h').value = parts[1] || 675;
        } else {
          resSelect.value = 'landscape_16_9';
          if (customResGroup) customResGroup.style.display = 'none';
        }
      }

      // Featured Resolution & Custom Dimensions
      const featRes = cfg.feature_resolution || 'landscape_16_9';
      const knownFeatPresets = ['landscape_16_9', 'opengraph_1200_630', 'fhd_16_9', 'banner_3_1'];
      const featSelect = document.getElementById('visual-feature-resolution');
      const customFeatGroup = document.getElementById('visual-custom-feature-res-group');
      if (featSelect) {
        if (knownFeatPresets.includes(featRes)) {
          featSelect.value = featRes;
          if (customFeatGroup) customFeatGroup.style.display = 'none';
        } else if (featRes.includes('x') || featRes.includes('X')) {
          featSelect.value = 'custom';
          if (customFeatGroup) customFeatGroup.style.display = 'grid';
          const fparts = featRes.toLowerCase().split('x');
          if (document.getElementById('visual-custom-feat-w')) document.getElementById('visual-custom-feat-w').value = fparts[0] || 1200;
          if (document.getElementById('visual-custom-feat-h')) document.getElementById('visual-custom-feat-h').value = fparts[1] || 630;
        } else {
          featSelect.value = 'landscape_16_9';
          if (customFeatGroup) customFeatGroup.style.display = 'none';
        }
      }

      // Visual Art Style & Custom Prompt
      const styleVal = cfg.image_type || cfg.visual_style || 'photorealistic';
      const styleSelect = document.getElementById('visual-style');
      const customStyleGroup = document.getElementById('visual-custom-style-group');
      if (styleSelect) {
        styleSelect.value = styleVal;
        if (customStyleGroup) {
          customStyleGroup.style.display = styleVal === 'custom' ? 'block' : 'none';
        }
      }
      if (document.getElementById('visual-custom-style-prompt')) {
        document.getElementById('visual-custom-style-prompt').value = cfg.image_type_custom || '';
      }

      if (document.getElementById('visual-image-type')) document.getElementById('visual-image-type').value = cfg.image_type_prompt || '';
      if (document.getElementById('visual-master-prompt')) document.getElementById('visual-master-prompt').value = cfg.master_image_prompt || '';
      if (document.getElementById('visual-negative-prompt')) document.getElementById('visual-negative-prompt').value = cfg.negative_prompt || '';

      // ── Populate Featured Image & Title Writer ──
      if (document.getElementById('visual-feature-master-prompt')) {
        document.getElementById('visual-feature-master-prompt').value = cfg.feature_image_master_prompt || '';
      }
      if (document.getElementById('visual-feature-text-overlay')) {
        document.getElementById('visual-feature-text-overlay').checked = cfg.feature_text_overlay !== false;
      }
      if (document.getElementById('visual-heading-text-overlay')) {
        document.getElementById('visual-heading-text-overlay').checked = !!cfg.heading_text_overlay;
      }
      if (document.getElementById('visual-font-family')) {
        document.getElementById('visual-font-family').value = cfg.render_font_family || 'arial.ttf';
      }
      if (document.getElementById('visual-font-size')) {
        document.getElementById('visual-font-size').value = cfg.render_header_font_size || 48;
      }
      if (document.getElementById('visual-scrim-enabled')) {
        document.getElementById('visual-scrim-enabled').checked = cfg.render_scrim_enabled !== false;
      }

      // ── Populate Content Architecture & Format ──
      const activeFmt = cfg.article_format || 'hybrid';
      if (document.getElementById('visual-article-format')) {
        document.getElementById('visual-article-format').value = activeFmt;
      }
      if (document.getElementById('setting-article-format')) {
        document.getElementById('setting-article-format').value = activeFmt;
      }
      if (document.getElementById('single-run-format')) {
        document.getElementById('single-run-format').value = activeFmt;
      }
      if (document.getElementById('visual-master-text-prompt')) {
        document.getElementById('visual-master-text-prompt').value = cfg.master_text_prompt || '';
      }
      const formatHelp = document.getElementById('visual-format-help');
      const formatDescMap = {
        hybrid: 'Rich explanatory paragraphs followed by an actionable key takeaways / bullet list.',
        point_wise: 'Concise context introduction followed by 4–6 scannable bullet points and takeaways.',
        paragraphs: 'Traditional in-depth narrative paragraphs (2–4 comprehensive paragraphs per section).',
        subheadings: 'Main H2 sections divided into 2–3 H3 subheadings with focused explanations.'
      };
      if (formatHelp && formatDescMap[activeFmt]) {
        formatHelp.textContent = formatDescMap[activeFmt];
      }

      // ── Populate Pinterest Pin ──
      if (document.getElementById('visual-pinterest-enabled')) document.getElementById('visual-pinterest-enabled').checked = !!cfg.generate_pinterest_pin;
      if (document.getElementById('visual-pin-style')) document.getElementById('visual-pin-style').value = cfg.pinterest_pin_style || 'modern_minimalist';
      if (document.getElementById('visual-master-pin-prompt')) document.getElementById('visual-master-pin-prompt').value = cfg.master_pin_prompt || '';

      // ── Populate WordPress Hub ──
      if (document.getElementById('wp-site-url')) document.getElementById('wp-site-url').value = cfg.wordpress_url || '';
      if (document.getElementById('wp-username')) document.getElementById('wp-username').value = cfg.wordpress_username || '';
      if (document.getElementById('wp-app-password')) document.getElementById('wp-app-password').value = cfg.wordpress_app_password || '';
      if (document.getElementById('wp-post-status')) document.getElementById('wp-post-status').value = cfg.wordpress_post_status || 'draft';
      if (document.getElementById('wp-category-id')) document.getElementById('wp-category-id').value = cfg.wordpress_default_category || 1;
      if (document.getElementById('wp-author-id')) document.getElementById('wp-author-id').value = cfg.wordpress_author_id || 1;
      if (document.getElementById('wp-rank-math-sync')) document.getElementById('wp-rank-math-sync').checked = cfg.rank_math_sync !== false;

      // ── Populate Settings View ──
      if (document.getElementById('setting-execution-mode')) document.getElementById('setting-execution-mode').value = cfg.execution_mode || 'online';
      if (document.getElementById('setting-output-dir')) document.getElementById('setting-output-dir').value = cfg.output_dir || 'output';
      if (document.getElementById('setting-auto-browser')) document.getElementById('setting-auto-browser').checked = cfg.auto_launch_browser !== false;
      if (document.getElementById('setting-gemini-key')) document.getElementById('setting-gemini-key').value = cfg.gemini_api_key || '';
      if (document.getElementById('setting-gemini-model')) document.getElementById('setting-gemini-model').value = cfg.gemini_model || 'gemini-2.5-flash';
      if (document.getElementById('setting-master-text-prompt')) document.getElementById('setting-master-text-prompt').value = cfg.master_text_prompt || '';
      if (document.getElementById('setting-gpu-url')) document.getElementById('setting-gpu-url').value = cfg.custom_gpu_endpoint || '';
      if (document.getElementById('setting-gpu-token')) document.getElementById('setting-gpu-token').value = cfg.custom_gpu_token || '';
      if (document.getElementById('setting-firebase-key')) document.getElementById('setting-firebase-key').value = cfg.firebase_api_key || '';
      if (document.getElementById('setting-firestore-project')) document.getElementById('setting-firestore-project').value = cfg.firestore_project_id || '';
      if (document.getElementById('setting-firestore-collection')) document.getElementById('setting-firestore-collection').value = cfg.firestore_collection || 'articles';
      if (document.getElementById('setting-firebase-email')) document.getElementById('setting-firebase-email').value = cfg.firebase_email || '';
      if (document.getElementById('setting-font-family')) document.getElementById('setting-font-family').value = cfg.render_font_family || 'arial.ttf';
      if (document.getElementById('setting-font-size')) document.getElementById('setting-font-size').value = cfg.render_header_font_size || 48;
      if (document.getElementById('setting-render-scrim')) document.getElementById('setting-render-scrim').checked = cfg.render_scrim_enabled !== false;

      // Update sidebar role label
      const engineMode = document.getElementById('engine-display-mode');
      if (engineMode) {
        engineMode.textContent = `${(cfg.execution_mode || 'online').toUpperCase()} Pipeline`;
      }
    } catch (e) {
      console.error('Error loading settings:', e);
    }
  }

  // =========================================================================
  // LIVE CONSOLE & LOGS
  // =========================================================================
  setupConsole() {
    const clearBtn = document.getElementById('btn-clear-logs');
    const downloadBtn = document.getElementById('btn-download-logs');

    if (clearBtn) {
      clearBtn.addEventListener('click', async () => {
        try {
          await fetch('/api/logs/clear', { method: 'POST' });
          if (window.sseClient) window.sseClient.clear();
          this.showToast('Console Cleared', 'In-memory log buffer reset.', 'info');
        } catch (e) {
          this.showToast('Error', e.message, 'error');
        }
      });
    }

    if (downloadBtn) {
      downloadBtn.addEventListener('click', () => {
        window.location.href = '/api/logs/download';
      });
    }
  }

  async refreshDashboardStats() {
    try {
      const queueRes = await fetch('/api/queue');
      const queueData = await queueRes.json();
      const count = (queueData.items || []).length;

      const statQueue = document.getElementById('stat-queue-count');
      if (statQueue) statQueue.textContent = count;
    } catch (e) {
      // Non-blocking
    }
  }

  async refreshAllData() {
    await this.loadSettings();
    await this.refreshDashboardStats();
    await this.loadQueue();
    await this.loadArticles();
    await this.loadSkills();
    await this.pollPipelineStatus();
  }

  escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Global initialization
document.addEventListener('DOMContentLoaded', () => {
  window.fluentApp = new FluentApp();
});
