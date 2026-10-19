import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from helm.api.routes import router
from helm.bank.router import router as bank_router
from helm.bootstrap import ensure_seeded, reset_demo
from helm.config import DEMO_MODE, DEMO_RESET_MINUTES, LLM_MODE


async def _demo_reset_loop():
    while True:
        await asyncio.sleep(DEMO_RESET_MINUTES * 60)
        await asyncio.to_thread(reset_demo)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await asyncio.to_thread(ensure_seeded)
    task = asyncio.create_task(_demo_reset_loop()) if DEMO_MODE else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="Helm API", version="0.1.0", lifespan=lifespan,
              description="Helm decides what to pay, when, and where to park spare cash. All data is synthetic demo data; payments go through a simulated Demo bank.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3100"],
    allow_origin_regex=r"https://.*\.(vercel\.app|onrender\.com|fly\.dev)",
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(router)
app.include_router(bank_router)


@app.get("/health", tags=["state"])
def health():
    return {"status": "ok", "llm_mode": LLM_MODE, "demo_mode": DEMO_MODE, "data": "synthetic demo data"}
