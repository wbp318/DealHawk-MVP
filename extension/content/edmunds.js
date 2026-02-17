/**
 * DealHawk Content Script for Edmunds
 *
 * Extracts listing data from Edmunds search results and detail pages.
 * Edmunds is a full React SPA — needs URL change detection via popstate
 * and polling for React Router navigation.
 * Uses MutationObserver to handle dynamically loaded content.
 */

(function () {
  'use strict';

  const PROCESSED_ATTR = 'data-dealhawk-processed';
  let listingsFound = 0;
  let listingsScored = 0;
  let lastUrl = window.location.href;

  // Wait for page to settle, then scan
  setTimeout(scanPage, 1500);

  // Watch for dynamic content changes (React re-renders)
  const observer = new MutationObserver((mutations) => {
    let hasNewNodes = false;
    for (const mutation of mutations) {
      if (mutation.addedNodes.length > 0) {
        hasNewNodes = true;
        break;
      }
    }
    if (hasNewNodes) {
      clearTimeout(window._dealhawkScanTimer);
      window._dealhawkScanTimer = setTimeout(scanPage, 800);
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });

  // Edmunds uses React Router — detect URL changes via popstate + polling
  window.addEventListener('popstate', () => {
    handleUrlChange();
  });

  // Poll for URL changes (React Router pushState doesn't fire popstate)
  const urlPollInterval = setInterval(() => {
    if (window.location.href !== lastUrl) {
      handleUrlChange();
    }
  }, 1000);

  // Clean up on page unload
  window.addEventListener('unload', () => {
    clearInterval(urlPollInterval);
    clearTimeout(window._dealhawkScanTimer);
    observer.disconnect();
  });

  function handleUrlChange() {
    lastUrl = window.location.href;
    // Reset detail page processing flag when navigating
    document.body.removeAttribute(PROCESSED_ATTR);
    clearTimeout(window._dealhawkScanTimer);
    window._dealhawkScanTimer = setTimeout(scanPage, 1500);
  }

  function scanPage() {
    const url = window.location.href;

    if (url.includes('/vin/') || url.match(/\/[a-z-]+\/\d{4}\/[a-z-]+\/vin\//i)) {
      scanDetailPage();
    } else if (url.includes('/inventory/')) {
      scanSearchResults();
    } else {
      scanSearchResults();
    }
  }

  function scanSearchResults() {
    const selectors = [
      '[data-tracking-type="listing-card"]',
      '.usurp-inventory-card',
      '[class*="inventory-card"]',
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

    // Price
    const priceEl =
      card.querySelector('.heading-3.usurp-inventory-card-price') ||
      card.querySelector('[class*="inventory-card-price"]') ||
      card.querySelector('[class*="price"]');
    if (priceEl) {
      listing.asking_price = parsePrice(priceEl.textContent);
    }

    // Link to detail page
    const link =
      card.querySelector('.usurp-inventory-card-vdp-url') ||
      card.querySelector('a[href*="/vin/"]') ||
      card.querySelector('a[href*="/inventory/"]');
    if (link) {
      listing.url = link.href;
    }

    // Title / Year Make Model
    const titleEl =
      card.querySelector('.usurp-inventory-card-vdp-url') ||
      card.querySelector('h2') ||
      card.querySelector('[class*="card-title"]');
    if (titleEl) {
      const parsed = parseTitle(titleEl.textContent);
      Object.assign(listing, parsed);
    }

    // Dealer name
    const dealerEl =
      card.querySelector('.dealer-name') ||
      card.querySelector('[class*="dealer"]');
    if (dealerEl) {
      listing.dealer_name = dealerEl.textContent.trim();
    }

    // Mileage
    const allText = card.textContent;
    const mileageMatch = allText.match(/([\d,]+)\s*mi/i);
    if (mileageMatch) {
      listing.mileage = parseInt(mileageMatch[1].replace(/,/g, ''));
    }

    listing.days_on_lot = 0;
    listing.platform = 'edmunds';
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
    const listing = { platform: 'edmunds' };
    const pageText = document.body.textContent;

    // VIN - check URL first (Edmunds often has VIN in URL)
    const urlVinMatch = window.location.href.match(/\/vin\/([A-HJ-NPR-Z0-9]{17})/i);
    if (urlVinMatch) {
      listing.vin = urlVinMatch[1].toUpperCase();
    }
    if (!listing.vin) {
      const vinMatch = pageText.match(/VIN[:\s]*([A-HJ-NPR-Z0-9]{17})/i);
      if (vinMatch) listing.vin = vinMatch[1].toUpperCase();
    }

    // Price
    const priceEl =
      document.querySelector('[class*="price"][class*="primary"]') ||
      document.querySelector('.heading-2[class*="price"]') ||
      document.querySelector('[class*="vdp-price"]');
    if (priceEl) {
      listing.asking_price = parsePrice(priceEl.textContent);
    }

    // MSRP
    const msrpMatch = pageText.match(/MSRP[:\s]*\$?([\d,]+)/i);
    if (msrpMatch) {
      listing.msrp = parseFloat(msrpMatch[1].replace(/,/g, ''));
    }

    // Title
    const titleEl = document.querySelector('h1');
    if (titleEl) {
      const parsed = parseTitle(titleEl.textContent);
      Object.assign(listing, parsed);
    }

    // Dealer info
    const dealerEl =
      document.querySelector('.dealer-name') ||
      document.querySelector('[class*="dealer-name"]');
    if (dealerEl) listing.dealer_name = dealerEl.textContent.trim();

    listing.days_on_lot = 0;
    return listing;
  }

  async function scoreListing(listing, cardElement) {
    const daysOnLot = listing.days_on_lot || 0;
    if (!listing.asking_price) return;

    const scoreData = {
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
        listingsScored++;
        if (typeof window.injectScoreBadge === 'function') {
          window.injectScoreBadge(cardElement, result, listing, { top: '8px', left: '8px' });
        }
        notifyServiceWorker();
      }
    } catch (err) {
      console.debug('DealHawk: Score request failed:', err.message);
    }
  }

  async function scoreAndShowDetail(listing) {
    const scoreData = {
      vin: listing.vin,
      asking_price: listing.asking_price,
      msrp: listing.msrp || listing.asking_price * 1.05,
      make: listing.make || 'Unknown',
      model: listing.model || 'Unknown',
      year: listing.year || new Date().getFullYear(),
      days_on_lot: listing.days_on_lot || 0,
    };

    try {
      const result = await chrome.runtime.sendMessage({
        action: 'SCORE_LISTING',
        data: scoreData,
      });

      if (result && !result.error) {
        listingsScored = 1;
        await chrome.storage.local.set({
          currentListing: { ...listing, scoreResult: result },
        });
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

    const match = text.match(/(\d{4})\s+(\w+)\s+(.+)/);
    if (match) {
      const year = parseInt(match[1]);
      const make = match[2];
      const rest = match[3].trim();

      const modelMatch = rest.match(
        /^(F-\d{3}|F \d{3}|Ram \d{4}|Sierra \d{4}(?:HD)?|Silverado \d{4}(?:HD)?|Tundra|Tacoma|Ranger|Frontier|Titan|Colorado|Canyon)/i
      );

      let model, trim;
      if (modelMatch) {
        model = modelMatch[1];
        trim = rest.slice(model.length).trim() || null;
      } else {
        const parts = rest.split(/\s+/);
        model = parts[0];
        trim = parts.slice(1).join(' ') || null;
      }

      return { year, make, model, trim };
    }
    return {};
  }
})();
