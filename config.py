"""
Configuration and constants for the UCSB Ski & Snowboard Team Dashboard.
Dark theme with the two blues from the classic team logo as highlight colors.
"""

import os

def _get_secret(key: str, default: str = "") -> str:
    """Safely retrieve configuration secret from Streamlit secrets, then local secrets file, then environment, else default."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and st.secrets is not None:
            if key in st.secrets:
                val = str(st.secrets[key]).strip()
                if val:
                    return val
            if "general" in st.secrets and key in st.secrets["general"]:
                val = str(st.secrets["general"][key]).strip()
                if val:
                    return val
    except Exception:
        pass

    # Fallback for offline scripts or testing outside Streamlit runtime
    try:
        local_secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
        if os.path.exists(local_secrets_path):
            try:
                import tomllib
                with open(local_secrets_path, "rb") as f:
                    data = tomllib.load(f)
            except ImportError:
                import toml
                with open(local_secrets_path, "r", encoding="utf-8") as f:
                    data = toml.load(f)
            if key in data:
                val = str(data[key]).strip()
                if val:
                    return val
    except Exception:
        pass

    env_val = os.environ.get(key, "").strip()
    return env_val if env_val else default

# UCSB Origin
ORIGIN_LOCATION = "UCSB (Isla Vista, CA)"

# Seasons
CURRENT_SEASON = "2026-2027"
AVAILABLE_SEASONS = ["2026-2027", "2025-2026"]

# Official Google Form / Sheets integration defaults (retrieved securely from secrets)
DEFAULT_MEMBERSHIP_FORM_SHEET_URL = _get_secret("MEMBERSHIP_FORM_SHEET_URL", "")
DEFAULT_LEDGER_SHEET_URL = _get_secret("LEDGER_SHEET_URL", "")
LEDGER_WEBHOOK_URL = _get_secret("LEDGER_WEBHOOK_URL", "")

# Default Trip Sign-Up Driver Options
DEFAULT_TRIP_DRIVER_OPTIONS = [
    "Cannot drive",
    "Can drive (1 passenger + gear)",
    "Can drive (2 passengers + gear)",
    "Can drive (3 passengers + gear)",
    "Can drive (4+ passengers + gear)",
]

# Primary Discipline Options
SKIBOARD_OPTIONS = ["", "Ski", "Board", "Both"]

# Security & Access Control (retrieved securely from secrets)
OFFICER_PASSWORD = _get_secret("OFFICER_PASSWORD", "demo_officer_pass")

# Ski Team Officers
OFFICERS = [
    "Olivia", "Kendall", "Kate", "Forrest", "Wiley", "Ty",
    "Justin", "Owin", "Anna", "Noelle", "Morgan", "Paige", "Emmett"
]

# Demo Mode Generic Officer Roles (for external showcase)
DEMO_OFFICERS = [
    "President", "Treasurer", "Trip Director", "Social Chair", "Gear Manager", "Safety Officer"
]

# Merch Inventory Configuration
SHIRT_SIZES = ["None", "S", "M", "L", "XL"]
VALID_SIZES = ["S", "M", "L", "XL"]

INITIAL_SHIRT_INVENTORY = {
    "S": 40,
    "M": 100,
    "L": 70,
    "XL": 40,
}

INITIAL_SWEATSHIRT_INVENTORY = {
    "S": 10,
    "M": 28,
    "L": 14,
    "XL": 8,
}

# Destination presets from UCSB
DESTINATIONS = {
    "Mammoth": {
        "one_way_miles": 360,
        "round_trip_miles": 720,
        "default_nights": 3,
        "description": "Mammy",
    },
    "Bear Valley": {
        "one_way_miles": 380,
        "round_trip_miles": 760,
        "default_nights": 3,
        "description": "aka Beer Valley",
    },
    "China Peak": {
        "one_way_miles": 275,
        "round_trip_miles": 550,
        "default_nights": 2,
        "description": "Chin on my Pea",
    },
    "Big Bear": {
        "one_way_miles": 185,
        "round_trip_miles": 370,
        "default_nights": 2,
        "description": "Jacob's Holy Land",
    },
    "Palisades": {
        "one_way_miles": 450,
        "round_trip_miles": 900,
        "default_nights": 4,
        "description": "It's still Squaw",
    },
}

# Trip Types & Statuses
TRIP_TYPES = ["Recreational", "Competition"]
TRIP_STATUS_OPTIONS = ["Planning", "Confirmed", "Completed", "Cancelled"]

# Event Types & Statuses (Meetings, Socials, Dryland, etc.)
EVENT_TYPES = [
    "Club Meeting",
    "Staff Meeting",
    "Social",
    "Fundraiser",
    "Competition / Race",
    "Tabling / Outreach",
    "Training",
    "Other"
]
EVENT_STATUS_OPTIONS = ["Planning", "Confirmed", "Completed", "Cancelled"]

# Vehicle & Travel calculation defaults
DEFAULT_MPG = 20.0             # Typical SUV / truck carrying skis and luggage
DEFAULT_GAS_PRICE = 4.85       # CA average estimated gas price ($/gallon)
DEFAULT_SEATS_PER_CAR = 4      # Skiers per vehicle with luggage
COMPETITION_GAS_RATE_PER_MILE = 0.70  # 70 cents/mile rate for competition trips

# Default baseline financial values
ANNUAL_DUES_AMOUNT = 60.00     # Typical yearly dues per member

# Ledger categories
INCOME_CATEGORIES = [
    "Membership Dues",
    "AS Funding",
    "Trip Payment",
    "Membership",
    "Fundraising",
    "Merch",
    "Ikon",
    "Sponsorship",
    "Other Income",
]

EXPENSE_CATEGORIES = [
    "Housing/Rental",
    "Food/Drink (Trip)",
    "USCSA",
    "Trip Payment",
    "Membership Dues",
    "Trip Refund",
    "Membership Refund",
    "Socials",
    "Merch",
    "Ikon",
    "Transportation/Gas",
    "Lift Tickets",
    "Staff",
    "Other",
]

ALL_CATEGORIES = sorted(list(set(INCOME_CATEGORIES + EXPENSE_CATEGORIES)))

# Dark theme palette with the two classic blues as highlights
THEME_COLORS = {
    "dark_bg": "#0e131f",          # Deep midnight dark background
    "surface_bg": "#171f30",       # Dark card and container background
    "surface_card": "#1d273d",     # Elevated card surface
    "slate_blue": "#33406a",       # Primary Blue 1 (Deep Slate Blue)
    "periwinkle": "#5d6895",       # Primary Blue 2 (Periwinkle Blue)
    "bright_blue": "#4a72b8",      # Bright interactive accent blue
    "ice_blue": "#d9e2ec",         # Soft light text/contrast
    "text_primary": "#f0f4f8",     # Main heading & text color
    "text_muted": "#8ea4c8",       # Subtitle & caption color
    "border_color": "#283552",     # Dark border
    "success_green": "#38a169",    # Positive cash flow
    "alert_red": "#e53e3e",        # Outflows & deficit
}
