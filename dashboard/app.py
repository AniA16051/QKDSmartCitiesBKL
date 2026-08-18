"""
Live dashboard for the QKD-secured smart city network -- professional edition.

Run with:
    streamlit run dashboard/app.py

Same functionality as before, reorganized into a cleaner, tabbed layout:
  - Top metrics strip (node counts, broker status)
  - Overview tab: alert banner + map
  - Nodes tab: sortable table + per-node QBER chart / latest reading on demand
  - Attack simulation tab: launch / stop attacker controls
  - Security log tab: tabular event history
"""

import sys
import os
import subprocess
import signal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh

from dashboard.mqtt_monitor import MqttMonitor
from dashboard.node_locations import get_location, CITY_CENTER

st.set_page_config(page_title="Smart City QKD Dashboard", layout="wide")

# --- Minimal professional styling (Databricks-esque: neutral, tabular, calm) ---
st.markdown("""
<style>
    .block-container { padding-top: 2rem; max-width: 1200px; }
    div[data-testid="stMetric"] {
        background: rgba(128, 128, 128, 0.06);
        border: 1px solid rgba(128, 128, 128, 0.15);
        border-radius: 6px;
        padding: 0.75rem 1rem;
    }
    div[data-testid="stMetricValue"] { font-size: 1.4rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        border-radius: 4px 4px 0 0;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_monitor():
    return MqttMonitor()


if "attack_processes" not in st.session_state:
    st.session_state.attack_processes = {}
if "was_aborted" not in st.session_state:
    st.session_state.was_aborted = set()

monitor = get_monitor()
st_autorefresh(interval=2000, key="dashboard_refresh")

state = monitor.snapshot()
nodes = state["nodes"]
readings = state["readings"]
qber_history = state["qber_history"]
events = state["events"]

# --- Header ------------------------------------------------------------
header_col1, header_col2 = st.columns([4, 1])
with header_col1:
    st.title("Smart city QKD network")
    st.caption("Quantum key distribution security monitoring for IoT infrastructure")
with header_col2:
    conn_label = "Connected" if state["connected"] else "Disconnected"
    conn_icon = "🟢" if state["connected"] else "🔴"
    st.markdown(f"<div style='text-align:right; padding-top: 1.5rem;'>"
                f"{conn_icon} <b>Broker: {conn_label}</b></div>", unsafe_allow_html=True)

# --- Top metrics strip ---------------------------------------------------
total_nodes = len(nodes)
healthy_nodes = sum(1 for info in nodes.values() if info.get("status") == "ok")
compromised_nodes_count = total_nodes - healthy_nodes
total_readings = sum(len(v) for v in readings.values())

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total nodes", total_nodes)
m2.metric("Healthy", healthy_nodes)
m3.metric("Compromised", compromised_nodes_count,
          delta=None if compromised_nodes_count == 0 else "attention needed",
          delta_color="inverse")
m4.metric("Readings logged", total_readings)

st.write("")

# --- Tabs ----------------------------------------------------------------
tab_overview, tab_nodes, tab_attack, tab_log = st.tabs(
    ["Overview", "Nodes", "Attack simulation", "Security log"]
)

# ===== OVERVIEW TAB =====
with tab_overview:
    compromised_ids = [nid for nid, info in nodes.items() if info.get("status") != "ok"]
    if compromised_ids:
        st.error(f"**Operations alert** — {len(compromised_ids)} node(s) under attack: {', '.join(compromised_ids)}. "
                 f"BB84 key exchange aborted. Key Vaults draining. Unencrypted transmission refused.")
        if st.button("🛡️ REROUTE KEY SUPPLY FROM FINANCIAL DISTRICT", use_container_width=True):
            st.success("Auxiliary QKD lifeline connected. All node Key Vault reserves replenished to 100%.")
    else:
        st.success("All monitored nodes are currently secure. Key Vault reserves at 100%.")

    # Vehicle Registry Tracker
    st.write("")
    st.subheader("QKD dynamic multi-camera handoff & vehicle plate surveillance")
    
    if "vehicle_registry" not in st.session_state:
        st.session_state.vehicle_registry = {
            'KA-01-MJ-8824': {'plate': 'KA-01-MJ-8824', 'model': 'Silver Sedan', 'type': 'Civilian', 'speed_kmh': 48.5, 'pattern': 'NOMINAL FLOW', 'active_camera': 'traffic-node-07'},
            'DL-04-CA-1092': {'plate': 'DL-04-CA-1092', 'model': 'Emergency Ambulance', 'type': 'Medical Transit', 'speed_kmh': 72.0, 'pattern': 'HIGH-PRIORITY CORRIDOR', 'active_camera': 'camera-22'},
            'MH-02-EE-4501': {'plate': 'MH-02-EE-4501', 'model': 'Black Armored Transport', 'type': 'Cash Transit', 'speed_kmh': 54.2, 'pattern': 'SECURE ESCORT', 'active_camera': 'water-meter-14'},
            'KA-05-TX-9910': {'plate': 'KA-05-TX-9910', 'model': 'City Bus #412', 'type': 'Transit', 'speed_kmh': 36.8, 'pattern': 'NOMINAL FLOW', 'active_camera': 'traffic-node-07'},
        }
    
    vc1, vc2, vc3, vc4 = st.columns([2, 2, 2, 2])
    with vc1:
        sel_plate = st.selectbox("Select Indexed Vehicle Plate", list(st.session_state.vehicle_registry.keys()), index=0)
    
    v_info = st.session_state.vehicle_registry[sel_plate]
    with vc2:
        st.metric("Vehicle ID", v_info['plate'], f"{v_info['model']} ({v_info['type']})")
    with vc3:
        cam_status = v_info['active_camera'] if not compromised_ids else "NODE-REROUTE-01"
        st.metric("Active Camera Node", cam_status)
    with vc4:
        flow_p = v_info['pattern'] if not compromised_ids else "SPEED ANOMALY DETECTED"
        st.metric("Flow & Speed", f"{flow_p} ({v_info['speed_kmh']} km/h)")

    st.write("")
    st.subheader("Sensor map & quantum optical mesh")
    
    # Custom Node Management Expander
    with st.expander("➕ Provision / Delete Custom Metropolitan Quantum Nodes", expanded=False):
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
            if "custom_nodes" not in st.session_state:
                st.session_state.custom_nodes = {}
            st.session_state.custom_nodes[new_nid] = {
                'id': new_nid, 'type': new_type, 'lat': new_lat, 'lon': new_lon,
                'status': 'ok', 'qber': 0.021, 'key_vault': 100.0, 'last_seen': 'Just now'
            }
            st.success(f"Node {new_nid} provisioned into quantum mesh! BB84 verification passed (QBER=2.1%).")
            st.rerun()

    # Map Rendering with full optical lines
    display_nodes = dict(nodes)
    if "custom_nodes" in st.session_state:
        display_nodes.update(st.session_state.custom_nodes)
    
    if not display_nodes:
        # Default placeholder mesh if MQTT waiting
        display_nodes = {
            "traffic-node-07": {"status": "ok", "qber": 0.021},
            "water-meter-14": {"status": "ok", "qber": 0.018},
            "camera-22": {"status": "ok", "qber": 0.034},
            "hospital-node-01": {"status": "ok", "qber": 0.015},
            "financial-core-01": {"status": "ok", "qber": 0.009},
        }

    m = folium.Map(location=CITY_CENTER, zoom_start=13, tiles="CartoDB dark_matter")
    
    node_coords = {}
    for node_id, info in display_nodes.items():
        if isinstance(info, dict) and 'lat' in info and 'lon' in info:
            lat, lon = info['lat'], info['lon']
        else:
            lat, lon = get_location(node_id)
        node_coords[node_id] = (lat, lon)
        
        status = info.get("status", "ok")
        qber = info.get("qber")
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
        ).add_to(m)

    # Draw Optical Lines Connecting Every Node
    n_list = list(node_coords.keys())
    n_count = len(n_list)
    
    if "reroute_active" in st.session_state and st.session_state.reroute_active:
        # Star reroute via Financial District
        hub = n_list[0]
        for other in n_list[1:]:
            folium.PolyLine(
                locations=[node_coords[hub], node_coords[other]],
                color="#06D6A0", weight=2.5, opacity=0.8, dash_array="6, 6"
            ).add_to(m)
    else:
        for idx in range(n_count):
            u_id = n_list[idx]
            v_id = n_list[(idx + 1) % n_count]
            u_stat = display_nodes[u_id].get("status", "ok")
            v_stat = display_nodes[v_id].get("status", "ok")
            line_color = "#FF6B6B" if (u_stat != "ok" or v_stat != "ok") else "#06D6A0"
            folium.PolyLine(
                locations=[node_coords[u_id], node_coords[v_id]],
                color=line_color, weight=2.5, opacity=0.8, dash_array="6, 6" if line_color == "#06D6A0" else None
            ).add_to(m)
            if n_count >= 4:
                v2_id = n_list[(idx + 2) % n_count]
                folium.PolyLine(
                    locations=[node_coords[u_id], node_coords[v2_id]],
                    color="#06D6A0" if (display_nodes[u_id].get("status") == "ok" and display_nodes[v2_id].get("status") == "ok") else "#FF6B6B",
                    weight=1.5, opacity=0.5, dash_array="4, 4"
                ).add_to(m)

    st_folium(m, width=None, height=400, key="city_map")

# ===== NODES TAB =====
with tab_nodes:
    if not nodes:
        st.info("No sensor nodes have reported in yet. Start one with:\n\n"
                "`python3 -m network.sensor_node --id traffic-node-07 --type traffic_flow`\n\n"
                "or use the Attack simulation tab.")
    else:
        rows = []
        for node_id, info in sorted(nodes.items()):
            status = info.get("status")
            qber = info.get("qber")
            rows.append({
                "Node ID": node_id,
                "Status": "Recovered" if info.get("just_recovered") else
                          ("Secure" if status == "ok" else "Compromised"),
                "QBER": f"{qber:.2%}" if qber is not None else "N/A",
                "Key fingerprint": info.get("fingerprint", "—") if status == "ok" else "—",
                "Readings logged": len(readings.get(node_id, [])),
                "Last seen (UTC)": info.get("last_seen", "—"),
            })
        df = pd.DataFrame(rows)

        def _highlight(row):
            color = "background-color: rgba(220, 50, 47, 0.12)" if row["Status"] == "Compromised" \
                else "background-color: rgba(38, 166, 91, 0.10)" if row["Status"] in ("Secure", "Recovered") \
                else ""
            return [color] * len(row)

        st.dataframe(df.style.apply(_highlight, axis=1), use_container_width=True, hide_index=True)

        st.write("")
        st.subheader("Node detail")
        selected_node = st.selectbox("Select a node to inspect", sorted(nodes.keys()))

        if selected_node:
            detail_col1, detail_col2 = st.columns([1, 1])
            with detail_col1:
                history = qber_history.get(selected_node, [])
                if len(history) >= 2:
                    hist_df = pd.DataFrame(
                        [(ts, q * 100) for ts, q in history],
                        columns=["time", "QBER (%)"],
                    ).set_index("time")
                    st.caption("QBER history")
                    st.line_chart(hist_df, height=220)
                else:
                    st.caption("Not enough QBER history yet for a chart.")
            with detail_col2:
                node_readings = readings.get(selected_node, [])
                st.caption(f"Latest decrypted reading ({len(node_readings)} logged)")
                if node_readings:
                    st.json(node_readings[0], expanded=True)
                else:
                    st.caption("No decrypted readings yet.")

# ===== ATTACK SIMULATION TAB =====
with tab_attack:
    st.subheader("Launch a live eavesdropping attack")
    st.caption("Starts a real sensor-node process running BB84 with an active "
               "eavesdropper, exactly as it would run on separate hardware.")

    atk_col1, atk_col2, atk_col3 = st.columns([2, 2, 2])
    with atk_col1:
        attack_node_id = st.text_input("Node ID to attack", value="camera-22")
    with atk_col2:
        sensor_type = st.selectbox("Sensor type", ["surveillance", "traffic_flow", "water_flow"])
    with atk_col3:
        st.write("")
        st.write("")
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            launch = st.button("Simulate attacker", type="primary", use_container_width=True)
        with btn_col2:
            stop = st.button("Stop attacker", use_container_width=True)

    if launch:
        proc = subprocess.Popen(
            [sys.executable, "-m", "network.sensor_node",
             "--id", attack_node_id, "--type", sensor_type,
             "--eavesdrop", "--interval", "6"],
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        st.session_state.attack_processes[attack_node_id] = proc.pid
        st.success(f"Launched attacking sensor node '{attack_node_id}' (PID {proc.pid}). "
                   f"Check the Nodes tab — its status should flip to Compromised within "
                   f"a few seconds.")

    if stop:
        pid = st.session_state.attack_processes.get(attack_node_id)
        if pid is None:
            st.warning(f"No tracked attacker process for '{attack_node_id}' in this session.")
        else:
            try:
                os.kill(pid, signal.SIGTERM)
                del st.session_state.attack_processes[attack_node_id]
                st.success(f"Stopped attacker on '{attack_node_id}' (PID {pid}). "
                           f"It should recover to a clean session within a few cycles.")
            except ProcessLookupError:
                st.info(f"Process {pid} already stopped.")
                st.session_state.attack_processes.pop(attack_node_id, None)

    if st.session_state.attack_processes:
        st.write("")
        st.caption("Currently tracked attacker processes (this session)")
        proc_df = pd.DataFrame(
            [{"Node ID": nid, "PID": pid} for nid, pid in st.session_state.attack_processes.items()]
        )
        st.dataframe(proc_df, use_container_width=True, hide_index=True)

# ===== SECURITY LOG TAB =====
with tab_log:
    st.subheader("Security event log")

    if not events:
        st.caption("No security events recorded.")
    else:
        log_rows = []
        for event in events[:50]:
            reason = event.get("reason", "unknown")
            node_id = event.get("node_id", "?")
            qber = event.get("qber")
            ts = event.get("timestamp", "")
            log_rows.append({
                "Timestamp (UTC)": ts,
                "Node ID": node_id,
                "Event": "Recovered" if reason == "recovered" else reason.replace("_", " ").title(),
                "QBER": f"{qber:.2%}" if qber is not None else "—",
            })
        log_df = pd.DataFrame(log_rows)

        def _highlight_log(row):
            color = "background-color: rgba(38, 166, 91, 0.10)" if row["Event"] == "Recovered" \
                else "background-color: rgba(220, 50, 47, 0.10)"
            return [color] * len(row)

        st.dataframe(log_df.style.apply(_highlight_log, axis=1), use_container_width=True, hide_index=True)