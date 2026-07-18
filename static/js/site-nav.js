/**
 * Mobile hamburger navigation for the public site.
 */
(function () {
  const panel = document.querySelector("[data-nav-panel]");
  const toggles = document.querySelectorAll("[data-nav-toggle]");
  if (!panel || !toggles.length) return;

  const openLabel = "Ouvrir le menu";
  const closeLabel = "Fermer le menu";

  function setOpen(open) {
    panel.hidden = !open;
    document.body.classList.toggle("nav-open", open);
    toggles.forEach((btn) => {
      btn.classList.toggle("is-active", open);
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      btn.setAttribute("aria-label", open ? closeLabel : openLabel);
    });
  }

  toggles.forEach((btn) => {
    btn.addEventListener("click", () => setOpen(panel.hidden));
  });

  panel.querySelectorAll("[data-nav-close]").forEach((el) => {
    el.addEventListener("click", (e) => {
      if (el.tagName === "A") return; // let navigation happen, still close
      e.preventDefault();
      setOpen(false);
    });
  });

  // Close drawer when following an in-panel link
  panel.querySelectorAll("a[data-nav-close]").forEach((a) => {
    a.addEventListener("click", () => setOpen(false));
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.hidden) setOpen(false);
  });

  window.addEventListener("resize", () => {
    if (window.matchMedia("(min-width: 1024px)").matches && !panel.hidden) {
      setOpen(false);
    }
  });
})();
