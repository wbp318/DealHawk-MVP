/**
 * DealHawk Overlay - Injects score badges onto listing cards.
 *
 * Badges are circular, color-coded (green/yellow/red), and clickable
 * to open the side panel with full analysis.
 */

(function () {
  'use strict';

  /**
   * Inject a score badge onto a listing card element.
   * Called by cargurus.js after scoring a listing.
   */
  window.injectScoreBadge = function (cardElement, scoreResult, listing) {
    if (!cardElement || !scoreResult) return;

    // Don't double-inject
    if (cardElement.querySelector('.dealhawk-badge')) return;

    const score = scoreResult.score;
    const grade = scoreResult.grade;

    // Create badge
    const badge = document.createElement('div');
    badge.className = 'dealhawk-badge';
    badge.setAttribute('data-score', score);

    // Color based on score
    if (score >= 80) {
      badge.classList.add('dealhawk-badge--great');
    } else if (score >= 50) {
      badge.classList.add('dealhawk-badge--good');
    } else {
      badge.classList.add('dealhawk-badge--poor');
    }

    // Badge content (use textContent to avoid XSS from scraped data)
    const scoreDiv = document.createElement('div');
    scoreDiv.className = 'dealhawk-badge__score';
    scoreDiv.textContent = score;
    const labelDiv = document.createElement('div');
    labelDiv.className = 'dealhawk-badge__label';
    labelDiv.textContent = grade;
    badge.appendChild(scoreDiv);
    badge.appendChild(labelDiv);

    // Tooltip
    const pricing = scoreResult.pricing || {};
    const offers = scoreResult.offers || {};
    badge.title = [
      `DealHawk Score: ${score}/100 (${grade})`,
      pricing.true_dealer_cost ? `Est. Dealer Cost: $${pricing.true_dealer_cost.toLocaleString()}` : '',
      offers.reasonable ? `Target Offer: $${offers.reasonable.toLocaleString()}` : '',
    ]
      .filter(Boolean)
      .join('\n');

    // Click to open side panel with full analysis
    badge.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopPropagation();

      // Store the listing data for the side panel
      await chrome.storage.local.set({
        currentListing: { ...listing, scoreResult },
      });

      // Open side panel
      chrome.runtime.sendMessage({ action: 'OPEN_SIDE_PANEL' });
    });

    // Position the badge
    const wrapper = cardElement.closest('a') || cardElement;
    if (getComputedStyle(wrapper).position === 'static') {
      wrapper.style.position = 'relative';
    }
    wrapper.appendChild(badge);
  };
})();
