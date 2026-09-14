// automation_hud.js - In-Browser Guided Control Layer for GitHub Actions Automation
(function() {
  if (window !== window.top) return; // Only run on top-level frame
  if (window.__SHADDA_AUTOMATION_HUD_INITED__) return;
  window.__SHADDA_AUTOMATION_HUD_INITED__ = true;

  const APP_API = "http://127.0.0.1:5055";
  let _lastStepId = null;
  let _isMinimized = false;
  let _hudContainer = null;
  let _cachedProfileId = window.__SHADDA_PROFILE_ID__ || null;

  async function fetchActiveState() {
    try {
      let url = `${APP_API}/api/automation/active-session`;
      if (_cachedProfileId) {
        url = `${APP_API}/api/automation/${_cachedProfileId}/state`;
      }
      const res = await fetch(url, { headers: { "X-App-Request": "HUD" } });
      if (!res.ok) return null;
      const data = await res.json();
      if (data && data.profileId) {
        _cachedProfileId = data.profileId;
      }
      return data;
    } catch (e) {
      return null;
    }
  }

  async function sendAction(actionType) {
    if (!_cachedProfileId) return;
    try {
      const btn = document.getElementById("shadda-hud-continue-btn");
      if (btn) {
        btn.disabled = true;
        btn.textContent = "⏳ Notifying GitHub Actions...";
      }
      const res = await fetch(`${APP_API}/api/automation/${_cachedProfileId}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: actionType || "continue" })
      });
      const data = await res.json();
      if (data.success) {
        updateHUD();
      }
    } catch (e) {
      alert("Failed to notify GitHub Actions: " + e.message);
    }
  }

  function createHUD() {
    if (_hudContainer) return;
    _hudContainer = document.createElement("div");
    _hudContainer.id = "shadda-automation-hud";
    _hudContainer.style.cssText = `
      position: fixed;
      top: 14px;
      right: 18px;
      z-index: 2147483647;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      font-size: 13px;
      color: #f8fafc;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.4);
      user-select: none;
      max-width: 440px;
      width: calc(100vw - 36px);
    `;

    document.documentElement.appendChild(_hudContainer);
  }

  function renderHUD(state) {
    createHUD();
    if (!state || !state.active) {
      _hudContainer.style.display = "none";
      return;
    }
    _hudContainer.style.display = "block";

    const step = state.currentStep || {};
    const isWaiting = step.requiresManual;
    const isDone = state.completed;
    const stepNum = (state.currentStepIndex || 0) + 1;
    const totalSteps = state.totalSteps || 1;
    const progressPct = Math.min(100, Math.round((stepNum / totalSteps) * 100));

    // Check auto-navigation
    if (step.targetUrl && !isDone && _lastStepId !== step.id) {
      _lastStepId = step.id;
      const cur = window.location.href.toLowerCase();
      const target = step.targetUrl.toLowerCase();
      const curHost = window.location.hostname;
      try {
        const targetHost = new URL(step.targetUrl).hostname;
        if (curHost !== targetHost && !cur.startsWith(target)) {
          console.log("[GitHub Actions HUD] Auto-navigating to:", step.targetUrl);
          setTimeout(() => {
            window.location.href = step.targetUrl;
          }, 1200);
        }
      } catch (e) {}
    }

    if (_isMinimized) {
      _hudContainer.innerHTML = `
        <div style="background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(12px); border: 1px solid rgba(14, 165, 233, 0.4); border-radius: 9999px; padding: 8px 16px; display: flex; align-items: center; gap: 10px; cursor: pointer; box-shadow: 0 4px 15px rgba(0,0,0,0.5);" onclick="window.__SHADDA_TOGGLE_HUD__()">
          <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: ${isWaiting ? '#f59e0b' : '#10b981'}; box-shadow: 0 0 8px ${isWaiting ? '#f59e0b' : '#10b981'};"></span>
          <span style="font-weight: 700; font-size: 12px; color: #38bdf8;">🤖 GitHub Actions</span>
          <span style="font-size: 11px; color: #cbd5e1;">Step ${stepNum}/${totalSteps}</span>
          <span style="color: #94a3b8; font-size: 12px; margin-left: 4px;">▲</span>
        </div>
      `;
      return;
    }

    _hudContainer.innerHTML = `
      <div style="background: rgba(15, 23, 42, 0.96); backdrop-filter: blur(16px); border: 1px solid ${isWaiting ? 'rgba(245, 158, 11, 0.5)' : 'rgba(14, 165, 233, 0.35)'}; border-radius: 14px; overflow: hidden; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.6);">
        <!-- Top Bar -->
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: rgba(30, 41, 59, 0.7); border-bottom: 1px solid rgba(255, 255, 255, 0.08);">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: ${isWaiting ? '#f59e0b' : '#10b981'}; box-shadow: 0 0 8px ${isWaiting ? '#f59e0b' : '#10b981'}; animation: pulse 2s infinite;"></span>
            <strong style="font-size: 12px; letter-spacing: 0.3px; color: #f8fafc; display: flex; align-items: center; gap: 6px;">
              <span>🤖 GitHub Actions Engine</span>
              <span style="font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 4px; background: rgba(14, 165, 233, 0.2); color: #38bdf8; border: 1px solid rgba(14, 165, 233, 0.3);">${state.githubRunId || 'Running'}</span>
            </strong>
          </div>
          <div style="display: flex; align-items: center; gap: 6px;">
            <button onclick="window.__SHADDA_TOGGLE_HUD__()" style="background: transparent; border: none; color: #94a3b8; cursor: pointer; font-size: 14px; padding: 2px 6px; border-radius: 4px;" title="Minimize HUD">_</button>
          </div>
        </div>

        <!-- Progress Track -->
        <div style="height: 3px; background: rgba(51, 65, 85, 0.5); width: 100%;">
          <div style="height: 100%; width: ${progressPct}%; background: linear-gradient(90deg, #0ea5e9, #38bdf8); transition: width 0.4s ease;"></div>
        </div>

        <!-- Step Content -->
        <div style="padding: 14px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
            <span style="font-size: 11px; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.5px;">
              ${step.platformName || 'Task'} &bull; Step ${stepNum} of ${totalSteps}
            </span>
            <span style="font-size: 11px; color: #94a3b8;">${state.elapsedSeconds || 0}s</span>
          </div>

          <h4 style="margin: 0 0 6px 0; font-size: 14px; font-weight: 700; color: #ffffff; line-height: 1.3;">
            ${step.title || 'Processing Automation...'}
          </h4>

          <p style="margin: 0 0 10px 0; font-size: 12px; color: #cbd5e1; line-height: 1.45;">
            ${step.description || ''}
          </p>

          ${step.targetUrl ? `
            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 10px; padding: 6px 10px; background: rgba(0,0,0,0.25); border-radius: 6px; font-family: monospace; font-size: 11px; color: #94a3b8;">
              <span style="color: #38bdf8;">🔗 Required Link:</span>
              <a href="${step.targetUrl}" style="color: #38bdf8; text-decoration: underline; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 250px;">${step.targetUrl}</a>
            </div>
          ` : ''}

          ${isWaiting ? `
            <!-- Manual Action Card -->
            <div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 8px; padding: 10px 12px; margin-bottom: 12px;">
              <div style="display: flex; align-items: center; gap: 6px; font-weight: 700; font-size: 12px; color: #f59e0b; margin-bottom: 4px;">
                <span>✋ Action Required from You:</span>
              </div>
              <div style="font-size: 12px; color: #fef08a; line-height: 1.4; margin-bottom: 10px;">
                ${step.instruction || 'Please complete the manual step in this window.'}
              </div>
              <button id="shadda-hud-continue-btn" onclick="window.__SHADDA_CONTINUE__()" style="width: 100%; background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: #ffffff; font-weight: 700; font-size: 12px; border: none; border-radius: 6px; padding: 8px 12px; cursor: pointer; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3); transition: transform 0.1s;">
                ✅ I Have Completed This Step — Continue Automation
              </button>
            </div>
          ` : ''}

          ${step.nextStep ? `
            <div style="font-size: 11px; color: #64748b; display: flex; align-items: center; gap: 5px; border-top: 1px solid rgba(255, 255, 255, 0.06); padding-top: 8px;">
              <span style="font-weight: 600; color: #94a3b8;">Next:</span>
              <span>${step.nextStep}</span>
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }

  window.__SHADDA_TOGGLE_HUD__ = function() {
    _isMinimized = !_isMinimized;
    updateHUD();
  };

  window.__SHADDA_CONTINUE__ = function() {
    sendAction("continue");
  };

  async function updateHUD() {
    const state = await fetchActiveState();
    renderHUD(state);
  }

  // Initial check & interval
  setTimeout(updateHUD, 800);
  setInterval(updateHUD, 1800);
})();
