# Helm

**An agentic CFO that checks before it pays.** Helm releases a payment only if the forecast says the business stays above its minimum cash balance, and it can show its working.

[GitHub repository](https://github.com/hmhhmm/Helm) · [Technical documentation](docs/TECHNICAL.md) · [Security self-assessment](docs/SECURITY.md) · [Demo script](docs/demo-script.md)

> All business data is **synthetic**. Warisan Printing Sdn Bhd is fictional. Helm is a non-custodial decision layer. It holds no funds, is not licensed, and is not connected to any real bank, payment rail or LHDN service. The default bank is a built in simulation, and the real **Wise sandbox** (test money) is available as an option.

```
P( min over the next H days of balance  >=  B  |  we pay )   >=   1 - alpha
```

`B` is the owner's minimum balance, `H` the horizon (90 days) and `alpha` the owner's risk tolerance. Statutory payments (EPF, SOCSO, EIS, PCB, SST) and payroll are scheduled first and never delayed by the optimiser.

![Today screen](docs/screenshots/ui-today.png)

## Contents

1. [What Helm does](#what-helm-does)
2. [Run it locally](#run-it-locally)
3. [Deploy a public demo](#deploy-a-public-demo)
4. [Test cases and results](#test-cases-and-results)
5. [Execution evidence](#execution-evidence)
6. [On-chain audit anchor](#on-chain-audit-anchor)
7. [Bank, e-invoice and live model options](#bank-e-invoice-and-live-model-options)
8. [How it is built](#how-it-is-built)
9. [Honesty notes](#honesty-notes)

## What Helm does

Helm forecasts a small business's cash for 90 days and releases a payment only when the chance of staying above the owner's minimum balance is high enough. Rules are code with a visible trace, so a poisoned invoice can never move money. A hash chained audit log with an on-chain anchor shows that history was not changed.

| Screen | What the owner gets |
|---|---|
| **Today** | One sentence on whether the business is okay, and what needs the owner |
| **Forecast** | The next 90 days as a band (median, 50% and 80% ranges), the minimum line, the lowest point and what causes it. What-ifs re-run the gate live |
| **Payments** | The queue. Each row has a verdict (ALLOW, HOLD, ESCALATE, DENY), a release date and one reason. "See working" opens the decision trace |
| **Collections** | Who to chase, ranked by effect on the low point, and a generated MyInvois e-invoice per invoice |
| **Cash** and **Policy** | Where to park spare cash, and the owner's rules and mandate in plain words |
| **Audit** | The pipeline, the hash chained log with **Verify chain**, the on-chain anchor, the kill switch and the bank statement |

The **Simulator** (click the date, top right) has three demo buttons: *Advance 1 week*, *Customer pays late* and *Inject malicious invoice*.

![Architecture](docs/Helm_Architecture.png)

## Run it locally

Needs Node 20+, pnpm (`corepack enable`) and Python 3.11+.

```bash
git clone https://github.com/hmhhmm/Helm.git && cd Helm
cp .env.example .env     # optional, the defaults already work
pnpm bootstrap           # installs web dependencies and creates services/api/.venv
pnpm dev                 # API http://localhost:8000/docs and web http://localhost:3000
```

The first start seeds the database (seed 2026) and runs the pipeline once. No model and no network are needed, because `LLM_MODE=fixtures` is the default. Mutating actions ask for the owner passcode, which is `helm-demo` by default and is shown on the login dialog.

With Docker, `docker compose up` starts Postgres 16, the API and the web app on http://localhost:3000. It is written to spec but was not run on the build machine, which has no Docker.

### Settings

| Setting | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | SQLite file | Use a Postgres URL for the hardened role setup |
| `LLM_MODE`, `LLM_PROVIDER`, `GEMINI_API_KEY` | `fixtures` | `live` makes the Reader and Explainer call Gemini |
| `BANK_PROVIDER`, `WISE_API_KEY` | `wise` when a Wise key is set, otherwise `demo` | `wise` pays through the Wise sandbox |
| `ANCHOR_RPC_URL`, `ANCHOR_PRIVATE_KEY`, `ANCHOR_CONTRACT` | empty | Turn on the on-chain anchor |
| `OWNER_PASSCODE`, `OWNER_TOKEN_SECRET` | demo values | Set both anywhere outside the demo |
| `DEMO_MODE` | off | Resets the database on a timer for a public demo |

## Deploy a public demo

1. **API and database.** Create a Render Blueprint from `render.yaml`. It builds `services/api/Dockerfile` from the repository root and creates a Postgres database. Set `DEMO_MODE=true`, `OWNER_PASSCODE` and `OWNER_TOKEN_SECRET`. Add the Gemini, Wise and anchor keys only if you want those options live.
2. **Web.** Import the repository into Vercel with root directory `apps/web`, and set `NEXT_PUBLIC_API_URL` to the API address from step 1.
3. **Check.** Open the web address, run the Simulator's *Inject malicious invoice*, then press **Verify chain** on the Audit screen.

No public deployment has been made from this repository yet.

## Live demo with the Wise sandbox

This is the flow to show a judge. Helm checks the payment, you approve it on the spot, and Wise receives it.

1. Put `WISE_API_KEY` in `.env` and run `pnpm dev`. A Wise key switches the bank to the Wise sandbox on its own. The Audit screen then calls the bank "Wise sandbox".
2. Open **Payments**, press **New payment**, and enter a payee, an amount and a reference.
3. With Wise connected, a payment to Ladang Kertas Utama (RM 985) is already waiting under **Needs you** after a reset, so you can skip the form. Any other new payee waits there too. Nothing has gone to Wise yet.
4. Press **Approve**. Helm sends the payment through the Wise sandbox and the row shows as sent.
5. Open **Audit**. The bank statement shows the Wise transfer id next to the accepted instruction, and the same id is in the Wise sandbox dashboard.

A run of this exact flow is recorded in [docs/evidence/sandbox-bank-log.txt](docs/evidence/sandbox-bank-log.txt). The seeded Warisan data stays in the database as the background business. The Wise sandbox uses test money.

## Test cases and results

```bash
pnpm test:api                              # 130 passed, 1 skipped on SQLite
DATABASE_URL=postgresql+psycopg:///helm_test pnpm test:api   # the same suite on Postgres 16, adds the role grant test
pnpm --filter web build && pnpm test:e2e   # 33 Playwright tests passed
```

The skipped test is the Postgres role grant test. The Playwright suite covers the demo flows, owner login, the anchor card, the mandate, axe accessibility checks in both themes, and 375px phone checks. Full output is in [docs/evidence/pytest-sqlite.txt](docs/evidence/pytest-sqlite.txt) and [docs/evidence/pytest-postgres.txt](docs/evidence/pytest-postgres.txt). Each file carries its date and commit hash.

### Red team suite (29 passed)

Prompt injection, hidden characters, changed bank details, replay, tampering, the kill switch and oversized documents. Every case checks that no money moves without ALLOW and that the audit chain still verifies.

![Red team test output](docs/screenshots/tests-redteam.png)

### Policy engine (all verdicts and rules)

![Policy engine test output](docs/screenshots/tests-policy.png)

### On-chain anchor (runs the real contract bytecode)

![On-chain test output](docs/screenshots/tests-onchain.png)

### Wise adapter, e-invoice, login and mandate

![Wise, e-invoice, auth and mandate test output](docs/screenshots/tests-more.png)

The images above are real `pytest -v` output rendered to PNG. Re-create the text with `cd services/api && . .venv/bin/activate && pytest -v`.

| Group | File | What it proves |
|---|---|---|
| Policy engine | `test_policy_engine.py` | Every rule and verdict. ALLOW when the chance is high, HOLD with an earliest safe date, ESCALATE (limit, new payee, quarantined document, changed account, unusual amount), DENY (kill switch, protected payee, duplicate, reserve too small). Statutory and payroll are never delayed |
| Audit and bank | `test_audit_bank.py` | The chain verifies, the app cannot edit audit rows, an edited row is named. The bank accepts only a scoped, expiring, single use key |
| Flows | `test_world_and_flows.py` | The seeded cash crunch is real and Helm resolves it. A late customer flips ALLOW to HOLD. A poisoned invoice moves no money. Payments are rechecked on the day they would go |
| Red team | `test_redteam.py` | RT1 to RT10, four more injection attacks and permission tier tests |
| On-chain | `test_onchain.py` | Only hashes reach the chain. Verification passes on an untouched log, fails after an edit and ignores events from other addresses. Log reads work across block windows |
| Auth and mandate | `test_mandate_auth.py` | Mutating routes refuse requests without an owner token. Tokens expire. Login is rate limited. Daily cap, monthly cap and mandate expiry are enforced and audited |
| Wise sandbox | `test_wise.py` | Quote, recipient, transfer and sandbox steps on a mocked transport. The bank key is checked before Wise is called. The key never reaches the call log |
| E-invoice | `test_einvoice.py` | The document matches the ledger and is never marked as submitted |
| Live model | `test_llm.py` | A model that obeys an injection cannot pass the schema check. A model that changes a number is not used. Recorded real Gemini responses replay through the same checks |
| FX and API | `test_fx.py`, `test_graph_api.py` | Conversion, caching, outage behaviour, and every screen endpoint |

## Execution evidence

Produced by running this code. Each file carries its date and commit hash.

| Evidence | Where |
|---|---|
| Test output on SQLite and Postgres 16 | `docs/evidence/pytest-sqlite.txt`, `pytest-postgres.txt` |
| Operation log against the running API, including a refused unauthenticated request | `docs/evidence/run-log.txt`, `run-log.json` |
| Local chain rehearsal (anchor, tamper, fail) | `docs/evidence/local-chain.txt` |
| Real payments through the Wise sandbox, with Wise's own transfer ids | `docs/evidence/sandbox-bank-log.txt` |
| Real Gemini responses on seeded and poisoned documents | `services/api/tests/fixtures/llm/recorded.json` |
| Real exchange rates from Frankfurter | `docs/evidence/fx-frankfurter.json` |
| Dependency audits | `docs/evidence/pip-audit.txt`, `pnpm-audit.txt` |
| Public test network transactions | `docs/evidence/onchain.json` |

### Screens

| Forecast | Payments |
|---|---|
| ![Forecast](docs/screenshots/ui-forecast.png) | ![Payments](docs/screenshots/ui-payments.png) |
| **Collections** | **Audit** |
| ![Collections](docs/screenshots/ui-collections.png) | ![Audit](docs/screenshots/ui-audit.png) |

## On-chain audit anchor

Helm writes two hashes to a public test network. One is the hash of the latest audit row, which commits to every earlier row. The other is the hash of the owner's cash policy and mandate. Only hashes are written. The contract in `contracts/AuditAnchor.sol` stores nothing, holds no funds and only emits events. Anyone can call it, so verification counts only events from the Helm anchor address and compares them with a hash recomputed from the database.

Live on Ethereum Sepolia:

- Contract [`0xD82F22e34Eaa2136d9ef091AD2b4e857fE33981f`](https://sepolia.etherscan.io/address/0xD82F22e34Eaa2136d9ef091AD2b4e857fE33981f)
- Deployment [`0x68c7cae0e683…`](https://sepolia.etherscan.io/tx/0x68c7cae0e68385d6a2d3678d45aa038f46bc9505276592e23e542631299996a5)
- Audit anchor [`0x55ce561154d3…`](https://sepolia.etherscan.io/tx/0x55ce561154d3cb244b732b5827c0e0c4f48c90d5d14437ad2b98a8ad00e702b7)
- Policy anchor [`0x8f0fcfb759f3…`](https://sepolia.etherscan.io/tx/0x8f0fcfb759f3acd67498c710081d2826c61eb0fbf3c2c967edd9477d60800adf)

The sending wallet is `0x860F433F8144f8CE80c49F62705F66ef5119DD67` and holds only test ETH. Some extra anchors from it were sent while tests ran against the live settings, before the tests were isolated from `.env`. The verifier ignores anything not recorded in the database.

```bash
python scripts/new_anchor_wallet.py   # throwaway wallet, key saved in .env, prints only the address
# fund the address with Sepolia test ETH, then
python scripts/deploy_anchor.py       # deploys, anchors, verifies, writes docs/evidence/onchain.json
```

Put the printed contract address in `.env` as `ANCHOR_CONTRACT` and the deploy block as `ANCHOR_FROM_BLOCK`. The Audit screen has **Anchor now** and **Verify on-chain**, and the API has `GET /anchor`, `POST /anchor/run` and `POST /anchor/verify`. To check one anchor by hand, find the `Anchored` event on the explorer. Its `headHash` must equal the `hash` in `onchain.json`.

The anchor proves the log has not changed since it was anchored. It does not prove the original events were true.

## Bank, e-invoice and live model options

- **Wise sandbox.** Set `BANK_PROVIDER=wise` and `WISE_API_KEY`. Each released bill goes through a real quote, recipient and transfer on `api.wise-sandbox.com`. Helm's scoped bank key is checked first. Test money only, payee bank numbers are synthetic, and a personal token cannot fund a transfer by API, so the sandbox's own simulation steps move it to sent.
- **LHDN MyInvois.** Each invoice on the Collections page has a generated e-invoice document (UBL JSON, type 01, version 1.1) to view and download. Helm does not submit it, because that needs the owner's own MyInvois account. The tax numbers in it are placeholders for the fictional business.
- **Live model.** `LLM_MODE=live` uses Gemini through its REST API (`helm/llm.py`), with Anthropic as an alternative. Only the Reader and the Explainer may call a model, and every answer passes the schema check or the number guard. A failed call falls back to the fixture parser.

## How it is built

| Layer | Choice |
|---|---|
| Web | Next.js (App Router), TypeScript, Tailwind, Radix, TanStack Query, Recharts. Typed client generated from OpenAPI. English and Bahasa Malaysia from one file |
| API | FastAPI, Pydantic v2, SQLAlchemy. SQLite by default, Postgres 16 supported |
| Agents | Reader, Forecaster, Collections, Scheduler, Treasury and Explainer in `services/api/helm/agents/`, with a LangGraph wrapper (`helm/graph.py`) over the plain pipeline (`helm/pipeline.py`) |
| Forecast | Monte Carlo over payment and bill timing learned from history (`helm/forecast/montecarlo.py`) |
| Optimiser | OR-Tools CP-SAT with the chance constraint as a scenario constraint (`helm/optimiser/scheduler.py`) |
| Policy | Pure functions (`helm/engine/policy.py`). Order: kill switch, statutory first, protected payee, duplicate or anomaly, approval limit, mandate, chance constraint |
| Money | Only the Executor sends ALLOW decisions to the bank, each with a scoped, expiring, single use key |
| Safety | Append only audit log with database triggers and a sha256 chain, owner token auth, kill switch, and a Watchdog self test after every run |

Repository layout:

```
apps/web/        Next.js app
services/api/    FastAPI app and tests
contracts/       AuditAnchor.sol and its compiled artifact
e2e/             Playwright tests
scripts/         evidence, deployment and client generation scripts
docs/            technical documentation, security assessment, demo script, evidence, screenshots
DECISIONS.md     every judgement call where the brief was silent
```

Read next: [Technical documentation](docs/TECHNICAL.md) for the architecture, algorithms and security design, and the [Security self-assessment](docs/SECURITY.md) for the permission tiers, threat table and known risk list.

## Honesty notes

- Targets and methods are not results. Every number on screen comes from the seeded simulation and is labelled synthetic. The forecast back-test on synthetic history is shown as computed (the 80% range covered the outcome 77% of the time).
- Helm is not licensed and holds no funds. Mentions of EPF, SOCSO, EIS, LHDN and BNM are context, not compliance claims.
- The Wise sandbox uses test money. The Demo bank is a simulation.
- The security assessment was done by the builders, with no independent penetration test.
