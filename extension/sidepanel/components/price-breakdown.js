/**
 * Price Breakdown Component
 * Renders the cost analysis table showing MSRP, invoice, holdback, true cost.
 */

function renderPriceBreakdown(container, askingPrice, pricing) {
  const fmt = (n) => n != null ? '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : 'N/A';

  const savingsFromMsrp = pricing.msrp - askingPrice;
  const savingsFromMsrpClass = savingsFromMsrp > 0 ? 'highlight' : 'negative';
  const askingVsCost = askingPrice - pricing.true_dealer_cost;

  container.textContent = '';

  const card = document.createElement('div');
  card.className = 'card';

  const title = document.createElement('div');
  title.className = 'card__title';
  title.textContent = 'Price Breakdown';
  card.appendChild(title);

  const table = document.createElement('table');
  table.className = 'price-table';

  function addRow(label, value, cssClass, isTotal) {
    const tr = document.createElement('tr');
    if (isTotal) tr.className = 'total-row';
    const tdLabel = document.createElement('td');
    tdLabel.textContent = label;
    const tdValue = document.createElement('td');
    tdValue.textContent = value;
    if (cssClass) tdValue.className = cssClass;
    tr.appendChild(tdLabel);
    tr.appendChild(tdValue);
    table.appendChild(tr);
  }

  addRow('MSRP', fmt(pricing.msrp));
  addRow('Invoice Price', fmt(pricing.invoice_price));
  addRow(pricing.holdback ? 'Holdback (refunded to dealer)' : 'Holdback (est.)', '-' + fmt(pricing.holdback), 'negative');
  addRow('Dealer Cash', pricing.dealer_cash ? '-' + fmt(pricing.dealer_cash) : '$0', 'negative');
  addRow('True Dealer Cost', fmt(pricing.true_dealer_cost), null, true);

  // Spacer
  const spacer = document.createElement('tr');
  const spacerTd = document.createElement('td');
  spacerTd.colSpan = 2;
  spacerTd.style.paddingTop = '12px';
  spacer.appendChild(spacerTd);
  table.appendChild(spacer);

  addRow('Asking Price', fmt(askingPrice));
  addRow('Savings from MSRP', (savingsFromMsrp >= 0 ? '' : '-') + fmt(Math.abs(savingsFromMsrp)), savingsFromMsrpClass);
  addRow('Asking vs True Cost', (askingVsCost > 0 ? '+' : '') + fmt(askingVsCost), askingVsCost > 0 ? 'negative' : 'highlight');

  card.appendChild(table);

  const source = document.createElement('div');
  source.style.cssText = 'margin-top: 8px; font-size: 11px; color: #94a3b8;';
  source.textContent = 'Source: ' + (pricing.source === 'cached' ? 'Invoice database' : 'Estimated from segment ratios');
  card.appendChild(source);

  container.appendChild(card);
}
