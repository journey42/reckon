/* Live-room outbox: hold a participant's writes on the device until they land.
 *
 * Why this exists: at a conference, several hundred phones share one access
 * point and the room page is used by people on marginal signal. A tap that has
 * to reach the server at that instant is a tap that silently does nothing. So
 * every participant write is recorded here first, in localStorage, and replayed
 * later — including across the page's own 20s auto-refresh, which destroys all
 * in-memory state.
 *
 * The queue is deliberately *desired state*, not a list of commands:
 *   { "<room slug>": { answer: {text, at}, edit: {text, at},
 *                      support: {reckoning_id, at}, draft: "..." } }
 * Only the newest intent of each kind is kept, and the server compares each one
 * against current state before acting. That is what makes replaying an intent
 * harmless, which matters more than anything else here: a write whose response
 * was lost looks identical, from the device's point of view, to a write that
 * never happened.
 *
 * Loaded on every page (see rhiz/rhiz.py). Outside /room/<slug> it does nothing
 * at all, because there is no room slug to key on.
 */
(function () {
  "use strict";

  var KEY = "rhiz_room_outbox_v2";
  var DRAFT = "draft";
  var KINDS = ["answer", "edit", "support"];
  var ANSWER_ID = "rhiz-answer";
  var EDIT_ID = "rhiz-edit";
  var NOTE_ID = "rhiz-outbox-note";
  var COUNT_ID = "rhiz-outbox-count";
  var SEND_ID = "rhiz-outbox-send";
  var BRIDGE_ID = "rhiz-outbox-payload";
  var SUBMIT_ID = "rhiz-submit-answer";
  var SAVE_ID = "rhiz-save-edit";
  // The support button carries the answer it backs in its own id:
  // "rhiz-support-1234" — ids pass through Reflex untouched, where a
  // custom attribute would not necessarily survive.
  var SUPPORT_ID = /^rhiz-support-(\d+)$/;
  var RETRY_MS = 15000;
  // How long to keep putting unsent typing back, for the reasons in restoreDraft.
  var RESTORE_MS = 8000;

  function store() {
    try {
      var parsed = JSON.parse(localStorage.getItem(KEY) || "{}");
      return parsed && typeof parsed === "object" && !Array.isArray(parsed)
        ? parsed
        : {};
    } catch (err) {
      // Quota exceeded or hand-edited storage: losing the queue must never
      // break the room for the person holding it.
      return {};
    }
  }

  function save(data) {
    try {
      localStorage.setItem(KEY, JSON.stringify(data));
    } catch (err) {
      /* nothing to do but carry on without it */
    }
  }

  function slug() {
    var match = (window.location.pathname || "").match(/^\/room\/([^/?#]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  /** This room's slot, or null when there is not one (and none was requested). */
  function slot(create) {
    var s = slug();
    if (!s) return null;
    var data = store();
    var room = data[s];
    if (!room || typeof room !== "object") {
      if (!create) return null;
      room = {};
      data[s] = room;
    }
    return { data: data, room: room, slug: s };
  }

  /** The revision the server has already accepted for this device. */
  function serverVersion() {
    var el = document.getElementById("rhiz-outbox-version");
    var v = el ? parseInt(el.value, 10) : 0;
    return isNaN(v) || v < 0 ? 0 : v;
  }

  function pendingCount() {
    var room = store()[slug()];
    if (!room || typeof room !== "object") return 0;
    var n = 0;
    for (var i = 0; i < KINDS.length; i++) {
      if (room[KINDS[i]] && typeof room[KINDS[i]] === "object") n++;
    }
    return n;
  }

  function put(kind, value) {
    var held = slot(true);
    if (!held) return;
    // Server-issued revision, not the phone's clock: the next intent is newer
    // than everything the server has accepted, so the server can reject an
    // older queued write instead of letting it overwrite a newer one.
    var next = Math.max(held.room.version || 0, serverVersion()) + 1;
    held.room.version = next;
    value.at = Date.now();
    value.version = next;
    held.room[kind] = value;
    save(held.data);
    paint();
  }

  /** Called by the server once it has settled an intent — applied, already
   *  applied, or refused for good. Nothing is cleared before that, because a
   *  cleared intent that never landed is a lost vote with no way to notice. */
  function clear(kinds) {
    var held = slot(false);
    if (!held) {
      paint();
      return;
    }
    var list = kinds && kinds.length ? kinds : KINDS.concat([DRAFT]);
    for (var i = 0; i < list.length; i++) delete held.room[list[i]];
    // Keep the revision even when nothing is queued: it is what makes the
    // next intent newer than everything already accepted. Only drop the slot
    // when there is neither an intent, a draft, nor a revision.
    var empty = true;
    for (var key in held.room) {
      if (Object.prototype.hasOwnProperty.call(held.room, key) && key !== "version") {
        empty = false;
        break;
      }
    }
    if (empty && !held.room.version) delete held.data[held.slug];
    save(held.data);
    paint();
  }

  /** Only the three intents, never the draft: unsent typing has no business
   *  being uploaded before the person chooses to send it. */
  function pendingJson() {
    var held = slot(false);
    if (!held) return "{}";
    var out = {};
    for (var i = 0; i < KINDS.length; i++) {
      var entry = held.room[KINDS[i]];
      if (entry && typeof entry === "object") out[KINDS[i]] = entry;
    }
    return JSON.stringify(out);
  }

  /** The server settled intents and told us its current revision. */
  window.rhizOutboxVersion = function (v) {
    var held = slot(false);
    if (!held) return;
    var n = parseInt(v, 10);
    if (isNaN(n) || n < 0) return;
    held.room.version = Math.max(held.room.version || 0, n);
    save(held.data);
  };

  function paint() {
    var n = pendingCount();
    var note = document.getElementById(NOTE_ID);
    var count = document.getElementById(COUNT_ID);
    if (count) {
      count.textContent =
        n === 1 ? "Waiting to send" : n + " waiting to send";
    }
    if (note) note.style.display = n ? "block" : "none";
  }

  function answerBox() {
    return document.getElementById(ANSWER_ID) || document.getElementById(EDIT_ID);
  }

  /**
   * Put unsent typing back after a reload.
   *
   * The text area is React-controlled, so assigning .value is not enough —
   * dispatching `input` is what makes Reflex's own on_change run and take the
   * words back into state.
   *
   * It is retried for a short window because one shot is not reliable: the text
   * area may not exist yet when this first runs (Reflex can mount after this
   * asset), and React writes its own — empty — value into the field when
   * hydration finishes, which can land *after* the words were put back. The
   * second of those only shows up when the machine is busy, which is how it
   * passed the first round of testing and then failed under load.
   *
   * The stored draft is re-read on every tick, so typing that clears the box or
   * replaces the draft wins immediately and is never refilled.
   */
  function restoreDraft(deadline) {
    var el = answerBox();
    var held = slot(false);
    var text =
      el && held && typeof held.room[DRAFT] === "string" ? held.room[DRAFT] : "";
    if (text && el.value !== text) {
      el.value = text;
      try {
        el.dispatchEvent(new Event("input", { bubbles: true }));
      } catch (err) {
        /* older browser: the words are still on screen, just not in state */
      }
    }
    if (Date.now() >= deadline) return;
    setTimeout(function () {
      restoreDraft(deadline);
    }, 300);
  }

  /**
   * Hand the queue to the server through the room page's hidden field.
   *
   * The native value setter is used because that field is React-controlled:
   * assigning ``.value`` directly is invisible to React, so its on_change —
   * which is the event that carries the queue into a state handler — would never
   * run. A fresh ``_n`` key is added so that two identical pushes still count as
   * a change; the server ignores keys it does not recognise.
   */
  function push() {
    var bridge = document.getElementById(BRIDGE_ID);
    if (!bridge || pendingCount() === 0) return;
    var payload = pendingJson();
    try {
      var parsed = JSON.parse(payload);
      parsed._n = Date.now();
      payload = JSON.stringify(parsed);
    } catch (err) {
      /* send it as it is; the server re-validates everything anyway */
    }
    try {
      var setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value"
      ).set;
      setter.call(bridge, payload);
    } catch (err) {
      bridge.value = payload;
    }
    try {
      bridge.dispatchEvent(new Event("input", { bubbles: true }));
    } catch (err) {
      /* nothing else to try */
    }
  }

  /** The retry path: push, and let the server decide what is settled. */
  function flush() {
    push();
  }

  function valueOf(id) {
    var el = document.getElementById(id);
    return el && typeof el.value === "string" ? el.value.trim() : "";
  }

  function saveDraft(text) {
    var held = slot(true);
    if (!held) return;
    if (text) held.room[DRAFT] = text;
    else delete held.room[DRAFT];
    if (!pendingCount() && !held.room[DRAFT] && !held.room.version) {
      delete held.data[held.slug];
    }
    save(held.data);
  }

  function init() {
    paint();
    restoreDraft(Date.now() + RESTORE_MS);
    if (window.__rhizOutboxBound) return;
    window.__rhizOutboxBound = true;

    document.addEventListener(
      "input",
      function (event) {
        var id = event.target && event.target.id;
        if (id === ANSWER_ID || id === EDIT_ID) {
          saveDraft(event.target.value || "");
        }
      },
      true
    );

    /*
     * Recording the tap. This is a plain DOM listener on purpose.
     *
     * It used to be an `rx.call_script(...)` chained in front of each submit
     * handler, and that is subtly wrong: a Reflex event is processed with the
     * server, so on a device that cannot reach the server the queueing step
     * never runs — the one moment it is needed. (Found by black-holing the
     * websocket rather than by switching the browser "offline", which leaves the
     * socket working and so hides the bug.)
     *
     * Capture phase, so it runs whatever else the button also does.
     */
    document.addEventListener(
      "click",
      function (event) {
        var target = event.target;
        var button =
          target && target.closest ? target.closest("button") : null;
        if (!button) return;
        if (button.id === SUBMIT_ID) {
          var answer = valueOf(ANSWER_ID);
          if (answer) put("answer", { text: answer });
          return;
        }
        if (button.id === SAVE_ID) {
          var edit = valueOf(EDIT_ID);
          if (edit) put("edit", { text: edit });
          return;
        }
        var backed = SUPPORT_ID.exec(button.id || "");
        if (backed) put("support", { reckoning_id: parseInt(backed[1], 10) });
      },
      true
    );

    // The moment signal returns, push — don't wait for the next retry tick.
    window.addEventListener("online", function () {
      paint();
      flush();
    });
    document.addEventListener("visibilitychange", function () {
      paint();
      if (!document.hidden) flush();
    });

    setInterval(function () {
      // Repaint every tick: this script can load before React has rendered the
      // banner or the answer box, and paint() is the only thing that re-links
      // them afterwards.
      paint();
      // Background tabs hold their peace and catch up when looked at again; a
      // room full of phones reloading every few seconds is its own outage.
      if (document.hidden || pendingCount() === 0) return;
      if (navigator.onLine === false) return;
      flush();
    }, RETRY_MS);
  }

  window.rhizOutboxClear = clear;
  window.rhizOutboxPush = push;
  window.rhizOutboxPendingJson = pendingJson;
  window.rhizOutboxPendingCount = pendingCount;
  window.rhizOutboxPaint = paint;
  window.rhizOutboxInit = init;

  // Self-start: the asset can arrive before React has rendered anything, and
  // the delegated listeners below work for elements mounted later.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
