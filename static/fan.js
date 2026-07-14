/*
 * fan.js — chat UI for the MetLife Wayfinder fan surface.
 *
 * Flow: Firebase Anonymous Auth → GET /profile → onboarding-or-nav mode →
 *   send loop against POST /profile or POST /navigate with a rolling
 *   3-turn history (Entry #10). All bodies rendered via textContent; the
 *   SVG map is set via <img src="data:...base64,..."> from the server.
 *
 * DESIGN.md microcopy:
 *   placeholder = "Where are you, and where do you want to go?"
 *   loading = "Working out the route…"
 *   error (transient) = "Something went wrong. Try again."
 *   error (permanent) = server-provided message.
 */

(function () {
  "use strict";

  const HISTORY_TURNS = 3;
  const PLACEHOLDER_NAV = "Where are you, and where do you want to go?";
  const PLACEHOLDER_ONBOARD =
    "Tell me your section, language, and any accessibility needs.";

  const els = {
    messages: document.getElementById("messages"),
    input: document.getElementById("composer-input"),
    send: document.getElementById("composer-send"),
    form: document.getElementById("composer"),
    status: document.getElementById("status"),
  };

  const state = {
    mode: null, // "onboarding" | "nav"
    history: [], // ConversationTurn[]
    tokenProvider: null, // () => Promise<string>
  };

  // ---- Rendering -----------------------------------------------------------

  function setStatus(text) {
    els.status.textContent = text;
  }

  function scrollToBottom() {
    els.messages.scrollTop = els.messages.scrollHeight;
  }

  function appendBubble(cls, text) {
    const el = document.createElement("div");
    el.className = "msg " + cls;
    el.textContent = text;
    els.messages.appendChild(el);
    scrollToBottom();
    return el;
  }

  function appendGuide(text, routeImage) {
    const bubble = appendBubble("guide", text);
    if (routeImage) {
      const img = document.createElement("img");
      img.className = "route-img";
      img.alt = buildAltText(text);
      img.src = routeImage;
      bubble.appendChild(img);
    }
    return bubble;
  }

  // Alt text for the route SVG. The SVG's internal <title> is invisible to
  // screen readers when delivered via <img src="data:...">, so we derive an
  // alt string from the actual Guide-Agent directions and cap the length so
  // it stays a summary rather than a dumped paragraph.
  const ALT_MAX = 140;
  const ALT_PREFIX = "Route map: ";
  const ALT_FALLBACK = "Schematic map of the route through MetLife Stadium.";

  function buildAltText(directions) {
    if (typeof directions !== "string") {
      return ALT_FALLBACK;
    }
    const cleaned = directions.replace(/\s+/g, " ").trim();
    if (cleaned.length === 0) {
      return ALT_FALLBACK;
    }
    const bodyMax = ALT_MAX - ALT_PREFIX.length;
    const body = cleaned.length <= bodyMax
      ? cleaned
      : cleaned.slice(0, bodyMax - 1).trimEnd() + "…";
    return ALT_PREFIX + body;
  }

  function appendHint(text) {
    const el = document.createElement("div");
    el.className = "msg guide";
    const hint = document.createElement("span");
    hint.className = "hint";
    hint.textContent = text;
    el.appendChild(hint);
    els.messages.appendChild(el);
    scrollToBottom();
  }

  function appendError(text) {
    appendBubble("error", text);
  }

  // ---- Networking ----------------------------------------------------------

  async function apiFetch(path, opts) {
    const token = await state.tokenProvider();
    const headers = Object.assign(
      { "Content-Type": "application/json", Authorization: "Bearer " + token },
      (opts && opts.headers) || {}
    );
    const init = Object.assign({}, opts, { headers: headers });
    const resp = await fetch(path, init);
    let body = null;
    try {
      body = await resp.json();
    } catch (_) {
      body = null;
    }
    return { status: resp.status, body: body };
  }

  function errorMessage(body, fallback) {
    if (body && body.type === "error" && typeof body.message === "string") {
      return body.message;
    }
    return fallback;
  }

  // ---- Modes ---------------------------------------------------------------

  function setInputEnabled(enabled, placeholder) {
    els.input.disabled = !enabled;
    els.send.disabled = !enabled;
    if (placeholder) {
      els.input.placeholder = placeholder;
    }
    if (enabled) {
      els.input.focus();
    }
  }

  function enterOnboarding() {
    state.mode = "onboarding";
    setInputEnabled(true, PLACEHOLDER_ONBOARD);
    setStatus("New here — let's set up your profile.");
    appendHint(
      "Tell me your section, preferred language, and any accessibility needs. Example: \"Section 128, English, no stairs.\""
    );
  }

  function enterNav(profile) {
    state.mode = "nav";
    state.history = [];
    setInputEnabled(true, PLACEHOLDER_NAV);
    setStatus("Section " + profile.seat_section + " · " + profile.preferred_language);
    appendHint("Ready. Ask for directions to anywhere in the stadium.");
  }

  async function bootstrapMode() {
    setStatus("Loading your profile…");
    const { status, body } = await apiFetch("/profile", { method: "GET" });
    if (status === 200 && body && body.seat_section) {
      enterNav(body);
      return;
    }
    if (status === 404) {
      enterOnboarding();
      return;
    }
    setStatus("Offline");
    appendError(errorMessage(body, "Something went wrong. Try again."));
  }

  // ---- Send handlers -------------------------------------------------------

  function pushHistory(query, directions) {
    state.history.push({ role: "user", content: query });
    state.history.push({ role: "assistant", content: directions });
    while (state.history.length > HISTORY_TURNS * 2) {
      state.history.shift();
    }
  }

  async function handleOnboardSend(text) {
    const { status, body } = await apiFetch("/profile", {
      method: "POST",
      body: JSON.stringify({ nl_input: text }),
    });
    if (status === 200 && body && body.seat_section) {
      appendGuide(
        "Profile saved: section " +
          body.seat_section +
          ", language " +
          body.preferred_language +
          ".",
        null
      );
      enterNav(body);
      return;
    }
    if (status === 200 && body && body.type === "profile_incomplete") {
      appendGuide(body.followup_question, null);
      return;
    }
    if (status === 200 && body && body.type === "profile_failed") {
      appendError(
        "I couldn't understand that. Try naming your section, e.g. \"128\"."
      );
      return;
    }
    appendError(errorMessage(body, "Something went wrong. Try again."));
  }

  async function handleNavSend(text) {
    const { status, body } = await apiFetch("/navigate", {
      method: "POST",
      body: JSON.stringify({ query: text, history: state.history }),
    });
    if (status === 200 && body && typeof body.directions === "string") {
      appendGuide(body.directions, body.route_image || null);
      pushHistory(text, body.directions);
      return;
    }
    if (status === 404) {
      appendError(errorMessage(body, "Your profile is gone. Reload the page."));
      return;
    }
    if (status >= 400 && status < 500) {
      appendError(
        errorMessage(
          body,
          "I couldn't find that location. Try a nearby gate or section."
        )
      );
      return;
    }
    appendError(errorMessage(body, "Something went wrong. Try again."));
  }

  async function onSubmit(event) {
    event.preventDefault();
    const text = els.input.value.trim();
    if (!text) {
      return;
    }
    appendBubble("fan", text);
    els.input.value = "";
    setInputEnabled(false, els.input.placeholder);
    setStatus("Working out the route…");
    try {
      if (state.mode === "onboarding") {
        await handleOnboardSend(text);
      } else {
        await handleNavSend(text);
      }
    } catch (err) {
      appendError("Something went wrong. Try again.");
    } finally {
      setInputEnabled(true, els.input.placeholder);
      setStatus(state.mode === "nav" ? "Online" : "Setting up profile");
    }
  }

  // ---- Auth bootstrap ------------------------------------------------------

  function ensureConfig() {
    if (!window.FIREBASE_CONFIG || !window.FIREBASE_CONFIG.apiKey) {
      throw new Error("Missing FIREBASE_CONFIG. Fill in static/firebase-config.js.");
    }
    return window.FIREBASE_CONFIG;
  }

  async function initAuth() {
    const config = ensureConfig();
    // eslint-disable-next-line no-undef
    firebase.initializeApp(config);
    // eslint-disable-next-line no-undef
    const auth = firebase.auth();
    await auth.signInAnonymously();
    const user = auth.currentUser;
    if (!user) {
      throw new Error("Anonymous sign-in returned no user.");
    }
    state.tokenProvider = function () {
      return auth.currentUser.getIdToken(false);
    };
  }

  async function main() {
    els.form.addEventListener("submit", onSubmit);
    try {
      await initAuth();
    } catch (err) {
      setStatus("Auth unavailable");
      appendError(
        "Could not sign in. Check the Firebase config, then reload."
      );
      return;
    }
    await bootstrapMode();
  }

  document.addEventListener("DOMContentLoaded", function () {
    main();
  });
})();
