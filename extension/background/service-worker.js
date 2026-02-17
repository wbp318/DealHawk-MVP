/**
 * DealHawk Service Worker
 * Routes messages between content scripts, popup, and side panel.
 * All API calls are proxied through here.
 */

import {
  decodeVin,
  scoreListing,
  getNegotiationBrief,
  getPricing,
  getIncentives,
  healthCheck,
  calculateSection179,
  getMarketTrends,
  getMarketStats,
  apiLogin,
  apiRegister,
  apiLogout,
  apiGetMe,
  apiRefreshToken,
  getSavedVehicles,
  saveVehicle,
  deleteSavedVehicle,
  updateSavedVehicle,
  getAlerts,
  createAlert,
  deleteAlert,
  updateAlert,
  checkAlerts,
  getSubscriptionStatus,
  createCheckout,
  createPortalSession,
} from './api-client.js';

// Cache TTL: 1 hour
const CACHE_TTL = 60 * 60 * 1000;

// Open side panel when extension icon is clicked (if on a supported site)
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false });

// Message handler - routes all inter-component communication
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message, sender).then(sendResponse).catch((err) => {
    sendResponse({ error: err.message });
  });
  return true; // Keep the message channel open for async response
});

async function handleMessage(message, sender) {
  const { action, data } = message;

  switch (action) {
    // --- Existing actions ---
    case 'DECODE_VIN':
      return handleWithCache(`vin:${data.vin}`, () => decodeVin(data.vin));

    case 'SCORE_LISTING':
      return scoreListing(data);

    case 'GET_NEGOTIATION':
      return getNegotiationBrief(data);

    case 'GET_PRICING':
      return handleWithCache(
        `pricing:${data.year}:${data.make}:${data.model}:${data.msrp}`,
        () => getPricing(data.year, data.make, data.model, data.msrp)
      );

    case 'GET_INCENTIVES':
      return handleWithCache(
        `incentives:${data.make}:${data.model || ''}`,
        () => getIncentives(data.make, data.model)
      );

    case 'HEALTH_CHECK':
      return healthCheck();

    // --- Section 179 + Market Data ---
    case 'CALCULATE_SECTION_179':
      return calculateSection179(data);

    case 'GET_MARKET_TRENDS':
      return handleWithCache(
        `market-trends:${data.make}:${data.model}`,
        () => getMarketTrends(data.make, data.model)
      );

    case 'GET_MARKET_STATS':
      return handleWithCache(
        `market-stats:${data.make}:${data.model}`,
        () => getMarketStats(data.make, data.model)
      );

    case 'OPEN_SIDE_PANEL':
      if (sender.tab) {
        await chrome.sidePanel.open({ tabId: sender.tab.id });
      }
      return { success: true };

    case 'LISTINGS_DETECTED':
      // Content script found listings - store count for popup
      await chrome.storage.local.set({
        [`listings:${sender.tab.id}`]: {
          count: data.count,
          scored: data.scored || 0,
          url: sender.tab.url,
          timestamp: Date.now(),
        },
      });
      return { success: true };

    case 'GET_LISTING_STATUS': {
      const tabId = data.tabId;
      const result = await chrome.storage.local.get(`listings:${tabId}`);
      return result[`listings:${tabId}`] || null;
    }

    // --- Auth actions ---
    case 'AUTH_LOGIN':
      return apiLogin(data.email, data.password);

    case 'AUTH_REGISTER':
      return apiRegister(data.email, data.password, data.display_name);

    case 'AUTH_LOGOUT':
      return apiLogout();

    case 'AUTH_GET_ME':
      return apiGetMe();

    case 'AUTH_REFRESH':
      return apiRefreshToken(data.refresh_token);

    // --- Saved Vehicles ---
    case 'SAVE_VEHICLE':
      return saveVehicle(data);

    case 'GET_SAVED_VEHICLES':
      return getSavedVehicles();

    case 'DELETE_SAVED_VEHICLE':
      return deleteSavedVehicle(data.id);

    case 'UPDATE_SAVED_VEHICLE':
      return updateSavedVehicle(data.id, data.updates);

    // --- Deal Alerts ---
    case 'GET_ALERTS':
      return getAlerts();

    case 'CREATE_ALERT':
      return createAlert(data);

    case 'DELETE_ALERT':
      return deleteAlert(data.id);

    case 'UPDATE_ALERT':
      return updateAlert(data.id, data.updates);

    case 'CHECK_ALERTS':
      return checkAlerts(data);

    // --- Subscription ---
    case 'GET_SUBSCRIPTION_STATUS':
      return getSubscriptionStatus();

    case 'CREATE_CHECKOUT':
      return createCheckout();

    case 'CREATE_PORTAL_SESSION':
      return createPortalSession();

    default:
      return { error: `Unknown action: ${action}` };
  }
}

async function handleWithCache(key, fetchFn) {
  // Check cache
  const cached = await chrome.storage.local.get(key);
  if (cached[key] && Date.now() - cached[key]._cachedAt < CACHE_TTL) {
    return cached[key].data;
  }

  // Fetch fresh data
  const data = await fetchFn();

  // Cache it
  await chrome.storage.local.set({
    [key]: { data, _cachedAt: Date.now() },
  });

  return data;
}
