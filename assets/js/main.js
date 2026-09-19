/* Notyga — progressive enhancement only.
   Every feature here is additive: with JS disabled the page still renders
   fully, reads correctly and every link works. */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---- Header: mark it once the page has scrolled off the top ---------- */
  var header = document.querySelector("[data-header]");
  if (header) {
    var setStuck = function () {
      header.classList.toggle("is-stuck", window.scrollY > 8);
    };
    setStuck();
    window.addEventListener("scroll", setStuck, { passive: true });
  }

  /* ---- Mobile navigation ---------------------------------------------- */
  var toggle = document.querySelector("[data-nav-toggle]");
  var panel = document.querySelector("[data-nav-panel]");

  if (toggle && panel) {
    var setNav = function (open) {
      toggle.setAttribute("aria-expanded", String(open));
      panel.classList.toggle("is-open", open);
    };

    toggle.addEventListener("click", function () {
      setNav(toggle.getAttribute("aria-expanded") !== "true");
    });

    // Close after following an in-page link, and on Escape.
    panel.addEventListener("click", function (e) {
      if (e.target.closest("a")) setNav(false);
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") setNav(false);
    });

    // Reset state when leaving the mobile breakpoint.
    window.matchMedia("(min-width: 901px)").addEventListener("change", function (e) {
      if (e.matches) setNav(false);
    });
  }

  /* ---- Scroll reveal ---------------------------------------------------
     The hiding styles are gated behind .js-reveal, which is only added when
     we know we can reveal again. */
  if ("IntersectionObserver" in window && !reduceMotion) {
    document.documentElement.classList.add("js-reveal");

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 }
    );

    document.querySelectorAll("[data-reveal]").forEach(function (el, i) {
      // Stagger siblings slightly so grids cascade instead of popping.
      var group = el.parentElement;
      var index = group ? Array.prototype.indexOf.call(group.children, el) : i;
      el.style.setProperty("--reveal-delay", Math.min(index, 6) * 70 + "ms");
      observer.observe(el);
    });
  }

  /* ---- Nav: highlight the section currently in view --------------------- */
  var navLinks = Array.prototype.slice.call(
    document.querySelectorAll(".nav__link[href^='#']")
  );

  if (navLinks.length && "IntersectionObserver" in window) {
    var sections = navLinks
      .map(function (link) {
        return document.querySelector(link.getAttribute("href"));
      })
      .filter(Boolean);

    var spy = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          navLinks.forEach(function (link) {
            link.setAttribute(
              "aria-current",
              link.getAttribute("href") === "#" + entry.target.id ? "true" : "false"
            );
          });
        });
      },
      { rootMargin: "-45% 0px -50% 0px" }
    );

    sections.forEach(function (s) {
      spy.observe(s);
    });
  }

  /* ---- Marquee: duplicate the track so the loop has no visible seam ----- */
  var track = document.querySelector("[data-marquee]");
  if (track && !reduceMotion) {
    track.innerHTML += track.innerHTML;
    track.setAttribute("aria-hidden", "true");
  }

  /* ---- Footer year ------------------------------------------------------ */
  document.querySelectorAll("[data-year]").forEach(function (el) {
    el.textContent = String(new Date().getFullYear());
  });
})();
