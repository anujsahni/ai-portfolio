// In-page dropdown menus for the form's <select> fields.
//
// Why: a native <select> popup is drawn by the browser as a separate OS window. On
// multi-monitor Macs, Chrome can open it on the wrong display. This menu is part of the
// page, so it always opens right under its field.
//
// The native <select> stays in the DOM (visually hidden) as the source of truth, so
// existing code that reads or sets .value, listens for "change", or replaces the options
// keeps working unchanged.
(function () {
  "use strict";

  let openMenu = null; // the one menu that is open, if any

  function enhance(select) {
    const field = select.closest(".input-with-icon");
    if (!field || select.dataset.enhanced) return;
    select.dataset.enhanced = "1";
    field.classList.add("select-field");

    const label = document.querySelector(`label[for="${select.id}"]`);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "select-button";
    button.setAttribute("aria-haspopup", "listbox");
    button.setAttribute("aria-expanded", "false");
    if (label) {
      label.id = label.id || `${select.id}-label`;
      label.htmlFor = ""; // the label now points at the button, via aria-labelledby
      button.setAttribute("aria-labelledby", `${label.id} ${select.id}-button`);
    } else if (select.getAttribute("aria-label")) {
      button.setAttribute("aria-label", select.getAttribute("aria-label"));
    }
    button.id = `${select.id}-button`;

    const list = document.createElement("ul");
    list.className = "select-menu";
    list.id = `${select.id}-menu`;
    list.setAttribute("role", "listbox");
    list.tabIndex = -1;
    list.hidden = true;
    button.setAttribute("aria-controls", list.id);

    select.classList.add("select-native");
    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");
    select.after(button);
    field.append(list);
    if (label) label.addEventListener("click", (e) => { e.preventDefault(); button.focus(); });

    let active = -1; // highlighted option index while open

    function refresh() {
      const option = select.options[select.selectedIndex];
      button.textContent = option ? option.textContent : "";
      list.innerHTML = "";
      Array.from(select.options).forEach((opt, i) => {
        const item = document.createElement("li");
        item.className = "select-option";
        item.id = `${select.id}-opt-${i}`;
        item.setAttribute("role", "option");
        item.setAttribute("aria-selected", String(i === select.selectedIndex));
        item.dataset.index = String(i);
        item.textContent = opt.textContent;
        list.append(item);
      });
    }

    function highlight(index) {
      const items = list.children;
      if (!items.length) return;
      active = Math.max(0, Math.min(items.length - 1, index));
      Array.from(items).forEach((el, i) => el.classList.toggle("active", i === active));
      list.setAttribute("aria-activedescendant", items[active].id);
      items[active].scrollIntoView({ block: "nearest" });
    }

    function open() {
      if (openMenu && openMenu !== api) openMenu.close(false);
      refresh();
      list.hidden = false;
      field.classList.add("open");
      button.setAttribute("aria-expanded", "true");
      // Open upward when there isn't room below the field.
      const room = window.innerHeight - field.getBoundingClientRect().bottom;
      field.classList.toggle("open-up", room < Math.min(list.scrollHeight, 260) + 12);
      highlight(select.selectedIndex);
      list.focus({ preventScroll: true });
      openMenu = api;
    }

    function close(returnFocus = true) {
      if (list.hidden) return;
      list.hidden = true;
      field.classList.remove("open", "open-up");
      button.setAttribute("aria-expanded", "false");
      list.removeAttribute("aria-activedescendant");
      if (openMenu === api) openMenu = null;
      if (returnFocus) button.focus();
    }

    function choose(index) {
      if (index >= 0 && index !== select.selectedIndex) {
        select.selectedIndex = index;
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
      refresh();
      close();
    }

    const api = { close, contains: (node) => field.contains(node) };

    button.addEventListener("click", () => (list.hidden ? open() : close()));
    // Clicking the icon or the chevron opens the menu too.
    field.addEventListener("mousedown", (e) => {
      if (e.target === field || e.target.classList.contains("field-icon") || e.target.classList.contains("input-trailing")) {
        e.preventDefault();
        list.hidden ? open() : close();
      }
    });
    button.addEventListener("keydown", (e) => {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) { e.preventDefault(); open(); }
    });
    list.addEventListener("mousedown", (e) => e.preventDefault()); // keep focus in the list
    list.addEventListener("click", (e) => {
      const item = e.target.closest(".select-option");
      if (item) choose(Number(item.dataset.index));
    });
    list.addEventListener("mousemove", (e) => {
      const item = e.target.closest(".select-option");
      if (item && Number(item.dataset.index) !== active) highlight(Number(item.dataset.index));
    });
    list.addEventListener("keydown", (e) => {
      const last = list.children.length - 1;
      switch (e.key) {
        case "ArrowDown": e.preventDefault(); return highlight(active + 1);
        case "ArrowUp": e.preventDefault(); return highlight(active - 1);
        case "Home": e.preventDefault(); return highlight(0);
        case "End": e.preventDefault(); return highlight(last);
        case "Enter": case " ": e.preventDefault(); return choose(active);
        case "Escape": e.preventDefault(); e.stopPropagation(); return close();
        case "Tab": return close(false);
        default:
          // Type-ahead: jump to the next option starting with that letter.
          if (e.key.length === 1 && /\S/.test(e.key)) {
            const items = Array.from(list.children);
            const key = e.key.toLowerCase();
            for (let step = 1; step <= items.length; step += 1) {
              const i = (active + step) % items.length;
              if (items[i].textContent.trim().toLowerCase().startsWith(key)) return highlight(i);
            }
          }
      }
    });

    // Keep the button in sync when app code sets .value or replaces the options.
    const proto = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value");
    Object.defineProperty(select, "value", {
      configurable: true,
      get() { return proto.get.call(this); },
      set(v) { proto.set.call(this, v); refresh(); },
    });
    select.addEventListener("change", refresh);
    new MutationObserver(refresh).observe(select, { childList: true, subtree: true });
    refresh();
  }

  document.addEventListener("mousedown", (e) => {
    if (openMenu && !openMenu.contains(e.target)) openMenu.close(false);
  });
  window.addEventListener("resize", () => openMenu && openMenu.close(false));

  document.querySelectorAll(".input-with-icon select").forEach(enhance);
})();
