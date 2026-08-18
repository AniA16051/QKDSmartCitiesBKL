#!/usr/bin/env python3
"""
Unified QKD Dashboard for Streamlit Cloud, Render, and Railway Deployment
Cyber Defense Operations Center (SOC) Interface
"""

import os
import sys

# Disable file watching in production to prevent inotify limit errors
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
os.environ["STREAMLIT_LOGGER_LEVEL"] = "warning"

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import hashlib
import json
import random
import time
import threading
import ssl
import paho.mqtt.client as mqtt

# Configuration for free cloud MQTT broker
def get_mqtt_config():
    """Get MQTT configuration from environment or Streamlit secrets"""
    broker = os.getenv("MQTT_BROKER", "broker.emqx.io")
    port = int(os.getenv("MQTT_PORT", 1883))
    username = os.getenv("MQTT_USERNAME", "")
    password = os.getenv("MQTT_PASSWORD", "")
    use_tls = os.getenv("MQTT_USE_TLS", "false").lower() == "true"
    
    try:
        if hasattr(st, 'secrets') and st.secrets is not None:
            if 'MQTT_BROKER' in st.secrets:
                broker = st.secrets['MQTT_BROKER']
            if 'MQTT_PORT' in st.secrets:
                port = int(st.secrets['MQTT_PORT'])
            if 'MQTT_USERNAME' in st.secrets:
                username = st.secrets['MQTT_USERNAME']
            if 'MQTT_PASSWORD' in st.secrets:
                password = st.secrets['MQTT_PASSWORD']
            if 'MQTT_USE_TLS' in st.secrets:
                use_tls = str(st.secrets['MQTT_USE_TLS']).lower() == "true"
    except Exception:
        pass
    
    return {
        'broker': broker,
        'port': port,
        'username': username,
        'password': password,
        'use_tls': use_tls
    }

MQTT_TOPIC = "qkd/smartcity/data"

def _get_mqtt_settings():
    """Lazy MQTT config; avoids accessing st.secrets at module-import time."""
    cfg = get_mqtt_config()
    return cfg['broker'], cfg['port'], cfg['username'], cfg['password'], cfg['use_tls']

# Simplified BB84 simulation
class UnifiedBB84:
    """Lightweight BB84 simulation integrated into dashboard"""
    
    @staticmethod
    def generate_key(length=256):
        """Generate random key bits"""
        return np.random.randint(0, 2, length)
    
    @staticmethod
    def generate_bases(length=256):
        """Generate random bases (0=Z, 1=X)"""
        return np.random.randint(0, 2, length)
    
    @staticmethod
    def simulate_bb84_protocol(key_length=256, attack=False):
        """
        Simulate complete BB84 protocol
        Returns: dict with protocol results
        """
        alice_key = UnifiedBB84.generate_key(key_length)
        alice_bases = UnifiedBB84.generate_bases(key_length)
        bob_bases = UnifiedBB84.generate_bases(key_length)
        bob_key = np.zeros(key_length, dtype=int)
        
        if attack:
            eve_bases = UnifiedBB84.generate_bases(key_length)
            eve_key = np.zeros(key_length, dtype=int)
            for i in range(key_length):
                if alice_bases[i] == eve_bases[i]:
                    eve_key[i] = alice_key[i]
                else:
                    eve_key[i] = random.randint(0, 1)
            for i in range(key_length):
                if eve_bases[i] == bob_bases[i]:
                    bob_key[i] = eve_key[i]
                else:
                    bob_key[i] = random.randint(0, 1)
        else:
            for i in range(key_length):
                if alice_bases[i] == bob_bases[i]:
                    bob_key[i] = alice_key[i]
                else:
                    bob_key[i] = random.randint(0, 1)
        
        matching_bases = (alice_bases == bob_bases)
        sifted_alice = alice_key[matching_bases]
        sifted_bob = bob_key[matching_bases]
        
        if len(sifted_alice) == 0:
            return {
                'success': False, 'qber': 100.0, 'sifted_length': 0,
                'final_key': None, 'attack_detected': True, 'raw_length': key_length
            }
        
        errors = np.sum(sifted_alice != sifted_bob)
        qber = (errors / len(sifted_alice)) * 100.0
        attack_detected = qber >= 11.0
        success = not attack_detected and len(sifted_alice) >= 32
        
        final_key = None
        if success:
            bit_string = ''.join(map(str, sifted_alice))
            final_key = hashlib.sha256(bit_string.encode()).hexdigest()
        
        return {
            'success': success, 'qber': qber, 'sifted_length': len(sifted_alice),
            'final_key': final_key, 'attack_detected': attack_detected, 'raw_length': key_length
        }

# Integrated Smart City Simulation
class IntegratedSmartCity:
    """Unified sensor simulation within the dashboard process"""
    
    def __init__(self):
        broker, port, username, password, use_tls = _get_mqtt_settings()
        self._mqtt_broker = broker
        self._mqtt_port = port
        self._mqtt_username = username
        self._mqtt_password = password
        self._mqtt_use_tls = use_tls

        self.sensors = {
            'traffic_light': {
                'id': 'NODE-TRF-01', 'type': 'traffic_flow',
                'location': 'Main St & 5th Ave',
                'lat': 12.9756, 'lon': 77.6006,
                'status': 'secure', 'qber': 0.0, 'last_key': None,
                'key_vault': 100.0,
                'data_points': [], 'last_update': datetime.now()
            },
            'traffic_junction': {
                'id': 'NODE-TRF-02', 'type': 'traffic_flow',
                'location': 'MG Road & Ring Junction',
                'lat': 12.9782, 'lon': 77.6068,
                'status': 'secure', 'qber': 0.0, 'last_key': None,
                'key_vault': 100.0,
                'data_points': [], 'last_update': datetime.now()
            },
            'hospital_node': {
                'id': 'NODE-MED-01', 'type': 'medical_telemetry',
                'location': 'City General Hospital',
                'lat': 12.9642, 'lon': 77.5975,
                'status': 'secure', 'qber': 0.0, 'last_key': None,
                'key_vault': 100.0,
                'data_points': [], 'last_update': datetime.now()
            },
            'financial_core': {
                'id': 'NODE-FIN-01', 'type': 'banking_qkd_trunk',
                'location': 'Financial District Core',
                'lat': 12.9720, 'lon': 77.6045,
                'status': 'secure', 'qber': 0.0, 'last_key': None,
                'key_vault': 100.0,
                'data_points': [], 'last_update': datetime.now()
            },
            'power_substation': {
                'id': 'NODE-PWR-01', 'type': 'smart_grid',
                'location': 'East Power Grid Substation',
                'lat': 12.9680, 'lon': 77.6110,
                'status': 'secure', 'qber': 0.0, 'last_key': None,
                'key_vault': 100.0,
                'data_points': [], 'last_update': datetime.now()
            },
            'water_meter': {
                'id': 'NODE-WTR-01', 'type': 'water_consumption',
                'location': 'Downtown Reservoir',
                'lat': 12.9698, 'lon': 77.5910,
                'status': 'secure', 'qber': 0.0, 'last_key': None,
                'key_vault': 100.0,
                'data_points': [], 'last_update': datetime.now()
            },
            'surveillance': {
                'id': 'NODE-CAM-01', 'type': 'security_monitoring',
                'location': 'Central Park North',
                'lat': 12.9741, 'lon': 77.5983,
                'status': 'secure', 'qber': 0.0, 'last_key': None,
                'key_vault': 100.0,
                'data_points': [], 'last_update': datetime.now()
            }
        }
        self.attacked_target = "None"
        self.isolated_nodes = set()
        self.rerouted_lifeline = False
        self.mqtt_client = None
        self.mqtt_connected = False
        self.terminal_logs = []
        self.tracking_target = {
            'vehicle_id': 'VEH-8824 [Silver Sedan]',
            'active_camera': 'NODE-CAM-01',
            'last_handoff': datetime.now(),
            'speed_kmh': 48.5,
            'pattern': 'NOMINAL FLOW',
            'qkd_session_key': None
        }
        
        for name in self.sensors:
            self.simulate_sensor(name)

    @property
    def attack_active(self):
        return self.attacked_target != "None"
    
    def initialize_mqtt(self):
        """Initialize MQTT client for cloud broker connection"""
        try:
            try:
                self.mqtt_client = mqtt.Client(
                    mqtt.CallbackAPIVersion.VERSION2,
                    client_id=f"qkd-dash-{random.randint(1000, 9999)}"
                )
            except AttributeError:
                self.mqtt_client = mqtt.Client(client_id=f"qkd-dash-{random.randint(1000, 9999)}")
            
            if self._mqtt_username and self._mqtt_password:
                self.mqtt_client.username_pw_set(self._mqtt_username, self._mqtt_password)
            
            if self._mqtt_use_tls or self._mqtt_port == 8883:
                try:
                    self.mqtt_client.tls_set(cert_reqs=ssl.CERT_NONE)
                    self.mqtt_client.tls_insecure_set(True)
                except Exception:
                    pass
            
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            self.mqtt_client.connect_async(self._mqtt_broker, self._mqtt_port, 60)
            self.mqtt_client.loop_start()
            return True
        except Exception:
            return False
    
    def _on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        self.mqtt_connected = (rc == 0)
    
    def _on_mqtt_disconnect(self, client, userdata, rc, properties=None):
        self.mqtt_connected = False
    
    def publish_sensor_data(self, sensor_name, data):
        if self.mqtt_connected and self.mqtt_client:
            try:
                self.mqtt_client.publish(f"{MQTT_TOPIC}/{sensor_name}", json.dumps(data))
                return True
            except Exception:
                return False
        return False
    
    def log_terminal(self, msg, level="INFO"):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.terminal_logs.append({"ts": ts, "level": level, "msg": msg})
        if len(self.terminal_logs) > 50:
            self.terminal_logs = self.terminal_logs[-50:]
    
    def reroute_key_supply(self, source_name="Financial District Core"):
        """Emergency Lifeline: Replenish key vaults and reroute optical mesh lines."""
        self.rerouted_lifeline = True
        for s in self.sensors.values():
            s['key_vault'] = 100.0
            if s['status'] in ['compromised', 'blackout']:
                s['status'] = 'secure'
        self.attacked_target = "None"
        self.isolated_nodes.clear()
        self.log_terminal(f"LIFELINE :: OPTICAL MESH REROUTED VIA [{source_name.upper()}]. ALL VAULTS AT 100%", "SECURE")
        self.update_all_sensors()

    def isolate_standby_node(self, target):
        """Standby Option: Quarantine and isolate compromised node, severing all optical lines while preserving network continuity."""
        if target == "All Nodes":
            for k in self.sensors.keys():
                self.isolated_nodes.add(k)
        elif target in self.sensors:
            self.isolated_nodes.add(target)
        self.log_terminal(f"STANDBY :: QUARANTINE PROTOCOL ENGAGED. NODE [{target.upper()}] ISOLATED (ALL LINES BROKEN).", "WARN")
        self.update_all_sensors()

    def fix_and_restore_node(self, target="All Nodes"):
        """Fix / Restore node to clean operational state."""
        if target == "All Nodes":
            self.isolated_nodes.clear()
            self.attacked_target = "None"
            for s in self.sensors.values():
                s['status'] = 'secure'
                s['key_vault'] = 100.0
        else:
            self.isolated_nodes.discard(target)
            if self.attacked_target == target:
                self.attacked_target = "None"
            if target in self.sensors:
                self.sensors[target]['status'] = 'secure'
                self.sensors[target]['key_vault'] = 100.0
        self.log_terminal(f"RESTORE :: NODE [{target.upper()}] PURGED & RECONNECTED TO SECURE MESH", "SECURE")
        self.update_all_sensors()

    def simulate_sensor(self, sensor_name):
        sensor = self.sensors[sensor_name]
        is_isolated = sensor_name in self.isolated_nodes
        is_attacked = (self.attacked_target == "All Nodes") or (self.attacked_target == sensor_name) or is_isolated
        
        qkd_result = UnifiedBB84.simulate_bb84_protocol(key_length=256, attack=is_attacked)
        
        sensor['qber'] = qkd_result['qber']
        sensor['last_update'] = datetime.now()
        
        if is_isolated:
            sensor['status'] = 'compromised'
            sensor['key_vault'] = 0.0
            sensor['last_key'] = None
        elif qkd_result['success']:
            sensor['key_vault'] = min(100.0, sensor.get('key_vault', 100.0) + 15.0)
            sensor['status'] = 'secure'
            sensor['last_key'] = qkd_result['final_key']
        else:
            # Drain reserve when BB84 key generation aborts
            drain_amt = random.uniform(25.0, 35.0)
            sensor['key_vault'] = max(0.0, sensor.get('key_vault', 100.0) - drain_amt)
            if sensor['key_vault'] <= 0.0:
                sensor['status'] = 'blackout'
                sensor['last_key'] = None
            else:
                sensor['status'] = 'compromised'
                sensor['last_key'] = hashlib.sha256(f"vault-{sensor['id']}-{int(sensor['key_vault'])}".encode()).hexdigest()
        
        # Telemetry generation
        if is_isolated:
            data_value = 0
            data_unit = 'ISOLATED / QUARANTINED'
        elif sensor['status'] == 'blackout':
            data_value = 0
            data_unit = 'OFFLINE (BLACKOUT)'
        elif sensor['type'] == 'traffic_flow':
            data_value = random.randint(15, 120)
            data_unit = 'cars/min'
        elif sensor['type'] == 'medical_telemetry':
            data_value = f"{random.randint(65, 88)} bpm / {random.randint(96, 99)}% SpO2"
            data_unit = 'vitals'
        elif sensor['type'] == 'banking_qkd_trunk':
            data_value = f"${random.randint(120, 890)}k / tx"
            data_unit = 'encrypted ledger'
        elif sensor['type'] == 'smart_grid':
            data_value = f"{round(random.uniform(228.0, 234.0), 1)} kV / 60Hz"
            data_unit = 'grid sync'
        elif sensor['type'] == 'water_consumption':
            data_value = round(random.uniform(50, 200), 2)
            data_unit = 'L/h'
        else:
            data_value = random.choice(['NOMINAL', 'MOTION_DET', 'SECURE'])
            data_unit = 'state'
        
        sensor_data = {
            'sensor_id': sensor['id'], 'sensor_type': sensor['type'],
            'location': sensor['location'], 'timestamp': datetime.now().isoformat(),
            'value': data_value, 'unit': data_unit,
            'qkd_status': sensor['status'], 'qber': sensor['qber'],
            'key_vault': sensor['key_vault'],
            'key_preview': sensor['last_key'][:8] + '...' if sensor['last_key'] else None
        }
        
        if is_isolated:
            self.log_terminal(
                f"ISOLATION ACTIVE  {sensor['id']}  QBER={sensor['qber']:.1f}%  OPTICAL LINKS CUT  AWAITING REPAIR",
                "WARN"
            )
        elif sensor['status'] == 'secure':
            self.log_terminal(
                f"BB84 OK  {sensor['id']}  QBER={sensor['qber']:.1f}%  VAULT={sensor['key_vault']:.0f}%  KEY={sensor['last_key'][:8]}...{sensor['last_key'][-4:]}",
                "SECURE"
            )
        elif sensor['status'] == 'compromised':
            self.log_terminal(
                f"BB84 ABORT  {sensor['id']}  QBER={sensor['qber']:.1f}% >= 11.0%  DRAINING VAULT: {sensor['key_vault']:.0f}%",
                "WARN"
            )
        else:
            self.log_terminal(
                f"BLACKOUT  {sensor['id']}  VAULT 0%  TRANSMISSION REFUSED (ZERO-TRUST)",
                "ALERT"
            )
        
        sensor['data_points'].append({
            'time': datetime.now(),
            'value': data_value if isinstance(data_value, (int, float)) else (1 if data_value == 'MOTION_DET' else 0),
            'qber': sensor['qber'],
            'vault': sensor['key_vault']
        })
        if len(sensor['data_points']) > 25:
            sensor['data_points'] = sensor['data_points'][-25:]
        
        # Dynamic BB84 camera tracking & handoff
        if sensor_name in ['traffic_light', 'traffic_junction', 'surveillance'] and sensor['status'] != 'blackout' and not is_isolated:
            cams = ['NODE-CAM-01', 'NODE-TRF-01', 'NODE-TRF-02']
            next_cam = random.choice(cams)
            self.tracking_target['active_camera'] = next_cam
            self.tracking_target['speed_kmh'] = round(random.uniform(42.0, 68.0), 1)
            patterns = ['NOMINAL FLOW', 'NOMINAL FLOW', 'SUDDEN LANE CONVERGENCE', 'SPEED ANOMALY']
            self.tracking_target['pattern'] = random.choice(patterns)
            if sensor['last_key']:
                self.tracking_target['qkd_session_key'] = sensor['last_key'][:16]
            self.tracking_target['last_handoff'] = datetime.now()
        
        self.publish_sensor_data(sensor_name, sensor_data)
        return sensor_data
    
    def toggle_attack(self, target="All Nodes"):
        if self.attacked_target == target:
            self.attacked_target = "None"
            self.isolated_nodes.discard(target)
            msg = f"ATTACK STOPPED :: CHANNEL RESTORED TO CLEAN STATE"
        else:
            self.attacked_target = target
            msg = f"INTERCEPT-RESEND ATTACK ACTIVATED ON {target.upper()}"
        self.log_terminal(f"THREAT ENGINE :: {msg}", "ALERT" if self.attack_active else "INFO")
        self.update_all_sensors()
        return self.attack_active
    
    def update_all_sensors(self):
        results = {}
        for sensor_name in self.sensors.keys():
            results[sensor_name] = self.simulate_sensor(sensor_name)
        return results

    def ping_node(self, sensor_name):
        """Simulate a cryptographic challenge-response ping"""
        sensor = self.sensors[sensor_name]
        nonce = hashlib.sha256(str(time.time()).encode()).hexdigest()[:16].upper()
        
        if sensor['status'] in ['secure', 'compromised'] and sensor['last_key']:
            self.log_terminal(f"PING :: [ {sensor['id']} ] CRYPTOGRAPHIC CHALLENGE (NONCE: {nonce})", "INFO")
            self.log_terminal(f"PING OK :: [ {sensor['id']} ] RESPONSE ENCRYPTED WITH KEY {sensor['last_key'][:8]}...", "SECURE")
            return True
        else:
            self.log_terminal(f"PING :: [ {sensor['id']} ] CRYPTOGRAPHIC CHALLENGE (NONCE: {nonce})", "INFO")
            self.log_terminal(f"PING FAILED :: [ {sensor['id']} ] NODE IN BLACKOUT (VAULT EMPTY)", "WARN")
            return False


# ═══════════════════════════════════════════════════════════════════════
# STREAMLIT UI — Cyber Defense Operations Center
# ═══════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="QKD Cyber Defense Operations Center",
        page_icon="Q",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # ── CSS Design System ──
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    :root {
        --bg-canvas: #080B10;
        --bg-panel: #0E131F;
        --bg-card: #111827;
        --border: #1E293B;
        --border-subtle: #162032;
        --text-primary: #F1F5F9;
        --text-secondary: #94A3B8;
        --text-muted: #64748B;
        --accent-cyan: #06B6D4;
        --accent-green: #10B981;
        --accent-red: #EF4444;
        --accent-amber: #F59E0B;
    }
    
    .stApp {
        background-color: var(--bg-canvas) !important;
    }
    
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 1rem !important;
        max-width: 96% !important;
    }
    
    /* ── Header ── */
    .soc-title {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.4rem;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: 2px;
        text-align: center;
        margin: 0;
    }
    .soc-subtitle {
        font-family: 'Inter', sans-serif;
        font-size: 0.82rem;
        color: var(--text-muted);
        text-align: center;
        margin-top: 2px;
        margin-bottom: 14px;
    }
    
    /* ── Status Bar ── */
    .status-bar {
        background: var(--bg-panel);
        border: 1px solid var(--border);
        padding: 10px 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 24px;
        flex-wrap: wrap;
        margin-bottom: 16px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem;
    }
    .status-item {
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .status-label {
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .status-val-green { color: var(--accent-green); font-weight: 700; }
    .status-val-red { color: var(--accent-red); font-weight: 700; }
    .status-val-amber { color: var(--accent-amber); font-weight: 700; }
    .status-val-cyan { color: var(--accent-cyan); font-weight: 700; }
    
    /* ── Section Headers ── */
    .section-hdr {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.82rem;
        font-weight: 700;
        color: var(--accent-cyan);
        text-transform: uppercase;
        letter-spacing: 1px;
        border-bottom: 1px solid var(--border);
        padding-bottom: 6px;
        margin-bottom: 12px;
        margin-top: 8px;
    }
    
    /* ── Metric Overrides ── */
    div[data-testid="stMetric"] {
        background: var(--bg-panel) !important;
        border: 1px solid var(--border) !important;
        border-radius: 0px !important;
        padding: 10px 14px !important;
    }
    div[data-testid="stMetricLabel"] {
        color: var(--text-muted) !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.7rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }
    div[data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 700 !important;
    }
    
    /* ── Buttons ── */
    .stButton > button {
        background: var(--bg-panel) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 2px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 700 !important;
        font-size: 0.78rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
        padding: 8px 16px !important;
        transition: all 0.08s ease !important;
    }
    .stButton > button:hover {
        border-color: var(--accent-cyan) !important;
        box-shadow: 0 0 12px rgba(6,182,212,0.25) !important;
    }
    .stButton > button:active {
        transform: translateY(1px) !important;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.6) !important;
    }
    
    /* ── Containers ── */
    div[data-testid="stExpander"] {
        border: 1px solid var(--border) !important;
        border-radius: 0px !important;
        background: var(--bg-panel) !important;
    }
    
    /* ── Terminal ── */
    .term-output {
        background: #05080E;
        border: 1px solid var(--border);
        padding: 12px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        line-height: 1.6;
        max-height: 240px;
        overflow-y: auto;
        color: var(--text-secondary);
    }
    .tl-secure { color: var(--accent-green); }
    .tl-warn { color: var(--accent-red); font-weight: 600; }
    .tl-alert { color: var(--accent-amber); font-weight: 600; }
    .tl-info { color: var(--accent-cyan); }
    .tl-ts { color: var(--text-muted); }
    
    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background-color: #0B0F19 !important;
        border-right: 1px solid var(--border) !important;
    }
    
    /* ── Dataframe ── */
    .stDataFrame {
        border: 1px solid var(--border) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # ── Initialize Backend ──
    if 'smart_city' not in st.session_state:
        st.session_state.smart_city = IntegratedSmartCity()
        st.session_state.smart_city.initialize_mqtt()
    
    sc = st.session_state.smart_city
    attack_active = sc.attack_active
    
    # ══════════════════════════════════════════════════════════════
    # HEADER
    # ══════════════════════════════════════════════════════════════
    st.markdown('<p class="soc-title">QKD CYBER DEFENSE OPERATIONS CENTER</p>', unsafe_allow_html=True)
    st.markdown('<p class="soc-subtitle">Real-time BB84 Quantum Key Distribution Simulation &mdash; IoT Sensor Network Security Monitor</p>', unsafe_allow_html=True)
    
    # ── Global Status Bar ──
    sys_status = '<span class="status-val-red">ATTACK ACTIVE</span>' if (attack_active or len(sc.isolated_nodes) > 0) else '<span class="status-val-green">ACTIVE DEFENSE</span>'
    mqtt_status = '<span class="status-val-green">CONNECTED</span>' if sc.mqtt_connected else '<span class="status-val-amber">STANDALONE</span>'
    tls_val = "ON" if (sc._mqtt_use_tls or sc._mqtt_port == 8883) else "OFF"
    
    online_count = sum(1 for s in sc.sensors.values() if s['status'] == 'secure')
    st.markdown(f"""
    <div class="status-bar">
        <div class="status-item"><span class="status-label">System:</span> {sys_status}</div>
        <div class="status-item"><span class="status-label">Protocol:</span> <span class="status-val-cyan">BB84 + AES-GCM-256</span></div>
        <div class="status-item"><span class="status-label">Broker:</span> <span class="status-val-cyan">{sc._mqtt_broker}:{sc._mqtt_port}</span></div>
        <div class="status-item"><span class="status-label">TLS:</span> <span class="status-val-cyan">{tls_val}</span></div>
        <div class="status-item"><span class="status-label">MQTT:</span> {mqtt_status}</div>
        <div class="status-item"><span class="status-label">Sensors:</span> <span class="status-val-green">{online_count}/{len(sc.sensors)} ONLINE</span></div>
    </div>
    """, unsafe_allow_html=True)
    
    # ══════════════════════════════════════════════════════════════
    # CONTROL BAR (Centered Row)
    # ══════════════════════════════════════════════════════════════
    c1, c2, c3, c4, c5 = st.columns([2.5, 2.5, 2, 2, 2])
    
    target_mapping = {
        "All Nodes": "All Nodes",
        "Traffic Signal 01 (Main St)": "traffic_light",
        "Traffic Signal 02 (MG Rd)": "traffic_junction",
        "Hospital Telemetry": "hospital_node",
        "Financial Core (QKD Trunk)": "financial_core",
        "Power Substation": "power_substation",
        "Water Utility": "water_meter",
        "Surveillance Camera": "surveillance"
    }

    with c1:
        selected_target_label = st.selectbox(
            "Attack Target Node",
            list(target_mapping.keys()),
            index=0,
            help="Select which IoT node to target with the Eve intercept-resend eavesdropping attack."
        )
        selected_target_key = target_mapping[selected_target_label]

    with c2:
        is_current_target_attacked = (sc.attacked_target == selected_target_key) or (sc.attacked_target == "All Nodes" and sc.attack_active)
        atk_label = f"STOP ATTACK ({sc.attacked_target.upper()})" if sc.attack_active else f"SIMULATE ATTACK"
        if st.button(
            atk_label,
            use_container_width=True,
            help="Toggles an intercept-resend (Eve) eavesdropper on the selected quantum channel target. When active, Eve measures each qubit in a random basis and resends it, causing QBER to exceed the 11% BB84 security threshold."
        ):
            sc.toggle_attack(target=selected_target_key)
            st.rerun()

    with c3:
        if st.button(
            "EXECUTE TELEMETRY CYCLE",
            use_container_width=True,
            help="Runs a fresh BB84 key exchange for every sensor node, generates new telemetry readings, and publishes encrypted payloads to the MQTT broker."
        ):
            sc.update_all_sensors()
            st.rerun()

    with c4:
        refresh = st.selectbox(
            "Auto-Refresh",
            ["Off", "5 seconds", "10 seconds"],
            index=0,
            help="Automatically re-runs the full telemetry cycle at the selected interval."
        )
        if refresh != "Off":
            ms = 5000 if refresh == "5 seconds" else 10000
            try:
                from streamlit_autorefresh import st_autorefresh
                count = st_autorefresh(interval=ms, key="soc_auto")
                if 'last_refresh_count' not in st.session_state:
                    st.session_state.last_refresh_count = 0
                
                if count > st.session_state.last_refresh_count:
                    sc.update_all_sensors()
                    st.session_state.last_refresh_count = count
            except ImportError:
                time.sleep(ms // 1000)
                sc.update_all_sensors()
                st.rerun()

    with c5:
        if len(sc.isolated_nodes) > 0:
            target_display = f"ISOLATED ({len(sc.isolated_nodes)})"
        elif sc.attack_active:
            target_display = f"ACTIVE ({sc.attacked_target})"
        else:
            target_display = "SECURED"
        st.metric(
            "Channel State",
            target_display,
            help="Reflects whether an active eavesdropper (Eve) is present on any quantum channel or nodes are quarantined."
        )
    
    st.markdown("---")
    
    # ══════════════════════════════════════════════════════════════
    # THREAT REMEDIATION & FAILSAFES
    # ══════════════════════════════════════════════════════════════
    if sc.attack_active or len(sc.isolated_nodes) > 0:
        st.markdown('<div class="section-hdr" style="color: var(--accent-amber);">Active Countermeasures & Failsafes</div>', unsafe_allow_html=True)
        fc1, fc2, fc3, fc4 = st.columns([1.5, 1.5, 1.2, 1.8])
        with fc1:
            if st.button("REROUTE KEY SUPPLY FROM FINANCIAL DISTRICT", use_container_width=True, help="Emergency Lifeline: Reconnects depleted nodes to the secondary uncompromised Financial District optical quantum backbone, fully replenishing key vaults to 100% and rerouting mesh connections."):
                sc.reroute_key_supply(source_name="Financial District Backbone")
                st.rerun()
        with fc2:
            if st.button("PROVISION STANDBY NODE", use_container_width=True, help="Quarantine compromised node: Severs all quantum optical lines to it, breaks mesh paths, and isolates it while network continuity remains active."):
                target_to_isolate = sc.attacked_target if sc.attack_active else "All Nodes"
                sc.isolate_standby_node(target=target_to_isolate)
                st.rerun()
        with fc3:
            if st.button("FIX & RESTORE MESH", use_container_width=True, help="Purge isolation, reconnect all broken optical links, and restore clean status."):
                sc.fix_and_restore_node("All Nodes")
                st.rerun()
        with fc4:
            if len(sc.isolated_nodes) > 0:
                st.markdown(f'<div style="color: var(--accent-red); font-family: \'JetBrains Mono\', monospace; font-size: 0.8rem; padding-top: 10px;">&gt; Isolated nodes: {", ".join(sc.isolated_nodes)}. Optical links severed. Stays in breach until fixed.</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="color: var(--accent-red); font-family: \'JetBrains Mono\', monospace; font-size: 0.8rem; padding-top: 10px;">&gt; Channel compromised ({sc.attacked_target}). Key vaults draining. Refuse unencrypted data.</div>', unsafe_allow_html=True)
        st.markdown("---")
    
    # ══════════════════════════════════════════════════════════════
    # NODE STATUS CARDS (Smart City Metropolitan Grid)
    # ══════════════════════════════════════════════════════════════
    st.markdown('<div class="section-hdr">Smart City Metropolitan IoT Nodes & Key Vault Reserves</div>', unsafe_allow_html=True)
    
    sensor_meta = [
        ('traffic_light', 'Traffic Signal 01', 'Vehicle throughput at Main & 5th Ave.'),
        ('traffic_junction', 'Traffic Signal 02', 'High-density MG Road Ring Junction flow.'),
        ('hospital_node', 'Hospital Emergency Telemetry', 'Encrypted patient vitals and ICU telemetry.'),
        ('financial_core', 'Financial District Core', 'Inter-bank transaction settlement QKD trunk.'),
        ('power_substation', 'Power Grid Substation', 'Grid telemetry & phase angle monitoring.'),
        ('water_meter', 'Water Utility', 'Municipal reservoir pump flow tracking.'),
        ('surveillance', 'Surveillance Camera', 'Optical public monitoring node with QKD handoff.'),
    ]
    
    # Render cards in rows of 3 and 4
    row1_cols = st.columns(4)
    row2_cols = st.columns(3)
    card_cols = list(row1_cols) + list(row2_cols)
    
    for col, (key, label, tooltip) in zip(card_cols, sensor_meta):
        s = sc.sensors[key]
        status_code = s['status']
        is_iso = key in sc.isolated_nodes
        with col:
            with st.container(border=True):
                st.markdown(f"**{label}**")
                st.caption(f"{s['location']}  ·  `{s['id']}`")
                
                m1, m2, m3 = st.columns(3)
                m1.metric(
                    "QBER",
                    f"{s['qber']:.1f}%",
                    help=f"Quantum Bit Error Rate for this node. {tooltip}"
                )
                
                if is_iso:
                    stat_str = "ISOLATED"
                elif status_code == 'secure':
                    stat_str = "SECURE"
                elif status_code == 'compromised':
                    stat_str = "DRAINING"
                else:
                    stat_str = "BLACKOUT"
                
                m2.metric(
                    "Status",
                    stat_str,
                    help="SECURE: Normal. DRAINING: Vault active. BLACKOUT: Vault 0%. ISOLATED: Optical links severed."
                )
                m3.metric(
                    "Key Vault",
                    f"{s.get('key_vault', 100.0):.0f}%",
                    help="Stored reserve of BB84 keys."
                )
                
                vault_pct = max(0.0, min(1.0, s.get('key_vault', 100.0) / 100.0))
                st.progress(vault_pct, text=f"Vault: {s.get('key_vault', 100.0):.0f}%")
                
                if s['last_key'] and not is_iso:
                    st.code(f"Key: {s['last_key'][:10]}...{s['last_key'][-4:]}", language=None)
                else:
                    st.code("Key: REFUSED / SEVERED", language=None)
                
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("PING", key=f"ping_{key}", use_container_width=True):
                        success = sc.ping_node(key)
                        if success:
                            st.toast(f"Ping OK for {s['id']}")
                        else:
                            st.toast(f"Ping FAILED for {s['id']}")
                        st.rerun()
                with b2:
                    if is_iso:
                        if st.button("RECONNECT", key=f"rec_{key}", use_container_width=True):
                            sc.fix_and_restore_node(key)
                            st.rerun()
                    else:
                        if st.button("ISOLATE", key=f"iso_{key}", use_container_width=True):
                            sc.isolate_standby_node(key)
                            st.rerun()
                
                if s['data_points']:
                    val = s['data_points'][-1]['value']
                    st.caption(f"Latest: **{val}**  ·  {s['last_update'].strftime('%H:%M:%S')}")
    
    # ══════════════════════════════════════════════════════════════
    # GEOSPATIAL MAP WITH OPTICAL FIBER MESH + QBER CHART
    # ══════════════════════════════════════════════════════════════
    st.markdown("---")
    
    map_col, chart_col = st.columns([1.1, 0.9])
    
    with map_col:
        st.markdown('<div class="section-hdr">Metropolitan Geospatial Mesh & Optical Lines</div>', unsafe_allow_html=True)
        
        lats, lons, names, colors, hovers = [], [], [], [], []
        for s_key, s in sc.sensors.items():
            lats.append(s['lat'])
            lons.append(s['lon'])
            names.append(s['id'])
            if s_key in sc.isolated_nodes or s['status'] == 'blackout':
                c = '#64748B'
            elif s['status'] == 'compromised':
                c = '#EF4444'
            else:
                c = '#10B981'
            colors.append(c)
            iso_tag = " (ISOLATED)" if s_key in sc.isolated_nodes else ""
            hovers.append(f"{s['id']}{iso_tag}<br>{s['location']}<br>QBER: {s['qber']:.1f}%<br>Vault: {s['key_vault']:.0f}%<br>Status: {s['status'].upper()}")
        
        fig_map = go.Figure()
        
        # Draw Optical Fiber Quantum Mesh Links
        # Define baseline mesh topology connections
        if sc.rerouted_lifeline:
            # Rerouted via Financial District Hub star-topology
            mesh_edges = [
                ('financial_core', 'traffic_light'),
                ('financial_core', 'traffic_junction'),
                ('financial_core', 'hospital_node'),
                ('financial_core', 'power_substation'),
                ('financial_core', 'water_meter'),
                ('financial_core', 'surveillance'),
            ]
        else:
            # Standard city ring & cross-grid topology
            mesh_edges = [
                ('traffic_light', 'traffic_junction'),
                ('traffic_junction', 'financial_core'),
                ('financial_core', 'power_substation'),
                ('power_substation', 'hospital_node'),
                ('hospital_node', 'water_meter'),
                ('water_meter', 'surveillance'),
                ('surveillance', 'traffic_light'),
                ('financial_core', 'hospital_node'),
                ('traffic_light', 'hospital_node')
            ]
        
        for u_key, v_key in mesh_edges:
            u = sc.sensors.get(u_key)
            v = sc.sensors.get(v_key)
            if not u or not v:
                continue
            
            u_broken = (u_key in sc.isolated_nodes) or (u['status'] in ['compromised', 'blackout'])
            v_broken = (v_key in sc.isolated_nodes) or (v['status'] in ['compromised', 'blackout'])
            
            if u_key in sc.isolated_nodes or v_key in sc.isolated_nodes:
                # Isolated node: line completely severed (do not draw or draw faint dark gray)
                continue
            elif u_broken or v_broken:
                # Breached channel link: red line
                fig_map.add_trace(go.Scattermapbox(
                    lat=[u['lat'], v['lat']],
                    lon=[u['lon'], v['lon']],
                    mode='lines',
                    line=dict(width=2, color='#EF4444'),
                    hoverinfo='none',
                    showlegend=False
                ))
            else:
                # Active clean quantum optical line: green dotted/dashed line
                fig_map.add_trace(go.Scattermapbox(
                    lat=[u['lat'], v['lat']],
                    lon=[u['lon'], v['lon']],
                    mode='lines',
                    line=dict(width=2, color='#10B981'),
                    hoverinfo='none',
                    showlegend=False
                ))
        
        # Pulse rings for compromised or isolated nodes
        for s_key, s in sc.sensors.items():
            if s_key in sc.isolated_nodes or s['status'] in ['compromised', 'blackout']:
                p_col = '#64748B' if s_key in sc.isolated_nodes or s['status'] == 'blackout' else '#EF4444'
                fig_map.add_trace(go.Scattermapbox(
                    lat=[s['lat']], lon=[s['lon']], mode='markers',
                    marker=dict(size=35, color=p_col, opacity=0.3),
                    hoverinfo='none', showlegend=False
                ))
        
        # Node Markers
        fig_map.add_trace(go.Scattermapbox(
            lat=lats, lon=lons, mode='markers+text',
            marker=dict(size=14, color=colors, opacity=0.95),
            text=names, textposition="top center",
            textfont=dict(size=9, color="#F3F4F6", family="JetBrains Mono"),
            hoverinfo='text', hovertext=hovers, showlegend=False
        ))
        
        fig_map.update_layout(
            mapbox_style="carto-darkmatter",
            mapbox=dict(center=dict(lat=12.9715, lon=77.6010), zoom=12.6),
            margin=dict(l=0, r=0, t=0, b=0),
            height=370,
            paper_bgcolor="#080B10",
        )
        st.plotly_chart(fig_map, use_container_width=True)
    
    with chart_col:
        st.markdown('<div class="section-hdr">QBER Threat Assessment & Thresholds</div>', unsafe_allow_html=True)
        
        sensors_list = list(sc.sensors.values())
        bar_colors = ['#EF4444' if (s['qber'] >= 11.0 or s['id'] in [sc.sensors[k]['id'] for k in sc.isolated_nodes]) else '#10B981' for s in sensors_list]
        
        fig_qber = go.Figure(go.Bar(
            x=[s['id'] for s in sensors_list],
            y=[s['qber'] for s in sensors_list],
            marker_color=bar_colors,
            text=[f"{s['qber']:.1f}%" for s in sensors_list],
            textposition='outside',
            textfont=dict(color='#F3F4F6', family="JetBrains Mono", size=11),
            hovertemplate="Node: %{x}<br>QBER: %{y:.1f}%<extra></extra>"
        ))
        
        fig_qber.add_hline(
            y=11.0, line_dash="dash", line_color="#EF4444", line_width=2,
            annotation_text="BB84 Security Threshold (11%)",
            annotation_font=dict(color="#EF4444", family="JetBrains Mono", size=10),
            annotation_position="top left"
        )
        
        fig_qber.update_layout(
            template="plotly_dark",
            paper_bgcolor="#080B10", plot_bgcolor="#0E131F",
            margin=dict(l=35, r=15, t=20, b=35),
            height=370,
            yaxis=dict(title="QBER (%)", range=[0, max(38, max(s['qber'] for s in sensors_list) + 8)], gridcolor="#162032"),
            xaxis=dict(gridcolor="#162032", tickangle=-30),
        )
        st.plotly_chart(fig_qber, use_container_width=True)
    
    # ══════════════════════════════════════════════════════════════
    # TELEMETRY TABLE + TERMINAL (Side by Side)
    # ══════════════════════════════════════════════════════════════
    st.markdown("---")
    
    tbl_col, term_col = st.columns([1.1, 0.9])
    
    with tbl_col:
        st.markdown('<div class="section-hdr">Metropolitan Node Telemetry & Vault Matrix</div>', unsafe_allow_html=True)
        
        rows = []
        for s_key, s in sc.sensors.items():
            latest = s['data_points'][-1]['value'] if s['data_points'] else 'N/A'
            is_iso = s_key in sc.isolated_nodes
            if is_iso:
                key_hash = "SEVERED"
                state_str = "ISOLATED"
            elif s['last_key']:
                key_hash = f"{s['last_key'][:8]}...{s['last_key'][-4:]}"
                state_str = s['status'].upper()
            else:
                key_hash = "BLACKOUT"
                state_str = s['status'].upper()
            
            rows.append({
                'Node ID': s['id'],
                'Type': s['type'],
                'Location': s['location'],
                'QBER (%)': round(s['qber'], 1),
                'Key Vault': f"{s.get('key_vault', 100.0):.0f}%",
                'Payload': str(latest),
                'AES-256 Key': key_hash,
                'State': state_str
            })
        
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "QBER (%)": st.column_config.NumberColumn(format="%.1f%%", help="Quantum Bit Error Rate"),
                "Key Vault": st.column_config.TextColumn(help="Stored reserve of QKD keys."),
                "AES-256 Key": st.column_config.TextColumn(help="Truncated SHA-256 digest of BB84 key."),
                "State": st.column_config.TextColumn(help="SECURE, COMPROMISED, BLACKOUT, or ISOLATED."),
                "Payload": st.column_config.TextColumn(help="Latest sensor telemetry reading."),
            }
        )
    
    with term_col:
        st.markdown('<div class="section-hdr">Cryptographic Handshake Log</div>', unsafe_allow_html=True)
        
        lines = []
        for entry in reversed(sc.terminal_logs):
            ts = entry['ts']
            level = entry['level']
            msg = entry['msg']
            
            if level == "SECURE":
                lines.append(f'<span class="tl-ts">[{ts}]</span> <span class="tl-secure">{msg}</span>')
            elif level == "WARN":
                lines.append(f'<span class="tl-ts">[{ts}]</span> <span class="tl-warn">{msg}</span>')
            elif level == "ALERT":
                lines.append(f'<span class="tl-ts">[{ts}]</span> <span class="tl-alert">{msg}</span>')
            else:
                lines.append(f'<span class="tl-ts">[{ts}]</span> <span class="tl-info">{msg}</span>')
        
        term_content = "<br>".join(lines) if lines else '<span class="tl-info">Awaiting handshake cycles...</span>'
        st.markdown(f'<div class="term-output">{term_content}</div>', unsafe_allow_html=True)
    
    # ══════════════════════════════════════════════════════════════
    # QUANTUM CAMERA HANDOFF & TRAFFIC ANOMALY MONITOR
    # ══════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown('<div class="section-hdr">QKD Dynamic Multi-Camera Handoff & Traffic Flow Surveillance</div>', unsafe_allow_html=True)
    
    trk = sc.tracking_target
    active_cam_node = sc.sensors.get('surveillance' if trk['active_camera'] == 'NODE-CAM-01' else 'traffic_light')
    is_cam_blackout = (active_cam_node['status'] == 'blackout') or ('surveillance' in sc.isolated_nodes and trk['active_camera'] == 'NODE-CAM-01')
    
    tc1, tc2, tc3, tc4 = st.columns([2, 1.5, 2, 2.5])
    with tc1:
        st.metric(
            "Tracked Target",
            trk['vehicle_id'],
            help="Intelligent metropolitan tracking: automated optical camera handoff across urban intersections secured by BB84 quantum keys."
        )
    with tc2:
        cam_disp = "OFFLINE (ISOLATED)" if is_cam_blackout else trk['active_camera']
        st.metric(
            "Active Camera Feed",
            cam_disp,
            help="Current video feed streaming target tracking metadata."
        )
    with tc3:
        pattern_color = "#EF4444" if "ANOMALY" in trk['pattern'] else "#10B981"
        st.markdown(f"""
        <div style="background: var(--bg-panel); border: 1px solid var(--border); padding: 10px 14px; height: 100%;">
            <div style="color: var(--text-muted); font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; font-weight: 600; text-transform: uppercase;">Traffic Pattern Analysis</div>
            <div style="color: {pattern_color}; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 0.95rem; margin-top: 4px;">{trk['pattern']} ({trk['speed_kmh']} km/h)</div>
        </div>
        """, unsafe_allow_html=True)
    with tc4:
        key_disp = trk['qkd_session_key'] if (trk['qkd_session_key'] and not is_cam_blackout) else "BLACKOUT (UNENCRYPTED FEED REFUSED)"
        st.markdown(f"""
        <div style="background: var(--bg-panel); border: 1px solid var(--border); padding: 10px 14px; height: 100%;">
            <div style="color: var(--text-muted); font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; font-weight: 600; text-transform: uppercase;">Camera Handoff BB84 Key Ring</div>
            <div style="color: var(--accent-cyan); font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; margin-top: 4px; word-break: break-all;"><code>{key_disp}</code></div>
        </div>
        """, unsafe_allow_html=True)
    
    # ══════════════════════════════════════════════════════════════
    # TREND CHARTS (Tabbed for All City Nodes)
    # ══════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown('<div class="section-hdr">Telemetry, Key Vault & QBER Time Series</div>', unsafe_allow_html=True)
    
    tab_labels = [
        "Traffic 01", "Traffic 02 (MG Rd)", "Hospital ICU", 
        "Financial Core", "Power Grid", "Water Utility", "Surveillance"
    ]
    tab_keys = [
        'traffic_light', 'traffic_junction', 'hospital_node',
        'financial_core', 'power_substation', 'water_meter', 'surveillance'
    ]
    tabs = st.tabs(tab_labels)
    
    for tab, key in zip(tabs, tab_keys):
        with tab:
            s = sc.sensors[key]
            if len(s['data_points']) >= 2:
                df_t = pd.DataFrame(s['data_points'])
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_t['time'], y=df_t['value'],
                    mode='lines+markers', name='Telemetry Value',
                    line=dict(color='#3B82F6', width=2),
                    hovertemplate="Value: %{y}<br>Time: %{x}<extra></extra>"
                ))
                fig.add_trace(go.Scatter(
                    x=df_t['time'], y=df_t['qber'],
                    mode='lines+markers', name='QBER (%)', yaxis='y2',
                    line=dict(color='#EF4444', width=2, dash='dash'),
                    hovertemplate="QBER: %{y:.1f}%<br>Time: %{x}<extra></extra>"
                ))
                if 'vault' in df_t.columns:
                    fig.add_trace(go.Scatter(
                        x=df_t['time'], y=df_t['vault'],
                        mode='lines+markers', name='Key Vault (%)', yaxis='y2',
                        line=dict(color='#10B981', width=2, dash='dot'),
                        hovertemplate="Vault: %{y:.0f}%<br>Time: %{x}<extra></extra>"
                    ))
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="#080B10", plot_bgcolor="#0E131F",
                    margin=dict(l=40, r=40, t=20, b=40),
                    height=280,
                    yaxis=dict(title="Telemetry", gridcolor="#162032"),
                    yaxis2=dict(title="QBER & Vault (%)", overlaying="y", side="right",
                                range=[0, 105], gridcolor="#162032"),
                    xaxis=dict(gridcolor="#162032"),
                    hovermode='x unified',
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Collecting data points — click 'Execute Telemetry Cycle' to generate readings.")
    
    # ══════════════════════════════════════════════════════════════
    # SECURITY AUDIT LOG
    # ══════════════════════════════════════════════════════════════
    st.markdown("---")
    
    with st.expander("Security Audit Event Log", expanded=False):
        events = []
        for s in sc.sensors.values():
            if s['status'] == 'compromised':
                events.append({
                    'Time': s['last_update'].strftime('%H:%M:%S'),
                    'Node': s['id'],
                    'Location': s['location'],
                    'Event': 'ATTACK DETECTED',
                    'QBER': f"{s['qber']:.1f}%",
                    'Action': 'Key aborted, transmission blocked'
                })
            elif s['last_key']:
                events.append({
                    'Time': s['last_update'].strftime('%H:%M:%S'),
                    'Node': s['id'],
                    'Location': s['location'],
                    'Event': 'KEY EXCHANGE OK',
                    'QBER': f"{s['qber']:.1f}%",
                    'Action': f"Encrypted via AES-256 ({s['last_key'][:8]}...)"
                })
        
        if events:
            st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
        else:
            st.caption("No security events recorded yet.")
    
    # ══════════════════════════════════════════════════════════════
    # BB84 PROTOCOL REFERENCE
    # ══════════════════════════════════════════════════════════════
    with st.expander("BB84 Protocol Reference", expanded=False):
        st.markdown("""
**BB84 Quantum Key Distribution Protocol**

1. **Quantum State Preparation** — Alice encodes random bits into photon polarization states using randomly chosen rectilinear or diagonal bases.
2. **Quantum Transmission** — Photons travel through the quantum channel to Bob.
3. **Measurement** — Bob measures each photon in a randomly chosen basis.
4. **Basis Reconciliation (Sifting)** — Alice and Bob publicly compare bases and keep only bits where they used the same basis.
5. **QBER Estimation** — A random sample of sifted bits is compared to estimate the Quantum Bit Error Rate.
6. **Security Decision** — If QBER ≥ 11%, the exchange is aborted (eavesdropper detected). If QBER < 11%, the remaining sifted bits undergo privacy amplification.
7. **Key Derivation** — SHA-256 hashing produces a 256-bit AES-GCM symmetric key for payload encryption.
        """)

if __name__ == "__main__":
    main()