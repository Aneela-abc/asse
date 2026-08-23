"""
Run CareFlow Streamlit Frontend UI.
"""
import sys
import subprocess
from pathlib import Path

if __name__ == "__main__":
    app_file = Path(__file__).resolve().parent / "streamlit_app.py"
    print("=================================================================")
    print("🩺 Starting CareFlow Streamlit Frontend UI...")
    print("🌐 Frontend App URL: http://localhost:8501")
    print("=================================================================")
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_file)]
    subprocess.run(cmd)
