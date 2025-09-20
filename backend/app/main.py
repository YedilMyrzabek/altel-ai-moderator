from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from .routers import parser, comments, analytics

app = FastAPI(title="Altel AI Moderator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parser.router, prefix="/api/v1/parser", tags=["Parser"])
app.include_router(comments.router, prefix="/api/v1/comments", tags=["Comments"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])

@app.get("/")
def root():
    return {"message": "Altel AI Moderator API", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
