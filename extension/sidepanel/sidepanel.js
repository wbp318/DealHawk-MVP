/**
 * DealHawk Side Panel Controller
 * Manages tabs, loads analysis data, handles calculator, saved vehicles, and alerts.
 */

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initAnalysis();
  initCalculator();
  initTax();
  initSaved();
  initAlerts();
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

      // Refresh saved/alerts when switching to those tabs
      if (tab.dataset.tab === 'saved') initSaved();
      if (tab.dataset.tab === 'alerts') initAlerts();
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

  // Fetch and render market context
  fetchMarketContext(listing);

  // Fetch and render negotiation talking points
  fetchTalkingPoints(listing, scoreResult);

  // Add "Save This Vehicle" button
  renderSaveButton(listing, scoreResult);
}

function renderSaveButton(listing, scoreResult) {
  // Remove existing save button if any
  const existing = document.getElementById('save-vehicle-btn');
  if (existing) existing.remove();

  const container = document.getElementById('analysis-content');
  const btn = document.createElement('button');
  btn.id = 'save-vehicle-btn';
  btn.className = 'btn btn--save';
  btn.textContent = 'Save This Vehicle';

  btn.addEventListener('click', async () => {
    btn.disabled = true;
    btn.textContent = 'Saving...';

    try {
      const saveData = {
        vin: listing.vin || null,
        platform: listing.platform || null,
        listing_url: listing.url || null,
        asking_price: listing.asking_price || null,
        msrp: listing.msrp || scoreResult.pricing?.msrp || null,
        year: listing.year || null,
        make: listing.make || null,
        model: listing.model || null,
        trim: listing.trim || null,
        days_on_lot: listing.days_on_lot || listing.days_on_platform || null,
        dealer_name: listing.dealer_name || null,
        dealer_location: listing.dealer_location || null,
        deal_score: scoreResult.score || null,
        deal_grade: scoreResult.grade || null,
      };

      const result = await chrome.runtime.sendMessage({
        action: 'SAVE_VEHICLE',
        data: saveData,
      });

      if (result && result.error) {
        if (result.error.includes('403')) {
          btn.textContent = 'Upgrade to Pro';
        } else if (result.error.includes('401')) {
          btn.textContent = 'Log in to Save';
        } else {
          btn.textContent = 'Save Failed';
        }
      } else {
        btn.textContent = 'Saved!';
      }
    } catch (err) {
      const msg = err.message || '';
      btn.textContent = msg.includes('403') ? 'Upgrade to Pro' : 'Log in to Save';
    }

    setTimeout(() => {
      btn.disabled = false;
      btn.textContent = 'Save This Vehicle';
    }, 2000);
  });

  container.appendChild(btn);
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

async function fetchMarketContext(listing) {
  const container = document.getElementById('market-context-container');
  const make = listing.make || '';
  const model = listing.model || '';

  if (!make || !model) {
    container.textContent = '';
    return;
  }

  try {
    const result = await chrome.runtime.sendMessage({
      action: 'GET_MARKET_TRENDS',
      data: { make, model },
    });

    if (result && !result.error) {
      renderMarketContext(container, result);
    }
  } catch {
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

// --- Tax Tab ---

function initTax() {
  const calcBtn = document.getElementById('tax-calc-btn');
  const resultsDiv = document.getElementById('tax-results');

  if (!calcBtn) return;

  calcBtn.addEventListener('click', async () => {
    const price = parseFloat(document.getElementById('tax-price').value) || 0;
    const model = document.getElementById('tax-model').value.trim() || null;
    const gvwrRaw = parseInt(document.getElementById('tax-gvwr').value);
    const gvwr = (gvwrRaw > 0) ? gvwrRaw : null;
    const businessPct = parseFloat(document.getElementById('tax-business-pct').value) || 0;
    const bracket = parseFloat(document.getElementById('tax-bracket').value) || 0;
    const stateRate = parseFloat(document.getElementById('tax-state-rate').value) || 0;
    const downPayment = parseFloat(document.getElementById('tax-down-payment').value) || 0;
    const interestRate = parseFloat(document.getElementById('tax-interest-rate').value) || 0;
    const loanTerm = parseInt(document.getElementById('tax-loan-term').value) || 60;

    if (price <= 0) {
      resultsDiv.textContent = '';
      const errCard = document.createElement('div');
      errCard.className = 'card';
      errCard.style.color = '#dc2626';
      errCard.textContent = 'Please enter a vehicle price.';
      resultsDiv.appendChild(errCard);
      return;
    }

    calcBtn.textContent = 'Calculating...';
    calcBtn.disabled = true;

    try {
      const result = await chrome.runtime.sendMessage({
        action: 'CALCULATE_SECTION_179',
        data: {
          vehicle_price: price,
          business_use_pct: businessPct,
          tax_bracket: bracket,
          state_tax_rate: stateRate,
          down_payment: downPayment,
          loan_interest_rate: interestRate,
          loan_term_months: loanTerm,
          model: model,
          gvwr: gvwr,
        },
      });

      if (result && result.error) throw new Error(result.error);

      renderTaxResults(resultsDiv, result);
    } catch (err) {
      resultsDiv.textContent = '';
      const errCard = document.createElement('div');
      errCard.className = 'card';
      errCard.style.color = '#dc2626';
      errCard.textContent = 'Calculation failed. Is the backend running?';
      resultsDiv.appendChild(errCard);
    }

    calcBtn.textContent = 'Calculate Tax Savings';
    calcBtn.disabled = false;
  });
}

// --- Saved Tab ---

async function initSaved() {
  const authRequired = document.getElementById('saved-auth-required');
  const proRequired = document.getElementById('saved-pro-required');
  const emptyState = document.getElementById('saved-empty');
  const listContainer = document.getElementById('saved-list');

  if (!authRequired) return;

  // Helper to hide all state divs
  function hideAll() {
    authRequired.hidden = true;
    if (proRequired) proRequired.hidden = true;
    emptyState.hidden = true;
    listContainer.hidden = true;
  }

  let user;
  try {
    user = await chrome.runtime.sendMessage({ action: 'AUTH_GET_ME' });
    if (!user || user.error || !user.email) {
      hideAll();
      authRequired.hidden = false;
      return;
    }
  } catch {
    hideAll();
    authRequired.hidden = false;
    return;
  }

  // Check Pro tier
  if (user.subscription_tier !== 'pro') {
    hideAll();
    if (proRequired) {
      proRequired.hidden = false;
      const upgradeBtn = document.getElementById('saved-upgrade-btn');
      if (upgradeBtn) {
        upgradeBtn.onclick = async () => {
          upgradeBtn.disabled = true;
          upgradeBtn.textContent = 'Loading...';
          try {
            const result = await chrome.runtime.sendMessage({ action: 'CREATE_CHECKOUT' });
            if (result && result.checkout_url) {
              chrome.tabs.create({ url: result.checkout_url });
            }
          } catch { /* ignore */ }
          setTimeout(() => {
            upgradeBtn.disabled = false;
            upgradeBtn.textContent = 'Upgrade to Pro';
          }, 3000);
        };
      }
    }
    return;
  }

  hideAll();

  try {
    const vehicles = await chrome.runtime.sendMessage({ action: 'GET_SAVED_VEHICLES' });
    if (!vehicles || vehicles.error || vehicles.length === 0) {
      emptyState.hidden = false;
      listContainer.hidden = true;
      return;
    }

    emptyState.hidden = true;
    listContainer.hidden = false;
    listContainer.textContent = '';

    for (const v of vehicles) {
      const card = document.createElement('div');
      card.className = 'card saved-card';

      const title = document.createElement('div');
      title.className = 'saved-card__title';
      title.textContent = [v.year, v.make, v.model, v.trim].filter(Boolean).join(' ') || 'Vehicle';
      card.appendChild(title);

      const details = document.createElement('div');
      details.className = 'saved-card__details';

      if (v.deal_score != null) {
        const scoreSpan = document.createElement('span');
        scoreSpan.className = 'saved-card__score';
        const scoreClass = v.deal_score >= 80 ? 'great' : v.deal_score >= 50 ? 'good' : 'poor';
        scoreSpan.classList.add(`saved-card__score--${scoreClass}`);
        scoreSpan.textContent = `${v.deal_score} (${v.deal_grade || ''})`;
        details.appendChild(scoreSpan);
      }

      if (v.asking_price) {
        const priceSpan = document.createElement('span');
        priceSpan.textContent = `$${v.asking_price.toLocaleString()}`;
        details.appendChild(priceSpan);
      }

      card.appendChild(details);

      const meta = document.createElement('div');
      meta.className = 'saved-card__meta';
      meta.textContent = [v.dealer_name, v.platform, v.saved_at?.split('T')[0]].filter(Boolean).join(' | ');
      card.appendChild(meta);

      if (v.notes) {
        const notes = document.createElement('div');
        notes.className = 'saved-card__notes';
        notes.textContent = v.notes;
        card.appendChild(notes);
      }

      // Delete button
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'btn btn--delete-small';
      deleteBtn.textContent = 'Remove';
      deleteBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        deleteBtn.disabled = true;
        try {
          await chrome.runtime.sendMessage({
            action: 'DELETE_SAVED_VEHICLE',
            data: { id: v.id },
          });
          card.remove();
          // Check if list is now empty
          if (listContainer.children.length === 0) {
            emptyState.hidden = false;
            listContainer.hidden = true;
          }
        } catch {
          deleteBtn.disabled = false;
        }
      });
      card.appendChild(deleteBtn);

      // Click card to load analysis
      card.addEventListener('click', () => {
        const fakeScoreResult = {
          score: v.deal_score,
          grade: v.deal_grade,
          pricing: v.msrp ? { msrp: v.msrp } : null,
        };
        chrome.storage.local.set({
          currentListing: { ...v, scoreResult: fakeScoreResult },
        });
        // Switch to analysis tab
        document.querySelector('[data-tab="analysis"]').click();
      });

      listContainer.appendChild(card);
    }
  } catch {
    emptyState.hidden = false;
    listContainer.hidden = true;
  }
}

// --- Alerts Tab ---

async function initAlerts() {
  const authRequired = document.getElementById('alerts-auth-required');
  const proRequired = document.getElementById('alerts-pro-required');
  const emptyState = document.getElementById('alerts-empty');
  const listContainer = document.getElementById('alerts-list');
  const newBtn = document.getElementById('new-alert-btn');
  const createForm = document.getElementById('alert-create-form');

  if (!authRequired) return;

  // Helper to hide all state divs
  function hideAll() {
    authRequired.hidden = true;
    if (proRequired) proRequired.hidden = true;
    emptyState.hidden = true;
    listContainer.hidden = true;
    if (newBtn) newBtn.hidden = true;
    if (createForm) createForm.hidden = true;
  }

  let user;
  try {
    user = await chrome.runtime.sendMessage({ action: 'AUTH_GET_ME' });
    if (!user || user.error || !user.email) {
      hideAll();
      authRequired.hidden = false;
      return;
    }
  } catch {
    hideAll();
    authRequired.hidden = false;
    return;
  }

  // Check Pro tier
  if (user.subscription_tier !== 'pro') {
    hideAll();
    if (proRequired) {
      proRequired.hidden = false;
      const upgradeBtn = document.getElementById('alerts-upgrade-btn');
      if (upgradeBtn) {
        upgradeBtn.onclick = async () => {
          upgradeBtn.disabled = true;
          upgradeBtn.textContent = 'Loading...';
          try {
            const result = await chrome.runtime.sendMessage({ action: 'CREATE_CHECKOUT' });
            if (result && result.checkout_url) {
              chrome.tabs.create({ url: result.checkout_url });
            }
          } catch { /* ignore */ }
          setTimeout(() => {
            upgradeBtn.disabled = false;
            upgradeBtn.textContent = 'Upgrade to Pro';
          }, 3000);
        };
      }
    }
    return;
  }

  hideAll();
  if (newBtn) newBtn.hidden = false;

  // Setup new alert button
  if (newBtn && createForm) {
    newBtn.onclick = () => {
      createForm.hidden = !createForm.hidden;
    };
  }

  // Setup create form submit
  const submitBtn = document.getElementById('alert-submit-btn');
  if (submitBtn) {
    submitBtn.onclick = async () => {
      const alertData = {
        name: document.getElementById('alert-name').value.trim() || 'My Alert',
        make: document.getElementById('alert-make').value || null,
        model: document.getElementById('alert-model').value.trim() || null,
        year_min: parseInt(document.getElementById('alert-year-min').value) || null,
        year_max: parseInt(document.getElementById('alert-year-max').value) || null,
        price_max: parseFloat(document.getElementById('alert-price-max').value) || null,
        score_min: parseInt(document.getElementById('alert-score-min').value) || null,
      };

      submitBtn.disabled = true;
      try {
        await chrome.runtime.sendMessage({ action: 'CREATE_ALERT', data: alertData });
        if (createForm) createForm.hidden = true;
        initAlerts(); // Refresh
      } catch {
        submitBtn.disabled = false;
      }
      submitBtn.disabled = false;
    };
  }

  try {
    const alerts = await chrome.runtime.sendMessage({ action: 'GET_ALERTS' });
    if (!alerts || alerts.error || alerts.length === 0) {
      emptyState.hidden = false;
      listContainer.hidden = true;
      return;
    }

    emptyState.hidden = true;
    listContainer.hidden = false;
    listContainer.textContent = '';

    for (const a of alerts) {
      const card = document.createElement('div');
      card.className = 'card alert-card';

      const title = document.createElement('div');
      title.className = 'alert-card__title';
      title.textContent = a.name;
      card.appendChild(title);

      const criteria = document.createElement('div');
      criteria.className = 'alert-card__criteria';
      const parts = [];
      if (a.make) parts.push(a.make);
      if (a.model) parts.push(a.model);
      if (a.year_min || a.year_max) parts.push(`${a.year_min || '?'}-${a.year_max || '?'}`);
      if (a.price_max) parts.push(`< $${a.price_max.toLocaleString()}`);
      if (a.score_min) parts.push(`Score ${a.score_min}+`);
      criteria.textContent = parts.join(' | ') || 'Any vehicle';
      card.appendChild(criteria);

      const statusSpan = document.createElement('span');
      statusSpan.className = `alert-card__status ${a.is_active ? 'alert-card__status--active' : 'alert-card__status--paused'}`;
      statusSpan.textContent = a.is_active ? 'Active' : 'Paused';
      card.appendChild(statusSpan);

      // Delete button
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'btn btn--delete-small';
      deleteBtn.textContent = 'Delete';
      deleteBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        deleteBtn.disabled = true;
        try {
          await chrome.runtime.sendMessage({ action: 'DELETE_ALERT', data: { id: a.id } });
          card.remove();
          if (listContainer.children.length === 0) {
            emptyState.hidden = false;
            listContainer.hidden = true;
          }
        } catch {
          deleteBtn.disabled = false;
        }
      });
      card.appendChild(deleteBtn);

      listContainer.appendChild(card);
    }
  } catch {
    emptyState.hidden = false;
    listContainer.hidden = true;
  }
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
      errCard.textContent = 'Calculation failed. Check your inputs and try again.';
      resultsDiv.appendChild(errCard);
    }

    calcBtn.textContent = 'Calculate';
    calcBtn.disabled = false;
  });
}
