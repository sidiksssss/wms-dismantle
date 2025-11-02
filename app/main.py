from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routers import router
from app.auth_router import router as auth_router
from app.chat_router import router as chat_router

app = FastAPI(
    title="WMS Dismantle API",
    description="API untuk mengelola data dismantle Work Orders dengan Authentication & Role-based Access",
    version="0.3.0"
)

# CORS middleware - allow frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Di production, ganti dengan domain spesifik
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for uploads
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include routers

app.include_router(auth_router)
app.include_router(router)
app.include_router(chat_router)

# Root and health endpoints to make quick checks easy
@app.get("/", tags=["Meta"])
def root():
    return {"status": "ok", "name": "WMS Dismantle API", "version": "0.3.0"}

@app.get("/healthz", tags=["Meta"])
def healthz():
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)