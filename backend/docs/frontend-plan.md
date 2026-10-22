# Frontend implementation plan

1. Preserve all existing working-tree edits and stage only files created for this frontend.
2. Match the verified `/chat` contract and 2,000-character limit; conversation IDs are UUIDs.
3. Add display-safe history and deletion, public catalog and config endpoints, and optional SPA serving without touching agent logic or guardrails.
4. Use exact allowlisted order phrases from `app/guardrail_rules.py`: `oui je confirme la commande`, `annule la commande`, `i confirm the order`, `cancel the order`.
5. Phase 1: strict React/Vite/TypeScript scaffold, typed API, chat, safe markdown, errors, persistence/restore, required backend endpoints; gate and commit task-owned files.
6. Phase 2: order/success/blocked cards, activity timeline, inspector, catalog and demo mode; gate and commit task-owned files.
7. Phase 3: responsive and visual polish, theme, FR/EN, accessibility, logo/favicon, CSP and documentation; gate and commit task-owned files.
8. Update README and gitignore, generate screenshots if tooling allows, and report deviations plus eight manual checks.

## Findings and assumptions

- `/chat` has no `guardrail` field; blocked prompt injection currently returns the fixed refusal and an empty trace. Identify that existing response without modifying agent behavior.
- No server-side sanitizer exists. Use a small HTML-to-text sanitizer for the display catalog; React markdown uses `rehype-sanitize` and no raw HTML.
- `data/products.json` is the available catalog snapshot; the WooCommerce helper is authenticated.
- Existing working-tree edits were present in app, tests, infrastructure, README and reports; they are user-owned and will be preserved.
- `node` and `npm` are not currently available in PATH; check local runtime locations and record if JavaScript gates cannot run.
