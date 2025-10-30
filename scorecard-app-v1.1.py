"""
EPCM Project Scorecard MVP - Version 1.1
Enhanced with:
- Staff rates lookup from Rate Schedule
- Weekly manning grid with actual and forecast hours per week
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io

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
    match = rates_df[rates_df['Position'] == position]
    if not match.empty:
        return float(match.iloc[0]['Rate'])
    return 170.0

def get_staff_rate(staff_name: str, staff_df: pd.DataFrame, rates_df: pd.DataFrame) -> float:
    """Get billing rate for staff member by looking up their position in rate schedule."""
    if staff_df is None or staff_df.empty:
        return 170.0
    match = staff_df[staff_df['Name'] == staff_name]
    if not match.empty:
        position = match.iloc[0]['Position']
        return lookup_rate_by_position(position, rates_df)
    return 170.0

def calculate_performance_factor(budget: float, actual: float) -> float:
    """Calculate performance factor (Budget/Actual)."""
    if actual > 0:
        return budget / actual
    return 1.0

def get_week_list(start_date, end_date, num_future_weeks=12):
    """Generate list of week ending dates from start to end, plus future weeks."""
    weeks = []
    current = calculate_week_ending(pd.to_datetime(start_date))
    end = calculate_week_ending(pd.to_datetime(end_date))
    
    # Historical weeks
    while current <= end:
        weeks.append(current)
        current = current + timedelta(days=7)
    
    # Future weeks
    for i in range(num_future_weeks):
        weeks.append(current)
        current = current + timedelta(days=7)
    
    return weeks

# ============================================================================
# DATA INITIALIZATION
# ============================================================================

def initialize_session_state():
    """Initialize session state variables."""
    
    if 'initialized' not in st.session_state:
        st.session_state.project_info = {
            'client': '',
            'project_name': '',
            'report_date': datetime.now().strftime('%Y-%m-%d'),
            'report_by': '',
            'budget_management': 50.0,
            'budget_engineering': 200.0,
            'budget_drafting': 100.0
        }
        
        # Staff Database - NO RATE COLUMN (rates come from rate schedule)
        st.session_state.staff = pd.DataFrame({
            'Name': ['Gavin Andersen', 'Mark Rankin', 'Ben Robinson', 'Will Smith', 'Ben Bowles'],
            'Function': ['MANAGEMENT', 'DRAFTING', 'ENGINEERING', 'ENGINEERING', 'ENGINEERING'],
            'Discipline': ['GN', 'GN', 'ME', 'ME', 'ME'],
            'Position': ['Engineering Manager', 'Drawing Office Manager', 'Senior Engineer', 'Lead Engineer', 'Senior Engineer']
        })
        
        # Rate Schedule
        st.session_state.rates = pd.DataFrame({
            'Position': ['Engineering Manager', 'Lead Engineer', 'Senior Engineer', 'Drawing Office Manager', 
                        'Lead Designer', 'Senior Designer', 'Designer', 'Principal Engineer', 'Technical Reviewer'],
            'Rate': [245, 195, 170, 195, 165, 150, 140, 210, 245]
        })
        
        st.session_state.timesheets = pd.DataFrame()
        
        # Weekly forecasts: {(staff_name, week_ending): hours}
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
    st.session_state.project_info['client'] = 'Liontown'
    st.session_state.project_info['project_name'] = 'Tails Pump Assessment'
    st.session_state.project_info['report_by'] = 'Will Smith'
    st.session_state.project_info['report_date'] = '2025-10-28'
    
    st.success("✅ Sample data loaded successfully!")

# ============================================================================
# PAGE: DASHBOARD
# ============================================================================

def page_dashboard():
    """Main dashboard page."""
    st.title("📊 Project Scorecard Dashboard")
    
    st.subheader("Project Information")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.session_state.project_info['client'] = st.text_input("Client", st.session_state.project_info['client'])
    with col2:
        st.session_state.project_info['project_name'] = st.text_input("Project", st.session_state.project_info['project_name'])
    with col3:
        st.session_state.project_info['report_date'] = st.date_input("Report Date", pd.to_datetime(st.session_state.project_info['report_date'])).strftime('%Y-%m-%d')
    with col4:
        st.session_state.project_info['report_by'] = st.text_input("Report By", st.session_state.project_info['report_by'])
    
    st.divider()
    
    if not st.session_state.timesheets.empty:
        df = st.session_state.timesheets
        
        total_actual_hours = df['hours'].sum()
        total_actual_cost = df['cost'].sum()
        
        by_function = df.groupby('function').agg({'hours': 'sum', 'cost': 'sum'}).reset_index()
        
        mgmt_actual = by_function[by_function['function'] == 'MANAGEMENT']['hours'].sum() if 'MANAGEMENT' in by_function['function'].values else 0
        eng_actual = by_function[by_function['function'] == 'ENGINEERING']['hours'].sum() if 'ENGINEERING' in by_function['function'].values else 0
        draft_actual = by_function[by_function['function'] == 'DRAFTING']['hours'].sum() if 'DRAFTING' in by_function['function'].values else 0
        
        budget_mgmt = st.session_state.project_info['budget_management']
        budget_eng = st.session_state.project_info['budget_engineering']
        budget_draft = st.session_state.project_info['budget_drafting']
        total_budget = budget_mgmt + budget_eng + budget_draft
        
        pf = calculate_performance_factor(total_budget, total_actual_hours)
        
        st.subheader("Key Metrics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Budget Hours", f"{total_budget:.1f}h")
        with col2:
            variance = total_actual_hours - total_budget
            st.metric("Actual Hours", f"{total_actual_hours:.1f}h", f"{variance:+.1f}h", delta_color="inverse")
        with col3:
            st.metric("Actual Cost", f"${total_actual_cost:,.0f}")
        with col4:
            st.metric("Performance Factor", f"{pf:.2f}")
        
        st.subheader("Hours by Function")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Management", f"{mgmt_actual:.1f}h", f"Budget: {budget_mgmt:.0f}h")
        with col2:
            st.metric("Engineering", f"{eng_actual:.1f}h", f"Budget: {budget_eng:.0f}h")
        with col3:
            st.metric("Drafting", f"{draft_actual:.1f}h", f"Budget: {budget_draft:.0f}h")
        
        st.subheader("Budget vs Actual Comparison")
        chart_data = pd.DataFrame({
            'Function': ['Management', 'Engineering', 'Drafting'],
            'Budget': [budget_mgmt, budget_eng, budget_draft],
            'Actual': [mgmt_actual, eng_actual, draft_actual]
        })
        st.bar_chart(chart_data.set_index('Function'))
        
    else:
        st.info("👈 No data loaded. Go to **Data Import** to upload or load sample data.")
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
    
    **Expected CSV columns:** `[Time] Date`, `[Job] Name`, `[Staff] Name`, `[Job Task] Name`, `[Time] Time`, `[Time] Billable`
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
                st.error(f"❌ Error processing file: {str(e)}")
    
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
            st.metric("Date Range", f"{df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")
        else:
            st.warning("No data loaded")

# ============================================================================
# PAGE: MASTER DATA
# ============================================================================

def page_master_data():
    """Master data management - Staff and Rates."""
    st.title("👥 Master Data Management")
    
    # Rate Schedule FIRST (since staff references it)
    st.subheader("📋 Rate Schedule")
    st.markdown("**Master rate schedule** - Staff positions lookup rates from here.")
    
    rates_df = st.data_editor(
        st.session_state.rates,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Position": st.column_config.TextColumn("Position Title", required=True),
            "Rate": st.column_config.NumberColumn("Hourly Rate ($/hr)", format="$%.0f", required=True)
        }
    )
    
    if st.button("💾 Save Rate Changes", key="save_rates"):
        st.session_state.rates = rates_df
        st.success("✅ Rate schedule updated!")
        st.rerun()
    
    st.divider()
    
    # Staff Database (NO RATE COLUMN - rates come from rate schedule)
    st.subheader("👤 Staff Database")
    st.markdown("**Staff information** - Billing rates are automatically looked up from Rate Schedule based on Position.")
    
    # Add a computed rate column for display only
    staff_display = st.session_state.staff.copy()
    staff_display['Current Rate'] = staff_display['Position'].apply(lambda x: lookup_rate_by_position(x, st.session_state.rates))
    
    staff_df = st.data_editor(
        staff_display,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Name": st.column_config.TextColumn("Name", required=True),
            "Function": st.column_config.SelectboxColumn("Function", options=["MANAGEMENT", "ENGINEERING", "DRAFTING"], required=True),
            "Discipline": st.column_config.TextColumn("Discipline"),
            "Position": st.column_config.SelectboxColumn("Position Title", 
                options=st.session_state.rates['Position'].tolist(), required=True),
            "Current Rate": st.column_config.NumberColumn("Current Rate ($/hr)", format="$%.0f", disabled=True, 
                help="Automatically looked up from Rate Schedule")
        }
    )
    
    if st.button("💾 Save Staff Changes", key="save_staff"):
        # Remove the computed rate column before saving
        staff_to_save = staff_df[['Name', 'Function', 'Discipline', 'Position']].copy()
        st.session_state.staff = staff_to_save
        st.success("✅ Staff database updated!")
        st.rerun()

# ============================================================================
# PAGE: MANNING VIEW - WEEKLY GRID
# ============================================================================

def page_manning():
    """Manning view with weekly grid - actual and forecast hours per week."""
    st.title("📅 Manning View - Weekly Resource Allocation")
    
    if st.session_state.timesheets.empty:
        st.warning("⚠️ No timesheet data loaded. Please import data first.")
        return
    
    df = st.session_state.timesheets
    report_date = pd.to_datetime(st.session_state.project_info['report_date'])
    
    # Get all unique staff
    all_staff = sorted(df['staff_name'].unique())
    
    # Get week range
    min_date = df['date'].min()
    max_date = df['date'].max()
    
    # Generate week list (historical + future)
    weeks = get_week_list(min_date, report_date, num_future_weeks=12)
    
    st.info(f"📅 **Report Date:** {report_date.strftime('%Y-%m-%d')} | Weeks before = Actual (from timesheets) | Weeks after = Forecast (editable)")
    
    # Aggregate actual hours by person and week
    actual_by_week = df.groupby(['staff_name', 'week_ending'])['hours'].sum().reset_index()
    
    # Build manning grid
    manning_rows = []
    
    for person in all_staff:
        row = {'Personnel': person}
        
        # Get person details
        person_info = st.session_state.staff[st.session_state.staff['Name'] == person]
        if not person_info.empty:
            row['Position'] = person_info.iloc[0]['Position']
            row['Function'] = person_info.iloc[0]['Function']
            row['Rate'] = get_staff_rate(person, st.session_state.staff, st.session_state.rates)
        else:
            row['Position'] = 'Unknown'
            row['Function'] = 'ENGINEERING'
            row['Rate'] = 170.0
        
        # Add columns for each week
        total_actual = 0
        total_forecast = 0
        
        for week in weeks:
            week_key = f"Week_{week.strftime('%Y-%m-%d')}"
            
            if week <= report_date:
                # ACTUAL hours from timesheets
                actual = actual_by_week[
                    (actual_by_week['staff_name'] == person) & 
                    (actual_by_week['week_ending'] == week)
                ]['hours'].sum()
                row[week_key] = actual
                total_actual += actual
            else:
                # FORECAST hours (editable)
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
    
    # Display options
    st.subheader("Display Options")
    col1, col2 = st.columns(2)
    with col1:
        show_weeks = st.slider("Number of weeks to display", min_value=4, max_value=len(weeks), value=min(12, len(weeks)))
    with col2:
        filter_function = st.selectbox("Filter by Function", ["All", "MANAGEMENT", "ENGINEERING", "DRAFTING"])
    
    # Filter data
    if filter_function != "All":
        manning_df_filtered = manning_df[manning_df['Function'] == filter_function]
    else:
        manning_df_filtered = manning_df
    
    # Select columns to display
    weeks_to_show = weeks[:show_weeks]
    week_columns = [f"Week_{w.strftime('%Y-%m-%d')}" for w in weeks_to_show]
    display_columns = ['Personnel', 'Position', 'Function', 'Rate'] + week_columns + ['Total Actual', 'Total Forecast', 'Total Hours', 'Total Cost']
    
    # Create column config
    column_config = {
        "Personnel": st.column_config.TextColumn("Personnel", width="medium", disabled=True),
        "Position": st.column_config.TextColumn("Position", width="medium", disabled=True),
        "Function": st.column_config.TextColumn("Function", width="small", disabled=True),
        "Rate": st.column_config.NumberColumn("Rate", format="$%.0f", width="small", disabled=True),
        "Total Actual": st.column_config.NumberColumn("Σ Actual", format="%.1f", width="small", disabled=True),
        "Total Forecast": st.column_config.NumberColumn("Σ Forecast", format="%.1f", width="small", disabled=True),
        "Total Hours": st.column_config.NumberColumn("Σ Total", format="%.1f", width="small", disabled=True),
        "Total Cost": st.column_config.NumberColumn("Σ Cost", format="$%,.0f", width="medium", disabled=True)
    }
    
    # Add week column configs
    for i, week in enumerate(weeks_to_show):
        week_key = f"Week_{week.strftime('%Y-%m-%d')}"
        is_past = week <= report_date
        
        column_config[week_key] = st.column_config.NumberColumn(
            week.strftime('%m/%d'),
            help=f"Week ending {week.strftime('%Y-%m-%d')}",
            format="%.1f",
            width="small",
            disabled=is_past  # Past weeks are read-only
        )
    
    st.subheader("Weekly Manning Grid")
    
    # Editable dataframe
    edited_df = st.data_editor(
        manning_df_filtered[display_columns],
        use_container_width=True,
        column_config=column_config,
        hide_index=True,
        height=600
    )
    
    # Update forecasts from edited data
    for idx, row in edited_df.iterrows():
        person = row['Personnel']
        for week in weeks_to_show:
            if week > report_date:  # Only update forecast weeks
                week_key = f"Week_{week.strftime('%Y-%m-%d')}"
                if week_key in row:
                    forecast_key = (person, week.strftime('%Y-%m-%d'))
                    st.session_state.weekly_forecasts[forecast_key] = row[week_key] if not pd.isna(row[week_key]) else 0.0
    
    # Summary
    st.divider()
    st.subheader("Summary by Function")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("**MANAGEMENT**")
        mgmt_data = manning_df[manning_df['Function'] == 'MANAGEMENT']
        st.metric("Actual", f"{mgmt_data['Total Actual'].sum():.1f}h")
        st.metric("Forecast", f"{mgmt_data['Total Forecast'].sum():.1f}h")
        st.metric("Total", f"{mgmt_data['Total Hours'].sum():.1f}h")
    
    with col2:
        st.markdown("**ENGINEERING**")
        eng_data = manning_df[manning_df['Function'] == 'ENGINEERING']
        st.metric("Actual", f"{eng_data['Total Actual'].sum():.1f}h")
        st.metric("Forecast", f"{eng_data['Total Forecast'].sum():.1f}h")
        st.metric("Total", f"{eng_data['Total Hours'].sum():.1f}h")
    
    with col3:
        st.markdown("**DRAFTING**")
        draft_data = manning_df[manning_df['Function'] == 'DRAFTING']
        st.metric("Actual", f"{draft_data['Total Actual'].sum():.1f}h")
        st.metric("Forecast", f"{draft_data['Total Forecast'].sum():.1f}h")
        st.metric("Total", f"{draft_data['Total Hours'].sum():.1f}h")
    
    with col4:
        st.markdown("**PROJECT TOTAL**")
        st.metric("Actual", f"{manning_df['Total Actual'].sum():.1f}h")
        st.metric("Forecast", f"{manning_df['Total Forecast'].sum():.1f}h")
        st.metric("Total Cost", f"${manning_df['Total Cost'].sum():,.0f}")

# ============================================================================
# PAGE: REPORT
# ============================================================================

def page_report():
    """Report generator page."""
    st.title("📈 Project Report")
    
    if st.session_state.timesheets.empty:
        st.warning("⚠️ No timesheet data loaded. Please import data first.")
        return
    
    df = st.session_state.timesheets
    
    st.markdown(f"""
    ### Weekly Progress Report
    **Client:** {st.session_state.project_info['client']}  
    **Project:** {st.session_state.project_info['project_name']}  
    **Date:** {st.session_state.project_info['report_date']}  
    **Report By:** {st.session_state.project_info['report_by']}
    """)
    
    st.divider()
    
    st.subheader("Project Budget")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.session_state.project_info['budget_management'] = st.number_input("Management Budget (hours)", value=st.session_state.project_info['budget_management'], min_value=0.0)
    with col2:
        st.session_state.project_info['budget_engineering'] = st.number_input("Engineering Budget (hours)", value=st.session_state.project_info['budget_engineering'], min_value=0.0)
    with col3:
        st.session_state.project_info['budget_drafting'] = st.number_input("Drafting Budget (hours)", value=st.session_state.project_info['budget_drafting'], min_value=0.0)
    
    total_budget = (st.session_state.project_info['budget_management'] + st.session_state.project_info['budget_engineering'] + st.session_state.project_info['budget_drafting'])
    
    by_function = df.groupby('function').agg({'hours': 'sum', 'cost': 'sum'}).reset_index()
    
    mgmt_actual = by_function[by_function['function'] == 'MANAGEMENT']['hours'].sum() if 'MANAGEMENT' in by_function['function'].values else 0
    eng_actual = by_function[by_function['function'] == 'ENGINEERING']['hours'].sum() if 'ENGINEERING' in by_function['function'].values else 0
    draft_actual = by_function[by_function['function'] == 'DRAFTING']['hours'].sum() if 'DRAFTING' in by_function['function'].values else 0
    total_actual = mgmt_actual + eng_actual + draft_actual
    
    mgmt_cost = by_function[by_function['function'] == 'MANAGEMENT']['cost'].sum() if 'MANAGEMENT' in by_function['function'].values else 0
    eng_cost = by_function[by_function['function'] == 'ENGINEERING']['cost'].sum() if 'ENGINEERING' in by_function['function'].values else 0
    draft_cost = by_function[by_function['function'] == 'DRAFTING']['cost'].sum() if 'DRAFTING' in by_function['function'].values else 0
    total_cost = mgmt_cost + eng_cost + draft_cost
    
    # Calculate forecasts from weekly manning data
    report_date = pd.to_datetime(st.session_state.project_info['report_date'])
    forecast_mgmt = 0
    forecast_eng = 0
    forecast_draft = 0
    
    for (person, week_str), hours in st.session_state.weekly_forecasts.items():
        week_date = pd.to_datetime(week_str)
        if week_date > report_date:
            person_info = st.session_state.staff[st.session_state.staff['Name'] == person]
            if not person_info.empty:
                function = person_info.iloc[0]['Function']
                if function == 'MANAGEMENT':
                    forecast_mgmt += hours
                elif function == 'ENGINEERING':
                    forecast_eng += hours
                elif function == 'DRAFTING':
                    forecast_draft += hours
    
    total_forecast = forecast_mgmt + forecast_eng + forecast_draft
    
    pf = calculate_performance_factor(total_budget, total_actual)
    forecast_at_completion = total_actual + total_forecast
    
    st.subheader("Performance Summary")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Budget", f"{total_budget:.1f}h")
    with col2:
        st.metric("Actual", f"{total_actual:.1f}h")
    with col3:
        st.metric("Earned Value", f"{total_budget:.1f}h")
    with col4:
        st.metric("Performance Factor", f"{pf:.2f}")
    with col5:
        st.metric("Forecast at Completion", f"{forecast_at_completion:.1f}h")
    
    st.divider()
    st.subheader("Breakdown by Function")
    
    report_data = pd.DataFrame({
        'Function': ['Management', 'Engineering', 'Drafting', 'TOTAL'],
        'Budget': [st.session_state.project_info['budget_management'], st.session_state.project_info['budget_engineering'], st.session_state.project_info['budget_drafting'], total_budget],
        'Actual': [mgmt_actual, eng_actual, draft_actual, total_actual],
        'Forecast': [forecast_mgmt, forecast_eng, forecast_draft, total_forecast],
        'Total': [mgmt_actual + forecast_mgmt, eng_actual + forecast_eng, draft_actual + forecast_draft, forecast_at_completion],
        'Cost': [mgmt_cost, eng_cost, draft_cost, total_cost]
    })
    
    st.dataframe(report_data, use_container_width=True, column_config={
        "Budget": st.column_config.NumberColumn("Budget (h)", format="%.1f"),
        "Actual": st.column_config.NumberColumn("Actual (h)", format="%.1f"),
        "Forecast": st.column_config.NumberColumn("Forecast (h)", format="%.1f"),
        "Total": st.column_config.NumberColumn("Total (h)", format="%.1f"),
        "Cost": st.column_config.NumberColumn("Cost ($)", format="$%,.0f")
    }, hide_index=True)
    
    st.divider()
    st.subheader("Export Report")
    
    col1, col2 = st.columns(2)
    
    with col1:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            report_data.to_excel(writer, sheet_name='Summary', index=False)
            df[['date', 'staff_name', 'task_name', 'hours', 'function', 'cost']].to_excel(writer, sheet_name='Timesheets', index=False)
        
        st.download_button(
            label="📥 Download Excel Report",
            data=output.getvalue(),
            file_name=f"Project_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    
    with col2:
        st.info("💡 Forecast hours come from the Manning View weekly grid.")

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application entry point."""
    
    initialize_session_state()
    
    st.sidebar.title("📊 Project Scorecard")
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio("Navigation", ["🏠 Dashboard", "📤 Data Import", "👥 Master Data", "📅 Manning View", "📈 Report"], label_visibility="collapsed")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Quick Actions")
    
    if st.sidebar.button("🎯 Load Sample Data"):
        load_sample_data()
        st.rerun()
    
    if st.sidebar.button("🗑️ Clear All Data"):
        st.session_state.timesheets = pd.DataFrame()
        st.session_state.weekly_forecasts = {}
        st.success("All data cleared!")
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("*EPCM Scorecard v1.1*")
    st.sidebar.markdown("✨ *New: Weekly grid & rate lookup*")
    
    if page == "🏠 Dashboard":
        page_dashboard()
    elif page == "📤 Data Import":
        page_data_import()
    elif page == "👥 Master Data":
        page_master_data()
    elif page == "📅 Manning View":
        page_manning()
    elif page == "📈 Report":
        page_report()

if __name__ == "__main__":
    main()
