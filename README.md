# Helm

An agentic CFO for Malaysian SMEs. Helm releases a payment only if the forecast says the business stays above its minimum cash balance, and it can show its working.

> All data is **synthetic demo data** (Warisan Printing Sdn Bhd is fictional). The bank is a **Demo bank**. Helm is a non-custodial decision layer; it does not hold funds and is not connected to any real bank.

## Run (local, no Docker)

```bash
cp .env.example .env
pnpm install
cd services/api && python3.12 -m venv .venv && .venv/bin/pip install -e . pytest && cd ../..
pnpm dev:api        # http://localhost:8000/health
pnpm dev            # http://localhost:3000
```

## Run (Docker)

```bash
docker compose up
```

Set `DATABASE_URL=sqlite:///./helm.db` for the one-file fallback. `LLM_MODE=fixtures` (default) means no LLM is needed.

## Layout

- `apps/web` — Next.js (App Router), Tailwind, Radix, TanStack Query
- `services/api` — FastAPI, SQLAlchemy, engine, agents, mock bank
- `e2e` — Playwright flows
- `DECISIONS.md` — every judgement call
