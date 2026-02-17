/**
 * Market Context Component
 * Renders market trend data — days supply, supply level, incentives, price trend.
 */

function renderMarketContext(container, trendData) {
  container.textContent = '';

  if (!trendData) return;

  const card = document.createElement('div');
  card.className = 'card';

  const title = document.createElement('div');
  title.className = 'card__title';
  title.textContent = 'Market Context';
  card.appendChild(title);

  const grid = document.createElement('div');
  grid.className = 'market-grid';

  // Days supply gauge
  const supplyItem = document.createElement('div');
  supplyItem.className = 'market-item';

  const supplyLabel = document.createElement('div');
  supplyLabel.className = 'market-item__label';
  supplyLabel.textContent = 'Days Supply';
  supplyItem.appendChild(supplyLabel);

  const supplyValue = document.createElement('div');
  supplyValue.className = 'market-item__value';
  supplyValue.textContent = String(trendData.days_supply);
  supplyItem.appendChild(supplyValue);

  const supplyNote = document.createElement('div');
  supplyNote.className = 'market-item__note';
  supplyNote.textContent = 'Industry avg: ' + trendData.industry_avg_days_supply;
  supplyItem.appendChild(supplyNote);

  grid.appendChild(supplyItem);

  // Supply level indicator
  const levelItem = document.createElement('div');
  levelItem.className = 'market-item';

  const levelLabel = document.createElement('div');
  levelLabel.className = 'market-item__label';
  levelLabel.textContent = 'Supply Level';
  levelItem.appendChild(levelLabel);

  const levelBadge = document.createElement('div');
  const level = String(trendData.supply_level || 'balanced');
  const levelClass = level === 'oversupplied' ? 'great' : level === 'undersupplied' ? 'poor' : 'good';
  levelBadge.className = 'market-badge market-badge--' + levelClass;
  levelBadge.textContent = level.charAt(0).toUpperCase() + level.slice(1);
  levelItem.appendChild(levelBadge);

  grid.appendChild(levelItem);

  // Price trend
  const trendItem = document.createElement('div');
  trendItem.className = 'market-item';

  const trendLabel = document.createElement('div');
  trendLabel.className = 'market-item__label';
  trendLabel.textContent = 'Price Trend';
  trendItem.appendChild(trendLabel);

  const trendValue = document.createElement('div');
  const trend = String(trendData.price_trend || 'stable');
  const trendArrow = trend === 'declining' ? '\u2193' : trend === 'rising' ? '\u2191' : '\u2194';
  const trendClass = trend === 'declining' ? 'great' : trend === 'rising' ? 'poor' : 'good';
  trendValue.className = 'market-trend market-trend--' + trendClass;
  trendValue.textContent = trendArrow + ' ' + trend.charAt(0).toUpperCase() + trend.slice(1);
  trendItem.appendChild(trendValue);

  grid.appendChild(trendItem);

  // Active incentives
  const incItem = document.createElement('div');
  incItem.className = 'market-item';

  const incLabel = document.createElement('div');
  incLabel.className = 'market-item__label';
  incLabel.textContent = 'Active Incentives';
  incItem.appendChild(incLabel);

  const incValue = document.createElement('div');
  incValue.className = 'market-item__value';
  incValue.textContent = String(trendData.active_incentive_count || 0);
  incItem.appendChild(incValue);

  if (trendData.total_incentive_value > 0) {
    const incTotal = document.createElement('div');
    incTotal.className = 'market-item__note market-item__note--green';
    incTotal.textContent = 'Up to $' + Number(trendData.total_incentive_value).toLocaleString();
    incItem.appendChild(incTotal);
  }

  grid.appendChild(incItem);

  card.appendChild(grid);

  if (trendData.source === 'stub') {
    const src = document.createElement('div');
    src.style.cssText = 'margin-top: 8px; font-size: 10px; color: #94a3b8;';
    src.textContent = 'Source: DealHawk research data';
    card.appendChild(src);
  }

  container.appendChild(card);
}
