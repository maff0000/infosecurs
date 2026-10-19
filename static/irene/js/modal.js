/*
 * IRENE modal behaviour (M010C PID §1; M010-UX-CUSTOMER-JOURNEYS.md §1).
 *
 * Minimal vanilla JavaScript - no framework, no build step (ADR-0001),
 * mirroring static/organisations/js/shell.js's own documented pattern.
 * This script ONLY opens/closes/tab-switches the presentation of markup
 * that is ALWAYS already fully present and server-rendered in the page
 * (irene.views.build_modal_context) - removing this file entirely would
 * leave the modal's content visible as an ordinary page section (no JS
 * fallback dead end), never hide or grant any capability. Entitlement is
 * decided server-side only (entitlements.capabilities.has_capability) -
 * this script never makes an access-control decision.
 */
(function () {
  "use strict";

  var modal = document.getElementById("irene-modal");
  if (!modal) {
    return;
  }

  var openButton = document.getElementById("irene-open-trigger");
  var closeButton = document.getElementById("irene-modal-close");
  var overlay = document.getElementById("irene-modal-overlay");
  var tabButtons = modal.querySelectorAll("[data-irene-tab]");
  var panels = modal.querySelectorAll("[data-irene-panel]");
  var lastFocused = null;
  var focusWasGrabbed = false;

  function isOpen() {
    return !modal.hidden;
  }

  function selectTab(name) {
    for (var i = 0; i < tabButtons.length; i++) {
      var isSelected = tabButtons[i].getAttribute("data-irene-tab") === name;
      tabButtons[i].setAttribute("aria-selected", isSelected ? "true" : "false");
      tabButtons[i].tabIndex = isSelected ? 0 : -1;
    }
    for (var j = 0; j < panels.length; j++) {
      panels[j].hidden = panels[j].getAttribute("data-irene-panel") !== name;
    }
  }

  function openModal(tabName, options) {
    // `grabFocus` defaults true (a real user gesture - the trigger
    // button, or a "?irene=open" direct-URL/redirect-back landing -
    // opened this modal, so moving focus into it is expected and
    // correct). The unsolicited AUTO-open path (below) passes `false`:
    // forcing focus into a dialog the instant the page loads, before
    // the user has done anything at all, is itself a disorienting
    // pattern several accessibility guidelines caution against - and,
    // separately, a real, reproduced Chromium quirk means calling
    // `.blur()` to later RESTORE focus to a `<body>` that was never
    // actually focus()'d by a real action leaves the browser's internal
    // sequential-tab-navigation position still anchored at the element
    // that was last really focused (here, the modal's own now-hidden
    // heading) rather than genuinely back at the top of the document -
    // so the very next real Tab press silently does nothing instead of
    // reaching the page's own skip-link (found by this package's own
    // real-browser regression testing against this codebase's
    // PRE-EXISTING keyboard-accessibility acceptance tests). Never
    // grabbing focus on an unsolicited auto-open avoids this class of
    // problem entirely, and the modal is still fully visible/readable
    // and keyboard-reachable via its own trigger button regardless.
    var grabFocus = !options || options.grabFocus !== false;
    focusWasGrabbed = grabFocus;
    if (grabFocus) {
      lastFocused = document.activeElement;
    }
    modal.hidden = false;
    if (overlay) {
      overlay.hidden = false;
    }
    if (openButton) {
      openButton.setAttribute("aria-expanded", "true");
    }
    selectTab(tabName || "continue");
    if (grabFocus) {
      var heading = modal.querySelector("h2, [tabindex]");
      if (heading) {
        heading.focus();
      }
    }
  }

  function closeModal() {
    modal.hidden = true;
    if (overlay) {
      overlay.hidden = true;
    }
    if (openButton) {
      openButton.setAttribute("aria-expanded", "false");
    }
    // Only touch focus at all if THIS open genuinely grabbed it
    // (`openModal`'s own `grabFocus` - see that function's docstring).
    // An unsolicited auto-open never moved focus away from wherever it
    // already was, so there is nothing to restore - leaving focus alone
    // on close is correct, and avoids the real Chromium quirk documented
    // above `openModal` (restoring focus to a never-really-focused
    // `<body>` via blur() leaves the browser's internal tab-sequence
    // position wrong for the NEXT real Tab press).
    if (!focusWasGrabbed) {
      return;
    }
    if (document.activeElement && typeof document.activeElement.blur === "function") {
      document.activeElement.blur();
    }
    if (lastFocused && lastFocused !== document.body && typeof lastFocused.focus === "function") {
      lastFocused.focus();
    } else if (openButton && lastFocused !== document.body) {
      openButton.focus();
    }
  }

  if (openButton) {
    openButton.addEventListener("click", function () {
      if (isOpen()) {
        closeModal();
      } else {
        openModal();
      }
    });
  }

  if (closeButton) {
    closeButton.addEventListener("click", closeModal);
  }

  if (overlay) {
    overlay.addEventListener("click", closeModal);
  }

  for (var k = 0; k < tabButtons.length; k++) {
    tabButtons[k].addEventListener("click", function (event) {
      selectTab(event.currentTarget.getAttribute("data-irene-tab"));
      event.currentTarget.focus();
    });
  }

  // Focus trap while open (M010-UX-CUSTOMER-JOURNEYS.md §1 "correct focus
  // trap while active, focus restoration on close, keyboard Escape").
  document.addEventListener("keydown", function (event) {
    if (!isOpen()) {
      return;
    }
    if (event.key === "Escape") {
      closeModal();
      return;
    }
    if (event.key !== "Tab") {
      return;
    }
    var candidates = modal.querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    // Only elements actually reachable by a real Tab press right now -
    // a hidden tab panel's own buttons/inputs match the selector above
    // but are never really focusable (offsetParent is null for any
    // display:none ancestor, which [hidden]/.irene-panel[hidden] sets),
    // so they must be excluded or the trap's own first/last boundaries
    // would point at an unreachable element and let real Tab escape past
    // the true last VISIBLE one.
    var focusable = [];
    for (var f = 0; f < candidates.length; f++) {
      if (candidates[f].offsetParent !== null) {
        focusable.push(candidates[f]);
      }
    }
    if (focusable.length === 0) {
      return;
    }
    var first = focusable[0];
    var last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  // Direct-URL-enforcement / redirect-back handling (irene.views.workspace,
  // irene.views.ask/confirm_task all redirect to "?irene=open[&irene_tab=X]").
  var params = new URLSearchParams(window.location.search);
  if (params.get("irene") === "open") {
    openModal(params.get("irene_tab"));
  } else if (modal.getAttribute("data-auto-open") === "true") {
    // Unsolicited auto-open (no real user gesture preceded this) - see
    // openModal's own docstring for why this never grabs focus.
    openModal("continue", { grabFocus: false });
  }
})();
