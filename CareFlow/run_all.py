"""
Unified launcher to start both CareFlow FastAPI Backend and Streamlit Frontend concurrently.
"""
import sys
import time
import subprocess
import signal
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent
    frontend_script = root / "streamlit_app.py"

    print("=========================================================================")
    print("🩺 Starting CareFlow Full Stack (FastAPI Backend + Streamlit Frontend)")
    print("=========================================================================")
    print("📡 Backend REST API Docs: http://127.0.0.1:8000/docs")
    print("🌐 Frontend App URL:      http://localhost:8501")
    print("-------------------------------------------------------------------------")
    print("Press Ctrl+C at any time to shut down both servers.")
    print("=========================================================================\n")

    # Start FastAPI Backend in subprocess
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(root)
    )

    # Wait 2 seconds for backend to start up
    time.sleep(2)

    # Start Streamlit Frontend in subprocess
    frontend_proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(frontend_script)],
        cwd=str(root)
    )

    def cleanup(sig, frame):
        print("\nShutting down servers...")
        try:
            backend_proc.terminate()
        except Exception:
            pass
        try:
            frontend_proc.terminate()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        while True:
            time.sleep(1)
            # If any process died, terminate the other
            if backend_proc.poll() is not None or frontend_proc.poll() is not None:
                break
    except KeyboardInterrupt:
        cleanup(None, None)
    finally:
        cleanup(None, None)

if __name__ == "__main__":
    main()
