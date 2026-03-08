from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="SymptomScribe API", version="1.0.0")

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers
from routers import appointments, sessions, summaries, voice

app.include_router(appointments.router, prefix="/api/appointments", tags=["appointments"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(summaries.router, prefix="/api/summaries", tags=["summaries"])
app.include_router(voice.router, prefix="/api/voice", tags=["voice"])

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "symptom-scribe"}

# Serve React frontend — must come after API routes
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)