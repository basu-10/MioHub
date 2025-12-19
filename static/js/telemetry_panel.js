/**
 * ═══════════════════════════════════════════════════════════════════
 * TelemetryPanel: Oscilloscope-style diagnostic display
 * Lightweight canvas-based waveform rendering with metric rotation
 * ═══════════════════════════════════════════════════════════════════
 */

(function() {
  'use strict';

  // Precomputed transition sequences (max 10 steps) for smooth state changes
  const IDLE_TO_ACTIVE_STEPS = [
    { amplitude: 5, frequency: 0.035 },
    { amplitude: 6, frequency: 0.042 },
    { amplitude: 7, frequency: 0.049 },
    { amplitude: 8, frequency: 0.056 },
    { amplitude: 9, frequency: 0.062 },
    { amplitude: 10, frequency: 0.067 },
    { amplitude: 11, frequency: 0.071 },
    { amplitude: 12, frequency: 0.074 },
    { amplitude: 13, frequency: 0.077 },
    { amplitude: 15, frequency: 0.08 }
  ];

  const ACTIVE_TO_IDLE_STEPS = IDLE_TO_ACTIVE_STEPS.slice().reverse();

  // Constants for performance and visual tuning
  const CONFIG = {
    // Waveform rendering
    IDLE_AMPLITUDE: 5,          // Low amplitude when idle
    ACTIVE_AMPLITUDE: 15,       // High amplitude during transfers
    IDLE_FREQUENCY: 0.035,       // Slow wave when idle
    ACTIVE_FREQUENCY: 0.08,     // Fast wave during transfers
    IDLE_SPEED: 0.01,           // Phase increment per frame (idle)
    ACTIVE_SPEED: 0.01,         // Phase increment per frame (active)
    WAVEFORM_COLOR: 'rgba(20, 184, 166, 0.8)',
    GRID_COLOR: 'rgba(20, 184, 166, 0.08)',
    
    // Metric rotation
    METRIC_ROTATION_INTERVAL: 10000,  // ms between metric changes
    
    // Activity detection
    ACTIVITY_TIMEOUT: 2000,     // ms to show "Transfer complete" message
    
    // API polling
    POLL_INTERVAL: 600000,      // ms between data fetches (10 minutes)

    // Waveform transitions
    TRANSITION_STEP_DURATION: 80, // ms per precomputed step
    TRANSITIONS: {
      idleToActive: IDLE_TO_ACTIVE_STEPS,
      activeToIdle: ACTIVE_TO_IDLE_STEPS
    }
  };

  class TelemetryPanel {
    constructor() {
      // Canvas elements
      this.miniCanvas = document.getElementById('telemetryCanvas');
      this.modalCanvas = document.getElementById('telemetryModalCanvas');
      this.miniCtx = this.miniCanvas?.getContext('2d');
      this.modalCtx = this.modalCanvas?.getContext('2d');
      
      // DOM elements
      this.miniPanel = document.getElementById('telemetryMiniPanel');
      this.panelContainer = document.getElementById('telemetryPanelContainer');
      this.metricText = document.getElementById('telemetryMetricText');
      this.pulseOverlay = document.getElementById('telemetryPulseOverlay');
      this.notificationsList = document.getElementById('notificationsList');
      this.notificationCount = document.getElementById('notificationCount');
      
      // State
      this.phase = 0;
      this.isActive = false;
      this.modalOpen = false;
      this.currentMetricIndex = 0;
      this.metrics = [];
      this.notifications = [];
      this.latestNotification = null;
      this.animationFrameId = null;
      this.transitionSequence = null;
      this.transitionIndex = 0;
      this.transitionTimer = null;
      this.currentAmplitude = CONFIG.IDLE_AMPLITUDE;
      this.currentFrequency = CONFIG.IDLE_FREQUENCY;
      
      // Prerendered grid (performance optimization)
      this.gridImageMini = null;
      this.gridImageModal = null;
      
      // API + timers
      this.apiUrl = this.panelContainer?.dataset?.telemetryUrl || '/api/telemetry_data';
      this.metricRotationTimer = null;
      this.activityTimer = null;
      this.pollTimer = null;
      
      // Initialize
      this.init();
    }

    init() {
      if (!this.miniCanvas || !this.miniCtx) {
        console.warn('TelemetryPanel: Canvas elements not found');
        return;
      }

      // Prerender grid backgrounds
      this.prerenderGrids();
      
      // Start animation loop
      this.startAnimation();
      
      // Start metric rotation
      this.startMetricRotation();
      
      // Start data polling
      this.startDataPolling();
      
      // Initial data fetch
      this.fetchTelemetryData();
      
      // Expose API for external triggers
      window.TelemetryPanel = {
        setActive: (message) => this.setActive(message),
        setIdle: (message) => this.setIdle(message),
        onModalOpen: () => this.onModalOpen(),
        onModalClose: () => this.onModalClose(),
        updateMetrics: (data) => this.updateMetrics(data),
        showNotification: (message, type) => this.showNotification(message, type)
      };
    }

    /**
     * Prerender grid backgrounds for performance
     */
    prerenderGrids() {
      // Mini canvas grid
      if (this.miniCanvas) {
        const canvas = document.createElement('canvas');
        canvas.width = this.miniCanvas.width;
        canvas.height = this.miniCanvas.height;
        const ctx = canvas.getContext('2d');
        
        ctx.strokeStyle = CONFIG.GRID_COLOR;
        ctx.lineWidth = 0.5;
        
        // Horizontal lines
        for (let y = 0; y < canvas.height; y += 10) {
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(canvas.width, y);
          ctx.stroke();
        }
        
        // Vertical lines
        for (let x = 0; x < canvas.width; x += 10) {
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x, canvas.height);
          ctx.stroke();
        }
        
        this.gridImageMini = canvas;
      }
      
      // Modal canvas grid
      if (this.modalCanvas) {
        const canvas = document.createElement('canvas');
        canvas.width = this.modalCanvas.width;
        canvas.height = this.modalCanvas.height;
        const ctx = canvas.getContext('2d');
        
        ctx.strokeStyle = CONFIG.GRID_COLOR;
        ctx.lineWidth = 0.5;
        
        // Horizontal lines
        for (let y = 0; y < canvas.height; y += 20) {
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(canvas.width, y);
          ctx.stroke();
        }
        
        // Vertical lines
        for (let x = 0; x < canvas.width; x += 20) {
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x, canvas.height);
          ctx.stroke();
        }
        
        this.gridImageModal = canvas;
      }
    }

    /**
     * Main animation loop using requestAnimationFrame
     */
    startAnimation() {
      const animate = () => {
        this.renderWaveform(this.miniCtx, this.miniCanvas, this.gridImageMini);
        
        if (this.modalOpen && this.modalCtx && this.modalCanvas) {
          this.renderWaveform(this.modalCtx, this.modalCanvas, this.gridImageModal);
        }
        
        // Update phase
        const speed = this.isActive ? CONFIG.ACTIVE_SPEED : CONFIG.IDLE_SPEED;
        this.phase += speed;
        
        this.animationFrameId = requestAnimationFrame(animate);
      };
      
      animate();
    }

    /**
     * Render waveform on canvas
     */
    renderWaveform(ctx, canvas, gridImage) {
      if (!ctx || !canvas) return;
      
      const width = canvas.width;
      const height = canvas.height;
      const centerY = height / 2;
      
      // Clear canvas
      ctx.clearRect(0, 0, width, height);
      
      // Draw prerendered grid
      if (gridImage) {
        ctx.drawImage(gridImage, 0, 0);
      }
      
      // Calculate waveform parameters
      const amplitude = this.currentAmplitude ?? (this.isActive ? CONFIG.ACTIVE_AMPLITUDE : CONFIG.IDLE_AMPLITUDE);
      const frequency = this.currentFrequency ?? (this.isActive ? CONFIG.ACTIVE_FREQUENCY : CONFIG.IDLE_FREQUENCY);
      
      // Draw waveform (sine wave with slight noise)
      ctx.beginPath();
      ctx.strokeStyle = CONFIG.WAVEFORM_COLOR;
      ctx.lineWidth = 1.5;
      
      for (let x = 0; x < width; x++) {
        const noise = (Math.random() - 0.5) * 0.5; // Subtle random variation
        const y = centerY + Math.sin((x * frequency) + this.phase) * amplitude + noise;
        
        if (x === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
      
      ctx.stroke();
      
      // Add glow effect when active
      if (this.isActive) {
        ctx.shadowBlur = 8;
        ctx.shadowColor = 'rgba(20, 184, 166, 0.6)';
        ctx.stroke();
        ctx.shadowBlur = 0;
      }
    }

    /**
     * Start metric rotation timer
     */
    startMetricRotation() {
      this.metricRotationTimer = setInterval(() => {
        this.rotateMetric();
      }, CONFIG.METRIC_ROTATION_INTERVAL);
      
      // Show first metric when data arrives
    }

    /**
     * Rotate to next metric
     */
    rotateMetric() {
      if (this.metrics.length === 0) {
        if (!this.isActive && this.metricText) {
          this.metricText.textContent = 'Telemetry unavailable';
        }
        return;
      }
      
      this.currentMetricIndex = (this.currentMetricIndex + 1) % this.metrics.length;
      const metric = this.metrics[this.currentMetricIndex];
      
      if (this.metricText) {
        // Trigger slide animation by removing and re-adding text
        this.metricText.style.animation = 'none';
        setTimeout(() => {
          this.metricText.textContent = metric;
          this.metricText.style.animation = 'telemetryTextSlide 0.5s ease-in-out';
        }, 10);
      }
    }

    /**
     * Start data polling
     */
    startDataPolling() {
      this.pollTimer = setInterval(() => {
        this.fetchTelemetryData();
      }, CONFIG.POLL_INTERVAL);
    }

    /**
     * Fetch telemetry data from server
     */
    async fetchTelemetryData() {
      try {
        const response = await fetch(this.apiUrl, {
          credentials: 'same-origin'
        });
        
        if (!response.ok) {
          console.warn('TelemetryPanel: Failed to fetch data');
          return;
        }
        
        const data = await response.json();
        this.updateMetrics(data);
      } catch (error) {
        console.error('TelemetryPanel: Error fetching data', error);
      }
    }

    /**
     * Update metrics with new data
     */
    updateMetrics(data) {
      // Build rotating metric messages
      this.metrics = [];
      
      if (data.user_type) {
        this.metrics.push(`USER: ${data.user_type.toUpperCase()}`);
      }
      
      if (data.storage_used !== undefined && data.storage_total !== undefined) {
        const usedMB = (data.storage_used / (1024 * 1024)).toFixed(1);
        const totalMB = data.storage_total ? (data.storage_total / (1024 * 1024)).toFixed(0) : '∞';
        this.metrics.push(`STORAGE: ${usedMB}/${totalMB} MB`);
      }
      
      if (data.total_images !== undefined) {
        this.metrics.push(`IMAGES: ${data.total_images}`);
      }
      
      if (data.last_sender) {
        this.metrics.push(`LAST SENDER: ${data.last_sender}`);
      }
      
      if (data.last_transfer_time) {
        const timeAgo = this.formatTimeAgo(data.last_transfer_time);
        this.metrics.push(`LAST XFER: ${timeAgo}`);
      }
      
      // Store notifications
      if (data.notifications && Array.isArray(data.notifications)) {
        this.notifications = data.notifications;
        
        // Track latest notification for mini panel display
        if (this.notifications.length > 0) {
          this.latestNotification = this.notifications[0];
        }
      }
      
      // Reset metric pointer so next rotation shows first item again
      this.currentMetricIndex = -1;
      
      // If we're idle, immediately show the latest metric snapshot
      if (!this.isActive) {
        this.rotateMetric();
      }
      
      // Update modal if open
      if (this.modalOpen) {
        this.updateModalMetrics(data);
        this.renderNotifications();
      }
    }

    /**
     * Update modal metric displays
     */
    updateModalMetrics(data) {
      const setValue = (id, value, className = '') => {
        const el = document.getElementById(id);
        if (el) {
          el.textContent = value;
          el.className = 'telemetry-metric-value ' + className;
        }
      };
      
      setValue('modalUserType', data.user_type?.toUpperCase() || '—');
      
      if (data.storage_used !== undefined) {
        const usedMB = (data.storage_used / (1024 * 1024)).toFixed(1);
        setValue('modalStorageUsed', usedMB + ' MB');
      }
      
      if (data.storage_remaining !== undefined) {
        const remainingMB = data.storage_remaining === null ? '∞' : (data.storage_remaining / (1024 * 1024)).toFixed(1) + ' MB';
        const className = data.storage_remaining !== null && data.storage_remaining < 5 * 1024 * 1024 ? 'warning' : '';
        setValue('modalStorageRemaining', remainingMB, className);
      }
      
      setValue('modalTotalImages', data.total_images?.toString() || '—');
      setValue('modalLastSender', data.last_sender || 'None');
      
      if (data.last_transfer_time) {
        const timeAgo = this.formatTimeAgo(data.last_transfer_time);
        setValue('modalLastTransfer', timeAgo);
      }
      
      const activityText = this.isActive ? 'Transferring...' : 'Idle';
      const activityClass = this.isActive ? 'active' : '';
      setValue('modalCurrentActivity', activityText, activityClass);
    }

    /**
     * Format timestamp as relative time
     */
    formatTimeAgo(timestamp) {
      const now = Date.now();
      const then = new Date(timestamp).getTime();
      const diffMs = now - then;
      
      const seconds = Math.floor(diffMs / 1000);
      const minutes = Math.floor(seconds / 60);
      const hours = Math.floor(minutes / 60);
      const days = Math.floor(hours / 24);
      
      if (days > 0) return `${days}d ago`;
      if (hours > 0) return `${hours}h ago`;
      if (minutes > 0) return `${minutes}m ago`;
      return `${seconds}s ago`;
    }

    /**
     * Render notifications list in modal
     */
    renderNotifications() {
      if (!this.notificationsList) return;
      
      // Update count
      if (this.notificationCount) {
        const count = this.notifications.length;
        this.notificationCount.textContent = `${count} notification${count !== 1 ? 's' : ''}`;
      }
      
      // Clear current content
      this.notificationsList.innerHTML = '';
      
      // If no notifications, show placeholder
      if (this.notifications.length === 0) {
        this.notificationsList.innerHTML = `
          <div class="telemetry-notification-placeholder">
            <i class="material-icons">notifications_none</i>
            <p>No notifications yet</p>
          </div>
        `;
        return;
      }
      
      // Render each notification
      this.notifications.forEach(notification => {
        const item = document.createElement('div');
        item.className = `telemetry-notification-item type-${notification.type}`;
        
        // Choose icon based on type
        let iconName = 'info';
        switch (notification.type) {
          case 'save':
            iconName = 'save';
            break;
          case 'transfer':
            iconName = 'swap_horiz';
            break;
          case 'delete':
            iconName = 'delete';
            break;
          case 'error':
            iconName = 'error';
            break;
          default:
            iconName = 'info';
        }
        
        const timeAgo = this.formatTimeAgo(notification.timestamp);
        
        item.innerHTML = `
          <i class="material-icons telemetry-notification-icon">${iconName}</i>
          <div class="telemetry-notification-content">
            <p class="telemetry-notification-message">${this.escapeHtml(notification.message)}</p>
            <span class="telemetry-notification-timestamp">${timeAgo}</span>
          </div>
        `;
        
        this.notificationsList.appendChild(item);
      });
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }

    /**
     * Set panel to active state (during transfers)
     */
    setActive(message = 'Transferring...') {
      const wasActive = this.isActive;
      this.isActive = true;
      
      // Show pulse overlay
      if (this.pulseOverlay) {
        this.pulseOverlay.classList.remove('hidden');
      }
      
      // Add active class to panel
      if (this.miniPanel) {
        this.miniPanel.classList.add('active');
      }
      
      // Update metric text to show transfer message
      if (this.metricText) {
        this.metricText.textContent = message;
      }
      
      // Clear any existing activity timer
      if (this.activityTimer) {
        clearTimeout(this.activityTimer);
        this.activityTimer = null;
      }

      if (!wasActive) {
        this.startTransition('idleToActive');
      } else {
        this.setWaveformState(CONFIG.ACTIVE_AMPLITUDE, CONFIG.ACTIVE_FREQUENCY);
      }
    }

    /**
     * Set panel to idle state
     */
    setIdle(message = 'Transfer complete') {
      // Show completion/failure message briefly, then return to normal
      if (this.metricText) {
        this.metricText.textContent = message;
      }
      
      // Refresh telemetry data to get latest notifications
      this.fetchTelemetryData();
      
      this.activityTimer = setTimeout(() => {
        const wasActive = this.isActive;
        this.isActive = false;
        
        // Hide pulse overlay
        if (this.pulseOverlay) {
          this.pulseOverlay.classList.add('hidden');
        }
        
        // Remove active class
        if (this.miniPanel) {
          this.miniPanel.classList.remove('active');
        }
        
        // Resume metric rotation
        this.rotateMetric();

                if (wasActive) {
                  this.startTransition('activeToIdle');
                } else {
                  this.setWaveformState(CONFIG.IDLE_AMPLITUDE, CONFIG.IDLE_FREQUENCY);
                }
      }, CONFIG.ACTIVITY_TIMEOUT);
    }

            /**
             * Apply a single transition step and schedule the next
             */
            applyTransitionStep() {
              if (!this.transitionSequence || this.transitionIndex >= this.transitionSequence.length) {
                this.transitionSequence = null;
                this.transitionIndex = 0;
                this.transitionTimer = null;
                return;
              }

              const step = this.transitionSequence[this.transitionIndex];
              this.setWaveformState(step.amplitude, step.frequency);
              this.transitionIndex += 1;

              if (this.transitionIndex < this.transitionSequence.length) {
                this.transitionTimer = setTimeout(() => this.applyTransitionStep(), CONFIG.TRANSITION_STEP_DURATION);
              } else {
                this.transitionSequence = null;
                this.transitionIndex = 0;
                this.transitionTimer = null;
              }
            }

            /**
             * Begin waveform transition using precomputed sequences
             */
            startTransition(sequenceKey) {
              const sequence = CONFIG.TRANSITIONS[sequenceKey];
              if (!sequence) {
                return;
              }

              if (this.transitionTimer) {
                clearTimeout(this.transitionTimer);
                this.transitionTimer = null;
              }

              this.transitionSequence = sequence;
              this.transitionIndex = 0;
              this.applyTransitionStep();
            }

            /**
             * Force waveform to a specific amplitude/frequency
             */
            setWaveformState(amplitude, frequency) {
              this.currentAmplitude = amplitude;
              this.currentFrequency = frequency;
            }

    /**
     * Handle modal open
     */
    onModalOpen() {
      this.modalOpen = true;
      // Fetch fresh data
      this.fetchTelemetryData();
    }

    /**
     * Handle modal close
     */
    onModalClose() {
      this.modalOpen = false;
    }

    /**
     * Show notification in mini panel (called externally)
     */
    showNotification(message, type = 'info') {
      // Add notification via API would go here
      // For now, just display in mini panel
      if (this.metricText) {
        this.metricText.textContent = message;
      }
      
      // Refresh data to get updated notifications list
      setTimeout(() => {
        this.fetchTelemetryData();
      }, 500);
    }

    /**
     * Cleanup on destroy
     */
    destroy() {
      if (this.animationFrameId) {
        cancelAnimationFrame(this.animationFrameId);
      }
      if (this.metricRotationTimer) {
        clearInterval(this.metricRotationTimer);
      }
      if (this.pollTimer) {
        clearInterval(this.pollTimer);
      }
      if (this.activityTimer) {
        clearTimeout(this.activityTimer);
      }
      if (this.transitionTimer) {
        clearTimeout(this.transitionTimer);
      }
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      new TelemetryPanel();
    });
  } else {
    new TelemetryPanel();
  }
})();
