import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import random
import os
from itertools import product

# Import configuration
try:
    from config import *
    print("✓ Configuration loaded from config.py")
except ImportError:
    print("⚠️  config.py not found, using default values")
    # Default configuration
    REORDER_THRESHOLD_RANGE = 20
    TARGET_DOI_RANGE = 35
    DAILY_SKU_CAPACITY = 360
    TOTAL_SKU_CAPACITY = 5100
    START_DATE = (2025, 7, 1)
    END_DATE = (2025, 12, 31)
    DATA_FILE = 'fulllead.csv'
    OUTPUT_DIR = 'simulation_results'
    SAVE_DETAILED_RESULTS = True
    SAVE_DAILY_SUMMARIES = True

# Convert date tuples to datetime objects if needed
if isinstance(START_DATE, tuple):
    START_DATE = datetime(*START_DATE)
if isinstance(END_DATE, tuple):
    END_DATE = datetime(*END_DATE)

# ========================================
# HELPER FUNCTIONS
# ========================================
def add_working_days(start_date, working_days):
    """
    Add working days to a date, skipping weekends.
    
    Args:
        start_date: Starting date
        working_days: Number of working days to add
    
    Returns:
        Date after adding working days
    """
    current_date = start_date
    days_added = 0
    
    while days_added < working_days:
        current_date += timedelta(days=1)
        # Check if it's a weekday (Monday=0, Sunday=6)
        if current_date.weekday() < 6:  # Monday to Friday
            days_added += 1
    
    return current_date

def run_single_simulation(sku_info, reorder_threshold, target_doi, date_range):
    """
    Run a single simulation with given parameters.
    
    Args:
        sku_info: DataFrame with SKU information
        reorder_threshold: Reorder threshold value
        target_doi: Target DOI value
        date_range: Date range for simulation
    
    Returns:
        DataFrame with simulation results
    """
    results = []
    
    for idx, sku_row in sku_info.iterrows():
        sku_code = sku_row['sku_code']
        product_name = sku_row['product_name']
        stock = sku_row['stock']
        qpd = sku_row['qpd']
        lead_time_days = int(sku_row['lead_time_days'])
        
        # Skip SKUs with no sales
        if qpd == 0 or pd.isna(qpd):
            continue
        
        # Track orders in transit: list of (arrival_date, quantity)
        orders_in_transit = []
        
        # Simulate each day
        for date in date_range:
            stock_beginning = stock
            
            # Check for arriving orders today
            arriving_orders = [order for order in orders_in_transit if order[0] == date]
            stock_received = sum([order[1] for order in arriving_orders])
            stock += stock_received
            
            # Remove received orders from transit list
            orders_in_transit = [order for order in orders_in_transit if order[0] != date]
            
            # Daily sales
            sales = qpd
            stock -= sales
            
            # Calculate DOI
            doi = stock / qpd if qpd > 0 else 999
            
            # Calculate total orders in transit
            total_in_transit = sum([order[1] for order in orders_in_transit])
            
            # Check if we need to reorder
            reorder_trigger = (doi <= reorder_threshold) and (len(orders_in_transit) == 0)
            
            order_placed = False
            order_quantity = 0
            
            if reorder_trigger:
                # Calculate order quantity to reach target DOI after lead time
                estimated_calendar_days = lead_time_days * 1.17
                order_quantity = (target_doi + estimated_calendar_days) * qpd - stock
                
                # Only place order if quantity is positive
                if order_quantity > 0:
                    order_placed = True
                    arrival_date = add_working_days(date, lead_time_days)
                    orders_in_transit.append((arrival_date, order_quantity))
            
            # Store daily results
            results.append({
                'date': date,
                'sku_code': sku_code,
                'product_name': product_name,
                'lead_time_days': lead_time_days,
                'stock_beginning': stock_beginning,
                'sales': sales,
                'stock_received': stock_received,
                'stock_ending': stock,
                'doi': doi,
                'order_placed': order_placed,
                'order_quantity': order_quantity,
                'orders_in_transit_qty': total_in_transit,
                'orders_in_transit_count': len(orders_in_transit)
            })
    
    return pd.DataFrame(results)

def analyze_simulation(results_df, reorder_threshold, target_doi, date_range):
    """
    Analyze simulation results and return key metrics.
    
    Args:
        results_df: DataFrame with simulation results
        reorder_threshold: Reorder threshold used
        target_doi: Target DOI used
        date_range: Date range of simulation
    
    Returns:
        Dictionary with analysis metrics
    """
    # Count unique SKUs that ARRIVED (received) each day
    daily_arrivals = results_df[results_df['stock_received'] > 0].groupby('date').agg({
        'sku_code': 'count'
    }).reset_index()
    daily_arrivals.columns = ['date', 'unique_skus_arrived']
    
    # Create complete date range (including days with 0 arrivals)
    all_dates = pd.DataFrame({'date': date_range})
    daily_arrivals = all_dates.merge(daily_arrivals, on='date', how='left').fillna(0)
    
    # Add day of week column
    daily_arrivals['day_of_week'] = daily_arrivals['date'].dt.day_name()
    
    # Calculate statistics
    avg_daily_skus = daily_arrivals['unique_skus_arrived'].mean()
    max_daily_skus = daily_arrivals['unique_skus_arrived'].max()
    median_daily_skus = daily_arrivals['unique_skus_arrived'].median()
    std_daily_skus = daily_arrivals['unique_skus_arrived'].std()
    
    # Days exceeding capacity
    days_over_capacity = (daily_arrivals['unique_skus_arrived'] > DAILY_SKU_CAPACITY).sum()
    
    # Binning analysis - categorize daily arrivals into ranges (EXCLUDING SUNDAYS)
    bins = [0, 30, 90, 180, 270, 360, 540, 720, float('inf')]
    bin_labels = ['0-30', '31-90', '91-180', '181-270', '271-360', '361-540', '541-720', '720+']
    
    # Filter out Sundays for binning analysis
    daily_arrivals_no_sunday = daily_arrivals[daily_arrivals['day_of_week'] != 'Sunday'].copy()
    
    daily_arrivals_no_sunday['bin'] = pd.cut(daily_arrivals_no_sunday['unique_skus_arrived'], 
                                              bins=bins, 
                                              labels=bin_labels, 
                                              include_lowest=True)
    
    # Count days in each bin (excluding Sundays)
    bin_counts = daily_arrivals_no_sunday['bin'].value_counts().sort_index()
    bin_distribution = dict(zip(bin_labels, [bin_counts.get(label, 0) for label in bin_labels]))
    
    # Total unique SKUs that arrived over the period
    total_unique_skus_arrived = results_df[results_df['stock_received'] > 0]['sku_code'].nunique()
    
    # Calculate average DOI
    avg_doi = results_df['doi'].mean()
    
    # Total orders placed
    total_orders = results_df['order_placed'].sum()
    
    # Calculate overload days by day of week
    daily_arrivals['is_overload'] = daily_arrivals['unique_skus_arrived'] > DAILY_SKU_CAPACITY
    overload_by_day = daily_arrivals.groupby('day_of_week')['is_overload'].sum().to_dict()
    
    # Calculate average arrivals by day of week
    avg_arrivals_by_day = daily_arrivals.groupby('day_of_week')['unique_skus_arrived'].mean().to_dict()
    
    return {
        'reorder_threshold': reorder_threshold,
        'target_doi': target_doi,
        'avg_daily_skus': avg_daily_skus,
        'max_daily_skus': max_daily_skus,
        'median_daily_skus': median_daily_skus,
        'std_daily_skus': std_daily_skus,
        'days_over_capacity': days_over_capacity,
        'pct_days_over_capacity': (days_over_capacity / len(date_range) * 100),
        'capacity_utilization': (avg_daily_skus / DAILY_SKU_CAPACITY * 100),
        'total_unique_skus_arrived': total_unique_skus_arrived,
        'total_capacity_utilization': (total_unique_skus_arrived / TOTAL_SKU_CAPACITY * 100),
        'total_orders': total_orders,
        'avg_doi': avg_doi,
        'daily_arrivals': daily_arrivals,
        'overload_by_day': overload_by_day,
        'avg_arrivals_by_day': avg_arrivals_by_day,
        'bin_distribution': bin_distribution
    }

# ========================================
# MAIN EXECUTION
# ========================================
def main():
    # Generate a unique run ID based on current datetime
    run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    print(f"Run ID: {run_id}")
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Load data
    print("Loading data...")
    df = pd.read_csv(DATA_FILE)
    df['tanggal_update'] = pd.to_datetime(df['tanggal_update'])
    
    
    # Prepare starting inventory
    print("\nPreparing starting inventory (July 1, 2025)...")
    july_1 = datetime(2025, 7, 1)
    starting_data = df[df['tanggal_update'] == july_1].copy()
    
    if len(starting_data) == 0:
        print(f"Warning: No data for July 1, using first available date: {df['tanggal_update'].min()}")
        starting_data = df[df['tanggal_update'] == df['tanggal_update'].min()].copy()
    
    sku_info = starting_data.groupby('sku_code').agg({
        'product_name': 'first',
        'stock': 'first',
        'qpd': 'first',
        'doi': 'first',
        'lead_time_days': 'first'
    }).reset_index()
    
    print(f"Starting with {len(sku_info)} unique SKUs")
    print(f"Lead time range: {sku_info['lead_time_days'].min():.0f} to {sku_info['lead_time_days'].max():.0f} working days")
    
    # Generate date range
    date_range = pd.date_range(START_DATE, END_DATE, freq='D')
    
    # Generate all parameter combinations
    param_combinations = list(product(REORDER_THRESHOLD_RANGE, TARGET_DOI_RANGE))
    total_scenarios = len(param_combinations)
    
    
    # Store all results
    all_scenario_results = []
    
    # Define day order for proper sorting
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    # Run simulations for each combination
    for scenario_num, (reorder_threshold, target_doi) in enumerate(param_combinations, 1):
        print(f"\nScenario {scenario_num}/{total_scenarios}: Reorder Threshold={reorder_threshold}, Target DOI={target_doi}")
        
        
        # Run simulation
        results_df = run_single_simulation(sku_info, reorder_threshold, target_doi, date_range)
        
        # Analyze results
        analysis = analyze_simulation(results_df, reorder_threshold, target_doi, date_range)
        all_scenario_results.append(analysis)
        
        
       
    # Create comparison summary
    print(f"\n{'='*60}")
    print("CREATING COMPARISON SUMMARY")
    print(f"{'='*60}")
    
    comparison_df = pd.DataFrame([
        {
            'Scenario': f"RT{r['reorder_threshold']}_DOI{r['target_doi']}",
            'Reorder_Threshold': r['reorder_threshold'],
            'Target_DOI': r['target_doi'],
            'Avg_Daily_SKUs': round(r['avg_daily_skus'], 2),
            'Max_Daily_SKUs': int(r['max_daily_skus']),
            'Days_Over_Capacity': int(r['days_over_capacity']),
            'Pct_Days_Over_Capacity': round(r['pct_days_over_capacity'], 2),
            'Capacity_Utilization_Pct': round(r['capacity_utilization'], 2),
            'Total_Orders': int(r['total_orders']),
            'Avg_DOI': round(r['avg_doi'], 2),
            # Add overload days by day of week
            'Overload_Monday': int(r['overload_by_day'].get('Monday', 0)),
            'Overload_Tuesday': int(r['overload_by_day'].get('Tuesday', 0)),
            'Overload_Wednesday': int(r['overload_by_day'].get('Wednesday', 0)),
            'Overload_Thursday': int(r['overload_by_day'].get('Thursday', 0)),
            'Overload_Friday': int(r['overload_by_day'].get('Friday', 0)),
            'Overload_Saturday': int(r['overload_by_day'].get('Saturday', 0)),
            'Overload_Sunday': int(r['overload_by_day'].get('Sunday', 0)),
            # Add average arrivals by day of week
            'Avg_Monday': round(r['avg_arrivals_by_day'].get('Monday', 0), 2),
            'Avg_Tuesday': round(r['avg_arrivals_by_day'].get('Tuesday', 0), 2),
            'Avg_Wednesday': round(r['avg_arrivals_by_day'].get('Wednesday', 0), 2),
            'Avg_Thursday': round(r['avg_arrivals_by_day'].get('Thursday', 0), 2),
            'Avg_Friday': round(r['avg_arrivals_by_day'].get('Friday', 0), 2),
            'Avg_Saturday': round(r['avg_arrivals_by_day'].get('Saturday', 0), 2),
            'Avg_Sunday': round(r['avg_arrivals_by_day'].get('Sunday', 0), 2)
        }
        for r in all_scenario_results
    ])
    
    # Sort by multiple criteria for better analysis
    comparison_df = comparison_df.sort_values(['Reorder_Threshold', 'Target_DOI'])
    
    # Save comparison summary
    comparison_df.to_csv(os.path.join(OUTPUT_DIR, f'scenario_comparison_summary_byday_{run_id}.csv'), index=False)
    
    # Display comparison table
    print("\n" + "="*60)
    print("SCENARIO COMPARISON TABLE")
    print("="*60)
    print(comparison_df.to_string(index=False))
    
    # Find optimal scenarios
    print("\n" + "="*60)
    print("OPTIMAL SCENARIO ANALYSIS")
    print("="*60)
    
    # Best scenario for minimizing capacity overload
    best_capacity = comparison_df.loc[comparison_df['Days_Over_Capacity'].idxmin()]
    print(f"\n✓ Best for capacity (fewest days over limit):")
    print(f"  Scenario: {best_capacity['Scenario']}")
    print(f"  Days over capacity: {best_capacity['Days_Over_Capacity']}")
    print(f"  Capacity utilization: {best_capacity['Capacity_Utilization_Pct']:.1f}%")
    
    
    # ========================================
    # SHARED SETUP FOR ALL CHARTS
    # ========================================
    print("\n" + "="*60)
    print("CREATING ALL VISUALIZATIONS (Grouped by Reorder Threshold)")
    print("="*60)
    
    # Extract unique reorder thresholds and target DOIs
    reorder_thresholds = sorted(set(r['reorder_threshold'] for r in all_scenario_results))
    target_dois = sorted(set(r['target_doi'] for r in all_scenario_results))
    num_thresholds = len(reorder_thresholds)
    num_scenarios = len(all_scenario_results)
    
    # Generate colors per target_doi
    doi_colors = plt.cm.Set2(np.linspace(0, 1, len(target_dois)))
    doi_color_map = {doi: doi_colors[i] for i, doi in enumerate(target_dois)}
    
    # Generate colors per day of week
    day_colors = plt.cm.Set2(np.linspace(0, 1, len(day_order)))
    day_color_map = {day: day_colors[i] for i, day in enumerate(day_order)}
    
    # Bin labels and colors
    bin_labels = ['0-30', '31-90', '91-180', '181-270', '271-360', '361-540', '541-720', '720+']
    bin_colors = plt.cm.tab10(np.linspace(0, 1, len(bin_labels)))
    bin_color_map = {bl: bin_colors[i] for i, bl in enumerate(bin_labels)}
    
    # Helper to ensure axes is iterable
    def ensure_axes_list(axes_obj, n):
        if n == 1:
            return [axes_obj]
        return axes_obj
    
    # Shared positional / width variables
    x_days = np.arange(len(day_order))
    x_doi_pos = np.arange(len(target_dois))
    width_doi = 0.8 / len(target_dois)
    width_day = 0.8 / len(day_order)
    
    # Global y-max values for consistent scaling
    all_avg_values = [r['avg_arrivals_by_day'].get(d, 0) for r in all_scenario_results for d in day_order]
    y_max_avg = max(all_avg_values) * 1.20
    
    all_overload_values = [int(r['overload_by_day'].get(d, 0)) for r in all_scenario_results for d in day_order]
    y_max_overload = max(all_overload_values) * 1.20 if max(all_overload_values) > 0 else 10
    
    # ========================================
    # CHART 3b: Overload Days Transposed (X=DOIs, bars=days) — grouped by RT
    # ========================================
    
    fig2b, axes2b = plt.subplots(
        nrows=num_thresholds, ncols=1,
        figsize=(16, 6 * num_thresholds),
        sharey=True
    )
    axes2b = ensure_axes_list(axes2b, num_thresholds)
    
    for ax, rt in zip(axes2b, reorder_thresholds):
        rt_scenarios = [r for r in all_scenario_results if r['reorder_threshold'] == rt]
        
        for i, day in enumerate(day_order):
            day_values = []
            for doi in target_dois:
                match = next((r for r in rt_scenarios if r['target_doi'] == doi), None)
                day_values.append(int(match['overload_by_day'].get(day, 0)) if match else 0)
            
            offset = (i - len(day_order)/2 + 0.5) * width_day
            bars = ax.bar(x_doi_pos + offset, day_values, width_day, label=day,
                         color=day_color_map[day], alpha=0.8, edgecolor='black')
            for bar, val in zip(bars, day_values):
                if val > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                           f'{val}', ha='center', va='bottom', fontsize=7, rotation=90)
        
        ax.set_xlabel('Target DOI', fontsize=12)
        ax.set_ylabel('Number of Overload Days', fontsize=12)
        ax.set_title(f'Reorder Threshold: {rt}', fontsize=13, fontweight='bold')
        ax.set_xticks(x_doi_pos)
        ax.set_xticklabels([f'DOI {doi}' for doi in target_dois], fontsize=10)
        ax.set_ylim(0, y_max_overload)
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')
    
    fig2b.suptitle(f'Overload Days by Target DOI — Grouped by Reorder Threshold\n(Days Exceeding {DAILY_SKU_CAPACITY} SKU Capacity)',
                   fontsize=15, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f'comparison_overload_days_bydoi_grouped_by_rt_{run_id}.png'), dpi=300, bbox_inches='tight')
    
    # ========================================
    # CHART 4: Avg Arrivals Transposed (X=DOIs, bars=days) — grouped by RT
    # ========================================
    
    fig3, axes3 = plt.subplots(
        nrows=num_thresholds, ncols=1,
        figsize=(16, 6 * num_thresholds),
        sharey=True
    )
    axes3 = ensure_axes_list(axes3, num_thresholds)
    
    x_doi_pos = np.arange(len(target_dois))
    width_day = 0.8 / len(day_order)
    
    for ax, rt in zip(axes3, reorder_thresholds):
        rt_scenarios = [r for r in all_scenario_results if r['reorder_threshold'] == rt]
        
        for i, day in enumerate(day_order):
            day_values = []
            for doi in target_dois:
                match = next((r for r in rt_scenarios if r['target_doi'] == doi), None)
                day_values.append(match['avg_arrivals_by_day'].get(day, 0) if match else 0)
            
            offset = (i - len(day_order)/2 + 0.5) * width_day
            bars = ax.bar(x_doi_pos + offset, day_values, width_day, label=day,
                         color=day_color_map[day], alpha=0.8, edgecolor='black')
            for bar, val in zip(bars, day_values):
                if val > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                           f'{val:.0f}', ha='center', va='bottom', fontsize=7, rotation=90)
        
        ax.axhline(y=DAILY_SKU_CAPACITY, color='r', linestyle='--', linewidth=2, label=f'Capacity ({DAILY_SKU_CAPACITY})')
        ax.set_xlabel('Target DOI', fontsize=12)
        ax.set_ylabel('Average Unique SKUs Arrived', fontsize=12)
        ax.set_title(f'Reorder Threshold: {rt}', fontsize=13, fontweight='bold')
        ax.set_xticks(x_doi_pos)
        ax.set_xticklabels([f'DOI {doi}' for doi in target_dois], fontsize=10)
        ax.set_ylim(0, y_max_avg)
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')
    
    fig3.suptitle('Average SKU Arrivals by Target DOI — Grouped by Reorder Threshold',
                  fontsize=15, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f'comparison_avg_arrivals_bydoi_grouped_by_rt_{run_id}.png'), dpi=300, bbox_inches='tight')
    
    
    # ========================================
    # CHART 6: Transposed Binning (X=DOIs, bars=bins) — grouped by RT
    # ========================================
    
    fig5, axes5 = plt.subplots(
        nrows=num_thresholds, ncols=1,
        figsize=(16, 6 * num_thresholds),
        sharey=True
    )
    axes5 = ensure_axes_list(axes5, num_thresholds)
    
    # Global y-max for binning
    all_bin_values = [int(r['bin_distribution'].get(bl, 0)) for r in all_scenario_results for bl in bin_labels]
    y_max_bin = max(all_bin_values) * 1.20 if max(all_bin_values) > 0 else 10
    
    width_bin = 0.8 / len(bin_labels)
    
    for ax, rt in zip(axes5, reorder_thresholds):
        rt_scenarios = [r for r in all_scenario_results if r['reorder_threshold'] == rt]
        
        for bin_idx, bl in enumerate(bin_labels):
            bin_values = []
            for doi in target_dois:
                match = next((r for r in rt_scenarios if r['target_doi'] == doi), None)
                bin_values.append(int(match['bin_distribution'].get(bl, 0)) if match else 0)
            
            offset = (bin_idx - len(bin_labels)/2 + 0.5) * width_bin
            bars = ax.bar(x_doi_pos + offset, bin_values, width_bin, label=bl,
                         color=bin_color_map[bl], alpha=0.8, edgecolor='black')
            for bar, val in zip(bars, bin_values):
                if val > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                           f'{val}', ha='center', va='bottom', fontsize=7, rotation=90)
        
        ax.set_xlabel('Target DOI', fontsize=12)
        ax.set_ylabel('Number of Days', fontsize=12)
        ax.set_title(f'Reorder Threshold: {rt}', fontsize=13, fontweight='bold')
        ax.set_xticks(x_doi_pos)
        ax.set_xticklabels([f'DOI {doi}' for doi in target_dois], fontsize=10)
        ax.set_ylim(0, y_max_bin)
        ax.legend(loc='upper right', fontsize=9, title='Arrivals Range')
        ax.grid(True, alpha=0.3, axis='y')
    
    fig5.suptitle('Daily Arrivals Distribution by DOI — Grouped by Reorder Threshold',
                  fontsize=15, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f'comparison_binning_distribution_byscenario_{run_id}.png'), dpi=300, bbox_inches='tight')
    
    # ========================================
    # CHART 7: Avg Arrivals (X=RT, bars=days) — subplots by DOI
    # ========================================
    
    num_dois = len(target_dois)
    
    fig7, axes7 = plt.subplots(
        nrows=num_dois, ncols=1,
        figsize=(16, 6 * num_dois),
        sharey=True
    )
    axes7 = ensure_axes_list(axes7, num_dois)
    
    x_rt = np.arange(len(reorder_thresholds))
    width_day_rt = 0.8 / len(day_order)
    
    for ax, doi in zip(axes7, target_dois):
        doi_scenarios = [r for r in all_scenario_results if r['target_doi'] == doi]
        
        for i, day in enumerate(day_order):
            day_values = []
            for rt in reorder_thresholds:
                match = next((r for r in doi_scenarios if r['reorder_threshold'] == rt), None)
                day_values.append(match['avg_arrivals_by_day'].get(day, 0) if match else 0)
            
            offset = (i - len(day_order)/2 + 0.5) * width_day_rt
            bars = ax.bar(x_rt + offset, day_values, width_day_rt, label=day,
                         color=day_color_map[day], alpha=0.8, edgecolor='black')
            for bar, val in zip(bars, day_values):
                if val > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                           f'{val:.0f}', ha='center', va='bottom', fontsize=7, rotation=90)
        
        ax.axhline(y=DAILY_SKU_CAPACITY, color='r', linestyle='--', linewidth=2, label=f'Capacity ({DAILY_SKU_CAPACITY})')
        ax.set_xlabel('Reorder Threshold', fontsize=12)
        ax.set_ylabel('Average Unique SKUs Arrived', fontsize=12)
        ax.set_title(f'Target DOI: {doi}', fontsize=13, fontweight='bold')
        ax.set_xticks(x_rt)
        ax.set_xticklabels([f'RT {rt}' for rt in reorder_thresholds], fontsize=10)
        ax.set_ylim(0, y_max_avg)
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')
    
    fig7.suptitle('Average SKU Arrivals by Reorder Threshold — Grouped by Target DOI',
                  fontsize=15, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f'comparison_avg_arrivals_byrt_grouped_by_doi_{run_id}.png'), dpi=300, bbox_inches='tight')
    
    # ========================================
    # CHART 8: Overload Days (X=RT, bars=days) — subplots by DOI
    # ========================================
    
    fig8, axes8 = plt.subplots(
        nrows=num_dois, ncols=1,
        figsize=(16, 6 * num_dois),
        sharey=True
    )
    axes8 = ensure_axes_list(axes8, num_dois)
    
    for ax, doi in zip(axes8, target_dois):
        doi_scenarios = [r for r in all_scenario_results if r['target_doi'] == doi]
        
        for i, day in enumerate(day_order):
            day_values = []
            for rt in reorder_thresholds:
                match = next((r for r in doi_scenarios if r['reorder_threshold'] == rt), None)
                day_values.append(int(match['overload_by_day'].get(day, 0)) if match else 0)
            
            offset = (i - len(day_order)/2 + 0.5) * width_day_rt
            bars = ax.bar(x_rt + offset, day_values, width_day_rt, label=day,
                         color=day_color_map[day], alpha=0.8, edgecolor='black')
            for bar, val in zip(bars, day_values):
                if val > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                           f'{val}', ha='center', va='bottom', fontsize=7, rotation=90)
        
        ax.set_xlabel('Reorder Threshold', fontsize=12)
        ax.set_ylabel('Number of Overload Days', fontsize=12)
        ax.set_title(f'Target DOI: {doi}', fontsize=13, fontweight='bold')
        ax.set_xticks(x_rt)
        ax.set_xticklabels([f'RT {rt}' for rt in reorder_thresholds], fontsize=10)
        ax.set_ylim(0, y_max_overload)
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')
    
    fig8.suptitle(f'Overload Days by Reorder Threshold — Grouped by Target DOI\n(Days Exceeding {DAILY_SKU_CAPACITY} SKU Capacity)',
                  fontsize=15, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f'comparison_overload_days_by_rt_grouped_by_doi_{run_id}.png'), dpi=300, bbox_inches='tight')
    
    
    # ========================================
    # CHART 9: Binning Distribution (X=RT, bars=bins) — subplots by DOI
    # ========================================
    
    fig9, axes9 = plt.subplots(
        nrows=num_dois, ncols=1,
        figsize=(16, 6 * num_dois),
        sharey=True
    )
    axes9 = ensure_axes_list(axes9, num_dois)
    
    width_bin_rt = 0.8 / len(bin_labels)
    
    for ax, doi in zip(axes9, target_dois):
        doi_scenarios = [r for r in all_scenario_results if r['target_doi'] == doi]
        
        for bin_idx, bl in enumerate(bin_labels):
            bin_values = []
            for rt in reorder_thresholds:
                match = next((r for r in doi_scenarios if r['reorder_threshold'] == rt), None)
                bin_values.append(int(match['bin_distribution'].get(bl, 0)) if match else 0)
            
            offset = (bin_idx - len(bin_labels)/2 + 0.5) * width_bin_rt
            bars = ax.bar(x_rt + offset, bin_values, width_bin_rt, label=bl,
                         color=bin_color_map[bl], alpha=0.8, edgecolor='black')
            for bar, val in zip(bars, bin_values):
                if val > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                           f'{val}', ha='center', va='bottom', fontsize=7, rotation=90)
        
        ax.set_xlabel('Reorder Threshold', fontsize=12)
        ax.set_ylabel('Number of Days', fontsize=12)
        ax.set_title(f'Target DOI: {doi}', fontsize=13, fontweight='bold')
        ax.set_xticks(x_rt)
        ax.set_xticklabels([f'RT {rt}' for rt in reorder_thresholds], fontsize=10)
        ax.set_ylim(0, y_max_bin)
        ax.legend(loc='upper right', fontsize=9, title='Arrivals Range')
        ax.grid(True, alpha=0.3, axis='y')
    
    fig9.suptitle('Daily Arrivals Distribution by Reorder Threshold — Grouped by Target DOI',
                  fontsize=15, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f'comparison_binning_distribution_by_rt_grouped_by_doi_{run_id}.png'), dpi=300, bbox_inches='tight')

    # ========================================
    # CHART 10: Boxplot of Daily Arrivals — grouped by RT, X = DOI
    # ========================================

    fig10, axes10 = plt.subplots(
        nrows=num_thresholds, ncols=1,
        figsize=(14, 6 * num_thresholds),
        sharey=True
    )
    axes10 = ensure_axes_list(axes10, num_thresholds)

    for ax, rt in zip(axes10, reorder_thresholds):
        rt_scenarios = [r for r in all_scenario_results if r['reorder_threshold'] == rt]

        # Build one array of daily values per DOI
        box_data = []
        box_labels = []
        for doi in target_dois:
            match = next((r for r in rt_scenarios if r['target_doi'] == doi), None)
            if match:
                # Use only non-Sunday days to stay consistent with other charts
                arrivals = match['daily_arrivals']
                filtered = arrivals[arrivals['day_of_week'] != 'Sunday']['unique_skus_arrived'].values
                box_data.append(filtered)
            else:
                box_data.append([])
            box_labels.append(f'DOI {doi}')

        # Draw boxplots
        bp = ax.boxplot(
            box_data,
            labels=box_labels,
            patch_artist=True,          # allows box fill color
            medianprops=dict(color='black', linewidth=2),
            whiskerprops=dict(linewidth=1.5),
            capprops=dict(linewidth=1.5),
            flierprops=dict(marker='o', markersize=4, alpha=0.5, linestyle='none')
        )

        # Color each box using the same doi_color_map as other charts
        for patch, doi in zip(bp['boxes'], target_dois):
            patch.set_facecolor(doi_color_map[doi])
            patch.set_alpha(0.7)

        # Capacity reference line
        ax.axhline(
            y=DAILY_SKU_CAPACITY,
            color='red', linestyle='--', linewidth=2,
            label=f'Daily Capacity ({DAILY_SKU_CAPACITY})'
        )

        ax.set_xlabel('Target DOI', fontsize=12)
        ax.set_ylabel('Daily Unique SKUs Arrived', fontsize=12)
        ax.set_title(f'Reorder Threshold: {rt}', fontsize=13, fontweight='bold')
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')

    fig10.suptitle(
        'Distribution of Daily SKU Arrivals by Target DOI — Grouped by Reorder Threshold\n(Excluding Sundays)',
        fontsize=15, fontweight='bold', y=1.01
    )
    plt.tight_layout()
    plt.savefig(
        os.path.join(OUTPUT_DIR, f'comparison_boxplot_arrivals_{run_id}.png'),
        dpi=300, bbox_inches='tight'
    )
    plt.close(fig10)

    # ========================================
    # SUMMARY
    # ========================================
    print("\n" + "="*60)
    print("MULTI-SCENARIO ANALYSIS COMPLETE!")
    

if __name__ == "__main__":
    main()
