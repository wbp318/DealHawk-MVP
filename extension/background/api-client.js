/**
 * DealHawk API Client
 * All backend communication goes through the service worker to avoid CORS issues.
 * Supports JWT auth with auto-refresh on 401.
 */

// Backend URL — set to localhost for local dev, Render URL for production
const API_HOST = 'https://dealhawk-api.onrender.com';
// const API_HOST = 'http://localhost:8000';  // Uncomment for local dev

const API_BASE = API_HOST + '/api/v1';

// --- Token management ---

async function _getTokens() {
  const result = await chrome.storage.local.get('authTokens');
  return result.authTokens || null;
}

async function _storeTokens(tokens) {
  await chrome.storage.local.set({ authTokens: tokens });
}

async function _clearTokens() {
  await chrome.storage.local.remove('authTokens');
}

async function _getAccessToken() {
  const tokens = await _getTokens();
  return tokens ? tokens.access_token : null;
}

async function _buildHeaders(extraHeaders = {}) {
  const headers = { 'Content-Type': 'application/json', ...extraHeaders };
  const token = await _getAccessToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

let _refreshInProgress = false;

async function _handleAuthRetry(resp, retryFn) {
  if (resp.status === 401 && !_refreshInProgress) {
    const tokens = await _getTokens();
    if (tokens && tokens.refresh_token) {
      _refreshInProgress = true;
      try {
        const newTokens = await apiRefreshToken(tokens.refresh_token);
        await _storeTokens(newTokens);
        // retryFn runs while flag is still true, preventing re-entry
        const result = await retryFn();
        _refreshInProgress = false;
        return result;
      } catch {
        _refreshInProgress = false;
        await _clearTokens();
      }
    }
  }
  return null;
}

// --- Core HTTP methods ---

export async function apiGet(path) {
  const headers = await _buildHeaders();
  const resp = await fetch(`${API_BASE}${path}`, { headers });

  if (!resp.ok) {
    const retry = await _handleAuthRetry(resp, () => apiGet(path));
    if (retry) return retry;
    const error = await resp.text();
    throw new Error(`API error ${resp.status}: ${error}`);
  }
  return resp.json();
}

export async function apiPost(path, body) {
  const headers = await _buildHeaders();
  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const retry = await _handleAuthRetry(resp, () => apiPost(path, body));
    if (retry) return retry;
    const error = await resp.text();
    throw new Error(`API error ${resp.status}: ${error}`);
  }
  return resp.json();
}

export async function apiPatch(path, body) {
  const headers = await _buildHeaders();
  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const retry = await _handleAuthRetry(resp, () => apiPatch(path, body));
    if (retry) return retry;
    const error = await resp.text();
    throw new Error(`API error ${resp.status}: ${error}`);
  }
  return resp.json();
}

export async function apiDelete(path) {
  const headers = await _buildHeaders();
  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers,
  });

  if (!resp.ok) {
    const retry = await _handleAuthRetry(resp, () => apiDelete(path));
    if (retry) return retry;
    const error = await resp.text();
    throw new Error(`API error ${resp.status}: ${error}`);
  }
  return resp.json();
}

// --- Existing endpoints (unchanged) ---

export async function decodeVin(vin) {
  return apiGet(`/vin/${encodeURIComponent(vin)}`);
}

export async function scoreListing(listingData) {
  return apiPost('/score', listingData);
}

export async function getNegotiationBrief(data) {
  return apiPost('/negotiate', data);
}

export async function getPricing(year, make, model, msrp) {
  return apiGet(`/pricing/${encodeURIComponent(year)}/${encodeURIComponent(make)}/${encodeURIComponent(model)}?msrp=${encodeURIComponent(msrp)}`);
}

export async function getIncentives(make, model = null) {
  let path = `/incentives/${encodeURIComponent(make)}`;
  if (model) path += `?model=${encodeURIComponent(model)}`;
  return apiGet(path);
}

export async function healthCheck() {
  return apiGet('/health');
}

// --- Section 179 ---

export async function calculateSection179(data) {
  return apiPost('/section-179/calculate', data);
}

// --- Market data ---

export async function getMarketTrends(make, model) {
  return apiGet(`/market/trends/${encodeURIComponent(make)}/${encodeURIComponent(model)}`);
}

export async function getMarketStats(make, model) {
  return apiGet(`/market/stats/${encodeURIComponent(make)}/${encodeURIComponent(model)}`);
}

// --- Auth endpoints ---

export async function apiLogin(email, password) {
  const resp = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!resp.ok) {
    const error = await resp.text();
    throw new Error(`Login failed: ${error}`);
  }
  const tokens = await resp.json();
  await _storeTokens(tokens);
  return tokens;
}

export async function apiRegister(email, password, displayName = null) {
  const body = { email, password };
  if (displayName) body.display_name = displayName;

  const resp = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const error = await resp.text();
    throw new Error(`Registration failed: ${error}`);
  }
  const tokens = await resp.json();
  await _storeTokens(tokens);
  return tokens;
}

export async function apiRefreshToken(refreshToken) {
  const resp = await fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!resp.ok) {
    throw new Error('Token refresh failed');
  }
  return resp.json();
}

export async function apiGetMe() {
  return apiGet('/auth/me');
}

export async function apiLogout() {
  await _clearTokens();
  return { success: true };
}

// --- Saved Vehicles ---

export async function getSavedVehicles() {
  return apiGet('/saved/');
}

export async function saveVehicle(vehicleData) {
  return apiPost('/saved/', vehicleData);
}

export async function deleteSavedVehicle(id) {
  return apiDelete(`/saved/${encodeURIComponent(id)}`);
}

export async function updateSavedVehicle(id, updates) {
  return apiPatch(`/saved/${encodeURIComponent(id)}`, updates);
}

// --- Deal Alerts ---

export async function getAlerts() {
  return apiGet('/alerts/');
}

export async function createAlert(alertData) {
  return apiPost('/alerts/', alertData);
}

export async function deleteAlert(id) {
  return apiDelete(`/alerts/${encodeURIComponent(id)}`);
}

export async function updateAlert(id, updates) {
  return apiPatch(`/alerts/${encodeURIComponent(id)}`, updates);
}

export async function checkAlerts(listingData) {
  return apiPost('/alerts/check', listingData);
}

// --- Subscription ---

const SUB_BASE = API_HOST;

export async function getSubscriptionStatus() {
  const headers = await _buildHeaders();
  const resp = await fetch(`${SUB_BASE}/subscription/status`, { headers });
  if (!resp.ok) {
    const error = await resp.text();
    throw new Error(`Status check failed: ${error}`);
  }
  return resp.json();
}

export async function createCheckout() {
  const headers = await _buildHeaders();
  const resp = await fetch(`${SUB_BASE}/subscription/checkout`, {
    method: 'POST',
    headers,
  });
  if (!resp.ok) {
    const error = await resp.text();
    throw new Error(`Checkout failed: ${error}`);
  }
  return resp.json();
}

export async function createPortalSession() {
  const headers = await _buildHeaders();
  const resp = await fetch(`${SUB_BASE}/subscription/portal`, {
    method: 'POST',
    headers,
  });
  if (!resp.ok) {
    const error = await resp.text();
    throw new Error(`Portal failed: ${error}`);
  }
  return resp.json();
}
