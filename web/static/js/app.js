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
            body: JSON.stringify({ url: targetUrl, publish_wp: publishWp })
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
    const btnSave = document.getElementById('btn-save-visual-settings');
    if (btnSave) {
      btnSave.addEventListener('click', async () => {
        const payload = {
          image_engine: document.getElementById('visual-engine').value,
          image_resolution_preset: document.getElementById('visual-resolution').value,
          visual_style: document.getElementById('visual-style').value,
          image_type_prompt: document.getElementById('visual-image-type').value,
          master_image_prompt: document.getElementById('visual-master-prompt').value,
          negative_prompt: document.getElementById('visual-negative-prompt').value,
          generate_pinterest_pin: document.getElementById('visual-pinterest-enabled').checked,
          pinterest_pin_style: document.getElementById('visual-pin-style').value,
          master_pin_prompt: document.getElementById('visual-master-pin-prompt').value
        };

        try {
          const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          const data = await res.json();
          if (data.status === 'success') {
            this.showToast('Visuals Saved', 'Image synthesis settings updated.', 'success');
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
      const cfg = await res.json();
      this.settings = cfg;

      // Populate Visual Studio
      if (document.getElementById('visual-engine')) document.getElementById('visual-engine').value = cfg.image_engine || 'pollinations';
      if (document.getElementById('visual-resolution')) document.getElementById('visual-resolution').value = cfg.image_resolution_preset || 'landscape_16_9';
      if (document.getElementById('visual-style')) document.getElementById('visual-style').value = cfg.visual_style || 'photorealistic';
      if (document.getElementById('visual-image-type')) document.getElementById('visual-image-type').value = cfg.image_type_prompt || '';
      if (document.getElementById('visual-master-prompt')) document.getElementById('visual-master-prompt').value = cfg.master_image_prompt || '';
      if (document.getElementById('visual-negative-prompt')) document.getElementById('visual-negative-prompt').value = cfg.negative_prompt || '';
      if (document.getElementById('visual-pinterest-enabled')) document.getElementById('visual-pinterest-enabled').checked = !!cfg.generate_pinterest_pin;
      if (document.getElementById('visual-pin-style')) document.getElementById('visual-pin-style').value = cfg.pinterest_pin_style || 'modern_minimalist';
      if (document.getElementById('visual-master-pin-prompt')) document.getElementById('visual-master-pin-prompt').value = cfg.master_pin_prompt || '';

      // Populate WordPress Hub
      if (document.getElementById('wp-site-url')) document.getElementById('wp-site-url').value = cfg.wordpress_url || '';
      if (document.getElementById('wp-username')) document.getElementById('wp-username').value = cfg.wordpress_username || '';
      if (document.getElementById('wp-app-password')) document.getElementById('wp-app-password').value = cfg.wordpress_app_password || '';
      if (document.getElementById('wp-post-status')) document.getElementById('wp-post-status').value = cfg.wordpress_post_status || 'draft';
      if (document.getElementById('wp-category-id')) document.getElementById('wp-category-id').value = cfg.wordpress_default_category || 1;
      if (document.getElementById('wp-author-id')) document.getElementById('wp-author-id').value = cfg.wordpress_author_id || 1;
      if (document.getElementById('wp-rank-math-sync')) document.getElementById('wp-rank-math-sync').checked = cfg.rank_math_sync !== false;

      // Populate Settings View
      if (document.getElementById('setting-execution-mode')) document.getElementById('setting-execution-mode').value = cfg.execution_mode || 'online';
      if (document.getElementById('setting-output-dir')) document.getElementById('setting-output-dir').value = cfg.output_dir || 'output';
      if (document.getElementById('setting-auto-browser')) document.getElementById('setting-auto-browser').checked = cfg.auto_launch_browser !== false;
      if (document.getElementById('setting-gemini-key')) document.getElementById('setting-gemini-key').value = cfg.gemini_api_key || '';
      if (document.getElementById('setting-gemini-model')) document.getElementById('setting-gemini-model').value = cfg.gemini_model || 'gemini-2.5-flash';
      if (document.getElementById('setting-article-format')) document.getElementById('setting-article-format').value = cfg.article_format || 'hybrid';
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
