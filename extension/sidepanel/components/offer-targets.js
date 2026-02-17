/**
 * Offer Targets Component
 * Renders the three offer target levels with carrying cost context.
 */

function renderOfferTargets(container, offers) {
  const fmt = (n) => n != null ? '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : 'N/A';

  container.textContent = '';

  const card = document.createElement('div');
  card.className = 'card';

  const title = document.createElement('div');
  title.className = 'card__title';
  title.textContent = 'Offer Targets';
  card.appendChild(title);

  const offersDiv = document.createElement('div');
  offersDiv.className = 'offers';

  function addOffer(cssClass, label, value) {
    const offer = document.createElement('div');
    offer.className = `offer ${cssClass}`;

    const labelWrap = document.createElement('div');
    const labelEl = document.createElement('div');
    labelEl.className = 'offer__label';
    labelEl.textContent = label;
    labelWrap.appendChild(labelEl);

    const valueEl = document.createElement('div');
    valueEl.className = 'offer__value';
    valueEl.textContent = fmt(value);

    offer.appendChild(labelWrap);
    offer.appendChild(valueEl);
    offersDiv.appendChild(offer);
  }

  addOffer('offer--aggressive', 'Aggressive (walk-away price)', offers.aggressive);
  addOffer('offer--reasonable', 'Reasonable (strong starting point)', offers.reasonable);
  addOffer('offer--likely', 'Likely Settlement', offers.likely);

  card.appendChild(offersDiv);

  if (offers.carrying_costs > 0) {
    const note = document.createElement('div');
    note.style.cssText = 'margin-top: 10px; font-size: 11px; color: #64748b; padding: 8px; background: #f8fafc; border-radius: 4px;';
    note.textContent = `Est. dealer carrying costs: ${fmt(offers.carrying_costs)} \u2014 this is money the dealer has already lost holding this vehicle. Use it in negotiation.`;
    card.appendChild(note);
  }

  container.appendChild(card);
}
