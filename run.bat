@echo off
cd /d "%~dp0"
echo Installing dependencies...
py -m pip install -r requirements.txt -q
echo.
echo Starting Obstacle Avoidance dashboard on http://localhost:8501
py -m streamlit run app.py --server.port 8501 --server.headless true
pause
