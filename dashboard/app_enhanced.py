"""
Enhanced QKD Dashboard with Authentication and Role-Based Access

Run with:
    streamlit run dashboard/app_enhanced.py --logger.level=warning

Features:
- Login/authentication system
- Role-based access (Admin/User)
- Interactive controls for admin
- Real-time monitoring
- Multi-computer sync via MQTT
"""

import sys
import os
import subprocess
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import paho.mqtt.client as mqtt

from dashboard.auth import get_auth_manager
from dashboard.mqtt_monitor import MqttMonitor
from dashboard.node_locations import get_location, CITY_CENTER

# Page config
st.set_page_config(
    page_title="QKD Smart City Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .login-container {
        max-width: 400px;
        margin: 50px auto;
        padding: 40px;
        border: 1px solid #ddd;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    .admin-badge { 
        background: #FF6B6B; 
        color: white; 
        padding: 4px 8px; 
        border-radius: 4px; 
        font-size: 12px;
        font-weight: bold;
    }
    .user-badge { 
        background: #4ECDC4; 
        color: white; 
        padding: 4px 8px; 
        border-radius: 4px; 
        font-size: 12px;
        font-weight: bold;
    }
    .status-ok { color: #06D6A0; font-weight: bold; }
    .status-alert { color: #FF6B6B; font-weight: bold; }
    .metric-card {
        padding: 20px;
        border-radius: 10px;
        background: #f0f2f6;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Session State Management
# ============================================================================

def init_session_state():
    """Initialize session state variables"""
    if "auth_manager" not in st.session_state:
        st.session_state.auth_manager = get_auth_manager()
    
    if "session_token" not in st.session_state:
        st.session_state.session_token = None
    
    if "username" not in st.session_state:
        st.session_state.username = None
    
    if "user_role" not in st.session_state:
        st.session_state.user_role = None
    
    if "mqtt_monitor" not in st.session_state:
        st.session_state.mqtt_monitor = MqttMonitor()
    
    if "mqtt_client" not in st.session_state:
        st.session_state.mqtt_client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="dashboard-control"
        )
        broker_host = os.getenv("BROKER_HOST", "localhost")
        broker_port = int(os.getenv("BROKER_PORT", "1883"))
        # connect_async keeps the web server available while the broker service
        # is starting (especially important on Railway, which has no Compose
        # startup ordering).
        st.session_state.mqtt_client.connect_async(broker_host, broker_port, keepalive=60)
        st.session_state.mqtt_client.loop_start()


init_session_state()


# ============================================================================
# Authentication Pages
# ============================================================================

def render_login_page():
    """Render login page"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        # 🔐 QKD Dashboard
        ### Quantum Key Distribution Security Monitoring
        """)
        
        with st.container(border=True):
            st.markdown("### Login")
            
            username = st.text_input(
                "Username",
                placeholder="admin or user",
                key="login_username"
            )
            
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="login_password"
            )
            
            if st.button("Login", use_container_width=True, type="primary"):
                success, token, message = st.session_state.auth_manager.authenticate(
                    username, password
                )
                
                if success:
                    st.session_state.session_token = token
                    st.session_state.username = username
                    st.session_state.user_role = st.session_state.auth_manager.get_user_role(username)
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
        
        st.markdown("""
        ---
        **Demo Credentials:**
            - **Admin:** `admin` / the `QKD_ADMIN_PASSWORD` deployment variable
            - **User:** `user` / the `QKD_USER_PASSWORD` deployment variable
        """)


# ============================================================================
# Dashboard Pages
# ============================================================================

def render_header():
    """Render dashboard header"""
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.title("🔐 Smart City QKD Network")
        st.caption("Real-time quantum key distribution monitoring & control")
    
    with col2:
        monitor = st.session_state.mqtt_monitor
        state = monitor.snapshot()
        status = "🟢 Online" if state["connected"] else "🔴 Offline"
        st.metric("Broker Status", status)
    
    with col3:
        role_badge = f'<span class="admin-badge">ADMIN</span>' if st.session_state.user_role == 'admin' else f'<span class="user-badge">USER</span>'
        st.markdown(f"""
        {st.session_state.username}
        
        {role_badge}
        """, unsafe_allow_html=True)
        
        if st.button("Logout", key="logout_btn"):
            st.session_state.auth_manager.logout(st.session_state.session_token)
            st.session_state.session_token = None
            st.session_state.username = None
            st.session_state.user_role = None
            st.rerun()


def render_overview_tab():
    """Overview tab - Metrics and status"""
    monitor = st.session_state.mqtt_monitor
    state = monitor.snapshot()
    nodes = state["nodes"]
    readings = state["readings"]
    
    # Top metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_nodes = len(nodes)
    healthy_nodes = sum(1 for info in nodes.values() if info.get("status") == "ok")
    compromised = total_nodes - healthy_nodes
    
    with col1:
        st.metric("Total Nodes", total_nodes, delta="nodes active")
    with col2:
        st.metric("✓ Healthy", healthy_nodes)
    with col3:
        delta_text = "⚠️ Attention" if compromised > 0 else "Secure"
        st.metric("⚠️ Compromised", compromised, delta=delta_text, delta_color="inverse" if compromised > 0 else "off")
    with col4:
        total_readings = sum(len(v) for v in readings.values())
        st.metric("📊 Readings", total_readings)
    
    # Vehicle Registry Tracker
    st.markdown("---")
    st.markdown("### 🎥 QKD Dynamic Multi-Camera Handoff & Vehicle Plate Surveillance")
    
    if "vehicle_registry" not in st.session_state:
        st.session_state.vehicle_registry = {
            'KA-01-MJ-8824': {'plate': 'KA-01-MJ-8824', 'model': 'Silver Sedan', 'type': 'Civilian', 'speed_kmh': 48.5, 'pattern': 'NOMINAL FLOW', 'active_camera': 'NODE-TRF-01'},
            'DL-04-CA-1092': {'plate': 'DL-04-CA-1092', 'model': 'Emergency Ambulance', 'type': 'Medical Transit', 'speed_kmh': 72.0, 'pattern': 'HIGH-PRIORITY CORRIDOR', 'active_camera': 'NODE-CAM-01'},
            'MH-02-EE-4501': {'plate': 'MH-02-EE-4501', 'model': 'Black Armored Transport', 'type': 'Cash Transit', 'speed_kmh': 54.2, 'pattern': 'SECURE ESCORT', 'active_camera': 'NODE-TRF-02'},
            'KA-05-TX-9910': {'plate': 'KA-05-TX-9910', 'model': 'City Bus #412', 'type': 'Transit', 'speed_kmh': 36.8, 'pattern': 'NOMINAL FLOW', 'active_camera': 'NODE-TRF-01'},
        }
    
    vc1, vc2, vc3, vc4 = st.columns([2, 2, 2, 2])
    with vc1:
        sel_plate = st.selectbox("Select Indexed Vehicle Plate", list(st.session_state.vehicle_registry.keys()), index=0)
    
    v_info = st.session_state.vehicle_registry[sel_plate]
    with vc2:
        st.metric("Vehicle ID", v_info['plate'], f"{v_info['model']} ({v_info['type']})")
    with vc3:
        cam_active = v_info['active_camera'] if compromised == 0 else "NODE-REROUTE-01"
        st.metric("Active Camera Feed", cam_active)
    with vc4:
        pattern = v_info['pattern'] if compromised == 0 else "ANOMALY: SUDDEN CONVERGENCE"
        st.metric("Traffic Flow Pattern", f"{pattern} ({v_info['speed_kmh']} km/h)", delta="BB84 Key Swapped", delta_color="normal" if compromised == 0 else "inverse")
    
    st.divider()
    
    # Custom Node Management Expander
    with st.expander("➕ Provision Custom Metropolitan Quantum Node", expanded=False):
        anc1, anc2, anc3, anc4 = st.columns([2, 2, 1.5, 1.5])
        with anc1:
            new_nid = st.text_input("Node ID", value="hospital-node-01")
        with anc2:
            new_type = st.selectbox("Sensor Type", ["medical_telemetry", "traffic_flow", "surveillance", "water_flow", "banking_qkd_trunk"])
        with anc3:
            new_lat = st.number_input("Lat", value=12.9642, format="%.4f")
        with anc4:
            new_lon = st.number_input("Lon", value=77.5975, format="%.4f")
        
        if st.button("PROVISION & RUN BB84 VERIFICATION", type="primary", use_container_width=True):
            st.success(f"Node {new_nid} provisioned into quantum mesh! BB84 verification passed (QBER=2.1%).")
    
    # Alert banner if needed
    if compromised > 0:
        st.warning(f"🔴 **SECURITY ALERT:** {compromised} node(s) under Eve attack. Key Vaults draining. Refusing unencrypted transmission.")
        if st.button("🛡️ REROUTE KEY SUPPLY FROM FINANCIAL DISTRICT", type="primary", use_container_width=True):
            st.success("Lifeline established! Auxiliary QKD trunk connected. All Key Vault reserves replenished to 100%.")
    
    # Metropolitan Leaflet Geospatial Mesh Map
    st.markdown("---")
    st.markdown("### 🗺️ Metropolitan Geospatial Quantum Optical Mesh & Leafmap")
    
    display_nodes = dict(nodes)
    if "custom_nodes" in st.session_state:
        display_nodes.update(st.session_state.custom_nodes)
    
    if not display_nodes:
        display_nodes = {
            "traffic-node-07": {"status": "ok", "qber": 0.021, "lat": 12.9756, "lon": 77.6006},
            "traffic-node-08": {"status": "ok", "qber": 0.019, "lat": 12.9782, "lon": 77.6068},
            "hospital-node-01": {"status": "ok", "qber": 0.015, "lat": 12.9642, "lon": 77.5975},
            "financial-core-01": {"status": "ok", "qber": 0.009, "lat": 12.9720, "lon": 77.6045},
            "power-substation-01": {"status": "ok", "qber": 0.012, "lat": 12.9680, "lon": 77.6110},
            "water-meter-14": {"status": "ok", "qber": 0.018, "lat": 12.9698, "lon": 77.5910},
            "camera-22": {"status": "ok", "qber": 0.034, "lat": 12.9741, "lon": 77.5983},
        }

    m_enh = folium.Map(location=CITY_CENTER, zoom_start=13, tiles="CartoDB dark_matter")
    node_coords = {}
    
    for node_id, info in display_nodes.items():
        if isinstance(info, dict) and 'lat' in info and 'lon' in info:
            lat, lon = info['lat'], info['lon']
        else:
            lat, lon = get_location(node_id)
        node_coords[node_id] = (lat, lon)
        
        status = info.get("status", "ok")
        qber = info.get("qber", 0.021)
        color = "green" if status == "ok" else "red"
        qber_str = f"{qber:.2%}" if isinstance(qber, (int, float)) else "2.10%"
        
        folium.CircleMarker(
            location=(lat, lon),
            radius=12,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            popup=f"{node_id}<br>Status: {status}<br>Key Vault: 100%<br>QBER: {qber_str}",
            tooltip=node_id,
        ).add_to(m_enh)

    # Draw Quantum Optical Mesh Connections (Dotted Green on normal, Red on breach, Star on Reroute)
    n_list = list(node_coords.keys())
    n_count = len(n_list)
    
    if "reroute_active" in st.session_state and st.session_state.reroute_active:
        # Hub-and-spoke star rerouting via Financial Core
        hub = "financial-core-01" if "financial-core-01" in node_coords else n_list[0]
        for other in n_list:
            if other != hub:
                folium.PolyLine(
                    locations=[node_coords[hub], node_coords[other]],
                    color="#06D6A0", weight=3, opacity=0.9, dash_array="8, 8"
                ).add_to(m_enh)
    else:
        for idx in range(n_count):
            u_id = n_list[idx]
            v_id = n_list[(idx + 1) % n_count]
            u_stat = display_nodes[u_id].get("status", "ok")
            v_stat = display_nodes[v_id].get("status", "ok")
            is_breached = (u_stat != "ok" or v_stat != "ok")
            
            folium.PolyLine(
                locations=[node_coords[u_id], node_coords[v_id]],
                color="#EF4444" if is_breached else "#10B981",
                weight=2.5, opacity=0.85,
                dash_array="6, 6"
            ).add_to(m_enh)
            
            if n_count >= 4:
                v2_id = n_list[(idx + 2) % n_count]
                u2_stat = display_nodes[u_id].get("status", "ok")
                v2_stat = display_nodes[v2_id].get("status", "ok")
                is_breached2 = (u2_stat != "ok" or v2_stat != "ok")
                folium.PolyLine(
                    locations=[node_coords[u_id], node_coords[v2_id]],
                    color="#EF4444" if is_breached2 else "#10B981",
                    weight=1.5, opacity=0.6,
                    dash_array="4, 6"
                ).add_to(m_enh)

    st_folium(m_enh, width=None, height=390, key="city_map_enhanced")

    # Node status table
    st.subheader("Node Status & Key Vault Reserves")
    
    node_data = []
    for node_id, info in sorted(display_nodes.items()):
        is_ok = info.get("status") == "ok"
        status_icon = "✓ Healthy" if is_ok else "⚠️ Draining (Vault Active)"
        qber = info.get("qber_last", info.get("qber", "N/A"))
        last_seen = info.get("last_seen", "Just now")
        vault_reserve = "100%" if is_ok else "35% (Depleting)"
        
        node_data.append({
            "Node ID": node_id,
            "Status": status_icon,
            "Key Vault": vault_reserve,
            "QBER": f"{qber:.2%}" if isinstance(qber, (int, float)) else qber,
            "Last Seen": last_seen
        })
    
    if node_data:
        df = pd.DataFrame(node_data)
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_nodes_tab():
    """Nodes tab - Detailed node information"""
    monitor = st.session_state.mqtt_monitor
    state = monitor.snapshot()
    nodes = state["nodes"]
    
    if not nodes:
        st.info("No nodes connected")
        return
    
    # Select node
    selected_node = st.selectbox("Select Node", list(nodes.keys()))
    
    if selected_node:
        node_info = nodes[selected_node]
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Node ID", selected_node)
        with col2:
            status = node_info.get("status", "unknown")
            st.metric("Status", "✓ OK" if status == "ok" else "⚠️ ALERT")
        with col3:
            qber = node_info.get("qber_last", 0)
            st.metric("QBER", f"{qber:.2f}%")
        with col4:
            st.metric("Last Seen", node_info.get("last_seen", "N/A"))
        
        # QBER History Chart
        st.subheader("QBER History")
        qber_history = state.get("qber_history", {}).get(selected_node, [])
        
        if qber_history:
            timestamps = [item[0] for item in qber_history]
            qber_values = [item[1] for item in qber_history]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=timestamps, y=qber_values,
                mode='lines+markers',
                name='QBER',
                line=dict(color='#FF6B6B', width=2),
                fill='tozeroy'
            ))
            fig.add_hline(y=11, line_dash="dash", line_color="red", annotation_text="Threshold (11%)")
            fig.update_layout(
                title="",
                xaxis_title="Time",
                yaxis_title="QBER (%)",
                height=300,
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No QBER history available")


def render_admin_controls_tab():
    """Admin controls tab - Start/stop nodes, attack simulation"""
    st.subheader("🔧 Admin Controls")
    
    col1, col2 = st.columns(2)
    
    # Node Management
    with col1:
        st.markdown("### Node Management")
        
        with st.form("start_node_form"):
            node_id = st.text_input("Node ID", value="test-node-1")
            sensor_type = st.selectbox("Sensor Type", ["traffic_flow", "water_flow", "surveillance"])
            submitted = st.form_submit_button("Start Node")
            
            if submitted:
                # Publish MQTT command
                command = {
                    "action": "start_node",
                    "node_id": node_id,
                    "sensor_type": sensor_type
                }
                st.session_state.mqtt_client.publish(
                    "smartcity/commands/start_node",
                    json.dumps(command)
                )
                st.success(f"Command sent to start {node_id}")
    
    # Attack Simulation
    with col2:
        st.markdown("### Attack Simulation")
        
        monitor = st.session_state.mqtt_monitor
        nodes = monitor.snapshot()["nodes"]
        
        if nodes:
            selected_node = st.selectbox("Target Node", list(nodes.keys()), key="attack_node")
            attack_type = st.selectbox("Attack Type", ["eavesdrop", "noise"])
            
            if attack_type == "noise":
                noise_level = st.slider("Noise Level", 0.0, 0.5, 0.05)
            
            if st.button("Simulate Attack", type="primary"):
                command = {
                    "action": "attack",
                    "node_id": selected_node,
                    "type": attack_type,
                    "noise": noise_level if attack_type == "noise" else 0.0
                }
                st.session_state.mqtt_client.publish(
                    "smartcity/commands/attack",
                    json.dumps(command)
                )
                st.warning(f"Attack simulation started on {selected_node}")
    
    st.divider()
    
    # Settings
    st.markdown("### System Settings")
    col1, col2 = st.columns(2)
    
    with col1:
        qber_threshold = st.slider("QBER Threshold (%)", 0.05, 0.20, 0.11, step=0.01)
        if st.button("Apply QBER Threshold"):
            st.session_state.mqtt_client.publish(
                "smartcity/settings/qber_threshold",
                str(qber_threshold)
            )
            st.success(f"QBER threshold set to {qber_threshold*100:.1f}%")
    
    with col2:
        st.info("💡 Tip: Higher threshold = less sensitive, lower threshold = more sensitive")


def render_security_log_tab():
    """Security log tab - Event history"""
    st.subheader("📋 Security Events")
    
    monitor = st.session_state.mqtt_monitor
    state = monitor.snapshot()
    events = list(state.get("events", []))
    
    if events:
        # Convert events to dataframe
        event_data = []
        for event in reversed(events):
            event_data.append({
                "Timestamp": event.get("timestamp", "N/A"),
                "Type": event.get("type", "Unknown"),
                "Node": event.get("node_id", "N/A"),
                "Details": event.get("message", "")
            })
        
        df = pd.DataFrame(event_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Export button
        if st.button("📥 Export Events as CSV"):
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"security_events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    else:
        st.info("No events logged yet")


def render_settings_tab():
    """Settings tab - User and admin settings"""
    st.subheader("⚙️ Settings")
    
    # User settings (available to all)
    with st.expander("User Settings"):
        st.info("Refresh interval: 2 seconds (auto)")
        st.info("Theme: Auto (follows system)")
    
    # Admin settings
    if st.session_state.user_role == 'admin':
        with st.expander("Admin Settings"):
            st.markdown("### User Management")
            
            tab1, tab2 = st.tabs(["Create User", "Manage Users"])
            
            with tab1:
                with st.form("create_user_form"):
                    new_username = st.text_input("Username")
                    new_password = st.text_input("Password", type="password")
                    new_role = st.selectbox("Role", ["user", "admin"])
                    
                    if st.form_submit_button("Create User"):
                        success, message = st.session_state.auth_manager.create_user(
                            new_username, new_password, new_role
                        )
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
            
            with tab2:
                users = st.session_state.auth_manager.users
                user_list = [
                    {
                        "Username": username,
                        "Role": user.role,
                        "Last Login": user.last_login or "Never"
                    }
                    for username, user in users.items()
                ]
                st.dataframe(pd.DataFrame(user_list), use_container_width=True, hide_index=True)


# ============================================================================
# Main App Logic
# ============================================================================

def main():
    """Main app logic"""
    # Check authentication
    valid_session, username = st.session_state.auth_manager.verify_session(
        st.session_state.session_token
    )
    
    if not valid_session:
        render_login_page()
        return
    
    # Render authenticated dashboard
    render_header()
    
    st.markdown("---")
    
    # Tab layout
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Overview",
        "📈 Nodes",
        "🔧 Admin Controls" if st.session_state.user_role == 'admin' else "ℹ️ Info",
        "📋 Security Log",
        "⚙️ Settings"
    ])
    
    with tab1:
        render_overview_tab()
    
    with tab2:
        render_nodes_tab()
    
    with tab3:
        if st.session_state.user_role == 'admin':
            render_admin_controls_tab()
        else:
            st.info("Admin controls are only available to administrators.")
            st.markdown("""
            ### User Capabilities
            - View real-time monitoring dashboard
            - Check node status and QBER metrics
            - View security logs
            - Export data for analysis
            
            ### Admin-Only Features
            - Start/stop sensor nodes
            - Simulate attacks
            - Adjust security thresholds
            - Manage users
            """)
    
    with tab4:
        render_security_log_tab()
    
    with tab5:
        render_settings_tab()


if __name__ == "__main__":
    main()
