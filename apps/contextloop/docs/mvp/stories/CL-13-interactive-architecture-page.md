# CL-13 — Interactive architecture page

**Phase:** 4 · Experience  
**Type:** UI and documentation  
**Priority:** P0  
**Estimate:** 5–7 hours  
**Story points:** 5 (the DealPulse pattern, extended with two views and a five-act walkthrough)  
**Target day:** Sat 14 Nov

## User story

As the presenter, I want an interactive map of the whole solution that I can step through act by act, and switch between "on this laptop" and "at a customer", so that I can explain the architecture to enterprise architects and executives from the same page.

## Scope

- `contextloop/ui/architecture/index.html`, `architecture.css` and `architecture.js`, in the same pattern as DealPulse: the page works on its own in a browser and is embedded in the Streamlit app with the CSS and JavaScript inlined.
- **Service map** laid out left to right in five bands: Sources → Move → Transform and Trust → Context → Activate, plus the app. Each node has an icon, a name, and a short label of what it does.
- **Hover** a node for a card: what it does, why it matters, the Fivetran or dbt capability it represents, and the container that runs it. **Click** to pin the card.
- **Step-through:** ← and → (or buttons) walk through the five acts. Each step lights up the nodes and the data path involved, dims the rest, and shows a caption with the one sentence from the talk track.
- **Request-flow mode** for Act 4: animates the eight steps of the headline question (agent → `list_metrics` → `check_freshness` → `query_metric` → lineage → answer), showing which MCP server handles each call.
- **Two views,** switched with a toggle:
  - *On this laptop*: the Docker services, volumes, ports and private network.
  - *At a customer*: native Fivetran connectors or hybrid deployment, Managed Data Lake Service on S3, ADLS or GCS, Snowflake, Databricks or BigQuery, the dbt platform and Semantic Layer, Fivetran Activations, and private networking options across AWS, Azure and GCP.
- Light and dark themes; readable when screen-shared at 1280 pixels.
- A static PNG rendered from the page for the README (`docs/images/architecture.png`).

**Out of scope:** live status from the containers on the map (the act pages show live data).

## Acceptance criteria

- [ ] The page opens directly in a browser and inside the app's Architecture page, with the same behaviour.
- [ ] Every node has a hover card; no card is empty or placeholder text.
- [ ] ← and → step through all five acts and the request flow; each step highlights the correct nodes (checked against the README's architecture).
- [ ] The toggle switches between the two views without reloading, and every laptop component has a named customer equivalent.
- [ ] Works in light and dark mode; no horizontal scroll at 1280 pixels.
- [ ] The README image is updated from the page.

## Dependencies and deliverables

**Dependencies:** CL-02 (service list), CL-12 (the app shell).  
**Deliverables:** `contextloop/ui/architecture/`, the Architecture page, `docs/images/architecture.png`.

## Completion evidence

Screenshots of both views and of one step in the walkthrough.
