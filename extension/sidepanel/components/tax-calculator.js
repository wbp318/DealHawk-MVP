/**
 * Tax Calculator Component
 * Renders Section 179 deduction results — qualification, savings, effective cost, financing.
 */

function renderTaxResults(container, data) {
  container.textContent = '';

  if (!data) return;

  // Disqualified
  if (!data.qualifies) {
    const card = document.createElement('div');
    card.className = 'card';
    const badge = document.createElement('div');
    badge.className = 'tax-badge tax-badge--no';
    badge.textContent = 'Does Not Qualify';
    card.appendChild(badge);

    const reason = document.createElement('div');
    reason.className = 'tax-reason';
    reason.textContent = data.reason;
    card.appendChild(reason);

    container.appendChild(card);
    return;
  }

  const fmt = (n) => '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });

  // Qualification badge
  const qualCard = document.createElement('div');
  qualCard.className = 'card';

  const badge = document.createElement('div');
  badge.className = 'tax-badge tax-badge--yes';
  badge.textContent = 'Qualifies for Section 179';
  qualCard.appendChild(badge);

  if (data.gvwr_note) {
    const gvwrNote = document.createElement('div');
    gvwrNote.className = 'tax-note';
    gvwrNote.textContent = data.gvwr_note;
    qualCard.appendChild(gvwrNote);
  }

  if (data.cap_note) {
    const capNote = document.createElement('div');
    capNote.className = 'tax-note';
    capNote.textContent = data.cap_note;
    qualCard.appendChild(capNote);
  }

  container.appendChild(qualCard);

  // Deduction + Savings
  const savingsCard = document.createElement('div');
  savingsCard.className = 'card';

  const savingsTitle = document.createElement('div');
  savingsTitle.className = 'card__title';
  savingsTitle.textContent = 'Tax Savings Breakdown';
  savingsCard.appendChild(savingsTitle);

  const deductionRow = document.createElement('div');
  deductionRow.className = 'tax-big-number';
  const deductionLabel = document.createElement('div');
  deductionLabel.className = 'tax-big-number__label';
  deductionLabel.textContent = 'First-Year Deduction';
  const deductionValue = document.createElement('div');
  deductionValue.className = 'tax-big-number__value';
  deductionValue.textContent = fmt(data.first_year_deduction);
  deductionRow.appendChild(deductionLabel);
  deductionRow.appendChild(deductionValue);
  savingsCard.appendChild(deductionRow);

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

  addRow('Vehicle Price', fmt(data.vehicle_price));
  addRow('Business Use', data.business_use_pct + '%');
  addRow('Federal Tax Savings', fmt(data.federal_tax_savings), 'highlight');
  if (data.state_tax_savings > 0) {
    addRow('State Tax Savings', fmt(data.state_tax_savings), 'highlight');
  }
  addRow('Total Tax Savings', fmt(data.total_tax_savings), 'highlight', true);

  savingsCard.appendChild(table);
  container.appendChild(savingsCard);

  // Effective cost
  const costCard = document.createElement('div');
  costCard.className = 'card';

  const costTitle = document.createElement('div');
  costTitle.className = 'card__title';
  costTitle.textContent = 'Effective Cost';
  costCard.appendChild(costTitle);

  const effectiveRow = document.createElement('div');
  effectiveRow.className = 'tax-big-number tax-big-number--green';
  const effectiveLabel = document.createElement('div');
  effectiveLabel.className = 'tax-big-number__label';
  effectiveLabel.textContent = 'After Tax Savings';
  const effectiveValue = document.createElement('div');
  effectiveValue.className = 'tax-big-number__value';
  effectiveValue.textContent = fmt(data.effective_cost_after_tax);
  effectiveRow.appendChild(effectiveLabel);
  effectiveRow.appendChild(effectiveValue);
  costCard.appendChild(effectiveRow);

  container.appendChild(costCard);

  // Financing details
  if (data.financing) {
    const finCard = document.createElement('div');
    finCard.className = 'card';

    const finTitle = document.createElement('div');
    finTitle.className = 'card__title';
    finTitle.textContent = 'Financing Details';
    finCard.appendChild(finTitle);

    const finTable = document.createElement('table');
    finTable.className = 'price-table';

    function addFinRow(label, value, cssClass, isTotal) {
      const tr = document.createElement('tr');
      if (isTotal) tr.className = 'total-row';
      const tdLabel = document.createElement('td');
      tdLabel.textContent = label;
      const tdValue = document.createElement('td');
      tdValue.textContent = value;
      if (cssClass) tdValue.className = cssClass;
      tr.appendChild(tdLabel);
      tr.appendChild(tdValue);
      finTable.appendChild(tr);
    }

    const fin = data.financing;
    addFinRow('Down Payment', fmt(fin.down_payment));
    addFinRow('Loan Amount', fmt(fin.loan_amount));
    addFinRow('Monthly Payment', fmt(fin.monthly_payment));
    if (fin.total_interest > 0) {
      addFinRow('Total Interest', fmt(fin.total_interest), 'negative');
    }
    addFinRow('Monthly Tax Benefit', fmt(fin.monthly_tax_benefit), 'highlight');
    addFinRow('Effective Monthly Cost', fmt(fin.effective_monthly_cost), null, true);

    finCard.appendChild(finTable);
    container.appendChild(finCard);
  }

  // Disclaimer
  const disclaimer = document.createElement('div');
  disclaimer.className = 'tax-disclaimer';
  disclaimer.textContent = `${data.tax_year} tax year. Section 179 limit: ${fmt(data.section_179_limit)}. ` +
    'This is an estimate for educational purposes only. Consult a tax professional.';
  container.appendChild(disclaimer);
}
