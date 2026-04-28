import streamlit as st
import pandas as pd
from datetime import datetime

# ====================== SESSION STATE INITIALIZATION ======================

if 'current_user' not in st.session_state:
    st.session_state.current_user = {"name": "Admin Student", "role": "Manager"}

if 'staff_data' not in st.session_state:
    st.session_state.staff_data = [
        {"id": 1, "name": "Alex", "skill": "Lead Designer", "day_rate": 300, "contracted_hours": 40},
        {"id": 2, "name": "Jordan", "skill": "Painter", "day_rate": 180, "contracted_hours": 35},
        {"id": 3, "name": "Sam", "skill": "Carpenter", "day_rate": 220, "contracted_hours": 40},
        {"id": 4, "name": "Peter", "skill": "Labourer", "day_rate": 150, "contracted_hours": 40}
    ]

if 'shift_ledger' not in st.session_state:
    st.session_state.shift_ledger = [
        {"worker_id": 1, "project": "Mayfair Penthouse", "hours": 8, "date": "2026-04-25"},
        {"worker_id": 1, "project": "Mayfair Penthouse", "hours": 8, "date": "2026-04-26"},
        {"worker_id": 2, "project": "Chelsea Studio", "hours": 10, "date": "2026-04-26"}
    ]

if 'role_rates' not in st.session_state:
    st.session_state.role_rates = {
        "Labourer": 150,
        "Painter": 180,
        "Carpenter": 220,
        "Lead Designer": 300
    }

if 'estimated_project_costs' not in st.session_state:
    st.session_state.estimated_project_costs = {}

if 'project_blueprints' not in st.session_state:
    st.session_state.project_blueprints = {
        "Chelsea Studio": [
            {"role": "Painter", "quantity": 4, "days": 4},
            {"role": "Labourer", "quantity": 1, "days": 2}
        ]
    }

if 'project_budgets' not in st.session_state:
    st.session_state.project_budgets = {
        "Mayfair Penthouse": 5000.00,
        "Chelsea Studio": 3030.00,
        "Modern Apartment Refurb": 5820.00
    }

# ====================== HELPER FUNCTIONS ======================

def get_staff_summary(worker_id):
    person = next((item for item in st.session_state.staff_data if item["id"] == worker_id), None)
    if not person:
        return None
    worked = sum(shift['hours'] for shift in st.session_state.shift_ledger if shift['worker_id'] == worker_id)
    difference = person['contracted_hours'] - worked
    status = "OWES HOURS" if difference > 0 else "TARGET MET"
    pay_owed = worked * (person['day_rate'] / 8)

    return {
        "Name": person['name'],
        "Worked": worked,
        "Contract": person['contracted_hours'],
        "Difference": abs(difference),
        "Status": status,
        "Current_Pay": f"£{pay_owed:,.2f}"
    }


def calculate_shift_duration(start_time, end_time):
    fmt = "%H:%M"
    start = datetime.strptime(start_time, fmt)
    end = datetime.strptime(end_time, fmt)
    duration = end - start
    return duration.total_seconds() / 3600


def check_rota_conflict(worker_id, date):
    conflicts = [s for s in st.session_state.shift_ledger 
                 if s['worker_id'] == worker_id and s['date'] == str(date)]
    if conflicts:
        return True, conflicts[0]['project']
    return False, None


def create_project_estimate(project_name, staff_requirements):
    total_estimate = 0
    breakdown_text = []

    for role, days in staff_requirements:
        rate = st.session_state.role_rates.get(role, 0)
        cost = rate * days
        total_estimate += cost
        unit = "days" if days >= 1 else "day"
        breakdown_text.append(f"• {role}: {days} {unit} @ £{rate}/day = £{cost:,.2f}")

    st.session_state.estimated_project_costs[project_name.lower()] = total_estimate
    return total_estimate, breakdown_text


def get_project_plan(project_name):
    if project_name not in st.session_state.project_blueprints:
        return None, "Project plan not found."

    plan = st.session_state.project_blueprints[project_name]
    total_estimated_cost = 0
    plan_details = []

    for item in plan:
        rate = st.session_state.role_rates.get(item['role'], 0)
        cost = item['quantity'] * item['days'] * rate
        total_estimated_cost += cost

        plan_details.append({
            "Role": item['role'],
            "Quantity": item['quantity'],
            "Days": item['days'],
            "Rate": f"£{rate}",
            "Cost": f"£{cost:,.2f}"
        })

    return plan_details, total_estimated_cost


def process_shift_entry(worker_id, worker_name, project, start_t, end_t, shift_date):
    has_conflict, conflict_project = check_rota_conflict(worker_id, shift_date)
    if has_conflict:
        return False, f"⚠️ Error: {worker_name} is already at '{conflict_project}' on this date."

    try:
        start_str = start_t.strftime("%H:%M")
        end_str = end_t.strftime("%H:%M")
        duration = calculate_shift_duration(start_str, end_str)

        if duration <= 0:
            return False, "❌ Finish time must be after start time."
    except Exception:
        return False, "❌ Invalid time selection."

    new_shift = {
        "worker_id": worker_id,
        "project": project.title(),
        "hours": round(duration, 2),
        "date": str(shift_date),
        "start": start_str,
        "end": end_str
    }
    st.session_state.shift_ledger.append(new_shift)
    return True, f"✅ Logged {round(duration, 2)} hours for {worker_name} on {project.title()}."


def get_manager_report():
    if not st.session_state.shift_ledger:
        return None, 0

    report_list = []
    total_spend = 0

    for shift in st.session_state.shift_ledger:
        worker = next(s for s in st.session_state.staff_data if s['id'] == shift['worker_id'])
        shift_cost = shift['hours'] * (worker['day_rate'] / 8)
        total_spend += shift_cost

        report_list.append({
            "Worker": worker['name'],
            "Project": shift['project'],
            "Date": shift['date'],
            "Hours": shift['hours'],
            "Cost": shift_cost
        })

    df = pd.DataFrame(report_list)
    df = df.sort_values(by=["Worker", "Project"])
    return df, total_spend


def get_budget_variance_report():
    budgets = st.session_state.project_budgets
    summary_data = []

    for project, budget in budgets.items():
        total_spent = 0
        for shift in st.session_state.shift_ledger:
            if shift['project'].lower() == project.lower():
                worker = next(s for s in st.session_state.staff_data if s['id'] == shift['worker_id'])
                total_spent += shift['hours'] * (worker['day_rate'] / 8)

        remaining = budget - total_spent
        percent_used = (total_spent / budget) * 100 if budget > 0 else 0

        if percent_used > 100:
            status = "🔴 OVER BUDGET"
        elif percent_used > 80:
            status = "🟡 WARNING"
        else:
            status = "🟢 HEALTHY"

        summary_data.append({
            "Project": project,
            "Budget": budget,
            "Spent": total_spent,
            "Remaining": remaining,
            "Usage": percent_used,
            "Status": status
        })

    return summary_data


# ====================== STREAMLIT UI ======================

st.set_page_config(page_title="Interior Allocations", layout="wide")
st.title("🏠 Interior Revolutions - Resource Allocation")

# ====================== SIDEBAR ======================
st.sidebar.title(f"Welcome, {st.session_state.current_user['name']}!")
user_role = st.session_state.current_user['role']

menu = ["Clock In/Out", "View My Shifts"]

if user_role == "Manager":
    menu.extend(["Create Project Estimate", "View Budget Dashboard", "Project Blueprints"])
    st.sidebar.success("✅ Manager Access Granted")

choice = st.sidebar.radio("Navigation", menu)

# ====================== MAIN PAGES ======================

if choice == "Project Blueprints":
    st.header("Project Planning & Estimation")
    st.subheader("View Original Blueprints")
    
    project_to_view = st.selectbox("Select Project", list(st.session_state.project_blueprints.keys()))
    
    if st.button("View Plan Details"):
        details, total = get_project_plan(project_to_view)
        if details:
            st.table(pd.DataFrame(details))
            st.metric("Total Estimated Cost", f"£{total:,.2f}")
        else:
            st.error(total)

elif choice == "Create Project Estimate":
    st.header("Create New Staff Estimate")
    
    with st.form("new_estimate_form"):
        new_p_name = st.text_input("Project Name", placeholder="e.g. Kensington Townhouse")
        role_to_add = st.selectbox("Staff Role", list(st.session_state.role_rates.keys()))
        qty = st.number_input("Quantity of Workers", min_value=1, step=1, value=1)
        days = st.number_input("Number of Days", min_value=0.5, step=0.5, value=1.0)
        submit_est = st.form_submit_button("Calculate & Save Estimate")
    
    if submit_est and new_p_name:
        total_days = qty * days
        total_cost, breakdown = create_project_estimate(new_p_name, [(role_to_add, total_days)])
        st.success(f"✅ Estimate for **{new_p_name}** saved!")
        st.metric("Total Estimated Cost", f"£{total_cost:,.2f}")
        st.write("**Breakdown:**")
        for line in breakdown:
            st.write(line)

elif choice == "Clock In/Out":
    st.header("Log New Shift")

    worker_map = {s['name']: s['id'] for s in st.session_state.staff_data}

    with st.form("shift_entry_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            selected_worker = st.selectbox("Worker Name", options=list(worker_map.keys()))
            project_name = st.text_input("Project Name", placeholder="e.g. Mayfair Penthouse")
            shift_date = st.date_input("Date of Shift", value=datetime.now().date())

        with col2:
            start_time = st.time_input("Start Time", value=datetime.strptime("08:00", "%H:%M").time())
            end_time = st.time_input("End Time", value=datetime.strptime("17:00", "%H:%M").time())

        submit = st.form_submit_button("Submit Shift")

    if submit:
        success, message = process_shift_entry(
            worker_map[selected_worker],
            selected_worker,
            project_name,
            start_time,
            end_time,
            shift_date
        )
        if success:
            st.success(message)
        else:
            st.error(message)

elif choice == "View My Shifts":
    st.header("Shift Report")
    report_df, grand_total = get_manager_report()
    
    if report_df is not None:
        st.metric("TOTAL BUSINESS OUTGOINGS", f"£{grand_total:,.2f}")
        st.subheader("Aggregated Shift Report")
        st.dataframe(
            report_df.style.format({"Cost": "£{:,.2f}", "Hours": "{:.2f}"}),
            use_container_width=True,
            hide_index=True
        )
        csv = report_df.to_csv(index=False).encode('utf-8')
        st.download_button("Export Report to CSV", data=csv, file_name="weekly_report.csv")
    else:
        st.info("No shifts logged yet.")

elif choice == "View Budget Dashboard":
    st.header("Project Budget Variance Report")
    
    variance_data = get_budget_variance_report()
    
    for item in variance_data:
        with st.expander(f"{item['Status']} - {item['Project']}", expanded=True):
            col1, col2, col3 = st.columns(3)
            col1.metric("Budget", f"£{item['Budget']:,.2f}")
            col2.metric("Spent", f"£{item['Spent']:,.2f}")
            col3.metric("Remaining", f"£{item['Remaining']:,.2f}")
            
            st.write(f"**Budget Usage:** {item['Usage']:.1f}%")
            st.progress(min(item['Usage'] / 100, 1.0))

# ====================== FOOTER ======================
st.divider()
st.caption("Interior Revolutions - Resource & Budget Management System")
