# 📦 Supply Chain Simulation

A **Streamlit web app** for simulating supply chain replenishment scenarios across multiple Reorder Trigger (RT) and Target Days-of-Inventory (DOI) combinations. Upload your inventory, lead time, and supplier data, configure parameters, and instantly get interactive charts and downloadable reports to find the optimal reorder policy for your warehouse.

---

## ✨ Features

- **Multi-scenario simulation** — Test every combination of RT and DOI values in a single run
- **4-file data join** — Merges stock & sales, lead times, active supplier + price, and day-of-week proportions automatically
- **Missing lead time handling** — Flags SKUs with no lead time in File 2 and lets you apply a single default value
- **Capacity analysis** — Tracks daily inbound SKU count against your warehouse's daily and total SKU limits
- **Volume tracking** — Measures total inbound quantity (units) per day, not just unique SKU count
- **Inventory value tracking** — Computes daily total inventory value using `net_price × stock` (if pricing data is provided)
- **Interactive charts** (Plotly) — Bar charts, box plots, and calendar heatmaps, all exportable
- **ZIP download** — Download all CSVs and charts in one click

---

## 📁 Repository Structure

```
sim/
├── app3_plotly.py          # Streamlit web app (UI + orchestration)
├── simulation3_plotly.py   # Core simulation & charting engine
├── requirements.txt        # Python dependencies
├── DEPLOY.md               # Deployment guide (local LAN + Streamlit Cloud)
└── .devcontainer/          # Dev container configuration
```

---

## 📂 Input File Formats

| # | File | Required Columns | Notes |
|---|------|-----------------|-------|
| **1** | Stock & Sales | `sku_code`, `product_name`, `tanggal_update`, `stock`, `quantity_sold_per_day`, `doi` | One row per SKU per date |
| **2** | Lead Times | `sku_code`, `supplier`, `lead_time_days` | One SKU can have multiple suppliers |
| **3** | Active Supplier | `sku_code`, `supplier`, `net_price` | One row per SKU — currently active supplier + unit price |
| **4** | Day Proportions | `day_of_week`, `proportion` | 7 rows (Monday–Sunday), must sum to 1.0 |

> **How the join works:** File 3 identifies the active supplier per SKU. File 2 provides lead times per SKU × supplier. These are inner-joined to get one lead time per SKU, then merged with File 1. SKUs whose active supplier has no entry in File 2 can be given a single default lead time.

---

## ⚙️ Simulation Parameters

| Parameter | Description |
|-----------|-------------|
| **RT Start / Stop** | Range of Reorder Trigger (DOI threshold) values to test |
| **DOI Start / Stop** | Range of Target Days-of-Inventory values to test |
| **Daily SKU Capacity** | Max unique SKUs the inbound team can receive per day |
| **Total SKU Capacity** | Total unique SKUs the warehouse can hold |
| **End Date** | Last day of the simulation reporting period |
| **Save detailed results** | Toggle per-SKU daily output CSVs |
| **Save daily summaries** | Toggle aggregated daily summary CSVs |

---

## 📊 Output Charts

| # | Chart | Description |
|---|-------|-------------|
| 1 | Overload Days by DOI (grouped by RT) | Days exceeding daily SKU capacity, broken down by day of week |
| 2 | Avg SKU Arrivals by DOI (grouped by RT) | Average daily unique SKUs arrived vs. capacity line |
| 3 | Binning Distribution by DOI (grouped by RT) | Days falling into each daily-volume bin (0–30, 31–90 … 720+) |
| 4 | Avg SKU Arrivals by RT (grouped by DOI) | Same as Chart 2, axes swapped |
| 5 | Overload Days by RT (grouped by DOI) | Same as Chart 1, axes swapped |
| 6 | Binning Distribution by RT (grouped by DOI) | Same as Chart 3, axes swapped |
| 7 | Boxplot of Daily Arrivals | Distribution spread per scenario, excluding Sundays |
| 8 | Calendar Heatmap | One calendar per scenario, each day colored by its arrival bin |
| 9 | Avg Daily Inbound Volume by DOI | Total units arriving per day (not unique SKUs) |
| 10 | Daily Inventory Value Time Series | Monetary value of all stock per day (requires `net_price`) |

All charts are saved as both interactive `.html` files and `.json` (Plotly format), and bundled in the ZIP download.

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/jeftawuarlela-jf/sim.git
cd sim
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app

```bash
streamlit run app3_plotly.py
```

The app will open in your browser at `http://localhost:8501`.

---

## 🌐 Deployment

### Option A — Local LAN (share with office network)

```bash
streamlit run app3_plotly.py --server.address 0.0.0.0 --server.port 8501
```

Your machine's local IP (e.g. `http://192.168.1.42:8501`) will be shown in the terminal. Anyone on the same network can open it without any installation.

> **Windows tip:** Run `ipconfig` in Command Prompt to find your IPv4 address.

### Option B — Streamlit Community Cloud (free, public URL)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
3. Click **New app** → select this repo → set main file to `app3_plotly.py`
4. Click **Deploy** — you'll get a public URL in ~2 minutes

> Free tier apps sleep after inactivity; first load after sleeping takes ~30 seconds.

See [`DEPLOY.md`](DEPLOY.md) for full details and troubleshooting tips.

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` on startup | Run `pip install -r requirements.txt` |
| `simulation3_plotly.py not found` | Ensure both `.py` files are in the same folder |
| Blank page on first load | Wait 10–30 seconds and refresh |
| Port 8501 already in use | Add `--server.port 8502` to the run command |
| App stops when terminal closes | Use Windows Task Scheduler, or `nohup streamlit run app3_plotly.py &` on Linux/Mac |

---

## 📦 Requirements

```
streamlit>=1.32.0
pandas>=1.5.0
numpy>=1.23.0
matplotlib>=3.6.0
plotly>=5.0.0
```

---

## 📄 License

This project is not currently licensed. All rights reserved by the repository owner.
