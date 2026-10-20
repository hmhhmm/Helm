# Helm

**An agentic CFO that checks before it pays.** Helm releases a payment only if the forecast says the business stays above its minimum cash balance, and it can show its working.

> Everything in this repo is **synthetic demo data**. Warisan Printing Sdn Bhd is fictional. The bank is a mock **Demo bank**. Helm is a non-custodial decision layer: it does not hold funds, is not licensed, and is not connected to any real bank, payment rail or LHDN service.

```
P( min over the next H days of balance  >=  B  |  we pay )   >=   1 - alpha
```
`B` is the owner's minimum balance, `H` the horizon (90 days), `alpha` the owner's risk tolerance. Statutory payments (EPF, SOCSO, EIS, PCB, SST) and payroll are scheduled first and never delayed by the optimiser.

**In three lines.** Helm forecasts a small business's cash for 90 days and releases a payment only when the chance of staying above the owner's minimum balance is high enough. Rules are code with a visible trace, so a poisoned invoice can never move money, and an audit log with a hash chain and an on-chain anchor shows that history was not changed. The bank, the data and the business are simulated and labelled as such.

**Live demo:** not deployed yet. Deploying needs a Vercel account and an API host (see [Deploying a public demo](#deploying-a-public-demo)). **Owner login for the demo:** the passcode is shown on the login dialog (`helm-demo` by default).

![Architecture](docs/Helm_Architecture.png)

## Run it (about 3 minutes)

Needs Node 20+, pnpm (`corepack enable`), and Python 3.11+.

```bash
cp .env.example .env     # optional: defaults already work
pnpm bootstrap           # installs web deps and creates services/api/.venv
pnpm dev                 # API http://localhost:8000/docs  +  web http://localhost:3000
```

The first start seeds the database (seed = 2026, idempotent) and runs the pipeline once. No LLM and no network are needed: `LLM_MODE=fixtures` is the default.

### Docker

```bash
docker compose up        # Postgres 16 + API + web  ->  http://localhost:3000
```

### Tests

```bash
pnpm test:api            # 124 pytest tests (123 passed, 1 skipped on SQLite)
DATABASE_URL=postgresql+psycopg:///helm_test pnpm test:api   # the same suite on Postgres 16 (124 passed, adds the role grant test)
pnpm --filter web build && pnpm test:e2e   # 32 Playwright tests: demo flows, owner login, anchor card, mandate, axe accessibility in both themes, 375px phone checks
```

Last run on the commit named in each evidence file. The one skipped test on SQLite is the Postgres role grant test. The Playwright suite was also run from a fresh clone of this branch (32 passed). Full output with dates and commit hashes is in [docs/evidence/](docs/evidence/).

| Group | File | What it proves |
|---|---|---|
| Policy engine | `tests/test_policy_engine.py` | Every rule and every verdict. ALLOW when the chance is high, HOLD with an earliest safe date, ESCALATE (limit, new payee, quarantined document, changed bank account, unusual amount), DENY (kill switch, protected payee with changed details, duplicate, reserve too small). Statutory and payroll are never delayed. Paying later is never less safe. Each released payment is committed before the next is judged |
| Audit and bank | `tests/test_audit_bank.py` | The hash chain verifies, the app cannot update or delete audit rows, and an edited or deleted row is detected and named. The bank accepts only what a scoped, expiring, single use key covers. On Postgres the agent role cannot write the rules or the audit log |
| Flows | `tests/test_world_and_flows.py` | The seeded cash crunch is real and Helm resolves it. A late customer flips ALLOW to HOLD. A poisoned invoice ends in ESCALATE with no money moved. Owner approval is the only way a flagged invoice is paid. A payment is rechecked on the day it would go |
| Red team | `tests/test_redteam.py` | RT1 to RT10, four extra attacks in the style of AgentDojo and InjecAgent, and permission tier tests. Every case checks that no money moves without ALLOW and that the audit chain still verifies |
| On-chain | `tests/test_onchain.py` | The contract cannot receive funds. Anchoring writes the audit head and the policy hash. Only hashes reach the chain. Verification passes on an untouched log, fails after an edit, and ignores events from any other address. A network failure does not break the app. Runs the real contract bytecode on an in process EVM |
| Auth and mandate | `tests/test_mandate_auth.py` | State changing routes refuse requests without an owner token, tokens expire and cannot be forged, login is rate limited, the daily cap, monthly cap and mandate expiry behave as written and are audited |
| Live model | `tests/test_llm.py` | A model that obeys an injection cannot get past the schema check, a model that changes a number is not used, the Gemini request keeps its key in a header and never in the URL, a rejected key gives a clean error, and the recorded real Gemini responses replay through the same check |
| FX | `tests/test_fx.py` | Conversion, caching and outage behaviour, and one live call to the real Frankfurter API that skips itself when offline |
| API | `tests/test_graph_api.py` | Every screen endpoint answers, owner actions are refused when nothing is waiting, a policy change is audited |

To run one group, use `cd services/api && . .venv/bin/activate && pytest tests/test_redteam.py -v`.

## Execution evidence

Everything below was produced by running this code. Each file carries its date and commit hash.

| Evidence | How it was produced | Where |
|---|---|---|
| Unit, red team, on-chain, login and mandate test output | `pytest -v` on SQLite and on Postgres 16 | `docs/evidence/pytest-sqlite.txt`, `docs/evidence/pytest-postgres.txt` |
| Operation log against the running API | `python scripts/run_evidence.py` drives the demo flows over HTTP, including an unauthenticated request that is refused | `docs/evidence/run-log.txt`, `run-log.json` |
| Local chain rehearsal | `python scripts/local_chain_demo.py` deploys the contract to an in process EVM, anchors, verifies, tampers and fails verification | `docs/evidence/local-chain.txt` |
| Real model responses | `python scripts/record_llm.py` calls Gemini on seeded and poisoned documents | `services/api/tests/fixtures/llm/recorded.json` |
| Real exchange rates | `python scripts/record_fx.py` calls Frankfurter | `docs/evidence/fx-frankfurter.json` |
| Dependency audits | `pip-audit` and `pnpm audit` | `docs/evidence/pip-audit.txt`, `docs/evidence/pnpm-audit.txt` |
| Public test network transaction hashes | `python scripts/deploy_anchor.py` with a funded throwaway key | `docs/evidence/onchain.json`. Real, on Ethereum Sepolia (chain 11155111). Contract [`0xD82F22e34Eaa2136d9ef091AD2b4e857fE33981f`](https://sepolia.etherscan.io/address/0xD82F22e34Eaa2136d9ef091AD2b4e857fE33981f), deployment [`0x68c7cae0e683…`](https://sepolia.etherscan.io/tx/0x68c7cae0e68385d6a2d3678d45aa038f46bc9505276592e23e542631299996a5), audit anchor [`0x55ce561154d3…`](https://sepolia.etherscan.io/tx/0x55ce561154d3cb244b732b5827c0e0c4f48c90d5d14437ad2b98a8ad00e702b7), policy anchor [`0x8f0fcfb759f3…`](https://sepolia.etherscan.io/tx/0x8f0fcfb759f3acd67498c710081d2826c61eb0fbf3c2c967edd9477d60800adf). Also confirmed through a second, unrelated RPC provider |

## On-chain audit anchor

Helm writes two kinds of hash to a public test network. One is the hash of the latest audit log row, which commits to every earlier row. The other is the hash of the owner's cash policy and mandate. Only hashes are written. The contract in `contracts/AuditAnchor.sol` stores nothing, holds no funds and only emits events. Anyone can call it, so verification counts only events from the Helm anchor address and compares them with a hash recomputed from the database. After each pipeline run Helm anchors automatically when the three settings below are present.

```bash
python scripts/new_anchor_wallet.py      # creates a throwaway wallet, saves its key in .env, prints only the address
# fund that address with Sepolia test ETH from a faucet, then
python scripts/deploy_anchor.py          # deploys, anchors, verifies, writes docs/evidence/onchain.json
```

Then put the printed contract address in `.env` as `ANCHOR_CONTRACT`, and the deploy block as `ANCHOR_FROM_BLOCK`. Running the script again reuses an existing contract. The Audit screen has **Anchor now** and **Verify on-chain** buttons, and the API has `GET /anchor`, `POST /anchor/run` and `POST /anchor/verify`. To rebuild the contract artifact, run `cd contracts && npm i && npm run compile`.

The contract is live on Ethereum Sepolia at `0xD82F22e34Eaa2136d9ef091AD2b4e857fE33981f`. The wallet that sent the anchors is `0x860F433F8144f8CE80c49F62705F66ef5119DD67` and it only ever holds test ETH. Note that this wallet also sent some extra anchors automatically while the tests were running against the live settings, before the tests were isolated from `.env`. Those events are on the contract but are not referenced by the evidence file, and the verifier ignores anything that is not recorded in the database.

To verify one anchor by hand, open `docs/evidence/onchain.json`. Open the contract link on the block explorer and look at the Events tab. Find the `Anchored` event with the row number from the file. Its `headHash` must equal the `hash` in the file, and its `by` address must be the sender in the file. Then run the verify button in the app. It recomputes the hash from the database and compares it with the one on chain.

What the anchor proves is that the log has not changed since it was anchored. It does not prove that the original events were true.

## Owner login

Every route that changes state needs an owner token (`helm/auth.py`). Reading the screens stays open. The web app shows a login dialog when a protected action is refused. The default passcode is `helm-demo` and the dialog shows it, because the demo data is synthetic. Set `OWNER_PASSCODE` and `OWNER_TOKEN_SECRET` anywhere else.

## The 60-second idea

1. **Today** tells the owner, in one sentence, whether they are okay and what needs them.
2. **Forecast** shows the next 90 days as a calibrated band (median, 50% and 80% ranges), the minimum-balance line, the lowest point, and the bill and invoice that cause it. What-ifs re-run the gate live.
3. **Payments** is the queue. Every row has a verdict (`ALLOW`, `HOLD`, `ESCALATE`, `DENY`), a release date and a one-sentence reason. "See working" opens the decision trace.
4. **Collections**, **Cash** and **Policy** act on the same numbers: who to chase (ranked by effect on the low point), where to park spare cash, and the owner's rules in plain words.
5. **Audit** shows the pipeline, the run log, the hash-chained audit log with a **Verify chain** button, the kill switch, and the Demo bank statement.

The **Simulator** (click the date, top right) has the three demo buttons: *Advance 1 week*, *Customer pays late*, *Inject malicious invoice*. See [docs/demo-script.md](docs/demo-script.md) for the 3-minute walkthrough.

## How it is built

| Layer | Choice |
|---|---|
| Web | Next.js (App Router), TypeScript strict, Tailwind, Radix primitives, TanStack Query, Recharts. API client generated from OpenAPI (`pnpm gen:api`). English + Bahasa Malaysia from one file (`apps/web/src/i18n/dict.ts`). |
| API | FastAPI, Pydantic v2, SQLAlchemy. One service, one database, separate tables. |
| Agents | Python modules behind one interface, `run(input) -> typed output`, in `services/api/helm/agents/`. Fixture mode by default. |
| Orchestration | Plain Python pipeline (`helm/pipeline.py`) with a LangGraph wrapper (`helm/graph.py`) that declares the same topology for the agent view. |
| Forecast | Monte Carlo over invoice-payment and bill-timing distributions learned from the seeded history (`helm/forecast/montecarlo.py`), behind a `Forecaster` interface. |
| Optimiser | OR-Tools CP-SAT chooses bill-release dates with the chance constraint as a scenario constraint (`helm/optimiser/scheduler.py`). |
| Policy | Pure functions (`helm/engine/policy.py`). Rule order: kill switch, statutory first, protected payee, duplicate or anomaly, approval limit, chance constraint, verdict. |
| Money | Executor (`helm/executor.py`) sends only `ALLOW` decisions to the mock bank (`helm/bank/`) with a scoped, expiring, single-use key. |
| Safety | Append-only audit log with DB triggers and a sha256 hash chain. On Postgres, the agent role can read but not write the rules (`helm_agent`). Kill switch. Watchdog self-test with a poisoned invoice after every run. |

Security basics you can check rather than take on trust: secrets only in `.env`; the Reader returns schema-checked JSON only and has no tools, so text inside a document can never move money; tampering with any audit row makes **Verify chain** fail and shows a banner; the kill switch makes the Executor refuse everything within one request.

## Honesty notes

- Targets and methods are not results. Every number on screen comes from the seeded simulation and is labelled synthetic. The forecast track record is a back-test on synthetic history and is shown as computed (the 80% range covered the real balance **77%** of the time in the seeded data, against a stated 80%).
- Helm is not licensed, holds no funds, and is live with no bank. Mentions of EPF, SOCSO, EIS, LHDN, BNM are context, not compliance claims.
- Competitor comparisons use only the vendor pages listed in the build brief.
- The live model path (`LLM_MODE=live`) uses Gemini through its REST API (`helm/llm.py`), with Anthropic as an alternative. The Reader and the Explainer are the only agents that may call a model, and every answer still goes through the schema check or the number guard. Real recorded Gemini responses, including two poisoned invoices, are in `services/api/tests/fixtures/llm/recorded.json` and are replayed by `tests/test_llm.py`. A failed call falls back to the fixture parser.
- The default bank is the built in Demo bank. Set BANK_PROVIDER=wise and WISE_API_KEY to pay through the real Wise sandbox instead. It uses test money, the payee bank numbers are synthetic, and because a personal token cannot fund a transfer by API the sandbox simulation steps move each transfer to sent. The log of a live run is in docs/evidence/sandbox-bank-log.txt.
- Docker is not installed on the machine this was built on, so `docker compose up` is written to spec but was not run there. The API and the full test suite were run against a local Postgres 16.

## Deploying a public demo

Set `DEMO_MODE=true` on the API (it resets the database every `DEMO_RESET_MINUTES`) and point the web build at it with `NEXT_PUBLIC_API_URL`. Web: Vercel with root directory `apps/web`. API: any container host using `services/api/Dockerfile` plus a Postgres URL. No deploy has been done from this repo yet. `render.yaml` describes the API and its Postgres database for Render, and the web app goes on Vercel with root directory `apps/web` and `NEXT_PUBLIC_API_URL` set to the API address.

## Layout

```
apps/web/        Next.js app (screens, overlays, i18n, typed client)
services/api/    FastAPI app: helm/{agents,engine,forecast,optimiser,bank,seed,api}, tests/
e2e/             Playwright tests
docs/            architecture image, demo script
scripts/         gen-api.sh (regenerates the typed client)
DECISIONS.md     every judgement call made where the brief was silent
```

## LHDN MyInvois

Each invoice on the Collections page has a generated MyInvois e-invoice document (UBL JSON, type 01, version 1.1) that can be viewed and downloaded. Helm does not submit it. Submitting needs your own MyInvois taxpayer account, which was not available in time, and the company tax numbers in the document are placeholders for the fictional business. The status is shown as ready to submit.
