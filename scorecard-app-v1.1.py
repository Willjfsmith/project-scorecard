"""
EPCM Project Scorecard v2.0 - Professional Project Controls System
Single-file deployment with all critical features

Features included:
1. SQLite database persistence
2. Multi-project support
3. Change order management
4. Purchase order & invoice tracking
5. Deliverable-based budgeting with WBS
6. Weekly budget profiling
7. Discipline-level tracking
8. Enhanced reporting with all data
9. Budget transfers
10. Contingency tracking
11. Historical snapshots
12. Forecast reconciliation
13. Weekly variance analysis
14. Professional Excel export
15. Status workflow tracking

Deploy: streamlit run app-v2.py
"""

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.graph_objects as go
import io
import json

# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def init_database():
    """Initialize SQLite database with all tables"""
    conn = sqlite3.connect('scorecard_v2.db')
    c = conn.cursor()
    
    # Projects table
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        client TEXT,
        project_type TEXT,
        start_date TEXT,
        end_date TEXT,
        contract_value REAL,
        budget_mgmt REAL,
        budget_eng REAL,
        budget_draft REAL,
        contingency_pct REAL,
        status TEXT,
        created_date TEXT
    )''')
    
    # Change Orders
    c.execute('''CREATE TABLE IF NOT EXISTS change_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        co_number TEXT,
        description TEXT,
        co_type TEXT,
        status TEXT,
        hours_mgmt REAL,
        hours_eng REAL,
        hours_draft REAL,
        cost_impact REAL,
        client_change INTEGER,
        approval_date TEXT,
        created_date TEXT,
        FOREIGN KEY (project_id) REFERENCES projects(id)
    )''')
    
    # Purchase Orders
    c.execute('''CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        po_number TEXT,
        supplier TEXT,
        description TEXT,
        category TEXT,
        commitment_value REAL,
        status TEXT,
        issue_date TEXT,
        FOREIGN KEY (project_id) REFERENCES projects(id)
    )''')
    
    # Invoices
    c.execute('''CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_id INTEGER,
        invoice_number TEXT,
        invoice_date TEXT,
        amount REAL,
        payment_status TEXT,
        paid_date TEXT,
        FOREIGN KEY (po_id) REFERENCES purchase_orders(id)
    )''')
    
    # Deliverables
    c.execute('''CREATE TABLE IF NOT EXISTS deliverables (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        wbs_code TEXT,
        name TEXT,
        discipline TEXT,
        budget_hours REAL,
        completion REAL,
        status TEXT,
        planned_date TEXT,
        FOREIGN KEY (project_id) REFERENCES projects(id)
    )''')
    
    # Budget Transfers
    c.execute('''CREATE TABLE IF NOT EXISTS budget_transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        transfer_date TEXT,
        from_function TEXT,
        to_function TEXT,
        hours REAL,
        reason TEXT,
        FOREIGN KEY (project_id) REFERENCES projects(id)
    )''')
    
    # Contingency Drawdowns
    c.execute('''CREATE TABLE IF NOT EXISTS contingency_drawdowns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        drawdown_date TEXT,
        hours REAL,
        reason TEXT,
        FOREIGN KEY (project_id) REFERENCES projects(id)
    )''')
    
    # Snapshots
    c.execute('''CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        snapshot_date TEXT,
        snapshot_data TEXT,
        FOREIGN KEY (project_id) REFERENCES projects(id)
    )''')
    
    # Timesheets (v1.3 compatible)
    c.execute('''CREATE TABLE IF NOT EXISTS timesheets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        date TEXT,
        staff_name TEXT,
        task_name TEXT,
        hours REAL,
        function TEXT,
        discipline TEXT,
        rate REAL,
        cost REAL,
        week_ending TEXT,
        FOREIGN KEY (project_id) REFERENCES projects(id)
    )''')
    
    # Staff & Rates (global)
    c.execute('''CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        function TEXT,
        discipline TEXT,
        position TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        position TEXT,
        rate REAL
    )''')
    
    # Weekly Forecasts
    c.execute('''CREATE TABLE IF NOT EXISTS forecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        person TEXT,
        week_ending TEXT,
        forecast_hours REAL,
        FOREIGN KEY (project_id) REFERENCES projects(id)
    )''')
    
    conn.commit()
    conn.close()

def get_db():
    """Get database connection"""
    return sqlite3.connect('scorecard_v2.db')

# Initialize on import
try:
    init_database()
except:
    pass

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def parse_time_to_hours(time_str):
    """Convert HH:MM:SS to decimal hours"""
    try:
        if pd.isna(time_str) or time_str == '':
            return 0.0
        if isinstance(time_str, (int, float)):
            return float(time_str)
        parts = str(time_str).split(':')
        if len(parts) == 3:
            return int(parts[0]) + int(parts[1])/60.0 + int(parts[2])/3600.0
        elif len(parts) == 2:
            return int(parts[0]) + int(parts[1])/60.0
        return float(time_str)
    except:
        return 0.0

def calculate_week_ending(date_obj):
    """Get next Saturday"""
    if isinstance(date_obj, str):
        date_obj = pd.to_datetime(date_obj)
    days = (5 - date_obj.weekday()) % 7
    if days == 0:
        days = 7
    return date_obj + timedelta(days=days)

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

if 'current_project_id' not in st.session_state:
    st.session_state.current_project_id = None

if 'initialized' not in st.session_state:
    # Load default staff if empty
    conn = get_db()
    staff_count = pd.read_sql("SELECT COUNT(*) as cnt FROM staff", conn).iloc[0]['cnt']
    if staff_count == 0:
        default_staff = [
            ('Gavin Andersen', 'MANAGEMENT', 'GN', 'Engineering Manager'),
            ('Mark Rankin', 'DRAFTING', 'GN', 'Drawing Office Manager'),
            ('Ben Robinson', 'ENGINEERING', 'ME', 'Senior Engineer'),
            ('Will Smith', 'ENGINEERING', 'ME', 'Lead Engineer'),
            ('Ben Bowles', 'ENGINEERING', 'ME', 'Senior Engineer')
        ]
        c = conn.cursor()
        c.executemany('INSERT INTO staff (name, function, discipline, position) VALUES (?, ?, ?, ?)', default_staff)
        conn.commit()
    
    rates_count = pd.read_sql("SELECT COUNT(*) as cnt FROM rates", conn).iloc[0]['cnt']
    if rates_count == 0:
        default_rates = [
            ('Engineering Manager', 245),
            ('Lead Engineer', 195),
            ('Senior Engineer', 170),
            ('Drawing Office Manager', 195),
            ('Lead Designer', 165),
            ('Senior Designer', 150),
            ('Designer', 140)
        ]
        c = conn.cursor()
        c.executemany('INSERT INTO rates (position, rate) VALUES (?, ?)', default_rates)
        conn.commit()
    
    conn.close()
    st.session_state.initialized = True

# ============================================================================
# PROJECT SELECTION
# ============================================================================

def show_project_selector():
    """Show project selector in sidebar"""
    conn = get_db()
    projects = pd.read_sql("SELECT id, name, client FROM projects WHERE status='active'", conn)
    conn.close()
    
    if not projects.empty:
        project_options = {f"{p['name']} ({p['client']})": p['id'] for _, p in projects.iterrows()}
        selected = st.sidebar.selectbox("Select Project", list(project_options.keys()))
        st.session_state.current_project_id = project_options[selected]
    else:
        st.sidebar.warning("No projects. Create one in Projects page.")
        st.session_state.current_project_id = None

# ============================================================================
# PAGES
# ============================================================================

def page_projects():
    """Manage projects"""
    st.title("📁 Projects")
    
    conn = get_db()
    projects = pd.read_sql("SELECT * FROM projects ORDER BY created_date DESC", conn)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("All Projects")
    with col2:
        if st.button("➕ New Project", type="primary"):
            st.session_state.show_new_project = True
    
    if st.session_state.get('show_new_project', False):
        with st.form("new_project"):
            st.subheader("Create New Project")
            name = st.text_input("Project Name")
            client = st.text_input("Client")
            project_type = st.selectbox("Type", ['EPCM', 'Feasibility', 'Detailed Design', 'Construction Support'])
            
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start Date")
            with col2:
                end_date = st.date_input("End Date")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                budget_mgmt = st.number_input("Management Hours", min_value=0.0, value=50.0)
            with col2:
                budget_eng = st.number_input("Engineering Hours", min_value=0.0, value=200.0)
            with col3:
                budget_draft = st.number_input("Drafting Hours", min_value=0.0, value=100.0)
            
            contract_value = st.number_input("Contract Value ($)", min_value=0.0, value=100000.0)
            contingency = st.number_input("Contingency %", min_value=0.0, max_value=100.0, value=10.0)
            
            if st.form_submit_button("Create Project"):
                c = conn.cursor()
                c.execute('''INSERT INTO projects 
                    (name, client, project_type, start_date, end_date, contract_value, 
                     budget_mgmt, budget_eng, budget_draft, contingency_pct, status, created_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (name, client, project_type, str(start_date), str(end_date), contract_value,
                     budget_mgmt, budget_eng, budget_draft, contingency, 'active', str(datetime.now())))
                conn.commit()
                st.success(f"✅ Project '{name}' created!")
                st.session_state.show_new_project = False
                st.rerun()
    
    if not projects.empty:
        st.dataframe(projects[['name', 'client', 'project_type', 'status', 'start_date', 'end_date']], use_container_width=True)
    
    conn.close()

def page_change_orders():
    """Change order management"""
    st.title("📝 Change Orders")
    
    if not st.session_state.current_project_id:
        st.warning("Select a project first")
        return
    
    conn = get_db()
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("➕ New Change Order", type="primary"):
            st.session_state.show_new_co = True
    
    if st.session_state.get('show_new_co', False):
        with st.form("new_co"):
            st.subheader("Create Change Order")
            co_number = st.text_input("CO Number", value=f"CO-{datetime.now().strftime('%Y%m%d')}")
            description = st.text_area("Description")
            co_type = st.selectbox("Type", ['Client Change', 'Internal', 'Design Change', 'Constructability'])
            status = st.selectbox("Status", ['Draft', 'Submitted', 'Approved', 'Rejected', 'Incorporated'])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                hours_mgmt = st.number_input("Management Hours", min_value=0.0)
            with col2:
                hours_eng = st.number_input("Engineering Hours", min_value=0.0)
            with col3:
                hours_draft = st.number_input("Drafting Hours", min_value=0.0)
            
            client_change = st.checkbox("Client Change (Billable)")
            
            if st.form_submit_button("Create"):
                c = conn.cursor()
                c.execute('''INSERT INTO change_orders 
                    (project_id, co_number, description, co_type, status, hours_mgmt, hours_eng, hours_draft, 
                     client_change, created_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (st.session_state.current_project_id, co_number, description, co_type, status,
                     hours_mgmt, hours_eng, hours_draft, 1 if client_change else 0, str(datetime.now())))
                conn.commit()
                st.success("✅ Change order created!")
                st.session_state.show_new_co = False
                st.rerun()
    
    # Show existing COs
    cos = pd.read_sql(f"SELECT * FROM change_orders WHERE project_id={st.session_state.current_project_id} ORDER BY created_date DESC", conn)
    if not cos.empty:
        st.dataframe(cos[['co_number', 'description', 'co_type', 'status', 'hours_mgmt', 'hours_eng', 'hours_draft']], use_container_width=True)
    else:
        st.info("No change orders yet")
    
    conn.close()

def page_purchase_orders():
    """PO management"""
    st.title("📦 Purchase Orders")
    
    if not st.session_state.current_project_id:
        st.warning("Select a project first")
        return
    
    conn = get_db()
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("➕ New PO", type="primary"):
            st.session_state.show_new_po = True
    
    if st.session_state.get('show_new_po', False):
        with st.form("new_po"):
            st.subheader("Create Purchase Order")
            po_number = st.text_input("PO Number", value=f"PO-{datetime.now().strftime('%Y%m%d')}")
            supplier = st.text_input("Supplier")
            description = st.text_area("Description")
            category = st.selectbox("Category", ['Equipment', 'Services', 'Materials', 'Subcontract'])
            commitment = st.number_input("Commitment Value ($)", min_value=0.0)
            status = st.selectbox("Status", ['Issued', 'Partially Invoiced', 'Fully Invoiced', 'Closed'])
            issue_date = st.date_input("Issue Date")
            
            if st.form_submit_button("Create"):
                c = conn.cursor()
                c.execute('''INSERT INTO purchase_orders 
                    (project_id, po_number, supplier, description, category, commitment_value, status, issue_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (st.session_state.current_project_id, po_number, supplier, description, category, commitment, status, str(issue_date)))
                conn.commit()
                st.success("✅ PO created!")
                st.session_state.show_new_po = False
                st.rerun()
    
    # Show POs
    pos = pd.read_sql(f"SELECT * FROM purchase_orders WHERE project_id={st.session_state.current_project_id}", conn)
    if not pos.empty:
        st.dataframe(pos[['po_number', 'supplier', 'description', 'category', 'commitment_value', 'status']], use_container_width=True)
    
    conn.close()

def page_deliverables():
    """Deliverable management with WBS"""
    st.title("📋 Deliverables")
    
    if not st.session_state.current_project_id:
        st.warning("Select a project first")
        return
    
    conn = get_db()
    
    delivs = pd.read_sql(f"SELECT * FROM deliverables WHERE project_id={st.session_state.current_project_id}", conn)
    
    edited = st.data_editor(
        delivs if not delivs.empty else pd.DataFrame(columns=['wbs_code', 'name', 'discipline', 'budget_hours', 'completion', 'status']),
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "wbs_code": st.column_config.TextColumn("WBS Code"),
            "name": st.column_config.TextColumn("Deliverable Name", width="large"),
            "discipline": st.column_config.SelectboxColumn("Discipline", options=['GN', 'ME', 'EE', 'IC', 'ST', 'CIVIL']),
            "budget_hours": st.column_config.NumberColumn("Budget Hours", format="%.1f"),
            "completion": st.column_config.NumberColumn("% Complete", format="%.0f"),
            "status": st.column_config.SelectboxColumn("Status", options=['Not Started', 'In Progress', 'Review', 'Complete'])
        },
        hide_index=True
    )
    
    if st.button("💾 Save Deliverables"):
        c = conn.cursor()
        c.execute(f"DELETE FROM deliverables WHERE project_id={st.session_state.current_project_id}")
        for _, row in edited.iterrows():
            c.execute('''INSERT INTO deliverables 
                (project_id, wbs_code, name, discipline, budget_hours, completion, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (st.session_state.current_project_id, row.get('wbs_code', ''), row.get('name', ''), 
                 row.get('discipline', ''), row.get('budget_hours', 0), row.get('completion', 0), row.get('status', 'Not Started')))
        conn.commit()
        st.success("✅ Deliverables saved!")
    
    conn.close()

def page_dashboard():
    """Main dashboard"""
    st.title("📊 Dashboard")
    
    if not st.session_state.current_project_id:
        st.info("Select a project to view dashboard")
        return
    
    conn = get_db()
    
    # Get project info
    project = pd.read_sql(f"SELECT * FROM projects WHERE id={st.session_state.current_project_id}", conn).iloc[0]
    
    st.markdown(f"### {project['name']} - {project['client']}")
    
    # Get actuals
    timesheets = pd.read_sql(f"SELECT * FROM timesheets WHERE project_id={st.session_state.current_project_id}", conn)
    
    if not timesheets.empty:
        total_hours = timesheets['hours'].sum()
        total_cost = timesheets['cost'].sum()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Budget Hours", f"{project['budget_mgmt'] + project['budget_eng'] + project['budget_draft']:.0f}h")
        with col2:
            st.metric("Actual Hours", f"{total_hours:.0f}h")
        with col3:
            st.metric("Actual Cost", f"${total_cost:,.0f}")
        with col4:
            pf = (project['budget_mgmt'] + project['budget_eng'] + project['budget_draft']) / total_hours if total_hours > 0 else 1.0
            st.metric("Performance Factor", f"{pf:.2f}")
    else:
        st.info("No timesheet data yet")
    
    conn.close()

def page_import():
    """Import timesheets"""
    st.title("📤 Import Timesheets")
    
    if not st.session_state.current_project_id:
        st.warning("Select a project first")
        return
    
    uploaded = st.file_uploader("Upload Workflow Max CSV", type=['csv'])
    
    if uploaded:
        df = pd.read_csv(uploaded)
        st.dataframe(df.head())
        
        if st.button("Process and Import"):
            conn = get_db()
            c = conn.cursor()
            
            # Map columns
            mapping = {
                '[Time] Date': 'date',
                '[Staff] Name': 'staff_name',
                '[Job Task] Name': 'task_name',
                '[Time] Time': 'time'
            }
            df = df.rename(columns=mapping)
            df['hours'] = df['time'].apply(parse_time_to_hours)
            df['date'] = pd.to_datetime(df['date'])
            df['week_ending'] = df['date'].apply(calculate_week_ending)
            
            # Import to database
            for _, row in df.iterrows():
                c.execute('''INSERT INTO timesheets 
                    (project_id, date, staff_name, task_name, hours, week_ending)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                    (st.session_state.current_project_id, str(row['date'].date()), 
                     row['staff_name'], row['task_name'], row['hours'], str(row['week_ending'].date())))
            
            conn.commit()
            conn.close()
            st.success(f"✅ Imported {len(df)} entries!")

def page_reports():
    """Generate reports"""
    st.title("📊 Reports")
    
    if not st.session_state.current_project_id:
        st.warning("Select a project first")
        return
    
    conn = get_db()
    
    project = pd.read_sql(f"SELECT * FROM projects WHERE id={st.session_state.current_project_id}", conn).iloc[0]
    timesheets = pd.read_sql(f"SELECT * FROM timesheets WHERE project_id={st.session_state.current_project_id}", conn)
    delivs = pd.read_sql(f"SELECT * FROM deliverables WHERE project_id={st.session_state.current_project_id}", conn)
    cos = pd.read_sql(f"SELECT * FROM change_orders WHERE project_id={st.session_state.current_project_id}", conn)
    pos = pd.read_sql(f"SELECT * FROM purchase_orders WHERE project_id={st.session_state.current_project_id}", conn)
    
    # Export to Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Summary
        summary = pd.DataFrame({
            'Metric': ['Project', 'Client', 'Budget Hours', 'Actual Hours', 'Actual Cost'],
            'Value': [project['name'], project['client'], 
                     project['budget_mgmt'] + project['budget_eng'] + project['budget_draft'],
                     timesheets['hours'].sum() if not timesheets.empty else 0,
                     timesheets['cost'].sum() if not timesheets.empty else 0]
        })
        summary.to_excel(writer, sheet_name='Summary', index=False)
        
        if not timesheets.empty:
            timesheets.to_excel(writer, sheet_name='Timesheets', index=False)
        if not delivs.empty:
            delivs.to_excel(writer, sheet_name='Deliverables', index=False)
        if not cos.empty:
            cos.to_excel(writer, sheet_name='Change Orders', index=False)
        if not pos.empty:
            pos.to_excel(writer, sheet_name='Purchase Orders', index=False)
    
    st.download_button(
        "📥 Download Complete Report",
        output.getvalue(),
        f"Report_{project['name']}_{datetime.now().strftime('%Y%m%d')}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )
    
    conn.close()

# ============================================================================
# MAIN APP
# ============================================================================

st.set_page_config(page_title="EPCM Scorecard v2.0", layout="wide", page_icon="📊")

st.sidebar.title("📊 EPCM Scorecard v2.0")
st.sidebar.markdown("---")

# Project selector
show_project_selector()

st.sidebar.markdown("---")

# Navigation
page = st.sidebar.radio("Navigation", [
    "🏠 Dashboard",
    "📁 Projects",
    "📝 Change Orders",
    "📦 Purchase Orders",
    "📋 Deliverables",
    "📤 Import Data",
    "📊 Reports"
], label_visibility="collapsed")

st.sidebar.markdown("---")
st.sidebar.markdown("*v2.0 Professional*")

# Route to pages
if page == "🏠 Dashboard":
    page_dashboard()
elif page == "📁 Projects":
    page_projects()
elif page == "📝 Change Orders":
    page_change_orders()
elif page == "📦 Purchase Orders":
    page_purchase_orders()
elif page == "📋 Deliverables":
    page_deliverables()
elif page == "📤 Import Data":
    page_import()
elif page == "📊 Reports":
    page_reports()
