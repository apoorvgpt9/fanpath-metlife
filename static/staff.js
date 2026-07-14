/*
 * staff.js — closure toggle panel.
 *
 * Auth model: shared STAFF_TOKEN (DECISIONS.md Entry #18). Entered per
 * session, stored in sessionStorage (never localStorage — the token
 * disappears when the tab closes). No token is ever put in the URL.
 */

(function () {
  "use strict";

  const STORAGE_KEY = "fanpath.staff_token";

  const els = {
    status: document.getElementById("status"),
    gate: document.getElementById("token-gate"),
    tokenForm: document.getElementById("token-form"),
    tokenInput: document.getElementById("token-input"),
    tokenError: document.getElementById("token-error"),
    body: document.getElementById("staff-body"),
    list: document.getElementById("closures-list"),
    addForm: document.getElementById("add-form"),
    addType: document.getElementById("add-type"),
    addId: document.getElementById("add-id"),
    addError: document.getElementById("add-error"),
  };

  function getToken() {
    return sessionStorage.getItem(STORAGE_KEY);
  }

  function setToken(value) {
    if (value) {
      sessionStorage.setItem(STORAGE_KEY, value);
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  }

  function showError(el, text) {
    if (!text) {
      el.hidden = true;
      el.textContent = "";
      return;
    }
    el.hidden = false;
    el.textContent = text;
  }

  function setStatus(text) {
    els.status.textContent = text;
  }

  async function apiFetch(method, body) {
    const token = getToken();
    const init = {
      method: method,
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + (token || ""),
      },
    };
    if (body !== undefined) {
      init.body = JSON.stringify(body);
    }
    const resp = await fetch("/staff/closures", init);
    let parsed = null;
    try {
      parsed = await resp.json();
    } catch (_) {
      parsed = null;
    }
    return { status: resp.status, body: parsed };
  }

  function errorMessage(body, fallback) {
    if (body && body.type === "error" && typeof body.message === "string") {
      return body.message;
    }
    return fallback;
  }

  function renderClosures(state) {
    els.list.textContent = "";
    const nodes = state.closed_nodes || [];
    const edges = state.closed_edges || [];
    const count = nodes.length + edges.length;
    setStatus(count === 0 ? "No closures active." : count + " closure(s) active.");
    if (count === 0) {
      const li = document.createElement("li");
      li.textContent = "No closures active.";
      els.list.appendChild(li);
      return;
    }
    nodes.forEach(function (id) {
      appendRow(id, "node");
    });
    edges.forEach(function (id) {
      appendRow(id, "edge");
    });
  }

  function appendRow(targetId, targetType) {
    const li = document.createElement("li");
    const label = document.createElement("span");
    label.textContent = targetId;
    const kind = document.createElement("span");
    kind.className = "kind";
    kind.textContent = targetType === "node" ? "zone" : "path";
    const btn = document.createElement("button");
    btn.className = "danger";
    btn.type = "button";
    btn.textContent = "Reopen";
    btn.addEventListener("click", function () {
      openClosure(targetId, targetType, btn);
    });
    li.appendChild(label);
    li.appendChild(kind);
    li.appendChild(btn);
    els.list.appendChild(li);
  }

  async function loadClosures() {
    setStatus("Loading closures…");
    const { status, body } = await apiFetch("GET");
    if (status === 200 && body) {
      renderClosures(body);
      return true;
    }
    if (status === 401) {
      setToken(null);
      showGate("Token rejected. Try again.");
      return false;
    }
    setStatus("Offline");
    showError(els.addError, errorMessage(body, "Could not load closures."));
    return false;
  }

  async function openClosure(targetId, targetType, btn) {
    btn.disabled = true;
    const { status, body } = await apiFetch("POST", {
      target_id: targetId,
      target_type: targetType,
      action: "open",
    });
    if (status === 200 && body) {
      renderClosures(body);
      return;
    }
    btn.disabled = false;
    showError(els.addError, errorMessage(body, "Could not reopen."));
  }

  async function handleAdd(event) {
    event.preventDefault();
    showError(els.addError, null);
    const payload = {
      target_id: els.addId.value.trim(),
      target_type: els.addType.value,
      action: "close",
    };
    if (!payload.target_id) {
      return;
    }
    const { status, body } = await apiFetch("POST", payload);
    if (status === 200 && body) {
      renderClosures(body);
      els.addId.value = "";
      return;
    }
    showError(els.addError, errorMessage(body, "Could not add closure."));
  }

  async function handleTokenSubmit(event) {
    event.preventDefault();
    const value = els.tokenInput.value.trim();
    if (!value) {
      return;
    }
    setToken(value);
    showError(els.tokenError, null);
    const ok = await loadClosures();
    if (ok) {
      hideGate();
    }
  }

  function showGate(errorText) {
    els.gate.hidden = false;
    els.body.hidden = true;
    if (errorText) {
      showError(els.tokenError, errorText);
    } else {
      showError(els.tokenError, null);
    }
    els.tokenInput.value = "";
    els.tokenInput.focus();
    setStatus("");
  }

  function hideGate() {
    els.gate.hidden = true;
    els.body.hidden = false;
    els.addId.focus();
  }

  async function main() {
    els.tokenForm.addEventListener("submit", handleTokenSubmit);
    els.addForm.addEventListener("submit", handleAdd);
    if (getToken()) {
      const ok = await loadClosures();
      if (ok) {
        hideGate();
        return;
      }
    }
    showGate(null);
  }

  document.addEventListener("DOMContentLoaded", function () {
    main();
  });
})();
