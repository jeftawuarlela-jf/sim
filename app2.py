"""
Supply Chain Simulation – Streamlit Web App
Run with:  streamlit run app2.py
"""

import streamlit as st
import subprocess
import sys
import os
import io
import zipfile
import tempfile
import textwrap
import glob
import time
import pandas as pd
from datetime import date, datetime

# ─────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Supply Chain Simulation",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stSidebar"] { background: #1e2a38; }
    [data-testid="stSidebar"] * { color: #e0e6ef !important; }
    [data-testid="stSidebar"] .stMarkdown h3 { color: #7eb8f7 !important; font-size: 0.85rem;
        text-transform: uppercase; letter-spacing: 1px; margin-top: 1.2rem; }
    .run-box { background: #eaf4ff; border-left: 4px solid #2980b9;
        padding: 1rem; border-radius: 6px; margin-bottom: 1rem; }
    .success-box { background: #eafaf1; border-left: 4px solid #27ae60;
        padding: 1rem; border-radius: 6px; }
    .log-box { background: #0d1117; color: #c9d1d9; font-family: monospace;
        font-size: 0.78rem; padding: 1rem; border-radius: 6px;
        max-height: 400px; overflow-y: auto; white-space: pre-wrap; }
    div[data-testid="metric-container"] { background: #f7f9fc;
        border: 1px solid #e0e6ef; border-radius: 8px; padding: 0.5rem; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# Sidebar – Configuration
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/supply-chain.png", width=60)
    st.title("Simulation Config")

    st.markdown("### 📁 Data File")
    uploaded_file = st.file_uploader(
        "Upload CSV data file", type=["csv"],
        help="Upload your inventory/sales CSV file (e.g. final2.csv)"
    )

    st.markdown("### 🔄 Reorder Trigger (RT)")
    col1, col2 = st.columns(2)
    with col1:
        rt_start = st.number_input("Start", min_value=1, max_value=99,  value=21, step=1)
    with col2:
        rt_stop  = st.number_input("Stop ①", min_value=2, max_value=100, value=22, step=1,
                                    help="Exclusive — e.g. Start=21, Stop=23 tests RT 21 and 22")

    st.markdown("### 🎯 Target DOI")
    col3, col4 = st.columns(2)
    with col3:
        doi_start = st.number_input("Start ",  min_value=1,   max_value=364, value=27, step=1)
    with col4:
        doi_stop  = st.number_input("Stop ②", min_value=2,   max_value=365, value=30, step=1,
                                    help="Exclusive — e.g. Start=27, Stop=30 tests DOI 27, 28, and 29")

    st.markdown("### 🏭 Capacity Limits")
    daily_cap = st.number_input("Daily SKU Capacity",  min_value=1, value=360,  step=10,
                                 help="Max unique SKUs your warehouse processes per day")
    total_cap = st.number_input("Total SKU Capacity",  min_value=1, value=5100, step=100,
                                 help="Total unique SKU count the warehouse can hold")

    st.markdown("### 📆 Simulation Period")
    start_date = st.date_input("Start Date", value=date(2026, 2, 1))
    end_date   = st.date_input("End Date",   value=date(2026, 3, 31))

    st.markdown("### 💾 Output Options")
    save_detailed = st.checkbox("Save detailed per-SKU results", value=True)
    save_daily    = st.checkbox("Save daily summaries",          value=True)

    st.markdown("---")
    st.caption("① ② Stop is exclusive (like Python's range())")

# ─────────────────────────────────────────────────────────────
# Validation helper
# ─────────────────────────────────────────────────────────────
def validate() -> list[str]:
    errors = []
    if rt_stop <= rt_start:
        errors.append("RT Stop must be greater than RT Start.")
    if doi_stop <= doi_start:
        errors.append("DOI Stop must be greater than DOI Start.")
    if end_date <= start_date:
        errors.append("End Date must be after Start Date.")
    if uploaded_file is None:
        errors.append("Please upload your CSV data file.")
    return errors

# ─────────────────────────────────────────────────────────────
# Config writer — writes a real config.py so simulation.py
# can import it normally, no monkey-patching needed.
# ─────────────────────────────────────────────────────────────
def write_config(work_dir: str, output_dir: str, csv_path: str) -> str:
    config_path = os.path.join(work_dir, "config.py")
    content = textwrap.dedent(f"""\
        REORDER_THRESHOLD_RANGE = range({rt_start}, {rt_stop})
        TARGET_DOI_RANGE        = range({doi_start}, {doi_stop})
        DAILY_SKU_CAPACITY      = {daily_cap}
        TOTAL_SKU_CAPACITY      = {total_cap}
        START_DATE = ({start_date.year}, {start_date.month}, {start_date.day})
        END_DATE   = ({end_date.year},   {end_date.month},   {end_date.day})
        DATA_FILE  = r'{csv_path}'
        OUTPUT_DIR = r'{output_dir}'
        SAVE_DETAILED_RESULTS = {save_detailed}
        SAVE_DAILY_SUMMARIES  = {save_daily}
    """)
    with open(config_path, "w") as f:
        f.write(content)
    return config_path

# ─────────────────────────────────────────────────────────────
# Main page
# ─────────────────────────────────────────────────────────────
st.title("📦 Supply Chain Simulation")
st.caption("Configure parameters in the sidebar, then click **Run Simulation** below.")

# Scenario preview
n_rt  = max(0, rt_stop - rt_start)
n_doi = max(0, doi_stop - doi_start)
n_scenarios = n_rt * n_doi

c1, c2, c3 = st.columns(3)
c1.metric("RT values to test",  n_rt,        f"RT {rt_start} → {rt_stop - 1}")
c2.metric("DOI values to test", n_doi,       f"DOI {doi_start} → {doi_stop - 1}")
c3.metric("Total scenarios",    n_scenarios, "combinations")

st.divider()

# ─── Run button ───────────────────────────────────────────────
run_clicked = st.button("▶  Run Simulation", type="primary",
                         use_container_width=True,
                         disabled=(uploaded_file is None))

if run_clicked:
    errors = validate()
    if errors:
        for e in errors:
            st.error(e)
        st.stop()

    # ── Set up working directories ──
    run_id   = datetime.now().strftime("%Y%m%d_%H%M%S")
    work_dir = tempfile.mkdtemp(prefix="sim_work_")
    out_dir  = tempfile.mkdtemp(prefix=f"sim_out_{run_id}_")

    # Save the uploaded CSV
    csv_path = os.path.join(work_dir, uploaded_file.name)
    with open(csv_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Write config.py and copy simulation.py into work_dir
    write_config(work_dir, out_dir, csv_path)

    # Find simulation.py — either next to this app or uploaded earlier
    sim_src = os.path.join(os.path.dirname(__file__), "simulation.py")
    if not os.path.exists(sim_src):
        st.error("simulation.py not found next to app.py. Please place both files in the same folder.")
        st.stop()

    import shutil
    shutil.copy(sim_src, os.path.join(work_dir, "simulation.py"))

    # ── Live log area ──
    st.markdown("### 🖥️ Simulation Log")
    log_placeholder = st.empty()
    log_lines = []

    def render_log():
        log_placeholder.markdown(
            f'<div class="log-box">{"".join(log_lines)}</div>',
            unsafe_allow_html=True,
        )

    status_placeholder = st.empty()
    status_placeholder.info("⏳  Simulation running — this may take a few minutes…")

    # ── Run simulation as subprocess ──
    proc = subprocess.Popen(
        [sys.executable, "simulation.py"],
        cwd=work_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    for line in proc.stdout:
        log_lines.append(line)
        render_log()

    proc.wait()
    success = (proc.returncode == 0)

    # ── Outcome ──
    if success:
        status_placeholder.success("✅  Simulation completed successfully!")
    else:
        status_placeholder.error("❌  Simulation failed — see log above for details.")
        st.stop()

    # ─────────────────────────────────────────────────────────
    # Results section
    # ─────────────────────────────────────────────────────────
    st.divider()
    st.markdown("## 📊 Results")

    # Find summary CSV
    csv_files = glob.glob(os.path.join(out_dir, "scenario_comparison_summary_byday_*.csv"))
    if csv_files:
        summary_csv = csv_files[0]
        df = pd.read_csv(summary_csv)

        st.markdown("### 📋 Scenario Comparison Table")
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Quick metrics from best scenario
        if "Days_Over_Capacity" in df.columns:
            best_row = df.loc[df["Days_Over_Capacity"].idxmin()]
            st.markdown("#### 🏆 Best Scenario (fewest days over capacity)")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Scenario",            best_row.get("Scenario", "—"))
            m2.metric("Days Over Capacity",  int(best_row.get("Days_Over_Capacity", 0)))
            m3.metric("Capacity Util %",     f"{best_row.get('Capacity_Utilization_Pct', 0):.1f}%")
            m4.metric("Stockout Rate %",     f"{best_row.get('Stockout_Rate_Pct', 0):.2f}%")

    # Charts
    png_files = sorted(glob.glob(os.path.join(out_dir, "*.png")))
    if png_files:
        st.markdown("### 📈 Charts")
        for png in png_files:
            chart_name = os.path.basename(png).replace("_", " ").replace(".png", "").title()
            with st.expander(f"📊 {chart_name}", expanded=False):
                st.image(png, use_container_width=True)

    # ─────────────────────────────────────────────────────────
    # ZIP download
    # ─────────────────────────────────────────────────────────
    st.markdown("### ⬇️ Download All Results")
    zip_buffer = io.BytesIO()
    all_output_files = glob.glob(os.path.join(out_dir, "*"))

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fpath in all_output_files:
            zf.write(fpath, arcname=os.path.basename(fpath))

    zip_buffer.seek(0)
    st.download_button(
        label="📥 Download Results ZIP (CSVs + Charts)",
        data=zip_buffer,
        file_name=f"simulation_results_{run_id}.zip",
        mime="application/zip",
        use_container_width=True,
        type="primary",
    )

# ─────────────────────────────────────────────────────────────
# Footer — only shown before running
# ─────────────────────────────────────────────────────────────
else:
    st.markdown("""
    <div class="run-box">
    <strong>How to use:</strong><br>
    1. Upload your CSV data file using the sidebar<br>
    2. Adjust the configuration parameters as needed<br>
    3. Click <strong>▶ Run Simulation</strong> above<br>
    4. Watch the live log, then download your results as a ZIP
    </div>
    """, unsafe_allow_html=True)

    with st.expander("ℹ️ Parameter Guide"):
        st.markdown("""
        | Parameter | What it does |
        |---|---|
        | **RT Start / Stop** | Range of Reorder Threshold values tested. Stop is exclusive — Start=21, Stop=23 tests RT 21 and 22 |
        | **DOI Start / Stop** | Range of Days-of-Inventory Target tested. Stop is exclusive — Start=27, Stop=30 tests DOI 27, 28, and 29 |
        | **Daily SKU Capacity** | Max unique SKUs the inbound can receive in a single day |
        | **Total SKU Capacity** | Total number of unique SKUs the warehouse can hold |
        | **Start / End Date** | The period to simulate |
        """)
