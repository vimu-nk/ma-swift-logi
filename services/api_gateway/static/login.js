/* ═══════════════════════════════════════════════════════════
   SwiftTrack — Login Page Script
   ═══════════════════════════════════════════════════════════ */

(() => {
  'use strict';

  const { $, $$, login, redirectIfAuthenticated, showToast, getUser } = window.SwiftTrack;

  function init() {
    // If already authenticated, redirect to dashboard
    if (redirectIfAuthenticated()) return;

    // Login form
    $('#login-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const errEl = $('#login-error');
      errEl.classList.remove('visible');

      const username = $('#login-username').value.trim();
      const password = $('#login-password').value;

      if (!username || !password) return;

      const btn = $('#login-btn');
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> Signing in...';

      try {
        await login(username, password);
        const user = getUser();
        window.location.replace('/' + user.role);
      } catch (e) {
        errEl.textContent = e.message;
        errEl.classList.add('visible');
      } finally {
        btn.disabled = false;
        btn.innerHTML = 'Sign In';
      }
    });

    // Demo account chips
    $$('.demo-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        $('#login-username').value = chip.dataset.user;
        $('#login-password').value = chip.dataset.pass;
      });
    });

    // Password visibility toggle
    $('#toggle-password').addEventListener('click', () => {
      const pw = $('#login-password');
      const btn = $('#toggle-password');
      if (pw.type === 'password') {
        pw.type = 'text';
        btn.textContent = '🙈';
        btn.title = 'Hide password';
      } else {
        pw.type = 'password';
        btn.textContent = '👁️';
        btn.title = 'Show password';
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
