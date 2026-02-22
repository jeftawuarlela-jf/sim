# Supply Chain Simulation – Streamlit Deployment Guide

## Files needed (keep all in the same folder)
```
app.py              ← the web interface
simulation.py       ← your simulation logic (unchanged)
requirements.txt    ← dependencies
```

---

## Option 1 — Run locally on your own machine (share via LAN)

This lets anyone on your office network access the app from their browser.

**Step 1 — Install dependencies (one time only)**
```
pip install -r requirements.txt
```

**Step 2 — Start the app**
```
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

**Step 3 — Share the URL**  
Your machine's IP will appear in the terminal, e.g.:
```
  Network URL: http://192.168.1.42:8501
```
Anyone on the same Wi-Fi / office network can open that link in their browser — no installation on their end.

> To find your IP on Windows: open Command Prompt → type `ipconfig` → look for "IPv4 Address"

**To keep it running overnight**, just leave the terminal open.  
For a more permanent setup, consider running it as a Windows Service or background task.

---

## Option 2 — Deploy to Streamlit Community Cloud (free, public URL)

Good if the team works remotely or you want a permanent link.

**Step 1 — Push files to GitHub**
Create a public (or private) GitHub repo and upload:
- `app.py`
- `simulation.py`
- `requirements.txt`

**Step 2 — Deploy**
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with GitHub
3. Click "New app" → select your repo → set main file to `app.py`
4. Click Deploy — you'll get a public URL in ~2 minutes

> Note: On the free tier, the app sleeps after inactivity. First load after sleeping takes ~30 seconds.

---

## How the supply chain team uses it

1. Open the URL in any browser (Chrome, Edge, etc.)
2. Upload their CSV data file using the sidebar
3. Adjust the parameters if needed
4. Click **▶ Run Simulation**
5. Watch the live log — when finished, the results table and charts appear
6. Click **📥 Download Results ZIP** to save everything locally

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` on startup | Run `pip install -r requirements.txt` |
| `simulation.py not found` | Make sure simulation.py is in the same folder as app.py |
| Blank page on first load | Wait 10–30 seconds and refresh |
| Port 8501 already in use | Add `--server.port 8502` (or any free port) to the run command |
| App stops when terminal closes | Use `nohup streamlit run app.py &` on Linux/Mac, or Windows Task Scheduler |
