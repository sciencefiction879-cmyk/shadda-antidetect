let allProfiles = [];
let allUserAgents = [];
let allGithubAccounts = [];
let activeFilter = "all";
let _popupShownThisSession = false;  // so the periodic ad refresh never re-opens the popup
let _latestUpdate = null;
let _updateInstalling = false;

// Auto-update notifications: default ON, user can turn off. Stored per machine in localStorage.
function isAutoUpdateEnabled() {
  try {
    return localStorage.getItem("autoUpdateEnabled") !== "false";
  } catch (e) {
    return true;
  }
}
function setAutoUpdateEnabled(on) {
  try {
    localStorage.setItem("autoUpdateEnabled", on ? "true" : "false");
  } catch (e) {}
}

document.addEventListener("DOMContentLoaded", async () => {
  // Native desktop app experience: disable default browser context menu & inspect shortcuts
  window.addEventListener("contextmenu", (e) => {
    if (e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA") {
      e.preventDefault();
    }
  });

  window.addEventListener("keydown", (e) => {
    if (
      e.key === "F12" ||
      (e.ctrlKey && e.shiftKey && (e.key === "I" || e.key === "i" || e.key === "J" || e.key === "j")) ||
      (e.ctrlKey && (e.key === "U" || e.key === "u"))
    ) {
      e.preventDefault();
    }
  });

  await loadUserAgents();
  await loadGithubAccounts();
  await loadCountryCatalog();
  await loadProfiles();
  await loadAds();
  setupEventListeners();
  initBuiltInUpdater();
  initDonationFeature();
  await CloudSyncManager.init();
  await AuthManager.init();

  // ── Admin detection: show Edit Wallets button only when admin panel is running ──
  detectAdminMode();

  // Auto-update toggle: reflect saved state and wire the button.
  initAutoUpdateToggle();

  // Responsive real-time profile polling: 1.2s when any profile is running, 3s when idle
  let _pollTimer = null;
  function scheduleNextProfilePoll() {
    clearTimeout(_pollTimer);
    const hasRunning = allProfiles && allProfiles.some(p => p.isRunning);
    const delay = hasRunning ? 1200 : 3000;
    _pollTimer = setTimeout(async () => {
      await loadProfiles();
      scheduleNextProfilePoll();
    }, delay);
  }
  window.scheduleNextProfilePoll = scheduleNextProfilePoll;
  scheduleNextProfilePoll();

  // Re-fetch ads/updates every 15 seconds so broadcasts reach users without a restart.
  setInterval(loadAds, 15 * 1000);
  window.addEventListener('focus', loadAds);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) loadAds();
  });
});

function initAutoUpdateToggle() {
  const btn = document.getElementById("btnAutoUpdateToggle");
  const state = document.getElementById("autoUpdateState");
  if (!btn || !state) return;

  function paint() {
    const on = isAutoUpdateEnabled();
    state.textContent = on ? "ON" : "OFF";
    btn.style.color = on ? "#10b981" : "var(--text-muted)";
    btn.style.background = on ? "rgba(16, 185, 129, 0.1)" : "rgba(148, 163, 184, 0.08)";
    btn.style.borderColor = on ? "rgba(16, 185, 129, 0.3)" : "var(--border-color)";
    btn.title = on
      ? "Automatic update notifications are ON. Click to turn off."
      : "Automatic update notifications are OFF. Critical (mandatory) updates are still shown. Click to turn on.";
  }

  btn.addEventListener("click", () => {
    setAutoUpdateEnabled(!isAutoUpdateEnabled());
    paint();
    loadAds();  // apply immediately (show or hide the optional update bar)
  });

  paint();
}

// ==========================================
// USER AGENTS
// ==========================================
async function loadUserAgents() {
  try {
    const res = await fetch("/api/user-agents");
    allUserAgents = await res.json();
    populateUaSelect();
  } catch (err) {
    console.error("Failed to load user agents:", err);
  }
}

function populateUaSelect() {
  const select = document.getElementById("formUserAgentSelect");
  select.innerHTML = "";

  const categories = {};
  allUserAgents.forEach(item => {
    const cat = item.category || "General";
    if (!categories[cat]) categories[cat] = [];
    categories[cat].push(item);
  });

  Object.keys(categories).forEach(cat => {
    const group = document.createElement("optgroup");
    group.label = cat;
    categories[cat].forEach(ua => {
      const opt = document.createElement("option");
      opt.value = ua.id;
      opt.textContent = ua.name;
      group.appendChild(opt);
    });
    select.appendChild(group);
  });

  const customOpt = document.createElement("option");
  customOpt.value = "custom";
  customOpt.textContent = "✏️ Custom User-Agent (Paste your own)";
  select.appendChild(customOpt);
}

// ==========================================
// GITHUB ACCOUNTS
// ==========================================
async function loadGithubAccounts() {
  try {
    const res = await fetch("/api/github-accounts");
    allGithubAccounts = await res.json();
    populateGithubAccountSelect();
    renderGithubAccountsList();
  } catch (err) {
    console.error("Failed to load GitHub accounts:", err);
  }
}

function populateGithubAccountSelect() {
  const select = document.getElementById("formGithubAccountSelect");
  if (!select) return;
  select.innerHTML = "";

  if (allGithubAccounts.length === 0) {
    const opt = document.createElement("option");
    opt.value = "default";
    opt.textContent = "⚠️ No GitHub account connected (Click + to connect)";
    select.appendChild(opt);
    return;
  }

  // Default option
  const defAcc = allGithubAccounts.find(a => a.is_default) || allGithubAccounts[0];
  const defOpt = document.createElement("option");
  defOpt.value = "default";
  defOpt.textContent = `★ Default Account (@${defAcc.username}${defAcc.label ? ' - ' + defAcc.label : ''})`;
  select.appendChild(defOpt);

  allGithubAccounts.forEach(acc => {
    const opt = document.createElement("option");
    opt.value = acc.id;
    opt.textContent = `@${acc.username} (${acc.label || acc.name || 'Account'}) [${acc.repo}]`;
    select.appendChild(opt);
  });
}

function renderGithubAccountsList() {
  const container = document.getElementById("githubAccountsList");
  if (!container) return;

  if (allGithubAccounts.length === 0) {
    container.innerHTML = `
      <div style="padding: 16px; background: var(--bg-card); border-radius: var(--radius-md); text-align: center; color: var(--text-muted); font-size: 13px;">
        No GitHub accounts connected yet. Add your first token below.
      </div>
    `;
    return;
  }

  container.innerHTML = allGithubAccounts.map(acc => `
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; background: var(--bg-card); border: 1px solid ${acc.is_default ? 'var(--accent-cyan)' : 'var(--border-color)'}; border-radius: var(--radius-md);">
      <div style="display: flex; align-items: center; gap: 12px;">
        <img src="${acc.avatar_url || 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png'}" width="36" height="36" style="border-radius: 50%; border: 1px solid var(--border-highlight);" alt="avatar">
        <div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <strong style="font-size: 14px; color: var(--text-primary);">@${acc.username}</strong>
            ${acc.is_default ? '<span style="background: rgba(14, 165, 233, 0.2); color: var(--accent-cyan); font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; text-transform: uppercase;">Default</span>' : ''}
          </div>
          <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">
            ${acc.label ? `<span>${acc.label} &bull; </span>` : ''}
            <span style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text-muted);">${acc.repo}</span>
            <span style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text-muted); margin-left: 6px;">(${acc.token_masked})</span>
          </div>
        </div>
      </div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <button class="btn-text" style="font-size: 11px; color: var(--text-secondary); background: rgba(255,255,255,0.06); padding: 4px 8px; border-radius: 4px; border: 1px solid var(--border-color);" onclick="testGithubAccount('${acc.id}', '${acc.username}')" title="Live test if this token is valid and has proper permissions">
          ⚡ Test Token
        </button>
        ${!acc.is_default ? `
          <button class="btn-text" style="font-size: 12px; color: var(--accent-cyan); padding: 4px 8px;" onclick="setDefaultGithubAccount('${acc.id}')">
            Set Default
          </button>
        ` : ''}
        <button class="btn-icon danger" title="Remove Account" onclick="deleteGithubAccount('${acc.id}', '${acc.username}')">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
        </button>
      </div>
    </div>
  `).join("");
}

function openGithubModal() {
  document.getElementById("githubModal").style.display = "flex";
  renderGithubAccountsList();
}

function closeGithubModal() {
  document.getElementById("githubModal").style.display = "none";
}

async function testGithubAccount(id, username) {
  try {
    const res = await fetch(`/api/github-accounts/${id}/verify`);
    if (!res.ok) {
      const txt = await res.text();
      alert(`Server error (${res.status}): ${txt}`);
      return;
    }
    const data = await res.json();
    if (data.success) {
      alert(`✅ GitHub Token Valid!\n\nAccount: @${data.username}\nScopes: ${data.scopes || 'Full Repo & Workflow'}\nStatus: Ready to launch cloud proxies!`);
    } else {
      alert(`❌ GitHub Token Error for @${username}:\n\n${data.error}\n\n👉 Solution: GitHub par jaakar naya Personal Access Token generate karein jisme 'repo' aur 'workflow' dono checkboxes ticked hon, aur yahan naya token add karein.`);
    }
  } catch (err) {
    alert(`Failed to test token: ${err.message}`);
  }
}

async function setDefaultGithubAccount(id) {
  try {
    await fetch(`/api/github-accounts/${id}/set-default`, { method: "POST" });
    await loadGithubAccounts();
  } catch (e) {
    alert("Failed to set default account: " + e.message);
  }
}

async function deleteGithubAccount(id, username) {
  if (!confirm(`Are you sure you want to remove GitHub account @${username}?`)) return;
  try {
    await fetch(`/api/github-accounts/${id}`, { method: "DELETE" });
    await loadGithubAccounts();
  } catch (e) {
    alert("Failed to remove account: " + e.message);
  }
}

// ==========================================
// PROFILES
// ==========================================
async function loadProfiles() {
  try {
    const res = await fetch("/api/profiles");
    allProfiles = await res.json();
    renderProfiles();
    updateCounts();
  } catch (err) {
    console.error("Failed to load profiles:", err);
  }
}

function updateCounts() {
  document.getElementById("countAll").textContent = allProfiles.length;
  document.getElementById("countRunning").textContent = allProfiles.filter(p => p.isRunning).length;
  document.getElementById("countMobile").textContent = allProfiles.filter(p => p.isMobile).length;
  const countCountryEl = document.getElementById("countCountry");
  if (countCountryEl) countCountryEl.textContent = allProfiles.filter(p => p.proxyType === "country").length;
  document.getElementById("countGithub").textContent = allProfiles.filter(p => p.proxyType === "github").length;
}

function renderProfiles() {
  const grid = document.getElementById("profilesGrid");
  const empty = document.getElementById("emptyState");
  const search = document.getElementById("searchInput").value.toLowerCase().trim();

  let filtered = allProfiles.filter(p => {
    // Filter pill
    if (activeFilter === "running" && !p.isRunning) return false;
    if (activeFilter === "mobile" && !p.isMobile) return false;
    if (activeFilter === "country" && p.proxyType !== "country") return false;
    if (activeFilter === "github" && p.proxyType !== "github") return false;

    // Search
    if (search) {
      const matchName = (p.name || "").toLowerCase().includes(search);
      const matchNotes = (p.notes || "").toLowerCase().includes(search);
      const matchUa = (p.userAgent || "").toLowerCase().includes(search);
      const matchCountry = (p.countryName || "").toLowerCase().includes(search);
      if (!matchName && !matchNotes && !matchUa && !matchCountry) return false;
    }
    return true;
  });

  if (filtered.length === 0) {
    grid.innerHTML = "";
    empty.style.display = "block";
    return;
  }

  empty.style.display = "none";

  const headerHtml = `
    <div class="profiles-header">
      <div class="col-serial">#</div>
      <div class="col-name">Profile</div>
      <div class="col-device">Device</div>
      <div class="col-proxy">Proxy</div>
      <div class="col-tz">Timezone</div>
      <div class="col-status">Status</div>
      <div class="col-actions">Actions</div>
    </div>`;

  const rowsHtml = filtered.map((p, idx) => {
    const uaObj = allUserAgents.find(u => u.id === p.userAgentId);
    const uaName = uaObj ? uaObj.name : (p.isMobile ? "📱 Custom Mobile" : "💻 Custom Desktop");
    const isRunning = p.isRunning || false;
    const color = p.color || "#0ea5e9";
    const serial = idx + 1;

    let proxyHtml = "";
    const ksBadge = (p.proxyType !== 'none' && p.killSwitch !== false)
      ? `<span class="cell-ks" style="font-size: 9.5px; color: #f87171; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); padding: 1px 5px; border-radius: 4px; font-weight: 700; margin-left: 5px;" title="🛡️ Strict Kill Switch Active: Internet strictly blocked if proxy fails">🛡️ KS</span>`
      : '';

    if (p.proxyType === "country") {
      const flag = p.countryFlag || "🌍";
      const cname = p.countryName || p.countryCode || "Country";
      const isLocked = Boolean(p.countryProxy || p.customProxy);
      proxyHtml = `<span class="cell-proxy proxy-custom" style="background: rgba(16, 185, 129, 0.12); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3);" title="${cname} Proxy: ${p.countryProxy || 'Auto-assign'}${isLocked ? ' (🔒 Locked)' : ''}">${flag} ${cname}${isLocked ? ' 🔒' : ''}</span>${ksBadge}`;
    } else if (p.proxyType === "github") {
      let ghLabel = "Azure IP";
      if (p.githubAccountId && p.githubAccountId !== "default") {
        const ghAcc = allGithubAccounts.find(a => a.id === p.githubAccountId);
        if (ghAcc) ghLabel = `@${ghAcc.username}`;
      }
      proxyHtml = `<span class="cell-proxy proxy-github" title="GitHub Cloud Runner: ${ghLabel}">☁️ ${ghLabel}</span>${ksBadge}`;
    } else if (p.proxyType === "custom") {
      proxyHtml = `<span class="cell-proxy proxy-custom" title="${p.customProxy || 'Custom Proxy'}">🔒 Custom</span>${ksBadge}`;
    } else {
      proxyHtml = `<span class="cell-proxy proxy-direct" title="Direct Connection (no proxy)">🌐 Direct</span>`;
    }

    const statusHtml = isRunning
      ? `<span class="cell-status status-on" title="${p.allocatedIp ? 'IP: ' + p.allocatedIp : 'Running'}"><span class="pulse-dot"></span>Running</span>`
      : `<span class="cell-status status-off">Idle</span>`;

    return `
      <div class="profile-card profile-row ${isRunning ? 'active-running' : ''}" data-id="${p.id}">
        <div class="col-serial">
          <span class="row-serial" style="border-color: ${color}; color: ${color};">${serial}</span>
        </div>
        <div class="col-name">
          <span class="row-dot" style="background:${color};"></span>
          <div class="row-name-text">
            <div class="profile-name" title="${p.name || ''}">
              ${p.name || 'Untitled'}
              ${p.automation && p.automation.enabled ? `
                <span class="badge-auto" style="font-size: 10px; font-weight: 700; background: rgba(14, 165, 233, 0.18); color: #38bdf8; border: 1px solid rgba(14, 165, 233, 0.35); padding: 1px 6px; border-radius: 4px; margin-left: 6px; display: inline-flex; align-items: center; gap: 3px;" title="GitHub Actions Automation Enabled">
                  🤖 ${(p.automation.platforms || ['YouTube']).map(x => x.toUpperCase()).join('+')}
                </span>
              ` : ''}
            </div>
            <div class="profile-notes" title="${p.notes || ''}">${p.notes || 'No notes'}</div>
          </div>
        </div>
        <div class="col-device"><span class="cell-device badge-ua" title="${uaName}">${uaName}</span></div>
        <div class="col-proxy">${proxyHtml}</div>
        <div class="col-tz"><span class="cell-tz" title="${p.timezone || 'America/New_York'}">🕒 ${p.timezone || 'America/New_York'}</span></div>
        <div class="col-status">${statusHtml}</div>
        <div class="col-actions">
          <div class="profile-actions">
            ${isRunning ? `
              <button class="btn-stop btn-row" onclick="stopProfile('${p.id}')" title="Stop this browser">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"></rect></svg>
                <span>Stop</span>
              </button>
            ` : `
              <button class="btn-launch btn-row" onclick="launchProfile('${p.id}')" title="Launch this profile">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                <span>Launch</span>
              </button>
              ${p.proxyType === 'github' ? `
                <button class="btn-icon btn-direct" onclick="launchProfile('${p.id}', null, true)" title="Instant launch without waiting for the GitHub Cloud Runner">⚡</button>
              ` : ''}
              <button class="btn-test btn-icon" onclick="testProfile('${p.id}')" title="Test this profile's anti-detect fingerprint on CreepJS">🧪</button>
            `}
            <button class="btn-icon" title="Edit profile & proxy settings" onclick="openEditModal('${p.id}')">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
            </button>
            <button class="btn-icon" title="Open storage folder" onclick="openFolder('${p.id}')">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
            </button>
            <button class="btn-icon danger" title="Delete profile" onclick="deleteProfile('${p.id}')">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join("");

  grid.innerHTML = headerHtml + rowsHtml;
}

// Launch Profile
async function launchProfile(id, urlOverride, forceDirect, withAutomation) {
  const p = allProfiles.find(x => x.id === id);

  // If automation is enabled on this profile and launch choice hasn't been made yet:
  if (p && p.automation && p.automation.enabled && withAutomation === undefined && !urlOverride) {
    const modal = document.getElementById("launchChoiceModal");
    const sub = document.getElementById("launchChoiceSubtitle");
    const title = document.getElementById("launchChoiceTitle");
    const plats = (p.automation.platforms || ['youtube']).map(x => x.toUpperCase()).join(', ');
    if (title) title.textContent = `🚀 Launch "${p.name || 'Profile'}"`;
    if (sub) sub.innerHTML = `This profile has <strong>GitHub Actions automation</strong> enabled for <strong>${plats}</strong>.<br><br>How would you like to launch this session?`;

    const btnWith = document.getElementById("btnLaunchWithAuto");
    const btnWithout = document.getElementById("btnLaunchWithoutAuto");
    const btnClose = document.getElementById("launchChoiceCloseBtn");

    if (btnWith) {
      btnWith.onclick = () => {
        modal.style.display = "none";
        launchProfile(id, urlOverride, forceDirect, true);
      };
    }
    if (btnWithout) {
      btnWithout.onclick = () => {
        modal.style.display = "none";
        launchProfile(id, urlOverride, forceDirect, false);
      };
    }
    if (btnClose) {
      btnClose.onclick = () => {
        modal.style.display = "none";
      };
    }
    modal.style.display = "flex";
    return;
  }

  const card = document.querySelector(`.profile-card[data-id="${id}"]`);
  const btn = card ? card.querySelector(".btn-launch") : null;
  const testBtn = card ? card.querySelector(".btn-test") : null;

  if (!forceDirect && p && p.proxyType === "github" && (!allGithubAccounts || allGithubAccounts.length === 0)) {
    if (p.killSwitch !== false) {
      alert("🛡️ Kill Switch Blocked Launch:\n\nGitHub Cloud Runner is not configured, and Kill Switch is active.\nDirect connection is strictly blocked to keep your real IP safe.\n\nPlease connect a GitHub account or assign a working Country Proxy.");
      return;
    }
    const wantDirect = confirm("⚠️ GitHub Account Connected Nahi Hai!\n\nIs profile par 'GitHub Cloud Runner' proxy set hai lekin koi GitHub account connect nahi hai.\n\n👉 Kya aap is profile ko Direct Connection (with full Anti-Detect stealth) ke sath abhi kholna chahte hain?");
    if (wantDirect) {
      return launchProfile(id, urlOverride, true, withAutomation);
    }
    return;
  }

  if (btn) {
    if (withAutomation) {
      btn.innerHTML = `<span class="pulse-dot"></span><span>Connecting GitHub Actions...</span>`;
    } else if (urlOverride) {
      btn.innerHTML = `<span class="pulse-dot"></span><span>Starting CreepJS...</span>`;
    } else if (!forceDirect && p && p.proxyType === "github") {
      btn.innerHTML = `<span class="pulse-dot"></span><span>Connecting Azure IP...</span>`;
    } else {
      btn.innerHTML = `<span class="pulse-dot"></span><span>Starting...</span>`;
    }
    btn.disabled = true;
  }
  if (testBtn) testBtn.disabled = true;

  try {
    const payload = {};
    if (urlOverride) payload.url = urlOverride;
    if (forceDirect) payload.direct = true;
    if (withAutomation !== undefined) payload.withAutomation = withAutomation;

    const res = await fetch(`/api/profiles/${id}/launch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    const errMsg = data.error || (data.success === false ? data.message : null);
    if (errMsg) {
      const isKillSwitch = errMsg.includes("Kill Switch") || (p && p.killSwitch !== false && p.proxyType !== 'none');
      if (isKillSwitch) {
        if (p && p.proxyType === 'country') {
          const cName = p.countryName || p.countryCode || "Country";
          const wantReassign = confirm(
            `${errMsg}\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n👉 Kya aap ${cName} ka naya VERIFIED LIVE proxy auto-assign karke browser launch karna chahte hain?\n\n(Click 'OK' to auto-assign a working proxy & launch, or 'Cancel' to keep safe & closed)`
          );
          if (wantReassign) {
            if (btn) btn.innerHTML = `<span class="pulse-dot"></span><span>Finding ${cName} Proxy...</span>`;
            try {
              const resReassign = await fetch(`/api/profiles/${id}/reassign-country-proxy`, { method: "POST" });
              const dataReassign = await resReassign.json();
              if (dataReassign.success) {
                await loadProfiles();
                CloudSyncManager.pushToCloud();
                return launchProfile(id, urlOverride);
              } else {
                alert(`⚠️ ${dataReassign.error || 'Live proxy nahi mila'}\n\nPlease header me '🌍 Country Proxies' par click karke koi dusra verified proxy select kijiye.`);
              }
            } catch (errRe) {
              alert("Reassign error: " + errRe.message);
            }
          }
        } else {
          alert(errMsg.includes("Kill Switch") ? errMsg : `🛡️ Kill Switch Protected Launch:\n\n${errMsg}\n\nDirect network connection was blocked to ensure your real IP is never leaked.`);
        }
      } else if (!forceDirect && p && p.killSwitch === false && (p.proxyType === "github" || errMsg.includes("GitHub"))) {
        const wantDirect = confirm(
          `⚠️ Cloud Proxy Note:\n${errMsg}\n\n👉 Kya aap is profile ko Direct Anti-Detect mode me turant launch krna chahte hain?\n(Full Anti-Detect protection, WebGL, Canvas noise, Nexus/Android fingerprint 100% active rahega!)`
        );
        if (wantDirect) {
          return launchProfile(id, urlOverride, true);
        }
      } else {
        alert(`Launch failed: ${errMsg}`);
      }
    }
  } catch (err) {
    if (!forceDirect && p && p.killSwitch === false && p.proxyType === "github") {
      const wantDirect = confirm(
        `⚠️ Cloud Proxy Error: ${err.message}\n\n👉 Kya aap Direct Anti-Detect mode me browser kholna chahte hain?\n(Instant launch, full stealth)`
      );
      if (wantDirect) {
        return launchProfile(id, urlOverride, true);
      }
    } else {
      alert(`Launch error: ${err.message}`);
    }
  } finally {
    await loadProfiles();
  }
}

function testProfile(id) {
  launchProfile(id, "https://creepjs.org/checker#scan");
}

// Stop Profile
async function stopProfile(id) {
  try {
    await fetch(`/api/profiles/${id}/stop`, { method: "POST" });
  } catch (err) {
    console.error("Stop error:", err);
  } finally {
    await loadProfiles();
  }
}

// Open Profile Folder
async function openFolder(id) {
  try {
    await fetch(`/api/profiles/${id}/open-folder`, { method: "POST" });
  } catch (e) {}
}

// Delete Profile
async function deleteProfile(id) {
  const p = allProfiles.find(x => x.id === id);
  const name = p ? p.name : "this profile";
  if (!confirm(`Are you sure you want to delete "${name}"?`)) return;

  try {
    await fetch(`/api/profiles/${id}`, { method: "DELETE" });
    await loadProfiles();
    CloudSyncManager.pushToCloud();
  } catch (err) {
    alert(`Delete failed: ${err.message}`);
  }
}

function setTimezoneValue(tz) {
  if (!tz) return;
  const sel = document.getElementById("formTimezone");
  if (!sel) return;
  let found = false;
  for (let i = 0; i < sel.options.length; i++) {
    if (sel.options[i].value === tz) {
      sel.selectedIndex = i;
      found = true;
      break;
    }
  }
  if (!found) {
    const opt = document.createElement("option");
    opt.value = tz;
    opt.textContent = `📍 ${tz} (Proxy Timezone)`;
    sel.appendChild(opt);
    sel.value = tz;
  }
}
window.setTimezoneValue = setTimezoneValue;

// Modal handling
function openCreateModal() {
  document.getElementById("modalTitle").textContent = "Create New Profile";
  document.getElementById("formProfileId").value = "";
  document.getElementById("formName").value = "";
  document.getElementById("formNotes").value = "";
  document.getElementById("formColor").value = getRandomColor();
  document.getElementById("formUserAgentSelect").value = "win_chrome";
  document.getElementById("formCustomUaGroup").style.display = "none";
  // Country proxy reset
  const cpGroup = document.getElementById("formCountryProxyGroup");
  if (cpGroup) cpGroup.style.display = "none";
  const cpInput = document.getElementById("formCountryProxyInput");
  if (cpInput) cpInput.value = "";
  const cpSelect = document.getElementById("formCountrySelect");
  if (cpSelect) cpSelect.value = "PK";

  // Check if GitHub account exists, otherwise default to Direct Connection
  const hasGh = (allGithubAccounts && allGithubAccounts.length > 0);
  if (hasGh) {
    document.querySelector('input[name="proxyType"][value="github"]').checked = true;
    document.getElementById("formGithubAccountGroup").style.display = "block";
    document.getElementById("formGithubAccountSelect").value = "default";
  } else {
    document.querySelector('input[name="proxyType"][value="none"]').checked = true;
    document.getElementById("formGithubAccountGroup").style.display = "none";
  }
  document.getElementById("formCustomProxyGroup").style.display = "none";
  document.getElementById("formCustomProxy").value = "";
  const qp = document.getElementById("formProxyQuickPaste");
  if (qp) qp.value = "";
  const ph = document.getElementById("formProxyHost");
  if (ph) ph.value = "";
  const pp = document.getElementById("formProxyPort");
  if (pp) pp.value = "";
  const pu = document.getElementById("formProxyUser");
  if (pu) pu.value = "";
  const ppw = document.getElementById("formProxyPass");
  if (ppw) ppw.value = "";
  const diagCard = document.getElementById("proxyDiagnosticCard");
  if (diagCard) diagCard.style.display = "none";
  const badge = document.getElementById("proxyTestStatusBadge");
  if (badge) badge.style.display = "none";
  setTimezoneValue("America/New_York");
  document.getElementById("formStartUrl").value = "https://studio.youtube.com";
  const ksCb = document.getElementById("formKillSwitch");
  if (ksCb) ksCb.checked = true;

  const autoGroup = document.getElementById("formAutoLaunchGroup");
  if (autoGroup) autoGroup.style.display = "block";
  const autoCb = document.getElementById("formAutoLaunch");
  if (autoCb) autoCb.checked = true;

  // Automation settings reset
  const autoOffRadio = document.querySelector('input[name="profileAutomationEnabled"][value="off"]');
  if (autoOffRadio) autoOffRadio.checked = true;
  const autoPlatformsGrp = document.getElementById("formAutomationPlatformsGroup");
  if (autoPlatformsGrp) autoPlatformsGrp.style.display = "none";
  document.querySelectorAll('input[name="autoPlatform"]').forEach(chk => {
    chk.checked = (chk.value === 'youtube');
  });
  const chkOther = document.getElementById("chkAutoPlatformOther");
  if (chkOther) chkOther.checked = false;
  const customUrlGrp = document.getElementById("formAutoCustomUrlGroup");
  if (customUrlGrp) customUrlGrp.style.display = "none";
  const customUrlInp = document.getElementById("formAutoCustomUrl");
  if (customUrlInp) customUrlInp.value = "";

  const saveBtn = document.getElementById("btnSaveProfile");
  if (saveBtn) saveBtn.textContent = "+ Create Profile";

  document.getElementById("profileModal").style.display = "flex";
}

function openEditModal(id) {
  const p = allProfiles.find(x => x.id === id);
  if (!p) return;

  const autoGroup = document.getElementById("formAutoLaunchGroup");
  if (autoGroup) autoGroup.style.display = "none";

  document.getElementById("modalTitle").textContent = `✏️ Edit Profile: ${p.name || ''}`;
  const saveBtn = document.getElementById("btnSaveProfile");
  if (saveBtn) saveBtn.textContent = "💾 Save Changes";

  document.getElementById("formProfileId").value = p.id;
  document.getElementById("formName").value = p.name || "";
  document.getElementById("formNotes").value = p.notes || "";
  document.getElementById("formColor").value = p.color || "#0ea5e9";
  
  const select = document.getElementById("formUserAgentSelect");
  if (p.userAgentId) {
    select.value = p.userAgentId;
  }
  if (p.userAgentId === "custom") {
    document.getElementById("formCustomUaGroup").style.display = "flex";
    document.getElementById("formCustomUaInput").value = p.userAgent || "";
  } else {
    document.getElementById("formCustomUaGroup").style.display = "none";
  }

  const proxyRadio = document.querySelector(`input[name="proxyType"][value="${p.proxyType || 'none'}"]`);
  if (proxyRadio) proxyRadio.checked = true;

  const cpGroup = document.getElementById("formCountryProxyGroup");
  if (p.proxyType === "country") {
    if (cpGroup) cpGroup.style.display = "block";
    const cpSelect = document.getElementById("formCountrySelect");
    if (cpSelect && p.countryCode) cpSelect.value = p.countryCode;
    const cpInput = document.getElementById("formCountryProxyInput");
    if (cpInput) cpInput.value = p.countryProxy || p.customProxy || "";
    loadCountryProxiesInForm(p.countryCode || "PK");
  } else {
    if (cpGroup) cpGroup.style.display = "none";
  }

  if (p.proxyType === "github") {
    document.getElementById("formGithubAccountGroup").style.display = "block";
    document.getElementById("formGithubAccountSelect").value = p.githubAccountId || "default";
  } else {
    document.getElementById("formGithubAccountGroup").style.display = "none";
  }

  const diagCard = document.getElementById("proxyDiagnosticCard");
  if (diagCard) diagCard.style.display = "none";
  const badge = document.getElementById("proxyTestStatusBadge");
  if (badge) badge.style.display = "none";

  if (p.proxyType === "custom") {
    document.getElementById("formCustomProxyGroup").style.display = "block";
    document.getElementById("formCustomProxy").value = p.customProxy || "";
    const parsed = parseProxyClientSide(p.customProxy || "");
    if (parsed) {
      applyParsedProxyToInputs(parsed);
      const qp = document.getElementById("formProxyQuickPaste");
      if (qp) qp.value = p.customProxy || "";
    }
  } else {
    document.getElementById("formCustomProxyGroup").style.display = "none";
  }

  // Populate Automation Settings
  const autoCfg = p.automation || {};
  const isAutoOn = !!autoCfg.enabled;
  const autoRadio = document.querySelector(`input[name="profileAutomationEnabled"][value="${isAutoOn ? 'on' : 'off'}"]`);
  if (autoRadio) autoRadio.checked = true;
  const autoPlatformsGrp = document.getElementById("formAutomationPlatformsGroup");
  if (autoPlatformsGrp) autoPlatformsGrp.style.display = isAutoOn ? "block" : "none";
  const selectedPlats = autoCfg.platforms || (isAutoOn ? ['youtube'] : []);
  document.querySelectorAll('input[name="autoPlatform"]').forEach(chk => {
    chk.checked = selectedPlats.includes(chk.value);
  });
  const chkOther = document.getElementById("chkAutoPlatformOther");
  if (chkOther) chkOther.checked = selectedPlats.includes('other');
  const customUrlGrp = document.getElementById("formAutoCustomUrlGroup");
  if (customUrlGrp) customUrlGrp.style.display = selectedPlats.includes('other') ? "block" : "none";
  const customUrlInp = document.getElementById("formAutoCustomUrl");
  if (customUrlInp) customUrlInp.value = autoCfg.customUrl || "";

  setTimezoneValue(p.timezone || "America/New_York");
  document.getElementById("formStartUrl").value = p.startUrl || "https://studio.youtube.com";
  const ksCb = document.getElementById("formKillSwitch");
  if (ksCb) ksCb.checked = (p.killSwitch !== false);
  document.getElementById("profileModal").style.display = "flex";
}

// Ensure global accessibility for inline onclick handlers
window.openEditModal = openEditModal;
window.openCreateModal = openCreateModal;
window.testProfile = testProfile;
window.launchProfile = launchProfile;
window.stopProfile = stopProfile;
window.openFolder = openFolder;
window.deleteProfile = deleteProfile;

function closeModal() {
  document.getElementById("profileModal").style.display = "none";
}

function getRandomColor() {
  const colors = ["#0ea5e9", "#10b981", "#ec4899", "#f59e0b", "#8b5cf6", "#f43f5e", "#06b6d4"];
  return colors[Math.floor(Math.random() * colors.length)];
}

function setupEventListeners() {
  document.getElementById("btnNewProfile").addEventListener("click", openCreateModal);
  document.getElementById("btnEmptyCreate").addEventListener("click", openCreateModal);
  document.getElementById("modalCloseBtn").addEventListener("click", closeModal);
  document.getElementById("btnCancelModal").addEventListener("click", closeModal);

  // Profile Automation Settings Toggle
  const autoRadios = document.querySelectorAll('input[name="profileAutomationEnabled"]');
  autoRadios.forEach(r => {
    r.addEventListener('change', () => {
      const isAuto = r.value === 'on';
      const grp = document.getElementById("formAutomationPlatformsGroup");
      if (grp) grp.style.display = isAuto ? "block" : "none";
    });
  });

  const chkOther = document.getElementById("chkAutoPlatformOther");
  if (chkOther) {
    chkOther.addEventListener('change', () => {
      const customGrp = document.getElementById("formAutoCustomUrlGroup");
      if (customGrp) customGrp.style.display = chkOther.checked ? "block" : "none";
    });
  }

  const launchChoiceClose = document.getElementById("launchChoiceCloseBtn");
  if (launchChoiceClose) {
    launchChoiceClose.addEventListener('click', () => {
      document.getElementById("launchChoiceModal").style.display = "none";
    });
  }

  // Cloud Sync Modal & Header button listeners
  const btnCloudSync = document.getElementById("btnCloudSync");
  if (btnCloudSync) btnCloudSync.addEventListener("click", openCloudSyncModal);

  const btnCloseCloudSyncModal = document.getElementById("btnCloseCloudSyncModal");
  if (btnCloseCloudSyncModal) btnCloseCloudSyncModal.addEventListener("click", closeCloudSyncModal);

  const cloudSyncModal = document.getElementById("cloudSyncModal");
  if (cloudSyncModal) {
    cloudSyncModal.addEventListener("click", (e) => {
      if (e.target === cloudSyncModal) closeCloudSyncModal();
    });
  }

  const btnGenRoomKey = document.getElementById("btnGenRoomKey");
  if (btnGenRoomKey) {
    btnGenRoomKey.addEventListener("click", () => {
      const randKey = "shadda-" + Math.random().toString(36).substring(2, 8);
      const input = document.getElementById("cloudSyncRoomKey");
      if (input) input.value = randKey;
    });
  }

  const btnCopyRoomKey = document.getElementById("btnCopyRoomKey");
  if (btnCopyRoomKey) {
    btnCopyRoomKey.addEventListener("click", async () => {
      const input = document.getElementById("cloudSyncRoomKey");
      if (!input || !input.value.trim()) {
        alert("Pehle Room Key enter ya generate kijiye!");
        return;
      }
      try {
        await navigator.clipboard.writeText(input.value.trim());
        btnCopyRoomKey.textContent = "✅ Copied!";
        setTimeout(() => {
          btnCopyRoomKey.textContent = "📋 Copy Key";
        }, 2000);
      } catch (e) {
        input.select();
        document.execCommand("copy");
        btnCopyRoomKey.textContent = "✅ Copied!";
        setTimeout(() => {
          btnCopyRoomKey.textContent = "📋 Copy Key";
        }, 2000);
      }
    });
  }

  const btnSaveCloudSync = document.getElementById("btnSaveCloudSync");
  if (btnSaveCloudSync) {
    btnSaveCloudSync.addEventListener("click", async () => {
      const roomKeyInput = document.getElementById("cloudSyncRoomKey");
      const urlInput = document.getElementById("cloudSyncFirebaseUrl");
      const roomKey = (roomKeyInput ? roomKeyInput.value : "").trim();
      const firebaseUrl = (urlInput && urlInput.value.trim()) ? urlInput.value.trim() : "https://user-ananlytics-default-rtdb.firebaseio.com";

      if (!roomKey) {
        alert("⚠️ Please enter a Sync Room Key (e.g. shadda-vault-491)!");
        if (roomKeyInput) roomKeyInput.focus();
        return;
      }

      btnSaveCloudSync.disabled = true;
      btnSaveCloudSync.innerHTML = `<span>⏳ Connecting...</span>`;

      try {
        await fetch("/api/cloud-sync/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            enabled: true,
            firebaseUrl: firebaseUrl,
            roomKey: roomKey
          })
        });

        CloudSyncManager.enabled = true;
        CloudSyncManager.firebaseUrl = firebaseUrl;
        CloudSyncManager.roomKey = roomKey;
        CloudSyncManager.updateUI();
        CloudSyncManager.connectSSE();

        // Check if cloud has existing profiles or if we should push local
        const base = firebaseUrl.replace(/\/+$/, "");
        const res = await fetch(`${base}/workspaces/${encodeURIComponent(roomKey)}/profiles.json`);
        const remoteData = await res.json();

        let remoteCount = 0;
        if (remoteData) {
          if (Array.isArray(remoteData)) remoteCount = remoteData.length;
          else if (typeof remoteData === "object") remoteCount = Object.keys(remoteData).length;
        }

        if (remoteCount > 0) {
          await CloudSyncManager.pullFromCloud(true);
          alert(`🎉 Live Cloud Sync Connected!\n\nRoom: ${roomKey}\nFound ${remoteCount} profiles in this cloud room and synced them to this device.`);
        } else {
          await CloudSyncManager.pushToCloud(false);
          alert(`🎉 Live Cloud Sync Connected!\n\nRoom: ${roomKey}\nUploaded your local profiles to this new room. Enter this exact same Room Key on your other laptop/PC to mirror in real-time!`);
        }
      } catch (err) {
        alert("Connection failed: " + err.message);
      } finally {
        btnSaveCloudSync.disabled = false;
        CloudSyncManager.updateUI();
      }
    });
  }

  const btnPushCloudSync = document.getElementById("btnPushCloudSync");
  if (btnPushCloudSync) {
    btnPushCloudSync.addEventListener("click", () => CloudSyncManager.pushToCloud(true));
  }

  const btnPullCloudSync = document.getElementById("btnPullCloudSync");
  if (btnPullCloudSync) {
    btnPullCloudSync.addEventListener("click", () => CloudSyncManager.pullFromCloud(false));
  }

  const btnDisconnectCloudSync = document.getElementById("btnDisconnectCloudSync");
  if (btnDisconnectCloudSync) {
    btnDisconnectCloudSync.addEventListener("click", async () => {
      if (!confirm("Are you sure you want to disconnect from Cloud Sync?\n\nYour profiles will remain safely on this device in local offline mode.")) return;
      await CloudSyncManager.disconnect();
      alert("Cloud Sync disconnected. This app is now running in local offline mode.");
    });
  }

  // Country Proxies Hub header button & modal listeners
  const btnCpHub = document.getElementById("btnCountryProxiesHub");
  if (btnCpHub) btnCpHub.addEventListener("click", () => openCountryProxiesHub("PK"));
  
  const btnCloseCpModal = document.getElementById("btnCloseCountryProxiesModal");
  if (btnCloseCpModal) btnCloseCpModal.addEventListener("click", closeCountryProxiesHub);
  
  const btnCpRefresh = document.getElementById("btnCountryHubRefresh");
  if (btnCpRefresh) btnCpRefresh.addEventListener("click", () => loadCountryHubTable(currentHubCountry, true));

  const btnCpQuickCreate = document.getElementById("btnCountryHubQuickCreate");
  if (btnCpQuickCreate) {
    btnCpQuickCreate.addEventListener("click", async () => {
      const cc = currentHubCountry;
      const cMeta = allCountryCatalog.find(c => c.code === cc) || { name: cc, timezone: 'UTC' };
      const res = await fetch(`/api/country-proxies/${cc}/best`);
      const best = await res.json();
      if (best && best.formatted) {
        quickCreateWithCountryProxy(best.formatted, cc, cMeta.name, best.timezone || cMeta.timezone);
      } else {
        alert("Please select a proxy from the table.");
      }
    });
  }

  // Country select in Profile Modal
  const formCountrySel = document.getElementById("formCountrySelect");
  if (formCountrySel) {
    formCountrySel.addEventListener("change", (e) => {
      loadCountryProxiesInForm(e.target.value);
    });
  }

  const btnAutoAssign = document.getElementById("btnAutoAssignCountryProxy");
  if (btnAutoAssign) {
    btnAutoAssign.addEventListener("click", autoAssignBestCountryProxy);
  }

  const btnRefreshCp = document.getElementById("btnRefreshCountryProxies");
  if (btnRefreshCp) {
    btnRefreshCp.addEventListener("click", () => {
      const cc = document.getElementById("formCountrySelect")?.value || "PK";
      loadCountryProxiesInForm(cc, true);
    });
  }

  const switchAllBtn = document.getElementById("btnSwitchAllDirect");
  if (switchAllBtn) {
    switchAllBtn.addEventListener("click", async () => {
      if (!confirm("⚡ Switch All Profiles to Direct Connection?\n\nSabhi profiles direct anti-detect mode me switch ho jayengi aur 'Launch' click karte hi 0.2 second me turant khulengi bina kisi GitHub token ya wait ke.")) return;
      try {
        await fetch("/api/profiles/switch-all-direct", { method: "POST" });
        await loadProfiles();
        CloudSyncManager.pushToCloud();
        alert("✅ Sabhi profiles ab Direct Connection par set ho gayi hain!\n\nAb 'Launch' dabate hi browser turant open ho jayega.");
      } catch (err) {
        alert("Failed: " + err.message);
      }
    });
  }

  // GitHub modal events
  document.getElementById("btnGithubAccounts").addEventListener("click", openGithubModal);
  document.getElementById("githubModalCloseBtn").addEventListener("click", closeGithubModal);
  document.getElementById("btnOpenGhModalFromForm").addEventListener("click", () => {
    closeModal();
    openGithubModal();
  });

  const copyBtn = document.getElementById("btnCopyGhLink");
  if (copyBtn) {
    copyBtn.addEventListener("click", () => {
      const link = "https://github.com/settings/tokens/new?description=AntiDetect-Studio-Proxy&scopes=repo,workflow";
      navigator.clipboard.writeText(link).then(() => {
        const origText = copyBtn.innerHTML;
        copyBtn.innerHTML = "✓ Link Copied!";
        copyBtn.style.color = "var(--accent-emerald)";
        setTimeout(() => {
          copyBtn.innerHTML = origText;
          copyBtn.style.color = "var(--text-primary)";
        }, 2500);
      }).catch(err => {
        prompt("Copy this link manually:", link);
      });
    });
  }

  // Add GitHub Account Form Submit
  document.getElementById("addGhAccountForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("btnSubmitGhAccount");
    const token = document.getElementById("ghTokenInput").value.trim();
    const label = document.getElementById("ghLabelInput").value.trim();
    const isDefault = document.getElementById("ghIsDefaultInput").checked;

    btn.disabled = true;
    btn.innerHTML = `<span class="pulse-dot"></span><span>Verifying & Setting up Repo...</span>`;

    try {
      const res = await fetch("/api/github-accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, label, is_default: isDefault })
      });
      const data = await res.json();
      if (data.error) {
        alert("GitHub Connection Failed: " + data.error);
      } else {
        document.getElementById("ghTokenInput").value = "";
        document.getElementById("ghLabelInput").value = "";
        document.getElementById("ghIsDefaultInput").checked = false;
        await loadGithubAccounts();
        alert(`Successfully connected GitHub account: @${data.account.username}`);
      }
    } catch (err) {
      alert("Error connecting account: " + err.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<span>Verify & Connect Account</span>`;
    }
  });

  // Search input
  document.getElementById("searchInput").addEventListener("input", renderProfiles);

  // Filter pills
  document.querySelectorAll(".pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      activeFilter = pill.dataset.filter;
      renderProfiles();
    });
  });

  // Proxy radio change
  document.querySelectorAll('input[name="proxyType"]').forEach(radio => {
    radio.addEventListener("change", (e) => {
      const isCountry = e.target.value === "country";
      const isCustom = e.target.value === "custom";
      const isGithub = e.target.value === "github";
      const cpGroup = document.getElementById("formCountryProxyGroup");
      if (cpGroup) cpGroup.style.display = isCountry ? "block" : "none";
      document.getElementById("formCustomProxyGroup").style.display = isCustom ? "block" : "none";
      document.getElementById("formGithubAccountGroup").style.display = isGithub ? "block" : "none";
      if (isCountry) {
        const cc = document.getElementById("formCountrySelect")?.value || "PK";
        loadCountryProxiesInForm(cc);
      } else if (isCustom) {
        assembleProxyString();
      }
    });
  });

  // Quick Paste / Auto-Fill Proxy (ixBrowser style)
  const quickPasteInput = document.getElementById("formProxyQuickPaste");
  const autoFillBtn = document.getElementById("btnAutoFillProxy");

  function triggerProxyAutoFill() {
    const raw = quickPasteInput?.value?.trim() || "";
    if (!raw) return;
    const parsed = parseProxyClientSide(raw);
    if (parsed) {
      applyParsedProxyToInputs(parsed);
      const badge = document.getElementById("proxyTestStatusBadge");
      if (badge) {
        badge.style.display = "inline";
        badge.style.color = "var(--accent-cyan)";
        badge.textContent = "⚡ Form auto-filled!";
        setTimeout(() => { badge.style.display = "none"; }, 2000);
      }
    }
  }

  if (quickPasteInput) {
    quickPasteInput.addEventListener("input", () => {
      const val = quickPasteInput.value.trim();
      if (val.includes(":") || val.includes("@")) {
        triggerProxyAutoFill();
      }
    });
  }

  if (autoFillBtn) {
    autoFillBtn.addEventListener("click", triggerProxyAutoFill);
  }

  // Structured Proxy Inputs Change -> Reassemble
  ["formProxyProtocol", "formProxyHost", "formProxyPort", "formProxyUser", "formProxyPass"].forEach(fId => {
    const el = document.getElementById(fId);
    if (el) {
      el.addEventListener("input", assembleProxyString);
      el.addEventListener("change", assembleProxyString);
    }
  });

  // Test Proxy Connection Button
  const btnTestProxy = document.getElementById("btnTestProxyConn");
  if (btnTestProxy) {
    btnTestProxy.addEventListener("click", handleTestProxyConnection);
  }

  // User-Agent select change
  document.getElementById("formUserAgentSelect").addEventListener("change", (e) => {
    document.getElementById("formCustomUaGroup").style.display = 
      e.target.value === "custom" ? "flex" : "none";
  });

  // Randomize button in modal
  document.getElementById("btnFormRandomUa").addEventListener("click", () => {
    const randomItem = allUserAgents[Math.floor(Math.random() * allUserAgents.length)];
    document.getElementById("formUserAgentSelect").value = randomItem.id;
    document.getElementById("formCustomUaGroup").style.display = "none";
  });

  // Form Submit
  document.getElementById("profileForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    assembleProxyString();
    const id = document.getElementById("formProfileId").value;
    const uaId = document.getElementById("formUserAgentSelect").value;
    const uaObj = allUserAgents.find(u => u.id === uaId);

    let uaString = "";
    let isMobile = false;

    if (uaId === "custom") {
      uaString = document.getElementById("formCustomUaInput").value.trim();
      isMobile = uaString.includes("Mobile") || uaString.includes("Android") || uaString.includes("iPhone");
    } else if (uaObj) {
      uaString = uaObj.ua;
      isMobile = uaObj.isMobile || false;
    }

    const pType = document.querySelector('input[name="proxyType"]:checked')?.value || "none";
    const selCountry = document.getElementById("formCountrySelect");
    const cCode = selCountry ? selCountry.value : "PK";
    const cText = selCountry && selCountry.options[selCountry.selectedIndex] ? selCountry.options[selCountry.selectedIndex].text : "🇵🇰 Pakistan";
    const cProxy = document.getElementById("formCountryProxyInput")?.value?.trim() || "";

    const autoEnabled = document.querySelector('input[name="profileAutomationEnabled"]:checked')?.value === 'on';
    const autoPlatforms = Array.from(document.querySelectorAll('input[name="autoPlatform"]:checked')).map(c => c.value);
    const autoCustomUrl = document.getElementById("formAutoCustomUrl")?.value?.trim() || "";

    const payload = {
      name: document.getElementById("formName").value.trim(),
      color: document.getElementById("formColor").value,
      notes: document.getElementById("formNotes").value.trim(),
      userAgentId: uaId,
      userAgent: uaString,
      isMobile: isMobile,
      proxyType: pType,
      countryCode: cCode,
      countryName: cText,
      countryProxy: cProxy,
      githubAccountId: document.getElementById("formGithubAccountSelect").value || "default",
      customProxy: pType === "country" && cProxy ? cProxy : document.getElementById("formCustomProxy").value.trim(),
      killSwitch: Boolean(document.getElementById("formKillSwitch")?.checked),
      timezone: document.getElementById("formTimezone").value || "America/New_York",
      startUrl: document.getElementById("formStartUrl").value.trim() || "https://studio.youtube.com",
      automation: {
        enabled: autoEnabled,
        platforms: autoPlatforms.length ? autoPlatforms : ['youtube'],
        customUrl: autoCustomUrl,
        githubAccountId: document.getElementById("formGithubAccountSelect").value || "default"
      }
    };

    if (payload.proxyType === "github" && (!allGithubAccounts || allGithubAccounts.length === 0)) {
      alert("⚠️ GitHub Account Required!\n\nAapne 'GitHub Cloud Runner' proxy chuna hai, lekin koi GitHub account connected nahi hai.\n\nYa to Settings me jaakar apna GitHub account jodiye, ya phir 'Direct Connection' ya 'Custom Proxy' select kijiye.");
      return;
    }

    let newProfileId = null;
    const shouldAutoLaunch = document.getElementById("formAutoLaunch")?.checked || false;

    if (id) {
      // Update
      await fetch(`/api/profiles/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    } else {
      // Create
      const res = await fetch("/api/profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.profile && data.profile.id) {
        newProfileId = data.profile.id;
      }
    }

    closeModal();
    await loadProfiles();
    CloudSyncManager.pushToCloud();

    // Automatically launch browser if requested
    if (newProfileId && shouldAutoLaunch) {
      launchProfile(newProfileId);
    }
  });

  // Ads modal close handlers
  document.getElementById("adPopupCloseBtn")?.addEventListener("click", closeAdPopup);
  document.getElementById("adPopupDismissBtn")?.addEventListener("click", closeAdPopup);
}

function isNewerVersion(remote, local) {
  const r = (remote || "").split(".").map(n => parseInt(n) || 0);
  const l = (local || "").split(".").map(n => parseInt(n) || 0);
  for (let i = 0; i < Math.max(r.length, l.length); i++) {
    const rv = r[i] || 0;
    const lv = l[i] || 0;
    if (rv > lv) return true;
    if (rv < lv) return false;
  }
  return false;
}

function initBuiltInUpdater() {
  document.getElementById("mandatoryUpdateBtn")?.addEventListener("click", startBuiltInUpdate);
  document.getElementById("updateNoticeBtn")?.addEventListener("click", startBuiltInUpdate);
}

function renderUpdateProgress(status) {
  const wrap = document.getElementById("updateInstallProgress");
  const fill = document.getElementById("updateProgressFill");
  const text = document.getElementById("updateProgressText");
  if (wrap) wrap.hidden = false;
  if (fill) fill.style.width = `${Math.max(0, Math.min(100, status.percent || 0))}%`;
  if (text) text.textContent = status.message || "Working on the update…";
  const label = status.stage === "ready" || status.stage === "restarting"
    ? "Installing & Restarting…" : `Updating… ${status.percent || 0}%`;
  const mandatoryText = document.getElementById("mandatoryBtnText");
  const noticeText = document.getElementById("updateNoticeBtnText");
  if (mandatoryText) mandatoryText.textContent = label;
  if (noticeText) noticeText.textContent = label;
}

function updateInstallFailed(message) {
  _updateInstalling = false;
  const status = {stage: "error", percent: 0, message: `Update failed: ${message} Your current app was not changed.`};
  renderUpdateProgress(status);
  ["mandatoryUpdateBtn", "updateNoticeBtn"].forEach(id => {
    const button = document.getElementById(id);
    if (button) button.disabled = false;
  });
  const mandatoryText = document.getElementById("mandatoryBtnText");
  const noticeText = document.getElementById("updateNoticeBtnText");
  if (mandatoryText) mandatoryText.textContent = "Retry Update";
  if (noticeText) noticeText.textContent = "Retry Update";
}

async function startBuiltInUpdate() { return; }

// ==========================================
// GLOBAL COUNTRY PROXIES SYSTEM (PAKISTAN, INDIA, USA, UK, GERMANY, PHILIPPINES, RUSSIA, ETC.)
// ==========================================
let allCountryCatalog = [];
let currentHubCountry = "PK";
let cachedCountryProxies = {};

async function loadCountryCatalog() {
  try {
    const res = await fetch("/api/country-proxies");
    if (!res.ok) return;
    allCountryCatalog = await res.json();
    renderCountrySelectOptions();
    renderCountryHubPills();
  } catch (e) {
    console.error("Failed to load country catalog:", e);
  }
}

function renderCountrySelectOptions() {
  const sel = document.getElementById("formCountrySelect");
  if (!sel || !allCountryCatalog || allCountryCatalog.length === 0) return;
  const currentVal = sel.value || "PK";
  sel.innerHTML = allCountryCatalog.map(c => `
    <option value="${c.code}" ${c.code === currentVal ? 'selected' : ''}>
      ${c.flag} ${c.name} (${c.availableCount} live)
    </option>
  `).join("");
}

function renderCountryHubPills() {
  const container = document.getElementById("countryHubPills");
  if (!container || !allCountryCatalog) return;
  container.innerHTML = allCountryCatalog.map(c => `
    <button type="button" class="pill ${c.code === currentHubCountry ? 'active' : ''}" onclick="switchCountryHub('${c.code}')" style="font-size: 12px; padding: 4px 10px; cursor: pointer;">
      <span>${c.flag}</span>
      <span>${c.name}</span>
      <span style="font-size: 10px; opacity: 0.75;">(${c.availableCount})</span>
    </button>
  `).join("");
}

async function loadCountryProxiesInForm(countryCode, forceRefresh = false) {
  const cc = (countryCode || document.getElementById("formCountrySelect")?.value || "PK").toUpperCase();
  const cMeta = allCountryCatalog.find(c => c.code === cc);
  if (cMeta && cMeta.timezone) {
    setTimezoneValue(cMeta.timezone);
  }

  const badge = document.getElementById("countryProxyCountBadge");
  if (badge) badge.textContent = "Checking live...";
  const tbody = document.getElementById("countryProxyTableBody");
  if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 12px; color: var(--text-muted);">⚡ Fetching live verified ${cMeta ? cMeta.name : cc} proxies...</td></tr>`;

  try {
    const endpoint = forceRefresh ? `/api/country-proxies/${cc}/refresh` : `/api/country-proxies/${cc}`;
    const opts = forceRefresh ? { method: 'POST' } : {};
    const res = await fetch(endpoint, opts);
    const data = await res.json();
    const proxies = forceRefresh ? (data.proxies || []) : (Array.isArray(data) ? data : []);
    cachedCountryProxies[cc] = proxies;

    if (badge) badge.textContent = `${proxies.length} Live Available`;

    if (proxies.length === 0) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 12px; color: #f59e0b;">No live proxies found right now. Click Refresh or try another country.</td></tr>`;
      return;
    }

    if (tbody) {
      tbody.innerHTML = proxies.map((p, idx) => `
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
          <td style="padding: 6px 10px; font-family: 'JetBrains Mono', monospace; color: #fff;">${p.host}:${p.port}</td>
          <td style="padding: 6px 10px;"><span style="text-transform: uppercase; color: var(--accent-cyan); font-weight: 600;">${p.protocol}</span></td>
          <td style="padding: 6px 10px; color: var(--text-muted);">${p.city || '-'}</td>
          <td style="padding: 6px 10px; color: ${p.latencyMs < 200 ? '#10b981' : (p.latencyMs < 600 ? '#f59e0b' : '#ef4444')}; font-weight: 600;">
            ${p.latencyMs}ms
          </td>
          <td style="padding: 6px 10px; text-align: right;">
            <button type="button" class="btn-text" style="font-size: 11px; color: #10b981; font-weight: 700; cursor: pointer;" onclick="selectCountryProxyFromTable('${p.formatted}', '${p.timezone || ''}')">
              Select ✓
            </button>
          </td>
        </tr>
      `).join("");
    }

    const currentInput = document.getElementById("formCountryProxyInput");
    if (currentInput && !currentInput.value && proxies.length > 0) {
      currentInput.value = proxies[0].formatted;
      const infoText = document.getElementById("countryProxyInfoText");
      if (infoText) infoText.innerHTML = `Auto-assigned <strong>${proxies[0].formatted}</strong> (${proxies[0].latencyMs}ms, ${proxies[0].city || cc})`;
    }
  } catch (e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 12px; color: #ef4444;">Error loading proxies: ${e.message}</td></tr>`;
  }
}

async function autoAssignBestCountryProxy() {
  const cc = (document.getElementById("formCountrySelect")?.value || "PK").toUpperCase();
  const cMeta = allCountryCatalog.find(c => c.code === cc);
  const infoText = document.getElementById("countryProxyInfoText");
  const input = document.getElementById("formCountryProxyInput");
  if (infoText) infoText.textContent = `⚡ Finding fastest verified live proxy for ${cMeta ? cMeta.name : cc}...`;

  try {
    const res = await fetch(`/api/country-proxies/${cc}/best`);
    const best = await res.json();
    if (best && best.formatted) {
      if (input) input.value = best.formatted;
      if (infoText) infoText.innerHTML = `✓ Assigned fastest live IP: <strong>${best.formatted}</strong> (⚡ ${best.latencyMs}ms - ${best.city || cc})`;
      if (best.timezone) {
        setTimezoneValue(best.timezone);
      }
    } else {
      if (infoText) infoText.textContent = `⚠️ Could not find a verified proxy for ${cc}. Click Refresh List.`;
    }
  } catch (e) {
    if (infoText) infoText.textContent = `Error: ${e.message}`;
  }
}

function selectCountryProxyFromTable(formatted, timezone) {
  const input = document.getElementById("formCountryProxyInput");
  if (input) input.value = formatted;
  if (timezone) {
    setTimezoneValue(timezone);
  }
  const infoText = document.getElementById("countryProxyInfoText");
  if (infoText) infoText.innerHTML = `✓ Selected: <strong>${formatted}</strong>`;
}

function openCountryProxiesHub(countryCode) {
  if (countryCode) currentHubCountry = countryCode.toUpperCase();
  const modal = document.getElementById("countryProxiesModal");
  if (modal) modal.style.display = "flex";
  renderCountryHubPills();
  loadCountryHubTable(currentHubCountry);
}

function closeCountryProxiesHub() {
  const modal = document.getElementById("countryProxiesModal");
  if (modal) modal.style.display = "none";
}

function switchCountryHub(countryCode) {
  currentHubCountry = countryCode.toUpperCase();
  renderCountryHubPills();
  loadCountryHubTable(currentHubCountry);
}

async function loadCountryHubTable(countryCode, forceRefresh = false) {
  const cc = countryCode.toUpperCase();
  const cMeta = allCountryCatalog.find(c => c.code === cc) || { name: cc, flag: '🌐', timezone: 'UTC' };
  
  const activeBadge = document.getElementById("countryHubActiveBadge");
  if (activeBadge) activeBadge.textContent = `${cMeta.flag} ${cMeta.name}`;
  const tzBadge = document.getElementById("countryHubTzBadge");
  if (tzBadge) tzBadge.textContent = `TZ: ${cMeta.timezone || 'UTC'}`;

  const tbody = document.getElementById("countryHubTableBody");
  if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 20px; color: var(--text-muted);">⚡ Testing & loading live ${cMeta.name} proxies...</td></tr>`;

  try {
    const endpoint = forceRefresh ? `/api/country-proxies/${cc}/refresh` : `/api/country-proxies/${cc}`;
    const opts = forceRefresh ? { method: 'POST' } : {};
    const res = await fetch(endpoint, opts);
    const data = await res.json();
    const proxies = forceRefresh ? (data.proxies || []) : (Array.isArray(data) ? data : []);
    cachedCountryProxies[cc] = proxies;

    if (proxies.length === 0) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 20px; color: #f59e0b;">No active proxies found right now. Click Refresh Proxies to scan anew.</td></tr>`;
      return;
    }

    if (tbody) {
      tbody.innerHTML = proxies.map((p, idx) => `
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.06); transition: background 0.15s;" onmouseover="this.style.background='rgba(255,255,255,0.03)'" onmouseout="this.style.background='transparent'">
          <td style="padding: 10px 14px; font-family: 'JetBrains Mono', monospace; font-weight: 600; color: #fff;">
            ${p.host}:${p.port}
          </td>
          <td style="padding: 10px 12px;">
            <span style="font-size: 11px; text-transform: uppercase; background: rgba(14, 165, 233, 0.12); color: var(--accent-cyan); padding: 2px 6px; border-radius: 4px; font-weight: 700;">
              ${p.protocol}
            </span>
          </td>
          <td style="padding: 10px 12px; color: var(--text-secondary);">${p.city || cMeta.city || '-'}</td>
          <td style="padding: 10px 12px; color: ${p.latencyMs < 200 ? '#10b981' : (p.latencyMs < 600 ? '#f59e0b' : '#ef4444')}; font-weight: 700;">
            ${p.latencyMs} ms
          </td>
          <td style="padding: 10px 12px;">
            <span style="font-size: 11px; color: #10b981; background: rgba(16, 185, 129, 0.12); padding: 2px 6px; border-radius: 4px; font-weight: 600;">
              ✓ Online
            </span>
          </td>
          <td style="padding: 10px 14px; text-align: right;">
            <div style="display: flex; gap: 6px; justify-content: flex-end;">
              <button type="button" class="btn-primary" style="padding: 4px 10px; font-size: 11.5px; font-weight: 600; background: var(--accent-emerald, #10b981); cursor: pointer;" onclick="quickCreateWithCountryProxy('${p.formatted}', '${cc}', '${cMeta.name}', '${cMeta.timezone}')">
                + Create Profile
              </button>
              <button type="button" class="btn-secondary" style="padding: 4px 8px; font-size: 11px; cursor: pointer;" onclick="copyProxyString('${p.formatted}')" title="Copy to clipboard">
                📋
              </button>
            </div>
          </td>
        </tr>
      `).join("");
    }
  } catch (e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 20px; color: #ef4444;">Error: ${e.message}</td></tr>`;
  }
}

function copyProxyString(str) {
  navigator.clipboard.writeText(str).then(() => {
    alert("✓ Proxy address copied to clipboard:\n\n" + str);
  }).catch(() => {
    prompt("Copy proxy address:", str);
  });
}

function quickCreateWithCountryProxy(proxyFormatted, countryCode, countryName, timezone) {
  closeCountryProxiesHub();
  openCreateModal();
  document.querySelector('input[name="proxyType"][value="country"]').checked = true;
  document.getElementById("formCountryProxyGroup").style.display = "block";
  document.getElementById("formCustomProxyGroup").style.display = "none";
  document.getElementById("formGithubAccountGroup").style.display = "none";
  
  const sel = document.getElementById("formCountrySelect");
  if (sel) sel.value = countryCode;
  const input = document.getElementById("formCountryProxyInput");
  if (input) input.value = proxyFormatted;
  if (timezone) {
    document.getElementById("formTimezone").value = timezone;
  }
  document.getElementById("formName").value = `${countryName} Profile`;
  const infoText = document.getElementById("countryProxyInfoText");
  if (infoText) infoText.innerHTML = `✓ Assigned <strong>${proxyFormatted}</strong> (${countryName})`;
}

window.switchCountryHub = switchCountryHub;
window.selectCountryProxyFromTable = selectCountryProxyFromTable;
window.quickCreateWithCountryProxy = quickCreateWithCountryProxy;
window.copyProxyString = copyProxyString;
window.openCountryProxiesHub = openCountryProxiesHub;
window.closeCountryProxiesHub = closeCountryProxiesHub;

// ==========================================
// REMOTE-CONTROLLED ADS & UPDATES SYSTEM
// ==========================================
async function loadAds() {
  try {
    const res = await fetch("/api/ads");
    if (!res.ok) return;
    const ads = await res.json();
    if (!ads) return;

    // 1. Render Banner Ad (Only in Profile Manager UI)
    const banner = ads.banner;
    const bannerContainer = document.getElementById("adBannerContainer");
    if (banner && banner.enabled && bannerContainer) {
      if (banner.badge) document.getElementById("adBannerBadge").textContent = banner.badge;
      if (banner.title) document.getElementById("adBannerTitle").textContent = banner.title;
      if (banner.description) document.getElementById("adBannerDesc").textContent = banner.description;
      if (banner.buttonText) document.getElementById("adBannerBtnText").textContent = banner.buttonText;
      if (banner.linkUrl) document.getElementById("adBannerBtn").href = banner.linkUrl;
      bannerContainer.style.display = "block";
    } else if (bannerContainer) {
      bannerContainer.style.display = "none";
    }

    // 2. Render Popup Ad (Only in Profile Manager UI)
    const popup = ads.popup;
    const popupModal = document.getElementById("adPopupModal");
    if (popup && popup.enabled && popupModal && !_popupShownThisSession) {
      const popupKey = "dismissed_ad_" + (popup.id || "default");
      const alreadyDismissed = sessionStorage.getItem(popupKey);
      if (!alreadyDismissed || !popup.showOncePerSession) {
        _popupShownThisSession = true;
        if (popup.badge) document.getElementById("adPopupBadge").textContent = popup.badge;
        if (popup.title) document.getElementById("adPopupTitle").textContent = popup.title;
        if (popup.message) document.getElementById("adPopupMessage").textContent = popup.message;
        if (popup.buttonText) document.getElementById("adPopupBtnText").textContent = popup.buttonText;
        if (popup.linkUrl) document.getElementById("adPopupBtn").href = popup.linkUrl;
        
        // Show popup after 1.5s delay for smooth entrance
        setTimeout(() => {
          popupModal.style.display = "flex";
        }, 1200);
      }
    }
  } catch (err) {
    console.error("Failed to load ads:", err);
  }
}

function closeAdPopup() {
  const modal = document.getElementById("adPopupModal");
  if (modal) {
    modal.style.display = "none";
    sessionStorage.setItem("dismissed_ad_popup", "true");
  }
}

// ==========================================
// DONATION / SUPPORT FEATURE
// ==========================================
let currentDonationConfig = null;

function initDonationFeature() {
  const btnDonate = document.getElementById("btnDonate");
  if (!btnDonate) return;
  const donateModal = document.getElementById("donateModal");
  const btnDonateClose = document.getElementById("btnDonateClose");

  if (btnDonate) {
    btnDonate.addEventListener("click", () => {
      openDonationModal();
    });
  }

  if (btnDonateClose && donateModal) {
    btnDonateClose.addEventListener("click", () => {
      donateModal.style.display = "none";
    });
  }

  if (donateModal) {
    donateModal.addEventListener("click", (e) => {
      if (e.target === donateModal) donateModal.style.display = "none";
    });
  }

  // Tab switching
  const tabBtns = document.querySelectorAll(".donate-tab-btn");
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const tab = btn.getAttribute("data-tab");
      switchDonationTab(tab);
    });
  });

  // Copy buttons
  setupCopyBtn("btnCopyUsdtTrc", () => currentDonationConfig?.usdtTrc20 || document.getElementById("donateUsdtTrcText")?.textContent);
  setupCopyBtn("btnCopyUsdtBep", () => currentDonationConfig?.usdtBep20 || document.getElementById("donateUsdtBepText")?.textContent);

  // In-modal Edit Wallets Toggle
  const toggleEditBtn = document.getElementById("btnToggleDonateEdit");
  const cancelEditBtn = document.getElementById("btnCancelDonationEdit");
  const saveEditBtn = document.getElementById("btnSaveDonationEdit");
  const viewSection = document.getElementById("donateViewSection");
  const editSection = document.getElementById("donateEditSection");
  const toggleText = document.getElementById("btnToggleDonateEditText");

  function setDonationEditMode(isEdit) {
    if (viewSection) viewSection.style.display = isEdit ? "none" : "block";
    if (editSection) editSection.style.display = isEdit ? "block" : "none";
    if (toggleText) toggleText.textContent = isEdit ? "Preview" : "Edit Wallets";
    const msg = document.getElementById("donateEditMsg");
    if (msg) msg.style.display = "none";
    if (isEdit && currentDonationConfig) {
      populateDonationEditFields(currentDonationConfig);
    }
  }

  if (toggleEditBtn) {
    toggleEditBtn.addEventListener("click", () => {
      const isCurrentlyEdit = editSection && editSection.style.display !== "none";
      setDonationEditMode(!isCurrentlyEdit);
    });
  }

  if (cancelEditBtn) {
    cancelEditBtn.addEventListener("click", () => {
      setDonationEditMode(false);
    });
  }

  if (saveEditBtn) {
    saveEditBtn.addEventListener("click", async () => {
      const payload = {
        title: document.getElementById("editDonationTitle")?.value?.trim() || "Support Shadda Anti Detect",
        subtitle: document.getElementById("editDonationSubtitle")?.value?.trim() || "",
        usdtBep20: document.getElementById("editDonationUsdtBep")?.value?.trim() || "",
        usdtTrc20: document.getElementById("editDonationUsdtTrc")?.value?.trim() || "",
        coffeeUrl: document.getElementById("editDonationCoffee")?.value?.trim() || "",
        customNote: document.getElementById("editDonationNote")?.value?.trim() || "",
        showUsdtTrc20: document.getElementById("editShowUsdtTrc")?.checked !== false,
        showUsdtBep20: document.getElementById("editShowUsdtBep")?.checked !== false,
        showCoffee: document.getElementById("editShowCoffee")?.checked !== false
      };

      const msg = document.getElementById("donateEditMsg");
      if (msg) {
        msg.textContent = "Saving...";
        msg.style.color = "var(--accent-cyan)";
        msg.style.display = "inline";
      }

      try {
        const res = await fetch("/api/donation-config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const ret = await res.json();
        if (ret && ret.success) {
          currentDonationConfig = ret.donation || payload;
          renderDonationDetails(currentDonationConfig);
          populateDonationEditFields(currentDonationConfig);
          if (msg) {
            msg.textContent = "✅ Saved successfully!";
            msg.style.color = "#22c55e";
          }
          setTimeout(() => {
            setDonationEditMode(false);
          }, 800);
        } else {
          if (msg) {
            msg.textContent = "❌ Failed to save";
            msg.style.color = "#ef4444";
          }
        }
      } catch (err) {
        if (msg) {
          msg.textContent = "❌ Error: " + err.message;
          msg.style.color = "#ef4444";
        }
      }
    });
  }
}

function switchDonationTab(tabName) {
  document.querySelectorAll(".donate-tab-btn").forEach(b => {
    const active = b.getAttribute("data-tab") === tabName;
    b.classList.toggle("active", active);
    b.style.background = active ? "rgba(14,165,233,0.12)" : "rgba(255,255,255,0.03)";
    b.style.borderColor = active ? "rgba(14,165,233,0.4)" : "var(--border-color)";
    b.style.color = active ? "var(--accent-cyan)" : "var(--text-secondary)";
  });

  const cryptoTab = document.getElementById("donateTabCrypto");
  const customTab = document.getElementById("donateTabCustom");

  if (cryptoTab) cryptoTab.style.display = (tabName === "crypto") ? "block" : "none";
  if (customTab) customTab.style.display = (tabName === "custom") ? "block" : "none";
}

function setupCopyBtn(btnId, getValueFn) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.addEventListener("click", async () => {
    const val = (getValueFn() || "").trim();
    if (!val) return;
    try {
      await navigator.clipboard.writeText(val);
      const originalText = btn.innerHTML;
      btn.innerHTML = "✅ Copied!";
      setTimeout(() => {
        btn.innerHTML = originalText;
      }, 2000);
    } catch {
      alert("Address: " + val);
    }
  });
}

async function openDonationModal() {
  const modal = document.getElementById("donateModal");
  if (!modal) return;
  modal.style.display = "flex";

  const viewSection = document.getElementById("donateViewSection");
  const editSection = document.getElementById("donateEditSection");
  const toggleText = document.getElementById("btnToggleDonateEditText");
  if (viewSection) viewSection.style.display = "block";
  if (editSection) editSection.style.display = "none";
  if (toggleText) toggleText.textContent = "Edit Wallets";

  try {
    const res = await fetch("/api/ads");
    if (res.ok) {
      const data = await res.json();
      if (data && data.donation) {
        currentDonationConfig = data.donation;
        renderDonationDetails(data.donation);
        populateDonationEditFields(data.donation);
      }
    }
  } catch (err) {
    console.error("Failed to load donation details:", err);
  }
}

function renderDonationDetails(d) {
  if (!d) return;
  const titleEl = document.getElementById("donateModalTitle");
  const subEl = document.getElementById("donateModalSubtitle");
  if (titleEl && d.title) titleEl.textContent = d.title;
  if (subEl && d.subtitle) subEl.textContent = d.subtitle;

  const usdtTrcEl = document.getElementById("donateUsdtTrcText");
  if (usdtTrcEl && d.usdtTrc20) usdtTrcEl.textContent = d.usdtTrc20;

  const usdtBepEl = document.getElementById("donateUsdtBepText");
  if (usdtBepEl && d.usdtBep20) usdtBepEl.textContent = d.usdtBep20;

  const coffeeLink = document.getElementById("donateCoffeeLink");
  if (coffeeLink && d.coffeeUrl) coffeeLink.href = d.coffeeUrl;

  const noteEl = document.getElementById("donateCustomNote");
  if (noteEl && d.customNote) noteEl.textContent = d.customNote;

  // Owner-controlled per-item visibility. A missing flag counts as visible (default on).
  const showTrc = d.showUsdtTrc20 !== false;
  const showBep = d.showUsdtBep20 !== false;
  const showCoffee = d.showCoffee !== false;

  const trcCard = document.getElementById("donateCardUsdtTrc");
  if (trcCard) trcCard.style.display = showTrc ? "block" : "none";
  const bepCard = document.getElementById("donateCardUsdtBep");
  if (bepCard) bepCard.style.display = showBep ? "block" : "none";

  // If both crypto items are hidden, show a small placeholder instead of an empty tab.
  const cryptoEmpty = document.getElementById("donateCryptoEmpty");
  if (cryptoEmpty) cryptoEmpty.style.display = (!showTrc && !showBep) ? "block" : "none";

  // Coffee lives on its own tab; hide the tab button and the link when turned off.
  const coffeeTabBtn = document.getElementById("tabBtnCustom");
  if (coffeeTabBtn) coffeeTabBtn.style.display = showCoffee ? "" : "none";
  if (coffeeLink) coffeeLink.style.display = showCoffee ? "" : "none";
  // If the coffee tab is hidden while active, fall back to the crypto tab.
  if (!showCoffee) {
    const customTab = document.getElementById("donateTabCustom");
    if (customTab && customTab.style.display !== "none") switchDonationTab("crypto");
  }
}

function populateDonationEditFields(d) {
  if (!d) return;
  const t = document.getElementById("editDonationTitle");
  if (t && d.title) t.value = d.title;
  const s = document.getElementById("editDonationSubtitle");
  if (s && d.subtitle) s.value = d.subtitle;
  const bep = document.getElementById("editDonationUsdtBep");
  if (bep && d.usdtBep20) bep.value = d.usdtBep20;
  const trc = document.getElementById("editDonationUsdtTrc");
  if (trc && d.usdtTrc20) trc.value = d.usdtTrc20;
  const c = document.getElementById("editDonationCoffee");
  if (c && d.coffeeUrl) c.value = d.coffeeUrl;
  const n = document.getElementById("editDonationNote");
  if (n && d.customNote) n.value = d.customNote;

  const showTrc = document.getElementById("editShowUsdtTrc");
  if (showTrc) showTrc.checked = d.showUsdtTrc20 !== false;
  const showBep = document.getElementById("editShowUsdtBep");
  if (showBep) showBep.checked = d.showUsdtBep20 !== false;
  const showCoffee = document.getElementById("editShowCoffee");
  if (showCoffee) showCoffee.checked = d.showCoffee !== false;
}

// -------------------------------------------------------------
// ixBrowser-Style Easy Proxy Parsing, Assembly, and Testing
// -------------------------------------------------------------
function parseProxyClientSide(rawStr) {
  if (!rawStr) return null;
  let raw = rawStr.trim();
  let protocol = "socks5";

  const protoMatch = raw.match(/^([a-zA-Z0-9]+):\/\//);
  if (protoMatch) {
    const p = protoMatch[1].toLowerCase();
    if (["http", "https", "socks5", "socks4"].includes(p)) {
      protocol = p;
    }
    raw = raw.substring(protoMatch[0].length).trim();
  }

  // Convert tab, comma, semicolon, pipe, or space delimiters to colons
  if (!raw.includes("@")) {
    if (raw.includes("\t")) {
      raw = raw.replace(/\t+/g, ":");
    } else if (raw.includes(",")) {
      raw = raw.replace(/,+/g, ":");
    } else if (raw.includes(";")) {
      raw = raw.replace(/;+/g, ":");
    } else if (raw.includes("|")) {
      raw = raw.replace(/\|+/g, ":");
    } else if (/\s+/.test(raw) && !raw.includes(":")) {
      raw = raw.replace(/\s+/g, ":");
    }
  }
  raw = raw.replace(/\s+/g, "");

  let host = "";
  let port = "";
  let user = "";
  let pass = "";

  if (raw.includes("@")) {
    const [left, right] = raw.split("@");
    if (right && right.includes(":")) {
      const rParts = right.split(":");
      const lParts = left.split(":");
      if (rParts.length >= 2 && !isNaN(rParts[rParts.length - 1])) {
        // user:pass@host:port
        user = lParts[0] || "";
        pass = lParts.slice(1).join(":");
        host = rParts[0] || "";
        port = rParts[1] || "";
      } else if (lParts.length >= 2 && !isNaN(lParts[lParts.length - 1])) {
        // host:port@user:pass
        host = lParts[0] || "";
        port = lParts[1] || "";
        user = rParts[0] || "";
        pass = rParts.slice(1).join(":");
      }
    }
  } else if (raw.includes(":")) {
    const parts = raw.split(":");
    if (parts.length === 2) {
      host = parts[0];
      port = parts[1];
    } else if (parts.length === 4) {
      if (!isNaN(parts[1])) {
        // host:port:user:pass
        host = parts[0];
        port = parts[1];
        user = parts[2];
        pass = parts[3];
      } else if (!isNaN(parts[3])) {
        // user:pass:host:port
        user = parts[0];
        pass = parts[1];
        host = parts[2];
        port = parts[3];
      }
    } else if (parts.length > 4 && !isNaN(parts[1])) {
      host = parts[0];
      port = parts[1];
      user = parts[2];
      pass = parts.slice(3).join(":");
    }
  } else {
    host = raw;
  }

  if (!port || isNaN(port)) port = "8080";

  return { protocol, host, port, user, pass };
}

function applyParsedProxyToInputs(parsed) {
  if (!parsed) return;
  const protoEl = document.getElementById("formProxyProtocol");
  const hostEl = document.getElementById("formProxyHost");
  const portEl = document.getElementById("formProxyPort");
  const userEl = document.getElementById("formProxyUser");
  const passEl = document.getElementById("formProxyPass");

  if (protoEl && parsed.protocol) protoEl.value = parsed.protocol;
  if (hostEl && parsed.host) hostEl.value = parsed.host;
  if (portEl && parsed.port) portEl.value = parsed.port;
  if (userEl) userEl.value = parsed.user || "";
  if (passEl) passEl.value = parsed.pass || "";

  assembleProxyString();
}

function assembleProxyString() {
  const proto = document.getElementById("formProxyProtocol")?.value || "socks5";
  const host = document.getElementById("formProxyHost")?.value?.trim() || "";
  const port = document.getElementById("formProxyPort")?.value?.trim() || "";
  const user = document.getElementById("formProxyUser")?.value?.trim() || "";
  const pass = document.getElementById("formProxyPass")?.value?.trim() || "";

  const customProxyEl = document.getElementById("formCustomProxy");
  if (!host || !port) {
    if (customProxyEl) customProxyEl.value = "";
    return "";
  }

  let formatted = "";
  if (user && pass) {
    formatted = `${proto}://${user}:${pass}@${host}:${port}`;
  } else {
    formatted = `${proto}://${host}:${port}`;
  }

  if (customProxyEl) customProxyEl.value = formatted;
  return formatted;
}

async function handleTestProxyConnection() {
  assembleProxyString();
  const proto = document.getElementById("formProxyProtocol")?.value || "socks5";
  const host = document.getElementById("formProxyHost")?.value?.trim() || "";
  const port = document.getElementById("formProxyPort")?.value?.trim() || "";
  const user = document.getElementById("formProxyUser")?.value?.trim() || "";
  const pass = document.getElementById("formProxyPass")?.value?.trim() || "";

  const btn = document.getElementById("btnTestProxyConn");
  const btnText = document.getElementById("btnTestProxyText");
  const badge = document.getElementById("proxyTestStatusBadge");
  const diagCard = document.getElementById("proxyDiagnosticCard");
  const diagContent = document.getElementById("proxyDiagContent");
  const applyTzBtn = document.getElementById("btnApplyProxyTimezone");

  if (!host || !port) {
    alert("Please enter Proxy Host / IP and Port first.");
    return;
  }

  btn.disabled = true;
  if (btnText) btnText.textContent = "Testing connection...";
  if (badge) {
    badge.style.display = "inline";
    badge.style.color = "var(--accent-cyan)";
    badge.textContent = "⏳ Testing...";
  }
  if (diagCard) diagCard.style.display = "none";
  if (applyTzBtn) applyTzBtn.style.display = "none";

  try {
    const res = await fetch("/api/proxy/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        protocol: proto,
        host: host,
        port: parseInt(port, 10),
        username: user,
        password: pass
      })
    });
    const data = await res.json();
    if (data.success) {
      if (badge) {
        badge.style.color = "#22c55e";
        badge.innerHTML = `✅ Connected (${data.latencyMs}ms)`;
      }
      if (diagCard && diagContent) {
        diagCard.style.display = "block";
        diagContent.innerHTML = `
          <span style="color: #22c55e; font-weight: 700;">🌍 IP: <span style="color:#fff; font-family: 'JetBrains Mono', monospace;">${data.ip || host}</span></span>
          <span style="color: var(--accent-cyan); font-weight: 600;">📍 Location: <span style="color:#fff;">${data.country || 'Unknown'} (${data.city || ''})</span></span>
          <span style="color: #eab308; font-weight: 600;">⚡ Ping: <span style="color:#fff;">${data.latencyMs}ms</span></span>
          ${data.timezone ? `<span style="color: #a855f7; font-weight: 600;">🕒 Timezone: <span style="color:#fff;">${data.timezone}</span></span>` : ''}
          ${data.isp ? `<span style="color: var(--text-muted);">🏢 ISP: ${data.isp}</span>` : ''}
        `;
      }
      if (applyTzBtn && data.timezone) {
        applyTzBtn.style.display = "inline-block";
        applyTzBtn.textContent = `🕒 Auto-Set Profile Timezone to ${data.timezone}`;
        applyTzBtn.onclick = () => {
          const tzSelect = document.getElementById("formTimezone");
          if (tzSelect) {
            let hasOpt = false;
            for (let i = 0; i < tzSelect.options.length; i++) {
              if (tzSelect.options[i].value === data.timezone) {
                tzSelect.selectedIndex = i;
                hasOpt = true;
                break;
              }
            }
            if (!hasOpt) {
              const opt = document.createElement("option");
              opt.value = data.timezone;
              opt.textContent = `📍 ${data.timezone} (Proxy Geo Location)`;
              tzSelect.appendChild(opt);
              tzSelect.value = data.timezone;
            }
            alert(`✅ Profile timezone successfully updated to ${data.timezone}!`);
          }
        };
      }
    } else {
      if (badge) {
        badge.style.color = "#ef4444";
        badge.innerHTML = `❌ Failed`;
      }
      if (diagCard && diagContent) {
        diagCard.style.display = "block";
        diagContent.innerHTML = `
          <span style="color: #ef4444; font-weight: 600;">⚠️ Error: ${data.error || 'Proxy connection failed'}</span>
        `;
      }
    }
  } catch (err) {
    if (badge) {
      badge.style.color = "#ef4444";
      badge.textContent = "❌ Test Error";
    }
    if (diagCard && diagContent) {
      diagCard.style.display = "block";
      diagContent.innerHTML = `<span style="color: #ef4444;">Error: ${err.message}</span>`;
    }
  } finally {
    btn.disabled = false;
    if (btnText) btnText.textContent = "Check / Test Proxy";
  }
}


// ─────────────────────────────────────────────────────────
//  Admin Mode Detection
//  Tries to reach the admin panel on port 5099.
//  If it's reachable (owner's machine), show the Edit Wallets button.
//  On regular user/release builds, port 5099 is never open → button stays hidden.
// ─────────────────────────────────────────────────────────
async function detectAdminMode() {
  try {
    // Use no-cors so CORS errors don't mask a live server
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 1500); // 1.5s timeout
    try {
      const resp = await fetch("http://127.0.0.1:5099/api/admin/ping", {
        method: "GET",
        mode: "no-cors",
        signal: ctrl.signal
      });
      clearTimeout(timer);
      // In no-cors mode, any response (even opaque) means server is UP
      showAdminEditButton(true);
    } catch (e) {
      clearTimeout(timer);
      if (e.name !== "AbortError") {
        // Network error = server not running = not admin
        showAdminEditButton(false);
      }
    }
  } catch (_) {
    // Silently ignore — default is hidden
  }
}

function showAdminEditButton(isAdmin) {
  const btn = document.getElementById("btnToggleDonateEdit");
  if (btn) {
    btn.style.display = isAdmin ? "flex" : "none";
  }
  const adminPanelBtn = document.getElementById("btnAdminPanel");
  if (adminPanelBtn) {
    adminPanelBtn.style.display = isAdmin ? "flex" : "none";
  }
}

// ─────────────────────────────────────────────────────────
//  User Authentication Manager (Login, Register, Session)
// ─────────────────────────────────────────────────────────

const AuthManager = {
  currentUser: null,
  isGuestMode: false,

  async init() {
    this.setupListeners();

    try {
      const res = await fetch("/api/auth/session");
      const data = await res.json();
      if (data && data.authenticated && data.user) {
        this.currentUser = data.user;
        this.showApp();
        return;
      }
    } catch (e) {
      console.warn("Session check error:", e);
    }

    // Default to showing auth screen if not logged in
    this.showAuth();
  },

  setupListeners() {
    // Tab buttons
    const tabLoginBtn = document.getElementById("tabLoginBtn");
    const tabRegisterBtn = document.getElementById("tabRegisterBtn");
    const loginForm = document.getElementById("loginForm");
    const registerForm = document.getElementById("registerForm");

    if (tabLoginBtn && tabRegisterBtn && loginForm && registerForm) {
      tabLoginBtn.addEventListener("click", () => {
        tabLoginBtn.classList.add("active");
        tabRegisterBtn.classList.remove("active");
        loginForm.style.display = "flex";
        registerForm.style.display = "none";
        this.clearAlerts();
      });

      tabRegisterBtn.addEventListener("click", () => {
        tabRegisterBtn.classList.add("active");
        tabLoginBtn.classList.remove("active");
        registerForm.style.display = "flex";
        loginForm.style.display = "none";
        this.clearAlerts();
      });
    }

    // Show/Hide password toggles
    document.querySelectorAll(".btn-toggle-pwd").forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetId = btn.getAttribute("data-target");
        const input = document.getElementById(targetId);
        if (input) {
          if (input.type === "password") {
            input.type = "text";
            btn.textContent = "🙈";
          } else {
            input.type = "password";
            btn.textContent = "👁️";
          }
        }
      });
    });

    // Login submit
    if (loginForm) {
      loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const submitBtn = document.getElementById("btnSubmitLogin");
        const identifier = document.getElementById("loginIdentifier")?.value?.trim();
        const password = document.getElementById("loginPassword")?.value;
        const rememberMe = document.getElementById("loginRememberMe")?.checked ?? true;

        if (!identifier || !password) {
          this.showAlert("loginAlert", "Please enter both username/email and password.", "error");
          return;
        }

        submitBtn.disabled = true;
        submitBtn.innerHTML = `<span>⏳ Signing in...</span>`;
        this.clearAlerts();

        try {
          const res = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              usernameOrEmail: identifier,
              password: password,
              rememberMe: rememberMe
            })
          });
          const data = await res.json();
          if (data.success && data.user) {
            this.currentUser = data.user;
            this.showApp();
            if (window.CloudSyncManager) {
              CloudSyncManager.enabled = true;
              CloudSyncManager.roomKey = data.user.workspaceId;
              CloudSyncManager.updateUI();
              CloudSyncManager.connectSSE();
              await CloudSyncManager.pullFromCloud(true);
            }
          } else {
            this.showAlert("loginAlert", data.error || "Login failed. Please check your credentials.", "error");
          }
        } catch (err) {
          this.showAlert("loginAlert", "Connection error: " + err.message, "error");
        } finally {
          submitBtn.disabled = false;
          submitBtn.innerHTML = `<span>Sign In & Sync Profiles</span>`;
        }
      });
    }

    // Register submit
    if (registerForm) {
      registerForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const submitBtn = document.getElementById("btnSubmitRegister");
        const username = document.getElementById("registerUsername")?.value?.trim();
        const email = document.getElementById("registerEmail")?.value?.trim();
        const password = document.getElementById("registerPassword")?.value;
        const confirmPassword = document.getElementById("registerConfirmPassword")?.value;

        if (password !== confirmPassword) {
          this.showAlert("registerAlert", "Passwords do not match! Please verify.", "error");
          return;
        }

        submitBtn.disabled = true;
        submitBtn.innerHTML = `<span>⏳ Creating Account...</span>`;
        this.clearAlerts();

        try {
          const res = await fetch("/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              username: username,
              email: email,
              password: password
            })
          });
          const data = await res.json();
          if (data.success && data.user) {
            this.currentUser = data.user;
            this.showApp();
            if (window.CloudSyncManager) {
              CloudSyncManager.enabled = true;
              CloudSyncManager.roomKey = data.user.workspaceId;
              CloudSyncManager.updateUI();
              CloudSyncManager.connectSSE();
              await CloudSyncManager.pushToCloud(false);
            }
          } else {
            this.showAlert("registerAlert", data.error || "Registration failed.", "error");
          }
        } catch (err) {
          this.showAlert("registerAlert", "Connection error: " + err.message, "error");
        } finally {
          submitBtn.disabled = false;
          submitBtn.innerHTML = `<span>Create Account & Start Live Sync</span>`;
        }
      });
    }

    // Guest / Offline Mode
    const btnGuest = document.getElementById("btnGuestMode");
    if (btnGuest) {
      btnGuest.addEventListener("click", () => {
        this.isGuestMode = true;
        this.currentUser = null;
        this.showApp();
      });
    }

    // User Menu in Header
    const btnUserMenu = document.getElementById("btnUserMenu");
    const userMenuDropdown = document.getElementById("userMenuDropdown");
    if (btnUserMenu && userMenuDropdown) {
      btnUserMenu.addEventListener("click", (e) => {
        e.stopPropagation();
        userMenuDropdown.style.display = userMenuDropdown.style.display === "block" ? "none" : "block";
      });

      document.addEventListener("click", (e) => {
        if (!btnUserMenu.contains(e.target) && !userMenuDropdown.contains(e.target)) {
          userMenuDropdown.style.display = "none";
        }
      });
    }

    // Cloud Sync from menu
    const btnOpenCloudSyncFromMenu = document.getElementById("btnOpenCloudSyncFromMenu");
    if (btnOpenCloudSyncFromMenu) {
      btnOpenCloudSyncFromMenu.addEventListener("click", () => {
        if (userMenuDropdown) userMenuDropdown.style.display = "none";
        if (typeof openCloudSyncModal === "function") openCloudSyncModal();
      });
    }

    // Logout
    const btnLogout = document.getElementById("btnLogout");
    if (btnLogout) {
      btnLogout.addEventListener("click", async () => {
        if (userMenuDropdown) userMenuDropdown.style.display = "none";
        if (!confirm("Are you sure you want to log out?")) return;
        try {
          await fetch("/api/auth/logout", { method: "POST" });
        } catch (e) {}
        this.currentUser = null;
        this.isGuestMode = false;
        if (window.CloudSyncManager) {
          CloudSyncManager.disconnect();
        }
        this.showAuth();
      });
    }
  },

  showAlert(elemId, message, type = "error") {
    const el = document.getElementById(elemId);
    if (!el) return;
    el.className = `auth-alert ${type}`;
    el.textContent = message;
    el.style.display = "block";
  },

  clearAlerts() {
    const a1 = document.getElementById("loginAlert");
    const a2 = document.getElementById("registerAlert");
    if (a1) { a1.style.display = "none"; a1.textContent = ""; }
    if (a2) { a2.style.display = "none"; a2.textContent = ""; }
  },

  showApp() {
    const authScreen = document.getElementById("authScreen");
    const appShell = document.getElementById("appShell");
    if (authScreen) authScreen.style.display = "none";
    if (appShell) appShell.style.display = "flex";

    // Update Header Badge
    const navUsername = document.getElementById("navUsername");
    const userAvatarCircle = document.getElementById("userAvatarCircle");
    const menuUserFullName = document.getElementById("menuUserFullName");
    const menuUserEmail = document.getElementById("menuUserEmail");
    const menuUserWorkspace = document.getElementById("menuUserWorkspace");

    if (this.currentUser) {
      const name = this.currentUser.username || "User";
      const initial = name.charAt(0).toUpperCase();
      if (navUsername) navUsername.textContent = name;
      if (userAvatarCircle) userAvatarCircle.textContent = initial;
      if (menuUserFullName) menuUserFullName.textContent = name;
      if (menuUserEmail) menuUserEmail.textContent = this.currentUser.email || "";
      if (menuUserWorkspace) menuUserWorkspace.textContent = `Workspace: ${this.currentUser.workspaceId || 'ws_' + name.toLowerCase()}`;
    } else if (this.isGuestMode) {
      if (navUsername) navUsername.textContent = "Guest (Offline)";
      if (userAvatarCircle) userAvatarCircle.textContent = "G";
      if (menuUserFullName) menuUserFullName.textContent = "Guest User";
      if (menuUserEmail) menuUserEmail.textContent = "Offline Local Workspace";
      if (menuUserWorkspace) menuUserWorkspace.textContent = "Workspace: Local Only";
    }
  },

  showAuth() {
    const authScreen = document.getElementById("authScreen");
    const appShell = document.getElementById("appShell");
    if (authScreen) authScreen.style.display = "flex";
    if (appShell) appShell.style.display = "none";
    this.clearAlerts();
  }
};

window.AuthManager = AuthManager;

// ─────────────────────────────────────────────────────────
//  Multi-Device Real-Time Cloud Sync (Firebase Free Tier)
// ─────────────────────────────────────────────────────────

function openCloudSyncModal() {
  const modal = document.getElementById("cloudSyncModal");
  if (!modal) return;
  CloudSyncManager.updateUI();
  const roomInput = document.getElementById("cloudSyncRoomKey");
  if (roomInput && !roomInput.value.trim()) {
    if (CloudSyncManager.roomKey) {
      roomInput.value = CloudSyncManager.roomKey;
    } else {
      roomInput.value = "shadda-" + Math.random().toString(36).substring(2, 8);
    }
  }
  modal.style.display = "flex";
}

function closeCloudSyncModal() {
  const modal = document.getElementById("cloudSyncModal");
  if (modal) modal.style.display = "none";
}

window.openCloudSyncModal = openCloudSyncModal;
window.closeCloudSyncModal = closeCloudSyncModal;

const CloudSyncManager = {
  enabled: false,
  firebaseUrl: "https://user-ananlytics-default-rtdb.firebaseio.com",
  roomKey: "",
  lastSync: 0,
  eventSource: null,
  isSyncingLocal: false,

  async init() {
    try {
      const res = await fetch("/api/cloud-sync/config");
      const cfg = await res.json();
      if (cfg) {
        this.enabled = Boolean(cfg.enabled);
        if (cfg.firebaseUrl) this.firebaseUrl = cfg.firebaseUrl;
        if (cfg.roomKey) this.roomKey = cfg.roomKey;
        if (cfg.lastSync) this.lastSync = cfg.lastSync;
      }
    } catch (e) {
      console.warn("Could not load cloud sync config:", e);
    }

    this.updateUI();

    if (this.enabled && this.roomKey) {
      this.connectSSE();
    }
  },

  updateUI() {
    const statusDot = document.getElementById("cloudSyncStatusDot");
    const btnText = document.getElementById("cloudSyncBtnText");
    const bigDot = document.getElementById("cloudSyncBigDot");
    const statusTitle = document.getElementById("cloudSyncStatusTitle");
    const statusTag = document.getElementById("cloudSyncStatusTag");
    const lastSyncTime = document.getElementById("cloudSyncLastSyncTime");
    const btnPush = document.getElementById("btnPushCloudSync");
    const btnPull = document.getElementById("btnPullCloudSync");
    const btnDisconnect = document.getElementById("btnDisconnectCloudSync");
    const btnSave = document.getElementById("btnSaveCloudSync");

    const inputRoomKey = document.getElementById("cloudSyncRoomKey");
    const inputFirebaseUrl = document.getElementById("cloudSyncFirebaseUrl");

    if (inputRoomKey && this.roomKey && !inputRoomKey.value) {
      inputRoomKey.value = this.roomKey;
    }
    if (inputFirebaseUrl && this.firebaseUrl) {
      inputFirebaseUrl.value = this.firebaseUrl;
    }

    let timeStr = "Never";
    if (this.lastSync) {
      const d = new Date(this.lastSync * 1000);
      timeStr = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) + " (" + d.toLocaleDateString() + ")";
    }

    if (this.enabled && this.roomKey) {
      if (statusDot) {
        statusDot.style.background = "#10b981";
        statusDot.style.boxShadow = "0 0 8px rgba(16, 185, 129, 0.7)";
      }
      if (btnText) btnText.textContent = `Sync: ${this.roomKey.length > 12 ? this.roomKey.slice(0, 10) + "..." : this.roomKey}`;
      if (bigDot) {
        bigDot.style.background = "#10b981";
        bigDot.style.boxShadow = "0 0 10px rgba(16, 185, 129, 0.8)";
      }
      if (statusTitle) statusTitle.textContent = `Live Synced (${this.roomKey})`;
      if (statusTag) {
        statusTag.textContent = "LIVE CLOUD";
        statusTag.style.background = "rgba(16, 185, 129, 0.15)";
        statusTag.style.color = "#10b981";
      }
      if (lastSyncTime) lastSyncTime.textContent = `Last sync: ${timeStr} • Real-time stream active`;
      if (btnPush) btnPush.style.display = "inline-flex";
      if (btnPull) btnPull.style.display = "inline-flex";
      if (btnDisconnect) btnDisconnect.style.display = "flex";
      if (btnSave) {
        btnSave.innerHTML = `<span>🔄 Update Cloud Settings</span>`;
      }
    } else {
      if (statusDot) {
        statusDot.style.background = "#64748b";
        statusDot.style.boxShadow = "0 0 6px rgba(100, 116, 139, 0.4)";
      }
      if (btnText) btnText.textContent = "Cloud Sync";
      if (bigDot) {
        bigDot.style.background = "#64748b";
        bigDot.style.boxShadow = "0 0 8px rgba(100, 116, 139, 0.5)";
      }
      if (statusTitle) statusTitle.textContent = "Offline (Local Workspace)";
      if (statusTag) {
        statusTag.textContent = "LOCAL ONLY";
        statusTag.style.background = "rgba(255,255,255,0.08)";
        statusTag.style.color = "var(--text-muted)";
      }
      if (lastSyncTime) lastSyncTime.textContent = `Last sync: ${timeStr}`;
      if (btnPush) btnPush.style.display = "none";
      if (btnPull) btnPull.style.display = "none";
      if (btnDisconnect) btnDisconnect.style.display = "none";
      if (btnSave) {
        btnSave.innerHTML = `<span>⚡ Connect & Start Live Sync</span>`;
      }
    }
  },

  connectSSE() {
    if (this.eventSource) {
      try { this.eventSource.close(); } catch (e) {}
      this.eventSource = null;
    }

    if (!this.enabled || !this.roomKey) return;

    const base = (this.firebaseUrl || "https://user-ananlytics-default-rtdb.firebaseio.com").replace(/\/+$/, "");
    const cleanRoom = encodeURIComponent(this.roomKey.trim());
    const sseUrl = `${base}/workspaces/${cleanRoom}/profiles.json`;

    try {
      this.eventSource = new EventSource(sseUrl);

      this.eventSource.addEventListener("put", async (e) => {
        if (this.isSyncingLocal) return; // Ignore own echo
        try {
          const payload = JSON.parse(e.data);
          if (!payload) return;

          if (payload.path === "/") {
            let incoming = payload.data;
            if (incoming === null) return;
            let profilesList = [];
            if (Array.isArray(incoming)) {
              profilesList = incoming.filter(Boolean);
            } else if (typeof incoming === "object") {
              profilesList = Object.values(incoming).filter(Boolean);
            }

            if (profilesList.length > 0) {
              await this.applyIncoming(profilesList);
            }
          } else {
            await this.pullFromCloud(true);
          }
        } catch (err) {
          console.warn("SSE put event parse error:", err);
        }
      });

      this.eventSource.addEventListener("patch", async () => {
        if (this.isSyncingLocal) return;
        await this.pullFromCloud(true);
      });

      this.eventSource.onopen = () => {
        const bigDot = document.getElementById("cloudSyncBigDot");
        const statusDot = document.getElementById("cloudSyncStatusDot");
        if (bigDot) {
          bigDot.style.background = "#10b981";
          bigDot.style.boxShadow = "0 0 10px rgba(16, 185, 129, 0.8)";
        }
        if (statusDot) {
          statusDot.style.background = "#10b981";
        }
      };

      this.eventSource.onerror = () => {
        const bigDot = document.getElementById("cloudSyncBigDot");
        if (bigDot) {
          bigDot.style.background = "#f59e0b";
          bigDot.style.boxShadow = "0 0 10px rgba(245, 158, 11, 0.6)";
        }
      };
    } catch (err) {
      console.warn("Failed to initiate EventSource for Firebase SSE:", err);
    }
  },

  async applyIncoming(profilesList) {
    try {
      const res = await fetch("/api/cloud-sync/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profiles: profilesList })
      });
      const data = await res.json();
      if (data.success) {
        this.lastSync = data.lastSync || Math.floor(Date.now() / 1000);
        this.updateUI();
        await loadProfiles();
      }
    } catch (e) {
      console.error("Failed to apply cloud sync payload:", e);
    }
  },

  async pushToCloud(showToast = false) {
    if (!this.enabled || !this.roomKey) return;
    this.isSyncingLocal = true;

    try {
      const res = await fetch("/api/profiles");
      const profiles = await res.json();
      const sanitized = (profiles || []).map(p => {
        const copy = { ...p };
        delete copy.isRunning;
        delete copy.allocatedIp;
        return copy;
      });

      const base = (this.firebaseUrl || "https://user-ananlytics-default-rtdb.firebaseio.com").replace(/\/+$/, "");
      const cleanRoom = encodeURIComponent(this.roomKey.trim());
      const putUrl = `${base}/workspaces/${cleanRoom}/profiles.json`;

      const fbRes = await fetch(putUrl, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(sanitized)
      });

      if (fbRes.ok) {
        const nowTs = Math.floor(Date.now() / 1000);
        this.lastSync = nowTs;
        await fetch("/api/cloud-sync/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lastSync: nowTs })
        });
        this.updateUI();
        if (showToast) {
          alert(`✅ Successfully pushed ${sanitized.length} profiles to Cloud Room '${this.roomKey}'!`);
        }
      }
    } catch (err) {
      console.error("Cloud push failed:", err);
      if (showToast) alert("Failed to push to Cloud: " + err.message);
    } finally {
      setTimeout(() => {
        this.isSyncingLocal = false;
      }, 1500);
    }
  },

  async pullFromCloud(silent = false) {
    if (!this.roomKey) return;
    try {
      const base = (this.firebaseUrl || "https://user-ananlytics-default-rtdb.firebaseio.com").replace(/\/+$/, "");
      const cleanRoom = encodeURIComponent(this.roomKey.trim());
      const getUrl = `${base}/workspaces/${cleanRoom}/profiles.json`;

      const res = await fetch(getUrl);
      const data = await res.json();

      if (data === null) {
        if (!silent) alert(`Cloud Room '${this.roomKey}' has no profiles yet.\n\nClick 'Push to Cloud' to upload your local profiles to this room.`);
        return;
      }

      let profilesList = [];
      if (Array.isArray(data)) {
        profilesList = data.filter(Boolean);
      } else if (typeof data === "object") {
        profilesList = Object.values(data).filter(Boolean);
      }

      if (profilesList.length > 0) {
        await this.applyIncoming(profilesList);
        if (!silent) {
          alert(`✅ Successfully pulled ${profilesList.length} profiles from Cloud Room '${this.roomKey}'!`);
        }
      } else {
        if (!silent) alert("No profiles found in this Cloud Room.");
      }
    } catch (err) {
      if (!silent) alert("Failed to pull from Cloud: " + err.message);
    }
  },

  async disconnect() {
    if (this.eventSource) {
      try { this.eventSource.close(); } catch (e) {}
      this.eventSource = null;
    }
    this.enabled = false;
    await fetch("/api/cloud-sync/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: false })
    });
    this.updateUI();
  }
};

window.CloudSyncManager = CloudSyncManager;
