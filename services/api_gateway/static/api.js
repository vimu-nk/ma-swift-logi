/* ═══════════════════════════════════════════════════════════
   SwiftTrack — API Module (ES Module)
   Centralised fetch wrapper with JWT injection and 401 handling.

   Usage:
     import { login, getOrders, createOrder, updateOrderStatus } from '/static/api.js';
   ═══════════════════════════════════════════════════════════ */

const API_BASE = '';
const TOKEN_KEY = 'swifttrack_token';
const USER_KEY = 'swifttrack_user';

// ── Core Fetch Wrapper ──────────────────────────────────

/**
 * Generic fetch helper.
 * • Automatically injects the JWT Bearer token from localStorage.
 * • On 401, clears the stored session and redirects to /login.
 */
async function request(method, path, body = null) {
  const headers = { 'Content-Type': 'application/json' };

  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const opts = { method, headers };
  if (body !== null) {
    opts.body = JSON.stringify(body);
  }

  const res = await fetch(`${API_BASE}${path}`, opts);

  // ── 401 → session expired / invalid ───────────────
  if (res.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    window.location.replace('/login');
    // Throw so callers don't continue processing
    throw new Error('Session expired — redirecting to login.');
  }

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || `API error: ${res.status}`);
  }

  return data;
}

// ── Public API Functions ────────────────────────────────

/**
 * Authenticate and store session.
 * Saves the JWT token and user profile to localStorage.
 *
 * @param {string} username
 * @param {string} password
 * @returns {Promise<{access_token: string, username: string, role: string, name: string}>}
 */
export async function login(username, password) {
  const data = await request('POST', '/api/auth/login', { username, password });

  // Persist session
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify({
    username: data.username,
    role: data.role,
    name: data.name,
  }));

  return data;
}

/**
 * Fetch orders with optional filters.
 *
 * @param {Object}  [opts]
 * @param {string}  [opts.status]  — filter by order status
 * @param {number}  [opts.limit]   — max results (default 100)
 * @returns {Promise<{orders: Array}>}
 */
export async function getOrders({ status = '', limit = 100 } = {}) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  params.set('limit', String(limit));

  return request('GET', `/api/orders?${params}`);
}

/**
 * Create a new delivery order.
 *
 * @param {Object} data
 * @param {string} data.pickup_address
 * @param {string} data.delivery_address
 * @param {Object} [data.package_details]
 * @returns {Promise<Object>} created order
 */
export async function createOrder(data) {
  return request('POST', '/api/orders', data);
}

/**
 * Update the status of an existing order.
 *
 * @param {string} orderId
 * @param {string} status  — e.g. 'IN_TRANSIT', 'DELIVERED', 'FAILED'
 * @returns {Promise<Object>} updated order
 */
export async function updateOrderStatus(orderId, status) {
  return request('PATCH', `/api/orders/${orderId}/status`, { status });
}

/**
 * Fetch a single order by ID.
 *
 * @param {string} orderId
 * @returns {Promise<Object>}
 */
export async function getOrder(orderId) {
  return request('GET', `/api/orders/${orderId}`);
}

/**
 * Clear stored session and redirect to login.
 */
export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.location.replace('/login');
}

/**
 * Get the current user from localStorage, or null.
 * @returns {{ username: string, role: string, name: string } | null}
 */
export function getUser() {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

/**
 * Get the stored JWT token, or null.
 * @returns {string | null}
 */
export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
