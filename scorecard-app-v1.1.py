"""
EPCM Project Scorecard - Version 1.3
Fixed version with:
- All column name consistency issues resolved
- CSV Import/Export for all data tables
- Enhanced report with S-curves and commentary
- TypeError fixes for plotly
- Proper weekly spend tracking

Author: Built with AI assistance
Version: 1.3 - Bug Fix & Enhancement Release
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import io
import base64

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="EPCM Project Scorecard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# HELPER FUNCTIONS - CALCULATIONS
# ============================================================================

def parse_time_to_hours(time_str: str) -> float:
    """Convert time string HH:MM:SS to decimal hours."""
    try:
        if pd.isna(time_str) or time_str == '':
            return 0.0
        if isinstance(time_str, (int, float)):
            return float(time_str)
        parts = str(time_str).split(':')
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
            return hours + (minutes / 60.0) + (seconds / 3600.0)
        elif len(parts) == 2:
            hours = int(parts[0])
            minutes = int(parts[1])
            return hours + (minutes / 60.0)
        else:
            return float(time_str)
    except:
        return 0.0

def calculate_week_ending(date_obj) -> datetime:
    """Calculate the next Saturday from given date."""
    if isinstance(date_obj, str):
        date_obj = pd.to_datetime(date_obj)
    days_until_saturday = (5 - date_obj.weekday()) % 7
    if days_until_saturday == 0:
        days_until_saturday = 7
    week_ending = date_obj + timedelta(days=days_until_saturday)
    return week_ending

def map_function(task_name: str) -> str:
    """Map task name to function category."""
    if pd.isna(task_name):
        return "ENGINEERING"
    task_upper = str(task_name).upper()
    if "PM" in task_upper or "MANAGEMENT" in task_upper:
        return "MANAGEMENT"
    elif "DF" in task_upper or "DRAFT" in task_upper or "3D" in task_upper:
        return "DRAFTING"
    else:
        return "ENGINEERING"

def lookup_rate_by_position(position: str, rates_df: pd.DataFrame) -> float:
    """Lookup billing rate by position from rate schedule."""
    if rates_df is None or rates_df.empty or pd.isna(position):
        return 170.0
    match = rates_df[rates_df['position'] == position]
    if not match.empty:
        return float(match.iloc[0]['rate'])
    return 170.0

def get_staff_rate(staff_name: str, staff_df: pd.DataFrame, rates_df: pd.DataFrame) -> float:
    """Get billing rate for staff member."""
    if staff_df is None or staff_df.empty:
        return 170.0
    match = staff_df[staff_df['name'] == staff_name]
    if not match.empty:
        position = match.iloc[0]['position']
        return lookup_rate_by_position(position, rates_df)
    return 170.0

def calculate_performance_factor(budget: float, actual: float) -> float:
    """Calculate performance factor (Budget/Actual)."""
    if actual > 0:
        return budget / actual
    return 1.0

def get_week_list(start_date, end_date, num_future_weeks=12):
    """Generate list of week ending dates."""
    weeks = []
    current = calculate_week_ending(pd.to_datetime(start_date))
    end = calculate_week_ending(pd.to_datetime(end_date))
    
    while current <= end:
        weeks.append(current)
        current = current + timedelta(days=7)
    
    for i in range(num_future_weeks):
        weeks.append(current)
        current = current + timedelta(days=7)
    
    return weeks

def calculate_earned_value(deliverables_df: pd.DataFrame) -> dict:
    """Calculate earned value from deliverables completion."""
    if deliverables_df is None or deliverables_df.empty:
        return {'earned_hours': 0, 'earned_cost': 0}
    
    deliverables_df['earned_hours'] = deliverables_df['budget_hours'] * deliverables_df['completion'] / 100.0
    
    earned_hours = deliverables_df['earned_hours'].sum()
    
    # Estimate earned cost based on function average rates
    total_earned_cost = 0
    for func in ['MANAGEMENT', 'ENGINEERING', 'DRAFTING']:
        # FIXED: Use lowercase 'function' consistently
        func_deliverables = deliverables_df[deliverables_df['function'] == func]
        if not func_deliverables.empty:
            func_earned_hours = func_deliverables['earned_hours'].sum()
            func_rate = {'MANAGEMENT': 245, 'ENGINEERING': 180, 'DRAFTING': 170}.get(func, 180)
            total_earned_cost += func_earned_hours * func_rate
    
    return {'earned_hours': earned_hours, 'earned_cost': total_earned_cost}

def create_download_link(df: pd.DataFrame, filename: str) -> str:
    """Create a download link for a dataframe as CSV."""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download {filename}</a>'
    return href

# ============================================================================
# DATA INITIALIZATION
# ============================================================================

def initialize_session_state():
    """Initialize session state variables."""
    
    if 'initialized' not in st.session_state:
        # Project Setup
        st.session_state.project_setup = {
            'client': '',
            'project_name': '',
            'project_type': 'EPCM',
            'start_date': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d'),
            'report_date': datetime.now().strftime('%Y-%m-%d'),
            'report_by': '',
            'currency': 'AUD',
            'budget_management': 50.0,
            'budget_engineering': 200.0,
            'budget_drafting': 100.0,
            'contract_value': 100000.0,
            'contingency_pct': 10.0
        }
        
        # Commentary sections
        st.session_state.commentary = {
            'key_activities': '',
            'next_period': '',
            'issues_risks': '',
            'general_notes': ''
        }
        
        # Staff Database - CONSISTENT LOWERCASE COLUMNS
        st.session_state.staff = pd.DataFrame({
            'name': ['Gavin Andersen', 'Mark Rankin', 'Ben Robinson', 'Will Smith', 'Ben Bowles'],
            'function': ['MANAGEMENT', 'DRAFTING', 'ENGINEERING', 'ENGINEERING', 'ENGINEERING'],
            'discipline': ['GN', 'GN', 'ME', 'ME', 'ME'],
            'position': ['Engineering Manager', 'Drawing Office Manager', 'Senior Engineer', 'Lead Engineer', 'Senior Engineer']
        })
        
        # Rate Schedule - CONSISTENT LOWERCASE COLUMNS
        st.session_state.rates = pd.DataFrame({
            'position': ['Engineering Manager', 'Lead Engineer', 'Senior Engineer', 'Drawing Office Manager', 
                        'Lead Designer', 'Senior Designer', 'Designer', 'Principal Engineer', 'Technical Reviewer'],
            'rate': [245, 195, 170, 195, 165, 150, 140, 210, 245]
        })
        
        # Deliverables List - CONSISTENT LOWERCASE COLUMNS
        st.session_state.deliverables = pd.DataFrame({
            'deliverable': ['Project Management Plan', 'Process Flow Diagrams', 'P&IDs - General Arrangement', 
                           'Equipment List', 'Piping Layout Drawings', 'Structural Design Drawings',
                           'Electrical Single Line Diagrams', 'I&C Architecture', 'Final Report'],
            'function': ['MANAGEMENT', 'ENGINEERING', 'ENGINEERING', 'ENGINEERING', 'DRAFTING', 
                        'DRAFTING', 'ENGINEERING', 'ENGINEERING', 'MANAGEMENT'],
            'discipline': ['GN', 'ME', 'ME', 'ME', 'GN', 'ST', 'EE', 'IC', 'GN'],
            'budget_hours': [20, 40, 60, 30, 80, 60, 40, 50, 20],
            'completion': [100, 80, 50, 60, 40, 20, 30, 10, 0],
            'status': ['Complete', 'In Progress', 'In Progress', 'In Progress', 'In Progress', 
                      'Started', 'Started', 'Started', 'Not Started']
        })
        
        st.session_state.timesheets = pd.DataFrame()
        st.session_state.weekly_forecasts = {}
        
        st.session_state.initialized = True

def load_sample_data():
    """Load sample timesheet data."""
    sample_data = [
        {'date': '2025-10-07', 'job_name': 'Tails Pump Assessment', 'staff_name': 'Gavin Andersen', 'task_name': 'PM - Management', 'time': '01:00:00'},
        {'date': '2025-10-08', 'job_name': 'Tails Pump Assessment', 'staff_name': 'Ben Robinson', 'task_name': 'EN - Mech Design', 'time': '04:00:00'},
        {'date': '2025-10-09', 'job_name': 'Tails Pump Assessment', 'staff_name': 'Ben Robinson', 'task_name': 'EN - Mech Design', 'time': '07:00:00'},
        {'date': '2025-10-09', 'job_name': 'Tails Pump Assessment', 'staff_name': 'Gavin Andersen', 'task_name': 'PM - Management', 'time': '01:00:00'},
        {'date': '2025-10-10', 'job_name': 'Tails Pump Assessment', 'staff_name': 'Ben Robinson', 'task_name': 'EN - Mech Design', 'time': '08:24:00'},
        {'date': '2025-10-13', 'job_name': 'Tails Pump Assessment', 'staff_name': 'Ben Robinson', 'task_name': 'EN - Mech Design', 'time': '08:00:00'},
        {'date': '2025-10-13', 'job_name': 'Tails Pump Assessment', 'staff_name': 'Will Smith', 'task_name': 'EN - Mech Design', 'time': '02:00:00'},
        {'date': '2025-10-14', 'job_name': 'Tails Pump Assessment', 'staff_name': 'Ben Robinson', 'task_name': 'EN - Mech Design', 'time': '08:00:00'},
        {'date': '2025-10-14', 'job_name': 'Tails Pump Assessment', 'staff_name': 'Will Smith', 'task_name': 'EN - Mech Design', 'time': '02:00:00'},
        {'date': '2025-10-14', 'job_name': 'Tails Pump Assessment', 'staff_name': 'Ben Bowles', 'task_name': 'EN - Variation', 'time': '04:30:00'},
        {'date': '2025-10-13', 'job_name': 'Tails Pump Assessment', 'staff_name': 'Mark Rankin', 'task_name': 'DF - Piping 3D', 'time': '02:00:00'},
        {'date': '2025-10-14', 'job_name': 'Tails Pump Assessment', 'staff_name': 'Mark Rankin', 'task_name': 'DF - Piping 3D', 'time': '02:00:00'},
        {'date': '2025-10-21', 'job_name': 'Tails Pump Assessment', 'staff_name': 'Ben Robinson', 'task_name': 'EN - Mech Design', 'time': '06:00:00'},
        {'date': '2025-10-22', 'job_name': 'Tails Pump Assessment', 'staff_name': 'Will Smith', 'task_name': 'EN - Mech Design', 'time': '08:00:00'},
        {'date': '2025-10-23', 'job_name': 'Tails Pump Assessment', 'staff_name': 'Mark Rankin', 'task_name': 'DF - Piping 3D', 'time': '04:00:00'},
    ]
    
    df = pd.DataFrame(sample_data)
    df['hours'] = df['time'].apply(parse_time_to_hours)
    df['week_ending'] = pd.to_datetime(df['date']).apply(calculate_week_ending)
    df['function'] = df['task_name'].apply(map_function)
    df['rate'] = df['staff_name'].apply(lambda x: get_staff_rate(x, st.session_state.staff, st.session_state.rates))
    df['cost'] = df['hours'] * df['rate']
    
    st.session_state.timesheets = df
    st.session_state.project_setup['client'] = 'Liontown'
    st.session_state.project_setup['project_name'] = 'Tails Pump Assessment'
    st.session_state.project_setup['report_by'] = 'Will Smith'
    st.session_state.project_setup['report_date'] = '2025-10-28'
    
    st.success("✅ Sample data loaded successfully!")

# ============================================================================
# PAGE: PROJECT SETUP
# ============================================================================

def page_project_setup():
    """Project setup and configuration page."""
    st.title("⚙️ Project Setup")
    st.markdown("Configure project parameters, dates, and budget allocations.")
    
    st.subheader("Project Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.session_state.project_setup['client'] = st.text_input(
            "Client Name", 
            st.session_state.project_setup['client'],
            help="Client or company name"
        )
        
        st.session_state.project_setup['project_name'] = st.text_input(
            "Project Name", 
            st.session_state.project_setup['project_name'],
            help="Full project name or code"
        )
        
        st.session_state.project_setup['project_type'] = st.selectbox(
            "Project Type",
            ['EPCM', 'Feasibility Study', 'Detailed Design', 'Construction Support', 'Operations Support'],
            index=0
        )
        
        st.session_state.project_setup['report_by'] = st.text_input(
            "Project Manager / Report By", 
            st.session_state.project_setup['report_by']
        )
    
    with col2:
        st.session_state.project_setup['start_date'] = st.date_input(
            "Project Start Date",
            pd.to_datetime(st.session_state.project_setup['start_date']),
            help="Actual or planned project start date"
        ).strftime('%Y-%m-%d')
        
        st.session_state.project_setup['end_date'] = st.date_input(
            "Project End Date",
            pd.to_datetime(st.session_state.project_setup['end_date']),
            help="Planned project completion date"
        ).strftime('%Y-%m-%d')
        
        st.session_state.project_setup['report_date'] = st.date_input(
            "Current Report Date",
            pd.to_datetime(st.session_state.project_setup['report_date']),
            help="Date for this progress report (splits actual vs forecast)"
        ).strftime('%Y-%m-%d')
        
        st.session_state.project_setup['currency'] = st.selectbox(
            "Currency",
            ['AUD', 'USD', 'EUR', 'GBP', 'CAD'],
            index=0
        )
    
    # Calculate project duration
    start = pd.to_datetime(st.session_state.project_setup['start_date'])
    end = pd.to_datetime(st.session_state.project_setup['end_date'])
    duration_days = (end - start).days
    duration_weeks = duration_days / 7
    
    st.info(f"📅 **Project Duration:** {duration_days} days ({duration_weeks:.1f} weeks)")
    
    st.divider()
    st.subheader("Budget Allocation")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.session_state.project_setup['budget_management'] = st.number_input(
            "Management Hours",
            value=st.session_state.project_setup['budget_management'],
            min_value=0.0,
            step=10.0,
            help="Total budgeted hours for project management"
        )
    
    with col2:
        st.session_state.project_setup['budget_engineering'] = st.number_input(
            "Engineering Hours",
            value=st.session_state.project_setup['budget_engineering'],
            min_value=0.0,
            step=10.0,
            help="Total budgeted hours for engineering"
        )
    
    with col3:
        st.session_state.project_setup['budget_drafting'] = st.number_input(
            "Drafting Hours",
            value=st.session_state.project_setup['budget_drafting'],
            min_value=0.0,
            step=10.0,
            help="Total budgeted hours for drafting/CAD"
        )
    
    with col4:
        total_budget = (st.session_state.project_setup['budget_management'] + 
                       st.session_state.project_setup['budget_engineering'] + 
                       st.session_state.project_setup['budget_drafting'])
        st.metric("Total Budget", f"{total_budget:.0f}h")
    
    st.divider()
    st.subheader("Financial Parameters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.session_state.project_setup['contract_value'] = st.number_input(
            f"Contract Value ({st.session_state.project_setup['currency']})",
            value=st.session_state.project_setup['contract_value'],
            min_value=0.0,
            step=10000.0,
            format="%.2f",
            help="Total contract value"
        )
    
    with col2:
        st.session_state.project_setup['contingency_pct'] = st.number_input(
            "Contingency (%)",
            value=st.session_state.project_setup['contingency_pct'],
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            help="Contingency percentage of budget"
        )
    
    # Calculate average rate
    if total_budget > 0:
        avg_rate = st.session_state.project_setup['contract_value'] / total_budget
        st.info(f"💰 **Average Rate:** {st.session_state.project_setup['currency']} ${avg_rate:.2f}/hour")
    
    st.divider()
    
    if st.button("💾 Save Project Setup", type="primary"):
        st.success("✅ Project setup saved successfully!")

# ============================================================================
# PAGE: DATA MANAGEMENT (NEW - CSV IMPORT/EXPORT)
# ============================================================================

def page_data_management():
    """Data management page for CSV import/export."""
    st.title("💾 Data Management")
    st.markdown("Import and export data tables as CSV files for bulk updates.")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Staff Database", "💰 Rate Schedule", "📋 Deliverables", "📅 Forecasts"])
    
    # TAB 1: STAFF
    with tab1:
        st.subheader("Staff Database")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📥 Import Staff CSV")
            uploaded_staff = st.file_uploader("Upload Staff CSV", type=['csv'], key='upload_staff')
            
            if uploaded_staff:
                try:
                    df_staff = pd.read_csv(uploaded_staff)
                    st.dataframe(df_staff)
                    
                    if st.button("✅ Import Staff Data"):
                        st.session_state.staff = df_staff
                        st.success("Staff data imported!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        
        with col2:
            st.markdown("### 📤 Export Staff CSV")
            st.dataframe(st.session_state.staff)
            
            csv_staff = st.session_state.staff.to_csv(index=False)
            st.download_button(
                label="📥 Download Staff CSV",
                data=csv_staff,
                file_name=f"staff_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    # TAB 2: RATES
    with tab2:
        st.subheader("Rate Schedule")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📥 Import Rates CSV")
            uploaded_rates = st.file_uploader("Upload Rates CSV", type=['csv'], key='upload_rates')
            
            if uploaded_rates:
                try:
                    df_rates = pd.read_csv(uploaded_rates)
                    st.dataframe(df_rates)
                    
                    if st.button("✅ Import Rates Data"):
                        st.session_state.rates = df_rates
                        st.success("Rates data imported!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        
        with col2:
            st.markdown("### 📤 Export Rates CSV")
            st.dataframe(st.session_state.rates)
            
            csv_rates = st.session_state.rates.to_csv(index=False)
            st.download_button(
                label="📥 Download Rates CSV",
                data=csv_rates,
                file_name=f"rates_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    # TAB 3: DELIVERABLES
    with tab3:
        st.subheader("Deliverables List")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📥 Import Deliverables CSV")
            uploaded_deliv = st.file_uploader("Upload Deliverables CSV", type=['csv'], key='upload_deliv')
            
            if uploaded_deliv:
                try:
                    df_deliv = pd.read_csv(uploaded_deliv)
                    st.dataframe(df_deliv)
                    
                    if st.button("✅ Import Deliverables Data"):
                        st.session_state.deliverables = df_deliv
                        st.success("Deliverables data imported!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        
        with col2:
            st.markdown("### 📤 Export Deliverables CSV")
            st.dataframe(st.session_state.deliverables)
            
            csv_deliv = st.session_state.deliverables.to_csv(index=False)
            st.download_button(
                label="📥 Download Deliverables CSV",
                data=csv_deliv,
                file_name=f"deliverables_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    # TAB 4: FORECASTS
    with tab4:
        st.subheader("Weekly Forecasts")
        
        # Convert forecasts dict to dataframe
        if st.session_state.weekly_forecasts:
            forecast_data = []
            for (person, week_str), hours in st.session_state.weekly_forecasts.items():
                forecast_data.append({'person': person, 'week_ending': week_str, 'forecast_hours': hours})
            df_forecasts = pd.DataFrame(forecast_data)
        else:
            df_forecasts = pd.DataFrame(columns=['person', 'week_ending', 'forecast_hours'])
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📥 Import Forecasts CSV")
            st.info("CSV should have columns: person, week_ending, forecast_hours")
            uploaded_forecast = st.file_uploader("Upload Forecasts CSV", type=['csv'], key='upload_forecast')
            
            if uploaded_forecast:
                try:
                    df_forecast_upload = pd.read_csv(uploaded_forecast)
                    st.dataframe(df_forecast_upload)
                    
                    if st.button("✅ Import Forecast Data"):
                        # Convert back to dict
                        new_forecasts = {}
                        for _, row in df_forecast_upload.iterrows():
                            key = (row['person'], row['week_ending'])
                            new_forecasts[key] = row['forecast_hours']
                        st.session_state.weekly_forecasts = new_forecasts
                        st.success("Forecast data imported!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        
        with col2:
            st.markdown("### 📤 Export Forecasts CSV")
            st.dataframe(df_forecasts)
            
            if not df_forecasts.empty:
                csv_forecast = df_forecasts.to_csv(index=False)
                st.download_button(
                    label="📥 Download Forecasts CSV",
                    data=csv_forecast,
                    file_name=f"forecasts_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No forecast data to export yet.")

# ============================================================================
# PAGE: DELIVERABLES (FIXED)
# ============================================================================

def page_deliverables():
    """Deliverables management with earned value tracking."""
    st.title("📋 Deliverables List")
    st.markdown("Manage project deliverables and track completion for earned value calculation.")
    
    # Display current earned value
    ev_data = calculate_earned_value(st.session_state.deliverables)
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_budget_hours = st.session_state.deliverables['budget_hours'].sum()
    avg_completion = st.session_state.deliverables['completion'].mean()
    
    with col1:
        st.metric("Total Budget Hours", f"{total_budget_hours:.0f}h")
    with col2:
        st.metric("Earned Hours", f"{ev_data['earned_hours']:.1f}h")
    with col3:
        st.metric("Avg Completion", f"{avg_completion:.1f}%")
    with col4:
        st.metric("Earned Value", f"${ev_data['earned_cost']:,.0f}")
    
    st.divider()
    st.subheader("Deliverables Editor")
    
    # Editable deliverables table
    edited_deliverables = st.data_editor(
        st.session_state.deliverables,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "deliverable": st.column_config.TextColumn("Deliverable Name", width="large", required=True),
            "function": st.column_config.SelectboxColumn("Function", 
                options=["MANAGEMENT", "ENGINEERING", "DRAFTING"], required=True),
            "discipline": st.column_config.TextColumn("Discipline", width="small"),
            "budget_hours": st.column_config.NumberColumn("Budget Hours", format="%.1f", min_value=0, required=True),
            "completion": st.column_config.NumberColumn("% Complete", format="%.0f", min_value=0, max_value=100, required=True),
            "status": st.column_config.SelectboxColumn("Status",
                options=["Not Started", "Started", "In Progress", "Review", "Complete"], required=True)
        },
        hide_index=True
    )
    
    if st.button("💾 Save Deliverables", type="primary"):
        st.session_state.deliverables = edited_deliverables
        st.success("✅ Deliverables saved!")
        st.rerun()
    
    st.divider()
    st.subheader("Deliverables by Function")
    
    # Group by function - FIXED: Use lowercase 'function'
    by_function = edited_deliverables.groupby('function').agg({
        'budget_hours': 'sum',
        'completion': 'mean'
    }).reset_index()
    
    col1, col2, col3 = st.columns(3)
    
    for i, (col, func) in enumerate(zip([col1, col2, col3], ['MANAGEMENT', 'ENGINEERING', 'DRAFTING'])):
        func_data = by_function[by_function['function'] == func]
        if not func_data.empty:
            with col:
                st.markdown(f"**{func}**")
                st.metric("Budget Hours", f"{func_data['budget_hours'].iloc[0]:.0f}h")
                st.metric("Avg Completion", f"{func_data['completion'].iloc[0]:.1f}%")
    
    # Completion chart
    st.subheader("Deliverables Progress")
    
    fig = go.Figure()
    
    for func in ['MANAGEMENT', 'ENGINEERING', 'DRAFTING']:
        func_deliv = edited_deliverables[edited_deliverables['function'] == func]
        if not func_deliv.empty:
            fig.add_trace(go.Bar(
                name=func,
                x=func_deliv['deliverable'],
                y=func_deliv['completion'],
                text=func_deliv['completion'].apply(lambda x: f"{x:.0f}%"),
                textposition='outside'
            ))
    
    fig.update_layout(
        title="Deliverable Completion by Function",
        xaxis_title="Deliverable",
        yaxis_title="% Complete",
        yaxis_range=[0, 110],
        barmode='group',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# PAGE: S-CURVES (FIXED)
# ============================================================================

def page_s_curves():
    """S-Curve visualization for project progress."""
    st.title("📈 S-Curves - Progress Tracking")
    st.markdown("Visual representation of Budget, Actual, Earned, and Forecast progress over time.")
    
    if st.session_state.timesheets.empty:
        st.warning("⚠️ No timesheet data loaded. S-curves require actual timesheet data.")
        if st.button("🎯 Load Sample Data"):
            load_sample_data()
            st.rerun()
        return
    
    df = st.session_state.timesheets
    start_date = pd.to_datetime(st.session_state.project_setup['start_date'])
    end_date = pd.to_datetime(st.session_state.project_setup['end_date'])
    report_date = pd.to_datetime(st.session_state.project_setup['report_date'])
    
    # Get week list
    weeks = get_week_list(start_date, end_date, num_future_weeks=8)
    
    # Calculate cumulative values by week
    budget_mgmt = st.session_state.project_setup['budget_management']
    budget_eng = st.session_state.project_setup['budget_engineering']
    budget_draft = st.session_state.project_setup['budget_drafting']
    total_budget = budget_mgmt + budget_eng + budget_draft
    
    # Planned budget (linear S-curve)
    total_weeks = len([w for w in weeks if w <= end_date])
    budget_curve = []
    actual_curve = []
    earned_curve = []
    forecast_curve = []
    
    for i, week in enumerate(weeks):
        # Budget (planned - linear distribution)
        if week <= end_date:
            week_num = len([w for w in weeks[:i+1] if w <= end_date])
            budget_cum = (week_num / total_weeks) * total_budget if total_weeks > 0 else 0
        else:
            budget_cum = total_budget
        budget_curve.append(budget_cum)
        
        # Actual (from timesheets)
        if week <= report_date:
            actual = df[df['week_ending'] <= week]['hours'].sum()
        else:
            actual = df['hours'].sum()
        actual_curve.append(actual)
        
        # Earned value (from deliverables completion)
        ev_data = calculate_earned_value(st.session_state.deliverables)
        if week <= report_date:
            actual_to_date = df['hours'].sum()
            if total_budget > 0:
                progress_pct = min(actual_to_date / total_budget, 1.0)
                earned = ev_data['earned_hours'] * progress_pct
            else:
                earned = 0
        else:
            earned = ev_data['earned_hours']
        earned_curve.append(earned)
        
        # Forecast
        if week <= report_date:
            forecast = actual
        else:
            forecast_hours = sum([hrs for (person, week_str), hrs in st.session_state.weekly_forecasts.items() 
                                if pd.to_datetime(week_str) <= week])
            forecast = df['hours'].sum() + forecast_hours
        forecast_curve.append(min(forecast, total_budget * 1.2))
    
    # Create S-curve chart - FIXED: Convert datetime to string for plotly
    fig = go.Figure()
    
    week_labels = [w.strftime('%Y-%m-%d') for w in weeks]
    
    fig.add_trace(go.Scatter(
        x=week_labels,
        y=budget_curve,
        mode='lines',
        name='Budget (Planned)',
        line=dict(color='blue', width=2, dash='dash')
    ))
    
    fig.add_trace(go.Scatter(
        x=week_labels,
        y=actual_curve,
        mode='lines+markers',
        name='Actual',
        line=dict(color='red', width=3),
        marker=dict(size=6)
    ))
    
    fig.add_trace(go.Scatter(
        x=week_labels,
        y=earned_curve,
        mode='lines+markers',
        name='Earned Value',
        line=dict(color='green', width=3),
        marker=dict(size=6)
    ))
    
    fig.add_trace(go.Scatter(
        x=week_labels,
        y=forecast_curve,
        mode='lines',
        name='Forecast',
        line=dict(color='orange', width=2, dash='dot')
    ))
    
    # Add report date line - FIXED: Use string format consistently
    fig.add_vline(
        x=report_date.strftime('%Y-%m-%d'),
        line_dash="solid",
        line_color="gray",
        annotation_text="Report Date",
        annotation_position="top"
    )
    
    fig.update_layout(
        title="Project S-Curve - Cumulative Hours",
        xaxis_title="Week Ending",
        yaxis_title="Cumulative Hours",
        height=500,
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Variance Analysis
    st.divider()
    st.subheader("Variance Analysis")
    
    col1, col2, col3, col4 = st.columns(4)
    
    current_actual = df['hours'].sum()
    current_earned = ev_data['earned_hours']
    
    # Find budget at report date
    report_week_idx = None
    for i, week in enumerate(weeks):
        if week >= report_date:
            report_week_idx = i
            break
    
    current_budget = budget_curve[report_week_idx] if report_week_idx is not None else total_budget
    
    schedule_variance = current_earned - current_budget
    cost_variance = current_earned - current_actual
    
    with col1:
        st.metric("Budget to Date", f"{current_budget:.0f}h")
    with col2:
        st.metric("Actual to Date", f"{current_actual:.0f}h")
    with col3:
        st.metric("Schedule Variance", f"{schedule_variance:+.0f}h", 
                 delta=f"{schedule_variance:+.0f}h",
                 delta_color="normal" if schedule_variance >= 0 else "inverse")
    with col4:
        st.metric("Cost Variance", f"{cost_variance:+.0f}h",
                 delta=f"{cost_variance:+.0f}h",
                 delta_color="normal" if cost_variance >= 0 else "inverse")
    
    # Performance indices
    spi = current_earned / current_budget if current_budget > 0 else 1.0
    cpi = current_earned / current_actual if current_actual > 0 else 1.0
    
    st.info(f"""
    **Performance Indices:**
    - **Schedule Performance Index (SPI):** {spi:.2f} {'✅ Ahead of schedule' if spi > 1.0 else '⚠️ Behind schedule'}
    - **Cost Performance Index (CPI):** {cpi:.2f} {'✅ Under budget' if cpi > 1.0 else '⚠️ Over budget'}
    """)

# ============================================================================
# PAGE: DASHBOARD
# ============================================================================

def page_dashboard():
    """Main dashboard with project overview."""
    st.title("📊 Project Dashboard")
    
    # Project header
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Client:** {st.session_state.project_setup['client']}")
        st.markdown(f"**Project:** {st.session_state.project_setup['project_name']}")
    with col2:
        st.markdown(f"**Type:** {st.session_state.project_setup['project_type']}")
        st.markdown(f"**PM:** {st.session_state.project_setup['report_by']}")
    with col3:
        st.markdown(f"**Report Date:** {st.session_state.project_setup['report_date']}")
        start = pd.to_datetime(st.session_state.project_setup['start_date'])
        end = pd.to_datetime(st.session_state.project_setup['end_date'])
        st.markdown(f"**Duration:** {(end-start).days} days")
    
    st.divider()
    
    if not st.session_state.timesheets.empty:
        df = st.session_state.timesheets
        
        total_actual_hours = df['hours'].sum()
        total_actual_cost = df['cost'].sum()
        
        by_function = df.groupby('function').agg({'hours': 'sum', 'cost': 'sum'}).reset_index()
        
        budget_mgmt = st.session_state.project_setup['budget_management']
        budget_eng = st.session_state.project_setup['budget_engineering']
        budget_draft = st.session_state.project_setup['budget_drafting']
        total_budget = budget_mgmt + budget_eng + budget_draft
        
        ev_data = calculate_earned_value(st.session_state.deliverables)
        pf = calculate_performance_factor(total_budget, total_actual_hours)
        
        st.subheader("Key Metrics")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Budget", f"{total_budget:.0f}h")
        with col2:
            variance = total_actual_hours - total_budget
            st.metric("Actual", f"{total_actual_hours:.0f}h", f"{variance:+.0f}h", delta_color="inverse")
        with col3:
            st.metric("Earned Value", f"{ev_data['earned_hours']:.0f}h")
        with col4:
            st.metric("Actual Cost", f"${total_actual_cost:,.0f}")
        with col5:
            st.metric("Performance Factor", f"{pf:.2f}")
        
        # Function breakdown
        st.subheader("Hours by Function")
        
        mgmt_actual = by_function[by_function['function'] == 'MANAGEMENT']['hours'].sum() if 'MANAGEMENT' in by_function['function'].values else 0
        eng_actual = by_function[by_function['function'] == 'ENGINEERING']['hours'].sum() if 'ENGINEERING' in by_function['function'].values else 0
        draft_actual = by_function[by_function['function'] == 'DRAFTING']['hours'].sum() if 'DRAFTING' in by_function['function'].values else 0
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Management", f"{mgmt_actual:.1f}h", f"of {budget_mgmt:.0f}h")
        with col2:
            st.metric("Engineering", f"{eng_actual:.1f}h", f"of {budget_eng:.0f}h")
        with col3:
            st.metric("Drafting", f"{draft_actual:.1f}h", f"of {budget_draft:.0f}h")
        
        # Chart
        st.subheader("Budget vs Actual Comparison")
        chart_data = pd.DataFrame({
            'Function': ['Management', 'Engineering', 'Drafting'],
            'Budget': [budget_mgmt, budget_eng, budget_draft],
            'Actual': [mgmt_actual, eng_actual, draft_actual]
        })
        st.bar_chart(chart_data.set_index('Function'))
        
    else:
        st.info("👈 No data loaded. Go to **Data Import** or click below to load sample data.")
        if st.button("🎯 Load Sample Data", type="primary"):
            load_sample_data()
            st.rerun()

# ============================================================================
# PAGE: DATA IMPORT
# ============================================================================

def page_data_import():
    """Data import page."""
    st.title("📤 Data Import")
    
    st.markdown("""
    Upload your Workflow Max timesheet export (CSV format) or load sample data.
    
    **Expected columns:** `[Time] Date`, `[Job] Name`, `[Staff] Name`, `[Job Task] Name`, `[Time] Time`, `[Time] Billable`
    """)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader("Choose a CSV file", type=['csv'])
        
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                st.success(f"✅ File uploaded: {uploaded_file.name}")
                st.write(f"**Rows:** {len(df)} | **Columns:** {len(df.columns)}")
                
                with st.expander("🔍 Preview Raw Data", expanded=True):
                    st.dataframe(df.head(10), use_container_width=True)
                
                if st.button("✨ Process and Import Data", type="primary"):
                    column_mapping = {
                        '[Time] Date': 'date',
                        '[Job] Name': 'job_name',
                        '[Staff] Name': 'staff_name',
                        '[Job Task] Name': 'task_name',
                        '[Job Task] Label': 'task_label',
                        '[Time] Time': 'time',
                        '[Time] Billable': 'billable'
                    }
                    
                    df_processed = df.rename(columns=column_mapping)
                    df_processed['hours'] = df_processed['time'].apply(parse_time_to_hours)
                    df_processed['date'] = pd.to_datetime(df_processed['date'])
                    df_processed['week_ending'] = df_processed['date'].apply(calculate_week_ending)
                    df_processed['function'] = df_processed['task_name'].apply(map_function)
                    df_processed['rate'] = df_processed['staff_name'].apply(lambda x: get_staff_rate(x, st.session_state.staff, st.session_state.rates))
                    df_processed['cost'] = df_processed['hours'] * df_processed['rate']
                    
                    st.session_state.timesheets = df_processed
                    st.success(f"✅ Successfully imported {len(df_processed)} entries!")
                    
                    with st.expander("📊 Processed Data Preview", expanded=True):
                        display_cols = ['date', 'staff_name', 'task_name', 'hours', 'function', 'rate', 'cost', 'week_ending']
                        st.dataframe(df_processed[display_cols].head(10), use_container_width=True)
                    
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    with col2:
        st.markdown("### Quick Start")
        if st.button("🎯 Load Sample Data", type="secondary"):
            load_sample_data()
            st.rerun()
        
        st.markdown("---")
        st.markdown("### Current Data")
        if not st.session_state.timesheets.empty:
            df = st.session_state.timesheets
            st.metric("Total Entries", len(df))
            st.metric("Total Hours", f"{df['hours'].sum():.1f}h")
        else:
            st.warning("No data loaded")

# ============================================================================
# PAGE: MASTER DATA
# ============================================================================

def page_master_data():
    """Master data management."""
    st.title("👥 Master Data Management")
    
    st.subheader("📋 Rate Schedule")
    
    rates_df = st.data_editor(
        st.session_state.rates,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "position": st.column_config.TextColumn("Position Title", required=True),
            "rate": st.column_config.NumberColumn("Hourly Rate ($/hr)", format="$%.0f", required=True)
        }
    )
    
    if st.button("💾 Save Rates", key="save_rates"):
        st.session_state.rates = rates_df
        st.success("✅ Rate schedule updated!")
        st.rerun()
    
    st.divider()
    st.subheader("👤 Staff Database")
    
    staff_display = st.session_state.staff.copy()
    staff_display['current_rate'] = staff_display['position'].apply(lambda x: lookup_rate_by_position(x, st.session_state.rates))
    
    staff_df = st.data_editor(
        staff_display,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "name": st.column_config.TextColumn("Name", required=True),
            "function": st.column_config.SelectboxColumn("Function", options=["MANAGEMENT", "ENGINEERING", "DRAFTING"], required=True),
            "discipline": st.column_config.TextColumn("Discipline"),
            "position": st.column_config.SelectboxColumn("Position", options=st.session_state.rates['position'].tolist(), required=True),
            "current_rate": st.column_config.NumberColumn("Rate ($/hr)", format="$%.0f", disabled=True)
        }
    )
    
    if st.button("💾 Save Staff", key="save_staff"):
        staff_to_save = staff_df[['name', 'function', 'discipline', 'position']].copy()
        st.session_state.staff = staff_to_save
        st.success("✅ Staff database updated!")
        st.rerun()

# ============================================================================
# PAGE: MANNING VIEW
# ============================================================================

def page_manning():
    """Manning view with weekly grid."""
    st.title("📅 Manning View - Weekly Resource Allocation")
    
    if st.session_state.timesheets.empty:
        st.warning("⚠️ No timesheet data loaded.")
        return
    
    df = st.session_state.timesheets
    report_date = pd.to_datetime(st.session_state.project_setup['report_date'])
    
    all_staff = sorted(df['staff_name'].unique())
    min_date = df['date'].min()
    max_date = df['date'].max()
    
    weeks = get_week_list(min_date, report_date, num_future_weeks=12)
    
    st.info(f"📅 **Report Date:** {report_date.strftime('%Y-%m-%d')} | Before = Actual | After = Forecast (editable)")
    
    actual_by_week = df.groupby(['staff_name', 'week_ending'])['hours'].sum().reset_index()
    
    manning_rows = []
    
    for person in all_staff:
        row = {'Personnel': person}
        
        person_info = st.session_state.staff[st.session_state.staff['name'] == person]
        if not person_info.empty:
            row['Position'] = person_info.iloc[0]['position']
            row['Function'] = person_info.iloc[0]['function']
            row['Rate'] = get_staff_rate(person, st.session_state.staff, st.session_state.rates)
        else:
            row['Position'] = 'Unknown'
            row['Function'] = 'ENGINEERING'
            row['Rate'] = 170.0
        
        total_actual = 0
        total_forecast = 0
        
        for week in weeks:
            week_key = f"Week_{week.strftime('%Y-%m-%d')}"
            
            if week <= report_date:
                actual = actual_by_week[(actual_by_week['staff_name'] == person) & (actual_by_week['week_ending'] == week)]['hours'].sum()
                row[week_key] = actual
                total_actual += actual
            else:
                forecast_key = (person, week.strftime('%Y-%m-%d'))
                forecast = st.session_state.weekly_forecasts.get(forecast_key, 0.0)
                row[week_key] = forecast
                total_forecast += forecast
        
        row['Total Actual'] = total_actual
        row['Total Forecast'] = total_forecast
        row['Total Hours'] = total_actual + total_forecast
        row['Total Cost'] = row['Total Hours'] * row['Rate']
        
        manning_rows.append(row)
    
    manning_df = pd.DataFrame(manning_rows)
    
    col1, col2 = st.columns(2)
    with col1:
        show_weeks = st.slider("Weeks to display", 4, len(weeks), min(12, len(weeks)))
    with col2:
        filter_function = st.selectbox("Filter by Function", ["All", "MANAGEMENT", "ENGINEERING", "DRAFTING"])
    
    if filter_function != "All":
        manning_df = manning_df[manning_df['Function'] == filter_function]
    
    weeks_to_show = weeks[:show_weeks]
    week_columns = [f"Week_{w.strftime('%Y-%m-%d')}" for w in weeks_to_show]
    display_columns = ['Personnel', 'Position', 'Function', 'Rate'] + week_columns + ['Total Actual', 'Total Forecast', 'Total Hours', 'Total Cost']
    
    column_config = {
        "Personnel": st.column_config.TextColumn("Personnel", disabled=True),
        "Position": st.column_config.TextColumn("Position", disabled=True),
        "Function": st.column_config.TextColumn("Function", disabled=True),
        "Rate": st.column_config.NumberColumn("Rate", format="$%.0f", disabled=True),
        "Total Actual": st.column_config.NumberColumn("Σ Actual", format="%.1f", disabled=True),
        "Total Forecast": st.column_config.NumberColumn("Σ Forecast", format="%.1f", disabled=True),
        "Total Hours": st.column_config.NumberColumn("Σ Total", format="%.1f", disabled=True),
        "Total Cost": st.column_config.NumberColumn("Σ Cost", format="$%,.0f", disabled=True)
    }
    
    for week in weeks_to_show:
        week_key = f"Week_{week.strftime('%Y-%m-%d')}"
        is_past = week <= report_date
        
        column_config[week_key] = st.column_config.NumberColumn(
            week.strftime('%m/%d'),
            format="%.1f",
            disabled=is_past
        )
    
    edited_df = st.data_editor(
        manning_df[display_columns],
        use_container_width=True,
        column_config=column_config,
        hide_index=True,
        height=600
    )
    
    for idx, row in edited_df.iterrows():
        person = row['Personnel']
        for week in weeks_to_show:
            if week > report_date:
                week_key = f"Week_{week.strftime('%Y-%m-%d')}"
                if week_key in row:
                    forecast_key = (person, week.strftime('%Y-%m-%d'))
                    st.session_state.weekly_forecasts[forecast_key] = row[week_key] if not pd.isna(row[week_key]) else 0.0

# ============================================================================
# PAGE: REPORT (ENHANCED)
# ============================================================================

def page_report():
    """Enhanced report generator with S-curve and commentary."""
    st.title("📈 Project Report")
    
    if st.session_state.timesheets.empty:
        st.warning("⚠️ No data loaded.")
        return
    
    df = st.session_state.timesheets
    
    # Report Header
    st.markdown(f"""
    ### Weekly Progress Report
    **Client:** {st.session_state.project_setup['client']}  
    **Project:** {st.session_state.project_setup['project_name']}  
    **Report Date:** {st.session_state.project_setup['report_date']}  
    **Report By:** {st.session_state.project_setup['report_by']}
    """)
    
    st.divider()
    
    # Performance Summary
    by_function = df.groupby('function').agg({'hours': 'sum', 'cost': 'sum'}).reset_index()
    
    mgmt_actual = by_function[by_function['function'] == 'MANAGEMENT']['hours'].sum() if 'MANAGEMENT' in by_function['function'].values else 0
    eng_actual = by_function[by_function['function'] == 'ENGINEERING']['hours'].sum() if 'ENGINEERING' in by_function['function'].values else 0
    draft_actual = by_function[by_function['function'] == 'DRAFTING']['hours'].sum() if 'DRAFTING' in by_function['function'].values else 0
    total_actual = mgmt_actual + eng_actual + draft_actual
    
    total_budget = (st.session_state.project_setup['budget_management'] + 
                   st.session_state.project_setup['budget_engineering'] + 
                   st.session_state.project_setup['budget_drafting'])
    
    ev_data = calculate_earned_value(st.session_state.deliverables)
    pf = calculate_performance_factor(total_budget, total_actual)
    
    st.subheader("Performance Summary")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Budget", f"{total_budget:.0f}h")
    with col2:
        st.metric("Actual", f"{total_actual:.0f}h")
    with col3:
        st.metric("Earned Value", f"{ev_data['earned_hours']:.0f}h")
    with col4:
        st.metric("Performance Factor", f"{pf:.2f}")
    with col5:
        completion = (ev_data['earned_hours'] / total_budget * 100) if total_budget > 0 else 0
        st.metric("% Complete", f"{completion:.1f}%")
    
    # Weekly Spend Table
    st.divider()
    st.subheader("Weekly Spend Summary")
    
    weekly_spend = df.groupby('week_ending').agg({'hours': 'sum', 'cost': 'sum'}).reset_index()
    weekly_spend['week_ending'] = weekly_spend['week_ending'].dt.strftime('%Y-%m-%d')
    weekly_spend = weekly_spend.sort_values('week_ending')
    weekly_spend.columns = ['Week Ending', 'Hours', 'Cost']
    
    st.dataframe(
        weekly_spend,
        use_container_width=True,
        column_config={
            "Week Ending": st.column_config.TextColumn("Week Ending"),
            "Hours": st.column_config.NumberColumn("Hours", format="%.1f"),
            "Cost": st.column_config.NumberColumn("Cost", format="$%,.0f")
        },
        hide_index=True
    )
    
    # S-Curve in Report
    st.divider()
    st.subheader("Progress S-Curve")
    
    # Generate S-curve (simplified version)
    start_date = pd.to_datetime(st.session_state.project_setup['start_date'])
    end_date = pd.to_datetime(st.session_state.project_setup['end_date'])
    report_date = pd.to_datetime(st.session_state.project_setup['report_date'])
    
    weeks = get_week_list(start_date, end_date, num_future_weeks=4)
    week_labels = [w.strftime('%m/%d') for w in weeks]
    
    # Simplified curves for report
    total_weeks = len([w for w in weeks if w <= end_date])
    budget_curve = []
    actual_curve = []
    
    for i, week in enumerate(weeks):
        if week <= end_date:
            week_num = len([w for w in weeks[:i+1] if w <= end_date])
            budget_cum = (week_num / total_weeks) * total_budget if total_weeks > 0 else 0
        else:
            budget_cum = total_budget
        budget_curve.append(budget_cum)
        
        if week <= report_date:
            actual = df[df['week_ending'] <= week]['hours'].sum()
        else:
            actual = df['hours'].sum()
        actual_curve.append(actual)
    
    fig_report = go.Figure()
    
    fig_report.add_trace(go.Scatter(
        x=week_labels,
        y=budget_curve,
        mode='lines',
        name='Budget',
        line=dict(color='blue', width=2, dash='dash')
    ))
    
    fig_report.add_trace(go.Scatter(
        x=week_labels,
        y=actual_curve,
        mode='lines+markers',
        name='Actual',
        line=dict(color='red', width=2),
        marker=dict(size=4)
    ))
    
    fig_report.update_layout(
        title="Cumulative Hours Progress",
        xaxis_title="Week",
        yaxis_title="Hours",
        height=350,
        showlegend=True,
        legend=dict(orientation="h", y=1.1)
    )
    
    st.plotly_chart(fig_report, use_container_width=True)
    
    # Commentary Sections
    st.divider()
    st.subheader("Project Commentary")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.session_state.commentary['key_activities'] = st.text_area(
            "Key Activities This Period",
            value=st.session_state.commentary['key_activities'],
            height=150,
            placeholder="Summarize major work completed this period..."
        )
        
        st.session_state.commentary['issues_risks'] = st.text_area(
            "Issues & Risks",
            value=st.session_state.commentary['issues_risks'],
            height=150,
            placeholder="Note any issues, risks, or concerns..."
        )
    
    with col2:
        st.session_state.commentary['next_period'] = st.text_area(
            "Planned Activities Next Period",
            value=st.session_state.commentary['next_period'],
            height=150,
            placeholder="Outline planned work for next period..."
        )
        
        st.session_state.commentary['general_notes'] = st.text_area(
            "General Notes",
            value=st.session_state.commentary['general_notes'],
            height=150,
            placeholder="Any additional notes or comments..."
        )
    
    # Export
    st.divider()
    st.subheader("Export Report")
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Summary sheet
        summary_data = pd.DataFrame({
            'Metric': ['Client', 'Project', 'Report Date', 'Budget', 'Actual', 'Earned', 'Performance Factor', '% Complete'],
            'Value': [
                st.session_state.project_setup['client'],
                st.session_state.project_setup['project_name'],
                st.session_state.project_setup['report_date'],
                total_budget,
                total_actual,
                ev_data['earned_hours'],
                pf,
                completion
            ]
        })
        summary_data.to_excel(writer, sheet_name='Summary', index=False)
        
        # Weekly spend
        weekly_spend.to_excel(writer, sheet_name='Weekly Spend', index=False)
        
        # Commentary
        commentary_data = pd.DataFrame({
            'Section': ['Key Activities', 'Next Period', 'Issues & Risks', 'General Notes'],
            'Content': [
                st.session_state.commentary['key_activities'],
                st.session_state.commentary['next_period'],
                st.session_state.commentary['issues_risks'],
                st.session_state.commentary['general_notes']
            ]
        })
        commentary_data.to_excel(writer, sheet_name='Commentary', index=False)
        
        # Data sheets
        df.to_excel(writer, sheet_name='Timesheets', index=False)
        st.session_state.deliverables.to_excel(writer, sheet_name='Deliverables', index=False)
    
    st.download_button(
        label="📥 Download Complete Report (Excel)",
        data=output.getvalue(),
        file_name=f"Project_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application."""
    initialize_session_state()
    
    st.sidebar.title("📊 Project Scorecard")
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio(
        "Navigation",
        ["⚙️ Project Setup", "🏠 Dashboard", "📤 Data Import", "💾 Data Management", "👥 Master Data", 
         "📋 Deliverables", "📅 Manning View", "📈 S-Curves", "📊 Report"],
        label_visibility="collapsed"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Quick Actions")
    
    if st.sidebar.button("🎯 Load Sample Data"):
        load_sample_data()
        st.rerun()
    
    if st.sidebar.button("🗑️ Clear All Data"):
        st.session_state.timesheets = pd.DataFrame()
        st.session_state.weekly_forecasts = {}
        st.success("Cleared!")
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("*EPCM Scorecard v1.3*")
    st.sidebar.markdown("✨ *Bug Fixes & Enhancements*")
    
    if page == "⚙️ Project Setup":
        page_project_setup()
    elif page == "🏠 Dashboard":
        page_dashboard()
    elif page == "📤 Data Import":
        page_data_import()
    elif page == "💾 Data Management":
        page_data_management()
    elif page == "👥 Master Data":
        page_master_data()
    elif page == "📋 Deliverables":
        page_deliverables()
    elif page == "📅 Manning View":
        page_manning()
    elif page == "📈 S-Curves":
        page_s_curves()
    elif page == "📊 Report":
        page_report()

if __name__ == "__main__":
    main()
