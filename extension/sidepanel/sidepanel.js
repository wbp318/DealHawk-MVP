/**
 * DealHawk Side Panel Controller
 * Manages tabs, loads analysis data, and handles the calculator.
 */

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initAnalysis();
  initCalculator();
});

// --- Tab Management ---

function initTabs() {
  const tabs = document.querySelectorAll('.tab');
  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      tabs.forEach((t) => t.classList.remove('tab--active'));
      tab.classList.add('tab--active');

      document.querySelectorAll('.tab-content').forEach((c) => c.classList.remove('tab-content--active'));
      document.getElementById(`tab-${tab.dataset.tab}`).classList.add('tab-content--active');
    });
  });
}

// --- Analysis Tab ---

function initAnalysis() {
  // Load current listing data from storage
  chrome.storage.local.get('currentListing', (result) => {
    if (result.currentListing && result.currentListing.scoreResult) {
      renderAnalysis(result.currentListing, result.currentListing.scoreResult);
    }
  });

  // Listen for updates
  chrome.storage.onChanged.addListener((changes) => {
    if (changes.currentListing) {
      const listing = changes.currentListing.newValue;
      if (listing && listing.scoreResult) {
        renderAnalysis(listing, listing.scoreResult);
      }
    }
  });
}

function renderAnalysis(listing, scoreResult) {
  document.getElementById('analysis-empty').hidden = true;
  document.getElementById('analysis-content').hidden = false;

  // Vehicle header
  const header = document.getElementById('vehicle-header');
  const title = [listing.year, listing.make, listing.model, listing.trim].filter(Boolean).join(' ');
  const meta = [
    listing.dealer_name,
    listing.dealer_location,
    listing.days_on_lot ? `${listing.days_on_lot} days on lot` : null,
    listing.vin ? `VIN: ${listing.vin}` : null,
  ].filter(Boolean).join(' | ');

  header.textContent = '';
  const titleDiv = document.createElement('div');
  titleDiv.className = 'vehicle-header__title';
  titleDiv.textContent = title || 'Vehicle';
  const metaDiv = document.createElement('div');
  metaDiv.className = 'vehicle-header__meta';
  metaDiv.textContent = meta;
  header.appendChild(titleDiv);
  header.appendChild(metaDiv);

  // Score gauge
  renderScoreGauge(
    document.getElementById('score-gauge-container'),
    scoreResult.score,
    scoreResult.grade
  );

  // Price breakdown
  if (scoreResult.pricing) {
    renderPriceBreakdown(
      document.getElementById('price-breakdown-container'),
      listing.asking_price,
      scoreResult.pricing
    );
  }

  // Offer targets
  if (scoreResult.offers) {
    renderOfferTargets(
      document.getElementById('offer-targets-container'),
      scoreResult.offers
    );
  }

  // Score breakdown bars
  if (scoreResult.breakdown) {
    renderScoreBreakdown(
      document.getElementById('score-breakdown-container'),
      scoreResult.breakdown
    );
  }

  // Fetch and render negotiation talking points
  fetchTalkingPoints(listing, scoreResult);
}

async function fetchTalkingPoints(listing, scoreResult) {
  const container = document.getElementById('talking-points-container');

  try {
    const data = {
      asking_price: listing.asking_price,
      msrp: listing.msrp || scoreResult.pricing?.msrp || listing.asking_price * 1.05,
      make: listing.make || 'Unknown',
      model: listing.model || 'Unknown',
      year: listing.year || new Date().getFullYear(),
      days_on_lot: listing.days_on_lot || listing.days_on_platform || 0,
      rebates_available: 0,
    };

    const result = await chrome.runtime.sendMessage({
      action: 'GET_NEGOTIATION',
      data,
    });

    if (result && result.talking_points) {
      renderTalkingPoints(container, result.talking_points);
    }
  } catch (err) {
    container.textContent = '';
  }
}

function renderScoreBreakdown(container, breakdown) {
  const factors = [
    { label: 'Price vs Cost', key: 'price' },
    { label: 'Days on Lot', key: 'days_on_lot' },
    { label: 'Incentives', key: 'incentives' },
    { label: 'Market Supply', key: 'market_supply' },
    { label: 'Timing', key: 'timing' },
  ];

  const card = document.createElement('div');
  card.className = 'card';
  const cardTitle = document.createElement('div');
  cardTitle.className = 'card__title';
  cardTitle.textContent = 'Score Breakdown';
  card.appendChild(cardTitle);

  const bars = document.createElement('div');
  bars.className = 'score-bars';

  for (const f of factors) {
    const data = breakdown[f.key];
    if (!data) continue;

    const score = Number(data.score) || 0;
    const clampedScore = Math.max(0, Math.min(100, score));
    const colorClass = clampedScore >= 70 ? 'great' : clampedScore >= 40 ? 'good' : 'poor';

    const bar = document.createElement('div');
    bar.className = 'score-bar';

    const label = document.createElement('span');
    label.className = 'score-bar__label';
    label.textContent = `${f.label} (${data.weight})`;

    const track = document.createElement('div');
    track.className = 'score-bar__track';
    const fill = document.createElement('div');
    fill.className = `score-bar__fill score-bar__fill--${colorClass}`;
    fill.style.width = `${clampedScore}%`;
    track.appendChild(fill);

    const value = document.createElement('span');
    value.className = 'score-bar__value';
    value.textContent = clampedScore;

    bar.appendChild(label);
    bar.appendChild(track);
    bar.appendChild(value);
    bars.appendChild(bar);
  }

  card.appendChild(bars);
  container.textContent = '';
  container.appendChild(card);
}

function renderTalkingPoints(container, points) {
  container.textContent = '';
  if (!points || points.length === 0) return;

  const card = document.createElement('div');
  card.className = 'card';
  const cardTitle = document.createElement('div');
  cardTitle.className = 'card__title';
  cardTitle.textContent = 'Negotiation Talking Points';
  card.appendChild(cardTitle);

  for (const pt of points) {
    const leverageClass = pt.leverage === 'high' ? 'high' : 'medium';

    const tpDiv = document.createElement('div');
    tpDiv.className = 'talking-point';

    const header = document.createElement('div');
    header.className = 'talking-point__header';
    const cat = document.createElement('span');
    cat.className = 'talking-point__category';
    cat.textContent = pt.category;
    const lev = document.createElement('span');
    lev.className = `talking-point__leverage talking-point__leverage--${leverageClass}`;
    lev.textContent = pt.leverage;
    header.appendChild(cat);
    header.appendChild(lev);

    const text = document.createElement('div');
    text.className = 'talking-point__text';
    text.textContent = pt.point;

    const script = document.createElement('div');
    script.className = 'talking-point__script';
    script.textContent = pt.script;

    tpDiv.appendChild(header);
    tpDiv.appendChild(text);
    tpDiv.appendChild(script);
    card.appendChild(tpDiv);
  }

  container.appendChild(card);
}

// --- Calculator Tab ---

function initCalculator() {
  const calcBtn = document.getElementById('calc-btn');
  const resultsDiv = document.getElementById('calc-results');

  calcBtn.addEventListener('click', async () => {
    const make = document.getElementById('calc-make').value;
    const model = document.getElementById('calc-model').value || 'Unknown';
    const year = parseInt(document.getElementById('calc-year').value) || 2026;
    const msrp = parseFloat(document.getElementById('calc-msrp').value) || 0;
    const asking = parseFloat(document.getElementById('calc-asking').value) || msrp;
    const days = parseInt(document.getElementById('calc-days').value) || 0;
    const rebates = parseFloat(document.getElementById('calc-rebates').value) || 0;

    if (msrp <= 0) {
      resultsDiv.hidden = false;
      resultsDiv.textContent = '';
      const errCard = document.createElement('div');
      errCard.className = 'card';
      errCard.style.color = '#dc2626';
      errCard.textContent = 'Please enter an MSRP value.';
      resultsDiv.appendChild(errCard);
      return;
    }

    calcBtn.textContent = 'Calculating...';
    calcBtn.disabled = true;

    try {
      const scoreResult = await chrome.runtime.sendMessage({
        action: 'SCORE_LISTING',
        data: {
          asking_price: asking,
          msrp,
          make,
          model,
          year,
          days_on_lot: days,
          rebates_available: rebates,
        },
      });

      if (scoreResult.error) throw new Error(scoreResult.error);

      resultsDiv.hidden = false;
      resultsDiv.textContent = '';

      // Score gauge
      const gaugeDiv = document.createElement('div');
      resultsDiv.appendChild(gaugeDiv);
      renderScoreGauge(gaugeDiv, scoreResult.score, scoreResult.grade);

      // Price breakdown
      if (scoreResult.pricing) {
        const priceDiv = document.createElement('div');
        resultsDiv.appendChild(priceDiv);
        renderPriceBreakdown(priceDiv, asking, scoreResult.pricing);
      }

      // Offer targets
      if (scoreResult.offers) {
        const offerDiv = document.createElement('div');
        resultsDiv.appendChild(offerDiv);
        renderOfferTargets(offerDiv, scoreResult.offers);
      }
    } catch (err) {
      resultsDiv.hidden = false;
      resultsDiv.textContent = '';
      const errCard = document.createElement('div');
      errCard.className = 'card';
      errCard.style.color = '#dc2626';
      errCard.textContent = `Error: ${err.message}. Is the backend running?`;
      resultsDiv.appendChild(errCard);
    }

    calcBtn.textContent = 'Calculate';
    calcBtn.disabled = false;
  });
}
