"""
Run CareFlow Backend REST API Server.
"""
import uvicorn

if __name__ == "__main__":
    print("=================================================================")
    print("🩺 Starting CareFlow Backend REST API (FastAPI)...")
    print("📡 Swagger Interactive API Documentation: http://127.0.0.1:8000/docs")
    print("📡 ReDoc Alternative Documentation:     http://127.0.0.1:8000/redoc")
    print("=================================================================")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
