# Deploy OAK Obstacle Avoidance on Render

Cloud runs **demo mode only** (synthetic camera + avoidance). A physical OAK-D cannot attach to Render.

## 1. Put this folder on GitHub

From `oa_obstacle_avoidance` (or `oa_pipeline` on the share):

```powershell
git init
git add .
git commit -m "Deploy Streamlit obstacle avoidance demo to Render"
gh repo create oak-obstacle-avoidance --public --source=. --remote=origin --push
```

Or create an empty repo in GitHub, then:

```powershell
git remote add origin https://github.com/<you>/oak-obstacle-avoidance.git
git branch -M main
git push -u origin main
```

## 2. Create the Web Service on Render

1. Open [https://dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint**  
   (or **Web Service** and connect the repo).
2. Select the GitHub repo. Root directory = repo root (this folder).
3. Render reads `render.yaml`:
   - **Build:** `pip install -r requirements-render.txt`
   - **Start:** Streamlit on `$PORT`
   - **Env:** `DEMO_MODE=1`
4. Deploy. Open the `*.onrender.com` URL.

### Manual Web Service (if not using Blueprint)

| Field | Value |
|--------|--------|
| Runtime | Python 3 |
| Build Command | `pip install -r requirements-render.txt` |
| Start Command | `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true` |
| Env vars | `DEMO_MODE=1` |

## 3. Use the app

1. Click **Start demo**.
2. Watch Live / Avoidance / VIO tabs update from the synthetic feed.

## Local live camera (not Render)

```bat
run.bat
```

Uses full `requirements.txt` (depthai + YOLO) on a PC with OAK-D attached.
