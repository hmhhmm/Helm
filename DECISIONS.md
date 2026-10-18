# Decisions

Where the brief was silent or contradictory, the simplest sound option was chosen and written here. Newest last within each group.

## Product and engine

1. **Protected payee means two things.** The owner's list is an allow-list of bank details (if the account on a bill differs from the one on file, the verdict is `DENY`, not just a flag) *and* the optimiser delays those payees last (double weight). Unprotected payees whose account changes are `ESCALATE`.
2. **Soft vs hard rules.** Hard (`DENY`): kill switch, protected payee with changed bank details, duplicate reference, reserve too small for a top-up. Soft (`ESCALATE`): above the approval limit, new payee, quarantined document, bank account differs for an unprotected payee, amount over 3x the supplier's usual. Chance failure is `HOLD` with the earliest safe date. Precedence: DENY, then ESCALATE, then HOLD, then ALLOW.
3. **Owner approval is not a bypass.** Approving an `ESCALATE` clears the soft flags and the approval limit, but the minimum-balance chance check still applies, so an approved payment can still be held until it is safe.
4. **Statutory and payroll are exempt from the approval limit and the chance gate** (they are fixed in the forecast and never delayed). If paying them would breach the minimum, the decision is `ALLOW` with a warning, and the Treasury Agent suggests a top-up.
5. **The chance constraint is checked jointly.** Decisions are made in a fixed order (statutory, then on-time bills, then bills the Scheduler chose to stretch). Each released payment is committed before the next is judged, so the whole plan, not just each payment, meets `1 - alpha`. `ESCALATE` and `DENY` are not committed, so a poisoned invoice cannot crowd out legitimate payments.
6. **Paying later is never less safe**, so the earliest safe date is found by binary search over the same scenarios. This is covered by a test.
7. **Low point is shown as the bad-but-plausible case (the 10th-percentile path)** next to the middle estimate. With `alpha = 10%` that is the case the owner asked Helm to guard against. The median is shown too.
8. **Two forecast views.** "If I pay everything on time" is what the Forecaster Agent writes (`cash_range`). "With Helm's holds" adds the released and held payments from the Policy Engine. The brief's story (a dip Helm resolves) needs both.
9. **Scheduler optimiser.** CP-SAT, scenario approach (160 of the 1000 simulated paths, at most `floor(alpha * S)` violating paths). Objective: pay as near the due date as possible; lateness cost rises faster than linearly (many short delays beat one long one), bills due soon cost more to delay, protected payees cost double, capped at 30 days late. The Policy Engine decides the actual date; the optimiser's plan sets the order and is shown in the trace.
10. **Top-ups are suggestions, not assumptions.** Helm does not count on the reserve when judging a bill. If the owner approves a top-up, the balance changes and the next run re-decides (held bills may flip to released). Sweeps and top-ups are executed only when the owner taps **Do it**.
11. **Reserve interest is an estimate** at an illustrative 2.5% a year and is labelled as such. It is not a quote from any bank.
12. **Chase ranking** uses a stated assumption: a reminder brings payment forward 10 days. The effect is capped at the invoice value. In the simulated world a "sent" reminder pulls the real payment forward up to 5 days; nothing is actually sent.
13. **"Customer pays late"** is a message the system reads (`late_signal_days`), shifts that customer's distribution by 20 days and widens it, and the hidden world pays 20 days late as well. It is idempotent; Reset demo to run it again.
14. **Gate on the day.** When advancing time, any payment whose release date arrives triggers a fresh forecast and decision before it is sent, so a payment is always re-checked against current cash.

## Data and simulation

15. **Seeded story.** The history is generated from per-customer behaviour (including two chronic late payers and one 62-day customer). To make one genuine crunch about five weeks out, September to October billing is hand-set soft (open invoices scaled to 30%) and two year-end orders are added (a RM 52,000 order from the 62-day customer, which lands in early December, and a RM 44,000 order from an education customer). The figures are in `helm/seed/world.py`. Nothing else is tuned; the forecast is not tuned to look accurate.
16. **Statutory and payroll calendar** is stored for the whole simulated period as known bills. Amounts are round, fictional numbers, not a computation of any real contribution rate.
17. **Documents.** Open invoices and bills each have a plain-text document that the Reader parsed. The history has no documents (ledger rows only).
18. **Hash chain row** is `{id, ts, actor, event, payload}`; `hash = sha256(prev_hash + canonical_json(row))` with sorted keys and compact separators. Decisions are logged when they are new or change, not on every identical re-run.
19. **Append-only** is enforced by triggers on SQLite and Postgres. The demo "tamper" button simulates someone with admin rights who drops the trigger; the hash chain is what catches it.
20. **Mock bank** keys are HMAC-signed, scoped to one destination account, one maximum amount and one payment, expire in 5 minutes, and are single-use. The bank keeps its own ledger.

## Build and tooling

21. **Python 3.11+** (developed on 3.12). **Next.js 16**: `cacheComponents` and `partialPrefetching` are switched off because the app is client-driven (TanStack Query).
22. **shadcn CLI not used.** Its current default targets Base UI, the brief says Radix. Components are small hand-written wrappers on Radix primitives with shadcn-style APIs.
23. **Contrast.** The brief's swatches for ALLOW (#0E8A4F) and HOLD (#B26A00) are slightly under 4.5:1 on white, so text uses #0B7A45 and #9A5B00. Dark theme has its own tokens. axe-core finds no serious or critical issues in either theme.
24. **x = 0 on a numeric Recharts axis is dropped**, so the chart's x axis starts at 1.
25. **Chart animation** is off on first paint and on for later changes (a what-if redraws the band), and always off under `prefers-reduced-motion`.
26. **Status is never colour alone**: every verdict has an icon and a word; chart markers differ in shape.
27. **LangGraph** declares the pipeline topology and replays a run for the agent view. The logic stays in plain Python so it is testable without LangGraph.
28. **Live LLM path** (Reader extraction, Explainer wording) exists behind `LLM_MODE=live`, falls back to fixtures on any error, and goes through the same schema check. It is not part of any test.
29. **Public demo mode** is interpreted as: all data synthetic, simulator actions allowed, the database resets itself on a timer. No auth, billing or roles (out of scope).
30. **Docker** was not available on the build machine. `docker-compose.yml` and the Dockerfiles follow the working local setup; the API and tests were run on Postgres 16 locally instead.
31. **Not done:** a public deployment, the 3-minute video recording, and the real-LLM path under test. The script for the video is in `docs/demo-script.md`.
