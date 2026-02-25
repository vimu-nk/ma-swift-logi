/* ═══════════════════════════════════════════════════════════
   SwiftTrack — Auth Module (ES Module)
   Session management, route guards, and logout.

   Usage:
     import { getCurrentUser, requireAuth, logout } from '/static/auth.js';
   ═══════════════════════════════════════════════════════════ */

const TOKEN_KEY = 'swifttrack_token';
const USER_KEY  = 'swifttrack_user';

/** Map a role to its default dashboard path. */
const ROLE_DASHBOARDS = {
  client: '/client',
  driver: '/driver',
  admin:  '/admin',
};

// ── Public Functions ────────────────────────────────────

/**
 * Retrieve the current user from localStorage.
 *
 * @returns {{ username: string, role: string, name: string } | null}
 */
export function getCurrentUser() {
  const token = localStorage.getItem(TOKEN_KEY);
  const raw   = localStorage.getItem(USER_KEY);

  if (!token || !raw) return null;

  try {
    return JSON.parse(raw);
  } catch {
    // Corrupted data — treat as logged-out
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    return null;
  }
}

/**
 * Auth + role guard.
 *
 * Call at the top of every protected page script:
 *   if (!requireAuth('client')) throw new Error('unauthorized');
 *
 * Behaviour:
 *   • No session   → redirect to /login, returns false.
 *   • Wrong role   → redirect to the user's own dashboard, returns false.
 *   • Authorised   → returns true (page may continue loading).
 *
 * @param {string} [role] — required role, e.g. 'client', 'driver', 'admin'.
 *                          If omitted, only checks that the user is logged in.
 * @returns {boolean}
 */
export function requireAuth(role) {
  const user = getCurrentUser();

  // ── Not logged in ─────────────────────────────────
  if (!user) {
    window.location.replace('/login');
    return false;
  }

  // ── Role mismatch ─────────────────────────────────
  if (role && user.role !== role) {
    const target = ROLE_DASHBOARDS[user.role] || '/login';
    window.location.replace(target);
    return false;
  }

  return true;
}

/**
 * Clear stored session and redirect to /login.
 */
export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.location.replace('/login');
}

/**
 * Check whether a session exists (without parsing the user).
 * Useful for the login page to skip rendering if already authenticated.
 *
 * @returns {boolean}
 */
export function isAuthenticated() {
  return !!(localStorage.getItem(TOKEN_KEY) && localStorage.getItem(USER_KEY));
}

/**
 * Get the dashboard path for the current user's role.
 * Returns '/login' if no session exists.
 *
 * @returns {string}
 */
export function getUserDashboard() {
  const user = getCurrentUser();
  if (!user) return '/login';
  return ROLE_DASHBOARDS[user.role] || '/login';
}
