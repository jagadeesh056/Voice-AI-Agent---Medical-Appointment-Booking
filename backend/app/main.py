import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from datetime import datetime

from app.database.connection import init_db
from app.cache.redis_handler import cache

load_dotenv()

app = FastAPI(
    title="Voice AI Agent - Clinical Appointment Booking",
    description="Real-time multilingual voice AI agent for clinical appointment booking",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    print("[v0] Starting FastAPI server...")
    init_db()
    print(f"[v0] Cache connected: {cache.is_connected()}")


@app.on_event("shutdown")
async def shutdown_event():
    print("[v0] Shutting down FastAPI server...")


@app.get("/health")
async def health_check():
    return {
        "status":    "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database":  "connected",
        "redis":     "connected" if cache.is_connected() else "disconnected",
    }


# ── Routers ──────────────────────────────────────────────────────────────
from app.routes import users, appointments, voice, sessions, slots   # ← slots added

app.include_router(users.router,        prefix="/api/users",        tags=["users"])
app.include_router(appointments.router, prefix="/api/appointments",  tags=["appointments"])
app.include_router(voice.router,        prefix="/api/voice",         tags=["voice"])
app.include_router(sessions.router,     prefix="/api/sessions",      tags=["sessions"])
app.include_router(slots.router,        prefix="/api/slots",         tags=["slots"])   # ← new


@app.get("/")
async def root():
    return {
        "service": "Voice AI Agent for Clinical Appointments",
        "version": "1.0.0",
        "status":  "running",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True,
        log_level="info",
    )