"""
FastAPI application entrypoint. Wires up routers, CORS, lifespan-managed
MongoDB connection, and a global exception handler so unhandled errors
return clean JSON instead of leaking stack traces.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import feedback, health, interview, upload
from app.core.config import settings
from app.core.logger import logger
from app.db.mongodb import close_connection, connect_and_ping


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting {} in {} mode", settings.app_name, settings.env)
    try:
        await connect_and_ping()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to connect to MongoDB on startup: {}", exc)
    yield
    await close_connection()
    logger.info("Shutdown complete")


app = FastAPI(
    title="AI Technical Interviewer",
    description=(
        "A live, adaptive spoken technical interview backend. Orchestrates an "
        "interviewer agent, an evaluator agent, and a feedback agent on top of "
        "an LLM, ElevenLabs TTS, and Whisper transcription, persisting state to MongoDB."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on {} {}", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health.router, prefix=settings.api_v1_prefix)
app.include_router(interview.router, prefix=settings.api_v1_prefix)
app.include_router(feedback.router, prefix=settings.api_v1_prefix)
app.include_router(upload.router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root():
    return {"message": "AI Technical Interviewer API", "docs": "/docs"}
