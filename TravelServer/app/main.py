from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.config import settings
from app.db import init_db
from app.graph.agent import build_graph, set_graph
from app.graph.checkpoint import open_checkpointer


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    async with open_checkpointer() as saver:
        await saver.setup()
        set_graph(build_graph(saver))
        yield


app = FastAPI(title="Travel Agent", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat_router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str | int]:
    return {
        "status": "ok",
        "model": settings.model_name,
        "context_window": settings.context_window,
    }
