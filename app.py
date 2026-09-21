"""
UCSB Ski & Snowboard Team Dashboard
Main Streamlit Application Entrypoint
Dark theme with the two classic blues as highlight colors.
Features new skier line-art logo, To-Do delegation, and Merch inventory tracking.
"""

import os
import sys

# Ensure repository root is on sys.path for Streamlit Cloud execution
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import streamlit as st
import streamlit.components.v1 as components
from streamlit.delta_generator import DeltaGenerator

# Helper to detect the Active Member Searchable selectbox in Trip Creator
def _is_searchable_member_arg(*args, **kwargs):
    key = str(kwargs.get("key", ""))
    label = str(args[0]) if args else str(kwargs.get("label", ""))
    return "sel_active_member" in key or "Select Active Member" in label

# Globally remove typing/search filter from all selectbox and multiselect dropdown menus,
# EXCEPT for the Select Active Member (Searchable) dropdown in Trip Creator.
_orig_dg_sb = DeltaGenerator.selectbox
def _patched_dg_sb(self, *args, **kwargs):
    if "filter_mode" not in kwargs:
        if _is_searchable_member_arg(*args, **kwargs):
            kwargs["filter_mode"] = "fuzzy"
        else:
            kwargs["filter_mode"] = None
    elif _is_searchable_member_arg(*args, **kwargs) and kwargs.get("filter_mode") is None:
        kwargs["filter_mode"] = "fuzzy"
    return _orig_dg_sb(self, *args, **kwargs)
DeltaGenerator.selectbox = _patched_dg_sb

_orig_st_sb = st.selectbox
def _patched_st_sb(*args, **kwargs):
    if "filter_mode" not in kwargs:
        if _is_searchable_member_arg(*args, **kwargs):
            kwargs["filter_mode"] = "fuzzy"
        else:
            kwargs["filter_mode"] = None
    elif _is_searchable_member_arg(*args, **kwargs) and kwargs.get("filter_mode") is None:
        kwargs["filter_mode"] = "fuzzy"
    return _orig_st_sb(*args, **kwargs)
st.selectbox = _patched_st_sb

_orig_dg_ms = DeltaGenerator.multiselect
def _patched_dg_ms(self, *args, **kwargs):
    if "filter_mode" not in kwargs:
        kwargs["filter_mode"] = None
    return _orig_dg_ms(self, *args, **kwargs)
DeltaGenerator.multiselect = _patched_dg_ms

_orig_st_ms = st.multiselect
def _patched_st_ms(*args, **kwargs):
    if "filter_mode" not in kwargs:
        kwargs["filter_mode"] = None
    return _orig_st_ms(*args, **kwargs)
st.multiselect = _patched_st_ms

# Auto-detect if files were uploaded inside a subfolder (e.g., "Ski Team Dash")
if not os.path.exists(os.path.join(ROOT_DIR, "utils", "data_manager.py")):
    for item in os.listdir(ROOT_DIR):
        candidate = os.path.join(ROOT_DIR, item)
        if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "utils", "data_manager.py")):
            ROOT_DIR = candidate
            if ROOT_DIR not in sys.path:
                sys.path.insert(0, ROOT_DIR)
            break

# If still missing, display clear diagnostics instead of an uncaught ModuleNotFoundError
if not os.path.exists(os.path.join(ROOT_DIR, "utils", "data_manager.py")):
    st.error("Missing required folders in your GitHub repository.")
    current_files = os.listdir(os.path.dirname(os.path.abspath(__file__)))
    st.write("Files currently detected in root:")
    st.code(str(current_files))
    st.info(
        "Please make sure the 'utils', 'modules', 'data', and 'assets' folders are uploaded to your GitHub repository."
    )
    st.stop()

import config
import importlib
import utils.data_manager
import modules.financials
import modules.ledger
import modules.registration
import modules.merch
import modules.trip_creator
import modules.trip_estimator
import modules.todo
import modules.calendar_view

# Ensure config and submodules are freshly reloaded on each run
importlib.reload(config)
importlib.reload(utils.data_manager)
importlib.reload(modules.financials)
importlib.reload(modules.ledger)
importlib.reload(modules.registration)
importlib.reload(modules.merch)
importlib.reload(modules.trip_creator)
importlib.reload(modules.trip_estimator)
importlib.reload(modules.todo)
importlib.reload(modules.calendar_view)

from config import THEME_COLORS, CURRENT_SEASON, AVAILABLE_SEASONS, OFFICER_PASSWORD

from utils.data_manager import (
    ensure_data_initialized, get_financial_kpis, load_members,
    load_trips, load_events, load_todos, get_merch_inventory_summary
)
from modules.financials import render_financials_tab
from modules.ledger import render_ledger_tab
from modules.registration import render_registration_tab
from modules.merch import render_merch_tab
from modules.trip_creator import render_trip_creator_tab
from modules.trip_estimator import render_trip_estimator_tab
from modules.todo import render_todo_tab
from modules.calendar_view import render_calendar_tab

# Ensure .streamlit/config.toml exists on the deployment host
streamlit_config_dir = os.path.join(ROOT_DIR, ".streamlit")
streamlit_config_path = os.path.join(streamlit_config_dir, "config.toml")
if not os.path.exists(streamlit_config_path):
    try:
        os.makedirs(streamlit_config_dir, exist_ok=True)
        with open(streamlit_config_path, "w", encoding="utf-8") as f:
            f.write("""[theme]
base = "dark"
primaryColor = "#5d6895"
backgroundColor = "#0e131f"
secondaryBackgroundColor = "#171f30"
textColor = "#f0f4f8"
font = "sans serif"

[client]
showErrorDetails = true
""")
    except Exception:
        pass

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="UCSB Ski Team Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- INJECT CUSTOM CSS FOR DARK THEME WITH TWO BLUES HIGHLIGHTS ---
st.markdown("""
<style>
    /* Global Streamlit Theme Variables - Force Periwinkle Blue and Dark Theme */
    :root, .stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], * {
        color-scheme: dark !important;
        --primary-color: #5d6895 !important;
        --primary: #5d6895 !important;
        --background-color: #0e131f !important;
        --secondary-background-color: #171f30 !important;
        --text-color: #f0f4f8 !important;
    }

    /* Main Application Surface Background */
    .stApp,
    div[data-testid="stAppViewContainer"],
    div[data-testid="stAppViewContainer"] > section:first-child,
    header[data-testid="stHeader"] {
        background-color: #0e131f !important;
        color: #f0f4f8 !important;
    }

    /* Sidebar Background & Border */
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] > div:first-child,
    div[data-testid="stSidebarContent"],
    div[data-testid="stSidebarUserContent"] {
        background-color: #171f30 !important;
        border-right: 1px solid #283552 !important;
    }
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label {
        color: #f0f4f8 !important;
    }

    /* Header Banner with Dark Surface and Periwinkle Accent */
    .main-header {
        background: linear-gradient(135deg, #131b2e 0%, #1a253d 100%);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        border-bottom: 3px solid #5d6895;
        border-left: 1px solid rgba(93, 104, 149, 0.3);
        border-top: 1px solid rgba(93, 104, 149, 0.3);
        border-right: 1px solid rgba(93, 104, 149, 0.3);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
    }
    .main-header h1 {
        color: #ffffff !important;
        margin: 0;
        font-size: 2.1rem;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    .main-header p {
        color: #8ea4c8 !important;
        margin: 0.3rem 0 0 0;
        font-size: 1.05rem;
    }

    /* Dark Metric Card Styling with Slate Border */
    div[data-testid="stMetric"] {
        background-color: #171f30 !important;
        border: 1px solid #283552 !important;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
    }
    div[data-testid="stMetricLabel"] p {
        color: #8ea4c8 !important;
    }
    div[data-testid="stMetricValue"] div {
        color: #f0f4f8 !important;
    }

    /* DASHBOARD SELECTOR (Sidebar Navigation Radio) - The Two Blues */
    div[data-testid="stRadio"] [role="radiogroup"] label {
        cursor: pointer !important;
    }
    /* Resting outer circle */
    div[data-testid="stRadio"] [role="radiogroup"] input + div,
    div[data-testid="stRadio"] [role="radiogroup"] input ~ div,
    div[data-testid="stRadio"] [role="radiogroup"] label > div:first-child > div:last-child {
        border: 2px solid #283552 !important;
        background-color: transparent !important;
    }
    /* Hover outer circle */
    div[data-testid="stRadio"] [role="radiogroup"] label:hover input + div,
    div[data-testid="stRadio"] [role="radiogroup"] label:hover input ~ div,
    div[data-testid="stRadio"] [role="radiogroup"] label:hover > div:first-child > div:last-child {
        border-color: #4a72b8 !important;
    }
    /* Checked outer ring */
    div[data-testid="stRadio"] [role="radiogroup"] input:checked + div,
    div[data-testid="stRadio"] [role="radiogroup"] input:checked ~ div,
    div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) input + div,
    div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) input ~ div,
    div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) > div:first-child > div:last-child {
        border-color: #5d6895 !important;
        background-color: transparent !important;
    }
    /* Checked inner dot */
    div[data-testid="stRadio"] [role="radiogroup"] input:checked + div > div,
    div[data-testid="stRadio"] [role="radiogroup"] input:checked ~ div > div,
    div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) input + div > div,
    div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) input ~ div > div,
    div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) > div:first-child > div:last-child > div {
        background-color: #5d6895 !important;
    }
    /* Active navigation text */
    div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) p,
    div[data-testid="stRadio"] [role="radiogroup"] label[data-checked="true"] p {
        color: #ffffff !important;
        font-weight: 600 !important;
    }
    div[data-testid="stRadio"] [role="radiogroup"] label p {
        color: #8ea4c8 !important;
    }

    /* FIELD OUTLINES & FOCUS (Inputs, Numbers, Datepickers, Textareas, Selectboxes) - The Two Blues */
    div[data-baseweb="input"],
    div[data-baseweb="base-input"],
    div[data-baseweb="textarea"],
    div[data-baseweb="select"] > div,
    div[data-testid="stTextInput"] div[data-baseweb="base-input"],
    div[data-testid="stNumberInput"] div[data-baseweb="base-input"],
    div[data-testid="stDateInput"] div[data-baseweb="base-input"],
    div[data-testid="stTextArea"] div[data-baseweb="base-input"] {
        background-color: #171f30 !important;
        border: 1px solid #283552 !important;
        color: #f0f4f8 !important;
        border-radius: 8px !important;
    }
    /* Field outline hover */
    div[data-baseweb="input"]:hover,
    div[data-baseweb="base-input"]:hover,
    div[data-baseweb="textarea"]:hover,
    div[data-baseweb="select"] > div:hover,
    div[data-testid="stTextInput"] div[data-baseweb="base-input"]:hover,
    div[data-testid="stNumberInput"] div[data-baseweb="base-input"]:hover,
    div[data-testid="stDateInput"] div[data-baseweb="base-input"]:hover,
    div[data-testid="stTextArea"] div[data-baseweb="base-input"]:hover {
        border-color: #33406a !important;
    }
    /* Field outline focus */
    div[data-baseweb="input"]:focus-within,
    div[data-baseweb="base-input"]:focus-within,
    div[data-baseweb="textarea"]:focus-within,
    div[data-baseweb="select"]:focus-within > div,
    div[data-baseweb="select"]:focus-within,
    div[data-testid="stTextInput"] div[data-baseweb="base-input"]:focus-within,
    div[data-testid="stNumberInput"] div[data-baseweb="base-input"]:focus-within,
    div[data-testid="stDateInput"] div[data-baseweb="base-input"]:focus-within,
    div[data-testid="stTextArea"] div[data-baseweb="base-input"]:focus-within {
        border-color: #5d6895 !important;
        box-shadow: 0 0 0 1px #5d6895 !important;
        outline: none !important;
    }
    input, textarea, select {
        color: #f0f4f8 !important;
        background-color: transparent !important;
    }
    input:focus, textarea:focus, select:focus {
        border-color: #5d6895 !important;
        outline: none !important;
        box-shadow: none !important;
    }

    /* Dropdown popover list items */
    div[data-baseweb="popover"],
    div[data-baseweb="menu"],
    ul[role="listbox"] {
        background-color: #171f30 !important;
        border: 1px solid #283552 !important;
    }
    ul[role="listbox"] li {
        background-color: #171f30 !important;
        color: #f0f4f8 !important;
    }
    ul[role="listbox"] li[aria-selected="true"] {
        background-color: #33406a !important;
        color: #ffffff !important;
    }
    ul[role="listbox"] li:hover {
        background-color: #1d273d !important;
        color: #d9e2ec !important;
    }

    /* Primary & Secondary Buttons in the Two Blues */
    button[kind="primary"],
    button[data-testid="baseButton-primary"] {
        background-color: #33406a !important;
        border: 1px solid #5d6895 !important;
        color: #ffffff !important;
    }
    button[kind="primary"]:hover,
    button[data-testid="baseButton-primary"]:hover {
        background-color: #5d6895 !important;
        border-color: #4a72b8 !important;
        color: #ffffff !important;
    }
    button[kind="secondary"],
    button[data-testid="baseButton-secondary"] {
        background-color: #1d273d !important;
        border: 1px solid #283552 !important;
        color: #f0f4f8 !important;
    }
    button[kind="secondary"]:hover,
    button[data-testid="baseButton-secondary"]:hover {
        border-color: #5d6895 !important;
        color: #5d6895 !important;
    }

    /* Tabs active indicator highlight in Periwinkle Blue */
    div[data-baseweb="tab-highlight"] {
        background-color: #5d6895 !important;
    }
    div[data-baseweb="tab-border"] {
        background-color: #283552 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"],
    button[data-baseweb="tab"][aria-selected="true"] p,
    button[data-baseweb="tab"][aria-selected="true"] div {
        color: #5d6895 !important;
        border-bottom-color: #5d6895 !important;
    }

    /* Checkbox highlight (only for standard checkboxes, not toggle switches) */
    div[data-testid="stCheckbox"]:has(input[type="checkbox"]:not([role="switch"])) label:has(input:checked) div:first-child,
    div[data-baseweb="checkbox"] label:has(input:checked) div:first-child,
    div[data-baseweb="checkbox"] input:checked + div,
    div[data-testid="stCheckbox"]:has(input[type="checkbox"]:not([role="switch"])) input:checked + div {
        background-color: #5d6895 !important;
        border-color: #5d6895 !important;
    }

    /* Toggle switch styling - keep thumb (white dot) always visible */
    div[data-testid="stCheckbox"]:has(input[role="switch"]) label:has(input:checked) div[class*="e15oan337"],
    div[data-testid="stCheckbox"]:has(input[role="switch"]) input:checked + div {
        background-color: #5d6895 !important;
        border-color: #5d6895 !important;
    }
    div[data-testid="stCheckbox"] input[role="switch"] ~ div div,
    div[data-testid="stCheckbox"] input[role="switch"] + div div,
    div[data-testid="stCheckbox"] div[class*="e15oan338"] {
        background-color: #ffffff !important;
        opacity: 1 !important;
        visibility: visible !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.5) !important;
    }

    /* Calendar / Date picker highlight */
    div[data-baseweb="calendar"] button[aria-selected="true"] {
        background-color: #5d6895 !important;
    }
    div[data-baseweb="calendar"] button:hover {
        background-color: #33406a !important;
    }

    /* Dividers */
    hr, div[data-testid="stDivider"] {
        border-color: #283552 !important;
        background-color: #283552 !important;
    }

    /* Data Editor Grid Styling */
    div[data-testid="stDataEditor"] {
        background-color: #171f30 !important;
        border: 1px solid #283552 !important;
        border-radius: 8px !important;
    }

    /* Hide all Streamlit form submit instructions ("Press enter to submit form") */
    [data-testid="InputInstructions"],
    .stForm [data-testid="InputInstructions"],
    div[data-testid="InputInstructions"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
        margin: 0px !important;
        padding: 0px !important;
    }

    /* Disable typing, cursor, and text selection across all dropdown select menus */
    [data-testid="stSelectbox"] input,
    [data-testid="stMultiSelect"] input,
    .react-aria-ComboBox input,
    div[data-baseweb="select"] input {
        caret-color: transparent !important;
        user-select: none !important;
        -webkit-user-select: none !important;
        cursor: pointer !important;
    }
    [data-testid="stSelectbox"],
    [data-testid="stMultiSelect"],
    .react-aria-ComboBox,
    div[data-baseweb="select"] {
        cursor: pointer !important;
    }

    /* EXCEPTION: Allow typing, text cursor, and selection ONLY for the Select Active Member dropdown */
    div[class*="st-key-sel_active_member"] input,
    div[class*="st-key-sel_active_member"] input:focus,
    div[data-testid="stSelectbox"]:has(label:has-text("Select Active Member")) input,
    div[data-testid="stSelectbox"]:has(input[aria-label*="Select Active Member"]) input {
        caret-color: #f0f4f8 !important;
        user-select: text !important;
        -webkit-user-select: text !important;
        cursor: text !important;
    }
    div[class*="st-key-sel_active_member"],
    div[class*="st-key-sel_active_member"] [data-baseweb="select"],
    div[data-testid="stSelectbox"]:has(label:has-text("Select Active Member")),
    div[data-testid="stSelectbox"]:has(input[aria-label*="Select Active Member"]) {
        cursor: default !important;
    }

    /* Hide the 0-height component iframe container */
    iframe[height="0"],
    div[data-testid="stCustomComponentV1"]:has(> iframe[height="0"]) {
        display: none !important;
        position: absolute !important;
        height: 0px !important;
        overflow: hidden !important;
    }
</style>
""", unsafe_allow_html=True)

# Injected client-side script to enforce readonly and intercept typing on all dropdown inputs
components.html("""
<script>
(function() {
    function getParentDoc() {
        try {
            return window.parent ? window.parent.document : document;
        } catch(e) {
            return document;
        }
    }

    const parentDoc = getParentDoc();
    if (!parentDoc) return;

    function isMemberSearchDropdown(el) {
        if (!el) return false;
        if (el.closest && el.closest('[class*="st-key-sel_active_member"]')) return true;
        const sb = el.closest ? el.closest('[data-testid="stSelectbox"]') : null;
        if (sb) {
            const label = sb.querySelector('label');
            if (label && label.textContent && label.textContent.includes('Select Active Member')) return true;
            const input = sb.querySelector('input');
            if (input && input.getAttribute('aria-label') && input.getAttribute('aria-label').includes('Select Active Member')) return true;
        }
        return false;
    }

    function lockDropdowns() {
        try {
            const inputs = parentDoc.querySelectorAll(
                '[data-testid="stSelectbox"] input, [data-testid="stMultiSelect"] input, .react-aria-ComboBox input, div[data-baseweb="select"] input'
            );
            inputs.forEach(inp => {
                if (isMemberSearchDropdown(inp)) {
                    if (inp.readOnly) {
                        inp.readOnly = false;
                        inp.removeAttribute('readonly');
                    }
                    inp.style.caretColor = '#f0f4f8';
                    inp.style.cursor = 'text';
                    inp.style.userSelect = 'text';
                    return;
                }
                if (!inp.readOnly) {
                    inp.readOnly = true;
                    inp.setAttribute('readonly', 'true');
                }
                inp.style.caretColor = 'transparent';
                inp.style.cursor = 'pointer';
                inp.style.userSelect = 'none';
            });
        } catch(e) {}
    }

    lockDropdowns();
    setInterval(lockDropdowns, 150);

    if (!parentDoc.__dropdownLockInitialized) {
        parentDoc.__dropdownLockInitialized = true;

        const observer = new MutationObserver(() => {
            lockDropdowns();
        });
        observer.observe(parentDoc.body, { childList: true, subtree: true });

        parentDoc.addEventListener('keydown', function(e) {
            const active = parentDoc.activeElement;
            if (active && active.tagName === 'INPUT' && (
                active.closest('[data-testid="stSelectbox"]') || 
                active.closest('[data-testid="stMultiSelect"]') || 
                active.closest('.react-aria-ComboBox') ||
                active.closest('div[data-baseweb="select"]')
            )) {
                if (isMemberSearchDropdown(active)) {
                    return; // Allow typing & searching!
                }
                const allowedKeys = ['Tab', 'Escape', 'Enter', 'ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight'];
                if (!allowedKeys.includes(e.key)) {
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }
            }
        }, true);

        parentDoc.addEventListener('beforeinput', function(e) {
            const active = parentDoc.activeElement;
            if (active && active.tagName === 'INPUT' && (
                active.closest('[data-testid="stSelectbox"]') || 
                active.closest('[data-testid="stMultiSelect"]') || 
                active.closest('.react-aria-ComboBox') ||
                active.closest('div[data-baseweb="select"]')
            )) {
                if (isMemberSearchDropdown(active)) {
                    return; // Allow typing & searching!
                }
                e.preventDefault();
                e.stopPropagation();
                return false;
            }
        }, true);
    }
})();
</script>
""", height=0, width=0)


def main():
    ensure_data_initialized()

    # --- SIDEBAR: NEW LOGO, GLOBAL SEASON & NAVIGATION ---
    with st.sidebar:
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.jpg")
        if os.path.exists(logo_path):
            st.image(logo_path, use_container_width=True)

        st.markdown("### UCSB Ski Team")
        st.caption("Operations and Treasury Portal")
        st.divider()

        # Global Season Selector
        season_display_map = {
            CURRENT_SEASON: f"{CURRENT_SEASON} (Current Season)",
            "2025-2026": "2025-2026 (Archived)",
            "All Seasons": "All Seasons (Combined)"
        }
        season_choices = [CURRENT_SEASON, "2025-2026", "All Seasons"]
        selected_season = st.selectbox(
            "Viewing Season",
            season_choices,
            format_func=lambda s: season_display_map.get(s, s),
            index=0,
            help="Select a season to filter financials, transactions, registrations, merch, and trips across the entire dashboard."
        )

        st.divider()

        # Officer Access Control (Password Protection)
        if "is_officer" not in st.session_state:
            st.session_state["is_officer"] = False

        is_officer = st.session_state["is_officer"]

        if not is_officer:
            with st.expander("Officer Login (Unlock Live Data & Editing)", expanded=False):
                st.caption("Enter officer passcode to view live UCSB Ski Team data, log receipts, or create trips:")
                with st.form("officer_login_form", clear_on_submit=False, border=False, enter_to_submit=True):
                    code_input = st.text_input("Officer Passcode", type="password", placeholder="Enter passcode", key="officer_passcode_input")
                    submit_login = st.form_submit_button("Unlock Live Data & Editing", use_container_width=True, type="primary")
                    if submit_login:
                        if code_input.strip() == OFFICER_PASSWORD:
                            st.session_state["is_officer"] = True
                            st.session_state["officer_editing"] = True
                            st.rerun()
                        else:
                            st.error("Incorrect passcode.")
            can_edit = False
        else:
            st.success("Officer Mode Active")
            st.caption("Live team database loaded.")

            if "officer_editing" not in st.session_state:
                st.session_state["officer_editing"] = True

            can_edit = st.toggle(
                "Enable Editing Mode",
                value=st.session_state["officer_editing"],
                key="officer_editing_toggle",
                help="Toggle between Editing Mode (modify records, create trips, log receipts) and Viewing Mode (safe read-only view of live team data)."
            )
            st.session_state["officer_editing"] = can_edit

            if can_edit:
                st.caption("Current State: **Editing Active**")
            else:
                st.caption("Current State: **Viewing Only** (Modifications locked)")

            if st.button("Lock / Switch to View-Only Demo", use_container_width=True, key="btn_lock_officer"):
                st.session_state["is_officer"] = False
                st.session_state["officer_editing"] = False
                st.rerun()

        st.divider()

        # Navigation
        nav_choice = st.radio(
            "Select Dashboard View:",
            [
                "Financial Overview",
                "Ledger and Officer Entry",
                "Membership Tracker",
                "Merch Tracking",
                "Trip Creator",
                "Team Calendar & Events",
                "Trip Cost Estimator",
                "Officer To-Do List",
            ],
            index=0
        )

        st.divider()

        # Season Snapshot
        kpis = get_financial_kpis(season=selected_season, is_officer=is_officer)
        active_members = load_members(season=selected_season, is_officer=is_officer)
        trips_df = load_trips(season=selected_season, is_officer=is_officer)
        events_df = load_events(season=selected_season, is_officer=is_officer)
        active_todos = load_todos(season=selected_season, status="Pending", is_officer=is_officer)

        st.markdown("##### Season Snapshot")
        st.markdown(f"**Season:** {selected_season}")
        st.markdown(f"**Treasury Balance:** \\${kpis['net_balance']:,.2f}")
        st.markdown(f"**Total Members:** {len(active_members)}")
        st.markdown(f"**Trips in Schedule:** {len(trips_df)}")
        st.markdown(f"**Scheduled Events:** {len(events_df)}")
        st.markdown(f"**Open Officer Tasks:** {len(active_todos)}")

        st.divider()
        st.caption("UCSB Ski and Snowboard Club\nOpen Operations")

    # --- TOP HEADER BANNER ---
    if is_officer:
        if can_edit:
            mode_badge = '<span style="background: rgba(56, 161, 105, 0.2); padding: 4px 10px; border-radius: 12px; font-size: 0.85rem; border: 1px solid #38a169; color: #38a169; font-weight: 600;">Officer Mode (Live Team Data - Editing Active)</span>'
        else:
            mode_badge = '<span style="background: rgba(74, 114, 184, 0.2); padding: 4px 10px; border-radius: 12px; font-size: 0.85rem; border: 1px solid #4a72b8; color: #d9e2ec; font-weight: 600;">Officer Mode (Live Team Data - Viewing Only)</span>'
    else:
        mode_badge = '<span style="background: rgba(93, 104, 149, 0.2); padding: 4px 10px; border-radius: 12px; font-size: 0.85rem; border: 1px solid #33406a; color: #8ea4c8;">Demo Mode (Sample Data / View-Only)</span>'

    st.markdown(f"""
    <div class="main-header">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
            <h1>UCSB Ski and Snowboard Team Dashboard</h1>
            <div>{mode_badge}</div>
        </div>
        <p>Treasury Ledger &bull; Athlete Rosters &bull; Merch Tracking &bull; Trip Creator &bull; Team Calendar &bull; Officer Tasks &bull; Season: {selected_season}</p>
    </div>
    """, unsafe_allow_html=True)

    # --- ROUTE TO VIEW MODULE ---
    if nav_choice == "Financial Overview":
        render_financials_tab(selected_season=selected_season, is_officer=is_officer)
    elif nav_choice == "Ledger and Officer Entry":
        render_ledger_tab(selected_season=selected_season, is_officer=is_officer, can_edit=can_edit)
    elif nav_choice == "Membership Tracker":
        render_registration_tab(selected_season=selected_season, is_officer=is_officer, can_edit=can_edit)
    elif nav_choice == "Merch Tracking":
        render_merch_tab(selected_season=selected_season, is_officer=is_officer, can_edit=can_edit)
    elif nav_choice == "Trip Creator":
        render_trip_creator_tab(selected_season=selected_season, is_officer=is_officer, can_edit=can_edit)
    elif nav_choice == "Team Calendar & Events":
        render_calendar_tab(selected_season=selected_season, is_officer=is_officer, can_edit=can_edit)
    elif nav_choice == "Trip Cost Estimator":
        render_trip_estimator_tab(is_officer=is_officer)
    elif nav_choice == "Officer To-Do List":
        render_todo_tab(selected_season=selected_season, is_officer=is_officer, can_edit=can_edit)


if __name__ == "__main__":
    main()
