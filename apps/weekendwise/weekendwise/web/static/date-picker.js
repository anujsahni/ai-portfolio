// In-page calendar for the form's <input type="date"> fields.
//
// Why: Chrome draws its built-in date picker as a separate OS window, which can open on the
// wrong display on multi-monitor Macs (same issue as native <select> popups; see
// select-menu.js). This calendar is part of the page, so it opens right under its field.
//
// The native date input stays visible for typing and is still the source of truth, so
// .value, min/max, "required" and the app's own validation keep working unchanged.
(function () {
  "use strict";

  const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
  let openPicker = null;

  const pad = (n) => String(n).padStart(2, "0");
  const toIso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const parse = (s) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || "");
    return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : null;
  };
  const sameDay = (a, b) => a && b && a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
  const addMonths = (d, n) => {
    const target = new Date(d.getFullYear(), d.getMonth() + n, 1);
    const last = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
    return new Date(target.getFullYear(), target.getMonth(), Math.min(d.getDate(), last));
  };

  function enhance(input) {
    const field = input.closest(".input-with-icon");
    if (!field || input.dataset.enhanced) return;
    input.dataset.enhanced = "1";
    field.classList.add("date-field");

    // Start and end of a trip share a .date-pair, so the calendar can shade the range.
    const pair = Array.from((input.closest(".date-pair") || field).querySelectorAll('input[type="date"]'));
    const name = input.getAttribute("aria-label") || "date";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "date-button";
    button.setAttribute("aria-label", `Choose ${name.toLowerCase()}`);
    button.setAttribute("aria-haspopup", "dialog");
    button.setAttribute("aria-expanded", "false");
    button.innerHTML = '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><rect x="2" y="3" width="12" height="11" rx="2" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M2 6.5h12M5.5 1.5v3M10.5 1.5v3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>';
    input.after(button);

    const pop = document.createElement("div");
    pop.className = "date-pop";
    pop.setAttribute("role", "dialog");
    pop.setAttribute("aria-label", `Choose ${name.toLowerCase()}`);
    pop.hidden = true;
    pop.innerHTML = `
      <div class="date-head">
        <button type="button" class="date-nav" data-step="-1" aria-label="Previous month">‹</button>
        <strong class="date-title" aria-live="polite"></strong>
        <button type="button" class="date-nav" data-step="1" aria-label="Next month">›</button>
      </div>
      <div class="date-grid" role="grid"></div>`;
    field.append(pop);
    const title = pop.querySelector(".date-title");
    const grid = pop.querySelector(".date-grid");

    let view = null; // first day of the month on screen
    let focus = null; // day with keyboard focus

    function bounds() {
      let min = parse(input.min);
      const max = parse(input.max);
      // The end date can't be before the start date.
      const start = pair.indexOf(input) > 0 ? parse(pair[0].value) : null;
      if (start && (!min || start > min)) min = start;
      return { min, max };
    }

    function render() {
      const { min, max } = bounds();
      const selected = parse(input.value);
      const [start, end] = pair.length === 2 ? pair.map((el) => parse(el.value)) : [null, null];
      const today = new Date();
      title.textContent = `${MONTHS[view.getMonth()]} ${view.getFullYear()}`;
      const first = addDays(view, -view.getDay());
      let html = WEEKDAYS.map((w) => `<span class="date-dow" role="columnheader">${w}</span>`).join("");
      for (let i = 0; i < 42; i += 1) {
        const day = addDays(first, i);
        const out = (min && day < min) || (max && day > max);
        const classes = ["date-day"];
        if (day.getMonth() !== view.getMonth()) classes.push("other");
        if (sameDay(day, today)) classes.push("today");
        if (sameDay(day, selected)) classes.push("selected");
        if (start && end && start <= end && day >= start && day <= end) {
          classes.push("in-range");
          if (sameDay(day, start)) classes.push("range-start");
          if (sameDay(day, end)) classes.push("range-end");
        }
        const label = day.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
        html += `<button type="button" role="gridcell" class="${classes.join(" ")}" data-date="${toIso(day)}" tabindex="${sameDay(day, focus) ? 0 : -1}"`
          + ` aria-label="${label}" aria-selected="${sameDay(day, selected)}"${out ? " disabled" : ""}>${day.getDate()}</button>`;
      }
      grid.innerHTML = html;
    }

    function clamp(day) {
      const { min, max } = bounds();
      if (min && day < min) return min;
      if (max && day > max) return max;
      return day;
    }

    function moveFocus(day) {
      focus = day;
      if (day.getMonth() !== view.getMonth() || day.getFullYear() !== view.getFullYear()) view = new Date(day.getFullYear(), day.getMonth(), 1);
      render();
      grid.querySelector(`[data-date="${toIso(day)}"]`)?.focus();
    }

    function open() {
      if (openPicker && openPicker !== api) openPicker.close(false);
      focus = parse(input.value) || (pair[0] !== input && parse(pair[0].value)) || new Date();
      const { min, max } = bounds();
      if (min && focus < min) focus = min;
      if (max && focus > max) focus = max;
      view = new Date(focus.getFullYear(), focus.getMonth(), 1);
      render();
      pop.hidden = false;
      field.classList.add("open");
      button.setAttribute("aria-expanded", "true");
      // Keep the calendar on screen: align right if it would overflow, open upward if no room below.
      field.classList.remove("align-right", "open-up");
      const rect = field.getBoundingClientRect();
      if (rect.left + pop.offsetWidth > window.innerWidth - 8) field.classList.add("align-right");
      if (window.innerHeight - rect.bottom < pop.offsetHeight + 12 && rect.top > pop.offsetHeight + 12) field.classList.add("open-up");
      grid.querySelector('[tabindex="0"]')?.focus({ preventScroll: true });
      openPicker = api;
    }

    function close(returnFocus = true) {
      if (pop.hidden) return;
      pop.hidden = true;
      field.classList.remove("open", "open-up", "align-right");
      button.setAttribute("aria-expanded", "false");
      if (openPicker === api) openPicker = null;
      if (returnFocus) button.focus();
    }

    function choose(iso) {
      input.value = iso;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      close(false);
      // After picking a start date, move straight on to the end date.
      const next = pair[pair.indexOf(input) + 1];
      if (next && next._datePicker) next._datePicker.open();
      else input.focus();
    }

    const api = { open, close, contains: (node) => field.contains(node) };
    input._datePicker = api;

    button.addEventListener("click", () => (pop.hidden ? open() : close()));
    field.querySelector(".field-icon")?.addEventListener("mousedown", (e) => { e.preventDefault(); pop.hidden ? open() : close(); });
    // Keyboard shortcuts that would open Chrome's own picker open this one instead.
    input.addEventListener("keydown", (e) => {
      if ((e.altKey && e.key === "ArrowDown") || e.key === "F4") { e.preventDefault(); open(); }
    });
    // Firefox and Safari open their picker on click; keep typing, skip their popup.
    input.addEventListener("click", (e) => { if (typeof input.showPicker === "function" && !navigator.userAgent.includes("Chrome")) e.preventDefault(); });

    pop.addEventListener("mousedown", (e) => e.preventDefault());
    pop.addEventListener("click", (e) => {
      const nav = e.target.closest(".date-nav");
      if (nav) { view = addMonths(view, Number(nav.dataset.step)); focus = clamp(addMonths(focus, Number(nav.dataset.step))); render(); return; }
      const day = e.target.closest(".date-day");
      if (day && !day.disabled) choose(day.dataset.date);
    });
    pop.addEventListener("keydown", (e) => {
      const keys = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
      if (e.key in keys) { e.preventDefault(); return moveFocus(clamp(addDays(focus, keys[e.key]))); }
      switch (e.key) {
        case "PageUp": e.preventDefault(); return moveFocus(clamp(addMonths(focus, e.shiftKey ? -12 : -1)));
        case "PageDown": e.preventDefault(); return moveFocus(clamp(addMonths(focus, e.shiftKey ? 12 : 1)));
        case "Home": e.preventDefault(); return moveFocus(clamp(addDays(focus, -focus.getDay())));
        case "End": e.preventDefault(); return moveFocus(clamp(addDays(focus, 6 - focus.getDay())));
        case "Escape": e.preventDefault(); e.stopPropagation(); return close();
        case "Tab": return close(false);
        case "Enter": case " ": {
          const day = e.target.closest(".date-day");
          if (day) { e.preventDefault(); if (!day.disabled) choose(day.dataset.date); }
        }
      }
    });
  }

  document.addEventListener("mousedown", (e) => {
    if (openPicker && !openPicker.contains(e.target)) openPicker.close(false);
  });
  window.addEventListener("resize", () => openPicker && openPicker.close(false));

  document.querySelectorAll('.input-with-icon input[type="date"]').forEach(enhance);
})();
