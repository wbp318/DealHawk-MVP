/**
 * DealHawk Content Script for CarGurus
 *
 * Extracts listing data from CarGurus search results and detail pages:
 * - VIN, asking price, MSRP, days at dealer, days on CarGurus
 * - Dealer name/location, deal rating, price history
 *
 * Uses MutationObserver to handle React-rendered dynamic content.
 */

(function () {
  'use strict';

  const PROCESSED_ATTR = 'data-dealhawk-processed';
  let listingsFound = 0;
  let listingsScored = 0;

  // Wait for page to settle, then scan
  setTimeout(scanPage, 1500);

  // Watch for dynamic content changes (React re-renders, infinite scroll)
  const observer = new MutationObserver((mutations) => {
    let hasNewNodes = false;
    for (const mutation of mutations) {
      if (mutation.addedNodes.length > 0) {
        hasNewNodes = true;
        break;
      }
    }
    if (hasNewNodes) {
      // Debounce - wait for React to finish rendering
      clearTimeout(window._dealhawkScanTimer);
      window._dealhawkScanTimer = setTimeout(scanPage, 800);
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });

  function scanPage() {
    const url = window.location.href;

    if (url.includes('/listing/') || url.includes('/vdp/')) {
      // Vehicle Detail Page
      scanDetailPage();
    } else {
      // Search Results Page
      scanSearchResults();
    }
  }

  function scanSearchResults() {
    // CarGurus listing cards - try multiple selectors for robustness
    const selectors = [
      '[data-cg-ft="car-blade"]',
      '.pazLTN',           // listing card class (may change)
      'a[href*="/listing/"]',
    ];

    let cards = [];
    for (const sel of selectors) {
      cards = document.querySelectorAll(sel);
      if (cards.length > 0) break;
    }

    if (cards.length === 0) return;

    let newListings = 0;
    cards.forEach((card) => {
      if (card.getAttribute(PROCESSED_ATTR)) return;
      card.setAttribute(PROCESSED_ATTR, 'true');

      const listing = extractFromCard(card);
      if (listing && listing.asking_price) {
        newListings++;
        scoreListing(listing, card);
      }
    });

    if (newListings > 0) {
      listingsFound += newListings;
      notifyServiceWorker();
    }
  }

  function extractFromCard(card) {
    const listing = {};

    // Price - look for the main price element
    const priceEl =
      card.querySelector('[class*="price"]') ||
      card.querySelector('h4') ||
      card.querySelector('span[class*="Price"]');
    if (priceEl) {
      listing.asking_price = parsePrice(priceEl.textContent);
    }

    // Link to detail page
    const link = card.tagName === 'A' ? card : card.querySelector('a[href*="/listing/"]');
    if (link) {
      listing.url = link.href;
    }

    // Title / Year Make Model
    const titleEl =
      card.querySelector('h4[class*="title"]') ||
      card.querySelector('[data-cg-ft="car-blade-title"]') ||
      card.querySelector('h4');
    if (titleEl) {
      const parsed = parseTitle(titleEl.textContent);
      Object.assign(listing, parsed);
    }

    // Deal rating badge from CarGurus
    const dealBadge =
      card.querySelector('[class*="dealBadge"]') ||
      card.querySelector('[class*="deal-rating"]') ||
      card.querySelector('[data-cg-ft="deal-badge"]');
    if (dealBadge) {
      listing.platform_deal_rating = dealBadge.textContent.trim();
    }

    // Days on CarGurus / Days at dealer
    const allText = card.textContent;
    const daysMatch = allText.match(/(\d+)\s*days?\s*(on\s*CarGurus|at\s*this\s*dealer)/i);
    if (daysMatch) {
      const days = parseInt(daysMatch[1]);
      if (daysMatch[2].toLowerCase().includes('cargurus')) {
        listing.days_on_platform = days;
      } else {
        listing.days_on_lot = days;
      }
    }

    // Mileage
    const mileageMatch = allText.match(/([\d,]+)\s*mi/i);
    if (mileageMatch) {
      listing.mileage = parseInt(mileageMatch[1].replace(/,/g, ''));
    }

    // Dealer name
    const dealerEl = card.querySelector('[class*="dealer"]');
    if (dealerEl) {
      listing.dealer_name = dealerEl.textContent.trim();
    }

    listing.platform = 'cargurus';
    return listing;
  }

  function scanDetailPage() {
    if (document.body.getAttribute(PROCESSED_ATTR)) return;
    document.body.setAttribute(PROCESSED_ATTR, 'detail');

    const listing = extractFromDetailPage();
    if (listing && listing.asking_price) {
      listingsFound = 1;
      scoreAndShowDetail(listing);
    }
  }

  function extractFromDetailPage() {
    const listing = { platform: 'cargurus' };
    const pageText = document.body.textContent;

    // VIN
    const vinMatch = pageText.match(/VIN[:\s]*([A-HJ-NPR-Z0-9]{17})/i);
    if (vinMatch) {
      listing.vin = vinMatch[1];
    }

    // Price
    const priceEl =
      document.querySelector('[class*="price"][class*="listing"]') ||
      document.querySelector('[data-cg-ft="price"]') ||
      document.querySelector('span[class*="Price"]');
    if (priceEl) {
      listing.asking_price = parsePrice(priceEl.textContent);
    }

    // MSRP / Original Price
    const msrpMatch = pageText.match(/MSRP[:\s]*\$?([\d,]+)/i);
    if (msrpMatch) {
      listing.msrp = parseFloat(msrpMatch[1].replace(/,/g, ''));
    }

    // Title
    const titleEl = document.querySelector('h1[class*="title"]') || document.querySelector('h1');
    if (titleEl) {
      const parsed = parseTitle(titleEl.textContent);
      Object.assign(listing, parsed);
    }

    // Days on lot / CarGurus
    const daysAtDealer = pageText.match(/(\d+)\s*days?\s*at\s*this\s*dealer/i);
    const daysOnCG = pageText.match(/(\d+)\s*days?\s*on\s*CarGurus/i);
    if (daysAtDealer) listing.days_on_lot = parseInt(daysAtDealer[1]);
    if (daysOnCG) listing.days_on_platform = parseInt(daysOnCG[1]);

    // Dealer info
    const dealerEl = document.querySelector('[class*="dealerName"]');
    if (dealerEl) listing.dealer_name = dealerEl.textContent.trim();

    const locationEl = document.querySelector('[class*="dealerAddress"]');
    if (locationEl) listing.dealer_location = locationEl.textContent.trim();

    // Deal rating
    const dealBadge = document.querySelector('[class*="dealBadge"]') ||
                      document.querySelector('[data-cg-ft="deal-badge"]');
    if (dealBadge) listing.platform_deal_rating = dealBadge.textContent.trim();

    // Price history
    listing.price_history = extractPriceHistory();

    return listing;
  }

  function extractPriceHistory() {
    const history = [];
    // CarGurus shows price changes in a timeline/chart
    const historyItems = document.querySelectorAll('[class*="priceHistory"] li, [class*="price-drop"] div');
    historyItems.forEach((item) => {
      const text = item.textContent;
      const match = text.match(/\$?([\d,]+).*?(\d{1,2}\/\d{1,2}\/\d{2,4})/);
      if (match) {
        history.push({
          price: parseFloat(match[1].replace(/,/g, '')),
          date: match[2],
        });
      }
    });
    return history;
  }

  async function scoreListing(listing, cardElement) {
    // Use the best available days figure
    const daysOnLot = listing.days_on_lot || listing.days_on_platform || 0;

    // We need at minimum price and some vehicle identification
    if (!listing.asking_price) return;

    const scoreData = {
      asking_price: listing.asking_price,
      msrp: listing.msrp || listing.asking_price * 1.05, // Rough estimate if no MSRP
      make: listing.make || 'Unknown',
      model: listing.model || 'Unknown',
      year: listing.year || new Date().getFullYear(),
      days_on_lot: daysOnLot,
    };

    try {
      const result = await chrome.runtime.sendMessage({
        action: 'SCORE_LISTING',
        data: scoreData,
      });

      if (result && !result.error) {
        listingsScored++;
        // Inject the score badge onto the card
        if (typeof window.injectScoreBadge === 'function') {
          window.injectScoreBadge(cardElement, result, listing);
        }
        notifyServiceWorker();
      }
    } catch (err) {
      console.debug('DealHawk: Score request failed:', err.message);
    }
  }

  async function scoreAndShowDetail(listing) {
    const daysOnLot = listing.days_on_lot || listing.days_on_platform || 0;

    const scoreData = {
      vin: listing.vin,
      asking_price: listing.asking_price,
      msrp: listing.msrp || listing.asking_price * 1.05,
      make: listing.make || 'Unknown',
      model: listing.model || 'Unknown',
      year: listing.year || new Date().getFullYear(),
      days_on_lot: daysOnLot,
    };

    try {
      const result = await chrome.runtime.sendMessage({
        action: 'SCORE_LISTING',
        data: scoreData,
      });

      if (result && !result.error) {
        listingsScored = 1;
        // Store for side panel to pick up
        await chrome.storage.local.set({
          currentListing: { ...listing, scoreResult: result },
        });

        // Open side panel
        chrome.runtime.sendMessage({ action: 'OPEN_SIDE_PANEL' });
      }
    } catch (err) {
      console.debug('DealHawk: Detail score failed:', err.message);
    }

    notifyServiceWorker();
  }

  function notifyServiceWorker() {
    chrome.runtime.sendMessage({
      action: 'LISTINGS_DETECTED',
      data: { count: listingsFound, scored: listingsScored },
    });
  }

  // --- Utility functions ---

  function parsePrice(text) {
    if (!text) return null;
    const match = text.match(/\$?([\d,]+)/);
    if (match) {
      return parseFloat(match[1].replace(/,/g, ''));
    }
    return null;
  }

  function parseTitle(text) {
    if (!text) return {};
    text = text.trim();

    // Pattern: "2025 Ford F-150 XLT SuperCrew 4WD" or "2024 Ram 2500 Laramie"
    const match = text.match(/(\d{4})\s+(\w+)\s+(.+)/);
    if (match) {
      const year = parseInt(match[1]);
      const make = match[2];
      const rest = match[3].trim();

      // Try to split model from trim
      // Common models: F-150, F-250, Ram 1500, Sierra 1500, Silverado 1500, etc.
      const modelMatch = rest.match(
        /^(F-\d{3}|F \d{3}|Ram \d{4}|Sierra \d{4}(?:HD)?|Silverado \d{4}(?:HD)?|Tundra|Tacoma|Ranger|Frontier|Titan|Colorado|Canyon)/i
      );

      let model, trim;
      if (modelMatch) {
        model = modelMatch[1];
        trim = rest.slice(model.length).trim() || null;
      } else {
        // First word is model
        const parts = rest.split(/\s+/);
        model = parts[0];
        trim = parts.slice(1).join(' ') || null;
      }

      return { year, make, model, trim };
    }
    return {};
  }
})();
