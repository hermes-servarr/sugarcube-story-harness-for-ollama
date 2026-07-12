/* SugarCube Story Harness - Client-side helper script.
 *
 * Supplemental utilities for the single-page UI. The main interaction logic
 * lives inline in templates/index.html; this file provides:
 * - Keyboard shortcut handling (global)
 * - Arc name display normalization
 * - Character sheet field rendering helpers
 */

(function () {
  'use strict';

  // ── Arc name display: convert NN_short_name to Title Case for UI ──────────────
  window.formatArcName = function (arcName) {
    if (!arcName) return '';
    // Strip leading NN_ prefix for display, convert underscores to spaces
    var parts = arcName.replace(/^\d+_/, '').replace(/_/g, ' ').trim();
    // Title Case each word
    return parts.split(' ').map(function (w) {
      return w.charAt(0).toUpperCase() + w.slice(1);
    }).join(' ');
  };

  // ── Format character sheet fields for structured display ─────────────────────
  window.renderCharacterFields = function (data) {
    var fields = [
      { key: 'physical', label: 'Physical Description' },
      { key: 'personality', label: 'Personality Traits' },
      { key: 'motivation', label: 'Motivation' },
      { key: 'backstory', label: 'Backstory' },
      { key: 'relationships', label: 'Key Relationships' },
      { key: 'speech', label: 'Speech Mannerisms' }
    ];
    var html = '';
    fields.forEach(function (f) {
      if (data[f.key] && data[f.key].trim()) {
        html += '<div class="char-field">' +
          '<div class="char-field-label">' + f.label + '</div>' +
          '<div class="char-field-value">' + data[f.key] + '</div>' +
          '</div>';
      }
    });
    return html;
  };

  // ── Keyboard shortcuts ───────────────────────────────────────────────────────
  document.addEventListener('keydown', function (e) {
    // Ctrl+G: focus generate prompt
    if (e.ctrlKey && e.key === 'g') {
      e.preventDefault();
      var el = document.getElementById('gen-prompt');
      if (el) el.focus();
    }
    // Ctrl+Enter: trigger generate
    if (e.ctrlKey && e.key === 'Enter') {
      e.preventDefault();
      var btn = document.getElementById('btn-generate');
      if (btn) btn.click();
    }
    // Esc: close any open modal/overlay
    if (e.key === 'Escape') {
      var overlay = document.getElementById('overlay');
      if (overlay) overlay.style.display = 'none';
    }
  });

  console.log('[harness] app.js loaded');
})();
