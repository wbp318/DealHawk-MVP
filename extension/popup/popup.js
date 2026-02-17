document.addEventListener('DOMContentLoaded', async () => {
  const statusEl = document.getElementById('status-indicator');
  const listingsCountEl = document.getElementById('listings-count');
  const scoredCountEl = document.getElementById('scored-count');
  const vinInput = document.getElementById('vin-input');
  const vinBtn = document.getElementById('vin-decode-btn');
  const vinResult = document.getElementById('vin-result');
  const openPanelBtn = document.getElementById('open-panel-btn');

  // Auth elements
  const authLoggedOut = document.getElementById('auth-logged-out');
  const authLoggedIn = document.getElementById('auth-logged-in');
  const authError = document.getElementById('auth-error');
  const userDisplayName = document.getElementById('user-display-name');
  const loginTab = document.getElementById('auth-login-tab');
  const registerTab = document.getElementById('auth-register-tab');
  const loginForm = document.getElementById('auth-login-form');
  const registerForm = document.getElementById('auth-register-form');
  const loginBtn = document.getElementById('login-btn');
  const registerBtn = document.getElementById('register-btn');
  const logoutBtn = document.getElementById('logout-btn');

  // Subscription elements
  const tierBadge = document.getElementById('tier-badge');
  const upgradeBtn = document.getElementById('upgrade-btn');
  const manageBtn = document.getElementById('manage-btn');

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

  // Check auth state
  await checkAuthState();

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

  // --- Auth Tab Switching ---
  loginTab.addEventListener('click', () => {
    loginTab.classList.add('popup__auth-tab--active');
    registerTab.classList.remove('popup__auth-tab--active');
    loginForm.hidden = false;
    registerForm.hidden = true;
    authError.hidden = true;
  });

  registerTab.addEventListener('click', () => {
    registerTab.classList.add('popup__auth-tab--active');
    loginTab.classList.remove('popup__auth-tab--active');
    registerForm.hidden = false;
    loginForm.hidden = true;
    authError.hidden = true;
  });

  // --- Login ---
  loginBtn.addEventListener('click', async () => {
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;

    if (!email || !password) {
      showAuthError('Please enter email and password');
      return;
    }

    loginBtn.disabled = true;
    loginBtn.textContent = '...';
    authError.hidden = true;

    try {
      const result = await chrome.runtime.sendMessage({
        action: 'AUTH_LOGIN',
        data: { email, password },
      });
      if (result && result.error) {
        showAuthError('Invalid email or password');
      } else {
        await checkAuthState();
      }
    } catch (err) {
      showAuthError('Invalid email or password');
    }

    loginBtn.disabled = false;
    loginBtn.textContent = 'Log In';
  });

  // --- Register ---
  registerBtn.addEventListener('click', async () => {
    const email = document.getElementById('register-email').value.trim();
    const displayName = document.getElementById('register-name').value.trim() || null;
    const password = document.getElementById('register-password').value;

    if (!email || !password) {
      showAuthError('Please enter email and password');
      return;
    }
    if (password.length < 8) {
      showAuthError('Password must be at least 8 characters');
      return;
    }

    registerBtn.disabled = true;
    registerBtn.textContent = '...';
    authError.hidden = true;

    try {
      const result = await chrome.runtime.sendMessage({
        action: 'AUTH_REGISTER',
        data: { email, password, display_name: displayName },
      });
      if (result && result.error) {
        showAuthError('Registration failed. Email may already be in use.');
      } else {
        await checkAuthState();
      }
    } catch (err) {
      showAuthError('Registration failed. Email may already be in use.');
    }

    registerBtn.disabled = false;
    registerBtn.textContent = 'Register';
  });

  // --- Logout ---
  logoutBtn.addEventListener('click', async () => {
    await chrome.runtime.sendMessage({ action: 'AUTH_LOGOUT' });
    await checkAuthState();
  });

  // --- Upgrade to Pro ---
  upgradeBtn.addEventListener('click', async () => {
    upgradeBtn.disabled = true;
    upgradeBtn.textContent = 'Loading...';
    try {
      const result = await chrome.runtime.sendMessage({ action: 'CREATE_CHECKOUT' });
      if (result && result.checkout_url) {
        chrome.tabs.create({ url: result.checkout_url });
      } else if (result && result.error) {
        upgradeBtn.textContent = 'Error - Try Again';
      }
    } catch {
      upgradeBtn.textContent = 'Error - Try Again';
    }
    setTimeout(() => {
      upgradeBtn.disabled = false;
      upgradeBtn.textContent = 'Upgrade to Pro';
    }, 3000);
  });

  // --- Manage Subscription ---
  manageBtn.addEventListener('click', async () => {
    manageBtn.disabled = true;
    manageBtn.textContent = 'Loading...';
    try {
      const result = await chrome.runtime.sendMessage({ action: 'CREATE_PORTAL_SESSION' });
      if (result && result.portal_url) {
        chrome.tabs.create({ url: result.portal_url });
      }
    } catch {
      // Silently fail
    }
    setTimeout(() => {
      manageBtn.disabled = false;
      manageBtn.textContent = 'Manage Subscription';
    }, 2000);
  });

  // --- Auth Helpers ---
  async function checkAuthState() {
    try {
      const user = await chrome.runtime.sendMessage({ action: 'AUTH_GET_ME' });
      if (user && user.email && !user.error) {
        authLoggedIn.hidden = false;
        authLoggedOut.hidden = true;
        userDisplayName.textContent = user.display_name || user.email;

        // Show subscription tier
        const isPro = user.subscription_tier === 'pro';
        tierBadge.textContent = isPro ? 'Pro' : 'Free';
        tierBadge.className = isPro ? 'popup__tier popup__tier--pro' : 'popup__tier popup__tier--free';
        upgradeBtn.hidden = isPro;
        manageBtn.hidden = !isPro;
      } else {
        showLoggedOut();
      }
    } catch {
      showLoggedOut();
    }
  }

  function showLoggedOut() {
    authLoggedIn.hidden = true;
    authLoggedOut.hidden = false;
  }

  function showAuthError(msg) {
    authError.hidden = false;
    authError.textContent = msg;
  }

  // --- VIN Decode ---
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
      vinResult.textContent = 'VIN decode failed. Check the VIN and try again.';
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
