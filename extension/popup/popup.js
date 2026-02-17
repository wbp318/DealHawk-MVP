document.addEventListener('DOMContentLoaded', async () => {
  const statusEl = document.getElementById('status-indicator');
  const listingsCountEl = document.getElementById('listings-count');
  const scoredCountEl = document.getElementById('scored-count');
  const vinInput = document.getElementById('vin-input');
  const vinBtn = document.getElementById('vin-decode-btn');
  const vinResult = document.getElementById('vin-result');
  const openPanelBtn = document.getElementById('open-panel-btn');

  // Check backend health
  try {
    const health = await chrome.runtime.sendMessage({ action: 'HEALTH_CHECK' });
    if (health && health.status === 'ok') {
      statusEl.textContent = 'Online';
      statusEl.className = 'popup__status popup__status--online';
    } else {
      throw new Error('Backend not ok');
    }
  } catch {
    statusEl.textContent = 'Offline';
    statusEl.className = 'popup__status popup__status--offline';
  }

  // Get current tab's listing status
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) {
      const status = await chrome.runtime.sendMessage({
        action: 'GET_LISTING_STATUS',
        data: { tabId: tab.id },
      });
      if (status) {
        listingsCountEl.textContent = status.count || 0;
        scoredCountEl.textContent = status.scored || 0;
      }
    }
  } catch {
    // Tab query might fail - that's fine
  }

  // VIN Decode
  vinBtn.addEventListener('click', async () => {
    const vin = vinInput.value.trim().toUpperCase();
    if (vin.length !== 17) {
      vinResult.hidden = false;
      vinResult.textContent = 'VIN must be 17 characters';
      vinResult.style.color = '#dc2626';
      return;
    }

    vinBtn.disabled = true;
    vinBtn.textContent = '...';
    vinResult.hidden = false;
    vinResult.textContent = 'Decoding...';
    vinResult.style.color = '';

    try {
      const data = await chrome.runtime.sendMessage({
        action: 'DECODE_VIN',
        data: { vin },
      });

      if (data.error) throw new Error(data.error);

      vinResult.textContent = '';
      vinResult.style.color = '';
      const fields = [
        ['Year', data.year],
        ['Make', data.make],
        ['Model', data.model],
        ['Trim', data.trim],
        ['Engine', `${data.engine_cylinders || '?'}cyl ${data.engine_displacement || '?'}L ${data.fuel_type || ''}`],
        ['Drive', data.drive_type],
        ['GVWR', data.gvwr],
        ['Plant', `${data.plant_city || '?'}, ${data.plant_country || '?'}`],
      ];
      for (const [label, value] of fields) {
        const row = document.createElement('div');
        const labelSpan = document.createElement('span');
        labelSpan.className = 'label';
        labelSpan.textContent = label + ':';
        const valueSpan = document.createElement('span');
        valueSpan.className = 'value';
        valueSpan.textContent = ' ' + (value || 'N/A');
        row.appendChild(labelSpan);
        row.appendChild(valueSpan);
        vinResult.appendChild(row);
      }

      // Also store for side panel
      await chrome.storage.local.set({ lastVinDecode: data });
    } catch (err) {
      vinResult.textContent = `Error: ${err.message}`;
      vinResult.style.color = '#dc2626';
    }

    vinBtn.disabled = false;
    vinBtn.textContent = 'Decode';
  });

  // Enter key triggers decode
  vinInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') vinBtn.click();
  });

  // Open side panel
  openPanelBtn.addEventListener('click', async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) {
      await chrome.sidePanel.open({ tabId: tab.id });
    }
    window.close();
  });
});
