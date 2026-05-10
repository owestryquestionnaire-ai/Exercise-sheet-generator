import streamlit as st
from datetime import datetime
import json
import os
import qrcode
import cv2
import numpy as np
from io import BytesIO

st.set_page_config(page_title="Exercise Prescription System", layout="wide")

# --- Custom CSS ---
st.markdown(
    """
    <style>
    html, body, [class*="css"]  { font-size: 18px !important; }
    h1 { font-size: 26px !important; font-weight:700 !important; }
    h2 { font-size: 20px !important; font-weight:600 !important; }
    .exercise-title { font-size:20px !important; font-weight:700 !important; margin-top: 8px; }
    .cart-item { font-size: 16px; color: #2e7d32; font-weight: 500; margin-bottom: 2px; }

    @media print {
        .stButton, .stSelectbox, .stTextInput, [data-testid="stSidebar"], 
        header, [data-testid="stHeader"], .no-print, [data-testid="stCameraInput"], .stMultiSelect {
            display: none !important;
        }
        .main .block-container { padding: 0 !important; margin: 0 !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

HISTORY_FILE = "prescription_history.json"


def save_to_history(p_code, prescription):
    data = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = {}
    if p_code not in data: data[p_code] = []
    data[p_code].append({"timestamp": datetime.now().strftime('%m/%d/%Y %H:%M'), "exercises": prescription})
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


EXERCISE_DB = {
    "Electrotherapy": [
        {"id": "e1", "name": "Ice + Magnetopulse"},
        {"id": "e2", "name": "Gameready"},
        {"id": "e3", "name": "Electrical Muscle Stimulation"},
        {"id": "e4", "name": "Lymphapress"},
    ],
    "Mobilization": [
        {"id": "s3", "name": "Knee to chest mob (gymball)"},
        {"id": "s4", "name": "Static bike"},
        {"id": "s5", "name": "Nustep"},
        {"id": "s7", "name": "Sling suspension"},
        {"id": "s8", "name": "Reciprocal pulley"}
    ],
    "Strengthening": [
        {"id": "st1", "name": "Quad exercise"},
        {"id": "st2", "name": "Standing + Hamstring curl"},
        {"id": "st3", "name": "Wall slides (gymball)"},
        {"id": "st4", "name": "企 + Hip strengthening"},
        {"id": "st7", "name": "Bridging"}  # New Bridging exercise
    ],
    "Functional training": [
        {"id": "f4", "name": "Stepping on box"},
        {"id": "f6", "name": "跨欄 (Hurdles)"},
        {"id": "f7", "name": "Stepping ex on foam"}  # New Foam stepping exercise
    ],
}

# --- Session State Initialization ---
if "show_sheet" not in st.session_state: st.session_state.show_sheet = False
if "prescription" not in st.session_state: st.session_state.prescription = []
if "p_code_input" not in st.session_state: st.session_state.p_code_input = ""
if "search_query" not in st.session_state: st.session_state.search_query = ""

if "master_registry" not in st.session_state:
    st.session_state.master_registry = {}

for cat_name, items in EXERCISE_DB.items():
    for ex in items:
        eid = ex["id"]
        default_mins = "15" if eid.startswith("e") else "10"

        # Define all default parameters centrally to prevent KeyErrors
        default_params = {
            "selected": False, "mins": default_mins,
            "side": "Right knee", "press": "Low pressure", "deg": "1",
            "e3_side": "Right quadriceps", "stim_mode_R": "Static Quads", "weight_R": "",
            "stim_mode_L": "Static Quads", "weight_L": "",
            "e4_side": "Right leg",
            "bike_range": "Full Circle", "level": "1", "seat": "",
            "s3_ball": "紅波", "s5_long_seat": False, "s8_towel": False,
            "s7_modes": ["平訓＋打開腳"], "s7_band": False, "s7_band_color": "Red theraband",
            "st1_weight": "", "st2_weight": "", "st3_ball": "紅波",

            # Dynamic Hip Sub-item Parameters
            "st4_modes": [],
            "st4_side_ground": False, "st4_side_band": False, "st4_side_res": "Red (Medium)",
            "st4_front_ground": False, "st4_front_band": False, "st4_front_res": "Red (Medium)",
            "st4_back_ground": False, "st4_back_band": False, "st4_back_res": "Red (Medium)",

            # New Bridging Parameters
            "st7_ball": "紅波", "st7_pos": "於膝下",

            "seat_type": "Short Seat", "sling_move": "Hip Abduction",
            "wave": "Blue Wave", "box_height": "4\"", "downstairs": False,
            "hurdle_height": "4\"", "lymph_press": "40 mmHg",

            # New Foam Stepping Parameters
            "f7_bars": False, "f7_family": False
        }

        if eid not in st.session_state.master_registry:
            # If completely new exercise, copy all defaults
            st.session_state.master_registry[eid] = default_params.copy()
        else:
            # If it exists, gracefully patch in any newly added parameters
            for key, val in default_params.items():
                if key not in st.session_state.master_registry[eid]:
                    st.session_state.master_registry[eid][key] = val


def update_registry(eid, field, value):
    st.session_state.master_registry[eid][field] = value


# --- Sidebar: History & QR ---
with st.sidebar:
    st.header("Patient History")
    with st.expander("📷 Scan QR"):
        img_file = st.camera_input("Scan QR")
        if img_file:
            file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
            opencv_img = cv2.imdecode(file_bytes, 1)
            det = cv2.QRCodeDetector()
            data, _, _ = det.detectAndDecode(opencv_img)
            if data:
                st.session_state.search_query = data
                st.success(f"ID: {data}")

    search_code = st.text_input("Lookup Patient ID", key="search_query")
    if search_code and os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        if search_code in history:
            if st.button("Load Most Recent"):
                last = history[search_code][-1]["exercises"]

                # Clear all registry and UI widget states first
                for eid in st.session_state.master_registry:
                    st.session_state.master_registry[eid]["selected"] = False
                    if f"chk_{eid}" in st.session_state:
                        st.session_state[f"chk_{eid}"] = False

                # Apply the loaded prescription
                for item in last:
                    eid = item["id"]
                    if eid in st.session_state.master_registry:
                        reg = st.session_state.master_registry[eid]
                        reg["selected"] = True
                        if f"chk_{eid}" in st.session_state:
                            st.session_state[f"chk_{eid}"] = True
                        for k, v in item.items(): reg[k] = v

                st.session_state.p_code_input = search_code
                st.rerun()

# --- Main Interface ---
if not st.session_state.show_sheet:
    st.title("Exercise Prescription")
    l_col, r_col = st.columns([1.2, 3])

    with l_col:
        st.subheader("Patient Info")
        st.text_input("Patient Code", key="p_code_input")
        category = st.selectbox("Category Filter", ["All categories"] + list(EXERCISE_DB.keys()))

        c1, c2 = st.columns(2)
        generate_btn = c1.button("Generate", type="primary", use_container_width=True)

        # Clear All Button - Resets dictionary AND widget state
        if c2.button("Clear All", use_container_width=True):
            for eid in st.session_state.master_registry:
                st.session_state.master_registry[eid]["selected"] = False
                if f"chk_{eid}" in st.session_state:
                    st.session_state[f"chk_{eid}"] = False
            st.rerun()

        st.markdown("---")
        st.subheader("🛒 Cart")
        for cat_name, items in EXERCISE_DB.items():
            for ex in items:
                eid = ex["id"]
                if st.session_state.master_registry[eid]["selected"]:
                    m = st.session_state.master_registry[eid]["mins"]
                    st.markdown(f'<div class="cart-item">✅ {ex["name"]} ({m}m)</div>', unsafe_allow_html=True)

    with r_col:
        cats = list(EXERCISE_DB.keys()) if category == "All categories" else [category]
        for cat in cats:
            st.markdown(f"## {cat}")
            for ex in EXERCISE_DB[cat]:
                eid = ex["id"]
                reg = st.session_state.master_registry[eid]

                # Main Exercise Row
                col1, col2, col3 = st.columns([0.1, 0.6, 0.3])
                col1.checkbox("", value=reg["selected"], key=f"chk_{eid}",
                              on_change=lambda e=eid: update_registry(e, "selected", st.session_state[f"chk_{e}"]))

                # Render Title
                col2.markdown(
                    f'<div class="exercise-title">{ex["name"]}</div>',
                    unsafe_allow_html=True)

                col3.text_input("Mins", value=reg["mins"], key=f"m_{eid}",
                                on_change=lambda e=eid: update_registry(e, "mins", st.session_state[f"m_{e}"]))

                # Parameter Row (Only shows if selected)
                if reg["selected"]:
                    _, indent_col = st.columns([0.1, 0.9])

                    with indent_col:
                        p1, p2, p3 = st.columns(3)

                        if eid == "e1":
                            p1.selectbox("Side", ["Right knee", "Left knee", "Bilateral knee"], key=f"s_{eid}",
                                         on_change=lambda e=eid: update_registry(e, "side", st.session_state[f"s_{e}"]))

                        elif eid == "e2":
                            p1.selectbox("Side", ["Right knee", "Left knee"], key=f"s_{eid}",
                                         on_change=lambda e=eid: update_registry(e, "side", st.session_state[f"s_{e}"]))
                            p2.selectbox("Pressure", ["Low pressure", "Medium pressure"], key=f"pr_{eid}",
                                         on_change=lambda e=eid: update_registry(e, "press",
                                                                                 st.session_state[f"pr_{e}"]))
                            p3.text_input("Temp (°C)", value=reg["deg"], key=f"dg_{eid}",
                                          on_change=lambda e=eid: update_registry(e, "deg",
                                                                                  st.session_state[f"dg_{e}"]))

                        elif eid == "e3":
                            p1.selectbox("Side", ["Right quadriceps", "Left quadriceps", "Bilateral quadriceps"],
                                         key=f"s_{eid}",
                                         on_change=lambda e=eid: update_registry(e, "e3_side",
                                                                                 st.session_state[f"s_{e}"]))
                            e3_side = reg["e3_side"]

                            if e3_side in ["Right quadriceps", "Left quadriceps"]:
                                p2.selectbox("Mode", ["Static Quads", "Quad Board 踢腳", "沙包壓腳"], key=f"sm_R_{eid}",
                                             on_change=lambda e=eid: update_registry(e, "stim_mode_R",
                                                                                     st.session_state[f"sm_R_{e}"]))
                                if reg["stim_mode_R"] != "Static Quads":
                                    p3.text_input("Sandbag Weight (lbs)", value=reg["weight_R"], key=f"w_R_{eid}",
                                                  on_change=lambda e=eid: update_registry(e, "weight_R",
                                                                                          st.session_state[f"w_R_{e}"]))
                            else:
                                st.markdown(
                                    "<div style='margin-top: 10px; font-weight: 600; color: #555;'>Bilateral Configuration</div>",
                                    unsafe_allow_html=True)
                                b1, b2 = st.columns(2)
                                with b1:
                                    st.selectbox("Mode (Right)", ["Static Quads", "Quad Board 踢腳", "沙包壓腳"],
                                                 key=f"sm_R_{eid}",
                                                 on_change=lambda e=eid: update_registry(e, "stim_mode_R",
                                                                                         st.session_state[f"sm_R_{e}"]))
                                    if reg["stim_mode_R"] != "Static Quads":
                                        st.text_input("Sandbag Weight (lbs) (Right)", value=reg["weight_R"],
                                                      key=f"w_R_{eid}",
                                                      on_change=lambda e=eid: update_registry(e, "weight_R",
                                                                                              st.session_state[
                                                                                                  f"w_R_{e}"]))
                                with b2:
                                    st.selectbox("Mode (Left)", ["Static Quads", "Quad Board 踢腳", "沙包壓腳"],
                                                 key=f"sm_L_{eid}",
                                                 on_change=lambda e=eid: update_registry(e, "stim_mode_L",
                                                                                         st.session_state[f"sm_L_{e}"]))
                                    if reg["stim_mode_L"] != "Static Quads":
                                        st.text_input("Sandbag Weight (lbs) (Left)", value=reg["weight_L"],
                                                      key=f"w_L_{eid}",
                                                      on_change=lambda e=eid: update_registry(e, "weight_L",
                                                                                              st.session_state[
                                                                                                  f"w_L_{e}"]))

                        elif eid == "e4":
                            p1.selectbox("Side", ["Right leg", "Left leg", "Bilateral legs"], key=f"s_{eid}",
                                         on_change=lambda e=eid: update_registry(e, "e4_side",
                                                                                 st.session_state[f"s_{e}"]))
                            p2.selectbox("Parameter", ["40 mmHg", "50 mmHg", "60 mmHg"], key=f"lp_{eid}",
                                         on_change=lambda e=eid: update_registry(e, "lymph_press",
                                                                                 st.session_state[f"lp_{e}"]))

                        # --- Mobilization Configs ---
                        elif eid == "s3":
                            p1.selectbox("Ball Option", ["紅波", "藍波"], key=f"bll_{eid}",
                                         on_change=lambda e=eid: update_registry(e, "s3_ball",
                                                                                 st.session_state[f"bll_{e}"]))

                        elif eid == "s4":
                            p1.selectbox("Bike Range", ["Full Circle", "Half Circle"], key=f"br_{eid}",
                                         on_change=lambda e=eid: update_registry(e, "bike_range",
                                                                                 st.session_state[f"br_{e}"]))

                        elif eid == "s5":
                            p1.text_input("Level", value=reg["level"], key=f"lv_{eid}",
                                          on_change=lambda e=eid: update_registry(e, "level",
                                                                                  st.session_state[f"lv_{e}"]))
                            p2.text_input("Seat Position", value=reg["seat"], key=f"se_{eid}",
                                          on_change=lambda e=eid: update_registry(e, "seat",
                                                                                  st.session_state[f"se_{e}"]))
                            p3.checkbox("Long Seat", value=reg["s5_long_seat"], key=f"ls_{eid}",
                                        on_change=lambda e=eid: update_registry(e, "s5_long_seat",
                                                                                st.session_state[f"ls_{e}"]))

                        elif eid == "s7":
                            p1.multiselect("Modes", ["平訓＋打開腳", "側訓＋前後"], default=reg.get("s7_modes", []),
                                           key=f"sm_{eid}",
                                           on_change=lambda e=eid: update_registry(e, "s7_modes",
                                                                                   st.session_state[f"sm_{e}"]))
                            p2.checkbox("加橡根", value=reg["s7_band"], key=f"sb_{eid}",
                                        on_change=lambda e=eid: update_registry(e, "s7_band",
                                                                                st.session_state[f"sb_{e}"]))
                            if reg["s7_band"]:
                                p3.selectbox("Band Color", ["Red theraband", "Green theraband"], key=f"sbc_{eid}",
                                             on_change=lambda e=eid: update_registry(e, "s7_band_color",
                                                                                     st.session_state[f"sbc_{e}"]))

                        elif eid == "s8":
                            p1.checkbox("毛巾於膝下", value=reg["s8_towel"], key=f"st_{eid}",
                                        on_change=lambda e=eid: update_registry(e, "s8_towel",
                                                                                st.session_state[f"st_{e}"]))

                        # --- Strengthening Configs ---
                        elif eid == "st1":
                            p1.text_input("Sandbag Weight (lbs)", value=reg["st1_weight"], key=f"w_{eid}",
                                          on_change=lambda e=eid: update_registry(e, "st1_weight",
                                                                                  st.session_state[f"w_{e}"]))

                        elif eid == "st2":
                            p1.text_input("Sandbag Weight (lbs)", value=reg["st2_weight"], key=f"w_{eid}",
                                          on_change=lambda e=eid: update_registry(e, "st2_weight",
                                                                                  st.session_state[f"w_{e}"]))

                        elif eid == "st3":
                            p1.selectbox("Ball Option", ["紅波", "藍波"], key=f"bll_{eid}",
                                         on_change=lambda e=eid: update_registry(e, "st3_ball",
                                                                                 st.session_state[f"bll_{e}"]))

                        elif eid == "st4":
                            # Dynamic Hip Exercises Sub-menus
                            st.multiselect("Directions", ["側 (Abduction)", "前 (Flexion)", "後 (Extension)"],
                                           default=reg.get("st4_modes", []), key=f"md_{eid}",
                                           on_change=lambda e=eid: update_registry(e, "st4_modes",
                                                                                   st.session_state[f"md_{e}"]))

                            for mode in reg.get("st4_modes", []):
                                st.markdown(
                                    f"<div style='margin-top: 5px; font-weight: 600; color: #555; font-size: 14px;'>↳ {mode} Configuration</div>",
                                    unsafe_allow_html=True)
                                m1, m2, m3 = st.columns(3)

                                # Determine the parameter prefix based on the selected mode
                                prefix = "side" if "側" in mode else "front" if "前" in mode else "back"

                                m1.checkbox("腳踩地", value=reg[f"st4_{prefix}_ground"], key=f"grnd_{prefix}_{eid}",
                                            on_change=lambda e=eid, p=prefix: update_registry(e, f"st4_{p}_ground",
                                                                                              st.session_state[
                                                                                                  f"grnd_{p}_{e}"]))

                                m2.checkbox("Theraband", value=reg[f"st4_{prefix}_band"], key=f"tb_{prefix}_{eid}",
                                            on_change=lambda e=eid, p=prefix: update_registry(e, f"st4_{p}_band",
                                                                                              st.session_state[
                                                                                                  f"tb_{p}_{e}"]))

                                if reg[f"st4_{prefix}_band"]:
                                    m3.selectbox("Resistance", ["Yellow (Light)", "Red (Medium)", "Green (Heavy)",
                                                                "Blue (Extra Heavy)"],
                                                 index=["Yellow (Light)", "Red (Medium)", "Green (Heavy)",
                                                        "Blue (Extra Heavy)"].index(reg[f"st4_{prefix}_res"]),
                                                 key=f"res_{prefix}_{eid}",
                                                 on_change=lambda e=eid, p=prefix: update_registry(e, f"st4_{p}_res",
                                                                                                   st.session_state[
                                                                                                       f"res_{p}_{e}"]))

                        elif eid == "st7":
                            p1.selectbox("Ball Option", ["紅波", "藍波"], key=f"bll_{eid}",
                                         on_change=lambda e=eid: update_registry(e, "st7_ball",
                                                                                 st.session_state[f"bll_{e}"]))
                            p2.selectbox("Position", ["於膝下", "腳腕下"], key=f"pos_{eid}",
                                         on_change=lambda e=eid: update_registry(e, "st7_pos",
                                                                                 st.session_state[f"pos_{e}"]))

                        # --- Functional Configs ---
                        elif eid == "f4":
                            p1.selectbox("Box Height", ["4\"", "6\"", "8\""], key=f"bh_{eid}",
                                         on_change=lambda e=eid: update_registry(e, "box_height",
                                                                                 st.session_state[f"bh_{e}"]))
                            p2.checkbox("Downstairs Training", value=reg["downstairs"], key=f"ds_{eid}",
                                        on_change=lambda e=eid: update_registry(e, "downstairs",
                                                                                st.session_state[f"ds_{e}"]))
                        elif eid == "f6":
                            p1.selectbox("Hurdle Height", ["4\"", "6\""], key=f"hh_{eid}",
                                         on_change=lambda e=eid: update_registry(e, "hurdle_height",
                                                                                 st.session_state[f"hh_{e}"]))
                        elif eid == "f7":
                            p1.checkbox("於平衡架內", value=reg["f7_bars"], key=f"bar_{eid}",
                                        on_change=lambda e=eid: update_registry(e, "f7_bars",
                                                                                st.session_state[f"bar_{e}"]))
                            p2.checkbox("家人陪", value=reg["f7_family"], key=f"fam_{eid}",
                                        on_change=lambda e=eid: update_registry(e, "f7_family",
                                                                                st.session_state[f"fam_{e}"]))
                st.markdown("---")

    if generate_btn:
        if not st.session_state.p_code_input:
            st.error("Missing Patient ID.")
        else:
            valid_params = {
                "e1": ["side"],
                "e2": ["side", "press", "deg"],
                "e3": ["e3_side", "stim_mode_R", "weight_R", "stim_mode_L", "weight_L"],
                "e4": ["e4_side", "lymph_press"],
                "s3": ["s3_ball"],
                "s4": ["bike_range"],
                "s5": ["level", "seat", "s5_long_seat"],
                "s7": ["s7_modes", "s7_band", "s7_band_color"],
                "s8": ["s8_towel"],
                "st1": ["st1_weight"],
                "st2": ["st2_weight"],
                "st3": ["st3_ball"],
                "st4": ["st4_modes",
                        "st4_side_ground", "st4_side_band", "st4_side_res",
                        "st4_front_ground", "st4_front_band", "st4_front_res",
                        "st4_back_ground", "st4_back_band", "st4_back_res"],
                "st7": ["st7_ball", "st7_pos"],  # Bridging
                "f4": ["box_height", "downstairs"],
                "f6": ["hurdle_height"],
                "f7": ["f7_bars", "f7_family"]  # Foam stepping
            }

            final_p = []
            for eid, data in st.session_state.master_registry.items():
                if data["selected"]:
                    name = next(ex["name"] for cat in EXERCISE_DB.values() for ex in cat if ex["id"] == eid)
                    item = {"id": eid, "name": name, "mins": data["mins"]}

                    allowed_keys = valid_params.get(eid, [])
                    for k in allowed_keys:
                        if k in data and data[k] is not None and data[k] != "":
                            item[k] = data[k]

                    final_p.append(item)

            if final_p:
                save_to_history(st.session_state.p_code_input, final_p)
                st.session_state.prescription = final_p
                st.session_state.show_sheet = True
                st.rerun()
            else:
                st.warning("Please select at least one exercise.")

# --- Print Sheet View ---
if st.session_state.show_sheet:
    h_col1, h_col2 = st.columns([3, 1])
    with h_col1:
        st.header("Exercise Prescription Sheet")
        st.write(f"**Patient ID:** {st.session_state.p_code_input} | **Date:** {datetime.now().strftime('%m/%d/%Y')}")

    with h_col2:
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(st.session_state.p_code_input);
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO();
        img.save(buf, format="PNG")
        st.image(buf, width=130)

    st.divider()
    for item in st.session_state.prescription:
        name, mins = item['name'], item.get('mins', '15')
        details = []
        eid = item['id']

        # --- Handle EMS Specific Output Logic ---
        if eid == "e3":
            side = item.get("e3_side", "Right quadriceps")
            details.append(side)

            if side == "Bilateral quadriceps":
                r_mode = item.get("stim_mode_R", "Static Quads")
                l_mode = item.get("stim_mode_L", "Static Quads")

                r_w = item.get("weight_R", "")
                r_str = f"R: {r_mode}" + (f" ({r_w} lbs)" if r_mode != "Static Quads" and r_w else "")

                l_w = item.get("weight_L", "")
                l_str = f"L: {l_mode}" + (f" ({l_w} lbs)" if l_mode != "Static Quads" and l_w else "")

                details.append(f"[{r_str} | {l_str}]")
            else:
                mode = item.get("stim_mode_R", "Static Quads")
                weight = item.get("weight_R", "")
                details.append(mode)
                if mode != "Static Quads" and weight:
                    details.append(f"{weight} lbs")

        # --- Handle Standard Output Logic ---
        else:
            if 'side' in item: details.append(item['side'])
            if 'e4_side' in item: details.append(item['e4_side'])
            if 'press' in item: details.append(item['press'])
            if 'deg' in item: details.append(f"{item['deg']}°C")
            if 'lymph_press' in item: details.append(item['lymph_press'])

            # Mobilization
            if 's3_ball' in item: details.append(item['s3_ball'])
            if item.get('s5_long_seat'): details.append("Long Seat")
            if item.get('s7_modes'): details.append(" & ".join(item['s7_modes']))
            if item.get('s7_band'): details.append(f"加橡根 ({item.get('s7_band_color', '')})")
            if item.get('s8_towel'): details.append("毛巾於膝下")

            if 'bike_range' in item: details.append(item['bike_range'])
            if 'level' in item: details.append(f"Level {item['level']}")
            if 'seat' in item: details.append(f"Seat {item['seat']}")

            # Strengthening
            if item.get('st1_weight'): details.append(f"{item['st1_weight']} lbs")
            if item.get('st2_weight'): details.append(f"{item['st2_weight']} lbs")
            if 'st3_ball' in item: details.append(item['st3_ball'])

            if 'st7_ball' in item: details.append(item['st7_ball'])
            if 'st7_pos' in item: details.append(item['st7_pos'])

            # Hip Exercises Output formatter
            if eid == "st4" and item.get("st4_modes"):
                for mode in item["st4_modes"]:
                    prefix = "side" if "側" in mode else "front" if "前" in mode else "back"
                    mode_details = []
                    if item.get(f"st4_{prefix}_ground"): mode_details.append("腳踩地")
                    if item.get(f"st4_{prefix}_band"): mode_details.append(
                        f"Theraband: {item.get(f'st4_{prefix}_res', '')}")

                    if mode_details:
                        details.append(f"{mode} ({', '.join(mode_details)})")
                    else:
                        details.append(f"{mode}")

            # Functional
            if 'box_height' in item: details.append(f"Box Height: {item['box_height']}")
            if item.get('downstairs') == True: details.append("Downstairs training")
            if 'hurdle_height' in item: details.append(f"Hurdle Height: {item['hurdle_height']}")

            if item.get('f7_bars'): details.append("於平衡架內")
            if item.get('f7_family'): details.append("家人陪")

        # Safety net: Convert all variables to strings before joining
        d_str = f" ({', '.join(str(d) for d in details)})" if details else ""
        st.markdown(f'<div style="font-size:24px; font-weight:700;">- {name}{d_str} x {mins} mins</div>',
                    unsafe_allow_html=True)

    st.divider()
    if st.button("Back to Selection"): st.session_state.show_sheet = False; st.rerun()