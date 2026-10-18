# Helm

**An agentic CFO that checks before it pays.** Helm releases a payment only if the forecast says the business stays above its minimum cash balance, and it can show its working.

> Everything in this repo is **synthetic demo data**. Warisan Printing Sdn Bhd is fictional. The bank is a mock **Demo bank**. Helm is a non-custodial decision layer: it does not hold funds, is not licensed, and is not connected to any real bank, payment rail or LHDN service.

```
P( min over the next H days of balance  >=  B  |  we pay )   >=   1 - alpha
```
`B` is the owner's minimum balance, `H` the horizon (90 days), `alpha` the owner's risk tolerance. Statutory payments (EPF, SOCSO, EIS, PCB, SST) and payroll are scheduled first and never delayed by the optimiser.

![Architecture](docs/Helm_Architecture.png)

## Run it (about 3 minutes)

Needs Node 20+, pnpm (`corepack enable`), and Python 3.11+.

```bash
cp .env.example .env     # optional: defaults already work
pnpm setup               # installs web deps and creates services/api/.venv
pnpm dev                 # API http://localhost:8000/docs  +  web http://localhost:3000
```

The first start seeds the database (seed = 2026, idempotent) and runs the pipeline once. No LLM and no network are needed: `LLM_MODE=fixtures` is the default.

### Docker

```bash
docker compose up        # Postgres 16 + API + web  ->  http://localhost:3000
```

### Tests

```bash
pnpm test:api            # 43 pytest tests: engine rules and verdicts, audit chain, bank, simulator flows
pnpm --filter web build && pnpm test:e2e   # 29 Playwright tests: demo flows, axe accessibility (both themes), 375px phone checks
DATABASE_URL=postgresql+psycopg:///helm_test pnpm test:api   # the same suite on Postgres (adds the role-grant test)
```

## The 60-second idea

1. **Today** tells the owner, in one sentence, whether they are okay and what needs them.
2. **Forecast** shows the next 90 days as a calibrated band (median, 50% and 80% ranges), the minimum-balance line, the lowest point, and the bill and invoice that cause it. What-ifs re-run the gate live.
3. **Payments** is the queue. Every row has a verdict (`ALLOW`, `HOLD`, `ESCALATE`, `DENY`), a release date and a one-sentence reason. "See working" opens the decision trace.
4. **Collections**, **Cash** and **Policy** act on the same numbers: who to chase (ranked by effect on the low point), where to park spare cash, and the owner's rules in plain words.
5. **Agents & audit** shows the pipeline, the run log, the hash-chained audit log with a **Verify chain** button, the kill switch, and the Demo bank statement.

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
- The optional live-LLM path (`LLM_MODE=live`, Reader extraction and Explainer wording) is wired but not exercised by the tests, which all run in fixture mode.
- Docker is not installed on the machine this was built on, so `docker compose up` is written to spec but was not run there. The API and the full test suite were run against a local Postgres 16.

## Deploying a public demo

Set `DEMO_MODE=true` on the API (it resets the database every `DEMO_RESET_MINUTES`) and point the web build at it with `NEXT_PUBLIC_API_URL`. Web: Vercel with root directory `apps/web`. API: any container host using `services/api/Dockerfile` plus a Postgres URL. No deploy has been done from this repo yet.

## Layout

```
apps/web/        Next.js app (screens, overlays, i18n, typed client)
services/api/    FastAPI app: helm/{agents,engine,forecast,optimiser,bank,seed,api}, tests/
e2e/             Playwright tests
docs/            architecture image, demo script
scripts/         gen-api.sh (regenerates the typed client)
DECISIONS.md     every judgement call made where the brief was silent
```
