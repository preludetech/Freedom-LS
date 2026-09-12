(function () {
  "use strict";

  /**
   * Copy button for the ReferralCode change form.
   *
   * Each button names the id of the span holding the URL it copies, reads
   * that text and writes it to the clipboard, then announces success
   * through a shared polite live region. No inline handler, since
   * SECURE_CSP_REPORT_ONLY is one step from enforcement.
   */

  function init() {
    var buttons = document.querySelectorAll("button[data-copy-target]");
    if (!buttons.length) return;

    var live = document.createElement("div");
    live.setAttribute("aria-live", "polite");
    // sr-only is not in Unfold's compiled CSS, so the live region is
    // hidden with inline styles rather than a class.
    live.style.position = "absolute";
    live.style.width = "1px";
    live.style.height = "1px";
    live.style.overflow = "hidden";
    document.body.appendChild(live);

    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        var target = document.getElementById(button.dataset.copyTarget);
        if (!target || !navigator.clipboard) return;
        navigator.clipboard.writeText(target.textContent).then(function () {
          live.textContent = "Copied";
        });
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
