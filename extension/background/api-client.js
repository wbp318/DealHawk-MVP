/**
 * DealHawk API Client
 * All backend communication goes through the service worker to avoid CORS issues.
 */

const API_BASE = 'http://localhost:8000/api/v1';

export async function apiGet(path) {
  const resp = await fetch(`${API_BASE}${path}`);
  if (!resp.ok) {
    const error = await resp.text();
    throw new Error(`API error ${resp.status}: ${error}`);
  }
  return resp.json();
}

export async function apiPost(path, body) {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const error = await resp.text();
    throw new Error(`API error ${resp.status}: ${error}`);
  }
  return resp.json();
}

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
