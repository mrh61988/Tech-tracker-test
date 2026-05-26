import streamlit as st
import pandas as pd
import numpy as np
import io
import datetime

# Set up the page layout
st.set_page_config(page_title="Tech Time Tracker", layout="wide")

# --- CSS FOR CLEAN LANDSCAPE FULL-WIDTH MULTI-PAGE PRINTING ---
st.markdown("""
<style>
@media print {
    /* Enforce landscape orientation to maximize wide printable space layout margins */
    @page {
        size: landscape;
        margin: 0.4in !important;
    }

    /* Hide structural utility blocks, upload buttons, tabs navigation bars, and panels from saved PDFs */
    header { display: none !important; }
    [data-testid="stHeader"] { display: none !important; }
    st.sidebar { display: none !important; }
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stSidebarCollapseButton"] { display: none !important; }
    [data-testid="stFileUploader"] { display: none !important; }
    [data-testid="stSelectbox"] { display: none !important; }
    div[data-baseweb="tab-list"] { display: none !important; }
    h1, .hide-on-print, .stAlert, iframe, button { display: none !important; }
    div[class*="stExpander"] { display: none !important; }
    
    /* Flatten flex and grid containers to standard sequential blocks to block overlapping */
    div[class*="stVerticalBlock"], 
    div[data-testid="element-container"],
    div[data-testid="stHorizontalBlock"],
    div[data-testid="column"] {
        display: block !important;
        position: static !important;
        float: none !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 100% !important;
        height: auto !important;
        max-height: none !important;
        overflow: visible !important;
        margin: 0 0 15px 0 !important;
        padding: 0 !important;
        box-shadow: none !important;
    }
    
    h2, h3, h4 {
        page-break-inside: avoid !important;
        page-break-after: avoid !important;
        margin-top: 20px !important;
        margin-bottom: 8px !important;
    }

    /* Unclamp core block layout canvas gutters to run margin-to-margin smoothly */
    div[data-testid="stAppViewBlockContainer"],
    .main .block-container,
    div[class*="block-container"] {
        max-width: 100% !important;
        width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    /* Forces summary KPI card layout objects to look clean side-by-side in Landscape */
    div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: wrap !important;
        width: 100% !important;
        gap: 12px !important;
    }
    div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) div[data-testid="column"] {
        display: inline-block !important;
        flex: 1 1 0% !important;
        min-width: 100px !important;
        width: auto !important;
        max-width: none !important;
        margin: 0 !important;
    }
    
    /* Grants wide tables and dataframes maximum layout canvas real estate */
    div[data-testid="stTable"], 
    div[data-testid="stTable"] > div,
    div[data-testid="stDataFrame"],
    div[data-testid="stDataFrame"] > div,
    table {
        width: 100% !important;
        max-width: 100% !important;
        min-width: 100% !important;
        display: block !important;
        height: auto !important;
        max-height: none !important;
        overflow: visible !important;
    }
    
    table {
        border-collapse: collapse !important;
        margin: 0 0 15px 0 !important;
    }
    tr {
        page-break-inside: avoid !important;
    }
    th, td {
        white-space: normal !important;
        word-break: break-word !important;
        overflow-wrap: break-word !important;
        padding: 4px 5px !important;
        font-size: 9.5px !important;
        text-align: left !important;
        line-height: 1.25 !important;
    }
    thead {
        display: table-header-group !important;
    }
}
</style>
""", unsafe_allow_html=True)
# ------------------------------

# --- GLOBAL HELPER & HIGHLIGHTING FUNCTIONS ---
def format_hm(hrs):
    if pd.isna(hrs) or hrs == 0: return "-"
    sign = "-" if hrs < 0 else ""
    hrs = abs(hrs)
    h = int(hrs)
    m = int(round((hrs - h) * 60))
    if m == 60:
        h += 1
        m = 0
    return f"{sign}{h}:{m:02d}"

def parse_hm(time_str):
    if pd.isna(time_str) or time_str == '-' or time_str == '':
        return 0.0
    try:
        clean_str = str(time_str).strip().rstrip(',').strip('"')
        parts = clean_str.split(':')
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return h + m / 60.0
    except:
        return 0.0

def parse_adj_hm(val_str):
    val_str = str(val_str).strip()
    if not val_str or val_str == '-' or val_str == '0' or val_str == '0:00':
        return 0.0
    try:
        sign = -1 if val_str.startswith('-') else 1
        clean_val = val_str.lstrip('+-').rstrip(',').strip('"')
        if ':' in clean_val:
            parts = clean_val.split(':')
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            return sign * (h + m / 60.0)
        else:
            return sign * float(clean_val)
    except:
        return 0.0

def parse_diff_to_hours(val):
    if val == '-' or pd.isna(val): return 0.0
    try:
        sign = -1 if str(val).startswith('-') else 1
        clean_val = str(val).replace('-', '').rstrip(',').strip('"')
        if ':' in clean_val:
            parts = clean_val.split(':')
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            return sign * (h + m / 60.0)
    except:
        pass
    return 0.0

# TIMEZONE NORMALIZATION LAYER WITH DEFENSIVE SHIFT GUARDRAIL
def parse_lowes_timestamp(val):
    if pd.isna(val) or str(val).strip() in ['', '-', 'NaT']:
        return pd.NaT
    try:
        s = str(val).strip()
        if 'GMT' in s:
            clean_s = s.split(' GMT')[0]
            dt = pd.to_datetime(clean_s, errors='coerce')
            if pd.notna(dt):
                if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                    pass
                else:
                    dt = dt - pd.Timedelta(hours=7)
        else:
            dt = pd.to_datetime(s, errors='coerce')
            
        if pd.notna(dt) and (dt.year < 2020 or dt.year > 2030):
            return pd.NaT
        return dt
    except:
        return pd.NaT

def check_late(row):
    if 'First_Punch' not in row or 'First_Status' not in row: return False
    fp = row['First_Punch']
    status = row['First_Status']
    if pd.isna(fp): return False
    if status in ['Lowes Store', 'On The Way']:
        return fp.hour >= 8
    elif status == 'In Progress':
        return fp.hour > 8 or (fp.hour == 8 and fp.minute >= 30)
    return False

def check_contractor(tech_str):
    CORE_TECHS = ['Bryan Pickett', 'Edward Lopez', 'Erik Tange', 'Matt Schlosser', 'Michael Owens', 'Nathan Smith', 'Sean Marble', 'Tanner LaForge']
    raw_members = [m.strip() for m in str(tech_str).split(',') if m.strip()]
    return not any(m in CORE_TECHS for m in raw_members)

def get_first_core_tech(tech_str):
    CORE_TECHS = ['Bryan Pickett', 'Edward Lopez', 'Erik Tange', 'Matt Schlosser', 'Michael Owens', 'Nathan Smith', 'Sean Marble', 'Tanner LaForge']
    raw_members = [m.strip() for m in str(tech_str).split(',') if m.strip()]
    core_members_on_job = [m for m in raw_members if m in CORE_TECHS]
    if core_members_on_job:
        return core_members_on_job[0]
    return None

def parse_az_city(addr):
    s = str(addr).lower()
    for c in ["prescott", "chandler", "scottsdale", "phoenix", "goodyear", "mesa", "glendale", "gilbert", "tempe", "peoria", "surprise", "buckeye", "avondale", "tucson", "marana", "maricopa", "sierra vista", "green valley"]:
        if c in s:
            return c.title()
    return "Phoenix Region"

def highlight_matrix_overhead(s):
    styles = []
    for val in s:
        try:
            if ' (Div: ' in str(val):
                tech_str, div_str = val.split(' (Div: ')
                t_h = parse_hm(tech_str)
                d_h = parse_hm(div_str.replace(')', ''))
                if t_h > d_h * 1.25 and t_h > 0:
                    styles.append('background-color: #ffcccc; color: #990000;')
                    continue
            styles.append('')
        except:
            styles.append('')
    return styles

def highlight_over_hour_row(row):
    styles = [''] * len(row)
    if 'Over Division Average By' in row.index:
        val = row['Over Division Average By']
        if '+' in str(val):
            hrs = parse_hm(str(val).replace('+', ''))
            if hrs > 1.0:
                return ['background-color: #ffcccc; color: #990000; font-weight: bold;'] * len(row)
    return styles

def get_assumed_pay(row):
    if 'Name' not in row or isinstance(row, bool): return 0.0
    nl = str(row['Name']).lower()
    clocked = row.get('Total_Weekly_Clocked_Hrs', 0.0)
    rev = row.get('Total_Assigned_Revenue', 0.0)
    
    if 'sean marble' in nl:
        base_salary = 70000.0 / 52.0
        penalty_burden = st.session_state.get('sean_absence_penalty_global', 0.0)
        return max(0.0, base_salary - penalty_burden)
    if 'michael owens' in nl:
        return 65000.0 / 52.0
    if 'bryan' in nl or 'erik' in nl:
        return rev * 0.33
        
    rate = 0.0
    if 'nate' in nl or 'nathan' in nl:
        rate = 22.50
    elif any(n in nl for n in ['edward', 'matt', 'tanner']):
        rate = 25.00
        
    if rate > 0:
        if clocked > 40.0:
            return (40.0 * rate) + ((clocked - 40.0) * rate * 1.5)  
        else:
            return clocked * rate
    return 0.0

def highlight_pay_pct_row(row):
    styles = [''] * len(row)
    if 'Pay % vs Assigned Revenue' in row.index and 'Name' in row.index:
        val = row['Pay % vs Assigned Revenue']
        name = str(row['Name']).lower()
        if val != '-' and pd.notna(val):
            try:
                v = float(str(val).replace('%', ''))
                idx = row.index.get_loc('Pay % vs Assigned Revenue')
                if 'bryan' in name or 'erik' in name:
                    if v < 34.0:
                        styles[idx] = 'background-color: #e6f4ea; color: #137333; font-weight: bold;'
                    else:
                        styles[idx] = 'background-color: #ffcccc; color: #990000;'
                else:
                    if v < 20.0:
                        styles[idx] = 'background-color: #e6f4ea; color: #137333; font-weight: bold;'
                    else:
                        styles[idx] = 'background-color: #ffcccc; color: #990000;'
            except:
                pass
    return styles

def highlight_low_margins(row):
    styles = [''] * len(row)
    if 'Line of Business' in row and 'Margin %' in row:
        try:
            bu = row['Line of Business']
            m_val = float(str(row['Margin %']).replace('%', '').strip())
            if 'Water Heaters' in bu and m_val < 35.0:
                return ['background-color: #ffcccc; color: #990000; font-weight: bold;'] * len(row)
            elif 'Simple Installs' in bu and m_val < 45.0:
                return ['background-color: #ffcccc; color: #990000; font-weight: bold;'] * len(row)
        except:
            pass
    return styles

# PROTECTED HOURLY ANALYSIS PAY DELEGATOR LAYER SECURED
def get_adjusted_table_pay(row):
    if isinstance(row, bool) or 'Name' not in row: return 0.0
    nl = str(row['Name']).lower()
    base_pay = get_assumed_pay(row)
    if 'sean marble' in nl:
        return max(0.0, base_pay)
    return base_pay

# NATIVE SYSTEM CLIPBOARD DATA EXPORTER (DEFINED AT GLOBAL SCOPE LEVEL)
def create_copy_button(df, raw_key):
    safe_key = "".join([c if c.isalnum() else "_" for c in raw_key])
    tsv_str = df.to_csv(sep='\t', index=False)
    safe_tsv = tsv_str.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')
    
    button_html = f"""
    <div class="hide-on-print" style="text-align: left; margin-top: 5px; margin-bottom: 8px;">
        <textarea id="tsv_{safe_key}" style="position: absolute; left: -9999px;">{safe_tsv}</textarea>
        <button id="btn_{safe_key}" onclick="copyTSV_{safe_key}()" style="background-color: #ffffff; color: #3c4043; padding: 6px 14px; border: 1px solid #dadce0; border-radius: 4px; cursor: pointer; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; font-weight: 500; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); transition: background-color 0.2s;">
            📋 Copy Table Data (For Email/Sheets/Docs)
        </button>
    </div>
    <script>
    function copyTSV_{safe_key}() {{
        var copyText = document.getElementById("tsv_{safe_key}");
        copyText.select();
        copyText.setSelectionRange(0, 999999);
        try {{
            var successful = document.execCommand('copy');
            var btn = document.getElementById("btn_{safe_key}");
            if (successful) {{
                btn.innerHTML = "✅ Copied table to clipboard!";
                btn.style.backgroundColor = "#e6f4ea";
                btn.style.color = "#137333";
                btn.style.borderColor = "#137333";
                setTimeout(function() {{
                    btn.innerHTML = "📋 Copy Table Data (For Email/Sheets/Docs)";
                    btn.style.backgroundColor = "#ffffff";
                    btn.style.color = "#3c4043";
                    btn.style.borderColor = "#dadce0";
                }}, 2000);
                }} else {{
                btn.innerHTML = "❌ Copy failed";
            }}
        }} catch (err) {{
            console.error('Execution fallback error:', err);
        }}
    }}
    </script>
    """
    st.components.v1.html(button_html, height=38)

# --- ADVANCED TIMELINE MATRICES ---
def run_baselines_matrix(ops_df):
    st.markdown("<h4>Advanced Team Processing Baselines Matrix</h4>", unsafe_allow_html=True)
    st.markdown("*(Technician tracking averages sorted by highest un-blended weekly duration totals. Store times ignore direct-to-site jobs)*")
    
    wh_jobs = ops_df[ops_df['Business Unit'] == 'Lowes - Water Heaters']
    lsi_jobs = ops_df[ops_df['Business Unit'] == 'Lowes - Simple Installs']
    
    div_avg_total = ops_df['Total_Job_Time_Hours'].mean() if not ops_df.empty else 0.0
    div_wh_baseline = wh_jobs['Total_Job_Time_Hours'].mean() if not wh_jobs.empty else 3.5
    div_lsi_baseline = lsi_jobs['Total_Job_Time_Hours'].mean() if not lsi_jobs.empty else 2.0
    
    wh_jobs_with_store = wh_jobs[wh_jobs['Store_Time_Hrs'] > 0]
    lsi_jobs_with_store = lsi_jobs[lsi_jobs['Store_Time_Hrs'] > 0]
    div_wh_store_baseline = wh_jobs_with_store['Store_Time_Hrs'].mean() if not wh_jobs_with_store.empty else 0.5
    div_lsi_store_baseline = lsi_jobs_with_store['Store_Time_Hrs'].mean() if not lsi_jobs_with_store.empty else 0.3
    
    st.markdown(f"""
    📊 **Current Division Baseline Averages (Store Averages Ignore Direct-To-Site Jobs):** &nbsp;&nbsp;•&nbsp;&nbsp;**Blended Total Avg:** `{format_hm(div_avg_total)}` &nbsp;&nbsp;|&nbsp;&nbsp; **WH Job Length:** `{format_hm(div_wh_baseline)}` &nbsp;&nbsp;|&nbsp;&nbsp; **LSI Job Length:** `{format_hm(div_lsi_baseline)}` 
    &nbsp;&nbsp;•&nbsp;&nbsp;**WH Store Delay:** `{format_hm(div_wh_store_baseline)}` &nbsp;&nbsp;|&nbsp;&nbsp; **LSI Store Delay:** `{format_hm(div_lsi_store_baseline)}`
    """)
    
    matrix_rows = []
    wh_over_baseline_rows = []
    lsi_over_baseline_rows = []
    
    for tech_name in sorted(ops_df['Assigned Team Members'].unique()):
        tech_jobs = ops_df[ops_df['Assigned Team Members'] == tech_name]
        
        t_wh = tech_jobs[tech_jobs['Business Unit'] == 'Lowes - Water Heaters']
        t_lsi = tech_jobs[tech_jobs['Business Unit'] == 'Lowes - Simple Installs']
        
        avg_total_val = tech_jobs['Total_Job_Time_Hours'].mean() if not tech_jobs.empty else np.nan
        avg_wh_val = t_wh['Total_Job_Time_Hours'].mean() if not t_wh.empty else np.nan
        avg_lsi_val = t_lsi['Total_Job_Time_Hours'].mean() if not t_lsi.empty else np.nan
        
        t_wh_store = t_wh[t_wh['Store_Time_Hrs'] > 0]
        t_lsi_store = t_lsi[t_lsi['Store_Time_Hrs'] > 0]
        avg_wh_store_val = t_wh_store['Store_Time_Hrs'].mean() if not t_wh_store.empty else np.nan
        avg_lsi_store_val = t_lsi_store['Store_Time_Hrs'].mean() if not t_lsi_store.empty else np.nan
        
        if not tech_jobs.empty:
            max_idx = tech_jobs['Total_Job_Time_Hours'].idxmax()
            max_job_val = tech_jobs['Total_Job_Time_Hours'].max()
            max_job_id = tech_jobs.loc[max_idx, '#ID'] if '#ID' in tech_jobs.columns else 'Unknown'
            if isinstance(max_job_id, float) and max_job_id.is_integer():
                max_job_id = int(max_job_id)
            max_job_str = f"{format_hm(max_job_val)} (ID: {max_job_id})"
        else:
            max_job_str = "-"
            
        if pd.notna(div_wh_baseline):
            for _, j in t_wh[t_wh['Total_Job_Time_Hours'] > div_wh_baseline].iterrows():
                jid = int(j['#ID']) if ('#ID' in j and isinstance(j['#ID'], float) and j['#ID'].is_integer()) else (j['#ID'] if '#ID' in j else 'Unknown')
                diff_val = j['Total_Job_Time_Hours'] - div_wh_baseline
                wh_over_baseline_rows.append({
                    "Technician": tech_name,
                    "Job ID": str(jid),
                    "Job Duration": format_hm(j['Total_Job_Time_Hours']),
                    "Over Division Average By": f"+{format_hm(diff_val)}",
                    "sort_key": diff_val
                })
        
        if pd.notna(div_lsi_baseline):
            for _, j in t_lsi[t_lsi['Total_Job_Time_Hours'] > div_lsi_baseline].iterrows():
                jid = int(j['#ID']) if ('#ID' in j and isinstance(j['#ID'], float) and j['#ID'].is_integer()) else (j['#ID'] if '#ID' in j else 'Unknown')
                diff_val = j['Total_Job_Time_Hours'] - div_lsi_baseline
                lsi_over_baseline_rows.append({
                    "Technician": tech_name,
                    "Job ID": str(jid),
                    "Job Duration": format_hm(j['Total_Job_Time_Hours']),
                    "Over Division Average By": f"+{format_hm(diff_val)}",
                    "sort_key": diff_val
                })
        
        matrix_rows.append({
            "Name": tech_name,
            "Total Avg Job Time": f"{format_hm(avg_total_val)} (Div: {format_hm(div_avg_total)})" if pd.notna(avg_total_val) else "-",
            "Avg WH Time": f"{format_hm(avg_wh_val)} (Div: {format_hm(div_wh_baseline)})" if pd.notna(avg_wh_val) else "-",
            "Avg LSI Time": f"{format_hm(avg_lsi_val)} (Div: {format_hm(div_lsi_baseline)})" if pd.notna(avg_lsi_val) else "-",
            "Avg WH Store Time": f"{format_hm(avg_wh_store_val)} (Div: {format_hm(div_wh_store_baseline)})" if pd.notna(avg_wh_store_val) else "-",
            "Avg LSI Store Time": f"{format_hm(avg_lsi_store_val)} (Div: {format_hm(div_lsi_store_baseline)})" if pd.notna(avg_lsi_store_val) else "-",
            "Max Single Job Length": max_job_str,
            "sort_key": avg_total_val if pd.notna(avg_total_val) else -1.0
        })
        
    matrix_df = pd.DataFrame(matrix_rows)
    if not matrix_df.empty:
        matrix_df = matrix_df.sort_values(by='sort_key', ascending=False).drop(columns=['sort_key'])
        
    try:
        styled_matrix = matrix_df.reset_index(drop=True).style.apply(highlight_matrix_overhead, subset=['Total Avg Job Time', 'Avg WH Time', 'Avg LSI Time', 'Avg WH Store Time', 'Avg LSI Store Time'])
        st.dataframe(styled_matrix, use_container_width=True) 
    except Exception:
        st.dataframe(matrix_df.reset_index(drop=True), use_container_width=True)
        
    create_copy_button(matrix_df, "baselines_matrix")
        
    st.markdown("<br><h4>🚨 Individual Over-Baseline Job Reference Breakdown</h4>", unsafe_allow_html=True)
    st.markdown("*(Granular tracking sheets isolating individual work orders exceeding the division run baselines, sorted largest variation to lowest. Rows >1 hour over are highlighted)*")
    
    split_col1, split_col2 = st.columns(2)
    with split_col1:
        st.markdown("##### 🛢️ Water Heaters Over-Baseline Jobs")
        if wh_over_baseline_rows:
            wh_matrix_df = pd.DataFrame(wh_over_baseline_rows).sort_values(by='sort_key', ascending=False).drop(columns=['sort_key']).reset_index(drop=True)
            try: st.dataframe(wh_matrix_df.style.apply(highlight_over_hour_row, axis=1), use_container_width=True)
            except Exception: st.dataframe(wh_matrix_df, use_container_width=True)
            create_copy_button(wh_matrix_df, "wh_over_baseline")
        else: st.success("✅ Zero individual Water Heater jobs exceeded the division baseline average.")
            
    with split_col2:
        st.markdown("##### 🔧 Simple Installs Over-Baseline Jobs")
        if lsi_over_baseline_rows:
            lsi_matrix_df = pd.DataFrame(lsi_over_baseline_rows).sort_values(by='sort_key', ascending=False).drop(columns=['sort_key']).reset_index(drop=True)
            try: st.dataframe(lsi_matrix_df.style.apply(highlight_over_hour_row, axis=1), use_container_width=True)
            except Exception: st.dataframe(lsi_matrix_df, use_container_width=True)
            create_copy_button(lsi_matrix_df, "lsi_over_baseline")
        else: st.success("✅ Zero individual Simple Install jobs exceeded the division baseline average.")

# --- MAIN BLOCK REPORT ENGINE ---
def show_advanced_reporting(unexploded_ops, ops_df, final_df, bounds_df, delayed_launches_df, daily_route, tab_key):
    st.markdown('<div class="hide-on-print"><br><hr><br></div>', unsafe_allow_html=True)
    st.header("📊 Ops Manager Tools (Benchmarking & Performance)")
    
    # Render baseline execution trackers natively at the head of the manager panel
    run_baselines_matrix(ops_df)
    st.markdown("<br><hr><br>", unsafe_allow_html=True)
    
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("⭐ The Gold Star High-Performer List")
        st.markdown("*(Technicians who average under 1:30 of unallocated difference per day worked. Store delays do NOT penalize techs)*")
        gold_star_df = final_df[(final_df['Daily_Avg_Diff_Hrs'] < 1.5) & (final_df['Days_Worked'] > 0)].copy()
        if not gold_star_df.empty:
            gold_star_df = gold_star_df.sort_values(by='Daily_Avg_Diff_Hrs', ascending=True)
            gold_star_df['Total Clocked'] = gold_star_df['Total_Weekly_Clocked_Hrs'].apply(format_hm)
            gold_star_df['Total Job Time'] = gold_star_df['Total_Weekly_Job_Hrs'].apply(format_hm)
            gold_star_df['Daily Avg Diff'] = gold_star_df['Daily_Avg_Diff_Hrs'].apply(format_hm)
            gold_star_df['Total Diff'] = gold_star_df['Total_Weekly_Diff_Hrs'].apply(format_hm)
            show_gold = gold_star_df[['Name', 'Total Clocked', 'Total Job Time', 'Daily Avg Diff', 'Total Diff']].copy()
            
            try: st.dataframe(show_gold.reset_index(drop=True).style.set_properties(**{'background-color': '#e6f4ea', 'color': '#137333'}), use_container_width=True)
            except Exception: st.dataframe(show_gold.reset_index(drop=True), use_container_width=True)
            create_copy_button(show_gold.reset_index(drop=True), f"gold_star_{tab_key}")

    with col_right:
        st.subheader("🎯 The Technician Skill Matrix & Training Flag")
        st.markdown("*(Compares a technician's LSI performance against their WH performance. Flags techs where the gap exceeds 15% sorted by priority warnings)*")
        skill_df = final_df.copy()
        if not skill_df.empty:
            skill_df['Eff Gap'] = np.where((skill_df['Simple_Installs_Count'] > 0) & (skill_df['Water_Heaters_Count'] > 0), abs(skill_df['LSI_Eff_Raw'] - skill_df['WH_Eff_Raw']), 0.0)
            def assign_skill_flag(row):
                lsi_cnt, wh_cnt = row['Simple_Installs_Count'], row['Water_Heaters_Count']
                if lsi_cnt > 0 and wh_cnt > 0: 
                    if row['Eff Gap'] > 15.0: return "⚠️ WH Ride-Along Required" if row['LSI_Eff_Raw'] > row['WH_Eff_Raw'] else "⚠️ LSI Ride-Along Required"
                    return "✅ Balanced Execution"
                if lsi_cnt > 0: return "ℹ️ Only LSI Jobs Assigned"
                if wh_cnt > 0: return "ℹ️ Only WH Jobs Assigned"
                return "ℹ️ No BU Jobs Assigned"
            skill_df['Action Required'] = skill_df.apply(assign_skill_flag, axis=1)
            
            skill_df['sort_action'] = skill_df['Action Required'].apply(lambda x: 0 if '⚠️' in str(x) else (1 if 'ℹ️' in str(x) else 2))
            skill_df = skill_df.sort_values(by='sort_action', ascending=True)
            
            show_skill = skill_df[['Name', 'Simple Installs Eff', 'Water Heaters Eff', 'Action Required']].rename(columns={'Simple Installs Eff': 'LSI Efficiency', 'Water Heaters Eff': 'WH Efficiency'})
            def style_flags(row): return ['background-color: #fff3cd; color: #856404; font-weight: bold;'] * len(row) if '⚠️' in row['Action Required'] else [''] * len(row)
            try: st.dataframe(show_skill.reset_index(drop=True).style.apply(style_flags, axis=1), use_container_width=True)
            except Exception: st.dataframe(show_skill.reset_index(drop=True), use_container_width=True)
            create_copy_button(show_skill.reset_index(drop=True), f"skills_{tab_key}")

    st.markdown("<br><h4>🗺️ Route Optimization Flags</h4>", unsafe_allow_html=True)
    st.markdown("*(Identifies service days where a technician spent over 40% of their billable shift driving to audit route density)*")
    poor_routes = daily_route[daily_route['Drive %'] > 40.0].copy()
    if not poor_routes.empty:
        poor_routes = poor_routes.sort_values(by='Drive %', ascending=False)
        poor_routes['Drive %'] = poor_routes['Drive %'].apply(lambda x: f"{x:.1f}%")
        poor_routes['Drive Time'] = poor_routes['Drive_Time_Hrs'].apply(format_hm)
        poor_routes['Work Time'] = poor_routes['In_Progress_Time_Hrs'].apply(format_hm)
        route_df_export = poor_routes[['Assigned Team Members', 'Short_Date', 'Job_Count', 'Drive Time', 'Work Time', 'Drive %']].rename(columns={'Assigned Team Members': 'Name', 'Short_Date': 'Date', 'Job_Count': 'Jobs'}).reset_index(drop=True)
        st.dataframe(route_df_export, use_container_width=True)
        create_copy_button(route_df_export, f"routes_{tab_key}")
    else: st.success("✅ Great density alignment! No single transport lane routing fell below benchmark efficiency requirements.")

    st.markdown("<br>", unsafe_allow_html=True)
    launch_col, launch_empty_col = st.columns(2)
    with launch_col:
        st.markdown("<h4>📊 Late Deployment Scorecard</h4>", unsafe_allow_html=True)
        st.markdown("*(Aggregates the total number of delayed morning launches per technician across the week)*")
        if not delayed_launches_df.empty:
            launch_counts = delayed_launches_df.groupby('Assigned Team Members').size().reset_index(name='Total Late Days').sort_values(by='Total Late Days', ascending=False)
            try: st.dataframe(launch_counts.reset_index(drop=True).style.set_properties(**{'background-color': '#fff3cd', 'color': '#856404;'}, subset=['Total Late Days']), use_container_width=True)
            except Exception: st.dataframe(launch_counts.reset_index(drop=True), use_container_width=True)
            create_copy_button(launch_counts.reset_index(drop=True).rename(columns={'Assigned Team Members': 'Name'}), f"late_score_{tab_key}")
        else: st.success("✅ Zero morning momentum delays recorded for core internal dispatches.")

    with launch_empty_col:
        st.markdown("<h4>🚗 Delayed Launch Alert</h4>", unsafe_allow_html=True)
        st.markdown("*(Provides a day-by-day chronological log of start-of-day timeline compliance delays)*")
        if not delayed_launches_df.empty:
            tech_late_list = sorted(delayed_launches_df['Assigned Team Members'].unique())
            most_late_tech = delayed_launches_df['Assigned Team Members'].value_counts().idxmax()
            default_late_idx = tech_late_list.index(most_late_tech) if most_late_tech in tech_late_list else 0
            
            selected_late_tech = st.selectbox("Select Tech to view launch times:", tech_late_list, index=default_late_idx, key=f"late_launch_{tab_key}")
            if selected_late_tech:
                tech_launches_df = delayed_launches_df[delayed_launches_df['Assigned Team Members'] == selected_late_tech].copy()
                tech_launches_df['First Punch log'] = tech_launches_df['First_Punch'].dt.strftime('%I:%M %p') + " (" + tech_launches_df['First_Status'] + ")"
                show_launches = tech_launches_df.sort_values(by='First_Punch', ascending=False)[['Short_Date', 'First Punch log']].rename(columns={'Short_Date': 'Date'}).reset_index(drop=True)
                try: st.dataframe(show_launches.style.set_properties(**{'background-color': '#ffcccc', 'color': '#990000;'}), use_container_width=True)
                except Exception: st.dataframe(show_launches, use_container_width=True)
                create_copy_button(show_launches, f"late_alert_{tab_key}")
        else: st.info("No timeline momentum compliance delays located inside current operational data streams.")

# --- THE MAIN TOP-LEVEL BASE EXECELINE PIPELINE LAYER BLOCK ---
st.sidebar.header("📂 Data Loading Pipeline")
time_file = st.sidebar.file_uploader("Upload Time Sheet (CSV)", type=['csv'])
ops_file = st.sidebar.file_uploader("Upload Lowes Ops Export (CSV)", type=['csv'])

if time_file and ops_file:
    try:
        CORE_TECHS = ['Bryan Pickett', 'Edward Lopez', 'Erik Tange', 'Matt Schlosser', 'Michael Owens', 'Nathan Smith', 'Sean Marble', 'Tanner LaForge']
        display_dfs = {} 
        
        # --- 1. Raw Read of
