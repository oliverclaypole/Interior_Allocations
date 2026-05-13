import streamlit as st
import pandas as pd
import sqlite3
import datetime
import calendar
import xgboost as xgb
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestRegressor
from sklearn.cluster import KMeans 

# ==============================================================================
# 0. THE MASTER HEADER ENGINE (Runs on every page)
# ==============================================================================
def display_page_header(title, caption=""):
    now = datetime.datetime.now()
    date_str = now.strftime("%A, %d %B %Y")
    time_str = now.strftime("%H:%M")
    
    st.markdown(f"""
        <div style='display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 10px;'>
            <h1 style='margin: 0; padding-bottom: 0;'>{title}</h1>
            <h4 style='margin: 0; color: #a8b2c1; padding-bottom: 5px;'>{date_str} | ⏰ {time_str}</h4>
        </div>
        <p style='color: #8e9aaf; margin-top: 0px;'>{caption}</p>
        <hr style='margin-top: 10px; margin-bottom: 25px; border: none; border-top: 1px solid rgba(255,255,255,0.1);' />
    """, unsafe_allow_html=True)


# ==============================================================================
# 1. PAGE CONFIG & CUSTOM CSS
# ==============================================================================
st.set_page_config(
    page_title="Interior Allocations", 
    page_icon="🏗️", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

hide_st_style = """
            <style>
            footer {visibility: hidden;}    
            
            html, body, [class*="css"] {
                font-family: "MS PGothic", sans-serif !important;
                color: #ffffff !important; /* Pure white text */
            }
            
            /* Main Background and Sidebar */
            [data-testid="stAppViewContainer"] {
                background-color: #081c34 !important; /* Deep Dark Blue */
            }
            [data-testid="stSidebar"] {
                border-right: 1px solid rgba(255,255,255,0.1);
                background-color: #152a45 !important; /* Slightly lighter Grey-Blue */
            }
            
            .block-container {
                padding-top: 1.5rem !important;
                padding-bottom: 1rem !important;
            }

            /* The standard container boxes */
            [data-testid="stVerticalBlockBorderWrapper"] {
                background-color: #152a45 !important; /* Slightly lighter Grey-Blue */
                border-radius: 12px !important;
                border: 1px solid #8e9aaf !important; 
                padding: 5px !important;
            }

            /* --- THE CALENDAR RULES --- */
            .white-cal [data-testid="stVerticalBlockBorderWrapper"] {
                background-color: #152a45 !important;
                border: 2px solid #8e9aaf !important;
            }
            .white-cal button {
                background-color: #081c34 !important;
                border: 1px solid #8e9aaf !important;
                color: #ffffff !important;
            }
            /* Make the Calendar Dates stand out */
            .white-cal button p {
                font-size: 18px !important;
                font-weight: 800 !important;
                color: #8e9aaf !important; 
            }
            .white-cal button:hover {
                background-color: #152a45 !important;
                border-color: #ffffff !important;
            }
            
            /* Glowing Expander Box */
            .glow-blue {
                border: 1px solid #8e9aaf !important;
                box-shadow: 0px 0px 12px rgba(142, 154, 175, 0.4) !important;
                border-radius: 8px;
                background-color: #152a45 !important;
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# ==============================================================================
# 2. DATABASE INIT
# ==============================================================================

def init_db():
    conn = sqlite3.connect('interior_revolutions.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS project_quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT,
                    item_type TEXT,
                    item_name TEXT,
                    quantity REAL,
                    total_cost REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS staff (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    password TEXT,
                    role TEXT,
                    day_rate REAL,
                    contracted_hours REAL,
                    employment_type TEXT,
                    cis_rate REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS shifts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_id INTEGER,
                    project TEXT,
                    hours REAL,
                    date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    budget REAL,
                    status TEXT DEFAULT 'Live',
                    start_date TEXT,
                    end_date TEXT)''')
                    
    # --- The Superior Loop Function ---
    cols = ["payment_status", "original_quote", "ai_suggested_quote", "final_accepted_quote", "tier", "amount_received"]
    for col in cols:
        try: c.execute(f"ALTER TABLE projects ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError: pass

    c.execute("SELECT COUNT(*) FROM staff WHERE role='Manager'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO staff (name, password, role, day_rate, contracted_hours, employment_type, cis_rate) VALUES (?,?,?,?,?,?,?)",
                  ('admin', 'boss123', 'Manager', 0, 0, 'CIS', 0))

    # Give Mario and Peter 37.5 hours and PAYE status.
    c.execute("UPDATE staff SET employment_type = 'PAYE', contracted_hours = 37.5, cis_rate = 0 WHERE name LIKE '%Mario%' OR name LIKE '%Peter%'")
    # Ensure everyone else is strictly CIS hourly.
    c.execute("UPDATE staff SET employment_type = 'CIS', contracted_hours = 0 WHERE name NOT LIKE '%Mario%' AND name NOT LIKE '%Peter%' AND role != 'Manager'")

    conn.commit()
    conn.close()

init_db()

# ==============================================================================
# 3. GLOBAL LOGIN GATE
# ==============================================================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.user_name = None
    st.session_state.worker_id = None

conn = sqlite3.connect('interior_revolutions.db')

# If they aren't logged in, show the login screen and STOP the app
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🔐 Interior Revolutions Login</h1>", unsafe_allow_html=True)
        
    # Center the login box nicely
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            with st.form("login_form"):
                username = st.text_input("Username")
                # FIXED: Changed test_input to text_input and added the password type mask
                password = st.text_input("Password", type="password")
                    
                if st.form_submit_button("Login", type="primary", use_container_width=True):
                    c = conn.cursor()
                    c.execute("SELECT id, role, password FROM staff WHERE name=?", (username,))
                    user = c.fetchone()
                        
                    if user and user[2] == password:
                        st.session_state.logged_in = True
                        st.session_state.role = user[1]
                        st.session_state.user_name = username
                        st.session_state.worker_id = user[0]
                        st.rerun()
                    else:
                        st.error("❌ Incorrect Password or Username.")
    conn.close()
    st.stop()
# ==============================================================================
# 4. DYNAMIC SIDEBAR NAVIGATION
# ==============================================================================
st.sidebar.markdown(f"### 👷 Welcome, {st.session_state.user_name.split(' ')[0]}")

# The Manager sees everything. The Worker only sees their portal.
if st.session_state.role == "Manager":
    menu_options = [
        "Manager Dashboard", 
        "Projects & Finances", 
        "Workforce & Payroll", 
        "Project Archive", 
        "ROI & Analytics", 
        "HR & Admin",
        "Experiment"
    ]
    st.sidebar.success("✅ Manager Access Granted")
else:
    menu_options = ["My Portal"]
    st.sidebar.info("👷 Worker Access Granted")

st.sidebar.markdown("### 🧭 Main Menu")

if 'active_page' not in st.session_state:
    st.session_state.active_page = menu_options[0]

# Failsafe: If a worker logs in but their session state is still trying to load the Manager Dashboard
if st.session_state.active_page not in menu_options:
    st.session_state.active_page = menu_options[0]

def switch_page(page_name):
    st.session_state.active_page = page_name

for page in menu_options:
    if st.session_state.active_page == page:
        st.sidebar.button(f"📍 {page}", on_click=switch_page, args=(page,), type="primary", use_container_width=True)
    else:
        st.sidebar.button(page, on_click=switch_page, args=(page,), type="secondary", use_container_width=True)

choice = st.session_state.active_page

st.sidebar.divider()
if st.sidebar.button("Log Out", type="primary", use_container_width=True):
    st.session_state.logged_in = False
    st.rerun()


# ==============================================================================
# 5. PAGE LOGIC
# ==============================================================================

if choice == "Manager Dashboard":
    conn = sqlite3.connect('interior_revolutions.db')
    display_page_header("📊 Morning Briefing", "Your daily command center for active projects, labor density, and budget health.")
    
    now = datetime.datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    current_month = now.strftime('%m')
    current_year = now.strftime('%Y')
    
    # Metrics
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM projects WHERE status = 'Live'")
    active_projects = c.fetchone()[0]
    
    # Ensure we only count workers who are currently deployed on 'Live' sites
    c.execute("""
        SELECT COUNT(DISTINCT s.worker_id) 
        FROM shifts s 
        JOIN projects p ON s.project = p.name 
        WHERE s.date = ? AND p.status = 'Live'
    """, (today_str,))
    workers_today = c.fetchone()[0]
    
    # 1. Calculate CIS (Hourly) Costs
    query_payroll_cis = """
    SELECT SUM(s.hours * (st.day_rate / 8)) AS Gross_Pay, SUM((s.hours * (st.day_rate / 8)) * (st.cis_rate / 100)) AS CIS_Tax
    FROM shifts s JOIN staff st ON s.worker_id = st.id
    WHERE strftime('%m', s.date) = ? AND strftime('%Y', s.date) = ? AND st.employment_type = 'CIS'
    """
    c.execute(query_payroll_cis, (current_month, current_year))
    cis_data = c.fetchone()
    monthly_gross_cis = cis_data[0] if cis_data[0] else 0
    monthly_cis = cis_data[1] if cis_data[1] else 0
    
    # 2. Calculate PAYE (Salaried) Costs (Assuming 4.33 weeks in a month)
    c.execute("SELECT SUM((day_rate / 8) * contracted_hours * 4.33) FROM staff WHERE employment_type = 'PAYE'")
    paye_data = c.fetchone()
    monthly_gross_paye = paye_data[0] if paye_data[0] else 0
    
    monthly_net = (monthly_gross_cis - monthly_cis) + monthly_gross_paye
    
    col1, col2, col3, col4 = st.columns(4)
    with col1.container(border=True):
        st.metric("🏗️ Live Projects", active_projects)
    with col2.container(border=True):
        st.metric("👷 Workers on Site Today", workers_today)
    with col3:
        st.markdown(f"""
        <div style="background-color: #1E293B; padding: 15px; border-radius: 8px; border: 1px solid #334155;">
            <p style="margin:0px; font-size: 14px; color: #94A3B8;">💰 Net Payroll (This Month)</p>
            <h2 style="margin:0px; font-weight: 600; color: #F8FAFC;">£{monthly_net:,.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div style="background-color: #1E293B; padding: 15px; border-radius: 8px; border: 1px solid #334155;">
            <p style="margin:0px; font-size: 14px; color: #94A3B8;">🏛️ CIS Liability (This Month)</p>
            <h2 style="margin:0px; font-weight: 600; color: #F8FAFC;">£{monthly_cis:,.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Budget Alerts
    st.subheader("🚨 Budget Alerts")
    df_projects = pd.read_sql_query("SELECT name FROM projects WHERE status = 'Live'", conn)
    alerts_found = False
    
    for _, row in df_projects.iterrows():
        p_name = row['name']
        c.execute("SELECT SUM(total_cost) FROM project_quotes WHERE project_name = ? AND item_type = 'Labor'", (p_name,))
        qb_labor = c.fetchone()[0]
        qb_labor = qb_labor if qb_labor else 0
        
        c.execute("SELECT SUM(s.hours * (st.day_rate / 8)) FROM shifts s JOIN staff st ON s.worker_id = st.id WHERE s.project = ?", (p_name,))
        actual_labor = c.fetchone()[0]
        actual_labor = actual_labor if actual_labor else 0
        
        if qb_labor > 0:
            usage_pct = (actual_labor / qb_labor) * 100
            if usage_pct >= 85:
                alerts_found = True
                if usage_pct >= 100:
                    st.error(f"⚠️ **{p_name}** is OVER LABOUR BUDGET! (£{actual_labor:,.2f} spent vs £{qb_labor:,.2f} estimate)")
                else:
                    st.warning(f"⚠️ **{p_name}** is nearing labour budget limit! ({usage_pct:.1f}% used)")
    
    if not alerts_found:
        st.success("✅ All live projects are currently running safely within their estimated labour budgets.")
        
    st.divider()
    
    # 7-Day Gantt Chart
    st.subheader("📅 Live Workforce Timeline")
    
    if 'gantt_offset' not in st.session_state:
        st.session_state.gantt_offset = 0

    col_nav1, col_nav2, col_nav3 = st.columns([1, 3, 1])
    with col_nav1:
        if st.button("◀️ Previous 7 Days", use_container_width=True):
            st.session_state.gantt_offset -= 7
            st.rerun()
    with col_nav3:
        if st.button("Next 7 Days ▶️", use_container_width=True):
            st.session_state.gantt_offset += 7
            st.rerun()
    
    start_window = pd.to_datetime(datetime.date.today()) + pd.to_timedelta(st.session_state.gantt_offset, unit='D')
    end_window = start_window + pd.to_timedelta(7, unit='D')
    
    # Ensure we pull BOTH Live and Completed projects for historical tracking
    query_timeline = """
    SELECT s.project AS Project, p.status AS Status, s.date AS Shift_Date, COUNT(s.id) AS Workers_On_Site, GROUP_CONCAT(st.name, ', ') AS Workers
    FROM shifts s JOIN projects p ON s.project = p.name JOIN staff st ON s.worker_id = st.id
    WHERE p.status IN ('Live', 'Completed', 'Archived') GROUP BY s.project, s.date
    """
    df_timeline = pd.read_sql_query(query_timeline, conn)
    
    if not df_timeline.empty:
        import plotly.express as px
        df_timeline['Start'] = pd.to_datetime(df_timeline['Shift_Date'])
        df_timeline['End'] = df_timeline['Start'] + pd.to_timedelta(1, unit='D') 
        
        mask = (df_timeline['Start'] >= start_window) & (df_timeline['Start'] <= end_window)
        df_filtered = df_timeline.loc[mask].copy()
        
        if not df_filtered.empty:
            df_filtered = df_filtered.sort_values(by=['Project', 'Start'])
            all_projects_in_view = df_filtered['Project'].unique().tolist()
            
            # --- CUSTOM DUAL-GRADIENT LOGIC ---
            max_workers = df_filtered['Workers_On_Site'].max()
            if max_workers == 0: max_workers = 1
            
            custom_colors = []
            for _, row in df_filtered.iterrows():
                # Calculates opacity from 30% (light) to 100% (dark) based on worker density
                intensity = 0.3 + (0.7 * (row['Workers_On_Site'] / max_workers))
                
                if row['Status'] == 'Live':
                    custom_colors.append(f"rgba(46, 204, 113, {intensity})") # Green Hue
                else:
                    custom_colors.append(f"rgba(56, 189, 248, {intensity})") # Sky Blue for Completed

            fig = px.timeline(df_filtered, x_start="Start", x_end="End", y="Project",
                              hover_data={"Workers": True, "Workers_On_Site": True, "Status": True, "Start": False, "End": False})
            
            # Force Plotly to apply our custom calculated colors
            fig.update_traces(marker_color=custom_colors)
            
            fig.update_yaxes(autorange="reversed", categoryorder='array', categoryarray=all_projects_in_view, tickfont=dict(size=14, weight="bold", color="#F8FAFC")) 
            fig.update_xaxes(range=[start_window, end_window], dtick="86400000", tickformat="%A<br>%d %b", tickfont=dict(size=13, weight="bold", color="#F8FAFC"), showgrid=True) 
            fig.update_layout(height=max(300, len(all_projects_in_view) * 80), margin=dict(t=20, b=20, l=0, r=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            
            with st.container(border=True):
                # Custom UI Legend
                st.markdown("<div style='text-align: right; margin-bottom: 5px;'><small>🟢 <b>Live</b> (Darker = More Workers) &nbsp;|&nbsp; 🔵 <b>Completed</b> (Darker = More Workers)</small></div>", unsafe_allow_html=True)
                st.plotly_chart(fig, use_container_width=True)
        else:
            with st.container(border=True):
                st.info(f"No shifts scheduled between {start_window.strftime('%d %b')} and {end_window.strftime('%d %b')}.")
    else:
        st.info("No timeline data available.")
        
    # Deep Dive Roster
    st.write("")
    st.subheader("🔍 Daily Roster")
    st.caption("Select any day from your timeline to see exactly who is on site and for how long.")
    
    date_list = [(start_window + pd.to_timedelta(i, unit='D')).strftime('%Y-%m-%d') for i in range(8)]
    selected_roster_date = st.selectbox("Select Date", date_list, format_func=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').strftime('%A, %d %B %Y'))
    
    if selected_roster_date:
        df_roster = pd.read_sql_query("""
            SELECT p.name AS Project, st.name AS Worker, st.role AS Role, s.hours AS Hours
            FROM shifts s JOIN projects p ON s.project = p.name JOIN staff st ON s.worker_id = st.id
            WHERE p.status = 'Live' AND s.date = ? ORDER BY p.name, st.name
        """, conn, params=[selected_roster_date])
        
        if not df_roster.empty:
            st.dataframe(df_roster.style.format({"Hours": "{:.1f}h"}), use_container_width=True, hide_index=True)
        else:
            with st.container(border=True):
                st.info(f"☕ No shifts logged for {datetime.datetime.strptime(selected_roster_date, '%Y-%m-%d').strftime('%A, %d %B')}. The sites are empty.")
    conn.close()

elif choice == "Projects & Finances":
    conn = sqlite3.connect('interior_revolutions.db')
    display_page_header("🏗️ Projects & Finances", "Manage the entire lifecycle of your active jobs and track live budgets.")
    
    col_proj_1, col_proj_2 = st.columns(2)
    
    with col_proj_1:
        # --- 1. CREATE NEW PROJECT ---
        with st.expander("➕ Create New Project", expanded=False):
            with st.form("new_project_form", clear_on_submit=True):
                new_p_name = st.text_input("Project Name")
                start_d = st.date_input("Actual Start Date")
                if st.form_submit_button("Launch Project", type="primary"):
                    if new_p_name:
                        c = conn.cursor()
                        try:
                            c.execute("INSERT INTO projects (name, budget, status, start_date, end_date) VALUES (?, ?, 'Live', ?, NULL)", (new_p_name.title(), 0.0, str(start_d)))
                            conn.commit()
                            import time
                            st.success(f"✅ {new_p_name.title()} is now Live!")
                            time.sleep(1.5)
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("❌ Project name exists!")

        # --- 2. DELETE PROJECT ---
        st.write("") 
        with st.expander("🗑️ Delete a Project", expanded=False):
            df_del = pd.read_sql_query("SELECT name FROM projects", conn)
            
            if not df_del.empty:
                with st.form("delete_project_form"):
                    p_to_delete = st.selectbox("Select Project to Permanently Remove", df_del['name'].tolist())
                    st.warning(f"⚠️ **Caution:** Deleting '{p_to_delete}' removes all shifts and history.")
                    confirm_del = st.checkbox("I confirm I want to destroy this project data.")
                    
                    if st.form_submit_button("Permanently Delete Project", type="secondary"):
                        if not confirm_del:
                            st.error("Please check the confirmation box first.")
                        else:
                            c = conn.cursor()
                            c.execute("DELETE FROM shifts WHERE project = ?", (p_to_delete,))
                            c.execute("DELETE FROM projects WHERE name = ?", (p_to_delete,))
                            conn.commit()
                            
                            st.success(f"💥 {p_to_delete} has been deleted.")
                            import time
                            time.sleep(1.5)
                            st.rerun()
            else:
                st.info("No projects found in database.")

    with col_proj_2:
        with st.expander("✏️ Edit Start Date", expanded=False):
            df_all_projs = pd.read_sql_query("SELECT id, name, start_date FROM projects WHERE status = 'Live'", conn)
            if not df_all_projs.empty:
                with st.form("edit_start_date_form"):
                    p_to_edit = st.selectbox("Select Live Project", df_all_projs['name'].tolist())
                    new_start_date = st.date_input("New Start Date")
                    if st.form_submit_button("Update Date"):
                        c = conn.cursor()
                        c.execute("UPDATE projects SET start_date = ? WHERE name = ?", (str(new_start_date), p_to_edit))
                        conn.commit()
                        import time
                        st.success(f"✅ {p_to_edit} start date updated to {new_start_date}!")
                        time.sleep(1.5)
                        st.rerun()
            else:
                st.info("No live projects to edit.")

        with st.expander("🏁 Complete a Job", expanded=False):
            if not df_all_projs.empty:
                with st.form("update_status_form"):
                    p_to_complete = st.selectbox("Select Live Project to Complete", df_all_projs['name'].tolist())
                    actual_end_date = st.date_input("What was the actual final day on site?")
                    amount_paid = st.number_input("Total Cash Received from Client (£)", min_value=0.0, value=0.0, step=100.0)
                    
                    if st.form_submit_button("Mark as Completed & Archive"):
                        c = conn.cursor()
                        c.execute("UPDATE projects SET status = 'Completed', end_date = ?, amount_received = ? WHERE name = ?", (str(actual_end_date), amount_paid, p_to_complete))
                        conn.commit()
                        import time
                        st.success(f"✅ {p_to_complete} successfully archived with £{amount_paid:,.2f} received!")
                        time.sleep(1.5)
                        st.rerun()
            else:
                st.info("No live projects to update.")

    st.subheader("🧠 Advanced Quote Optimizer (XGBoost + RandomForest + KMeans Ensemble)")

    # Force connection open for the AI engine
    conn = sqlite3.connect('interior_revolutions.db')
    df_live_project = pd.read_sql_query("SELECT name FROM projects WHERE status = 'Live'", conn)

    if not df_live_project.empty:
        # ====================== USER INPUT ======================
        st.markdown("**📍 Location Context**")
        quote_location = st.text_input(
            "Area / Postcode (strongly affects pricing)", 
            placeholder="Marylebone, NW1, Chelsea, Hackney",
            help="This significantly impacts the final recommendation"
        ).strip().lower()
        
        uploaded_file = st.file_uploader("Upload QuickBooks Estimate (.csv)", type=["csv"])
        
        if uploaded_file is not None:
            df_quote = pd.read_csv(uploaded_file)
            
            # 1. Standardize all headers first
            df_quote.columns = [c.strip().lower().replace(" ", "_") for c in df_quote.columns]
            
            # 2. Safety net for 'total_cost'
            if 'total_cost' not in df_quote.columns:
                cost_fallbacks = {'amount': 'total_cost', 'total': 'total_cost', 'cost': 'total_cost'}
                for old, new in cost_fallbacks.items():
                    if old in df_quote.columns:
                        df_quote = df_quote.rename(columns={old: new})
                        break
            
            # 3. Safety net for 'item_type'
            if 'item_type' not in df_quote.columns:
                type_fallbacks = {'type': 'item_type', 'category': 'item_type'}
                for old, new in type_fallbacks.items():
                    if old in df_quote.columns:
                        df_quote = df_quote.rename(columns={old: new})
                        break

            # 4. Safety net for 'item_name' (The one you are adding now!)
            if 'item_name' not in df_quote.columns:
                name_fallbacks = {'name': 'item_name', 'description': 'item_name', 'item': 'item_name'}
                for old, new in name_fallbacks.items():
                    if old in df_quote.columns:
                        df_quote = df_quote.rename(columns={old: new})
                        break

            # --- CRITICAL: Now the math can safely run because we found the columns ---
            df_quote['total_cost'] = pd.to_numeric(df_quote['total_cost'], errors='coerce').fillna(0)
            item_text = " ".join(df_quote['item_name'].astype(str)).lower()
            
            base_mats = df_quote[df_quote['item_type'].isin(['Material', 'Service'])]['total_cost'].sum()
            base_labor = df_quote[df_quote['item_type'].str.contains('Labour|Labor', case=False, na=False)]['total_cost'].sum()
            base_cost = base_mats + base_labor
            
            # Richer context for NLP
            item_text = " ".join(df_quote['item_name'].astype(str)).lower()
            full_context = f"{quote_location} premium luxury renovation {item_text}"
            
            # Tier classification
            if base_cost < 2500: tier = "Tier 1 (<£2.5k)"
            elif base_cost < 18000: tier = "Tier 2 (£2.5k-£18k)"
            else: tier = "Tier 3 (£18k+)"

            # ====================== MODEL TRAINING & PREDICTION ======================
            with st.spinner("Training 3-model ensemble..."):
                df_history = pd.read_sql_query("""
                    SELECT p.name, p.amount_received 
                    FROM projects p 
                    WHERE p.status IN ('Completed', 'Archived') AND p.amount_received > 1000
                """, conn)
                
                # --- ADD THIS FIX RIGHT HERE ---
                df_history['amount_received'] = pd.to_numeric(df_history['amount_received'], errors='coerce')
                # -------------------------------
                
                historical_texts, historical_costs, historical_targets = [], [], []
                
                for _, row in df_history.iterrows():
                    p_name, target = row['name'], row['amount_received']
                    df_items = pd.read_sql_query("SELECT item_name, total_cost FROM project_quotes WHERE project_name = ?", conn, params=[p_name])
                    
                    if not df_items.empty:
                        text = f"{p_name.lower()} " + " ".join(df_items['item_name'].astype(str)).lower()
                        historical_texts.append(text)
                        historical_costs.append(df_items['total_cost'].sum())
                        historical_targets.append(target)
                
                if len(historical_texts) >= 6:
                    vectorizer = TfidfVectorizer(max_features=40, ngram_range=(1, 2), stop_words='english', min_df=1)
                    X_text = vectorizer.fit_transform(historical_texts).toarray()
                    X_cost = np.array(historical_costs).reshape(-1, 1)
                    X_train = np.hstack((X_cost, X_text))
                    y_train = np.array(historical_targets, dtype=float)
                    
                    # Model 1: XGBoost
                    xgb_model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.07, subsample=0.85, random_state=42)
                    xgb_model.fit(X_train, y_train)
                    
                    # Model 2: RandomForest
                    rf_model = RandomForestRegressor(n_estimators=120, max_depth=6, min_samples_split=3, random_state=42, n_jobs=-1)
                    rf_model.fit(X_train, y_train)
                    
                    # Model 3: KMeans
                    n_clusters = 5
                    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                    cluster_labels = kmeans.fit_predict(X_train)
                    
                    # Predict new quote
                    new_text_vec = vectorizer.transform([full_context]).toarray()
                    X_new = np.hstack((np.array([[base_cost]]), new_text_vec))
                    
                    xgb_pred = float(xgb_model.predict(X_new)[0])
                    rf_pred = float(rf_model.predict(X_new)[0])
                    new_cluster = int(kmeans.predict(X_new)[0])
                    
                    peer_ratios = [historical_targets[i] / historical_costs[i] for i, c in enumerate(cluster_labels) if c == new_cluster and historical_costs[i] > 0]
                    peer_multiplier = np.median(peer_ratios) if peer_ratios else 1.28
                    cluster_price = base_cost * peer_multiplier
                    
                    # ENSEMBLE BLEND
                    blended_price = (xgb_pred * 0.40) + (rf_pred * 0.40) + (cluster_price * 0.20)
                else:
                    blended_price = base_cost * 1.30
                    st.warning("⚠️ Limited historical data — using safe conservative markup")
                    peer_multiplier = 1.30
                    xgb_pred = rf_pred = blended_price

                # Safety bounds
                safety_floor = base_cost * 1.20
                safety_ceiling = base_cost * 1.70
                ai_suggested_price = max(safety_floor, min(safety_ceiling, blended_price))
                
                # Location premium
                luxury_keywords = ['marylebone','chelsea','kensington','mayfair','knightsbridge','belgravia','nw1','sw1','sw3','sw7','w1','w8']
                location_boost = 0
                if any(kw in quote_location for kw in luxury_keywords):
                    location_boost = ai_suggested_price * 0.09
                    ai_suggested_price += location_boost

            # ====================== DISPLAY RESULTS ======================
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**Base Cost:** £{base_cost:,.2f}\n**Tier:** {tier}")
                if 'peer_multiplier' in locals():
                    st.success(f"**Similar Jobs Multiplier:** {peer_multiplier:.2f}x")
            with col2:
                st.success(f"**AI Recommended Selling Price:** £{ai_suggested_price:,.2f}")
                if location_boost > 0:
                    st.caption(f"↑ £{location_boost:,.0f} premium from location")

            # ====================== SAVE FORM ======================
            with st.form("save_quote_form"):
                project_name = st.selectbox("Assign to which project?", df_live_project['name'].tolist())
                choice = st.radio("Pricing Strategy", ["Use AI Ensemble Price", "Standard 20% Markup", "Custom Price"])
                custom_price = st.number_input("Custom Price (£)", value=float(ai_suggested_price), step=500.0)
                
                if st.form_submit_button("💾 Lock Quote & Update Database", type="primary"):
                    final_price = {
                        "Use AI Ensemble Price": ai_suggested_price,
                        "Standard 20% Markup": base_cost * 1.20,
                        "Custom Price": custom_price
                    }[choice]

                    c = conn.cursor()
                    c.execute("""UPDATE projects SET budget=?, original_quote=?, ai_suggested_quote=?, final_accepted_quote=?, tier=? WHERE name=?""", 
                              (final_price, base_cost*1.15, ai_suggested_price, final_price, tier, project_name))
                    
                    c.execute("DELETE FROM project_quotes WHERE project_name=?", (project_name,))
                    for _, row in df_quote.iterrows():
                        c.execute('''INSERT INTO project_quotes (project_name, item_type, item_name, quantity, total_cost) VALUES (?,?,?,?,?)''', 
                                  (project_name, row['item_type'], row['item_name'], row.get('quantity',1), row['total_cost']))
                    conn.commit()
                    st.success(f"✅ Quote locked for **{project_name}** at £{final_price:,.2f}")
                    st.rerun()
    st.divider()

    # --- RESTORED LIVE FINANCIAL BREAKDOWN ---
    st.subheader("📉 Live Financial Breakdown")
    df_live_project_details = pd.read_sql_query("SELECT name, start_date FROM projects WHERE status = 'Live'", conn)
    
    if not df_live_project_details.empty:
        for index, row in df_live_project_details.iterrows():
            p_name = row['name']
            start_d_str = row['start_date']
            days_live = 0
            if pd.notna(start_d_str) and start_d_str:
                try:
                    s_date = datetime.datetime.strptime(start_d_str, "%Y-%m-%d").date()
                    days_live = max(0, (datetime.date.today() - s_date).days)
                except: pass
            
            df_qb = pd.read_sql_query("SELECT item_type, item_name, quantity, total_cost FROM project_quotes WHERE project_name = ?", conn, params=[p_name])
            if not df_qb.empty:
                df_qb['total_cost'] = pd.to_numeric(df_qb['total_cost'], errors='coerce').fillna(0)
                qb_materials_cost = df_qb[df_qb['item_type'].isin(['Material', 'Service'])]['total_cost'].sum()
                qb_labor_cost = df_qb[df_qb['item_type'] == 'Labor']['total_cost'].sum()
                total_budget = qb_materials_cost + qb_labor_cost
            else:
                qb_materials_cost = qb_labor_cost = total_budget = 0
            
            query_actual = """SELECT st.role AS Role, SUM(s.hours) AS Actual_Hours, SUM(s.hours * (st.day_rate / 8)) AS Gross_Pay
                              FROM shifts s JOIN staff st ON s.worker_id = st.id WHERE s.project = ? GROUP BY st.role"""
            df_actual = pd.read_sql_query(query_actual, conn, params=[p_name])
            actual_labor_cost = df_actual['Gross_Pay'].sum() if not df_actual.empty else 0
            
            with st.expander(f"📊 {p_name.upper()} - Total Budget: £{total_budget:,.2f}", expanded=False):
                if total_budget == 0: st.warning("⚠️ No QuickBooks quote attached. Showing active labor only.")
                    
                st.caption("🎯 **THE QUOTE (From QuickBooks)**")
                m1, m2, m3 = st.columns(3)
                with m1.container(border=True): st.metric("Total Quote Budget", f"£{total_budget:,.2f}")
                with m2.container(border=True): st.metric("Quoted Materials Cost", f"£{qb_materials_cost:,.2f}")
                with m3.container(border=True): st.metric("Quoted Labour Cost", f"£{qb_labor_cost:,.2f}")
                
                st.write("")
                st.caption("⏱️ **LIVE REALITY CHECK**")
                m4, m5 = st.columns(2)
                with m4.container(border=True): st.metric("Days Project Live", f"{days_live} Days")
                with m5.container(border=True): st.metric("Amount Spent on Labour So Far", f"£{actual_labor_cost:,.2f}")
                
                st.divider()
                
                c_left, c_right = st.columns(2)
                with c_left:
                    st.caption("📦 **Material Details**")
                    if total_budget > 0:
                        st.dataframe(df_qb[df_qb['item_type'].isin(['Material', 'Service'])][['item_name', 'total_cost']].style.format({"total_cost": "£{:,.2f}"}), use_container_width=True, hide_index=True)
                    else: st.info("No materials data.")

                with c_right:
                    st.caption("👷 **Labour Burn Rate (Hours)**")
                    df_actual = pd.read_sql_query("SELECT st.role AS Role, SUM(s.hours) AS Actual_Hours FROM shifts s JOIN staff st ON s.worker_id = st.id WHERE s.project = ? GROUP BY st.role", conn, params=[p_name])
                    
                    df_lab_quoted = df_qb[df_qb['item_type'] == 'Labor'].copy()
                    if not df_lab_quoted.empty:
                        df_lab_quoted = df_lab_quoted[['item_name', 'quantity']].rename(columns={'item_name': 'Role'})
                        df_lab_quoted['Role'] = df_lab_quoted['Role'].str.replace(' Day Rate', '', case=False).str.strip().str.title()
                        df_lab_quoted['Role'] = df_lab_quoted['Role'].str.replace('Laborer', 'Labourer', case=False) 
                        df_lab_quoted = df_lab_quoted.groupby('Role', as_index=False).sum()
                        df_lab_quoted['Quoted_Hours'] = df_lab_quoted['quantity'].astype(float) * 8
                    else:
                        df_lab_quoted = pd.DataFrame(columns=['Role', 'Quoted_Hours'])
                        
                    if not df_actual.empty:
                        df_actual['Role'] = df_actual['Role'].str.replace(' Day Rate', '', case=False).str.strip().str.title()
                        df_actual['Role'] = df_actual['Role'].str.replace('Laborer', 'Labourer', case=False)
                        df_actual = df_actual.groupby('Role', as_index=False).sum()

                    if not df_actual.empty or not df_lab_quoted.empty:
                        df_labor_merge = pd.merge(df_actual, df_lab_quoted, on='Role', how='outer').fillna(0)
                        for _, l_row in df_labor_merge.iterrows():
                            role, act, quo = l_row['Role'], l_row['Actual_Hours'], l_row['Quoted_Hours']
                            pct = (act / quo * 100) if quo > 0 else (100 if act > 0 else 0)
                            bar_width = min(pct, 100)
                            bar_color = "#E74C3C" if act > quo else "#2ECC71" 
                            
                            st.markdown(f"**{role}**")
                            st.markdown(f"""
                                <div style="display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 2px;">
                                    <span style="color: {'#E74C3C' if act > quo else '#94A3B8'};"><b>{act:.1f}h</b> actual</span>
                                    <span style="color: #94A3B8;">{quo:.1f}h quoted</span>
                                </div>
                                <div style="width: 100%; background-color: rgba(255,255,255,0.1); border-radius: 5px; height: 10px; margin-bottom: 10px;">
                                    <div style="width: {bar_width}%; background-color: {bar_color}; height: 10px; border-radius: 5px;"></div>
                                </div>
                            """, unsafe_allow_html=True)
                            
                            if act > quo: st.error(f"⚠️ Over budget by {(act - quo):.1f} hours!")
                    else: st.info("No labour data available.")
    conn.close()

elif choice == "Workforce & Payroll":
    conn = sqlite3.connect('interior_revolutions.db')
    
    if st.session_state.role == "Manager":
        display_page_header("👷 Workforce Management", "Company payroll, team calendar, and shift logging.")
    else:
        display_page_header("👷 My Portal", "View your logged hours, estimated pay, and shift schedule.")
    
    if 'view_year' not in st.session_state:
        st.session_state.view_year = datetime.datetime.now().year
        st.session_state.view_month = datetime.datetime.now().month
        st.session_state.selected_date = None

    def prev_month():
        st.session_state.view_month -= 1
        st.session_state.selected_date = None
        if st.session_state.view_month < 1: 
            st.session_state.view_month, st.session_state.view_year = 12, st.session_state.view_year - 1

    def next_month():
        st.session_state.view_month += 1
        st.session_state.selected_date = None
        if st.session_state.view_month > 12: 
            st.session_state.view_month, st.session_state.view_year = 1, st.session_state.view_year + 1

    selected_month_str = f"{st.session_state.view_year}-{st.session_state.view_month:02d}"
    month_name = calendar.month_name[st.session_state.view_month]

    if st.session_state.role == "Manager":
        st.subheader(f"📅 Team Calendar: {month_name} {st.session_state.view_year}")
        
        # --- 1. THE CALENDAR ---
        st.markdown('<div class="white-cal">', unsafe_allow_html=True)
        with st.container(border=True):
            cal_c1, cal_c2, cal_c3 = st.columns([1, 2, 1])
            with cal_c1: st.button("◀️ Prev Month", on_click=prev_month, use_container_width=True)
            with cal_c2: st.markdown(f"<h3 style='text-align: center; margin-top:0px;'>{month_name} {st.session_state.view_year}</h3>", unsafe_allow_html=True)
            with cal_c3: st.button("Next Month ▶️", on_click=next_month, use_container_width=True)

            query_shifts = "SELECT s.id, s.date, t.name AS worker_name, s.project, s.hours FROM shifts s JOIN staff t ON s.worker_id = t.id"
            df_shifts = pd.read_sql_query(query_shifts, conn)

            cols = st.columns(7)
            for i, day in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]): 
                cols[i].markdown(f"<div style='text-align:center'><b>{day}</b></div>", unsafe_allow_html=True) 

            for week in calendar.monthcalendar(st.session_state.view_year, st.session_state.view_month):
                week_cols = st.columns(7)
                for i, day in enumerate(week):
                    if day != 0:
                        date_str = f"{st.session_state.view_year}-{st.session_state.view_month:02d}-{day:02d}"
                        shift_count = len(df_shifts[df_shifts['date'] == date_str])
                        
                        if shift_count == 1: btn_label = f"{day} \n🟢 1 worker"
                        elif shift_count > 1: btn_label = f"{day} \n🟢 {shift_count} workers"
                        else: btn_label = f"{day}"
                            
                        if week_cols[i].button(btn_label, key=f"btn_{date_str}", use_container_width=True):
                            st.session_state.selected_date = date_str

            if st.session_state.selected_date:
                st.divider()
                st.caption(f"📝 **Shift Details for {st.session_state.selected_date}**")
                selected_df = df_shifts[df_shifts['date'] == st.session_state.selected_date]
                if not selected_df.empty:
                    st.dataframe(selected_df[['worker_name', 'project', 'hours']], use_container_width=True, hide_index=True)
                    with st.form("delete_form"):
                        shift_opts = {f"{row['worker_name']} - {row['project']} ({row['hours']}h)": row['id'] for _, row in selected_df.iterrows()}
                        selected_del = st.selectbox("Select to delete:", list(shift_opts.keys()))
                        confirm = st.checkbox("⚠️ Confirm deletion")
                        if st.form_submit_button("Delete Shift") and confirm:
                            c = conn.cursor()
                            c.execute("DELETE FROM shifts WHERE id=?", (shift_opts[selected_del],))
                            conn.commit()
                            st.session_state.selected_date = None
                            st.rerun()
                else:
                    st.info("No shifts logged.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.divider()

        # --- 2. MANAGER OVERRIDE (GLOWING BLUE) ---
        st.markdown('<div class="glow-blue" style="padding: 5px; margin-bottom: 20px;">', unsafe_allow_html=True)
        with st.expander("✨ Manager Override: Manual Shift Entry", expanded=False):
            try:
                df_active_staff = pd.read_sql_query("SELECT id, name, role FROM staff WHERE role != 'Manager'", conn)
                df_live_projs = pd.read_sql_query("SELECT name FROM projects WHERE status = 'Live'", conn)
            except pd.errors.DatabaseError:
                df_active_staff = pd.DataFrame()
                df_live_projs = pd.DataFrame()

            if not df_active_staff.empty and not df_live_projs.empty:
                with st.form("manual_shift_form", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        worker_name = st.selectbox("Select Worker", df_active_staff['name'].tolist())
                        shift_date = st.date_input("Date of Shift")
                    with col2:
                        project = st.selectbox("Assign to Project", df_live_projs['name'].tolist())
                        hours = st.number_input("Hours Worked", min_value=0.5, max_value=14.0, value=8.0, step=0.5)

                    if st.form_submit_button("Log Shift Manually", type="primary"):
                        c = conn.cursor()
                        c.execute("SELECT id FROM staff WHERE name = ?", (worker_name,))
                        w_id_result = c.fetchone()
                        if w_id_result:
                            c.execute("INSERT INTO shifts (worker_id, project, hours, date) VALUES (?, ?, ?, ?)", (w_id_result[0], project, hours, str(shift_date)))
                            conn.commit()
                            st.success(f"✅ Shift logged for {worker_name}.")
                            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # --- 3. PAYROLL METRICS & TABLE ---
        st.subheader(f"💰 {month_name} Company Payroll Breakdown")
        
        query_cis = """
        SELECT st.name AS Worker, 'CIS' AS Type, SUM(s.hours) AS Total_Hours, SUM(s.hours * (st.day_rate / 8)) AS Gross_Pay, SUM((s.hours * (st.day_rate / 8)) * (st.cis_rate / 100)) AS CIS_Tax
        FROM shifts s JOIN staff st ON s.worker_id = st.id 
        WHERE strftime('%Y-%m', s.date) = ? AND st.employment_type = 'CIS' GROUP BY st.id
        """
        df_cis = pd.read_sql_query(query_cis, conn, params=[selected_month_str])
        
        # --- FIXED PAYE ENGINE ---
        query_paye = """SELECT name AS Worker, 'PAYE' AS Type, (contracted_hours * 4.33) AS Total_Hours, 
                        ((day_rate / 8) * contracted_hours * 4.33) AS Gross_Pay, 
                        (MAX(0, ((day_rate / 8) * contracted_hours * 4.33) - 1047.50) * 0.20) + 
                        (MAX(0, ((day_rate / 8) * contracted_hours * 4.33) - 1048.00) * 0.08) AS CIS_Tax 
                        FROM staff WHERE employment_type = 'PAYE'"""
        df_paye = pd.read_sql_query(query_paye, conn)
        
        df_monthly = pd.concat([df_cis, df_paye], ignore_index=True)
        
        total_gross = df_monthly['Gross_Pay'].sum() if not df_monthly.empty else 0
        total_cis = df_monthly['CIS_Tax'].sum() if not df_monthly.empty else 0
        total_net = total_gross - total_cis
        
        # Glowing Blue HTML Metric Cards (Dark Theme)
        st.markdown(f"""
        <div style="display: flex; gap: 15px; margin-bottom: 20px;">
            <div style="flex: 1; background: #1E293B; border: 2px solid #38BDF8; box-shadow: 0 0 15px rgba(56, 189, 248, 0.4); padding: 15px; border-radius: 10px;">
                <p style="margin:0; color:#94A3B8; font-weight:bold;">Total Worker Spend</p>
                <h2 style="margin:0; color:#38BDF8; text-shadow: 0 0 8px rgba(56, 189, 248, 0.3);">£{total_gross:,.2f}</h2>
            </div>
            <div style="flex: 1; background: #1E293B; border: 2px solid #38BDF8; box-shadow: 0 0 15px rgba(56, 189, 248, 0.4); padding: 15px; border-radius: 10px;">
                <p style="margin:0; color:#94A3B8; font-weight:bold;">Total Net Paid</p>
                <h2 style="margin:0; color:#38BDF8; text-shadow: 0 0 8px rgba(56, 189, 248, 0.3);">£{total_net:,.2f}</h2>
            </div>
            <div style="flex: 1; background: #1E293B; border: 2px solid #38BDF8; box-shadow: 0 0 15px rgba(56, 189, 248, 0.4); padding: 15px; border-radius: 10px;">
                <p style="margin:0; color:#94A3B8; font-weight:bold;">Total Taxes/CIS Withheld</p>
                <h2 style="margin:0; color:#38BDF8; text-shadow: 0 0 8px rgba(56, 189, 248, 0.3);">£{total_cis:,.2f}</h2>
            </div>
        </div>
        """, unsafe_allow_html=True)
            
        if not df_monthly.empty:
            df_export = df_monthly.copy()
            df_export['Gross_Pay'] = df_export['Gross_Pay'].apply(lambda x: f"£{x:.2f}")
            df_export['CIS_Tax'] = df_export['CIS_Tax'].apply(lambda x: f"£{x:.2f}")
            df_export['Net_Pay'] = (df_monthly['Gross_Pay'] - df_monthly['CIS_Tax']).apply(lambda x: f"£{x:.2f}")
            
            # Styled Pandas Table for Dark Theme
            styled_df = df_export[['Worker', 'Type', 'Total_Hours', 'Gross_Pay', 'CIS_Tax', 'Net_Pay']].style.set_properties(**{
                'background-color': '#1E293B',
                'color': '#F8FAFC',
                'border-color': '#334155',
                'font-size': '15px'
            })
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            csv = df_export.to_csv(index=False).encode('utf-8-sig')
            st.download_button(label=f"📥 Download {month_name} Payroll", data=csv, file_name=f"Payroll_{month_name}_{st.session_state.view_year}.csv", mime="text/csv", type="primary")
        else:
            st.info(f"No shifts logged in {month_name}.")
            
    else:
        # WORKER FALLBACK (My Portal view duplicated in correct section, handled safely here as fallback)
        st.subheader(f"💸 My Earnings: {month_name} {st.session_state.view_year}")
        c = conn.cursor()
        c.execute("SELECT employment_type, contracted_hours, day_rate FROM staff WHERE id = ?", (st.session_state.worker_id,))
        emp_data = c.fetchone()
        
        if emp_data and emp_data[0] == 'PAYE':
            my_hours = emp_data[1] * 4.33
            my_gross = (emp_data[2] / 8) * my_hours
            st.info("ℹ️ **You are a Salaried PAYE Employee.** Your monthly pay is fixed regardless of daily shift logs.")
        else:
            c.execute("SELECT SUM(s.hours), SUM(s.hours * (st.day_rate / 8)) FROM shifts s JOIN staff st ON s.worker_id = st.id WHERE strftime('%Y-%m', s.date) = ? AND s.worker_id = ?", (selected_month_str, st.session_state.worker_id))
            my_data = c.fetchone()
            my_hours, my_gross = (my_data[0] or 0, my_data[1] or 0)
        
        w1, w2 = st.columns(2)
        with w1.container(border=True): st.metric("⏱️ Total Hours (Monthly)", f"{my_hours:,.1f}h")
        with w2.container(border=True): st.metric("💰 Estimated Gross Pay", f"£{my_gross:,.2f}")

    conn.close()


elif choice == "Project Archive":
    conn = sqlite3.connect('interior_revolutions.db')
    display_page_header("🗂️ Project Archive", "Historical performance and monthly financial scoreboards.")
    
    # --- 1. SESSION STATE & NAVIGATION ---
    if 'arch_view_year' not in st.session_state:
        st.session_state.arch_view_year = datetime.datetime.now().year
        st.session_state.arch_view_month = datetime.datetime.now().month

    def arch_prev_month():
        st.session_state.arch_view_month -= 1
        if st.session_state.arch_view_month < 1: 
            st.session_state.arch_view_month, st.session_state.arch_view_year = 12, st.session_state.arch_view_year - 1

    def arch_next_month():
        st.session_state.arch_view_month += 1
        if st.session_state.arch_view_month > 12: 
            st.session_state.arch_view_month, st.session_state.arch_view_year = 1, st.session_state.arch_view_year + 1

    arch_month_name = calendar.month_name[st.session_state.arch_view_month]

    # --- 2. DATA CALCULATION ENGINE ---
    df_archived = pd.read_sql_query("SELECT name, start_date, end_date, amount_received, budget FROM projects WHERE status IN ('Completed', 'Archived')", conn)
    
    monthly_income = 0
    monthly_staff = 0
    monthly_mats = 0
    df_month_filtered = pd.DataFrame()
    active_this_month_names = []

    if not df_archived.empty:
        # THESE LINES MUST BE INDENTED FURTHER TO THE RIGHT
        df_archived['amount_received'] = pd.to_numeric(df_archived['amount_received'], errors='coerce')
        df_archived['budget'] = pd.to_numeric(df_archived['budget'], errors='coerce')
        
        df_archived['start_date_dt'] = pd.to_datetime(df_archived['start_date'], errors='coerce')
        df_archived['end_date_dt'] = pd.to_datetime(df_archived['end_date'], errors='coerce')
        
        # Projects that actually finished this month
        df_month_filtered = df_archived[(df_archived['end_date_dt'].dt.month == st.session_state.arch_view_month) & 
                                        (df_archived['end_date_dt'].dt.year == st.session_state.arch_view_year)]
        
        cal_start = pd.Timestamp(year=st.session_state.arch_view_year, month=st.session_state.arch_view_month, day=1)
        cal_end = cal_start + pd.offsets.MonthEnd(1)
        
        for _, row in df_archived.iterrows():
            if pd.notna(row['start_date_dt']) and pd.notna(row['end_date_dt']):
                if row['start_date_dt'] <= cal_end and row['end_date_dt'] >= cal_start:
                    active_this_month_names.append(row['name'])

        for _, row in df_month_filtered.iterrows():
            p_name = row['name']
            income = row['amount_received'] if pd.notna(row['amount_received']) else (row['budget'] or 0.0)
            c = conn.cursor()
            mats = c.execute("SELECT SUM(total_cost) FROM project_quotes WHERE project_name = ? AND item_type IN ('Material', 'Service')", (p_name,)).fetchone()[0] or 0
            staff = c.execute("SELECT SUM(s.hours * (st.day_rate / 8)) FROM shifts s JOIN staff st ON s.worker_id = st.id WHERE s.project = ?", (p_name,)).fetchone()[0] or 0
            monthly_income += income
            monthly_mats += mats
            monthly_staff += staff
            
    # Calculations and UI stay inside the 'elif' but outside the 'if not empty' block to show 0s if empty
    monthly_profit = monthly_income - (monthly_mats + monthly_staff)

    # --- 3. HIGH-IMPACT HERO METRICS ---
    st.markdown(f"<h1 style='text-align: center; font-size: 3rem; font-weight: 900; margin-bottom: 25px;'>🏆 {arch_month_name} {st.session_state.arch_view_year} Performance</h1>", unsafe_allow_html=True)
    
    st.markdown("""
        <style>
        .hero-card { 
            background: #1E293B; 
            padding: 20px 30px; 
            border-radius: 12px; 
            border: 1px solid #334155; 
            display: flex; 
            flex-direction: row; 
            justify-content: space-between; 
            align-items: center; 
            margin-bottom: 15px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
        }
        .hero-label { color: #94A3B8; font-size: 1.4rem; margin: 0; text-transform: uppercase; font-weight: bold; }
        .hero-value { color: #F8FAFC; font-size: 3.2rem; font-weight: 900; margin: 0; }
        .hero-profit { color: #2ECC71; font-size: 3.5rem; font-weight: 900; margin: 0; text-shadow: 0px 0px 15px rgba(46, 204, 113, 0.3); }
        </style>
    """, unsafe_allow_html=True)

    h1, h2 = st.columns(2)
    with h1: 
        st.markdown(f"<div class='hero-card'><p class='hero-label'>Total Income</p><p class='hero-value'>£{monthly_income:,.0f}</p></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='hero-card'><p class='hero-label'>Material Spend</p><p class='hero-value'>£{monthly_mats:,.0f}</p></div>", unsafe_allow_html=True)
    with h2: 
        st.markdown(f"<div class='hero-card'><p class='hero-label'>Staff (Gross)</p><p class='hero-value'>£{monthly_staff:,.0f}</p></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='hero-card' style='border-color: #2ecc71; background: rgba(46, 204, 113, 0.05);'><p class='hero-label' style='color:#2ecc71;'>Net Profit</p><p class='hero-profit'>£{monthly_profit:,.0f}</p></div>", unsafe_allow_html=True)

    st.write("")

    # --- 4. NAVIGATION & CALENDAR ---
    with st.container(border=True):
        cal_c1, cal_c2, cal_c3 = st.columns([1, 2, 1])
        with cal_c1: st.button("◀️ Prev Month", on_click=arch_prev_month, key="arch_prev", use_container_width=True)
        with cal_c2: st.markdown(f"<h3 style='text-align: center; margin-top:0px;'>{arch_month_name} {st.session_state.arch_view_year}</h3>", unsafe_allow_html=True)
        with cal_c3: st.button("Next Month ▶️", on_click=arch_next_month, key="arch_next", use_container_width=True)

        color_palette = ["🔴", "🔵", "🟠", "🟣", "🟤", "🟡", "🟢", "⚪"]
        proj_colors = {p_name: color_palette[i % len(color_palette)] for i, p_name in enumerate(set(active_this_month_names))}

        cols = st.columns(7)
        for i, day in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]): 
            cols[i].markdown(f"<div style='text-align:center'><b>{day}</b></div>", unsafe_allow_html=True) 

        for week in calendar.monthcalendar(st.session_state.arch_view_year, st.session_state.arch_view_month):
            week_cols = st.columns(7)
            for i, day in enumerate(week):
                if day != 0:
                    date_str = f"{st.session_state.arch_view_year}-{st.session_state.arch_view_month:02d}-{day:02d}"
                    active_dots = ""
                    for p_name, color in proj_colors.items():
                        row = df_archived[df_archived['name'] == p_name].iloc[0]
                        if row['start_date'] <= date_str <= row['end_date']:
                            active_dots += color
                    
                    if week_cols[i].button(f"{day}\n{active_dots}" if active_dots else f"{day}", key=f"arch_btn_{date_str}", use_container_width=True):
                        st.session_state.arch_selected_date = date_str

    if proj_colors:
        st.caption("**Calendar Legend:**")
        legend_cols = st.columns(min(4, max(1, len(proj_colors))))
        for idx, (p_name, color) in enumerate(proj_colors.items()):
            legend_cols[idx % 4].markdown(f"{color} {p_name}")

    st.divider()

    # --- 5. UNARCHIVE TOOL ---
    with st.expander("⏪ Unarchive a Project"):
        if not df_archived.empty:
            with st.form("unarchive_form"):
                p_to_revive = st.selectbox("Select Project to Re-open", df_archived['name'].tolist())
                if st.form_submit_button("Re-open Project", type="primary"):
                    c = conn.cursor()
                    c.execute("UPDATE projects SET status = 'Live', end_date = NULL WHERE name = ?", (p_to_revive,))
                    conn.commit()
                    st.success(f"✅ {p_to_revive} is Live again!")
                    st.rerun()

    # --- 6. INDIVIDUAL PROJECT EXPANDERS ---
    st.subheader(f"📂 {arch_month_name} Detailed Breakdowns")
    
    if not df_month_filtered.empty:
        for index, row in df_month_filtered.iterrows():
            p_name = row['name']
            amount_received = row['amount_received'] if pd.notna(row['amount_received']) else (row['budget'] or 0.0)
            
            c = conn.cursor()
            df_qb = pd.read_sql_query("SELECT item_type, item_name, quantity, total_cost FROM project_quotes WHERE project_name = ?", conn, params=[p_name])
            qb_mats = df_qb[df_qb['item_type'].isin(['Material', 'Service'])]['total_cost'].sum() if not df_qb.empty else 0
            qb_lab = df_qb[df_qb['item_type'] == 'Labor']['total_cost'].sum() if not df_qb.empty else 0
            
            actual_lab = c.execute("SELECT SUM(s.hours * (st.day_rate / 8)) FROM shifts s JOIN staff st ON s.worker_id = st.id WHERE s.project = ?", (p_name,)).fetchone()[0] or 0
            net_profit = amount_received - (qb_mats + actual_lab)
            
            with st.expander(f"🗂️ {proj_colors.get(p_name, '⚪')} {p_name.upper()} | Profit: £{net_profit:,.2f}"):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.caption("📦 **Material Details**")
                    if not df_qb.empty:
                        st.dataframe(df_qb[df_qb['item_type'].isin(['Material', 'Service'])][['item_name', 'quantity', 'total_cost']].style.format({"total_cost": "£{:,.2f}"}), use_container_width=True, hide_index=True)
                with col_b:
                    st.caption("👷 **Labour Burn Rate (Screaming Red Alert)**")
                    df_actual = pd.read_sql_query("SELECT st.role AS Role, SUM(s.hours) AS Actual_Hours FROM shifts s JOIN staff st ON s.worker_id = st.id WHERE s.project = ? GROUP BY st.role", conn, params=[p_name])
                    
                    df_lab_quoted = df_qb[df_qb['item_type'] == 'Labor'].copy() if not df_qb.empty else pd.DataFrame(columns=['item_name', 'quantity'])
                    if not df_lab_quoted.empty:
                        df_lab_quoted = df_lab_quoted[['item_name', 'quantity']].rename(columns={'item_name': 'Role'})
                        df_lab_quoted['Role'] = df_lab_quoted['Role'].str.replace(' Day Rate', '', case=False).str.strip().str.title()
                        df_lab_quoted['Role'] = df_lab_quoted['Role'].str.replace('Laborer', 'Labourer', case=False) 
                        df_lab_quoted = df_lab_quoted.groupby('Role', as_index=False).sum()
                        df_lab_quoted['Quoted_Hours'] = df_lab_quoted['quantity'].astype(float) * 8
                    else:
                        df_lab_quoted = pd.DataFrame(columns=['Role', 'Quoted_Hours'])
                        
                    if not df_actual.empty:
                        df_actual['Role'] = df_actual['Role'].str.replace(' Day Rate', '', case=False).str.strip().str.title()
                        df_actual['Role'] = df_actual['Role'].str.replace('Laborer', 'Labourer', case=False)
                        df_actual = df_actual.groupby('Role', as_index=False).sum()

                    if not df_actual.empty or not df_lab_quoted.empty:
                        df_labor_merge = pd.merge(df_actual, df_lab_quoted, on='Role', how='outer').fillna(0)
                        for _, l_row in df_labor_merge.iterrows():
                            role, act, quo = l_row['Role'], l_row['Actual_Hours'], l_row['Quoted_Hours']
                            pct = (act / quo * 100) if quo > 0 else (100 if act > 0 else 0)
                            bar_width = min(pct, 100)
                            
                            is_over_budget = act > quo
                            bar_color = "#E74C3C" if is_over_budget else "#2ECC71" 
                            text_color = "#E74C3C" if is_over_budget else "#94A3B8"
                            font_weight = "900" if is_over_budget else "bold"
                            
                            st.markdown(f"**{role}**")
                            st.markdown(f"""
                                <div style="display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 2px;">
                                    <span style="color: {text_color}; font-weight: {font_weight};">{act:.1f}h actual</span>
                                    <span style="color: #94A3B8;">{quo:.1f}h quoted</span>
                                </div>
                                <div style="width: 100%; background-color: rgba(255,255,255,0.1); border-radius: 5px; height: 12px; margin-bottom: 5px;">
                                    <div style="width: {bar_width}%; background-color: {bar_color}; height: 12px; border-radius: 5px;"></div>
                                </div>
                            """, unsafe_allow_html=True)
                            
                            if is_over_budget:
                                st.markdown(f"<div style='background-color: rgba(231, 76, 60, 0.15); border: 1px solid #E74C3C; border-radius: 5px; padding: 8px; margin-bottom: 15px;'><span style='color: #E74C3C; font-weight: bold;'>⚠️ LOSS DETECTED: Paid for {(act - quo):.1f} unquoted hours!</span></div>", unsafe_allow_html=True)
                    else:
                        st.info("No labour data available.")
    else:
        st.info(f"No projects ended in {arch_month_name}.")
    
    conn.close()

elif choice == "ROI & Analytics":
    conn = sqlite3.connect('interior_revolutions.db')
    display_page_header("📈 ROI & Business Analytics", "Track profit margins, historical AI performance, and project tier health.")
    
    try:
        df_archived = pd.read_sql_query("SELECT name, budget, end_date, ai_suggested_quote, tier FROM projects WHERE status IN ('Completed', 'Archived')", conn)
    except pd.errors.DatabaseError:
        df_archived = pd.DataFrame()
    
    if not df_archived.empty:
        # --- PASTE THESE TWO LINES HERE ---
        df_archived['budget'] = pd.to_numeric(df_archived['budget'], errors='coerce')
        df_archived['ai_suggested_quote'] = pd.to_numeric(df_archived['ai_suggested_quote'], errors='coerce')
        # ----------------------------------
        analytics_data = []
        for _, row in df_archived.iterrows():
            p_name = row['name']
            revenue = row['budget'] or 0.0
            end_date = row['end_date']
            ai_quote = row['ai_suggested_quote'] or revenue
            tier = row['tier'] or "Tier 2 (£1k-£10k)"
            
            if not end_date: continue 
            
            c = conn.cursor()
            mats_try = c.execute("SELECT SUM(total_cost) FROM project_quotes WHERE project_name = ? AND item_type IN ('Material', 'Service')", (p_name,)).fetchone()
            mats_cost = mats_try[0] if mats_try and mats_try[0] else 0
            
            labor_try = c.execute("SELECT SUM(s.hours * (st.day_rate / 8)) FROM shifts s JOIN staff st ON s.worker_id = st.id WHERE s.project = ?", (p_name,)).fetchone()
            labor_cost = labor_try[0] if labor_try and labor_try[0] else 0
            
            total_cost = mats_cost + labor_cost
            profit = revenue - total_cost
            roi_pct = (profit / total_cost * 100) if total_cost > 0 else 0
            
            left_on_table = max(0, ai_quote - revenue) if (ai_quote > revenue) else 0
            month_year = datetime.datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y-%m")
            analytics_data.append({"Project": p_name, "Revenue": revenue, "Total Cost": total_cost, "Profit": profit, "ROI %": roi_pct, "Month": month_year, "Tier": tier, "Lost AI Upside": left_on_table})
            
        df_analytics = pd.DataFrame(analytics_data)
        
        if not df_analytics.empty:
            st.subheader("🏆 Global Performance & AI Tracking")
            total_rev = df_analytics['Revenue'].sum()
            total_prof = df_analytics['Profit'].sum()
            global_roi = (total_prof / df_analytics['Total Cost'].sum() * 100) if df_analytics['Total Cost'].sum() > 0 else 0
            total_lost_ai = df_analytics['Lost AI Upside'].sum()
            
            k1, k2, k3, k4 = st.columns(4)
            with k1.container(border=True): st.metric("Total Historical Revenue", f"£{total_rev:,.2f}")
            with k2.container(border=True): st.metric("Total Historical Profit", f"£{total_prof:,.2f}")
            with k3.container(border=True): st.metric("Global Average ROI", f"{global_roi:.1f}%")
            with k4.container(border=True): st.metric("Revenue Ignored (AI Upside)", f"£{total_lost_ai:,.2f}", help="Money left on the table by overriding AI suggestions.")
            
            st.divider()
            
            col_charts_1, col_charts_2 = st.columns(2)
            import plotly.express as px
            
            with col_charts_1:
                st.subheader("📊 Average ROI by Project Tier")
                df_tiers = df_analytics.groupby('Tier', as_index=False)['ROI %'].mean()
                fig_tiers = px.bar(df_tiers, x='Tier', y='ROI %', color='Tier', color_discrete_map={"Tier 1 (<£1k)": "#2ECC71", "Tier 2 (£1k-£10k)": "#3498DB", "Tier 3 (£10k+)": "#27AE60"}, text_auto='.1f')
                fig_tiers.update_layout(showlegend=False, yaxis_title="Average ROI (%)", xaxis_title="", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#F8FAFC")
                with st.container(border=True): st.plotly_chart(fig_tiers, use_container_width=True)
                
            with col_charts_2:
                st.subheader("📈 Monthly ROI Trend (Global)")
                df_trend = df_analytics.groupby('Month', as_index=False).apply(lambda x: pd.Series({"Monthly ROI": (x['Profit'].sum() / x['Total Cost'].sum() * 100) if x['Total Cost'].sum() > 0 else 0})).sort_values('Month')
                fig_trend = px.line(df_trend, x='Month', y='Monthly ROI', markers=True, line_shape='spline')
                fig_trend.update_traces(line_color='#38BDF8', line_width=4, marker=dict(size=10, color='white', line=dict(width=2, color='#38BDF8')))
                fig_trend.update_layout(yaxis_title="ROI (%)", xaxis_title="", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#F8FAFC")
                with st.container(border=True): st.plotly_chart(fig_trend, use_container_width=True)

            st.write("") 

            st.subheader("📉 Tier ROI Fluctuations Over Time")
            
            if 'Date_Month' not in df_analytics.columns:
                df_analytics['Date_Month'] = pd.to_datetime(df_analytics['Month'], errors='coerce')
            
            df_tier_trend = df_analytics.groupby(['Date_Month', 'Tier'], as_index=False).apply(
                lambda x: pd.Series({"Monthly ROI": (x['Profit'].sum() / x['Total Cost'].sum() * 100) if x['Total Cost'].sum() > 0 else 0})
            ).sort_values('Date_Month')
            
            fig_tier_trend = px.line(df_tier_trend, x='Date_Month', y='Monthly ROI', color='Tier', markers=True, line_shape='spline',
                                     color_discrete_map={"Tier 1 (<£1k)": "#2ECC71", "Tier 2 (£1k-£10k)": "#38BDF8", "Tier 3 (£10k+)": "#9B59B6"})
            fig_tier_trend.update_layout(yaxis_title="ROI (%)", xaxis_title="", legend_title_text='', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#F8FAFC")
            
            with st.container(border=True): st.plotly_chart(fig_tier_trend, use_container_width=True)
            st.divider()

            if 'roi_view_year' not in st.session_state: st.session_state.roi_view_year = datetime.datetime.now().year

            def roi_prev_year(): st.session_state.roi_view_year -= 1
            def roi_next_year(): st.session_state.roi_view_year += 1

            with st.container(border=True):
                rc1, rc2, rc3 = st.columns([1, 2, 1])
                with rc1: st.button("◀️ Previous Year", on_click=roi_prev_year, key="roi_prev_yr", use_container_width=True)
                with rc2: st.markdown(f"<h3 style='text-align: center; margin-top:0px;'>{st.session_state.roi_view_year} Performance</h3>", unsafe_allow_html=True)
                with rc3: st.button("Next Year ▶️", on_click=roi_next_year, key="roi_next_yr", use_container_width=True)

            df_yearly = df_analytics[df_analytics['Date_Month'].dt.year == st.session_state.roi_view_year]

            st.write("")
            c_best, c_worst = st.columns(2)
            
            if not df_yearly.empty:
                with c_best:
                    st.success(f"🟢 Top 5 Most Profitable Jobs ({st.session_state.roi_view_year})")
                    df_best = df_yearly.sort_values(by='Profit', ascending=False).head(5)
                    st.dataframe(df_best[['Project', 'Tier', 'Profit', 'ROI %']].style.format({"Profit": "£{:,.2f}", "ROI %": "{:.1f}%"}), use_container_width=True, hide_index=True)
                    
                with c_worst:
                    st.error(f"🔴 Top 5 Biggest Bleeds ({st.session_state.roi_view_year})")
                    df_worst = df_yearly.sort_values(by='Profit', ascending=True).head(5)
                    st.dataframe(df_worst[['Project', 'Tier', 'Profit', 'ROI %']].style.format({"Profit": "£{:,.2f}", "ROI %": "{:.1f}%"}), use_container_width=True, hide_index=True)
            else:
                st.info(f"No completed projects found for {st.session_state.roi_view_year}.")
        else:
            st.info("No completed projects with valid budgets available yet.")
    else:
        st.info("No completed projects available yet to run analytics.")
    conn.close()

elif choice == "HR & Admin":
    conn = sqlite3.connect('interior_revolutions.db')
    display_page_header("⚙️ Human Resources", "Register new workers, manage team profiles, and remove inactive staff.")
    
    with st.expander("➕ Register New Worker", expanded=False):
        with st.form("register_staff_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_name = st.text_input("Full Name")
                new_password = st.text_input("Password", value="changeme") 
                new_role = st.selectbox("Role", ["Carpenter", "Painter", "Labourer", "Manager"])
            with col2:
                new_rate = st.number_input("Day Rate (£)", min_value=50.0, value=150.0, step=10.0)
                new_cis = st.selectbox("CIS Tax Rate (%)", [20, 30, 0]) 
            if st.form_submit_button("Register Worker", type="primary"):
                c = conn.cursor()
                c.execute("SELECT name FROM staff WHERE name=?", (new_name,))
                if c.fetchone(): st.error("❌ Name already exists!")
                else:
                    c.execute("INSERT INTO staff (name, password, role, day_rate, contracted_hours, employment_type, cis_rate) VALUES (?, ?, ?, ?, 0, 'CIS', ?)", (new_name, new_password, new_role, new_rate, new_cis))
                    conn.commit()
                    st.success(f"✅ {new_name} added!"); import time; time.sleep(1.5); st.rerun()

    st.divider()
    st.subheader("📋 Team Roster")
    df_staff = pd.read_sql_query("SELECT id, name, role, day_rate, cis_rate FROM staff", conn)
    
    if not df_staff.empty:
        st.dataframe(df_staff[['name', 'role', 'day_rate', 'cis_rate']].style.format({"day_rate": "£{:.2f}", "cis_rate": "{:.0f}%"}), use_container_width=True, hide_index=True)
        
        c_edit, c_del = st.columns(2)
        with c_edit:
            with st.expander("🛠️ Edit a Profile"):
                worker_opts = {row['name']: row['id'] for _, row in df_staff.iterrows()}
                selected_name = st.selectbox("Select Worker to Edit", list(worker_opts.keys()))
                worker_id = worker_opts[selected_name]
                cur_data = df_staff[df_staff['id'] == worker_id].iloc[0]
                
                with st.form("update_staff"):
                    c1, c2 = st.columns(2)
                    with c1: 
                        new_role = st.selectbox("Role", ["Carpenter", "Painter", "Labourer", "Manager"])
                        new_cis = st.selectbox("CIS Rate", [20, 30, 0], index=[20,30,0].index(int(cur_data['cis_rate'])))
                    with c2: 
                        new_rate = st.number_input("Day Rate", value=float(cur_data['day_rate']))
                        
                    if st.form_submit_button("Update Profile", type="primary"):
                        c = conn.cursor()
                        c.execute("UPDATE staff SET role=?, day_rate=?, cis_rate=? WHERE id=?", (new_role, new_rate, new_cis, worker_id))
                        conn.commit()
                        st.success("✅ Profile updated!"); import time; time.sleep(1.5); st.rerun()
                        
        with c_del:
            with st.expander("🗑️ Delete a Worker"):
                del_opts = {row['name']: row['id'] for _, row in df_staff.iterrows() if row['name'] != 'admin'}
                if del_opts:
                    with st.form("delete_staff"):
                        selected_del_name = st.selectbox("Select Worker to Delete", list(del_opts.keys()))
                        confirm_delete = st.checkbox(f"⚠️ Confirm removal of {selected_del_name}.")
                        if st.form_submit_button("Delete Worker", type="primary"):
                            if confirm_delete:
                                c = conn.cursor()
                                c.execute("DELETE FROM staff WHERE id=?", (del_opts[selected_del_name],))
                                conn.commit()
                                st.success(f"✅ {selected_del_name} removed."); import time; time.sleep(1.5); st.rerun()
                            else: st.error("Check the confirmation box.")
                else: st.info("No removable workers found.")
    conn.close()

elif choice == "My Portal":
    conn = sqlite3.connect('interior_revolutions.db')
    display_page_header(f"👋 Welcome back, {st.session_state.user_name.split(' ')[0]}!", "Log your hours, check your upcoming pay, and review your schedule.")
    
    if 'my_view_year' not in st.session_state:
        st.session_state.my_view_year = datetime.datetime.now().year
        st.session_state.my_view_month = datetime.datetime.now().month
        st.session_state.my_selected_date = None

    def my_prev_month():
        st.session_state.my_view_month -= 1
        st.session_state.my_selected_date = None
        if st.session_state.my_view_month < 1: 
            st.session_state.my_view_month, st.session_state.my_view_year = 12, st.session_state.my_view_year - 1

    def my_next_month():
        st.session_state.my_view_month += 1
        st.session_state.my_selected_date = None
        if st.session_state.my_view_month > 12: 
            st.session_state.my_view_month, st.session_state.my_view_year = 1, st.session_state.my_view_year + 1

    my_month_str = f"{st.session_state.my_view_year}-{st.session_state.my_view_month:02d}"
    my_month_name = calendar.month_name[st.session_state.my_view_month]

    df_live = pd.read_sql_query("SELECT name FROM projects WHERE status = 'Live'", conn)
    
    with st.expander("⏱️ Submit Today's Timesheet", expanded=True):
        if not df_live.empty:
            with st.form("worker_shift_logger", clear_on_submit=True):
                project = st.selectbox("Which site were you on today?", df_live['name'].tolist())
                c1, c2 = st.columns(2)
                with c1: shift_date = st.date_input("Date of Shift")
                with c2: hours = st.number_input("Hours Worked", min_value=0.5, max_value=14.0, value=8.0, step=0.5)
                confirm_shift = st.checkbox("⚠️ I confirm that these hours and location are strictly accurate.")
                
                if st.form_submit_button("Submit Timesheet to Manager", type="primary", use_container_width=True):
                    if not confirm_shift: st.error("❌ You must check the confirmation box.")
                    else:
                        c = conn.cursor()
                        c.execute("SELECT SUM(hours) FROM shifts WHERE worker_id = ? AND date = ?", (st.session_state.worker_id, str(shift_date)))
                        hours_already_logged = c.fetchone()[0] or 0
                        if hours_already_logged + hours > 14.0: st.error(f"❌ Overtime Limit Reached for {shift_date}.")
                        else:
                            c.execute("INSERT INTO shifts (worker_id, project, hours, date) VALUES (?, ?, ?, ?)", (st.session_state.worker_id, project, hours, str(shift_date)))
                            conn.commit()
                            st.success(f"✅ Timesheet submitted!"); import time; time.sleep(1.5); st.rerun()
        else: st.info("No live projects currently active.")
            
    st.divider()
    st.subheader(f"💸 My Earnings: {my_month_name} {st.session_state.my_view_year}")
    
    c = conn.cursor()
    c.execute("SELECT employment_type, contracted_hours, day_rate, cis_rate FROM staff WHERE id = ?", (st.session_state.worker_id,))
    emp_data = c.fetchone()
    
    if emp_data and emp_data[0] == 'PAYE':
        c.execute("SELECT SUM(hours) FROM shifts WHERE strftime('%Y-%m', date) = ? AND worker_id = ?", (my_month_str, st.session_state.worker_id))
        logged_hours = c.fetchone()[0] or 0
        my_hours = emp_data[1] * 4.33
        my_gross = (emp_data[2] / 8) * my_hours
        
        taxable_pay = max(0, my_gross - 1047.50)
        income_tax = taxable_pay * 0.20 
        niable_pay = max(0, my_gross - 1048.00)
        ni_tax = niable_pay * 0.08 
        hmrc_deduction = income_tax + ni_tax
        my_net = my_gross - hmrc_deduction
        
        w1, w2, w3, w4 = st.columns(4)
        with w1.container(border=True): st.metric("⏱️ Logged Hours", f"{logged_hours:,.1f}h")
        with w2.container(border=True): st.metric("💰 Gross Pay", f"£{my_gross:,.2f}")
        with w3.container(border=True): st.metric("🏛️ HMRC Tax/NI", f"-£{hmrc_deduction:,.2f}", help=f"Income Tax: £{income_tax:,.2f} | NI: £{ni_tax:,.2f}")
        with w4.container(border=True): st.metric("💸 Net Pay", f"£{my_net:,.2f}")
        st.info("ℹ️ **You are a Salaried PAYE Employee.** Deductions calculated via 1257L tax code.")
    else:
        cis_rate_pct = emp_data[3] if emp_data else 20
        c.execute("SELECT SUM(s.hours), SUM(s.hours * (st.day_rate / 8)) FROM shifts s JOIN staff st ON s.worker_id = st.id WHERE strftime('%Y-%m', s.date) = ? AND s.worker_id = ?", (my_month_str, st.session_state.worker_id))
        my_data = c.fetchone()
        my_hours = my_data[0] or 0
        my_gross = my_data[1] or 0
        my_cis_tax = my_gross * (cis_rate_pct / 100)
        my_net = my_gross - my_cis_tax
        
        w1, w2, w3, w4 = st.columns(4)
        with w1.container(border=True): st.metric("⏱️ Logged Hours", f"{my_hours:,.1f}h")
        with w2.container(border=True): st.metric("💰 Gross Pay", f"£{my_gross:,.2f}")
        with w3.container(border=True): st.metric(f"🏛️ CIS Deduction ({cis_rate_pct}%)", f"-£{my_cis_tax:,.2f}")
        with w4.container(border=True): st.metric("💸 Net Pay", f"£{my_net:,.2f}")
        st.caption("💡 As a CIS Sub-Contractor, you must pay your own NI via Self Assessment.")

    st.divider()
    st.subheader("📅 My Shift Calendar")
    
    with st.container(border=True):
        cal_c1, cal_c2, cal_c3 = st.columns([1, 2, 1])
        with cal_c1: st.button("◀️ Prev Month", on_click=my_prev_month, key="my_prev", use_container_width=True)
        with cal_c2: st.markdown(f"<h4 style='text-align: center; margin-top:8px;'>{my_month_name} {st.session_state.my_view_year}</h4>", unsafe_allow_html=True)
        with cal_c3: st.button("Next Month ▶️", on_click=my_next_month, key="my_next", use_container_width=True)

        df_my_shifts = pd.read_sql_query("SELECT id, date, project, hours FROM shifts WHERE worker_id = ?", conn, params=[st.session_state.worker_id])
        cols = st.columns(7)
        for i, day in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]): cols[i].markdown(f"<div style='text-align:center'><b>{day}</b></div>", unsafe_allow_html=True) 
        for week in calendar.monthcalendar(st.session_state.my_view_year, st.session_state.my_view_month):
            week_cols = st.columns(7)
            for i, day in enumerate(week):
                if day != 0:
                    date_str = f"{st.session_state.my_view_year}-{st.session_state.my_view_month:02d}-{day:02d}"
                    shift_count = len(df_my_shifts[df_my_shifts['date'] == date_str])
                    btn_label = f"{day} \n🟢 Logged" if shift_count == 1 else f"{day} \n🟢 {shift_count} logs" if shift_count > 1 else f"{day}"
                    if week_cols[i].button(btn_label, key=f"my_btn_{date_str}", use_container_width=True): st.session_state.my_selected_date = date_str

        if st.session_state.my_selected_date:
            st.divider()
            st.caption(f"📝 **Shift Details for {st.session_state.my_selected_date}**")
            selected_df = df_my_shifts[df_my_shifts['date'] == st.session_state.my_selected_date]
            if not selected_df.empty: st.dataframe(selected_df[['project', 'hours']], use_container_width=True, hide_index=True)
            else: st.info("No shifts logged on this date.")
    conn.close()

elif choice == "Experiment":
    conn = sqlite3.connect('interior_revolutions.db')
    display_page_header("🔬 AI Experiment & Model Forensics", "Audit the reasoning behind the AI's pricing suggestions.")

    df_audit = pd.read_sql_query("SELECT name, tier, original_quote, ai_suggested_quote, budget FROM projects WHERE ai_suggested_quote IS NOT NULL", conn)
    
    if not df_audit.empty:
        # --- PASTE THESE THREE LINES HERE ---
        df_audit['original_quote'] = pd.to_numeric(df_audit['original_quote'], errors='coerce')
        df_audit['ai_suggested_quote'] = pd.to_numeric(df_audit['ai_suggested_quote'], errors='coerce')
        df_audit['budget'] = pd.to_numeric(df_audit['budget'], errors='coerce')
        # ----------------------------------
        selected_audit = st.selectbox("Select a Project to Audit:", df_audit['name'].tolist())
        proj_data = df_audit[df_audit['name'] == selected_audit].iloc[0]
        
        st.subheader(f"📥 Input Data: {selected_audit}")
        df_items = pd.read_sql_query("SELECT item_type, item_name, total_cost FROM project_quotes WHERE project_name = ?", conn, params=[selected_audit])
        cost_mats = df_items[df_items['item_type'].isin(['Material', 'Service'])]['total_cost'].sum()
        cost_labour = df_items[df_items['item_type'] == 'Labor']['total_cost'].sum()
        total_base_cost = cost_mats + cost_labour
        
        c1, c2, c3 = st.columns(3)
        with c1.container(border=True): st.metric("Base Materials", f"£{cost_mats:,.2f}")
        with c2.container(border=True): st.metric("Base Labour", f"£{cost_labour:,.2f}")
        with c3.container(border=True): st.metric("Total Break-Even Cost", f"£{total_base_cost:,.2f}")

        st.divider()
        st.subheader("⚖️ Prediction Breakdown")
        
        ai_price = proj_data['ai_suggested_quote']
        original_human = proj_data['original_quote']
        
        if ai_price < total_base_cost: st.error(f"🚨 **CRITICAL MODEL FAILURE:** The AI suggested £{ai_price:,.2f}, which is BELOW COST.")
        
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.write("**Human Base (Cost + 15%)**")
            st.title(f"£{original_human:,.2f}")
        with m_col2:
            st.write("**AI Ensemble Prediction**")
            st.title(f"£{ai_price:,.2f}")
        with m_col3:
            st.write("**Final Accepted Price**")
            st.title(f"£{proj_data['budget']:,.2f}")

        st.divider()
        st.subheader("🧠 Model Reasoning")
        
        keywords = ["mews", "premium", "oak", "farrow", "structural", "external", "bespoke"]
        found_keywords = [word for word in keywords if word in " ".join(df_items['item_name'].astype(str).tolist()).lower()]
        
        col_reason_1, col_reason_2 = st.columns(2)
        with col_reason_1:
            st.write("**Feature Weights:**")
            st.info(f"✅ **Base Cost Impact:** +£{total_base_cost:,.0f} (Primary Driver)")
            st.info(f"🔍 **NLP Sentiment:** High-End detected in {len(found_keywords)} items.")
            
        with col_reason_2:
            st.write("**Detected Keywords (High Value Indicators):**")
            if found_keywords:
                for word in found_keywords: st.markdown(f"- `{word.upper()}`")
            else: st.write("No high-value keywords detected in the item names.")

    else:
        st.info("No projects with AI quotes found. Go to 'Projects & Finances' and assign a Quote using the ML Engine first.")
    
    conn.close()

# ====================== FOOTER ======================
st.divider()
st.caption("Interior Revolutions - Resource & Budget Management System | Dark Slate Edition")

# ====================== FOOTER ======================
st.divider()
st.caption("Interior Revolutions - Resource & Budget Management System")