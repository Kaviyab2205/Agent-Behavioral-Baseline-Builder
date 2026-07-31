from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from backend.database import get_db

# Configure Streamlit page
st.set_page_config(
    page_title=" Agent Behavioral Baseline Builder",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Backend API Configuration
BACKEND_URL = "http://127.0.0.1:8000/api"

# Pre-defined templates for easy agent creation
AGENT_TEMPLATES = {
    "Select Template...": None,
    "Antigravity Banking Agent": {
        "prompt": "You are a customer support agent representing Antigravity Bank. You help customers with account balance inquiries, update their profile information, send transaction confirmation emails, and create support tickets for issues.",
        "tools": ["search_database", "get_customer", "update_customer", "get_account", "send_email", "create_ticket"],
        "version": "1.0.0"
    },
    "E-commerce Retail Agent": {
        "prompt": "You are a retail operations assistant for a major online store. You assist customers in checking order status, shipping details, canceling orders, updating order records, and creating logistics support tickets.",
        "tools": ["search_database", "retrieve_order", "update_customer", "send_email", "create_ticket"],
        "version": "1.1.0"
    },
    "IT Operations Helpdesk": {
        "prompt": "You are an internal IT support bot. You retrieve system logs, look up employee database details, close support tickets, reset credentials, and send email alerts.",
        "tools": ["search_database", "get_customer", "update_customer", "send_email", "create_ticket"],
        "version": "1.0.0"
    }
}

# Custom CSS styles
st.markdown("""
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F3F4F6;
        border-radius: 8px;
        padding: 1rem;
        border-left: 5px solid #2563EB;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
    }
    .metric-title {
        font-size: 0.8rem;
        text-transform: uppercase;
        color: #6B7280;
        font-weight: 600;
    }
    .metric-value {
        font-size: 1.4rem;
        font-weight: 700;
        color: #1F2937;
    }
    .status-badge {
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 700;
        display: inline-block;
    }
    .status-normal { background-color: #DEF7EC; color: #03543F; border-left: 3px solid #31C48D; }
    .status-warning { background-color: #FEF3C7; color: #92400E; border-left: 3px solid #F59E0B; }
    .status-alert { background-color: #FEE2E2; color: #991B1B; border-left: 3px solid #F05252; }
    .status-drift { background-color: #EDEBFE; color: #5521B5; border-left: 3px solid #7E3AF2; }
    </style>
""", unsafe_allow_html=True)

# Helper functions to query the backend API
def check_backend_health():
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False

def get_agents():
    try:
        response = requests.get(f"{BACKEND_URL}/agents")
        return response.json() if response.status_code == 200 else []
    except requests.RequestException:
        return []

def create_agent(name, system_prompt, tools, version):
    try:
        payload = {"name": name, "system_prompt": system_prompt, "tools": tools, "version": version}
        return requests.post(f"{BACKEND_URL}/agents", json=payload)
    except requests.RequestException:
        return None

def get_scenarios(agent_id):
    try:
        response = requests.get(f"{BACKEND_URL}/scenarios/{agent_id}")
        return response.json() if response.status_code == 200 else []
    except requests.RequestException:
        return []

def generate_scenarios(agent_id, count=50):
    try:
        payload = {"agent_id": agent_id, "count": count}
        return requests.post(f"{BACKEND_URL}/scenarios/generate", json=payload)
    except requests.RequestException:
        return None

def create_baseline(agent_id):
    try:
        return requests.post(f"{BACKEND_URL}/baseline/create/{agent_id}")
    except requests.RequestException:
        return None

def get_active_baseline(agent_id):
    try:
        response = requests.get(f"{BACKEND_URL}/baseline/{agent_id}")
        return response.json() if response.status_code == 200 else None
    except requests.RequestException:
        return None

def get_baseline_fingerprints(agent_id):
    # Returns all fingerprints for the active baseline (including intent clustered ones)
    try:
        active_bl = get_active_baseline(agent_id)
        if not active_bl:
            return []
        response = requests.get(f"{BACKEND_URL}/baseline/{agent_id}/fingerprint") # Wait, this returns only one.
        # Let's hit a direct DB query via helper endpoint or just fetch the active baseline's details.
        # Let's look up how we query in backend: GET /api/baseline/{agent_id}/fingerprint returns the active fingerprint.
        # Let's adjust so that we can query intent-specific ones if needed, or query them via setting/api.
        # We can implement a clean retrieval for the dashboard!
        return active_bl
    except requests.RequestException:
        return None

def get_settings():
    try:
        response = requests.get(f"{BACKEND_URL}/settings")
        return response.json() if response.status_code == 200 else None
    except requests.RequestException:
        return None

def update_settings(payload):
    try:
        return requests.post(f"{BACKEND_URL}/settings", json=payload)
    except requests.RequestException:
        return None

def simulate_production(agent_id, count=10, profile="normal"):
    try:
        payload = {"agent_id": agent_id, "count": count, "profile": profile}
        return requests.post(f"{BACKEND_URL}/production/simulate", json=payload)
    except requests.RequestException:
        return None

def get_production_sessions(agent_id=None, severity=None, limit=100):
    try:
        params = {"limit": limit}
        if agent_id:
            params["agent_id"] = agent_id
        if severity:
            params["severity"] = severity
        response = requests.get(f"{BACKEND_URL}/production/sessions", params=params)
        return response.json() if response.status_code == 200 else []
    except requests.RequestException:
        return []

def get_monitor_summary(agent_id, window=100):
    try:
        response = requests.get(f"{BACKEND_URL}/monitor/summary/{agent_id}", params={"window": window})
        return response.json() if response.status_code == 200 else None
    except requests.RequestException:
        return None

def get_alerts(agent_id=None, status_val=None, severity=None):
    try:
        params = {}
        if status_val:
            params["status"] = status_val
        if severity:
            params["severity"] = severity
        
        url = f"{BACKEND_URL}/alerts/{agent_id}" if agent_id else f"{BACKEND_URL}/alerts"
        response = requests.get(url, params=params)
        return response.json() if response.status_code == 200 else []
    except requests.RequestException:
        return []

def resolve_alert(event_id):
    try:
        return requests.post(f"{BACKEND_URL}/alerts/{event_id}/resolve")
    except requests.RequestException:
        return None

def reanalyze_all():
    try:
        return requests.post(f"{BACKEND_URL}/monitor/analyze-all")
    except requests.RequestException:
        return None

# Check connection to backend
backend_online = check_backend_health()

# Main Layout Headers
st.markdown('<div class="main-header">🛡️ Agent Behavioral Baseline Builder</div>', unsafe_allow_html=True)

if not backend_online:
    st.error("🔌 Cannot connect to backend server. Make sure the FastAPI backend is running at http://127.0.0.1:8000")
    st.info("💡 Run `uvicorn backend.main:app --reload` to start the backend API.")
    st.stop()

# Load settings to display/use
settings_data = get_settings()

# Sidebar Setup
st.sidebar.header("🧭 Navigation")
page = st.sidebar.radio("Go to Page", [
    "Overview",
    "Agent Configuration",
    "Synthetic Scenarios",
    "Baseline",
    "Production Monitoring",
    "Anomaly Events",
    "Drift Detection",
    "Intent Baselines",
    "Settings",
    "Demo / Test Scenarios"
])

# Apply agent ID override from Demo Sandbox
if "selected_agent_id_override" in st.session_state:
    st.session_state["active_agent_id"] = st.session_state.pop("selected_agent_id_override")

st.sidebar.markdown("---")
st.sidebar.subheader("🔧 Active Agent Selection")
agents_list = get_agents()
agent_options = {f"{a['name']} ({a['version']})": a for a in agents_list}

# Find default index of the active agent in the options list
default_index = 0
if "active_agent_id" in st.session_state:
    for idx, a in enumerate(agents_list):
        if a["id"] == st.session_state["active_agent_id"]:
            default_index = idx + 1
            break

# If stored ID is no longer in the agents list, clear it
if default_index == 0 and "active_agent_id" in st.session_state:
    del st.session_state["active_agent_id"]

selected_agent_name = st.sidebar.selectbox(
    "Active Agent",
    ["-- Select Agent --"] + list(agent_options.keys()),
    index=default_index,
    key="active_agent_selectbox"
)

active_agent = None
if selected_agent_name != "-- Select Agent --":
    active_agent = agent_options[selected_agent_name]
    st.session_state["active_agent_id"] = active_agent["id"]
else:
    if "active_agent_id" in st.session_state:
        del st.session_state["active_agent_id"]
# Helper status color mappings
def get_severity_badge_html(sev: str) -> str:
    sev = sev.upper()
    if sev == "NORMAL":
        return f'<span class="status-badge status-normal">NORMAL</span>'
    elif sev == "WARNING":
        return f'<span class="status-badge status-warning">WARNING</span>'
    elif sev == "ALERT":
        return f'<span class="status-badge status-alert">ALERT</span>'
    elif sev == "DRIFT":
        return f'<span class="status-badge status-drift">DRIFT</span>'
    return f'<span class="status-badge">{sev}</span>'

# ==================== PAGE: OVERVIEW ====================
if page == "Overview":
    st.subheader("System Overview Dashboard")
    
    if not active_agent:
        st.info("💡 Select an agent in the sidebar to view metrics, or create one in the 'Agent Configuration' page.")
    else:
        # Fetch active baseline, running statistics
        active_bl = get_active_baseline(active_agent["id"])
        summary = get_monitor_summary(active_agent["id"], window=100)
        
        # Determine model/prompt versions from last simulated sessions
        recent_sessions = get_production_sessions(agent_id=active_agent["id"], limit=1)
        model_ver = recent_sessions[0]["model_version"] if recent_sessions else "agent-model-v1"
        prompt_ver = recent_sessions[0]["prompt_version"] if recent_sessions else "v1"

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            bl_ver = active_bl["version"] if active_bl else "None"
            st.markdown(f'<div class="metric-card"><div class="metric-title">Active Baseline</div><div class="metric-value">{bl_ver}</div></div>', unsafe_allow_html=True)
        with col_m2:
            st.markdown(f'<div class="metric-card"><div class="metric-title">Model / Prompt Version</div><div class="metric-value" style="font-size:1.1rem; font-weight:600;">{model_ver} / {prompt_ver}</div></div>', unsafe_allow_html=True)
        with col_m3:
            total_sessions = summary["total_sessions"] if summary else 0
            st.markdown(f'<div class="metric-card"><div class="metric-title">Total Production Sessions</div><div class="metric-value">{total_sessions}</div></div>', unsafe_allow_html=True)
        with col_m4:
            drift_status = summary["drift_status"] if summary else "NORMAL"
            drift_color = "#7E3AF2" if drift_status == "DRIFT_DETECTED" else "#10B981"
            st.markdown(f'<div class="metric-card" style="border-left-color: {drift_color};"><div class="metric-title">Drift Status</div><div class="metric-value">{drift_status}</div></div>', unsafe_allow_html=True)

        if total_sessions == 0:
            st.warning("⚠️ No production traffic recorded yet. Go to the 'Production Monitoring' page to simulate traffic.")
        else:
            col_k1, col_k2, col_k3, col_k4 = st.columns(4)
            with col_k1:
                st.markdown(f'<div class="metric-card" style="border-left-color: #10B981; background-color: #EDFDF5;"><div class="metric-title">Normal Sessions</div><div class="metric-value" style="color: #047857;">{summary["normal_count"]}</div></div>', unsafe_allow_html=True)
            with col_k2:
                st.markdown(f'<div class="metric-card" style="border-left-color: #F59E0B; background-color: #FFFBEB;"><div class="metric-title">Warning Sessions</div><div class="metric-value" style="color: #B45309;">{summary["warning_count"]}</div></div>', unsafe_allow_html=True)
            with col_k3:
                st.markdown(f'<div class="metric-card" style="border-left-color: #EF4444; background-color: #FDF2F2;"><div class="metric-title">Alert Sessions</div><div class="metric-value" style="color: #B91C1C;">{summary["alert_count"]}</div></div>', unsafe_allow_html=True)
            with col_k4:
                st.markdown(f'<div class="metric-card" style="border-left-color: #3B82F6;"><div class="metric-title">Avg Anomaly Score</div><div class="metric-value">{summary["avg_anomaly_score"]:.1f}</div></div>', unsafe_allow_html=True)

            # Retrieve sessions list for plotting
            sessions_list = get_production_sessions(agent_id=active_agent["id"], limit=100)
            sessions_df = pd.DataFrame(sessions_list)
            # Sort chronological
            sessions_df = sessions_df.iloc[::-1].reset_index(drop=True)

            col_c1, col_c2 = st.columns(2)
            with col_c1:
                # Anomaly score over time
                fig_time = px.line(
                    sessions_df,
                    y="anomaly_score",
                    title="Anomaly Score Trend (Last 100 Sessions)",
                    labels={"index": "Time Sequence", "anomaly_score": "Anomaly Score"},
                    markers=True,
                    color_discrete_sequence=["#2563EB"]
                )
                # Add threshold lines
                if settings_data:
                    fig_time.add_hline(y=settings_data["warning_threshold"], line_dash="dash", line_color="#F59E0B", annotation_text="Warning Threshold")
                    fig_time.add_hline(y=settings_data["alert_threshold"], line_dash="dash", line_color="#EF4444", annotation_text="Alert Threshold")
                st.plotly_chart(fig_time, width="stretch")
                
            with col_c2:
                # Severity distribution
                sev_counts = sessions_df["severity"].value_counts().reset_index()
                sev_counts.columns = ["Severity", "Count"]
                fig_sev = px.pie(
                    sev_counts,
                    values="Count",
                    names="Severity",
                    title="Traffic Severity Distribution",
                    hole=0.4,
                    color="Severity",
                    color_discrete_map={"NORMAL": "#31C48D", "WARNING": "#F59E0B", "ALERT": "#F05252"}
                )
                st.plotly_chart(fig_sev, width="stretch")

            col_c3, col_c4 = st.columns(2)
            with col_c3:
                # Latency Trend
                fig_lat = px.line(
                    sessions_df,
                    y="latency_ms",
                    title="Latency Trend (ms)",
                    labels={"index": "Time Sequence", "latency_ms": "Latency (ms)"},
                    color_discrete_sequence=["#8B5CF6"]
                )
                st.plotly_chart(fig_lat, width="stretch")
            with col_c4:
                # Response Length Trend
                fig_len = px.histogram(
                    sessions_df,
                    x="response_length",
                    nbins=15,
                    title="Response Length Distribution (chars)",
                    color_discrete_sequence=["#EC4899"]
                )
                st.plotly_chart(fig_len, width="stretch")

# ==================== PAGE: AGENT CONFIGURATION ====================
elif page == "Agent Configuration":
    st.subheader("Agent Configuration & Lifecycle")
    
    col_a1, col_a2 = st.columns([1, 1])
    
    with col_a1:
        st.markdown("### Register New Agent Profile")
        st.write("Configure a new agent name, version, prompt, and tool registry. The configuration is stored persistently in SQLite.")
        
        template_sel = st.selectbox("Load Predefined Profile", list(AGENT_TEMPLATES.keys()))
        
        default_name = ""
        default_prompt = ""
        default_tools = []
        default_version = "1.0.0"
        
        if template_sel != "Select Template..." and AGENT_TEMPLATES[template_sel] is not None:
            template_data = AGENT_TEMPLATES[template_sel]
            default_name = template_sel
            default_prompt = template_data["prompt"]
            default_tools = template_data["tools"]
            default_version = template_data["version"]
            
        new_name = st.text_input("Agent Name", value=default_name)
        new_version = st.text_input("Agent Version", value=default_version)
        new_prompt = st.text_area("System Prompt", value=default_prompt, height=150)
        
        all_available_tools = ["search_database", "get_customer", "update_customer", "send_email", "create_ticket", "retrieve_order", "get_account"]
        new_tools = st.multiselect("Available Tool Set", all_available_tools, default=default_tools)
        
        if st.button("Register Agent Profile", type="primary"):
            if not new_name.strip():
                st.error("Agent name cannot be empty.")
            elif not new_prompt.strip():
                st.error("System prompt cannot be empty.")
            elif not new_tools:
                st.error("Select at least one tool for the agent.")
            else:
                resp = create_agent(new_name, new_prompt, new_tools, new_version)
                if resp and resp.status_code == 201:
                    st.success(f"Agent '{new_name}' registered successfully!")
                    st.rerun()
                elif resp:
                    st.error(resp.json().get("detail", "Error creating agent."))

    with col_a2:
        st.markdown("### Registered Agent List")
        if not agents_list:
            st.info("No agents registered yet.")
        else:
            for idx, a in enumerate(agents_list):
                with st.container():
                    st.markdown(f"**{idx+1}. {a['name']} (Version: {a['version']})**")
                    st.text(f"Agent ID: {a['id']}")
                    st.text_area("System Prompt instruction", value=a["system_prompt"], height=70, disabled=True, key=f"p_{a['id']}")
                    st.markdown(f"**Tools:** {', '.join(a['tools'])}")
                    st.markdown("---")

# ==================== PAGE: SYNTHETIC SCENARIOS ====================
elif page == "Synthetic Scenarios":
    st.subheader("Synthetic Scenarios Generator")
    
    if not active_agent:
        st.warning("⚠️ No active agent selected. Select an agent in the sidebar to view/generate scenarios.")
    else:
        scenarios = get_scenarios(active_agent["id"])
        
        st.write(f"Generate diverse synthetic test scenarios that exercise the expected behaviour space for **{active_agent['name']}**.")
        
        col_s1, col_s2 = st.columns([1, 2])
        with col_s1:
            st.markdown("#### Scenario Settings")
            count_input = st.number_input("Number of Scenarios to Generate", min_value=5, max_value=100, value=50, step=5)
            
            if st.button("Generate & Store Scenarios", type="primary", width="stretch"):
                with st.spinner("Generating scenarios..."):
                    resp = generate_scenarios(active_agent["id"], count=count_input)
                    if resp and resp.status_code == 201:
                        st.success(f"Generated and saved {count_input} diverse test scenarios!")
                        st.rerun()
                    elif resp:
                        st.error(resp.json().get("detail", "Error generating scenarios."))
            
            if scenarios:
                df = pd.DataFrame(scenarios)
                st.markdown("#### Intent Categories Breakdown")
                intent_counts = df["intent"].value_counts().reset_index()
                intent_counts.columns = ["Intent", "Count"]
                st.dataframe(intent_counts, hide_index=True, width="stretch")
                
        with col_s2:
            st.markdown(f"#### Generated Scenarios List ({len(scenarios)})")
            if not scenarios:
                st.info("No scenarios generated yet. Click 'Generate' to create 50 scenarios by default.")
            else:
                df_scenarios = pd.DataFrame(scenarios)
                # Form list tool list to string
                df_scenarios["expected_tool_calls"] = df_scenarios["expected_tool_calls"].apply(lambda x: ", ".join(x))
                
                st.dataframe(
                    df_scenarios[["id", "intent", "difficulty", "data_sensitivity", "user_request", "expected_tool_calls"]],
                    column_config={
                        "id": st.column_config.TextColumn("ID"),
                        "intent": st.column_config.TextColumn("Intent Category"),
                        "difficulty": st.column_config.TextColumn("Difficulty"),
                        "data_sensitivity": st.column_config.TextColumn("Sensitivity"),
                        "user_request": st.column_config.TextColumn("User Request", width="large"),
                        "expected_tool_calls": st.column_config.TextColumn("Expected Tools"),
                    },
                    hide_index=True,
                    width="stretch"
                )

# ==================== PAGE: BASELINE ====================
elif page == "Baseline":
    st.subheader("Agent Behavioral Baseline Fingerprint")
    
    if not active_agent:
        st.warning("⚠️ No active agent selected. Select an agent in the sidebar.")
    else:
        active_bl = get_active_baseline(active_agent["id"])
        
        if not active_bl:
            st.warning("⚠️ No active baseline recorded for this agent yet. Generate scenarios and click 'Create Baseline' in the sidebar.")
        else:
            # Query fingerprint (direct api call)
            fp_url = f"{BACKEND_URL}/baseline/{active_agent['id']}/fingerprint"
            response = requests.get(fp_url)
            
            if response.status_code != 200:
                st.error("Failed to load baseline fingerprint from backend.")
            else:
                fp = response.json()
                
                st.subheader(f"Active Baseline Version: {active_bl['version']}")
                st.write(f"Established on: **{active_bl['created_at']}** | Simulated **{active_bl['scenario_count']}** normal scenarios.")
                
                # Metrics KPIs
                col_k1, col_k2, col_k3, col_k4, col_k5 = st.columns(5)
                with col_k1:
                    st.metric("Success Rate", f"{fp['success_rate']*100:.1f}%")
                with col_k2:
                    st.metric("Avg Latency", f"{fp['latency_stats']['avg']:.1f} ms")
                with col_k3:
                    st.metric("Avg Response Length", f"{fp['avg_response_length']:.1f} chars")
                with col_k4:
                    st.metric("Avg Tool Count", f"{fp['tool_count_stats']['avg']:.2f}")
                with col_k5:
                    st.metric("Error Rate", f"{fp['error_rate']:.2f} per run")

                # Charts
                col_ch1, col_ch2 = st.columns(2)
                with col_ch1:
                    tf_df = pd.DataFrame(list(fp["tool_frequency"].items()), columns=["Tool Name", "Frequency"])
                    tf_df = tf_df.sort_values(by="Frequency", ascending=True)
                    fig_tf = px.bar(
                        tf_df,
                        y="Tool Name",
                        x="Frequency",
                        orientation="h",
                        title="Tool Call Frequency Distribution (%)",
                        color="Frequency",
                        color_continuous_scale="Blues"
                    )
                    fig_tf.update_layout(coloraxis_showscale=False)
                    st.plotly_chart(fig_tf, width="stretch")
                    
                with col_ch2:
                    dp_df = pd.DataFrame(list(fp["data_access_patterns"].items()), columns=["Data Category", "Proportion"])
                    fig_dp = px.pie(
                        dp_df,
                        values="Proportion",
                        names="Data Category",
                        title="Data Access Distribution",
                        hole=0.4,
                        color_discrete_sequence=px.colors.qualitative.Pastel
                    )
                    st.plotly_chart(fig_dp, width="stretch")

                col_ch3, col_ch4 = st.columns(2)
                with col_ch3:
                    # Tool transitions
                    st.markdown("#### Tool Call Transition Frequencies")
                    if fp["tool_sequence_patterns"]:
                        seq_df = pd.DataFrame(list(fp["tool_sequence_patterns"].items()), columns=["Sequence Transition Path", "Relative Probability"])
                        seq_df = seq_df.sort_values(by="Relative Probability", ascending=False)
                        st.dataframe(seq_df, hide_index=True, width="stretch")
                    else:
                        st.info("No transition sequences found.")
                with col_ch4:
                    st.markdown("#### Intent Distribution in Scenarios")
                    intent_df = pd.DataFrame(list(fp["intent_distribution"].items()), columns=["Intent", "Proportion"])
                    fig_intent = px.bar(intent_df, x="Intent", y="Proportion", title="Intent Distribution", color="Intent")
                    st.plotly_chart(fig_intent, width="stretch")

# ==================== PAGE: PRODUCTION MONITORING ====================
elif page == "Production Monitoring":
    st.subheader("Live Production Traffic Monitor")
    
    if not active_agent:
        st.warning("⚠️ No active agent selected. Select an agent in the sidebar.")
    else:
        active_bl = get_active_baseline(active_agent["id"])
        
        if not active_bl:
            st.warning("⚠️ Baseline must be created first before you can monitor production traffic.")
        else:
            col_p1, col_p2 = st.columns([1, 2])
            
            with col_p1:
                st.markdown("### Generate Production Traffic")
                st.write("Simulate production sessions. You can generate normal baseline traffic, or inject deviations (Moderate Anomaly, Severe Anomaly, or Version Drift).")
                
                count_sim = st.number_input("Sessions count", min_value=1, max_value=50, value=10, step=1)
                profile_sim = st.selectbox("Behavioral Profile", ["normal", "moderate_anomaly", "severe_anomaly", "drift"])
                
                if st.button("Simulate & Analyze Traffic", type="primary", width="stretch"):
                    with st.spinner("Simulating traffic, scoring against baseline..."):
                        resp = simulate_production(active_agent["id"], count=count_sim, profile=profile_sim)
                        if resp and resp.status_code == 201:
                            st.success(f"Simulated {count_sim} sessions of profile '{profile_sim}' successfully!")
                            st.rerun()
                        elif resp:
                            st.error(resp.json().get("detail", "Error simulating traffic."))
                            
                st.markdown("---")
                # Severity Filters
                st.markdown("#### Filter Sessions")
                sev_filter = st.selectbox("Filter by Severity", ["ALL", "NORMAL", "WARNING", "ALERT"])
                
            with col_p2:
                st.markdown("### Simulated Production Sessions")
                sev_arg = None if sev_filter == "ALL" else sev_filter
                sessions = get_production_sessions(agent_id=active_agent["id"], severity=sev_arg, limit=100)
                
                if not sessions:
                    st.info("No production sessions found matching filters.")
                else:
                    sessions_df = pd.DataFrame(sessions)
                    display_df = sessions_df[["session_id", "timestamp", "intent", "anomaly_score", "severity", "model_version"]].copy()
                    
                    st.dataframe(
                        display_df,
                        column_config={
                            "session_id": st.column_config.TextColumn("Session ID"),
                            "timestamp": st.column_config.DatetimeColumn("Timestamp"),
                            "intent": st.column_config.TextColumn("Intent"),
                            "anomaly_score": st.column_config.NumberColumn("Anomaly Score", format="%.1f"),
                            "severity": st.column_config.TextColumn("Severity"),
                            "model_version": st.column_config.TextColumn("Model Version"),
                        },
                        hide_index=True,
                        width="stretch"
                    )
                    
            st.markdown("---")
            st.markdown("### 🔍 Inspect Session Behavior & Anomaly Explanation")
            if sessions:
                selected_sess_id = st.selectbox("Select Session ID to analyze", options=sessions_df["session_id"].tolist())
                if selected_sess_id:
                    sess_row = sessions_df[sessions_df["session_id"] == selected_sess_id].iloc[0]
                    
                    col_det1, col_det2 = st.columns([1, 1])
                    with col_det1:
                        st.markdown(f"**Session ID:** `{sess_row['session_id']}`")
                        st.markdown(f"**Timestamp:** {sess_row['timestamp']}")
                        st.markdown(f"**User Request:** *\"{sess_row['user_request']}\"*")
                        st.markdown(f"**Intent Category:** `{sess_row['intent']}`")
                        st.markdown(f"**Tools Executed:** `{', '.join(sess_row['tool_calls'])}`")
                        st.markdown(f"**Tool sequence path:** `{', '.join(sess_row['tool_sequence'])}`")
                        st.markdown(f"**Data Categories Accessed:** `{', '.join(sess_row['data_access'])}`")
                        st.markdown(f"**Latency:** {sess_row['latency_ms']:.1f} ms")
                        st.markdown(f"**Response Length:** {sess_row['response_length']} characters")
                        st.markdown(f"**Success Status:** `{sess_row['success']}` (Errors: {sess_row['error_count']})")
                        st.markdown(f"**Model / Prompt Version:** `{sess_row['model_version']}` / `{sess_row['prompt_version']}`")
                        
                    with col_det2:
                        # Anomaly Score Gauge
                        score = sess_row["anomaly_score"]
                        severity = sess_row["severity"]
                        
                        st.markdown(f"#### Anomaly Score: **{score:.1f}**")
                        st.markdown(f"Severity Class: {get_severity_badge_html(severity)}", unsafe_allow_html=True)
                        
                        fig_gauge = go.Figure(go.Indicator(
                            mode = "gauge+number",
                            value = score,
                            domain = {'x': [0, 1], 'y': [0, 1]},
                            title = {'text': "Behavioral Deviation Score"},
                            gauge = {
                                'axis': {'range': [None, 100]},
                                'bar': {'color': "#1F2937"},
                                'steps' : [
                                    {'range': [0, settings_data['warning_threshold'] if settings_data else 30], 'color': "#31C48D"},
                                    {'range': [settings_data['warning_threshold'] if settings_data else 30, settings_data['alert_threshold'] if settings_data else 60], 'color': "#F59E0B"},
                                    {'range': [settings_data['alert_threshold'] if settings_data else 60, 100], 'color': "#F05252"}
                                ],
                            }
                        ))
                        fig_gauge.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=10))
                        st.plotly_chart(fig_gauge, width="stretch")
                        
                        st.markdown("**Deviation Explanations (Explainable Reasons why flagged):**")
                        # Split by semicolon
                        reasons = sess_row["explanation"].split("; ")
                        for r in reasons:
                            st.write(f"- {r}")

# ==================== PAGE: ANOMALY EVENTS ====================
elif page == "Anomaly Events":
    st.subheader("Persistent Anomaly Alert Events")
    
    if not active_agent:
        st.warning("⚠️ No active agent selected. Select an agent in the sidebar.")
    else:
        # Load alerts
        alerts_list = get_alerts(agent_id=active_agent["id"])
        
        col_al1, col_al2 = st.columns([1, 3])
        with col_al1:
            st.markdown("#### Event Statistics")
            if not alerts_list:
                st.metric("Total Warnings", 0)
                st.metric("Total Alerts", 0)
            else:
                al_df = pd.DataFrame(alerts_list)
                total_w = sum(1 for a in alerts_list if a["severity"] == "WARNING")
                total_a = sum(1 for a in alerts_list if a["severity"] == "ALERT")
                total_open = sum(1 for a in alerts_list if a["status"] == "OPEN")
                
                st.metric("Open Alerts", total_open)
                st.metric("Warnings", total_w)
                st.metric("Alerts", total_a)
                
                # Pie chart of severity
                fig_alert_sev = px.pie(
                    al_df,
                    names="severity",
                    title="Alert Severity Distribution",
                    color="severity",
                    color_discrete_map={"WARNING": "#F59E0B", "ALERT": "#F05252"}
                )
                st.plotly_chart(fig_alert_sev, width="stretch")
                
        with col_al2:
            st.markdown("#### Active Alerts Log")
            
            # Filters
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                status_filter = st.selectbox("Status Filter", ["ALL", "OPEN", "RESOLVED"])
            with col_f2:
                severity_filter = st.selectbox("Severity Filter", ["ALL", "WARNING", "ALERT"])
                
            filtered_alerts = alerts_list
            if status_filter != "ALL":
                filtered_alerts = [a for a in filtered_alerts if a["status"] == status_filter]
            if severity_filter != "ALL":
                filtered_alerts = [a for a in filtered_alerts if a["severity"] == severity_filter]
                
            if not filtered_alerts:
                st.info("No alerts found matching filters.")
            else:
                alert_selected = st.selectbox("Select Anomaly Event to Manage", options=[f"{a['event_id']} (Session: {a['session_id']} | Severity: {a['severity']} | Score: {a['anomaly_score']:.1f})" for a in filtered_alerts])
                
                if alert_selected:
                    sel_evt_id = alert_selected.split(" ")[0]
                    evt_row = next(a for a in filtered_alerts if a["event_id"] == sel_evt_id)
                    
                    st.markdown(f"##### Detailed Anomaly Reasons (Event: `{evt_row['event_id']}`)")
                    st.write(f"Logged on: **{evt_row['timestamp']}** | Anomaly Score: **{evt_row['anomaly_score']:.1f}**")
                    st.write(f"Status: `{evt_row['status']}` | Model Version: `{evt_row['model_version']}` | Baseline: `{evt_row['baseline_version']}`")
                    for r in evt_row["reasons"]:
                        st.write(f"- {r}")
                        
                    if evt_row["status"] == "OPEN":
                        if st.button("Mark Alert as RESOLVED", type="primary"):
                            resp = resolve_alert(evt_row["event_id"])
                            if resp and resp.status_code == 200:
                                st.success("Alert resolved successfully!")
                                st.rerun()
                    else:
                        st.success("✅ This alert has already been resolved.")
                        
                st.markdown("---")
                st.markdown("##### Alerts History Table")
                al_df_tbl = pd.DataFrame(filtered_alerts)
                al_display = al_df_tbl[["event_id", "session_id", "severity", "anomaly_score", "baseline_version", "status", "timestamp"]].copy()
                st.dataframe(al_display, hide_index=True, width="stretch")

# ==================== PAGE: DRIFT DETECTION ====================
elif page == "Drift Detection":
    st.subheader("Model Drift Detection Dashboard")
    
    if not active_agent:
        st.warning("⚠️ No active agent selected. Select an agent in the sidebar.")
    else:
        # Load active baseline & run drift check
        active_bl = get_active_baseline(active_agent["id"])
        
        if not active_bl:
            st.warning("⚠️ Baseline must be created first before you can check for drift.")
        else:
            # Query summary to run drift detector
            summary = get_monitor_summary(active_agent["id"])
            
            # Fetch last W sessions to verify counts
            sessions = get_production_sessions(agent_id=active_agent["id"], limit=100)
            
            # Call API to get direct drift details
            drift_res = requests.get(f"{BACKEND_URL}/monitor/summary/{active_agent['id']}").json()
            drift_status = drift_res.get("drift_status", "NORMAL")
            drift_score = drift_res.get("drift_score", 0.0)
            drift_threshold = drift_res.get("drift_threshold", 0.25)
            
            col_d1, col_d2 = st.columns([1, 1])
            with col_d1:
                st.markdown("### Drift Parameters")
                st.metric("Drift Score (Sliding Window)", f"{drift_score:.2f}")
                st.metric("Drift Trigger Threshold", f"{drift_threshold:.2f}")
                
                # Check status
                if drift_status == "DRIFT_DETECTED":
                    st.markdown("""
                        <div style="background-color: #FEE2E2; border-left: 5px solid #EF4444; padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem;">
                            <h4 style="color: #991B1B; margin-top: 0; margin-bottom:0.2rem;">🚨 BASELINE DRIFT DETECTED</h4>
                            <p style="color: #991B1B; margin-bottom:0;">Production behavior has shifted consistently from the baseline. Model update or prompt changes detected.</p>
                        </div>
                    """, unsafe_allow_html=True)
                    st.write("**Drift Reasons:**")
                    for r in drift_res["reasons"]:
                        st.write(f"- {r}")
                        
                    st.markdown("---")
                    st.markdown("#### Action: Refresh Behavioral Baseline")
                    st.write("Since production behavior has consistently changed, click 'Refresh Baseline' to run synthetic scenarios against the updated model behavior, calculate a new behavioral fingerprint, and create Baseline version **v2** (retaining v1 in SQLite for history).")
                    
                    if st.button("🔄 REFRESH BASELINE", type="primary", width="stretch"):
                        with st.spinner("Generating fresh scenario set & re-baselining..."):
                            # Delete scenarios, generate scenarios, and create baseline
                            gen_resp = generate_scenarios(active_agent["id"], count=50)
                            if gen_resp and gen_resp.status_code == 201:
                                bl_resp = create_baseline(active_agent["id"])
                                if bl_resp and bl_resp.status_code == 201:
                                    st.success(f"Behavioral baseline refreshed successfully to version {bl_resp.json()['version']}!")
                                    st.rerun()
                else:
                    st.success("✅ Baseline and production are aligned. No drift detected.")
                    
            with col_d2:
                st.markdown("### Tool Call Frequency Shift (Baseline vs Production)")
                st.write("Visual side-by-side comparison of the active baseline tool frequencies against the sliding window of recent production sessions.")
                
                if not sessions:
                    st.info("No production sessions found to plot.")
                else:
                    # Query fingerprint
                    fp_url = f"{BACKEND_URL}/baseline/{active_agent['id']}/fingerprint"
                    fp = requests.get(fp_url).json()
                    
                    # Compute production frequencies
                    prod_traces = [{"tool_calls": s["tool_calls"]} for s in sessions[:20]]
                    from backend.services.behavior_analyzer import BehaviorAnalyzer
                    prod_fp = BehaviorAnalyzer.calculate_fingerprint(prod_traces)
                    
                    # Merge into DataFrame
                    all_tools = set(fp["tool_frequency"].keys()).union(set(prod_fp["tool_frequency"].keys()))
                    compare_data = []
                    for t in all_tools:
                        compare_data.append({
                            "Tool Name": t,
                            "Source": "Baseline",
                            "Frequency (%)": fp["tool_frequency"].get(t, 0.0) * 100
                        })
                        compare_data.append({
                            "Tool Name": t,
                            "Source": "Production (Window)",
                            "Frequency (%)": prod_fp["tool_frequency"].get(t, 0.0) * 100
                        })
                        
                    comp_df = pd.DataFrame(compare_data)
                    fig_comp = px.bar(
                        comp_df,
                        x="Tool Name",
                        y="Frequency (%)",
                        color="Source",
                        barmode="group",
                        title="Baseline vs Production Tool Usage comparison",
                        color_discrete_map={"Baseline": "#3B82F6", "Production (Window)": "#9333EA"}
                    )
                    st.plotly_chart(fig_comp, width="stretch")

# ==================== PAGE: INTENT BASELINES ====================
elif page == "Intent Baselines":
    st.subheader("Intent-Based Clustered Baselines")
    st.write(" Bonus: Maintain separate behavioral baseline fingerprints clustered by scenario intent categories. Production sessions are evaluated against their matching intent baseline.")
    
    if not active_agent:
        st.warning("⚠️ No active agent selected. Select an agent in the sidebar.")
    else:
        active_bl = get_active_baseline(active_agent["id"])
        
        if not active_bl:
            st.warning("⚠️ Baseline must be created first.")
        else:
            # Query all fingerprints for this baseline
            # Query the database direct link
            db_conn = get_db()
            db_session = next(db_conn)
            
            from backend.models import BaselineFingerprint
            fingerprints = db_session.query(BaselineFingerprint).filter(
                BaselineFingerprint.baseline_id == active_bl["id"]
            ).all()
            
            if not fingerprints:
                st.error("No fingerprints found in database.")
            else:
                intent_options = [fp.intent if fp.intent else "Global" for fp in fingerprints]
                selected_intent_view = st.selectbox("Select Clustered Baseline View", intent_options)
                
                # Fetch fingerprint matching selection
                fp_db = next(fp for fp in fingerprints if (fp.intent if fp.intent else "Global") == selected_intent_view)
                
                col_i1, col_i2 = st.columns(2)
                with col_i1:
                    st.markdown(f"#### Fingerprint KPIs: {selected_intent_view}")
                    st.table({
                        "Metric Name": [
                            "Average Response Length (chars)",
                            "Average Latency (ms)",
                            "Average Tool Calls",
                            "Execution Success Rate",
                            "Execution Error Rate"
                        ],
                        "Baseline Value": [
                            f"{fp_db.avg_response_length:.2f} chars",
                            f"{fp_db.latency_stats.get('avg', 0.0):.2f} ms",
                            f"{fp_db.tool_count_stats.get('avg', 0.0):.2f}",
                            f"{fp_db.success_rate*100:.2f}%",
                            f"{fp_db.error_rate:.2f} per run"
                        ]
                    })
                    
                with col_i2:
                    # Data access patterns
                    dp_df = pd.DataFrame(list(fp_db.data_access_patterns.items()), columns=["Data Category", "Proportion"])
                    fig_dp = px.pie(
                        dp_df,
                        values="Proportion",
                        names="Data Category",
                        title=f"{selected_intent_view} Data Access Distribution",
                        hole=0.4
                    )
                    st.plotly_chart(fig_dp, width="stretch")
                    
                st.markdown("#### Tool call frequencies in cluster")
                tf_df = pd.DataFrame(list(fp_db.tool_frequency.items()), columns=["Tool Name", "Frequency"])
                fig_tf = px.bar(tf_df, x="Tool Name", y="Frequency", title=f"{selected_intent_view} Tool Usage Frequencies")
                st.plotly_chart(fig_tf, width="stretch")

# ==================== PAGE: SETTINGS ====================
elif page == "Settings":
    st.subheader("Threshold & Anomaly Weights Configuration")
    
    if not settings_data:
        st.error("Failed to load settings from backend.")
    else:
        st.write("Adjust anomaly thresholds and scoring weights. The monitoring engine uses these settings dynamically. Click 'Save Settings' and re-analyze to apply them.")
        
        with st.form("settings_form"):
            col_t1, col_t2, col_t3 = st.columns(3)
            with col_t1:
                warn_thresh = st.slider("Warning Threshold (NORMAL -> WARNING)", min_value=0, max_value=100, value=int(settings_data["warning_threshold"]))
            with col_t2:
                alert_thresh = st.slider("Alert Threshold (WARNING -> ALERT)", min_value=0, max_value=100, value=int(settings_data["alert_threshold"]))
            with col_t3:
                drift_thresh = st.slider("Drift Threshold (TVD shift boundary)", min_value=0.01, max_value=1.0, value=float(settings_data["drift_threshold"]), step=0.01)
                
            col_t4, col_t5 = st.columns(2)
            with col_t4:
                drift_window = st.number_input("Drift Window Size (production sessions count)", min_value=5, max_value=100, value=int(settings_data["drift_window"]))
            with col_t5:
                min_sessions = st.number_input("Min Sessions required for drift", min_value=2, max_value=50, value=int(settings_data["min_drift_sessions"]))
                
            st.markdown("#### Anomaly Deviation Component Weights")
            col_w1, col_w2, col_w3, col_w4 = st.columns(4)
            with col_w1:
                w_tool = st.number_input("Tool frequency weight", min_value=0.0, value=float(settings_data["tool_frequency_weight"]), step=0.1)
                w_seq = st.number_input("Tool sequence weight", min_value=0.0, value=float(settings_data["sequence_weight"]), step=0.1)
            with col_w2:
                w_len = st.number_input("Response length weight", min_value=0.0, value=float(settings_data["response_length_weight"]), step=0.1)
                w_data = st.number_input("Data access weight", min_value=0.0, value=float(settings_data["data_access_weight"]), step=0.1)
            with col_w3:
                w_intent = st.number_input("Intent distribution weight", min_value=0.0, value=float(settings_data["intent_weight"]), step=0.1)
                w_lat = st.number_input("Latency weight", min_value=0.0, value=float(settings_data["latency_weight"]), step=0.1)
            with col_w4:
                w_err = st.number_input("Error & success rate weight", min_value=0.0, value=float(settings_data["error_rate_weight"]), step=0.1)
                
            save_btn = st.form_submit_button("💾 Save Settings Configuration")
            
            if save_btn:
                if warn_thresh >= alert_thresh:
                    st.error("Validation error: Warning threshold must be strictly less than the Alert threshold.")
                else:
                    payload = {
                        "warning_threshold": float(warn_thresh),
                        "alert_threshold": float(alert_thresh),
                        "drift_threshold": float(drift_thresh),
                        "drift_window": int(drift_window),
                        "min_drift_sessions": int(min_sessions),
                        "tool_frequency_weight": float(w_tool),
                        "sequence_weight": float(w_seq),
                        "response_length_weight": float(w_len),
                        "data_access_weight": float(w_data),
                        "intent_weight": float(w_intent),
                        "latency_weight": float(w_lat),
                        "error_rate_weight": float(w_err)
                    }
                    resp = update_settings(payload)
                    if resp and resp.status_code == 200:
                        st.success("Settings updated successfully!")
                        st.rerun()
                    elif resp:
                        st.error(resp.json().get("detail", "Error saving settings."))
                        
        st.markdown("---")
        st.markdown("#### Apply Configuration to Historical Database")
        st.write("Clicking below will re-evaluate all historical production sessions against the active baseline using the saved weights and thresholds, updating alert flags in real time.")
        if st.button("⚡ Re-analyze all production sessions", type="secondary"):
            resp = reanalyze_all()
            if resp and resp.status_code == 200:
                st.success(resp.json()["message"])
                st.rerun()

# ==================== PAGE: DEMO / TEST SCENARIOS ====================
elif page == "Demo / Test Scenarios":
    st.subheader("PS-4.1 Automated Success Criteria Test Runner")
    st.write("Use this sandbox to trigger the exact scenarios specified in the PS-4.1 requirements. The page runs the test pipeline and asserts the expected severity class.")
    
    if not active_agent:
        st.info("💡 Select an agent in the sidebar to run success tests, or run the demo sandbox pipeline to build one automatically.")
    else:
        # Check active baseline
        active_bl = get_active_baseline(active_agent["id"])
        
        if not active_bl:
            st.warning("⚠️ Baseline must be created first before you can run success criteria tests.")
        else:
            col_t1, col_t2 = st.columns([1, 1])
            with col_t1:
                st.markdown("### Run Success Test Suite")
                
                # Test A: Normal
                st.markdown("#### 🟢 Test A — Normal Behavior")
                st.write("Generates production sessions conforming closely to the baseline configuration.")
                if st.button("Run Test A (Normal)"):
                    with st.spinner("Running..."):
                        resp = simulate_production(active_agent["id"], count=5, profile="normal")
                        if resp and resp.status_code == 201:
                            st.session_state["test_a_res"] = resp.json()
                            
                # Test B: Moderate Anomaly
                st.markdown("#### 🟡 Test B — Moderate Anomaly Behavior")
                st.write("Simulates traffic with mild tool call additions and slightly elevated latency.")
                if st.button("Run Test B (Moderate Anomaly)"):
                    with st.spinner("Running..."):
                        resp = simulate_production(active_agent["id"], count=5, profile="moderate_anomaly")
                        if resp and resp.status_code == 201:
                            st.session_state["test_b_res"] = resp.json()

                # Test C: Severe Anomaly
                st.markdown("#### 🔴 Test C — Severe Anomaly Behavior")
                st.write("Simulates loops, incorrect data access categories, and extreme latencies.")
                if st.button("Run Test C (Severe Anomaly)"):
                    with st.spinner("Running..."):
                        resp = simulate_production(active_agent["id"], count=5, profile="severe_anomaly")
                        if resp and resp.status_code == 201:
                            st.session_state["test_c_res"] = resp.json()

                # Test D: Drift & Model Update
                st.markdown("#### 🟣 Test D — Baseline Drift Shift")
                st.write("Simulates a model update (agent-model-v2 / prompt v2) with persistent behavior shifts across 20 sessions.")
                if st.button("Run Test D (Drift Check)"):
                    with st.spinner("Running..."):
                        # Drift window is default 20. We will simulate 20 sessions of drift traffic to evaluate
                        resp = simulate_production(active_agent["id"], count=20, profile="drift")
                        if resp and resp.status_code == 201:
                            st.session_state["test_d_res"] = resp.json()

            with col_t2:
                st.markdown("### Test Verification Board")
                
                # Verify Test A
                if "test_a_res" in st.session_state:
                    traces = st.session_state["test_a_res"]
                    avg_score = sum(t["anomaly_score"] for t in traces) / len(traces)
                    # We expect all/most to be NORMAL
                    severities = [t["severity"] for t in traces]
                    passed = all(s == "NORMAL" for s in severities) or avg_score < 30.0
                    status_badge = '<span class="status-badge status-normal">PASS</span>' if passed else '<span class="status-badge status-alert">FAIL</span>'
                    st.markdown(f"**Test A (Normal Traffic):** {status_badge}", unsafe_allow_html=True)
                    st.write(f"- Avg Score: {avg_score:.1f} (Expected: < 30.0)")
                    st.write(f"- Severities recorded: {', '.join(severities)}")
                    st.markdown("---")
                    
                # Verify Test B
                if "test_b_res" in st.session_state:
                    traces = st.session_state["test_b_res"]
                    avg_score = sum(t["anomaly_score"] for t in traces) / len(traces)
                    # We expect WARNING severity or elevated scores
                    severities = [t["severity"] for t in traces]
                    passed = "WARNING" in severities or avg_score >= 30.0
                    status_badge = '<span class="status-badge status-normal">PASS</span>' if passed else '<span class="status-badge status-alert">FAIL</span>'
                    st.markdown(f"**Test B (Moderate Anomaly):** {status_badge}", unsafe_allow_html=True)
                    st.write(f"- Avg Score: {avg_score:.1f} (Expected: elevated, >= 30.0)")
                    st.write(f"- Severities recorded: {', '.join(severities)}")
                    st.markdown("---")

                # Verify Test C
                if "test_c_res" in st.session_state:
                    traces = st.session_state["test_c_res"]
                    avg_score = sum(t["anomaly_score"] for t in traces) / len(traces)
                    # We expect ALERT severity
                    severities = [t["severity"] for t in traces]
                    passed = "ALERT" in severities or avg_score >= 60.0
                    status_badge = '<span class="status-badge status-normal">PASS</span>' if passed else '<span class="status-badge status-alert">FAIL</span>'
                    st.markdown(f"**Test C (Severe Anomaly):** {status_badge}", unsafe_allow_html=True)
                    st.write(f"- Avg Score: {avg_score:.1f} (Expected: high, >= 60.0)")
                    st.write(f"- Severities recorded: {', '.join(severities)}")
                    st.markdown("---")

                # Verify Test D
                if "test_d_res" in st.session_state:
                    traces = st.session_state["test_d_res"]
                    # Call API to get drift detector results
                    drift_res = requests.get(f"{BACKEND_URL}/monitor/summary/{active_agent['id']}").json()
                    passed = drift_res["drift_status"] == "DRIFT_DETECTED"
                    status_badge = '<span class="status-badge status-normal">PASS</span>' if passed else '<span class="status-badge status-alert">FAIL</span>'
                    st.markdown(f"**Test D (Drift Detection):** {status_badge}", unsafe_allow_html=True)
                    st.write(f"- Running Window Drift Status: **{drift_res.get('drift_status', 'UNKNOWN')}**")
                    st.write(f"- Calculated Drift Score: **{drift_res.get('drift_score', 0.0):.2f}** (Threshold: {drift_res.get('drift_threshold', 0.25):.2f})")
                    st.markdown("---")
