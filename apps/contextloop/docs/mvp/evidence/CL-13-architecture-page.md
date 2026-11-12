# CL-13 completion record: interactive architecture page

**Date:** 11 Nov 2026 · **Result:** all acceptance criteria met.

- `contextloop/ui/architecture/index.html`, `architecture.css`, `architecture.js`: opens directly in a browser, and is embedded in
  the app's **Architecture** page with the CSS and JavaScript inlined (same file, same behaviour).
- **Service map**, left to right: Sources → Move → Transform and trust → Context → Activate, plus the app; 20 nodes, each with
  an icon, a name and a short label.
- **Hover cards** (what, why, capability, where it runs) for every node in both views, pinned on click. `tests/test_ui.py` checks
  that all 20 nodes have six non-empty fields in each view.
- **Step-through:** ← and → (keyboard or buttons) walk the overview, Acts 1 to 5 and the request flow; each step highlights its
  nodes and paths and shows the talk-track sentence. Act 1 also shows the agent's raw-SQL path, dashed.
- **Request flow:** ▶ animates the eight steps of the headline question, numbering each node and naming the MCP server.
- **Two views:** *On this laptop* and *At a customer*. Every laptop component has a named production equivalent (native
  connectors or hybrid deployment, the customer's warehouse, the dbt platform and Semantic Layer, Managed Data Lake Service,
  Fivetran Activations), plus the private-networking options.
- **Themes:** light and dark (system setting or the ◐ toggle); no horizontal scroll at 1280 pixels (`scrollWidth` = 1280).
- **README image:** `docs/images/architecture-page.png`, rendered from the page, is in the README's Architecture section next
  to the static diagram.

Screenshots: `docs/images/guide/12-architecture-act4.png` and `13-architecture-customer.png`.
