/*
 * Application shell hamburger/drawer behaviour (PID §16.2).
 *
 * Minimal vanilla JavaScript - no framework, no build step (ADR-0001).
 * This script ONLY opens/closes the sidebar presentation at narrow
 * viewports. It never decides whether a nav item is visible or a route is
 * reachable - every link this drawer shows or hides was already filtered
 * server-side by `entitlements.navigation.build_navigation_tree` before
 * this HTML ever reached the browser (PID §4.5 "no client-side
 * entitlement logic"). Removing this file entirely would only make the
 * sidebar always visible/always static - it would never grant or hide any
 * capability.
 */
(function () {
  "use strict";

  var toggle = document.getElementById("shell-nav-toggle");
  var sidebar = document.getElementById("shell-sidebar");
  var overlay = document.getElementById("shell-nav-overlay");

  if (!toggle || !sidebar || !overlay) {
    return;
  }

  var OPEN_CLASS = "shell-sidebar--open";

  function isOpen() {
    return sidebar.classList.contains(OPEN_CLASS);
  }

  function openDrawer() {
    sidebar.classList.add(OPEN_CLASS);
    overlay.hidden = false;
    toggle.setAttribute("aria-expanded", "true");

    var firstLink = sidebar.querySelector(".shell-nav__link");
    if (firstLink) {
      firstLink.focus();
    }
  }

  function closeDrawer(options) {
    var returnFocus = !options || options.returnFocus !== false;
    sidebar.classList.remove(OPEN_CLASS);
    overlay.hidden = true;
    toggle.setAttribute("aria-expanded", "false");

    if (returnFocus) {
      toggle.focus();
    }
  }

  toggle.addEventListener("click", function () {
    if (isOpen()) {
      closeDrawer({ returnFocus: false });
    } else {
      openDrawer();
    }
  });

  overlay.addEventListener("click", function () {
    closeDrawer();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && isOpen()) {
      closeDrawer();
    }
  });
})();
