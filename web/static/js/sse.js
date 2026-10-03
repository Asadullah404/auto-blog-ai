/**
 * Content Pipeline Pro - Server-Sent Events (SSE) Client
 * Establishes real-time streaming connection for logs and pipeline progress.
 */

class SSEClient {
  constructor() {
    this.eventSource = null;
    this.reconnectDelay = 2000;
    this.maxReconnectDelay = 10000;
    this.currentDelay = 2000;
    this.autoScroll = true;
    this.maxLogLines = 500;
    this.logHistory = [];

    this.terminal = document.getElementById('fluent-terminal');
    this.miniLogs = document.getElementById('dashboard-mini-logs');
    this.autoScrollCheckbox = document.getElementById('logs-auto-scroll');

    if (this.autoScrollCheckbox) {
      this.autoScrollCheckbox.addEventListener('change', (e) => {
        this.autoScroll = e.target.checked;
      });
    }

    this.init();
  }

  init() {
    this.connect();
    this.setupFilters();
  }

  connect() {
    if (this.eventSource) {
      this.eventSource.close();
    }

    this.eventSource = new EventSource('/api/logs/stream');

    this.eventSource.onopen = () => {
      this.currentDelay = this.reconnectDelay;
      this.addLogLine({
        timestamp: new Date().toLocaleTimeString(),
        level: 'SUCCESS',
        message: 'Connected to live pipeline event stream.'
      });
    };

    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'log') {
          this.handleLogMessage(data.payload);
        } else if (data.type === 'status' || data.type === 'progress') {
          this.handleProgressUpdate(data.payload);
        }
      } catch (err) {
        // Fallback for plain text
        this.addLogLine({
          timestamp: new Date().toLocaleTimeString(),
          level: 'INFO',
          message: event.data
        });
      }
    };

    this.eventSource.onerror = () => {
      this.eventSource.close();
      setTimeout(() => {
        this.currentDelay = Math.min(this.currentDelay * 1.5, this.maxReconnectDelay);
        this.connect();
      }, this.currentDelay);
    };
  }

  handleLogMessage(logEntry) {
    this.logHistory.push(logEntry);
    if (this.logHistory.length > this.maxLogLines) {
      this.logHistory.shift();
    }
    this.addLogLine(logEntry);
  }

  handleProgressUpdate(status) {
    const badge = document.getElementById('pipeline-status-badge');
    const badgeText = document.getElementById('pipeline-status-text');
    const activeTask = document.getElementById('pipeline-active-task');
    const execArticle = document.getElementById('exec-article-title');
    const execPhase = document.getElementById('exec-phase-badge');
    const execPercent = document.getElementById('exec-percentage');
    const execBar = document.getElementById('exec-progress-bar');
    const execDetails = document.getElementById('exec-detail-text');
    const execCounter = document.getElementById('exec-item-counter');
    const execPulse = document.getElementById('exec-pulse');

    // Update status badge
    if (badge && badgeText) {
      const state = (status.state || 'idle').toLowerCase();
      badge.className = `fluent-badge badge-${state}`;
      badgeText.textContent = state.charAt(0).toUpperCase() + state.slice(1);
    }

    if (activeTask && status.current_task) {
      activeTask.textContent = status.current_task;
    }

    if (execArticle && status.article_title) {
      execArticle.textContent = status.article_title;
    }

    if (execPhase && status.phase_name) {
      execPhase.textContent = status.phase_name;
      execPhase.className = `fluent-badge badge-${(status.state || 'active').toLowerCase()}`;
    }

    const percent = Math.min(100, Math.max(0, Math.round(status.progress || 0)));
    if (execPercent) execPercent.textContent = `${percent}%`;
    if (execBar) execBar.style.width = `${percent}%`;

    if (execDetails && status.message) {
      execDetails.textContent = status.message;
    }

    if (execCounter && status.total_items) {
      execCounter.textContent = `${status.current_item || 0} / ${status.total_items} items`;
    }

    // Toggle pulse animation
    if (execPulse) {
      if (status.state === 'running') {
        execPulse.classList.add('pulse-active');
      } else {
        execPulse.classList.remove('pulse-active');
      }
    }

    // Update workflow canvas node state
    if (window.workflowManager) {
      window.workflowManager.updateFromProgress(status);
    }

    // Update toolbar button states
    const btnStart = document.getElementById('btn-start-pipeline');
    const btnPause = document.getElementById('btn-pause-pipeline');
    const btnStop = document.getElementById('btn-stop-pipeline');

    if (status.state === 'running') {
      if (btnStart) btnStart.disabled = true;
      if (btnPause) {
        btnPause.disabled = false;
        btnPause.querySelector('span').textContent = 'Pause';
      }
      if (btnStop) btnStop.disabled = false;
    } else if (status.state === 'paused') {
      if (btnStart) btnStart.disabled = true;
      if (btnPause) {
        btnPause.disabled = false;
        btnPause.querySelector('span').textContent = 'Resume';
      }
      if (btnStop) btnStop.disabled = false;
    } else {
      if (btnStart) btnStart.disabled = false;
      if (btnPause) {
        btnPause.disabled = true;
        btnPause.querySelector('span').textContent = 'Pause';
      }
      if (btnStop) btnStop.disabled = true;
    }
  }

  addLogLine(entry) {
    const level = (entry.level || 'INFO').toUpperCase();
    const timestamp = entry.timestamp || new Date().toLocaleTimeString();
    const message = entry.message || '';

    // Append to main terminal
    if (this.terminal) {
      const line = document.createElement('div');
      line.className = `fluent-log-line log-${level.toLowerCase()}`;
      line.dataset.level = level.toLowerCase();
      line.innerHTML = `
        <span class="log-time">[${timestamp}]</span>
        <span class="log-badge badge-${level.toLowerCase()}">${level}</span>
        <span class="log-text">${this.escapeHtml(message)}</span>
      `;

      this.terminal.appendChild(line);

      // Enforce max DOM lines
      while (this.terminal.childElementCount > this.maxLogLines) {
        this.terminal.removeChild(this.terminal.firstChild);
      }

      if (this.autoScroll) {
        this.terminal.scrollTop = this.terminal.scrollHeight;
      }
    }

    // Append to mini logs preview on Dashboard
    if (this.miniLogs) {
      const miniLine = document.createElement('div');
      miniLine.className = `log-line log-${level.toLowerCase()}`;
      miniLine.textContent = `[${timestamp}] ${message}`;
      this.miniLogs.appendChild(miniLine);

      while (this.miniLogs.childElementCount > 15) {
        this.miniLogs.removeChild(this.miniLogs.firstChild);
      }
      this.miniLogs.scrollTop = this.miniLogs.scrollHeight;
    }
  }

  setupFilters() {
    const pills = document.querySelectorAll('.filter-pill');
    pills.forEach((pill) => {
      pill.addEventListener('click', () => {
        pills.forEach((p) => p.classList.remove('active'));
        pill.classList.add('active');

        const filter = pill.dataset.filter;
        const lines = this.terminal ? this.terminal.querySelectorAll('.fluent-log-line') : [];

        lines.forEach((line) => {
          if (filter === 'all' || line.dataset.level === filter) {
            line.style.display = 'flex';
          } else {
            line.style.display = 'none';
          }
        });
      });
    });
  }

  clear() {
    if (this.terminal) this.terminal.innerHTML = '';
    if (this.miniLogs) this.miniLogs.innerHTML = '';
    this.logHistory = [];
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Global initialization
document.addEventListener('DOMContentLoaded', () => {
  window.sseClient = new SSEClient();
});
