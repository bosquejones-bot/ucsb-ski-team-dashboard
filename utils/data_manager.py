"""
Data management module for the UCSB Ski Team Dashboard.
Handles multi-season persistence for ledger, members, Google Forms sync,
trip creator/estimator records, trip signups with driver tracking & payment checkboxes,
officer to-do tasks, and merch inventory.
"""

import os
import re
import shutil
import urllib.parse
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta, timezone
import config
from config import (
    CURRENT_SEASON, INITIAL_SHIRT_INVENTORY, INITIAL_SWEATSHIRT_INVENTORY,
    VALID_SIZES, OFFICERS, DEMO_OFFICERS, INCOME_CATEGORIES
)

DEFAULT_LEDGER_SHEET_URL = getattr(config, "DEFAULT_LEDGER_SHEET_URL", "")
LEDGER_WEBHOOK_URL = getattr(config, "LEDGER_WEBHOOK_URL", "")
TRIPS_EVENTS_SHEET_URL = getattr(config, "TRIPS_EVENTS_SHEET_URL", "")
MEMBERS_SHEET_URL = getattr(config, "MEMBERS_SHEET_URL", "")
LEDGER_SHEET_URL = getattr(config, "LEDGER_SHEET_URL", "") or DEFAULT_LEDGER_SHEET_URL

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DEMO_DATA_DIR = os.path.join(DATA_DIR, "demo")

LEDGER_FILE = os.path.join(DATA_DIR, "ledger.csv")
MEMBERS_FILE = os.path.join(DATA_DIR, "members.csv")
TRIPS_FILE = os.path.join(DATA_DIR, "trips.csv")
TRIP_SIGNUPS_FILE = os.path.join(DATA_DIR, "trip_signups.csv")
TODOS_FILE = os.path.join(DATA_DIR, "todos.csv")
MERCH_FILE = os.path.join(DATA_DIR, "merch_adjustments.csv")
EVENTS_FILE = os.path.join(DATA_DIR, "events.csv")
OFFICERS_FILE = os.path.join(DATA_DIR, "officers.csv")

DEMO_LEDGER_FILE = os.path.join(DEMO_DATA_DIR, "ledger.csv")
DEMO_MEMBERS_FILE = os.path.join(DEMO_DATA_DIR, "members.csv")
DEMO_TRIPS_FILE = os.path.join(DEMO_DATA_DIR, "trips.csv")
DEMO_TRIP_SIGNUPS_FILE = os.path.join(DEMO_DATA_DIR, "trip_signups.csv")
DEMO_TODOS_FILE = os.path.join(DEMO_DATA_DIR, "todos.csv")
DEMO_MERCH_FILE = os.path.join(DEMO_DATA_DIR, "merch_adjustments.csv")
DEMO_EVENTS_FILE = os.path.join(DEMO_DATA_DIR, "events.csv")
DEMO_OFFICERS_FILE = os.path.join(DEMO_DATA_DIR, "officers.csv")

DOWNLOADS_SOURCE = r"C:\Users\bosqu\Downloads\ski_team_financial_data.csv"


def get_officers_file(is_officer: bool = False) -> str:
    return OFFICERS_FILE if is_officer else DEMO_OFFICERS_FILE


def get_ledger_file(is_officer: bool = False) -> str:
    return LEDGER_FILE if is_officer else DEMO_LEDGER_FILE


def get_members_file(is_officer: bool = False) -> str:
    return MEMBERS_FILE if is_officer else DEMO_MEMBERS_FILE


def get_trips_file(is_officer: bool = False) -> str:
    return TRIPS_FILE if is_officer else DEMO_TRIPS_FILE


def get_trip_signups_file(is_officer: bool = False) -> str:
    return TRIP_SIGNUPS_FILE if is_officer else DEMO_TRIP_SIGNUPS_FILE


def get_todos_file(is_officer: bool = False) -> str:
    return TODOS_FILE if is_officer else DEMO_TODOS_FILE


def get_merch_file(is_officer: bool = False) -> str:
    return MERCH_FILE if is_officer else DEMO_MERCH_FILE


def get_events_file(is_officer: bool = False) -> str:
    return EVENTS_FILE if is_officer else DEMO_EVENTS_FILE


TRIP_COLS = [
    "TripID", "Season", "Name", "Destination", "TripType", "StartDate", "EndDate",
    "Nights", "RoundTripMiles", "Attendees", "Vehicles", "CabinCost",
    "FoodAlcoholCost", "LiftTicketsCost", "GasCost", "TotalCost",
    "RevenueCollected", "Status", "AttendeeRoster", "Notes",
    "SchoolFunding", "NetCost", "SchoolCoverageDetails"
]

TODO_COLS = [
    "TaskID", "Season", "Title", "Description", "AssignedTo",
    "SubmittedDate", "TargetDate", "Status", "CompletedDate", "Notes"
]

SIGNUP_COLS = [
    "SignupID", "TripID", "TripName", "Season", "Name", "Phone",
    "DrivingCapacity", "Questions", "PaymentReceived", "SignupDate"
]

DEMO_MEMBER_NAMES = {
    "jordan taylor", "alex morgan", "casey chen", "morgan reed", "riley davis",
    "taylor brooks", "sam patel", "jamie kim", "chris martinez", "cameron lee",
    "dakota johnson", "avery wright", "skyler white", "peyton clark", "quinn anderson",
    "reese wilson", "finley thomas", "hayden jackson", "logan harris", "kendall martin",
    "parker thompson", "jesse garcia", "rowan robinson", "drew clark", "spencer lewis"
}


def purge_demo_members_from_df(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out any demo member records from a DataFrame."""
    if df is None or df.empty:
        return df
    clean = df.copy()
    mask = pd.Series(True, index=clean.index)
    if "MemberID" in clean.columns:
        mask = mask & (~clean["MemberID"].astype(str).str.strip().str.startswith("MEM-"))
    if "Email" in clean.columns:
        mask = mask & (~clean["Email"].astype(str).str.lower().str.strip().str.endswith("@university.edu"))
    if "Phone" in clean.columns:
        mask = mask & (~clean["Phone"].astype(str).str.strip().str.startswith("555-01"))
    if "Name" in clean.columns:
        mask = mask & (~clean["Name"].astype(str).str.lower().str.strip().isin(DEMO_MEMBER_NAMES))
    return clean[mask].copy().reset_index(drop=True)


def format_phone_number(phone_str: str) -> str:
    """
    Standardize a phone number string to XXX-XXX-XXXX format.
    Handles raw 10-digit strings, strings with dashes/dots/spaces/parentheses,
    and 11-digit numbers with leading US country code '1'.
    Returns the original string cleaned if it cannot be parsed to 10 digits.
    """
    if phone_str is None or pd.isna(phone_str):
        return ""
    raw = str(phone_str).strip()
    if not raw or raw.lower() in ["nan", "none", "null"]:
        return ""
    
    # Remove all non-digits
    digits = re.sub(r"\D", "", raw)
    # If 11 digits and starts with 1, drop leading US country code
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    
    return raw


def generate_next_member_id(all_df: pd.DataFrame, season: str = CURRENT_SEASON) -> str:
    """
    Generate the next sequential MemberID for a given season.
    For season 2026-2027, generates MBR-26-001, MBR-26-002, etc.
    Finds the maximum sequence number present for the season's prefix and increments by 1.
    """
    season_short = season.replace("20", "")[:2] if season else "26"
    prefix = f"MBR-{season_short}-"
    if all_df is None or all_df.empty or "MemberID" not in all_df.columns:
        return f"{prefix}001"
    
    existing_ids = all_df["MemberID"].dropna().astype(str).tolist()
    nums = []
    for mid in existing_ids:
        mid_s = mid.strip()
        if mid_s.startswith(prefix):
            suffix = mid_s[len(prefix):]
            if suffix.isdigit():
                nums.append(int(suffix))
    
    next_num = max(nums) + 1 if nums else 1
    return f"{prefix}{next_num:03d}"


# --- GOOGLE SHEETS CLOUD CONNECTION (OPTION 1A) ---

def get_gsheets_connection():
    """Safely retrieve GSheetsConnection instance if configured in Streamlit secrets."""
    try:
        import streamlit as st
        from streamlit_gsheets import GSheetsConnection
        conn = st.connection("gsheets", type=GSheetsConnection)
        return conn
    except Exception:
        return None


def read_gsheet_worksheet(spreadsheet_url: str, worksheet, ttl: int = 60) -> pd.DataFrame:
    """Read a specific worksheet from Google Sheets into a DataFrame, with caching and fallback."""
    if not spreadsheet_url:
        return None
    conn = get_gsheets_connection()
    if conn is None:
        return None
    try:
        df = conn.read(spreadsheet=spreadsheet_url, worksheet=worksheet, ttl=ttl)
        if df is not None and not df.empty:
            df = df.dropna(how="all").reset_index(drop=True)
            # Drop any trailing columns generated by spreadsheet formatting (e.g. Unnamed: 23)
            df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed")].copy()
            return df
        return df
    except Exception as e:
        print(f"GSheets read failed for worksheet '{worksheet}' on {spreadsheet_url}: {e}")
        return None


def write_gsheet_worksheet(spreadsheet_url: str, worksheet, df: pd.DataFrame) -> bool:
    """Write DataFrame back to a specific worksheet in Google Sheets, invalidating read cache."""
    if not spreadsheet_url or df is None:
        return False
    conn = get_gsheets_connection()
    if conn is None:
        return False
    try:
        clean_df = df.copy()
        for col in clean_df.columns:
            if clean_df[col].dtype == object:
                clean_df[col] = clean_df[col].fillna("").astype(str)
            elif pd.api.types.is_numeric_dtype(clean_df[col]):
                clean_df[col] = clean_df[col].fillna(0.0)

        ws_title = str(worksheet)
        written = False
        try:
            conn.update(spreadsheet=spreadsheet_url, worksheet=worksheet, data=clean_df)
            written = True
        except Exception:
            try:
                conn.create(spreadsheet=spreadsheet_url, worksheet=ws_title, data=clean_df)
                written = True
            except Exception:
                pass

        if not written:
            # Fallback to direct gspread client access
            raw_client = getattr(conn, "_raw_instance", None)
            if raw_client and hasattr(raw_client, "_client"):
                gc = raw_client._client
                ss = gc.open_by_url(spreadsheet_url)
                try:
                    ws = ss.worksheet(ws_title)
                except Exception:
                    ws = ss.add_worksheet(title=ws_title, rows=max(100, len(clean_df) + 10), cols=max(26, len(clean_df.columns) + 5))
                ws.clear()
                header = list(clean_df.columns)
                rows = clean_df.values.tolist()
                ws.update([header] + rows)
                written = True

        # Clear Streamlit read cache so updates reflect immediately
        try:
            import streamlit as st
            st.cache_data.clear()
        except Exception:
            pass
        return written
    except Exception as e:
        print(f"GSheets write failed for worksheet '{worksheet}' on {spreadsheet_url}: {e}")
        return False


def ensure_demo_data_initialized():
    """Ensure demo data directory and realistic sample CSV files exist."""
    os.makedirs(DEMO_DATA_DIR, exist_ok=True)

    if not os.path.exists(DEMO_TRIPS_FILE):
        trips_data = [
            # 2025-2026
            {
                "TripID": "TRIP-001", "Name": "Mammoth Winter Opener 2025", "Destination": "Mammoth Mountain",
                "StartDate": "2025-11-14", "EndDate": "2025-11-17", "Nights": 3, "RoundTripMiles": 720.0,
                "Attendees": 24, "Vehicles": 6, "CabinCost": 2200.0, "FoodAlcoholCost": 350.0,
                "LiftTicketsCost": 0.0, "GasCost": 1050.0, "TotalCost": 3600.0, "RevenueCollected": 3840.0,
                "Status": "Completed", "Notes": "Early season kickoff weekend at Mammoth Mountain.",
                "Season": "2025-2026", "TripType": "Recreational", "AttendeeRoster": ""
            },
            {
                "TripID": "TRIP-002", "Name": "Lake Tahoe MLK Shredder 2026", "Destination": "Palisades Tahoe",
                "StartDate": "2026-01-16", "EndDate": "2026-01-19", "Nights": 3, "RoundTripMiles": 880.0,
                "Attendees": 32, "Vehicles": 8, "CabinCost": 3800.0, "FoodAlcoholCost": 500.0,
                "LiftTicketsCost": 350.0, "GasCost": 1400.0, "TotalCost": 6050.0, "RevenueCollected": 6720.0,
                "Status": "Completed", "Notes": "Peak winter MLK trip, two large cabins booked.",
                "Season": "2025-2026", "TripType": "Recreational", "AttendeeRoster": ""
            },
            {
                "TripID": "TRIP-003", "Name": "Big Bear Weekend 2026", "Destination": "Big Bear Mountain Resort",
                "StartDate": "2026-01-23", "EndDate": "2026-01-25", "Nights": 2, "RoundTripMiles": 370.0,
                "Attendees": 18, "Vehicles": 4, "CabinCost": 1800.0, "FoodAlcoholCost": 260.0,
                "LiftTicketsCost": 120.0, "GasCost": 360.0, "TotalCost": 2540.0, "RevenueCollected": 2520.0,
                "Status": "Completed", "Notes": "SoCal local weekend trip.",
                "Season": "2025-2026", "TripType": "Recreational", "AttendeeRoster": ""
            },
            {
                "TripID": "TRIP-004", "Name": "China Peak USCSA Qualifier", "Destination": "China Peak",
                "StartDate": "2026-01-30", "EndDate": "2026-02-01", "Nights": 2, "RoundTripMiles": 550.0,
                "Attendees": 14, "Vehicles": 3, "CabinCost": 1450.0, "FoodAlcoholCost": 450.0,
                "LiftTicketsCost": 400.0, "GasCost": 400.0, "TotalCost": 2700.0, "RevenueCollected": 2520.0,
                "Status": "Completed", "Notes": "USCSA Southwest conference qualifier.",
                "Season": "2025-2026", "TripType": "Competition", "AttendeeRoster": ""
            },
            {
                "TripID": "TRIP-010", "Name": "Mammoth Spring Fling 2026", "Destination": "Mammoth Mountain",
                "StartDate": "2026-03-06", "EndDate": "2026-03-09", "Nights": 3, "RoundTripMiles": 720.0,
                "Attendees": 24, "Vehicles": 6, "CabinCost": 2100.0, "FoodAlcoholCost": 380.0,
                "LiftTicketsCost": 0.0, "GasCost": 980.0, "TotalCost": 3460.0, "RevenueCollected": 3840.0,
                "Status": "Completed", "Notes": "Spring break sunshine shred at Mammoth.",
                "Season": "2025-2026", "TripType": "Recreational", "AttendeeRoster": ""
            },

            # 2026-2027
            {
                "TripID": "TRIP-005", "Name": "Mammoth Season Opener 2026", "Destination": "Mammoth Mountain",
                "StartDate": "2026-11-20", "EndDate": "2026-11-23", "Nights": 3, "RoundTripMiles": 720.0,
                "Attendees": 24, "Vehicles": 6, "CabinCost": 2400.0, "FoodAlcoholCost": 420.0,
                "LiftTicketsCost": 0.0, "GasCost": 840.0, "TotalCost": 3660.0, "RevenueCollected": 3840.0,
                "Status": "Completed", "Notes": "Annual kickoff trip to Mammoth Mountain.",
                "Season": "2026-2027", "TripType": "Recreational",
                "AttendeeRoster": "Jordan Taylor, Alex Morgan, Casey Chen, Morgan Reed, Riley Davis, Taylor Brooks, Sam Patel, Jamie Kim"
            },
            {
                "TripID": "TRIP-006", "Name": "Palisades Tahoe MLK Trip 2027", "Destination": "Palisades Tahoe",
                "StartDate": "2027-01-15", "EndDate": "2027-01-18", "Nights": 3, "RoundTripMiles": 880.0,
                "Attendees": 32, "Vehicles": 8, "CabinCost": 3800.0, "FoodAlcoholCost": 620.0,
                "LiftTicketsCost": 420.0, "GasCost": 1350.0, "TotalCost": 6190.0, "RevenueCollected": 6720.0,
                "Status": "Completed", "Notes": "Peak winter MLK trip, two large cabins booked in Tahoe Donner.",
                "Season": "2026-2027", "TripType": "Recreational",
                "AttendeeRoster": "Jordan Taylor, Alex Morgan, Casey Chen, Morgan Reed, Chris Martinez, Cameron Lee, Dakota Johnson, Avery Wright, Skyler White, Peyton Clark, Quinn Anderson, Reese Wilson"
            },
            {
                "TripID": "TRIP-007", "Name": "China Peak USCSA Qualifier 2027", "Destination": "China Peak",
                "StartDate": "2027-01-29", "EndDate": "2027-01-31", "Nights": 2, "RoundTripMiles": 550.0,
                "Attendees": 14, "Vehicles": 3, "CabinCost": 1450.0, "FoodAlcoholCost": 380.0,
                "LiftTicketsCost": 0.0, "GasCost": 420.0, "TotalCost": 2250.0, "RevenueCollected": 2520.0,
                "Status": "Completed", "Notes": "USCSA Southwest conference qualifier races.",
                "Season": "2026-2027", "TripType": "Competition",
                "AttendeeRoster": "Jordan Taylor, Taylor Brooks, Chris Martinez, Skyler White, Hayden Jackson, Rowan Robinson"
            },
            {
                "TripID": "TRIP-008", "Name": "Big Bear Weekend 2027", "Destination": "Big Bear Mountain Resort",
                "StartDate": "2027-02-12", "EndDate": "2027-02-14", "Nights": 2, "RoundTripMiles": 370.0,
                "Attendees": 18, "Vehicles": 4, "CabinCost": 1650.0, "FoodAlcoholCost": 310.0,
                "LiftTicketsCost": 240.0, "GasCost": 380.0, "TotalCost": 2580.0, "RevenueCollected": 2880.0,
                "Status": "Completed", "Notes": "SoCal weekend progression trip.",
                "Season": "2026-2027", "TripType": "Recreational",
                "AttendeeRoster": "Alex Morgan, Casey Chen, Dakota Johnson, Quinn Anderson, Jesse Garcia, Kendall Martin"
            },
            {
                "TripID": "TRIP-009", "Name": "Mammoth Spring Fling 2027", "Destination": "Mammoth Mountain",
                "StartDate": "2027-03-19", "EndDate": "2027-03-22", "Nights": 3, "RoundTripMiles": 720.0,
                "Attendees": 24, "Vehicles": 6, "CabinCost": 2400.0, "FoodAlcoholCost": 540.0,
                "LiftTicketsCost": 0.0, "GasCost": 920.0, "TotalCost": 3860.0, "RevenueCollected": 4320.0,
                "Status": "Completed", "Notes": "Spring break sunshine shred weekend.",
                "Season": "2026-2027", "TripType": "Recreational",
                "AttendeeRoster": "Jordan Taylor, Alex Morgan, Morgan Reed, Riley Davis, Cameron Lee, Finley Thomas, Hayden Jackson"
            }
        ]
        pd.DataFrame(trips_data).to_csv(DEMO_TRIPS_FILE, index=False)

    if not os.path.exists(DEMO_TRIP_SIGNUPS_FILE):
        signups_data = [
            {
                "SignupID": "SIGNUP-001", "TripID": "TRIP-005", "TripName": "Mammoth Season Opener 2026",
                "Season": "2026-2027", "Name": "Jordan Taylor", "Phone": "555-0101",
                "DrivingCapacity": "Can drive (3 passengers + gear)",
                "Questions": "Leaving Friday 2pm from campus, roof rack fits 4 snowboards",
                "PaymentReceived": True, "SignupDate": "2026-09-10"
            },
            {
                "SignupID": "SIGNUP-002", "TripID": "TRIP-005", "TripName": "Mammoth Season Opener 2026",
                "Season": "2026-2027", "Name": "Alex Morgan", "Phone": "555-0102",
                "DrivingCapacity": "Can drive (4+ passengers + gear)",
                "Questions": "Subaru Outback with Thule box",
                "PaymentReceived": True, "SignupDate": "2026-09-10"
            },
            {
                "SignupID": "SIGNUP-003", "TripID": "TRIP-005", "TripName": "Mammoth Season Opener 2026",
                "Season": "2026-2027", "Name": "Casey Chen", "Phone": "555-0103",
                "DrivingCapacity": "Can drive (2 passengers + gear)",
                "Questions": "Truck with bed cover",
                "PaymentReceived": False, "SignupDate": "2026-09-11"
            },
            {
                "SignupID": "SIGNUP-004", "TripID": "TRIP-005", "TripName": "Mammoth Season Opener 2026",
                "Season": "2026-2027", "Name": "Morgan Reed", "Phone": "555-0104",
                "DrivingCapacity": "Cannot drive",
                "Questions": "Vegetarian meal request",
                "PaymentReceived": True, "SignupDate": "2026-09-11"
            },
            {
                "SignupID": "SIGNUP-005", "TripID": "TRIP-005", "TripName": "Mammoth Season Opener 2026",
                "Season": "2026-2027", "Name": "Riley Davis", "Phone": "555-0105",
                "DrivingCapacity": "Cannot drive",
                "Questions": "Need to rent demo skis",
                "PaymentReceived": False, "SignupDate": "2026-09-12"
            },
            {
                "SignupID": "SIGNUP-006", "TripID": "TRIP-005", "TripName": "Mammoth Season Opener 2026",
                "Season": "2026-2027", "Name": "Taylor Brooks", "Phone": "555-0106",
                "DrivingCapacity": "Cannot drive",
                "Questions": "",
                "PaymentReceived": True, "SignupDate": "2026-09-12"
            },
            {
                "SignupID": "SIGNUP-007", "TripID": "TRIP-005", "TripName": "Mammoth Season Opener 2026",
                "Season": "2026-2027", "Name": "Sam Patel", "Phone": "555-0107",
                "DrivingCapacity": "Can drive (1 passenger + gear)",
                "Questions": "Leaving Friday 4pm",
                "PaymentReceived": False, "SignupDate": "2026-09-13"
            },
            {
                "SignupID": "SIGNUP-008", "TripID": "TRIP-005", "TripName": "Mammoth Season Opener 2026",
                "Season": "2026-2027", "Name": "Jamie Kim", "Phone": "555-0108",
                "DrivingCapacity": "Cannot drive",
                "Questions": "First time on a team trip!",
                "PaymentReceived": False, "SignupDate": "2026-09-13"
            }
        ]
        pd.DataFrame(signups_data).to_csv(DEMO_TRIP_SIGNUPS_FILE, index=False)

    if not os.path.exists(DEMO_MEMBERS_FILE):
        demo_members_2627 = [
            ("Jordan Taylor", "jordan.taylor@university.edu", "555-0101", "3", "Ski", True, True, "L", True, "Mammoth Season Opener 2026", "Freestyle captain"),
            ("Alex Morgan", "alex.m@university.edu", "555-0102", "4", "Board", True, True, "M", False, "Mammoth Season Opener 2026", "Has 4Runner with roof box"),
            ("Casey Chen", "casey.chen@university.edu", "555-0103", "2", "Both", False, True, "M", False, "Mammoth Season Opener 2026", "Tacoma with bed cover"),
            ("Morgan Reed", "morgan.r@university.edu", "555-0104", "1", "Ski", True, False, "S", False, "Mammoth Season Opener 2026", "Vegetarian meal request"),
            ("Riley Davis", "riley.d@university.edu", "555-0105", "3", "Board", False, False, "L", False, "Mammoth Season Opener 2026", "Needs demo ski rentals"),
            ("Taylor Brooks", "taylor.b@university.edu", "555-0106", "2", "Ski", True, True, "M", True, "Mammoth Season Opener 2026", "Slalom racer"),
            ("Sam Patel", "sam.patel@university.edu", "555-0107", "4", "Board", False, True, "XL", False, "Mammoth Season Opener 2026", "Honda Civic driver"),
            ("Jamie Kim", "jamie.k@university.edu", "555-0108", "1", "Ski", False, False, "S", False, "Mammoth Season Opener 2026", "First time on club trip"),
            ("Chris Martinez", "chris.m@university.edu", "555-0109", "Grad", "Both", True, True, "XL", True, "", "Grad student advisor"),
            ("Cameron Lee", "cameron.l@university.edu", "555-0110", "2", "Ski", True, True, "M", False, "", ""),
            ("Dakota Johnson", "dakota.j@university.edu", "555-0111", "3", "Board", True, False, "L", False, "", ""),
            ("Avery Wright", "avery.w@university.edu", "555-0112", "1", "Ski", False, False, "S", False, "", ""),
            ("Skyler White", "skyler.w@university.edu", "555-0113", "4", "Both", True, True, "M", True, "", "Giant slalom specialist"),
            ("Peyton Clark", "peyton.c@university.edu", "555-0114", "2", "Board", True, True, "M", False, "", ""),
            ("Quinn Anderson", "quinn.a@university.edu", "555-0115", "3", "Ski", True, True, "L", False, "", ""),
            ("Reese Wilson", "reese.w@university.edu", "555-0116", "1", "Board", False, True, "S", False, "", ""),
            ("Finley Thomas", "finley.t@university.edu", "555-0117", "Grad", "Ski", True, True, "XL", False, "", ""),
            ("Hayden Jackson", "hayden.j@university.edu", "555-0118", "4", "Both", True, True, "L", True, "", "Freeride competitor"),
            ("Logan Harris", "logan.h@university.edu", "555-0119", "2", "Ski", True, False, "M", False, "", ""),
            ("Kendall Martin", "kendall.m@university.edu", "555-0120", "3", "Board", True, True, "M", False, "", ""),
            ("Parker Thompson", "parker.t@university.edu", "555-0121", "1", "Ski", False, False, "S", False, "", ""),
            ("Jesse Garcia", "jesse.g@university.edu", "555-0122", "4", "Board", True, True, "XL", False, "", ""),
            ("Rowan Robinson", "rowan.r@university.edu", "555-0123", "2", "Both", True, True, "M", True, "", "Racer"),
            ("Drew Clark", "drew.c@university.edu", "555-0124", "3", "Ski", False, True, "L", False, "", ""),
            ("Spencer Lewis", "spencer.l@university.edu", "555-0125", "1", "Board", True, True, "M", False, "", "")
        ]

        demo_members_2526 = [
            ("Jordan Taylor", "jordan.taylor@university.edu", "555-0101", "2", "Ski", True, True, "L", True, "Mammoth Winter Opener 2025, Lake Tahoe MLK Shredder 2026", "Freestyle captain"),
            ("Alex Morgan", "alex.m@university.edu", "555-0102", "3", "Board", True, True, "M", False, "Mammoth Winter Opener 2025, Big Bear Weekend 2026", ""),
            ("Chris Martinez", "chris.m@university.edu", "555-0109", "4", "Both", True, True, "XL", True, "Lake Tahoe MLK Shredder 2026, China Peak USCSA Qualifier", ""),
            ("Skyler White", "skyler.w@university.edu", "555-0113", "3", "Both", True, True, "M", True, "China Peak USCSA Qualifier", ""),
            ("Hayden Jackson", "hayden.j@university.edu", "555-0118", "3", "Both", True, True, "L", True, "Lake Tahoe MLK Shredder 2026, China Peak USCSA Qualifier", ""),
            ("Rowan Robinson", "rowan.r@university.edu", "555-0123", "1", "Both", True, True, "M", True, "China Peak USCSA Qualifier", ""),
            ("Dakota Johnson", "dakota.j@university.edu", "555-0111", "2", "Board", True, True, "L", False, "Big Bear Weekend 2026", ""),
            ("Quinn Anderson", "quinn.a@university.edu", "555-0115", "2", "Ski", True, True, "L", False, "Mammoth Winter Opener 2025", ""),
            ("Jesse Garcia", "jesse.g@university.edu", "555-0122", "3", "Board", True, True, "XL", False, "Mammoth Winter Opener 2025, Lake Tahoe MLK Shredder 2026", ""),
            ("Kendall Martin", "kendall.m@university.edu", "555-0120", "2", "Board", True, True, "M", False, "Lake Tahoe MLK Shredder 2026", ""),
            ("Finley Thomas", "finley.t@university.edu", "555-0117", "4", "Ski", True, True, "XL", False, "Big Bear Weekend 2026", ""),
            ("Logan Harris", "logan.h@university.edu", "555-0119", "1", "Ski", True, True, "M", False, "Mammoth Winter Opener 2025", ""),
            ("Taylor Brooks", "taylor.b@university.edu", "555-0106", "1", "Ski", True, True, "M", True, "China Peak USCSA Qualifier", ""),
            ("Sam Patel", "sam.patel@university.edu", "555-0107", "3", "Board", True, True, "XL", False, "Lake Tahoe MLK Shredder 2026", "")
        ]

        all_members_rows = []
        for i, m in enumerate(demo_members_2627, 1):
            all_members_rows.append({
                "MemberID": f"MEM-27-{i:03d}", "Season": "2026-2027", "Name": m[0],
                "Email": m[1], "Phone": m[2], "Year": m[3], "SkiBoard": m[4],
                "DuesPaid": m[5], "Slack": m[6], "TShirtSize": m[7], "CompTeam": m[8],
                "TripsAttended": m[9], "Notes": m[10]
            })
        for i, m in enumerate(demo_members_2526, 1):
            all_members_rows.append({
                "MemberID": f"MEM-26-{i:03d}", "Season": "2025-2026", "Name": m[0],
                "Email": m[1], "Phone": m[2], "Year": m[3], "SkiBoard": m[4],
                "DuesPaid": m[5], "Slack": m[6], "TShirtSize": m[7], "CompTeam": m[8],
                "TripsAttended": m[9], "Notes": m[10]
            })
        pd.DataFrame(all_members_rows).to_csv(DEMO_MEMBERS_FILE, index=False)

    if not os.path.exists(DEMO_LEDGER_FILE):
        ledger_rows = [
            # =========================================================================
            # SEASON 2026-2027 (CURRENT SEASON - 9 CONTINUOUS MONTHS)
            # =========================================================================
            {"Date": "09-01-2026", "Entity": "UCSB Ski Team Treasury", "Amount": 3850.0, "Category": "Other Income", "Notes": "Carryover Operating Funds from 2025-2026 Season", "Type": "Income", "Season": "2026-2027"},
            {"Date": "09-05-2026", "Entity": "Fall 2026 Dues Wave 1", "Amount": 1800.0, "Category": "Membership Dues", "Notes": "30 active member registrations ($60/ea)", "Type": "Income", "Season": "2026-2027"},
            {"Date": "09-08-2026", "Entity": "Costco & Albertsons", "Amount": 240.0, "Category": "Socials", "Notes": "Welcome Back BBQ burgers, buns, drinks & charcoal", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "09-12-2026", "Entity": "Alpine Screenprinting", "Amount": 1450.0, "Category": "Merch", "Notes": "Season 26-27 team t-shirts restock order (180 units)", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "09-18-2026", "Entity": "Campus Merch Pop-Up", "Amount": 520.0, "Category": "Merch", "Notes": "Club fair t-shirt & sticker sales", "Type": "Income", "Season": "2026-2027"},
            {"Date": "09-22-2026", "Entity": "Surf & Mountain Supply", "Amount": 1000.0, "Category": "Sponsorship", "Notes": "Annual gold-tier club sponsor contribution", "Type": "Income", "Season": "2026-2027"},
            {"Date": "10-04-2026", "Entity": "Fall 2026 Dues Wave 2", "Amount": 1500.0, "Category": "Membership Dues", "Notes": "25 additional member sign-ups", "Type": "Income", "Season": "2026-2027"},
            {"Date": "10-10-2026", "Entity": "Alterra Mountain Co", "Amount": 1200.0, "Category": "Ikon", "Notes": "Ikon Pass club group discount commission rebate", "Type": "Income", "Season": "2026-2027"},
            {"Date": "10-14-2026", "Entity": "IV Theater Rental", "Amount": 350.0, "Category": "Socials", "Notes": "TGR ski film premiere screening hall rental", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "10-20-2026", "Entity": "Custom Ink", "Amount": 1980.0, "Category": "Merch", "Notes": "Team heavyweight fleece embroidered hoodies (75 units)", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "10-25-2026", "Entity": "Mammoth Vacation Rentals", "Amount": 1200.0, "Category": "Housing/Rental", "Notes": "Mammoth Season Opener 50% reservation deposit", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "10-28-2026", "Entity": "Online Team Store", "Amount": 890.0, "Category": "Merch", "Notes": "Pre-orders for 26-27 hoodies & beanies", "Type": "Income", "Season": "2026-2027"},
            {"Date": "11-02-2026", "Entity": "Mammoth Opener Signups", "Amount": 3840.0, "Category": "Trip Payment", "Notes": "24 attendees at $160 package fee", "Type": "Income", "Season": "2026-2027"},
            {"Date": "11-06-2026", "Entity": "Mammoth Vacation Rentals", "Amount": 1200.0, "Category": "Housing/Rental", "Notes": "Mammoth Season Opener final cabin rental balance", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "11-10-2026", "Entity": "Costco Wholesale", "Amount": 420.0, "Category": "Food/Drink (Trip)", "Notes": "Mammoth trip grocery run - breakfasts, pasta, snacks", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "11-12-2026", "Entity": "USCSA National Office", "Amount": 650.0, "Category": "USCSA", "Notes": "USCSA 2026-2027 institutional team dues & club insurance", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "11-24-2026", "Entity": "Member Carpool Drivers", "Amount": 840.0, "Category": "Transportation/Gas", "Notes": "Gas reimbursement for 6 Mammoth driver vehicles (720 mi)", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "11-28-2026", "Entity": "Wax Clinic & Bake Sale", "Amount": 460.0, "Category": "Fundraising", "Notes": "Campus ski tuning table & homemade treats", "Type": "Income", "Season": "2026-2027"},
            {"Date": "12-05-2026", "Entity": "Winter Dues Collection", "Amount": 900.0, "Category": "Membership Dues", "Notes": "15 late-fall & transfer student registrations", "Type": "Income", "Season": "2026-2027"},
            {"Date": "12-10-2026", "Entity": "Tahoe Donner Properties", "Amount": 1900.0, "Category": "Housing/Rental", "Notes": "Palisades Tahoe MLK Trip 50% booking deposit", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "12-14-2026", "Entity": "Knitcraft Headwear", "Amount": 560.0, "Category": "Merch", "Notes": "Team jacquard pom beanies (100 units)", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "12-18-2026", "Entity": "Sierra Avalanche Center", "Amount": 350.0, "Category": "Staff", "Notes": "AIARE Level 1 certified instructor guest lecture stipend", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "12-20-2026", "Entity": "Holiday Merch Pop-Up", "Amount": 780.0, "Category": "Merch", "Notes": "Winter break gift merch pop-up sales", "Type": "Income", "Season": "2026-2027"},
            {"Date": "01-08-2027", "Entity": "Palisades Tahoe MLK Signups", "Amount": 6720.0, "Category": "Trip Payment", "Notes": "32 attendees at $210 package fee", "Type": "Income", "Season": "2026-2027"},
            {"Date": "01-10-2027", "Entity": "Tahoe Donner Properties", "Amount": 1900.0, "Category": "Housing/Rental", "Notes": "Palisades Tahoe MLK Trip final cabin balance", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "01-12-2027", "Entity": "Raley's Supermarket", "Amount": 620.0, "Category": "Food/Drink (Trip)", "Notes": "Tahoe MLK weekend grocery provisions & team dinners", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "01-15-2027", "Entity": "Palisades Tahoe Group Desk", "Amount": 420.0, "Category": "Lift Tickets", "Notes": "Discounted day passes for non-Ikon club members", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "01-20-2027", "Entity": "Member Carpool Drivers", "Amount": 1350.0, "Category": "Transportation/Gas", "Notes": "Gas reimbursement for 8 Tahoe drivers (880 mi roundtrip)", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "01-22-2027", "Entity": "China Peak USCSA Signups", "Amount": 2520.0, "Category": "Trip Payment", "Notes": "14 comp team racers at $180 travel fee", "Type": "Income", "Season": "2026-2027"},
            {"Date": "01-24-2027", "Entity": "China Peak Mountain Lodge", "Amount": 1450.0, "Category": "Housing/Rental", "Notes": "2 nights comp team slope-side cabins", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "01-25-2027", "Entity": "USCSA Southwest Division", "Amount": 500.0, "Category": "USCSA", "Notes": "China Peak Qualifier team slalom/GS bib registration", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "01-26-2027", "Entity": "Costco - Race Team Nutrition", "Amount": 380.0, "Category": "Food/Drink (Trip)", "Notes": "Hydration electrolytes, energy bars, race breakfast", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "01-29-2027", "Entity": "Racer Driver Gas Reimbursement", "Amount": 420.0, "Category": "Transportation/Gas", "Notes": "3 driver vehicles to China Peak (550 mi roundtrip)", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "02-04-2027", "Entity": "Big Bear Weekend Signups", "Amount": 2880.0, "Category": "Trip Payment", "Notes": "18 attendees at $160 package fee", "Type": "Income", "Season": "2026-2027"},
            {"Date": "02-06-2027", "Entity": "Big Bear Lakefront Cabins", "Amount": 1650.0, "Category": "Housing/Rental", "Notes": "2 nights lodging for Big Bear weekend", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "02-08-2027", "Entity": "Stater Bros Markets", "Amount": 310.0, "Category": "Food/Drink (Trip)", "Notes": "Big Bear cabin groceries, s'mores, sandwich supplies", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "02-10-2027", "Entity": "Big Bear Mountain Day Tickets", "Amount": 240.0, "Category": "Lift Tickets", "Notes": "Beginner ticket upgrades for new athletes", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "02-12-2027", "Entity": "Member Carpool Drivers", "Amount": 380.0, "Category": "Transportation/Gas", "Notes": "Gas stipends for 4 Big Bear vehicles (370 mi)", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "02-18-2027", "Entity": "Red Bull College Network", "Amount": 750.0, "Category": "Sponsorship", "Notes": "Spring contest prize support and event sponsor grant", "Type": "Income", "Season": "2026-2027"},
            {"Date": "02-22-2027", "Entity": "Wilderness Medical Systems", "Amount": 210.0, "Category": "Other", "Notes": "Replacement splints, gauze, and club two-way radio batteries", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "03-05-2027", "Entity": "Mammoth Spring Fling Signups", "Amount": 4320.0, "Category": "Trip Payment", "Notes": "24 attendees at $180 spring break fee", "Type": "Income", "Season": "2026-2027"},
            {"Date": "03-08-2027", "Entity": "Mammoth Mountain Condos", "Amount": 2400.0, "Category": "Housing/Rental", "Notes": "3 nights 2-condo rental for spring break", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "03-12-2027", "Entity": "Vons Mammoth Lakes", "Amount": 540.0, "Category": "Food/Drink (Trip)", "Notes": "Spring break taco bar provisions & team groceries", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "03-15-2027", "Entity": "Member Carpool Drivers", "Amount": 920.0, "Category": "Transportation/Gas", "Notes": "Gas reimbursements for 6 vehicles to Mammoth", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "03-18-2027", "Entity": "Spring Quarter Dues", "Amount": 600.0, "Category": "Membership Dues", "Notes": "10 spring quarter joiners", "Type": "Income", "Season": "2026-2027"},
            {"Date": "03-24-2027", "Entity": "USCSA Southwest Division", "Amount": 400.0, "Category": "USCSA", "Notes": "USCSA Regional Championship race bib entries", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "04-05-2027", "Entity": "Alumni & Parent Donor Drive", "Amount": 1850.0, "Category": "Fundraising", "Notes": "Annual spring alumni booster campaign", "Type": "Income", "Season": "2026-2027"},
            {"Date": "04-12-2027", "Entity": "Campus Merch Clearance", "Amount": 640.0, "Category": "Merch", "Notes": "End-of-season stickers, tees, and hats sale", "Type": "Income", "Season": "2026-2027"},
            {"Date": "04-18-2027", "Entity": "Goleta Beach Park Dayge", "Amount": 290.0, "Category": "Socials", "Notes": "End of season beach BBQ grill supplies and drinks", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "04-22-2027", "Entity": "Crown Awards Co", "Amount": 280.0, "Category": "Other", "Notes": "Custom engraved team awards & senior plaques", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "05-06-2027", "Entity": "Banquet Ticket Sales", "Amount": 1100.0, "Category": "Other Income", "Notes": "22 banquet guest tickets at $50/ea", "Type": "Income", "Season": "2026-2027"},
            {"Date": "05-10-2027", "Entity": "The Club & Guest House UCSB", "Amount": 850.0, "Category": "Socials", "Notes": "Annual End-of-Season Awards Banquet venue rental", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "05-12-2027", "Entity": "Campus Catering", "Amount": 920.0, "Category": "Socials", "Notes": "Banquet dinner buffet & dessert", "Type": "Expense", "Season": "2026-2027"},
            {"Date": "05-20-2027", "Entity": "Isla Vista Mini Storage", "Amount": 480.0, "Category": "Other", "Notes": "Annual locker rental for slalom gates, wax benches & drills", "Type": "Expense", "Season": "2026-2027"},

            # =========================================================================
            # SEASON 2025-2026 (ARCHIVED SEASON - COMPLETE 9 MONTHS)
            # =========================================================================
            {"Date": "09-01-2025", "Entity": "UCSB Ski Team Treasury", "Amount": 3500.0, "Category": "Other Income", "Notes": "Carryover Operating Funds from 2024-2025 Season", "Type": "Income", "Season": "2025-2026"},
            {"Date": "09-15-2025", "Entity": "Costco Wholesale", "Amount": 220.0, "Category": "Socials", "Notes": "Welcome Back BBQ provisions", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "10-05-2025", "Entity": "Fall Dues Collection (Batch 1)", "Amount": 1500.0, "Category": "Membership Dues", "Notes": "25 member registrations", "Type": "Income", "Season": "2025-2026"},
            {"Date": "10-15-2025", "Entity": "Custom Ink", "Amount": 1200.0, "Category": "Merch", "Notes": "Season member t-shirts (200 qty)", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "10-18-2025", "Entity": "Fall Dues Collection (Batch 2)", "Amount": 1200.0, "Category": "Membership Dues", "Notes": "20 member registrations", "Type": "Income", "Season": "2025-2026"},
            {"Date": "10-25-2025", "Entity": "Costco Wholesale", "Amount": 280.0, "Category": "Socials", "Notes": "Kickoff BBQ burgers & provisions", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "11-02-2025", "Entity": "Local Board Shop Sponsorship", "Amount": 1000.0, "Category": "Sponsorship", "Notes": "Annual club sponsor contribution", "Type": "Income", "Season": "2025-2026"},
            {"Date": "11-05-2025", "Entity": "Mammoth Mountain Chalet", "Amount": 2200.0, "Category": "Housing/Rental", "Notes": "Winter opener 3 nights cabin rental", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "11-10-2025", "Entity": "Mammoth Opener Signups", "Amount": 3840.0, "Category": "Trip Payment", "Notes": "24 attendees at $160", "Type": "Income", "Season": "2025-2026"},
            {"Date": "11-12-2025", "Entity": "Vons Supermarket", "Amount": 350.0, "Category": "Food/Drink (Trip)", "Notes": "Mammoth trip breakfast provisions", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "11-18-2025", "Entity": "Member Gas Reimbursement", "Amount": 1050.0, "Category": "Transportation/Gas", "Notes": "6 driver vehicles (720 miles)", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "12-05-2025", "Entity": "Winter Dues Collection", "Amount": 900.0, "Category": "Membership Dues", "Notes": "15 late fall registrations", "Type": "Income", "Season": "2025-2026"},
            {"Date": "12-10-2025", "Entity": "Alpine Screenprinting", "Amount": 950.0, "Category": "Merch", "Notes": "Winter team hoodies", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "12-15-2025", "Entity": "Winter Holiday Merch Pop-Up", "Amount": 480.0, "Category": "Merch", "Notes": "Apparel sales at campus holiday fair", "Type": "Income", "Season": "2025-2026"},
            {"Date": "01-08-2026", "Entity": "Tahoe Mountain Lodge", "Amount": 3800.0, "Category": "Housing/Rental", "Notes": "MLK 3 nights lodging for 32 athletes", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "01-10-2026", "Entity": "Lake Tahoe MLK Signups", "Amount": 6720.0, "Category": "Trip Payment", "Notes": "32 attendees at $210", "Type": "Income", "Season": "2025-2026"},
            {"Date": "01-14-2026", "Entity": "Raley's Supermarket", "Amount": 500.0, "Category": "Food/Drink (Trip)", "Notes": "Tahoe weekend group provisions", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "01-15-2026", "Entity": "Palisades Group Lift Tickets", "Amount": 350.0, "Category": "Lift Tickets", "Notes": "Non-Ikon athlete day passes", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "01-20-2026", "Entity": "Member Gas Reimbursement", "Amount": 1400.0, "Category": "Transportation/Gas", "Notes": "8 driver vehicles (880 miles)", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "01-20-2026", "Entity": "Big Bear Weekend Signups", "Amount": 2520.0, "Category": "Trip Payment", "Notes": "18 attendees at $140", "Type": "Income", "Season": "2025-2026"},
            {"Date": "01-22-2026", "Entity": "Big Bear Vacation Rentals", "Amount": 1800.0, "Category": "Housing/Rental", "Notes": "2 nights cabin", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "01-23-2026", "Entity": "Stater Bros", "Amount": 260.0, "Category": "Food/Drink (Trip)", "Notes": "Big Bear food & drinks", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "01-24-2026", "Entity": "Big Bear Mountain Tickets", "Amount": 120.0, "Category": "Lift Tickets", "Notes": "Beginner day passes", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "01-26-2026", "Entity": "Member Gas Reimbursement", "Amount": 360.0, "Category": "Transportation/Gas", "Notes": "4 driver vehicles (370 miles)", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "01-28-2026", "Entity": "China Peak Signups", "Amount": 2520.0, "Category": "Trip Payment", "Notes": "14 racers at $180", "Type": "Income", "Season": "2025-2026"},
            {"Date": "01-28-2026", "Entity": "China Peak Inn", "Amount": 1450.0, "Category": "Housing/Rental", "Notes": "2 nights comp team lodging", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "01-29-2026", "Entity": "USCSA Southwest Division", "Amount": 450.0, "Category": "USCSA", "Notes": "Qualifier team registration fees", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "01-29-2026", "Entity": "China Peak Lift Tickets", "Amount": 400.0, "Category": "Lift Tickets", "Notes": "Racer discounted passes", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "01-30-2026", "Entity": "Costco - Race Provisions", "Amount": 450.0, "Category": "Food/Drink (Trip)", "Notes": "Energy bars, hydration, racer breakfast", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "02-02-2026", "Entity": "Member Gas Reimbursement", "Amount": 400.0, "Category": "Transportation/Gas", "Notes": "3 driver vehicles (550 miles)", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "02-15-2026", "Entity": "Campus Merch Pop-Up", "Amount": 650.0, "Category": "Merch", "Notes": "Cash & card apparel sales", "Type": "Income", "Season": "2025-2026"},
            {"Date": "02-18-2026", "Entity": "Wilderness First Aid Gear", "Amount": 320.0, "Category": "Other", "Notes": "Safety kits and radios", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "02-20-2026", "Entity": "Red Bull Campus Contribution", "Amount": 500.0, "Category": "Sponsorship", "Notes": "Contest prize sponsorship", "Type": "Income", "Season": "2025-2026"},
            {"Date": "03-05-2026", "Entity": "Mammoth Spring Trip Signups", "Amount": 3840.0, "Category": "Trip Payment", "Notes": "24 attendees at $160", "Type": "Income", "Season": "2025-2026"},
            {"Date": "03-08-2026", "Entity": "Mammoth Mountain Chalet", "Amount": 2100.0, "Category": "Housing/Rental", "Notes": "Spring break 3 nights cabin", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "03-10-2026", "Entity": "Vons Supermarket", "Amount": 380.0, "Category": "Food/Drink (Trip)", "Notes": "Mammoth spring groceries", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "03-15-2026", "Entity": "Member Gas Reimbursement", "Amount": 980.0, "Category": "Transportation/Gas", "Notes": "6 driver vehicles to Mammoth", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "03-22-2026", "Entity": "Spring Dues Collection", "Amount": 480.0, "Category": "Membership Dues", "Notes": "8 late joiner registrations", "Type": "Income", "Season": "2025-2026"},
            {"Date": "04-08-2026", "Entity": "Alumni Booster Campaign", "Amount": 1400.0, "Category": "Fundraising", "Notes": "Spring alumni fundraiser", "Type": "Income", "Season": "2025-2026"},
            {"Date": "04-15-2026", "Entity": "End-of-Season Beach BBQ", "Amount": 260.0, "Category": "Socials", "Notes": "Grill supplies, drinks, beach permits", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "04-25-2026", "Entity": "Trophy & Awards Co", "Amount": 240.0, "Category": "Other", "Notes": "Custom senior athlete awards", "Type": "Expense", "Season": "2025-2026"},
            {"Date": "05-05-2026", "Entity": "Banquet Ticket Sales", "Amount": 950.0, "Category": "Other Income", "Notes": "19 banquet guest tickets at $50/ea", "Type": "Income", "Season": "2025-2026"},
            {"Date": "05-10-2026", "Entity": "UCSB Faculty Club Banquet", "Amount": 1350.0, "Category": "Socials", "Notes": "End-of-year team banquet hall rental & dinner", "Type": "Expense", "Season": "2025-2026"}
        ]
        pd.DataFrame(ledger_rows).to_csv(DEMO_LEDGER_FILE, index=False)

    if not os.path.exists(DEMO_TODOS_FILE):
        todos_data = [
            {
                "TaskID": "TASK-001", "Season": "2026-2027", "Title": "Submit Ikon Club Pass Application",
                "Description": "Verify member roster meets 20+ pass minimum for discount tier",
                "AssignedTo": "President, Treasurer", "SubmittedDate": "2026-09-10", "TargetDate": "2026-09-30",
                "Status": "Pending", "CompletedDate": "", "Notes": "Early deadline"
            },
            {
                "TaskID": "TASK-002", "Season": "2026-2027", "Title": "Finalize Mammoth Cabin Contract",
                "Description": "Sign rental agreement and pay 50% security deposit",
                "AssignedTo": "Trip Director", "SubmittedDate": "2026-09-12", "TargetDate": "2026-10-05",
                "Status": "Pending", "CompletedDate": "", "Notes": "Owner confirmed check-in codes"
            },
            {
                "TaskID": "TASK-003", "Season": "2026-2027", "Title": "Order Fall Team Hoodies",
                "Description": "Consolidate member sizing and submit print purchase order",
                "AssignedTo": "Gear Manager", "SubmittedDate": "2026-09-14", "TargetDate": "2026-10-15",
                "Status": "Pending", "CompletedDate": "", "Notes": "2-week turnaround"
            },
            {
                "TaskID": "TASK-004", "Season": "2026-2027", "Title": "Plan Welcome Back BBQ & Wax Clinic",
                "Description": "Reserve campus park space, buy burgers and ski wax supplies",
                "AssignedTo": "Social Chair", "SubmittedDate": "2026-09-08", "TargetDate": "2026-09-22",
                "Status": "Completed", "CompletedDate": "2026-09-20", "Notes": "Great turnout, 45 attended"
            },
            {
                "TaskID": "TASK-005", "Season": "2025-2026", "Title": "USCSA Southwest Division Meeting",
                "Description": "Attend annual competition scheduling conference call",
                "AssignedTo": "President", "SubmittedDate": "2025-10-01", "TargetDate": "2025-10-15",
                "Status": "Completed", "CompletedDate": "2025-10-14", "Notes": "Schedule confirmed"
            }
        ]
        pd.DataFrame(todos_data).to_csv(DEMO_TODOS_FILE, index=False)

    if not os.path.exists(DEMO_MERCH_FILE):
        merch_data = [
            {"AdjustmentID": "ADJ-001", "Season": "2026-2027", "Date": "2026-09-15", "ItemType": "T-Shirt", "Size": "L", "Quantity": -2, "Reason": "Sold at Club Fair", "LoggedBy": "Gear Manager"},
            {"AdjustmentID": "ADJ-002", "Season": "2026-2027", "Date": "2026-09-16", "ItemType": "Sweatshirt", "Size": "M", "Quantity": -1, "Reason": "Welcome BBQ Raffle Prize", "LoggedBy": "Social Chair"},
            {"AdjustmentID": "ADJ-003", "Season": "2026-2027", "Date": "2026-09-18", "ItemType": "T-Shirt", "Size": "M", "Quantity": 15, "Reason": "Restock from Alpine Print Co", "LoggedBy": "Treasurer"}
        ]
        pd.DataFrame(merch_data).to_csv(DEMO_MERCH_FILE, index=False)

    if not os.path.exists(DEMO_EVENTS_FILE):
        events_data = [
            # 2026-2027 Events
            {
                "EventID": "EVT-001", "Season": "2026-2027", "Title": "Fall Welcome Back BBQ & Wax Clinic",
                "EventType": "Social", "StartDate": "2026-09-22", "EndDate": "2026-09-22",
                "StartTime": "16:00", "EndTime": "19:00", "Location": "Anisq'Oyo' Park, Isla Vista",
                "Status": "Completed", "OfficerLead": "Social Chair",
                "Description": "Burgers, hot dogs, cold drinks, ski tuning benches, and team stickers. Bring your boards to wax!",
                "RsvpLink": ""
            },
            {
                "EventID": "EVT-002", "Season": "2026-2027", "Title": "Fall General Meeting #1 (Club Kickoff & Ikon Info)",
                "EventType": "Club Meeting", "StartDate": "2026-10-06", "EndDate": "2026-10-06",
                "StartTime": "19:00", "EndTime": "20:30", "Location": "Campbell Hall 1610, UCSB Campus",
                "Status": "Completed", "OfficerLead": "President",
                "Description": "Annual club season overview, Ikon college discount code distribution, and trip calendar preview.",
                "RsvpLink": "https://forms.gle/ucsb-ski-meeting-1"
            },
            {
                "EventID": "EVT-003", "Season": "2026-2027", "Title": "Teton Gravity Research Ski Film Premiere",
                "EventType": "Social", "StartDate": "2026-10-16", "EndDate": "2026-10-16",
                "StartTime": "20:00", "EndTime": "22:00", "Location": "Isla Vista Theater (IV Theater 1)",
                "Status": "Completed", "OfficerLead": "Social Chair",
                "Description": "Annual premiere of the new TGR freeride movie. Free popcorn, sponsor raffle, and winter hype!",
                "RsvpLink": ""
            },
            {
                "EventID": "EVT-004", "Season": "2026-2027", "Title": "Pre-Season Dryland Leg Burner & Core Workout",
                "EventType": "Dryland / Fitness", "StartDate": "2026-11-04", "EndDate": "2026-11-04",
                "StartTime": "17:00", "EndTime": "18:15", "Location": "UCSB Rec Cen Turf Fields",
                "Status": "Completed", "OfficerLead": "Safety Officer",
                "Description": "Ski-specific plyometrics, squat circuits, and agility ladder drills to prep for Mammoth opening week.",
                "RsvpLink": ""
            },
            {
                "EventID": "EVT-005", "Season": "2026-2027", "Title": "Thanksgiving Ski Wax Clinic & Bake Sale",
                "EventType": "Fundraiser / Merch", "StartDate": "2026-11-18", "EndDate": "2026-11-18",
                "StartTime": "11:00", "EndTime": "15:00", "Location": "UCSB Arbor Walkway",
                "Status": "Completed", "OfficerLead": "Gear Manager",
                "Description": "$10 quick hot wax for students, homemade baked goods, and team merch pre-orders.",
                "RsvpLink": ""
            },
            {
                "EventID": "EVT-006", "Season": "2026-2027", "Title": "AIARE Avalanche Safety & Beacon Clinic",
                "EventType": "Clinic / Workshop", "StartDate": "2026-12-08", "EndDate": "2026-12-08",
                "StartTime": "18:30", "EndTime": "20:00", "Location": "Buchanan Hall 1930, UCSB Campus",
                "Status": "Completed", "OfficerLead": "Safety Officer",
                "Description": "Certified backcountry guide guest presentation on beacon search techniques, snowpack tests, and companion rescue.",
                "RsvpLink": ""
            },
            {
                "EventID": "EVT-007", "Season": "2026-2027", "Title": "Winter General Meeting & Tahoe MLK Trip Briefing",
                "EventType": "Club Meeting", "StartDate": "2027-01-10", "EndDate": "2027-01-10",
                "StartTime": "19:00", "EndTime": "20:15", "Location": "Campbell Hall 1610, UCSB Campus",
                "Status": "Completed", "OfficerLead": "Trip Director",
                "Description": "Mandatory trip briefing for all athletes attending the Palisades Tahoe MLK trip. Carpools and cabin rules announced.",
                "RsvpLink": ""
            },
            {
                "EventID": "EVT-008", "Season": "2026-2027", "Title": "End-of-Season Beach Dayge BBQ",
                "EventType": "Social", "StartDate": "2027-04-18", "EndDate": "2027-04-18",
                "StartTime": "13:00", "EndTime": "17:30", "Location": "Goleta Beach Park (Area B)",
                "Status": "Confirmed", "OfficerLead": "Social Chair",
                "Description": "Post-season beach day celebration with volleyball, spikeball, burgers, and spring sun.",
                "RsvpLink": ""
            },
            {
                "EventID": "EVT-009", "Season": "2026-2027", "Title": "Annual UCSB Ski Team Awards Banquet",
                "EventType": "Social", "StartDate": "2027-05-14", "EndDate": "2027-05-14",
                "StartTime": "18:00", "EndTime": "21:30", "Location": "The Club & Guest House at UCSB",
                "Status": "Confirmed", "OfficerLead": "President",
                "Description": "Semi-formal banquet dinner, season highlight video premiere, graduating senior tributes, and annual athlete awards.",
                "RsvpLink": "https://tickets.ucsbskiteam.com/banquet2027"
            },

            # 2025-2026 Events
            {
                "EventID": "EVT-010", "Season": "2025-2026", "Title": "Fall Kickoff BBQ & Team Meeting",
                "EventType": "Social", "StartDate": "2025-09-24", "EndDate": "2025-09-24",
                "StartTime": "16:30", "EndTime": "19:00", "Location": "Anisq'Oyo' Park, Isla Vista",
                "Status": "Completed", "OfficerLead": "President",
                "Description": "Welcome back barbecue and season kickoff.",
                "RsvpLink": ""
            },
            {
                "EventID": "EVT-011", "Season": "2025-2026", "Title": "Warren Miller Ski Film Screening",
                "EventType": "Social", "StartDate": "2025-10-18", "EndDate": "2025-10-18",
                "StartTime": "19:30", "EndTime": "21:30", "Location": "IV Theater",
                "Status": "Completed", "OfficerLead": "Social Chair",
                "Description": "Annual winter stoke film premiere.",
                "RsvpLink": ""
            },
            {
                "EventID": "EVT-012", "Season": "2025-2026", "Title": "End-of-Year Awards Banquet 2026",
                "EventType": "Social", "StartDate": "2026-05-10", "EndDate": "2026-05-10",
                "StartTime": "18:30", "EndTime": "21:30", "Location": "UCSB Faculty Club",
                "Status": "Completed", "OfficerLead": "President",
                "Description": "Annual team awards banquet dinner.",
                "RsvpLink": ""
            }
        ]
        pd.DataFrame(events_data).to_csv(DEMO_EVENTS_FILE, index=False)

    if not os.path.exists(DEMO_OFFICERS_FILE):
        pd.DataFrame({"Officer": DEMO_OFFICERS}).to_csv(DEMO_OFFICERS_FILE, index=False)


def ensure_data_initialized():
    """Ensure data directory and required CSV files exist with baseline schema without demo data bleeding."""
    os.makedirs(DATA_DIR, exist_ok=True)
    ensure_demo_data_initialized()

    def _file_is_empty_or_missing(filepath: str) -> bool:
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            return True
        try:
            df_check = pd.read_csv(filepath)
            return df_check.empty
        except Exception:
            return True

    if _file_is_empty_or_missing(LEDGER_FILE):
        if os.path.exists(DOWNLOADS_SOURCE):
            shutil.copyfile(DOWNLOADS_SOURCE, LEDGER_FILE)
            df = pd.read_csv(LEDGER_FILE)
            df["Season"] = "2025-2026"
            df.to_csv(LEDGER_FILE, index=False)
        else:
            df = pd.DataFrame(columns=["Date", "Entity", "Amount", "Category", "Notes", "Type", "Season", "LoggedBy"])
            df.to_csv(LEDGER_FILE, index=False)

    if _file_is_empty_or_missing(MEMBERS_FILE):
        df_members = pd.DataFrame(columns=[
            "MemberID", "Season", "Name", "Email", "Phone", "Year", "SkiBoard",
            "DuesPaid", "Slack", "TShirtSize", "CompTeam", "TripsAttended", "Notes"
        ])
        df_members.to_csv(MEMBERS_FILE, index=False)
    else:
        # Automatic safeguard: purge any demo members from production members.csv
        try:
            m_df = pd.read_csv(MEMBERS_FILE)
            cleaned_m_df = purge_demo_members_from_df(m_df)
            if len(cleaned_m_df) != len(m_df):
                cleaned_m_df.to_csv(MEMBERS_FILE, index=False)
        except Exception:
            pass

    if _file_is_empty_or_missing(TRIPS_FILE):
        df_trips = pd.DataFrame(columns=TRIP_COLS)
        df_trips.to_csv(TRIPS_FILE, index=False)

    if _file_is_empty_or_missing(TRIP_SIGNUPS_FILE):
        df_signups = pd.DataFrame(columns=SIGNUP_COLS)
        df_signups.to_csv(TRIP_SIGNUPS_FILE, index=False)

    if _file_is_empty_or_missing(TODOS_FILE):
        df_todos = pd.DataFrame(columns=TODO_COLS)
        df_todos.to_csv(TODOS_FILE, index=False)

    if not os.path.exists(MERCH_FILE):
        df_merch = pd.DataFrame(columns=[
            "AdjustmentID", "Season", "Date", "ItemType", "Size", "Quantity", "Reason", "LoggedBy"
        ])
        df_merch.to_csv(MERCH_FILE, index=False)

    if _file_is_empty_or_missing(EVENTS_FILE):
        df_events = pd.DataFrame(columns=EVENT_COLS)
        df_events.to_csv(EVENTS_FILE, index=False)

    if not os.path.exists(OFFICERS_FILE):
        pd.DataFrame({"Officer": OFFICERS}).to_csv(OFFICERS_FILE, index=False)


# --- LEDGER OPERATIONS (MULTI-SEASON) ---

def trigger_ledger_webhook(action: str, transaction_data: dict):
    """Optionally notify a Google Apps Script webhook to mirror ledger additions to Google Sheet."""
    if not LEDGER_WEBHOOK_URL:
        return
    try:
        import json
        import urllib.request
        payload = json.dumps({"action": action, "data": transaction_data}).encode("utf-8")
        req = urllib.request.Request(
            LEDGER_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "SkiTeamDash/1.0"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception as e:
        print(f"Ledger webhook notification skipped or failed: {e}")


def import_ledger_dataframe(df_source: pd.DataFrame, mode: str = "replace", is_officer: bool = False) -> tuple[bool, str, int]:
    """
    Intelligently map, clean, and import an external DataFrame (from CSV or Google Sheet)
    into the master ledger (multi-season).
    Modes:
      - 'replace': Replaces current master ledger records.
      - 'append': Appends new transactions, de-duplicating against existing entries.
    """
    try:
        if df_source is None or df_source.empty:
            return False, "Import data is empty or contains no records.", 0

        df = df_source.copy()
        norm_cols = {c: re.sub(r"[^a-zA-Z0-9]", "", str(c)).lower() for c in df.columns}

        col_map = {}
        for orig_col, norm in norm_cols.items():
            if norm in ["date", "transactiondate", "transdate", "txdate", "timestamp"]:
                if "Date" not in col_map:
                    col_map["Date"] = orig_col
            elif norm in ["entity", "vendor", "payer", "payee", "merchant", "person", "recipient", "target", "name"]:
                if "Entity" not in col_map:
                    col_map["Entity"] = orig_col
            elif norm in ["amount", "cost", "total", "amt", "value", "price", "usd", "dollars"]:
                if "Amount" not in col_map:
                    col_map["Amount"] = orig_col
            elif norm in ["category", "cat", "budgetcategory", "item"]:
                if "Category" not in col_map:
                    col_map["Category"] = orig_col
            elif norm in ["notes", "note", "description", "memo", "details", "comment", "comments", "desc"]:
                if "Notes" not in col_map:
                    col_map["Notes"] = orig_col
            elif norm in ["type", "transtype", "transactiontype", "incomeexpense", "flow", "classification"]:
                if "Type" not in col_map:
                    col_map["Type"] = orig_col
            elif norm in ["season", "academicyear", "year", "schoolyear"]:
                if "Season" not in col_map:
                    col_map["Season"] = orig_col
            elif norm in ["loggedby", "officer", "author", "enteredby", "submittedby", "admin"]:
                if "LoggedBy" not in col_map:
                    col_map["LoggedBy"] = orig_col

        if "Amount" not in col_map and "Entity" not in col_map:
            return False, "Could not identify required ledger columns (Date, Entity, Amount).", 0

        std_rows = []
        for _, row in df.iterrows():
            # Date
            raw_date = str(row[col_map["Date"]]).strip() if "Date" in col_map and pd.notna(row[col_map["Date"]]) else ""
            if raw_date and raw_date.lower() not in ["nan", "none", "nat"]:
                try:
                    dt = pd.to_datetime(raw_date, errors="coerce")
                    if pd.notna(dt):
                        date_str = dt.strftime("%m-%d-%Y")
                    else:
                        date_str = raw_date
                except Exception:
                    date_str = raw_date
            else:
                date_str = date.today().strftime("%m-%d-%Y")

            # Entity
            entity_val = str(row[col_map["Entity"]]).strip() if "Entity" in col_map and pd.notna(row[col_map["Entity"]]) else ""
            if entity_val.lower() in ["nan", "none"]:
                entity_val = ""

            # Amount
            amt_raw = row[col_map["Amount"]] if "Amount" in col_map and pd.notna(row[col_map["Amount"]]) else 0.0
            is_negative = False
            if isinstance(amt_raw, str):
                cleaned_amt = amt_raw.replace("$", "").replace(",", "").strip()
                if cleaned_amt.startswith("(") and cleaned_amt.endswith(")"):
                    is_negative = True
                    cleaned_amt = cleaned_amt[1:-1].strip()
                try:
                    amount_val = float(cleaned_amt)
                    if is_negative:
                        amount_val = -abs(amount_val)
                except Exception:
                    amount_val = 0.0
            else:
                try:
                    amount_val = float(amt_raw)
                except Exception:
                    amount_val = 0.0

            # Type
            raw_type = str(row[col_map["Type"]]).strip() if "Type" in col_map and pd.notna(row[col_map["Type"]]) else ""
            if raw_type.lower() in ["income", "revenue", "inflow", "credit", "deposit"]:
                trans_type = "Income"
            elif raw_type.lower() in ["expense", "disbursement", "outflow", "debit", "cost"]:
                trans_type = "Expense"
            else:
                if amount_val < 0:
                    trans_type = "Expense"
                elif "Category" in col_map and str(row[col_map["Category"]]).strip() in INCOME_CATEGORIES:
                    trans_type = "Income"
                else:
                    trans_type = "Expense"

            amount_val = abs(amount_val)

            # Category
            cat_val = str(row[col_map["Category"]]).strip() if "Category" in col_map and pd.notna(row[col_map["Category"]]) else "Other"
            if cat_val.upper() == "IKON":
                cat_val = "Ikon"
            elif cat_val.lower() in ["nan", "none", ""]:
                cat_val = "Other"

            # Notes
            notes_val = str(row[col_map["Notes"]]).strip() if "Notes" in col_map and pd.notna(row[col_map["Notes"]]) else ""
            if notes_val.lower() in ["nan", "none"]:
                notes_val = ""

            # Season
            season_val = str(row[col_map["Season"]]).strip() if "Season" in col_map and pd.notna(row[col_map["Season"]]) else ""
            if season_val.lower() in ["nan", "none", ""]:
                try:
                    dt_check = pd.to_datetime(date_str, errors="coerce")
                    if pd.notna(dt_check):
                        y = dt_check.year
                        m = dt_check.month
                        season_val = f"{y}-{y+1}" if m >= 8 else f"{y-1}-{y}"
                    else:
                        season_val = CURRENT_SEASON
                except Exception:
                    season_val = CURRENT_SEASON

            # LoggedBy
            logged_val = str(row[col_map["LoggedBy"]]).strip() if "LoggedBy" in col_map and pd.notna(row[col_map["LoggedBy"]]) else ""
            if logged_val.lower() in ["nan", "none"]:
                logged_val = ""

            if not entity_val and amount_val == 0.0:
                continue

            std_rows.append({
                "Date": date_str,
                "Entity": entity_val,
                "Amount": amount_val,
                "Category": cat_val,
                "Notes": notes_val,
                "Type": trans_type,
                "Season": season_val,
                "LoggedBy": logged_val
            })

        if not std_rows:
            return False, "No valid transaction rows could be parsed from the provided data.", 0

        new_df = pd.DataFrame(std_rows)

        if mode == "append":
            current_df = load_ledger(season=None, is_officer=is_officer)
            combined_df = pd.concat([new_df, current_df], ignore_index=True)
            combined_df = combined_df.drop_duplicates(
                subset=["Date", "Entity", "Amount", "Category", "Type", "Season", "Notes"],
                keep="first"
            ).reset_index(drop=True)
            final_df = combined_df
            added_count = len(final_df) - len(current_df)
            msg = f"Appended {added_count} new transaction(s) into master ledger (total records: {len(final_df)})."
        else:
            final_df = new_df
            msg = f"Loaded {len(final_df)} transaction(s) into master ledger across all seasons."

        save_ledger(final_df, is_officer=is_officer)
        return True, msg, len(final_df)
    except Exception as e:
        return False, f"Error processing ledger data: {e}", 0


def sync_ledger_from_google_sheet(sheet_url: str, mode: str = "replace", is_officer: bool = False) -> tuple[bool, str, int]:
    """Fetch a Google Sheet via public CSV export URL and sync into master ledger."""
    clean_url = sheet_url.strip()
    if not clean_url:
        return False, "Google Sheet URL or ID is empty.", 0

    gid_match = re.search(r"gid=([0-9]+)", clean_url)
    gid_str = f"&gid={gid_match.group(1)}" if gid_match else ""

    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", clean_url)
    if match:
        sheet_id = match.group(1)
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv{gid_str}"
    elif clean_url.startswith("http"):
        csv_url = clean_url
    else:
        csv_url = f"https://docs.google.com/spreadsheets/d/{clean_url}/export?format=csv{gid_str}"

    try:
        import urllib.request
        req = urllib.request.Request(
            csv_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            df_sheet = pd.read_csv(response)
        return import_ledger_dataframe(df_sheet, mode=mode, is_officer=is_officer)
    except Exception as e:
        return False, f"Could not fetch Google Sheet. Verify link sharing ('Anyone with the link can view') or upload CSV manually. Details: {e}", 0


def get_master_ledger_csv_bytes(is_officer: bool = False) -> bytes:
    """Get raw UTF-8 CSV bytes of the master ledger across all seasons."""
    df = load_ledger(season=None, is_officer=is_officer)
    cols = ["Date", "Entity", "Amount", "Category", "Notes", "Type", "Season", "LoggedBy"]
    export_df = df[[c for c in cols if c in df.columns]].copy()
    return export_df.to_csv(index=False).encode("utf-8")


def load_ledger(season: str = None, is_officer: bool = False) -> pd.DataFrame:
    """Load and normalize ledger data, optionally filtered by season."""
    ensure_data_initialized()
    if not is_officer:
        if os.path.exists(DEMO_LEDGER_FILE):
            df = pd.read_csv(DEMO_LEDGER_FILE)
        else:
            df = pd.DataFrame(columns=["Date", "Entity", "Amount", "Category", "Notes", "Type", "Season", "LoggedBy"])
    else:
        sheet_url = getattr(config, "LEDGER_SHEET_URL", "") or DEFAULT_LEDGER_SHEET_URL
        df = None
        if sheet_url:
            gs_df = read_gsheet_worksheet(sheet_url, "Ledger", ttl=60)
            if gs_df is None or gs_df.empty or "Amount" not in gs_df.columns:
                gs_df = read_gsheet_worksheet(sheet_url, 0, ttl=60)
            if gs_df is not None and not gs_df.empty and "Amount" in gs_df.columns:
                try:
                    cols = ["Date", "Entity", "Amount", "Category", "Notes", "Type", "Season", "LoggedBy"]
                    save_cache = gs_df[[c for c in cols if c in gs_df.columns]].copy()
                    save_cache.to_csv(LEDGER_FILE, index=False)
                except Exception:
                    pass
                df = gs_df
        if df is None or df.empty:
            if os.path.exists(LEDGER_FILE):
                df = pd.read_csv(LEDGER_FILE)
            else:
                df = pd.DataFrame(columns=["Date", "Entity", "Amount", "Category", "Notes", "Type", "Season", "LoggedBy"])

    try:
        if "Season" not in df.columns:
            df["Season"] = "2025-2026"
            save_ledger(df, is_officer=is_officer)
        if "LoggedBy" not in df.columns:
            df["LoggedBy"] = ""
            
        df["Date_dt"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.sort_values(by="Date_dt", ascending=False).reset_index(drop=True)
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
        df["Type"] = df["Type"].fillna("Expense")
        df["Category"] = df["Category"].replace({"IKON": "Ikon"})
        df["LoggedBy"] = df["LoggedBy"].fillna("").astype(str)

        if season and season != "All Seasons":
            return df[df["Season"] == season].copy().reset_index(drop=True)
        return df
    except Exception as e:
        print(f"Error loading ledger: {e}")
        return pd.DataFrame(columns=["Date", "Entity", "Amount", "Category", "Notes", "Type", "Season", "LoggedBy"])


def save_ledger(df: pd.DataFrame, is_officer: bool = False):
    """Save ledger back to CSV, preserving standard columns and syncing to Google Sheets."""
    cols = ["Date", "Entity", "Amount", "Category", "Notes", "Type", "Season", "LoggedBy"]
    save_df = df[[c for c in cols if c in df.columns]].copy()
    if not is_officer:
        save_df.to_csv(DEMO_LEDGER_FILE, index=False)
        return

    save_df.to_csv(LEDGER_FILE, index=False)
    sheet_url = getattr(config, "LEDGER_SHEET_URL", "") or DEFAULT_LEDGER_SHEET_URL
    if sheet_url:
        ok = write_gsheet_worksheet(sheet_url, "Ledger", save_df)
        if not ok:
            write_gsheet_worksheet(sheet_url, 0, save_df)


def save_edited_ledger(edited_df: pd.DataFrame, is_officer: bool = False) -> bool:
    """
    Update ledger from in-table st.data_editor edits.
    Updates the master ledger dataset using the Row index.
    """
    try:
        full_df = load_ledger(season=None, is_officer=is_officer).copy()
        
        for _, row in edited_df.iterrows():
            if "Row" not in row or pd.isna(row["Row"]):
                continue
            idx = int(row["Row"])
            if 0 <= idx < len(full_df):
                if "Date" in row and pd.notna(row["Date"]):
                    full_df.at[idx, "Date"] = str(row["Date"]).strip()
                if "Entity" in row and pd.notna(row["Entity"]):
                    full_df.at[idx, "Entity"] = str(row["Entity"]).strip()
                if "Type" in row and pd.notna(row["Type"]):
                    full_df.at[idx, "Type"] = str(row["Type"]).strip()
                if "Category" in row and pd.notna(row["Category"]):
                    full_df.at[idx, "Category"] = str(row["Category"]).strip()
                if "Amount" in row and pd.notna(row["Amount"]):
                    amt_val = row["Amount"]
                    if isinstance(amt_val, str):
                        amt_val = float(amt_val.replace("$", "").replace(",", "").strip())
                    full_df.at[idx, "Amount"] = float(amt_val)
                if "Notes" in row:
                    full_df.at[idx, "Notes"] = str(row["Notes"]).strip() if pd.notna(row["Notes"]) else ""
                if "Season" in row and pd.notna(row["Season"]):
                    full_df.at[idx, "Season"] = str(row["Season"]).strip()
                if "LoggedBy" in row:
                    full_df.at[idx, "LoggedBy"] = str(row["LoggedBy"]).strip() if pd.notna(row["LoggedBy"]) else ""

        save_ledger(full_df, is_officer=is_officer)
        return True
    except Exception as e:
        print(f"Error saving edited ledger: {e}")
        return False


def add_transaction(date_str: str, entity: str, amount: float, category: str, notes: str, trans_type: str, season: str = CURRENT_SEASON, is_officer: bool = False, logged_by: str = "") -> bool:
    """Append a new transaction to the ledger with designated season."""
    try:
        df = load_ledger(season=None, is_officer=is_officer)
        new_tx = {
            "Date": date_str,
            "Entity": entity.strip(),
            "Amount": float(amount),
            "Category": category,
            "Notes": notes.strip(),
            "Type": trans_type,
            "Season": season,
            "LoggedBy": logged_by.strip()
        }
        new_row = pd.DataFrame([new_tx])
        df = pd.concat([new_row, df], ignore_index=True)
        save_ledger(df, is_officer=is_officer)
        if is_officer and LEDGER_WEBHOOK_URL:
            trigger_ledger_webhook("add", new_tx)
        return True
    except Exception as e:
        print(f"Error adding transaction: {e}")
        return False


def delete_transaction(index: int, is_officer: bool = False) -> bool:
    """Delete a transaction by index."""
    try:
        df = load_ledger(season=None, is_officer=is_officer)
        if 0 <= index < len(df):
            df = df.drop(df.index[index]).reset_index(drop=True)
            save_ledger(df, is_officer=is_officer)
            return True
        return False
    except Exception as e:
        print(f"Error deleting transaction: {e}")
        return False



# --- MEMBER OPERATIONS (EDITABLE IN-TABLE CHECKBOXES & NOTES) ---

def _is_truthy(val) -> bool:
    """Safely check boolean truthiness across bool, float, int, and string representations."""
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if isinstance(val, (int, float, np.integer, np.floating)):
        return not np.isnan(val) and val != 0
    s = str(val).strip().lower()
    return s in ["true", "1", "1.0", "yes", "y", "t"]


def reconcile_member_trips_attended(df: pd.DataFrame, is_officer: bool = False) -> tuple[pd.DataFrame, bool]:
    """
    Reconciles members' TripsAttended with actual records from trip_signups.csv and trips.csv.
    Ensures that any member signed up for a trip or listed in a trip roster has that trip
    logged in TripsAttended for their corresponding season, while filtering out cross-season mismatches,
    removing any trips that have been deleted, and removing any tracked trips the member is no longer registered for.
    Also purges any orphaned signups in trip_signups.csv whose trip was deleted.
    """
    try:
        if df.empty or "Name" not in df.columns:
            return df, False

        trips_path = get_trips_file(is_officer)
        signups_path = get_trip_signups_file(is_officer)
        trips_df = pd.read_csv(trips_path) if os.path.exists(trips_path) else pd.DataFrame()
        signups_df = pd.read_csv(signups_path) if os.path.exists(signups_path) else pd.DataFrame()

        # 1. Clean up orphaned signups from deleted trips in signups_df
        valid_trip_ids: set[str] = set()
        valid_trip_names_lower: set[str] = set()
        if not trips_df.empty:
            if "TripID" in trips_df.columns:
                valid_trip_ids = {str(x).strip() for x in trips_df["TripID"].dropna() if str(x).strip() and str(x).strip().lower() not in ["nan", "none", "0.0", "0"]}
            if "Name" in trips_df.columns:
                valid_trip_names_lower = {str(x).strip().lower() for x in trips_df["Name"].dropna() if str(x).strip() and str(x).strip().lower() not in ["nan", "none", "0.0", "0"]}

        if not signups_df.empty and (valid_trip_ids or valid_trip_names_lower):
            s_tid = signups_df["TripID"].astype(str).str.strip() if "TripID" in signups_df.columns else pd.Series([""] * len(signups_df))
            s_tname = signups_df["TripName"].astype(str).str.strip().str.lower() if "TripName" in signups_df.columns else pd.Series([""] * len(signups_df))
            is_valid_signup = s_tid.isin(valid_trip_ids) | s_tname.isin(valid_trip_names_lower)
            if not is_valid_signup.all():
                signups_df = signups_df[is_valid_signup].copy().reset_index(drop=True)
                save_trip_signups(signups_df, is_officer=is_officer)

        # 2. Build authoritative trip metadata and attendee roster mapping
        trip_name_to_season: dict[str, str] = {}
        trip_canonical_names: dict[str, str] = {}
        trip_tracked_attendees: dict[str, set[str]] = {}
        seasons_with_trips: set[str] = set()

        if not trips_df.empty and "Name" in trips_df.columns:
            for _, t_row in trips_df.iterrows():
                t_name = str(t_row.get("Name", "")).strip()
                t_s = str(t_row.get("Season", "")).strip()
                if t_name and t_name.lower() not in ["nan", "none", "0.0", "0"]:
                    t_lower = t_name.lower()
                    trip_canonical_names[t_lower] = t_name
                    if t_s and t_s.lower() not in ["nan", "none"]:
                        trip_name_to_season[t_lower] = t_s
                        seasons_with_trips.add(t_s)
                    if t_lower not in trip_tracked_attendees:
                        trip_tracked_attendees[t_lower] = set()

                    roster_raw = str(t_row.get("AttendeeRoster", "")).strip()
                    if roster_raw and roster_raw.lower() not in ["nan", "none", "0.0", "0"]:
                        names = {n.strip().lower() for n in roster_raw.split(",") if n.strip() and n.strip().lower() not in ["nan", "none", "0.0", "0"]}
                        trip_tracked_attendees[t_lower].update(names)

        if not signups_df.empty and "TripName" in signups_df.columns:
            for _, s_row in signups_df.iterrows():
                t_name = str(s_row.get("TripName", "")).strip()
                t_s = str(s_row.get("Season", "")).strip()
                m_s_name = str(s_row.get("Name", "")).strip().lower()
                if t_name and t_name.lower() not in ["nan", "none", "0.0", "0"]:
                    t_lower = t_name.lower()
                    if t_lower not in trip_canonical_names:
                        trip_canonical_names[t_lower] = t_name
                    if t_s and t_s.lower() not in ["nan", "none"] and t_lower not in trip_name_to_season:
                        trip_name_to_season[t_lower] = t_s
                    if t_lower not in trip_tracked_attendees:
                        trip_tracked_attendees[t_lower] = set()
                    if m_s_name and m_s_name not in ["nan", "none", "0.0", "0"]:
                        trip_tracked_attendees[t_lower].add(m_s_name)

        changed = False

        # 3. Reconcile each member's TripsAttended against active trips and rosters
        for idx, row in df.iterrows():
            m_name = str(row.get("Name", "")).strip().lower()
            if not m_name or m_name in ["nan", "none"]:
                continue
            m_season = str(row.get("Season", "")).strip()
            curr_raw = str(row.get("TripsAttended", "")).strip()
            if curr_raw.lower() in ["nan", "none", "0.0", "0"]:
                curr_raw = ""

            existing_trips = []
            if curr_raw:
                for t in curr_raw.split(","):
                    t_str = t.strip()
                    if not t_str or t_str.lower() in ["nan", "none", "0.0", "0"]:
                        continue
                    t_lower = t_str.lower()

                    # Exclude trip if it's known to belong to a different season
                    t_known_season = trip_name_to_season.get(t_lower)
                    if t_known_season and m_season and t_known_season != m_season:
                        continue

                    # If this member's season actively tracks trips in trips.csv:
                    if m_season in seasons_with_trips:
                        # If the trip is not in trips.csv, it has been DELETED -> remove it!
                        if t_lower not in trip_canonical_names:
                            continue
                        # If the trip exists in trips.csv, verify member is actually on its roster/signups
                        if m_name not in trip_tracked_attendees.get(t_lower, set()):
                            continue
                    else:
                        # Historical season with no records in trips.csv:
                        # If trip is actively tracked somewhere, ensure member is on it
                        if t_lower in trip_tracked_attendees:
                            if m_name not in trip_tracked_attendees[t_lower]:
                                continue

                    canonical_val = trip_canonical_names.get(t_lower, t_str)
                    if not any(x.lower() == t_lower for x in existing_trips):
                        existing_trips.append(canonical_val)

            # Add any trips for this member's season where the member is listed as an attendee
            for t_lower, attendees in trip_tracked_attendees.items():
                if m_name in attendees:
                    t_s = trip_name_to_season.get(t_lower, "")
                    if not t_s or not m_season or t_s == m_season or m_season == "All Seasons":
                        canonical_val = trip_canonical_names.get(t_lower, t_lower.title())
                        if not any(x.lower() == t_lower for x in existing_trips):
                            existing_trips.append(canonical_val)

            new_val = ", ".join(existing_trips)
            if new_val != curr_raw:
                df.at[idx, "TripsAttended"] = new_val
                changed = True

        return df, changed
    except Exception as e:
        print(f"Error reconciling trips attended: {e}")
        return df, False


def load_members(season: str = None, is_officer: bool = False) -> pd.DataFrame:
    """Load members directory, optionally filtered by season."""
    ensure_data_initialized()
    if not is_officer:
        if os.path.exists(DEMO_MEMBERS_FILE):
            df = pd.read_csv(DEMO_MEMBERS_FILE)
        else:
            df = pd.DataFrame(columns=[
                "MemberID", "Season", "Name", "Email", "Phone", "Year", "SkiBoard",
                "DuesPaid", "Slack", "TShirtSize", "CompTeam", "TripsAttended", "Notes"
            ])
    else:
        sheet_url = getattr(config, "MEMBERS_SHEET_URL", "") or DEFAULT_MEMBERSHIP_FORM_SHEET_URL
        df = None
        if sheet_url:
            gs_df = read_gsheet_worksheet(sheet_url, "Members", ttl=60)
            if gs_df is not None and not gs_df.empty and "Name" in gs_df.columns:
                gs_df = purge_demo_members_from_df(gs_df)
                try:
                    gs_df.to_csv(MEMBERS_FILE, index=False)
                except Exception:
                    pass
                df = gs_df

        if df is None or df.empty:
            if os.path.exists(MEMBERS_FILE):
                df = pd.read_csv(MEMBERS_FILE)
            else:
                df = pd.DataFrame(columns=[
                    "MemberID", "Season", "Name", "Email", "Phone", "Year", "SkiBoard",
                    "DuesPaid", "Slack", "TShirtSize", "CompTeam", "TripsAttended", "Notes"
                ])
        df = purge_demo_members_from_df(df)

    try:
        if "Season" not in df.columns:
            df["Season"] = "2025-2026"
        if "DuesPaid" not in df.columns:
            df["DuesPaid"] = False
        if "Slack" not in df.columns:
            df["Slack"] = False
        if "Year" not in df.columns:
            df["Year"] = ""
        if "SkiBoard" not in df.columns:
            df["SkiBoard"] = ""
        if "TShirtSize" not in df.columns:
            df["TShirtSize"] = "None"
        if "Notes" not in df.columns:
            df["Notes"] = ""
        if "TripsAttended" not in df.columns:
            df["TripsAttended"] = ""
        if "PassType" in df.columns:
            df = df.drop(columns=["PassType"])

        df["DuesPaid"] = df["DuesPaid"].fillna(False).astype(bool)
        df["Slack"] = df["Slack"].fillna(False).astype(bool)
        df["CompTeam"] = df["CompTeam"].fillna(False).astype(bool)
        def _clean_yr(y):
            s = str(y).strip()
            if not s or s.lower() in ["nan", "none", "null"]:
                return ""
            try:
                f = float(s)
                if f.is_integer():
                    return str(int(f))
            except Exception:
                pass
            return s

        df["Year"] = df["Year"].apply(_clean_yr)
        df["SkiBoard"] = df["SkiBoard"].fillna("").astype(str).replace({"nan": "", "None": "", "NaN": ""})
        df["TShirtSize"] = df["TShirtSize"].fillna("None").astype(str)
        df["Notes"] = df["Notes"].fillna("").astype(str)
        df["TripsAttended"] = df["TripsAttended"].fillna("").astype(str).replace({"nan": "", "None": "", "NaN": ""})

        # Automatically reconcile TripsAttended against trip_signups.csv and trips.csv
        df, changed = reconcile_member_trips_attended(df, is_officer=is_officer)
        if changed:
            save_members(df, is_officer=is_officer)

        if season and season != "All Seasons":
            return df[df["Season"] == season].copy().reset_index(drop=True)
        return df
    except Exception as e:
        print(f"Error loading members: {e}")
        return pd.DataFrame(columns=[
            "MemberID", "Season", "Name", "Email", "Phone", "Year", "SkiBoard",
            "DuesPaid", "Slack", "TShirtSize", "CompTeam", "TripsAttended", "Notes"
        ])


def save_members(df: pd.DataFrame, is_officer: bool = False):
    """Save members directory to CSV and Google Sheets."""
    if "PassType" in df.columns:
        df = df.drop(columns=["PassType"])
    if not is_officer:
        df.to_csv(DEMO_MEMBERS_FILE, index=False)
        return

    clean_df = purge_demo_members_from_df(df)
    clean_df.to_csv(MEMBERS_FILE, index=False)
    sheet_url = getattr(config, "MEMBERS_SHEET_URL", "") or DEFAULT_MEMBERSHIP_FORM_SHEET_URL
    if sheet_url:
        write_gsheet_worksheet(sheet_url, "Members", clean_df)


def record_dues_payment_in_ledger(member_name: str, season: str = CURRENT_SEASON, notes: str = None, is_officer: bool = False) -> bool:
    """
    Log an entry in the ledger under member_name for $60.00 Income, Membership category.
    Avoids duplicate entries for the same member within the same season.
    """
    try:
        clean_name = str(member_name).strip().title()
        if not clean_name or clean_name.lower() == "nan":
            return False

        df_ledger = load_ledger(season=None, is_officer=is_officer)

        # Check if already logged for this season to avoid duplicate entries
        existing = df_ledger[
            (df_ledger["Entity"].astype(str).str.lower().str.strip() == clean_name.lower()) &
            (df_ledger["Category"].isin(["Membership", "Membership Dues"])) &
            (df_ledger["Season"] == season) &
            (df_ledger["Type"] == "Income")
        ]
        if not existing.empty:
            return True

        note_text = notes.strip() if notes else f"Membership dues payment - {season}"
        return add_transaction(
            date_str=date.today().strftime("%m-%d-%Y"),
            entity=clean_name,
            amount=60.00,
            category="Membership",
            notes=note_text,
            trans_type="Income",
            season=season,
            is_officer=is_officer
        )
    except Exception as e:
        print(f"Error recording dues payment in ledger: {e}")
        return False


def remove_dues_payment_from_ledger(member_name: str, season: str = CURRENT_SEASON, is_officer: bool = False) -> bool:
    """
    Remove the dues payment entry ($60 Income, Membership/Membership Dues) from the ledger
    for member_name in the specified season when dues paid status is revoked.
    """
    try:
        clean_name = str(member_name).strip().lower()
        if not clean_name or clean_name == "nan":
            return False

        df_ledger = load_ledger(season=None, is_officer=is_officer)
        if df_ledger.empty:
            return False

        # Match entity by member name, category in Membership/Membership Dues, Type Income, and Season
        matches = df_ledger[
            (df_ledger["Entity"].astype(str).str.lower().str.strip() == clean_name) &
            (df_ledger["Category"].isin(["Membership", "Membership Dues"])) &
            (df_ledger["Type"] == "Income") &
            (df_ledger["Season"] == season)
        ]

        if matches.empty and (not season or season == "All Seasons"):
            matches = df_ledger[
                (df_ledger["Entity"].astype(str).str.lower().str.strip() == clean_name) &
                (df_ledger["Category"].isin(["Membership", "Membership Dues"])) &
                (df_ledger["Type"] == "Income")
            ]

        if not matches.empty:
            df_ledger = df_ledger.drop(matches.index).reset_index(drop=True)
            save_ledger(df_ledger, is_officer=is_officer)
            return True
        return False
    except Exception as e:
        print(f"Error removing dues payment from ledger: {e}")
        return False


def save_edited_members(edited_df: pd.DataFrame, current_view_season: str = None, is_officer: bool = False) -> bool:
    """
    Update members from in-table st.data_editor edits.
    Merges updated rows back into the main members dataset by MemberID.
    Automatically logs a $60 Membership Income entry in the ledger when DuesPaid is checked,
    and removes the corresponding ledger entry when DuesPaid is unchecked (revoked).
    """
    try:
        full_df = load_members(season=None, is_officer=is_officer)
        col_rename_back = {
            "ID": "MemberID",
            "Season": "Season",
            "Name": "Name",
            "Email": "Email",
            "Phone": "Phone",
            "Year": "Year",
            "Ski/Board": "SkiBoard",
            "SkiBoard": "SkiBoard",
            "Dues Paid": "DuesPaid",
            "Slack": "Slack",
            "T-Shirt Size": "TShirtSize",
            "Comp Team": "CompTeam",
            "Trips Attended": "TripsAttended",
            "Notes": "Notes"
        }
        df_to_merge = edited_df.rename(columns=col_rename_back).copy()
        if "MemberID" in df_to_merge.columns:
            df_to_merge = df_to_merge.drop_duplicates(subset=["MemberID"], keep="last")

        full_df.set_index("MemberID", inplace=True)
        df_to_merge.set_index("MemberID", inplace=True)

        def _to_bool(val) -> bool:
            if isinstance(val, (bool, np.bool_)):
                return bool(val)
            if isinstance(val, (int, np.integer, float, np.floating)):
                return val != 0 and not np.isnan(val)
            s = str(val).strip().lower()
            return s in ["true", "1", "yes", "y", "t"]

        # Detect newly checked or unchecked Dues Paid boxes, and trip roster updates
        for mid, row in df_to_merge.iterrows():
            if mid in full_df.index:
                was_paid = _is_truthy(full_df.loc[mid, "DuesPaid"]) if "DuesPaid" in full_df.columns else False
                now_paid = _is_truthy(row.get("DuesPaid", False))
                athlete_name = str(row.get("Name", full_df.loc[mid, "Name"])).strip().title()
                athlete_season = str(row.get("Season", full_df.loc[mid, "Season"])).strip()
                if not was_paid and now_paid:
                    record_dues_payment_in_ledger(athlete_name, season=athlete_season, is_officer=is_officer)
                elif was_paid and not now_paid:
                    remove_dues_payment_from_ledger(athlete_name, season=athlete_season, is_officer=is_officer)

                # Detect changes in Trips Attended
                if "TripsAttended" in row:
                    old_raw = str(full_df.loc[mid, "TripsAttended"]) if "TripsAttended" in full_df.columns and pd.notnull(full_df.loc[mid, "TripsAttended"]) else ""
                    new_raw = str(row["TripsAttended"]) if pd.notnull(row["TripsAttended"]) else ""
                    if old_raw.lower() in ["nan", "none", "0.0", "0"]:
                        old_raw = ""
                    if new_raw.lower() in ["nan", "none", "0.0", "0"]:
                        new_raw = ""
                    old_trips = {t.strip() for t in old_raw.split(",") if t.strip() and t.strip().lower() not in ["nan", "none", "0.0", "0"]}
                    new_trips = {t.strip() for t in new_raw.split(",") if t.strip() and t.strip().lower() not in ["nan", "none", "0.0", "0"]}
                    removed_trips = {t for t in old_trips if not any(x.lower() == t.lower() for x in new_trips)}
                    added_trips = {t for t in new_trips if not any(x.lower() == t.lower() for x in old_trips)}
                    for rem_t in removed_trips:
                        remove_trip_from_member_roster_and_signups(athlete_name, rem_t, season=athlete_season, is_officer=is_officer)
                    for add_t in added_trips:
                        add_trip_to_member_roster(athlete_name, add_t, season=athlete_season, is_officer=is_officer)

        for col in ["Name", "Email", "Phone", "Year", "SkiBoard", "DuesPaid", "Slack", "TShirtSize", "CompTeam", "TripsAttended", "Notes"]:
            if col in df_to_merge.columns:
                if col == "Phone":
                    df_to_merge["Phone"] = df_to_merge["Phone"].apply(format_phone_number)
                full_df.update(df_to_merge[[col]])

        full_df.reset_index(inplace=True)
        save_members(full_df, is_officer=is_officer)
        return True
    except Exception as e:
        print(f"Error saving edited members: {e}")
        return False


def add_member(name: str, email: str, phone: str, dues_paid: bool, tshirt_size: str,
               comp_team: bool, notes: str = "", season: str = CURRENT_SEASON,
               year: str = "", ski_board: str = "", slack: bool = False, is_officer: bool = False) -> bool:
    """Add a new member to the roster for the given season."""
    try:
        all_df = load_members(season=None, is_officer=is_officer)
        new_id = generate_next_member_id(all_df, season=season)

        new_member = pd.DataFrame([{
            "MemberID": new_id,
            "Season": season,
            "Name": name.strip(),
            "Email": email.strip(),
            "Phone": format_phone_number(phone),
            "Year": str(year).strip(),
            "SkiBoard": str(ski_board).strip(),
            "DuesPaid": bool(dues_paid),
            "Slack": bool(slack),
            "TShirtSize": str(tshirt_size).strip(),
            "CompTeam": bool(comp_team),
            "TripsAttended": "",
            "Notes": notes.strip()
        }])
        all_df = pd.concat([all_df, new_member], ignore_index=True)
        save_members(all_df, is_officer=is_officer)

        # Log dues payment to ledger if marked paid
        if dues_paid:
            record_dues_payment_in_ledger(name.strip(), season=season, is_officer=is_officer)

        return True
    except Exception as e:
        print(f"Error adding member: {e}")
        return False


def delete_member(member_id: str, is_officer: bool = False) -> bool:
    """
    Delete a single member from the database by MemberID.
    Cleans up associated dues payments from the ledger and any trip signups.
    """
    return delete_multiple_members([member_id], is_officer=is_officer) > 0


def delete_multiple_members(member_ids: list[str], is_officer: bool = False) -> int:
    """
    Delete multiple members from the database by their MemberIDs.
    Cleans up associated dues payments from the ledger and any trip signups.
    Returns the count of removed members.
    """
    try:
        if not member_ids:
            return 0
        clean_ids = [str(mid).strip() for mid in member_ids if str(mid).strip()]
        if not clean_ids:
            return 0

        all_members = load_members(season=None, is_officer=is_officer)
        if all_members.empty:
            return 0

        match_rows = all_members[all_members["MemberID"].isin(clean_ids)]
        if match_rows.empty:
            return 0

        all_signups = load_trip_signups(season=None, is_officer=is_officer)

        # For each deleted member:
        for _, m_row in match_rows.iterrows():
            name = str(m_row.get("Name", "")).strip()
            season = str(m_row.get("Season", "")).strip()
            was_paid = bool(m_row.get("DuesPaid", False))
            if name:
                # Remove dues payment from ledger if dues were marked paid
                if was_paid:
                    remove_dues_payment_from_ledger(name, season=season, is_officer=is_officer)

                # Clean up any trip signups for this member in that season
                if not all_signups.empty:
                    m_signups = all_signups[
                        (all_signups["Name"].astype(str).str.lower().str.strip() == name.lower()) &
                        (all_signups["Season"] == season)
                    ]
                    if not m_signups.empty:
                        delete_multiple_trip_attendees(m_signups["SignupID"].tolist(), is_officer=is_officer)

        # Drop the deleted members from members.csv
        remaining_members = all_members[~all_members["MemberID"].isin(clean_ids)].copy().reset_index(drop=True)
        save_members(remaining_members, is_officer=is_officer)
        return len(match_rows)
    except Exception as e:
        print(f"Error deleting members: {e}")
        return 0


def reset_active_season_roster(new_season_name: str, is_officer: bool = False) -> tuple[bool, str]:
    """Start a new season across the dashboard without deleting previous data."""
    try:
        df_m = load_members(season=None, is_officer=is_officer)
        save_members(df_m, is_officer=is_officer)
        return True, f"Active season is now '{new_season_name}'. All previous records preserved."
    except Exception as e:
        return False, str(e)


def add_trip_to_member_history(member_name: str, trip_name: str, season: str = None, is_officer: bool = False) -> bool:
    """
    Append trip_name to member's TripsAttended field in members.csv.
    Ensures no duplicates and preserves previous trips.
    """
    try:
        if not member_name or not trip_name:
            return False
        df = load_members(season=None, is_officer=is_officer)
        clean_name = member_name.strip().lower()
        clean_trip = trip_name.strip()

        # Match member by name and optionally season
        target_season = season if season and season != "All Seasons" else CURRENT_SEASON
        mask = df["Name"].astype(str).str.lower().str.strip() == clean_name
        season_mask = mask & (df["Season"] == target_season)
        if season_mask.any():
            mask = season_mask

        indices = df[mask].index
        if len(indices) == 0:
            return False

        updated = False
        for idx in indices:
            curr_trips_raw = str(df.loc[idx, "TripsAttended"]) if pd.notnull(df.loc[idx, "TripsAttended"]) else ""
            if curr_trips_raw.lower() in ["nan", "none"]:
                curr_trips_raw = ""
            
            trip_list = [t.strip() for t in curr_trips_raw.split(",") if t.strip()]
            if not any(t.lower() == clean_trip.lower() for t in trip_list):
                trip_list.append(clean_trip)
                df.loc[idx, "TripsAttended"] = ", ".join(trip_list)
                updated = True

        if updated:
            save_members(df, is_officer=is_officer)
        return True
    except Exception as e:
        print(f"Error adding trip to member history: {e}")
        return False


def remove_trip_from_member_history(member_name: str, trip_name: str, season: str = None, is_officer: bool = False) -> bool:
    """
    Remove trip_name from member's TripsAttended field in members.csv.
    """
    try:
        if not member_name or not trip_name:
            return False
        df = load_members(season=None, is_officer=is_officer)
        clean_name = member_name.strip().lower()
        clean_trip = trip_name.strip().lower()

        mask = df["Name"].astype(str).str.lower().str.strip() == clean_name
        if season and season != "All Seasons":
            season_mask = mask & (df["Season"] == season)
            if season_mask.any():
                mask = season_mask

        indices = df[mask].index
        if len(indices) == 0:
            return False

        updated = False
        for idx in indices:
            curr_trips_raw = str(df.loc[idx, "TripsAttended"]) if pd.notnull(df.loc[idx, "TripsAttended"]) else ""
            if curr_trips_raw.lower() in ["nan", "none"]:
                curr_trips_raw = ""
            
            trip_list = [t.strip() for t in curr_trips_raw.split(",") if t.strip()]
            new_list = [t for t in trip_list if t.lower() != clean_trip]
            if len(new_list) != len(trip_list):
                df.loc[idx, "TripsAttended"] = ", ".join(new_list)
                updated = True

        if updated:
            save_members(df, is_officer=is_officer)
        return True
    except Exception as e:
        print(f"Error removing trip from member history: {e}")
        return False


def remove_trip_from_member_roster_and_signups(athlete_name: str, trip_name: str, season: str = None, is_officer: bool = False) -> bool:
    """
    Remove athlete from a trip's AttendeeRoster in trips.csv and from trip_signups.csv,
    and remove ledger trip payment if was recorded.
    """
    try:
        clean_name = athlete_name.strip()
        clean_trip = trip_name.strip()
        if not clean_name or not clean_trip:
            return False

        # 1. Remove from trip_signups.csv
        all_signups = load_trip_signups(season=None, is_officer=is_officer)
        if not all_signups.empty:
            s_mask = (all_signups["Name"].astype(str).str.lower().str.strip() == clean_name.lower()) & \
                     (all_signups["TripName"].astype(str).str.lower().str.strip() == clean_trip.lower())
            if season and season != "All Seasons":
                s_mask = s_mask & (all_signups["Season"] == season)
            match_rows = all_signups[s_mask]
            if not match_rows.empty:
                for _, row in match_rows.iterrows():
                    was_paid = _is_truthy(row.get("PaymentReceived", False))
                    s_season = str(row.get("Season", season or CURRENT_SEASON)).strip()
                    if was_paid:
                        remove_trip_payment_from_ledger(clean_name, clean_trip, s_season, is_officer=is_officer)
                remaining_signups = all_signups[~s_mask].copy().reset_index(drop=True)
                save_trip_signups(remaining_signups, is_officer=is_officer)

        # 2. Remove from trips.csv AttendeeRoster
        trips_df = load_trips(season=None, is_officer=is_officer)
        if not trips_df.empty and "AttendeeRoster" in trips_df.columns:
            t_mask = trips_df["Name"].astype(str).str.lower().str.strip() == clean_trip.lower()
            if season and season != "All Seasons" and "Season" in trips_df.columns:
                t_mask = t_mask & (trips_df["Season"] == season)
            match_t_indices = trips_df[t_mask].index
            trips_changed = False
            for t_idx in match_t_indices:
                curr_roster = str(trips_df.loc[t_idx, "AttendeeRoster"]).strip()
                if curr_roster and curr_roster.lower() not in ["nan", "none", "0.0", "0"]:
                    r_names = [n.strip() for n in curr_roster.split(",") if n.strip() and n.strip().lower() not in ["nan", "none", "0.0", "0"]]
                    new_r = [n for n in r_names if n.lower() != clean_name.lower()]
                    if len(new_r) != len(r_names):
                        trips_df.at[t_idx, "AttendeeRoster"] = ", ".join(new_r)
                        if "Attendees" in trips_df.columns:
                            try:
                                trips_df.at[t_idx, "Attendees"] = max(0, len(new_r))
                            except Exception:
                                pass
                        trips_changed = True
            if trips_changed:
                save_trips(trips_df, is_officer=is_officer)

        return True
    except Exception as e:
        print(f"Error removing trip from member roster: {e}")
        return False


def add_trip_to_member_roster(athlete_name: str, trip_name: str, season: str = None, is_officer: bool = False) -> bool:
    """
    Add athlete to a trip's AttendeeRoster in trips.csv if trip exists.
    """
    try:
        clean_name = athlete_name.strip()
        clean_trip = trip_name.strip()
        if not clean_name or not clean_trip:
            return False

        trips_df = load_trips(season=None, is_officer=is_officer)
        if not trips_df.empty and "AttendeeRoster" in trips_df.columns:
            t_mask = trips_df["Name"].astype(str).str.lower().str.strip() == clean_trip.lower()
            if season and season != "All Seasons" and "Season" in trips_df.columns:
                t_mask = t_mask & (trips_df["Season"] == season)
            match_t_indices = trips_df[t_mask].index
            trips_changed = False
            for t_idx in match_t_indices:
                curr_roster = str(trips_df.loc[t_idx, "AttendeeRoster"]).strip()
                if curr_roster.lower() in ["nan", "none", "0.0", "0"]:
                    curr_roster = ""
                r_names = [n.strip() for n in curr_roster.split(",") if n.strip() and n.strip().lower() not in ["nan", "none", "0.0", "0"]]
                if not any(n.lower() == clean_name.lower() for n in r_names):
                    r_names.append(clean_name.title())
                    trips_df.at[t_idx, "AttendeeRoster"] = ", ".join(r_names)
                    if "Attendees" in trips_df.columns:
                        try:
                            trips_df.at[t_idx, "Attendees"] = max(len(r_names), int(trips_df.loc[t_idx, "Attendees"]))
                        except Exception:
                            pass
                    trips_changed = True
            if trips_changed:
                save_trips(trips_df, is_officer=is_officer)
        return True
    except Exception as e:
        print(f"Error adding trip to member roster: {e}")
        return False


def sync_all_members_trips_attended(is_officer: bool = False) -> int:
    """
    Synchronize all trip sign-ups from trip_signups.csv with members' TripsAttended field.
    Returns the count of signups synchronized.
    """
    try:
        signups_df = load_trip_signups(season=None, is_officer=is_officer)
        if signups_df.empty:
            return 0
        
        count = 0
        for _, s_row in signups_df.iterrows():
            name = str(s_row.get("Name", "")).strip()
            trip_name = str(s_row.get("TripName", "")).strip()
            season = str(s_row.get("Season", "")).strip()
            if name and trip_name:
                if add_trip_to_member_history(name, trip_name, season, is_officer=is_officer):
                    count += 1
        return count
    except Exception as e:
        print(f"Error syncing member trips attended: {e}")
        return 0


# --- GOOGLE FORM PARSING & LIVE SYNC (LINKED WITH QUESTIONS/CONCERNS) ---

def parse_and_sync_google_form_df(df_form: pd.DataFrame, target_season: str = CURRENT_SEASON, is_officer: bool = False) -> tuple[bool, str, int]:
    """
    Intelligently map Google Form column headers and sync entries into the roster.
    Correctly maps 'Questions or concerns for us?' column to Notes, updates existing members,
    and detects Dues Paid and T-Shirt Size.
    """
    try:
        all_members = load_members(season=None, is_officer=is_officer)
        all_members = purge_demo_members_from_df(all_members)
        existing_in_season = all_members[all_members["Season"] == target_season].copy()
        
        col_map = {}
        for col in df_form.columns:
            c_low = col.lower().strip()
            if "email" in c_low and "email" not in col_map:
                col_map["email"] = col
            elif ("name" in c_low or "first and last" in c_low) and "name" not in col_map:
                col_map["name"] = col
            elif ("phone" in c_low or "cell" in c_low or "number" in c_low) and "phone" not in col_map:
                col_map["phone"] = col
            elif ("dues" in c_low or "paid" in c_low or "payment" in c_low) and "dues" not in col_map:
                col_map["dues"] = col
            elif ("shirt" in c_low or "size" in c_low or "swag" in c_low) and "shirt" not in col_map:
                col_map["shirt"] = col
            elif any(k in c_low for k in ["what year", "year are you", "academic year", "class standing"]) and "year" not in col_map:
                col_map["year"] = col
            elif any(k in c_low for k in ["ski or board", "ski/board", "do you ski"]) and "ski_board" not in col_map:
                col_map["ski_board"] = col
            elif ("ski" in c_low and "board" in c_low) and "ski_board" not in col_map:
                col_map["ski_board"] = col
            # Match Questions or concerns for us?
            elif any(k in c_low for k in ["question", "concern", "note", "comment", "diet", "anything"]) and "notes" not in col_map:
                col_map["notes"] = col

        # Fallback for year if not matched
        if "year" not in col_map:
            for col in df_form.columns:
                c_low = col.lower().strip()
                if "year" in c_low and "notes" not in c_low and "email" not in c_low:
                    col_map["year"] = col
                    break

        # If notes column wasn't explicitly caught by keyword, the user confirmed the final field is the questions/concerns column
        if "notes" not in col_map and len(df_form.columns) > 0:
            col_map["notes"] = df_form.columns[-1]

        if "name" not in col_map and len(df_form.columns) > 1:
            col_map["name"] = df_form.columns[1]

        added_count = 0
        updated_count = 0

        for _, row in df_form.iterrows():
            name_val = str(row.get(col_map.get("name", ""), "")).strip()
            email_val = str(row.get(col_map.get("email", ""), "")).strip()
            phone_val = str(row.get(col_map.get("phone", ""), "")).strip()
            
            # Extract year
            raw_year = str(row.get(col_map.get("year", ""), "")).strip()
            clean_year = "" if raw_year.lower() in ["nan", "none", "null"] else raw_year
            try:
                f_yr = float(clean_year)
                if f_yr.is_integer():
                    clean_year = str(int(f_yr))
            except Exception:
                pass

            # Extract ski / board
            raw_skiboard = str(row.get(col_map.get("ski_board", ""), "")).strip()
            clean_skiboard = "" if raw_skiboard.lower() in ["nan", "none", "null"] else raw_skiboard
            if clean_skiboard.lower() in ["ski", "board", "both"]:
                clean_skiboard = clean_skiboard.capitalize()

            # Extract notes from 'Questions or concerns for us?' (or final column)
            raw_notes = str(row.get(col_map.get("notes", ""), "")).strip()
            clean_notes = "" if raw_notes.lower() in ["nan", "none", "null"] else raw_notes
            clean_notes = clean_notes.replace("\ufffd", "'").replace("’", "'").replace("‘", "'").replace("`", "'")

            if not name_val or name_val.lower() == "nan":
                continue

            # Checkbox: Dues Paid boolean
            dues_val = str(row.get(col_map.get("dues", ""), "")).lower()
            dues_paid = True if any(w in dues_val for w in ["yes", "paid", "done", "venmo", "zelle", "true"]) else False

            # Dropdown: T-Shirt Size
            shirt_val = str(row.get(col_map.get("shirt", ""), "")).strip().upper()
            tshirt_size = "None"
            for sz in ["XL", "L", "M", "S"]:
                if sz in shirt_val:
                    tshirt_size = sz
                    break

            # Check if athlete already exists in this season
            email_match = pd.Series(False, index=all_members.index)
            if email_val and email_val.lower() != "nan":
                email_match = (all_members["Email"].astype(str).str.lower().str.strip() == email_val.lower().strip()) & (all_members["Season"] == target_season)

            name_match = (all_members["Name"].astype(str).str.lower().str.strip() == name_val.lower().strip()) & (all_members["Season"] == target_season)
            existing_idx = all_members[email_match | name_match].index

            if len(existing_idx) > 0:
                # Update existing member's notes, year, and ski/board
                idx = existing_idx[0]
                if clean_year:
                    all_members.loc[idx, "Year"] = clean_year
                if clean_skiboard:
                    all_members.loc[idx, "SkiBoard"] = clean_skiboard
                if clean_notes:
                    all_members.loc[idx, "Notes"] = clean_notes
                if phone_val and phone_val.lower() != "nan":
                    all_members.loc[idx, "Phone"] = format_phone_number(phone_val)
                if dues_paid:
                    all_members.loc[idx, "DuesPaid"] = True
                    record_dues_payment_in_ledger(name_val.title(), season=target_season, is_officer=is_officer)
                if tshirt_size != "None":
                    all_members.loc[idx, "TShirtSize"] = tshirt_size
                updated_count += 1
            else:
                # Add new member
                added_count += 1
                m_id = generate_next_member_id(all_members, season=target_season)

                new_row = pd.DataFrame([{
                    "MemberID": m_id,
                    "Season": target_season,
                    "Name": name_val.title(),
                    "Email": email_val if email_val != "nan" else f"{name_val.lower().replace(' ', '')[:8]}@ucsb.edu",
                    "Phone": format_phone_number(phone_val) if phone_val != "nan" else "",
                    "Year": clean_year,
                    "SkiBoard": clean_skiboard,
                    "DuesPaid": dues_paid,
                    "Slack": False,
                    "TShirtSize": tshirt_size,
                    "CompTeam": False,
                    "TripsAttended": "",
                    "Notes": clean_notes
                }])
                all_members = pd.concat([all_members, new_row], ignore_index=True)
                if dues_paid:
                    record_dues_payment_in_ledger(name_val.title(), season=target_season, is_officer=is_officer)

        save_members(all_members, is_officer=is_officer)
        msg = f"Synced with Google Form: {added_count} new athlete(s) registered, {updated_count} existing record(s) updated with form questions/notes."
        return True, msg, (added_count + updated_count)

    except Exception as e:
        return False, f"Error processing Google Form data: {e}", 0


def fetch_and_sync_google_sheet(sheet_url: str, target_season: str = CURRENT_SEASON, is_officer: bool = False) -> tuple[bool, str, int]:
    """Fetch a Google Sheet via public CSV export URL and sync responses."""
    clean_url = sheet_url.strip()
    gid_match = re.search(r"gid=([0-9]+)", clean_url)
    gid_str = f"&gid={gid_match.group(1)}" if gid_match else ""
    
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", clean_url)
    if match:
        sheet_id = match.group(1)
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv{gid_str}"
    elif clean_url.startswith("http"):
        csv_url = clean_url
    else:
        csv_url = f"https://docs.google.com/spreadsheets/d/{clean_url}/export?format=csv{gid_str}"

    try:
        df_form = pd.read_csv(csv_url)
        return parse_and_sync_google_form_df(df_form, target_season, is_officer=is_officer)
    except Exception as e:
        return False, f"Could not fetch Google Sheet. Verify link sharing ('Anyone with link can view') or upload CSV. Details: {e}", 0


# --- TRIPS CREATOR & ESTIMATOR OPERATIONS ---

def load_trips(season: str = None, is_officer: bool = False) -> pd.DataFrame:
    """Load trips dataset, optionally filtered by season."""
    ensure_data_initialized()
    if not is_officer:
        if os.path.exists(DEMO_TRIPS_FILE):
            df = pd.read_csv(DEMO_TRIPS_FILE)
        else:
            df = pd.DataFrame(columns=TRIP_COLS)
    else:
        sheet_url = getattr(config, "TRIPS_EVENTS_SHEET_URL", "") or TRIPS_EVENTS_SHEET_URL
        df = None
        if sheet_url:
            gs_df = read_gsheet_worksheet(sheet_url, "Trips", ttl=60)
            if gs_df is not None and not gs_df.empty and "Name" in gs_df.columns:
                try:
                    gs_df.to_csv(TRIPS_FILE, index=False)
                except Exception:
                    pass
                df = gs_df

        if df is None or df.empty:
            if os.path.exists(TRIPS_FILE):
                df = pd.read_csv(TRIPS_FILE)
            else:
                df = pd.DataFrame(columns=TRIP_COLS)

    try:
        if "Season" not in df.columns:
            df["Season"] = "2025-2026"
        if "TripType" not in df.columns:
            df["TripType"] = "Recreational"
        if "AttendeeRoster" not in df.columns:
            df["AttendeeRoster"] = ""
        else:
            df["AttendeeRoster"] = df["AttendeeRoster"].fillna("").astype(str).replace({"nan": "", "None": "", "NaN": "", "0.0": "", "0": ""})
        if "SchoolFunding" not in df.columns:
            df["SchoolFunding"] = 0.0
        else:
            df["SchoolFunding"] = pd.to_numeric(df["SchoolFunding"], errors="coerce").fillna(0.0)
        if "NetCost" not in df.columns:
            df["NetCost"] = df["TotalCost"] if "TotalCost" in df.columns else 0.0
        else:
            df["NetCost"] = pd.to_numeric(df["NetCost"], errors="coerce").fillna(df["TotalCost"] if "TotalCost" in df.columns else 0.0)
        if "SchoolCoverageDetails" not in df.columns:
            df["SchoolCoverageDetails"] = ""
        else:
            df["SchoolCoverageDetails"] = df["SchoolCoverageDetails"].fillna("").astype(str)

        if season and season != "All Seasons":
            return df[df["Season"] == season].copy().reset_index(drop=True)
        return df
    except Exception as e:
        print(f"Error loading trips: {e}")
        return pd.DataFrame(columns=TRIP_COLS)


def save_trips(df: pd.DataFrame, is_officer: bool = False):
    """Save trips dataset to CSV and Google Sheets."""
    save_cols = [c for c in TRIP_COLS if c in df.columns]
    save_df = df[save_cols].copy() if save_cols else df.copy()
    if not is_officer:
        save_df.to_csv(DEMO_TRIPS_FILE, index=False)
        return

    save_df.to_csv(TRIPS_FILE, index=False)
    sheet_url = getattr(config, "TRIPS_EVENTS_SHEET_URL", "") or TRIPS_EVENTS_SHEET_URL
    if sheet_url:
        write_gsheet_worksheet(sheet_url, "Trips", save_df)


def add_created_trip(name: str, destination: str, trip_type: str, start_date: str, end_date: str,
                     nights: int, miles: float, attendees: int, vehicles: int, cabin: float,
                     food: float, tickets: float, gas: float, attendee_roster: list,
                     status: str = "Planning", notes: str = "", season: str = CURRENT_SEASON,
                     is_officer: bool = False, school_funding: float = 0.0, net_cost: float = None,
                     school_coverage_details: str = "") -> bool:
    """Create a new trip in the trip creator with attendee roster, school funding, and trip type."""
    try:
        df = load_trips(season=None, is_officer=is_officer)
        next_id = f"TRIP-{len(df) + 1:03d}"

        # When creating a competition trip, automatically add all members on the comp team
        actual_season = season if season and season != "All Seasons" else CURRENT_SEASON
        comp_members_to_signup = []
        if trip_type == "Competition":
            members_season_df = load_members(season=actual_season, is_officer=is_officer)
            comp_df = members_season_df[members_season_df["CompTeam"] == True]
            if comp_df.empty:
                # Check across all members if current season hasn't designated comp members yet
                all_m = load_members(season=None, is_officer=is_officer)
                comp_df = all_m[all_m["CompTeam"] == True]

            if not comp_df.empty:
                comp_names = [str(n).strip() for n in comp_df["Name"].dropna().tolist() if str(n).strip()]
                combined_roster = list(dict.fromkeys((attendee_roster or []) + comp_names))
                attendee_roster = combined_roster
                if len(attendee_roster) > attendees:
                    attendees = len(attendee_roster)
                comp_members_to_signup = comp_df.to_dict("records")

        total_cost = float(cabin + food + tickets + gas)
        funding_amt = float(school_funding) if school_funding is not None else 0.0
        final_net = float(net_cost) if net_cost is not None else max(0.0, total_cost - funding_amt)
        roster_str = ", ".join(attendee_roster) if attendee_roster else ""
        
        new_trip = pd.DataFrame([{
            "TripID": next_id,
            "Season": actual_season,
            "Name": name.strip(),
            "Destination": destination,
            "TripType": trip_type,
            "StartDate": start_date,
            "EndDate": end_date,
            "Nights": int(nights),
            "RoundTripMiles": float(miles),
            "Attendees": int(attendees),
            "Vehicles": int(vehicles),
            "CabinCost": float(cabin),
            "FoodAlcoholCost": float(food),
            "LiftTicketsCost": float(tickets),
            "GasCost": float(gas),
            "TotalCost": float(total_cost),
            "SchoolFunding": float(funding_amt),
            "NetCost": float(final_net),
            "SchoolCoverageDetails": str(school_coverage_details).strip(),
            "RevenueCollected": 0.0,
            "Status": status,
            "AttendeeRoster": roster_str,
            "Notes": notes.strip()
        }])
        df = pd.concat([df, new_trip], ignore_index=True)
        save_trips(df, is_officer=is_officer)

        # Add comp members to trip_signups.csv
        if comp_members_to_signup:
            all_signups = load_trip_signups(season=None, is_officer=is_officer)
            signup_rows = []
            for c_rec in comp_members_to_signup:
                c_name = str(c_rec.get("Name", "")).strip().title()
                c_phone = str(c_rec.get("Phone", "")).strip()
                if c_phone.lower() == "nan":
                    c_phone = ""
                # Avoid duplicate signup for this trip
                is_signed_up = not all_signups[(all_signups["TripID"] == next_id) & (all_signups["Name"].str.lower() == c_name.lower())].empty
                if not is_signed_up:
                    s_id = f"SIGNUP-{len(all_signups) + len(signup_rows) + 1:03d}"
                    signup_rows.append({
                        "SignupID": s_id,
                        "TripID": next_id,
                        "TripName": name.strip(),
                        "Season": actual_season,
                        "Name": c_name,
                        "Phone": c_phone,
                        "DrivingCapacity": "Cannot drive",
                        "Questions": "Competition Team member automatic registration",
                        "PaymentReceived": False,
                        "SignupDate": date.today().strftime("%Y-%m-%d")
                    })
            if signup_rows:
                all_signups = pd.concat([all_signups, pd.DataFrame(signup_rows)], ignore_index=True)
                save_trip_signups(all_signups, is_officer=is_officer)

        # Directly update attendee members' TripsAttended in members file for actual_season
        if attendee_roster:
            members_df = load_members(season=None, is_officer=is_officer)
            if "TripsAttended" in members_df.columns:
                m_changed = False
                for m_name in attendee_roster:
                    c_name = str(m_name).strip().lower()
                    m_mask = members_df["Name"].astype(str).str.lower().str.strip() == c_name
                    s_mask = m_mask & (members_df["Season"] == actual_season)
                    target_indices = members_df[s_mask].index if s_mask.any() else members_df[m_mask].index
                    for m_idx in target_indices:
                        curr_trips_raw = str(members_df.loc[m_idx, "TripsAttended"]) if pd.notnull(members_df.loc[m_idx, "TripsAttended"]) else ""
                        if curr_trips_raw.lower() in ["nan", "none"]:
                            curr_trips_raw = ""
                        t_list = [t.strip() for t in curr_trips_raw.split(",") if t.strip()]
                        if not any(t.lower() == name.strip().lower() for t in t_list):
                            t_list.append(name.strip())
                            members_df.at[m_idx, "TripsAttended"] = ", ".join(t_list)
                            m_changed = True
                if m_changed:
                    save_members(members_df, is_officer=is_officer)

        return True
    except Exception as e:
        print(f"Error adding trip: {e}")
        return False


def add_trip(name: str, destination: str, start_date: str, end_date: str, nights: int,
             miles: float, attendees: int, vehicles: int, cabin: float, food: float,
             tickets: float, gas: float, status: str = "Planning", notes: str = "",
             season: str = CURRENT_SEASON, is_officer: bool = False, trip_type: str = "Recreational",
             school_funding: float = 0.0, net_cost: float = None, school_coverage_details: str = "") -> bool:
    """Compatibility wrapper for add_created_trip."""
    return add_created_trip(
        name=name, destination=destination, trip_type=trip_type, start_date=start_date,
        end_date=end_date, nights=nights, miles=miles, attendees=attendees, vehicles=vehicles,
        cabin=cabin, food=food, tickets=tickets, gas=gas, attendee_roster=[], status=status,
        notes=notes, season=season, is_officer=is_officer, school_funding=school_funding,
        net_cost=net_cost, school_coverage_details=school_coverage_details
    )


def delete_trip(trip_id: str, is_officer: bool = False) -> bool:
    """Delete a trip from the database by its TripID or Name, and clean up signups, ledger, and member history."""
    try:
        if not trip_id:
            return False
        df = load_trips(season=None, is_officer=is_officer)
        match_idx = df[(df["TripID"].astype(str).str.strip() == str(trip_id).strip()) |
                       (df["Name"].astype(str).str.lower().str.strip() == str(trip_id).lower().strip())].index
        if len(match_idx) > 0:
            trip_row = df.loc[match_idx[0]]
            trip_name = str(trip_row.get("Name", "")).strip()
            actual_trip_id = str(trip_row.get("TripID", "")).strip()
            trip_season = str(trip_row.get("Season", "")).strip()

            # 1. Clean up all signups for this trip and ledger payments
            all_signups = load_trip_signups(season=None, is_officer=is_officer)
            if not all_signups.empty:
                s_mask = (all_signups["TripID"].astype(str).str.strip() == actual_trip_id) | \
                         (all_signups["TripName"].astype(str).str.lower().str.strip() == trip_name.lower())
                trip_signups = all_signups[s_mask]
                if not trip_signups.empty:
                    for _, s_row in trip_signups.iterrows():
                        s_name = str(s_row.get("Name", "")).strip()
                        s_paid = _is_truthy(s_row.get("PaymentReceived", False))
                        s_season = str(s_row.get("Season", trip_season)).strip()
                        if s_paid and s_name:
                            remove_trip_payment_from_ledger(s_name, trip_name, s_season, is_officer=is_officer)
                    remaining_signups = all_signups[~s_mask].copy().reset_index(drop=True)
                    save_trip_signups(remaining_signups, is_officer=is_officer)

            # 2. Delete trip from trips file
            df = df.drop(match_idx).reset_index(drop=True)
            save_trips(df, is_officer=is_officer)

            # 3. Remove deleted trip from members file across all members
            members_df = load_members(season=None, is_officer=is_officer)
            if not members_df.empty and "TripsAttended" in members_df.columns:
                m_changed = False
                for m_idx, m_row in members_df.iterrows():
                    m_trips = str(m_row.get("TripsAttended", "")).strip()
                    if m_trips and m_trips.lower() not in ["nan", "none", "0.0", "0"]:
                        t_list = [t.strip() for t in m_trips.split(",") if t.strip() and t.strip().lower() not in ["nan", "none", "0.0", "0"]]
                        new_t_list = [t for t in t_list if t.lower() != trip_name.lower()]
                        if len(new_t_list) != len(t_list):
                            members_df.at[m_idx, "TripsAttended"] = ", ".join(new_t_list)
                            m_changed = True
                if m_changed:
                    save_members(members_df, is_officer=is_officer)

            return True
        return False
    except Exception as e:
        print(f"Error deleting trip: {e}")
        return False


def update_trip_status(trip_id: str, new_status: str, is_officer: bool = False) -> bool:
    """Update the status of an existing trip by TripID."""
    try:
        clean_status = str(new_status).strip()
        if not trip_id or not clean_status:
            return False
        df = load_trips(season=None, is_officer=is_officer)
        if df.empty:
            return False
        mask = df["TripID"] == trip_id
        if not mask.any():
            return False
        df.loc[mask, "Status"] = clean_status
        save_trips(df, is_officer=is_officer)
        return True
    except Exception as e:
        print(f"Error updating trip status: {e}")
        return False


def generate_trips_ical(trips_df: pd.DataFrame, calendar_name: str = "UCSB Ski Team Trips") -> str:
    """
    Generate RFC 5545 compliant iCalendar (.ics) format string for scheduled trips.
    Compatible with Google Calendar, Apple Calendar, and Microsoft Outlook.
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//UCSB Ski and Snowboard Team//Trip Schedule//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{calendar_name}",
        "X-WR-TIMEZONE:America/Los_Angeles"
    ]

    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def _parse_date(val):
        if not val or str(val).strip().lower() in ["nan", "none", ""]:
            return None
        s = str(val).strip()
        for fmt in ["%Y-%m-%d", "%m-%d-%Y", "%m/%d/%Y", "%Y/%m/%d"]:
            try:
                return datetime.strptime(s[:10], fmt).date()
            except Exception:
                pass
        return None

    for _, row in trips_df.iterrows():
        trip_id = str(row.get("TripID", "")).strip()
        trip_name = str(row.get("Name", "Ski Trip")).strip()
        destination = str(row.get("Destination", "")).strip()
        trip_type = str(row.get("TripType", "Recreational")).strip()
        status = str(row.get("Status", "Confirmed")).strip()
        notes = str(row.get("Notes", "")).strip()
        nights = int(row.get("Nights", 1)) if pd.notnull(row.get("Nights")) else 1
        attendees = int(row.get("Attendees", 0)) if pd.notnull(row.get("Attendees")) else 0
        total_cost = float(row.get("TotalCost", 0.0)) if pd.notnull(row.get("TotalCost")) else 0.0

        start_dt = _parse_date(row.get("StartDate"))
        if not start_dt:
            continue

        end_dt = _parse_date(row.get("EndDate"))
        if not end_dt:
            end_dt = start_dt + timedelta(days=nights)

        # In iCalendar, DTEND for all-day events is exclusive (day after last day)
        exclusive_end_dt = end_dt + timedelta(days=1)

        dtstart_str = start_dt.strftime("%Y%m%d")
        dtend_str = exclusive_end_dt.strftime("%Y%m%d")
        uid = f"{trip_id or 'TRIP'}-{dtstart_str}@ucsbskiteam.com"

        date_str = start_dt.strftime('%b %d, %Y') if start_dt == end_dt else f"{start_dt.strftime('%b %d, %Y')} to {end_dt.strftime('%b %d, %Y')}"

        desc_lines = [
            f"Trip: {trip_name}",
            f"Type: {trip_type}",
            f"Destination: {destination}",
            f"Dates: {date_str}",
            f"Status: {status}"
        ]

        description = "\\n".join(desc_lines)

        ical_status = "CONFIRMED"
        if status.lower() == "cancelled":
            ical_status = "CANCELLED"
        elif status.lower() == "planning":
            ical_status = "TENTATIVE"

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART;VALUE=DATE:{dtstart_str}",
            f"DTEND;VALUE=DATE:{dtend_str}",
            f"SUMMARY:UCSB Ski Team: {trip_name}",
            f"DESCRIPTION:{description}",
            f"LOCATION:{destination}",
            f"STATUS:{ical_status}",
            "END:VEVENT"
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def get_cost_benchmarks(is_officer: bool = False) -> dict:
    """Extract data-driven benchmarks from completed trips and ledger receipts."""
    ensure_data_initialized()
    df_trips = load_trips(season=None, is_officer=is_officer)

    benchmarks = {
        "avg_cabin_per_night": 950.0,
        "avg_cabin_per_person_night": 35.0,
        "avg_food_per_person_day": 18.50,
        "avg_gas_per_car_mile": 0.24,
        "completed_trips_count": 0,
        "total_tracked_expenses": 0.0
    }

    if not df_trips.empty:
        completed = df_trips[df_trips["Status"] == "Completed"]
        if not completed.empty:
            benchmarks["completed_trips_count"] = len(completed)
            valid_cabin = completed[completed["Nights"] > 0]
            if not valid_cabin.empty:
                benchmarks["avg_cabin_per_night"] = float((valid_cabin["CabinCost"] / valid_cabin["Nights"]).mean())
                total_person_nights = (valid_cabin["Attendees"] * valid_cabin["Nights"]).sum()
                if total_person_nights > 0:
                    benchmarks["avg_cabin_per_person_night"] = float(valid_cabin["CabinCost"].sum() / total_person_nights)

            valid_food = completed[completed["Attendees"] > 0]
            if not valid_food.empty:
                total_skier_days = (valid_food["Attendees"] * valid_food["Nights"]).sum()
                if total_skier_days > 0:
                    benchmarks["avg_food_per_person_day"] = float(valid_food["FoodAlcoholCost"].sum() / total_skier_days)

    return benchmarks


# --- TRIP SIGN-UPS & CARPOOL TRACKING (GOOGLE FORMS & PAYMENT CHECKBOX) ---

def load_trip_signups(trip_id_or_name: str = None, season: str = CURRENT_SEASON, is_officer: bool = False) -> pd.DataFrame:
    """Load trip sign-up records, optionally filtered by trip and season."""
    ensure_data_initialized()
    if not is_officer:
        if os.path.exists(DEMO_TRIP_SIGNUPS_FILE):
            df = pd.read_csv(DEMO_TRIP_SIGNUPS_FILE)
        else:
            df = pd.DataFrame(columns=SIGNUP_COLS)
    else:
        sheet_url = getattr(config, "TRIPS_EVENTS_SHEET_URL", "") or TRIPS_EVENTS_SHEET_URL
        df = None
        if sheet_url:
            gs_df = read_gsheet_worksheet(sheet_url, "Signups", ttl=60)
            if gs_df is not None and not gs_df.empty and "Name" in gs_df.columns:
                try:
                    gs_df.to_csv(TRIP_SIGNUPS_FILE, index=False)
                except Exception:
                    pass
                df = gs_df

        if df is None or df.empty:
            if os.path.exists(TRIP_SIGNUPS_FILE):
                df = pd.read_csv(TRIP_SIGNUPS_FILE)
            else:
                df = pd.DataFrame(columns=SIGNUP_COLS)

    try:
        if "PaymentReceived" not in df.columns:
            df["PaymentReceived"] = False
        df["PaymentReceived"] = df["PaymentReceived"].fillna(False).astype(bool)

        for col in ["SignupID", "TripID", "TripName", "Season", "Name", "Phone", "DrivingCapacity", "Questions", "SignupDate"]:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str)

        if season and season != "All Seasons":
            df = df[df["Season"] == season]
        if trip_id_or_name:
            df = df[(df["TripID"] == trip_id_or_name) | (df["TripName"] == trip_id_or_name)]
        return df.copy().reset_index(drop=True)
    except Exception as e:
        print(f"Error loading trip signups: {e}")
        return pd.DataFrame(columns=SIGNUP_COLS)


def save_trip_signups(df: pd.DataFrame, is_officer: bool = False):
    """Save trip signups dataset to CSV and Google Sheets."""
    save_cols = [c for c in SIGNUP_COLS if c in df.columns]
    save_df = df[save_cols].copy() if save_cols else df.copy()
    if not is_officer:
        save_df.to_csv(DEMO_TRIP_SIGNUPS_FILE, index=False)
        return

    save_df.to_csv(TRIP_SIGNUPS_FILE, index=False)
    sheet_url = getattr(config, "TRIPS_EVENTS_SHEET_URL", "") or TRIPS_EVENTS_SHEET_URL
    if sheet_url:
        write_gsheet_worksheet(sheet_url, "Signups", save_df)


def record_trip_payment_in_ledger(athlete_name: str, trip_name: str, trip_id: str = None,
                                  season: str = CURRENT_SEASON, amount: float = None,
                                  notes: str = None, is_officer: bool = False) -> bool:
    """
    Log an entry in the ledger under athlete_name for the trip fee (Income, Trip Payment category).
    Avoids duplicate entries for the same athlete on the same trip in the same season.
    """
    try:
        clean_name = str(athlete_name).strip().title()
        clean_trip = str(trip_name).strip()
        if not clean_name or clean_name.lower() == "nan" or not clean_trip:
            return False

        # If amount not specified, look up calculated per-skier trip cost from trips
        final_amount = amount
        if final_amount is None or final_amount <= 0:
            df_trips = load_trips(season=None, is_officer=is_officer)
            trip_match = pd.DataFrame()
            if trip_id:
                trip_match = df_trips[df_trips["TripID"] == trip_id]
            if trip_match.empty and clean_trip:
                trip_match = df_trips[df_trips["Name"].astype(str).str.lower().str.strip() == clean_trip.lower()]

            if not trip_match.empty:
                t_row = trip_match.iloc[0]
                t_cost = float(t_row.get("NetCost", t_row.get("TotalCost", 0.0)))
                t_att = max(1, int(t_row.get("Attendees", 1)))
                final_amount = round(t_cost / t_att, 2) if t_cost > 0 else 0.0
            else:
                final_amount = 95.0

        if final_amount <= 0.0:
            # 100% subsidized by school funding - no attendee payment required
            return True

        df_ledger = load_ledger(season=None, is_officer=is_officer)

        # Check if already logged for this athlete, trip, and season to avoid duplicates
        if not df_ledger.empty:
            existing = df_ledger[
                (df_ledger["Entity"].astype(str).str.lower().str.strip() == clean_name.lower()) &
                (df_ledger["Category"] == "Trip Payment") &
                (df_ledger["Type"] == "Income") &
                (df_ledger["Season"] == season) &
                (df_ledger["Notes"].astype(str).str.lower().str.contains(clean_trip.lower(), na=False))
            ]
            if not existing.empty:
                return True

        note_text = notes.strip() if notes else f"{clean_trip} - Trip payment"
        return add_transaction(
            date_str=date.today().strftime("%m-%d-%Y"),
            entity=clean_name,
            amount=float(final_amount),
            category="Trip Payment",
            notes=note_text,
            trans_type="Income",
            season=season,
            is_officer=is_officer
        )
    except Exception as e:
        print(f"Error recording trip payment in ledger: {e}")
        return False


def remove_trip_payment_from_ledger(athlete_name: str, trip_name: str, season: str = CURRENT_SEASON,
                                    is_officer: bool = False) -> bool:
    """
    Remove the trip payment entry (Income, Trip Payment) from the ledger for athlete_name
    and trip_name in the specified season when Payment Received status is unchecked (revoked).
    """
    try:
        clean_name = str(athlete_name).strip().lower()
        clean_trip = str(trip_name).strip().lower()
        if not clean_name or clean_name == "nan" or not clean_trip:
            return False

        df_ledger = load_ledger(season=None, is_officer=is_officer)
        if df_ledger.empty:
            return False

        # Match entity, category Trip Payment, Type Income, Season, and Notes containing trip name
        matches = df_ledger[
            (df_ledger["Entity"].astype(str).str.lower().str.strip() == clean_name) &
            (df_ledger["Category"] == "Trip Payment") &
            (df_ledger["Type"] == "Income") &
            (df_ledger["Season"] == season) &
            (df_ledger["Notes"].astype(str).str.lower().str.contains(clean_trip, na=False))
        ]

        if matches.empty and (not season or season == "All Seasons"):
            matches = df_ledger[
                (df_ledger["Entity"].astype(str).str.lower().str.strip() == clean_name) &
                (df_ledger["Category"] == "Trip Payment") &
                (df_ledger["Type"] == "Income") &
                (df_ledger["Notes"].astype(str).str.lower().str.contains(clean_trip, na=False))
            ]

        if not matches.empty:
            df_ledger = df_ledger.drop(matches.index).reset_index(drop=True)
            save_ledger(df_ledger, is_officer=is_officer)
            return True
        return False
    except Exception as e:
        print(f"Error removing trip payment from ledger: {e}")
        return False


def save_edited_trip_signups(edited_df: pd.DataFrame, trip_id: str, is_officer: bool = False) -> bool:
    """
    Save in-table edits from st.data_editor for trip signups (e.g. Payment Received checkbox).
    Automatically logs an Income, Trip Payment entry in the ledger when Payment Received is checked,
    and removes the corresponding ledger entry when Payment Received is unchecked (revoked).
    """
    try:
        full_df = load_trip_signups(season=None, is_officer=is_officer)
        col_rename_back = {
            "ID": "SignupID",
            "Name": "Name",
            "Phone": "Phone",
            "Driving Capacity (with gear)": "DrivingCapacity",
            "If you can drive (and how many passengers accounting for gear)": "DrivingCapacity",
            "Questions": "Questions",
            "Questions or Concerns?": "Questions",
            "Payment Received": "PaymentReceived",
            "Sign-Up Date": "SignupDate"
        }
        df_to_merge = edited_df.rename(columns=col_rename_back).copy()

        def _to_bool(val) -> bool:
            if isinstance(val, (bool, np.bool_)):
                return bool(val)
            if isinstance(val, (int, np.integer, float, np.floating)):
                return val != 0 and not np.isnan(val)
            s = str(val).strip().lower()
            return s in ["true", "1", "yes", "y", "t"]

        # Pre-lookup trip details for ticket price calculation and fallback trip name
        trips_df = load_trips(season=None, is_officer=is_officer)
        trip_price = None
        fallback_trip_name = ""
        if trip_id:
            trip_match = trips_df[trips_df["TripID"] == trip_id]
            if not trip_match.empty:
                t_row = trip_match.iloc[0]
                fallback_trip_name = str(t_row.get("Name", "")).strip()
                t_cost = float(t_row.get("TotalCost", 0.0))
                t_att = max(1, int(t_row.get("Attendees", 1)))
                trip_price = round(t_cost / t_att, 2) if t_cost > 0 else 95.0

        full_df.set_index("SignupID", inplace=True)
        df_to_merge.set_index("SignupID", inplace=True)

        # Detect newly checked or unchecked Payment Received boxes and update ledger
        for sid, row in df_to_merge.iterrows():
            if sid in full_df.index:
                was_paid = _to_bool(full_df.loc[sid, "PaymentReceived"]) if "PaymentReceived" in full_df.columns else False
                now_paid = _to_bool(row.get("PaymentReceived", False))
                athlete_name = str(row.get("Name", full_df.loc[sid, "Name"])).strip().title()
                trip_name = str(full_df.loc[sid, "TripName"]).strip() if pd.notnull(full_df.loc[sid, "TripName"]) and str(full_df.loc[sid, "TripName"]).strip() else fallback_trip_name
                athlete_season = str(full_df.loc[sid, "Season"]).strip() if "Season" in full_df.columns and pd.notnull(full_df.loc[sid, "Season"]) else CURRENT_SEASON

                if not was_paid and now_paid:
                    record_trip_payment_in_ledger(
                        athlete_name=athlete_name,
                        trip_name=trip_name,
                        trip_id=trip_id,
                        season=athlete_season,
                        amount=trip_price,
                        is_officer=is_officer
                    )
                elif was_paid and not now_paid:
                    remove_trip_payment_from_ledger(
                        athlete_name=athlete_name,
                        trip_name=trip_name,
                        season=athlete_season,
                        is_officer=is_officer
                    )

        for col in ["Name", "Phone", "DrivingCapacity", "Questions", "PaymentReceived"]:
            if col in df_to_merge.columns:
                full_df.update(df_to_merge[[col]])

        full_df.reset_index(inplace=True)
        save_trip_signups(full_df, is_officer=is_officer)
        return True
    except Exception as e:
        print(f"Error saving edited trip signups: {e}")
        return False


def parse_and_sync_trip_form_df(df_form: pd.DataFrame, trip_id: str, trip_name: str, season: str = CURRENT_SEASON,
                            is_officer: bool = False) -> tuple[bool, str, int]:
    """
    Parse a Google Form response sheet specifically created for a trip sign-up.
    Extracts Name, Phone, Driving capacity, and Questions, initializing PaymentReceived=False.
    """
    try:
        all_signups = load_trip_signups(season=None, is_officer=is_officer)
        
        col_map = {}
        for col in df_form.columns:
            c_low = col.lower().strip()
            if ("name" in c_low or "first and last" in c_low) and "name" not in col_map:
                col_map["name"] = col
            elif ("phone" in c_low or "cell" in c_low or "number" in c_low) and "phone" not in col_map:
                col_map["phone"] = col
            elif any(k in c_low for k in ["drive", "driver", "passenger", "car", "vehicle", "seat", "gear"]) and "driving" not in col_map:
                col_map["driving"] = col
            elif any(k in c_low for k in ["question", "concern", "comment", "note"]) and "questions" not in col_map:
                col_map["questions"] = col

        if "name" not in col_map and len(df_form.columns) > 1:
            col_map["name"] = df_form.columns[1]

        added_count = 0
        updated_count = 0

        for _, row in df_form.iterrows():
            name_val = str(row.get(col_map.get("name", ""), "")).strip()
            phone_val = str(row.get(col_map.get("phone", ""), "")).strip()
            driving_val = str(row.get(col_map.get("driving", ""), "")).strip()
            questions_val = str(row.get(col_map.get("questions", ""), "")).strip()

            if not name_val or name_val.lower() == "nan":
                continue

            clean_phone = format_phone_number(phone_val) if phone_val.lower() != "nan" else ""
            clean_driving = "Cannot drive" if driving_val.lower() in ["nan", "", "no"] else driving_val
            clean_questions = "" if questions_val.lower() in ["nan", "none", "n/a", "no"] else questions_val

            # Check if this person already signed up for this trip
            match_idx = all_signups[(all_signups["TripID"] == trip_id) & (all_signups["Name"].str.lower() == name_val.lower())].index

            if len(match_idx) > 0:
                idx = match_idx[0]
                if clean_phone:
                    all_signups.loc[idx, "Phone"] = clean_phone
                all_signups.loc[idx, "DrivingCapacity"] = clean_driving
                if clean_questions:
                    all_signups.loc[idx, "Questions"] = clean_questions
                updated_count += 1
            else:
                added_count += 1
                s_id = f"SIGNUP-{len(all_signups) + added_count:03d}"
                new_row = pd.DataFrame([{
                    "SignupID": s_id,
                    "TripID": trip_id,
                    "TripName": trip_name,
                    "Season": season,
                    "Name": name_val.title(),
                    "Phone": clean_phone,
                    "DrivingCapacity": clean_driving,
                    "Questions": clean_questions,
                    "PaymentReceived": False,
                    "SignupDate": date.today().strftime("%Y-%m-%d")
                }])
                all_signups = pd.concat([all_signups, new_row], ignore_index=True)

            # Sync trip into member's TripsAttended profile
            add_trip_to_member_history(name_val.title(), trip_name, season, is_officer=is_officer)

        save_trip_signups(all_signups, is_officer=is_officer)

        # Update AttendeeRoster and Attendees count in trips file
        trips_df = load_trips(season=None, is_officer=is_officer)
        if not trips_df.empty:
            t_mask = (trips_df["TripID"] == trip_id) | (trips_df["Name"].str.lower() == trip_name.strip().lower())
            if t_mask.any():
                t_idx = trips_df[t_mask].index[0]
                curr_roster = str(trips_df.loc[t_idx, "AttendeeRoster"]).strip() if "AttendeeRoster" in trips_df.columns and pd.notnull(trips_df.loc[t_idx, "AttendeeRoster"]) else ""
                if curr_roster.lower() in ["nan", "none"]:
                    curr_roster = ""
                r_names = [n.strip() for n in curr_roster.split(",") if n.strip()]
                trip_signups_names = all_signups[all_signups["TripID"] == trip_id]["Name"].dropna().tolist()
                for s_name in trip_signups_names:
                    s_clean = str(s_name).strip().title()
                    if s_clean and not any(n.lower() == s_clean.lower() for n in r_names):
                        r_names.append(s_clean)
                trips_df.loc[t_idx, "AttendeeRoster"] = ", ".join(r_names)
                if "Attendees" in trips_df.columns:
                    try:
                        if len(r_names) > int(trips_df.loc[t_idx, "Attendees"]):
                            trips_df.loc[t_idx, "Attendees"] = len(r_names)
                    except Exception:
                        pass
                save_trips(trips_df, is_officer=is_officer)

        msg = f"Synced {trip_name} Sign-Ups: {added_count} new skier(s) registered, {updated_count} response(s) updated."
        return True, msg, (added_count + updated_count)

    except Exception as e:
        return False, f"Error processing trip sign-up data: {e}", 0


def fetch_and_sync_trip_form_sheet(sheet_url: str, trip_id: str, trip_name: str, season: str = CURRENT_SEASON,
                                   is_officer: bool = False) -> tuple[bool, str, int]:
    """Fetch a Google Sheet for trip sign-ups and parse responses."""
    clean_url = sheet_url.strip()
    gid_match = re.search(r"gid=([0-9]+)", clean_url)
    gid_str = f"&gid={gid_match.group(1)}" if gid_match else ""
    
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", clean_url)
    if match:
        sheet_id = match.group(1)
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv{gid_str}"
    elif clean_url.startswith("http"):
        csv_url = clean_url
    else:
        csv_url = f"https://docs.google.com/spreadsheets/d/{clean_url}/export?format=csv{gid_str}"

    try:
        df_form = pd.read_csv(csv_url)
        return parse_and_sync_trip_form_df(df_form, trip_id, trip_name, season, is_officer=is_officer)
    except Exception as e:
        return False, f"Could not fetch trip sign-up sheet. Verify link sharing or upload CSV. Details: {e}", 0


def add_trip_attendee(trip_id: str, trip_name: str, name: str, phone: str,
                      driving_capacity: str, questions: str = "",
                      payment_received: bool = False, season: str = CURRENT_SEASON,
                      is_officer: bool = False) -> bool:
    """Manually add an attendee to a trip roster and synchronize member trip history."""
    try:
        clean_name = name.strip().title()
        all_signups = load_trip_signups(trip_id_or_name=None, is_officer=is_officer)
        s_id = f"SIGNUP-{len(all_signups) + 1:03d}"
        new_row = pd.DataFrame([{
            "SignupID": s_id,
            "TripID": trip_id,
            "TripName": trip_name.strip(),
            "Season": season,
            "Name": clean_name,
            "Phone": format_phone_number(phone),
            "DrivingCapacity": driving_capacity.strip(),
            "Questions": questions.strip(),
            "PaymentReceived": bool(payment_received),
            "SignupDate": date.today().strftime("%Y-%m-%d")
        }])
        all_signups = pd.concat([all_signups, new_row], ignore_index=True)
        save_trip_signups(all_signups, is_officer=is_officer)

        # Update AttendeeRoster and attendee count in trips file if the trip exists
        trips_df = load_trips(season=None, is_officer=is_officer)
        if not trips_df.empty:
            t_mask = (trips_df["TripID"] == trip_id) | (trips_df["Name"].str.lower() == trip_name.strip().lower())
            if t_mask.any():
                t_idx = trips_df[t_mask].index[0]
                curr_roster = str(trips_df.loc[t_idx, "AttendeeRoster"]).strip() if "AttendeeRoster" in trips_df.columns and pd.notnull(trips_df.loc[t_idx, "AttendeeRoster"]) else ""
                if curr_roster.lower() in ["nan", "none"]:
                    curr_roster = ""
                r_names = [n.strip() for n in curr_roster.split(",") if n.strip()]
                if not any(n.lower() == clean_name.lower() for n in r_names):
                    r_names.append(clean_name)
                    trips_df.loc[t_idx, "AttendeeRoster"] = ", ".join(r_names)
                    if "Attendees" in trips_df.columns:
                        try:
                            if len(r_names) > int(trips_df.loc[t_idx, "Attendees"]):
                                trips_df.loc[t_idx, "Attendees"] = len(r_names)
                        except Exception:
                            pass
                    save_trips(trips_df, is_officer=is_officer)

        # Synchronize trip to member's TripsAttended history in members file
        add_trip_to_member_history(clean_name, trip_name.strip(), season, is_officer=is_officer)

        # If payment received was checked on manual add form, record in ledger
        if payment_received:
            record_trip_payment_in_ledger(
                athlete_name=clean_name,
                trip_name=trip_name.strip(),
                trip_id=trip_id,
                season=season,
                is_officer=is_officer
            )

        return True
    except Exception as e:
        print(f"Error adding trip attendee: {e}")
        return False


def delete_multiple_trip_attendees(signup_ids: list, trip_id: str = None, trip_name: str = None,
                                   season: str = None, is_officer: bool = False) -> int:
    """
    Remove multiple attendees from trip sign-up rosters and AttendeeRoster,
    automatically remove the trip from each athlete's TripsAttended history in members file,
    and remove any recorded trip payment from the ledger.
    Accepts SignupIDs, athlete names, or attendee dicts.
    Returns the count of removed attendees.
    """
    try:
        if not signup_ids:
            return 0

        target_signup_ids = set()
        target_names = set()
        for item in signup_ids:
            if isinstance(item, dict):
                if item.get("signup_id"):
                    target_signup_ids.add(str(item["signup_id"]).strip())
                if item.get("name"):
                    target_names.add(str(item["name"]).strip().lower())
            elif isinstance(item, str):
                s = item.strip()
                if s.startswith("SIGNUP-"):
                    target_signup_ids.add(s)
                else:
                    target_names.add(s.lower())

        all_signups = load_trip_signups(season=None, is_officer=is_officer)
        matched_signups_mask = pd.Series(False, index=all_signups.index) if not all_signups.empty else pd.Series(dtype=bool)
        affected_trips = set()
        removed_records = []

        if not all_signups.empty:
            if target_signup_ids:
                matched_signups_mask = matched_signups_mask | all_signups["SignupID"].isin(target_signup_ids)
            if target_names:
                name_match = all_signups["Name"].astype(str).str.lower().str.strip().isin(target_names)
                if trip_id or trip_name:
                    t_filter = pd.Series(False, index=all_signups.index)
                    if trip_id:
                        t_filter = t_filter | (all_signups["TripID"].astype(str).str.strip() == str(trip_id).strip())
                    if trip_name:
                        t_filter = t_filter | (all_signups["TripName"].astype(str).str.lower().str.strip() == str(trip_name).lower().strip())
                    name_match = name_match & t_filter
                matched_signups_mask = matched_signups_mask | name_match

            match_rows = all_signups[matched_signups_mask]
            for _, row in match_rows.iterrows():
                r_name = str(row.get("Name", "")).strip()
                r_trip = str(row.get("TripName", "")).strip()
                r_season = str(row.get("Season", "")).strip()
                r_paid = _is_truthy(row.get("PaymentReceived", False))
                if r_name:
                    target_names.add(r_name.lower())
                if r_trip:
                    affected_trips.add(r_trip.lower())
                removed_records.append((r_name, r_trip, r_season, r_paid))

            # 1. Remove matching rows from trip_signups file
            if matched_signups_mask.any():
                remaining_signups = all_signups[~matched_signups_mask].copy().reset_index(drop=True)
                save_trip_signups(remaining_signups, is_officer=is_officer)

        if trip_name:
            affected_trips.add(str(trip_name).strip().lower())

        # 2. Update trips file AttendeeRoster and adjust Attendees count
        trips_df = load_trips(season=None, is_officer=is_officer)
        if not trips_df.empty and "AttendeeRoster" in trips_df.columns:
            trips_changed = False
            for t_idx, t_row in trips_df.iterrows():
                curr_t_id = str(t_row.get("TripID", "")).strip()
                curr_t_name = str(t_row.get("Name", "")).strip().lower()
                is_affected = (curr_t_name in affected_trips) or (trip_id and curr_t_id == str(trip_id).strip())
                if is_affected:
                    curr_roster = str(t_row.get("AttendeeRoster", "")).strip()
                    if curr_roster and curr_roster.lower() not in ["nan", "none", "0.0", "0"]:
                        r_names = [n.strip() for n in curr_roster.split(",") if n.strip() and n.strip().lower() not in ["nan", "none", "0.0", "0"]]
                        new_r = [n for n in r_names if n.lower() not in target_names]
                        if len(new_r) != len(r_names):
                            trips_df.at[t_idx, "AttendeeRoster"] = ", ".join(new_r)
                            if "Attendees" in trips_df.columns:
                                try:
                                    trips_df.at[t_idx, "Attendees"] = max(0, len(new_r))
                                except Exception:
                                    pass
                            trips_changed = True
            if trips_changed:
                save_trips(trips_df, is_officer=is_officer)

        # 3. Clean up ledger payments
        for r_name, r_trip, r_season, r_paid in removed_records:
            if r_paid and r_name and r_trip:
                remove_trip_payment_from_ledger(r_name, r_trip, r_season, is_officer=is_officer)

        # 4. Remove trip(s) from each member's TripsAttended in members.csv
        members_df = load_members(season=None, is_officer=is_officer)
        if not members_df.empty and "TripsAttended" in members_df.columns:
            m_changed = False
            for m_idx, m_row in members_df.iterrows():
                m_name = str(m_row.get("Name", "")).strip().lower()
                if m_name in target_names:
                    curr_trips = str(m_row.get("TripsAttended", "")).strip()
                    if curr_trips and curr_trips.lower() not in ["nan", "none", "0.0", "0"]:
                        t_list = [t.strip() for t in curr_trips.split(",") if t.strip() and t.strip().lower() not in ["nan", "none", "0.0", "0"]]
                        new_t_list = [t for t in t_list if t.lower() not in affected_trips]
                        if len(new_t_list) != len(t_list):
                            members_df.at[m_idx, "TripsAttended"] = ", ".join(new_t_list)
                            m_changed = True
            if m_changed:
                save_members(members_df, is_officer=is_officer)

        return max(len(target_names), len(removed_records))
    except Exception as e:
        print(f"Error deleting multiple trip attendees: {e}")
        return 0


def delete_trip_attendee(signup_id: str, is_officer: bool = False) -> bool:
    """Remove a single attendee from a trip sign-up roster and sync member history."""
    return delete_multiple_trip_attendees([signup_id], is_officer=is_officer) > 0


# --- OFFICER ROSTER & TO-DO LIST OPERATIONS ---

def load_officers(is_officer: bool = False) -> list:
    """Load the list of club officers."""
    ensure_data_initialized()
    target_file = get_officers_file(is_officer)
    try:
        if os.path.exists(target_file):
            df = pd.read_csv(target_file)
            if "Officer" in df.columns:
                officers = [str(x).strip() for x in df["Officer"].dropna().tolist() if str(x).strip()]
                if officers:
                    return officers
        default_pool = OFFICERS if is_officer else DEMO_OFFICERS
        save_officers(default_pool, is_officer=is_officer)
        return list(default_pool)
    except Exception as e:
        print(f"Error loading officers: {e}")
        return list(OFFICERS if is_officer else DEMO_OFFICERS)


def save_officers(officers: list, is_officer: bool = False) -> bool:
    """Save officers list to CSV."""
    try:
        target_file = get_officers_file(is_officer)
        clean_officers = []
        for o in officers:
            s = str(o).strip()
            if s and s not in clean_officers:
                clean_officers.append(s)
        pd.DataFrame({"Officer": clean_officers}).to_csv(target_file, index=False)
        return True
    except Exception as e:
        print(f"Error saving officers: {e}")
        return False


def add_officer(name: str, is_officer: bool = False) -> tuple:
    """Add a new officer to the roster."""
    clean_name = str(name).strip()
    if not clean_name:
        return False, "Officer name cannot be empty."
    current_officers = load_officers(is_officer=is_officer)
    if any(o.lower() == clean_name.lower() for o in current_officers):
        return False, f"Officer '{clean_name}' already exists in the roster."
    current_officers.append(clean_name)
    if save_officers(current_officers, is_officer=is_officer):
        return True, f"Officer '{clean_name}' added successfully."
    return False, "Failed to save officer."


def delete_officer(name: str, is_officer: bool = False) -> tuple:
    """Remove an officer from the roster."""
    clean_name = str(name).strip()
    current_officers = load_officers(is_officer=is_officer)
    matching = [o for o in current_officers if o.lower() == clean_name.lower()]
    if not matching:
        return False, f"Officer '{clean_name}' not found in roster."
    if len(current_officers) <= 1:
        return False, "Cannot remove the last remaining officer."
    current_officers = [o for o in current_officers if o.lower() != clean_name.lower()]
    if save_officers(current_officers, is_officer=is_officer):
        return True, f"Officer '{clean_name}' removed successfully."
    return False, "Failed to save updated officer list."


def load_todos(season: str = None, status: str = None, is_officer: bool = False) -> pd.DataFrame:
    """Load officer tasks, optionally filtered by season and status."""
    ensure_data_initialized()
    if not is_officer:
        if os.path.exists(DEMO_TODOS_FILE):
            df = pd.read_csv(DEMO_TODOS_FILE)
        else:
            df = pd.DataFrame(columns=TODO_COLS)
    else:
        sheet_url = getattr(config, "TRIPS_EVENTS_SHEET_URL", "") or TRIPS_EVENTS_SHEET_URL
        df = None
        if sheet_url:
            gs_df = read_gsheet_worksheet(sheet_url, "Todos", ttl=60)
            if gs_df is not None and not gs_df.empty and "Title" in gs_df.columns:
                try:
                    gs_df.to_csv(TODOS_FILE, index=False)
                except Exception:
                    pass
                df = gs_df

        if df is None or df.empty:
            if os.path.exists(TODOS_FILE):
                df = pd.read_csv(TODOS_FILE)
            else:
                df = pd.DataFrame(columns=TODO_COLS)

    try:
        if "Season" not in df.columns:
            df["Season"] = "2026-2027"
        if season and season != "All Seasons":
            df = df[df["Season"] == season]
        if status:
            df = df[df["Status"] == status]
        return df.copy().reset_index(drop=True)
    except Exception as e:
        print(f"Error loading todos: {e}")
        return pd.DataFrame(columns=TODO_COLS)


def save_todos(df: pd.DataFrame, is_officer: bool = False):
    """Save todos dataset to CSV and Google Sheets."""
    save_cols = [c for c in TODO_COLS if c in df.columns]
    save_df = df[save_cols].copy() if save_cols else df.copy()
    if not is_officer:
        save_df.to_csv(DEMO_TODOS_FILE, index=False)
        return

    save_df.to_csv(TODOS_FILE, index=False)
    sheet_url = getattr(config, "TRIPS_EVENTS_SHEET_URL", "") or TRIPS_EVENTS_SHEET_URL
    if sheet_url:
        write_gsheet_worksheet(sheet_url, "Todos", save_df)


def add_todo(title: str, description: str, assigned_to_list: list, target_date: str,
             submitted_date: str = None, notes: str = "", season: str = CURRENT_SEASON,
             is_officer: bool = False) -> bool:
    """Create a new task assigned to one or more officers."""
    try:
        df = load_todos(season=None, is_officer=is_officer)
        next_id = f"TASK-{len(df) + 1:03d}"
        assigned_str = ", ".join(assigned_to_list) if assigned_to_list else "Unassigned"
        sub_date = submitted_date if submitted_date else date.today().strftime("%Y-%m-%d")

        new_task = pd.DataFrame([{
            "TaskID": next_id,
            "Season": season,
            "Title": title.strip(),
            "Description": description.strip(),
            "AssignedTo": assigned_str,
            "SubmittedDate": sub_date,
            "TargetDate": target_date,
            "Status": "Pending",
            "CompletedDate": "",
            "Notes": notes.strip()
        }])
        df = pd.concat([df, new_task], ignore_index=True)
        save_todos(df, is_officer=is_officer)
        return True
    except Exception as e:
        print(f"Error adding todo: {e}")
        return False


def set_todo_status(task_id: str, new_status: str, is_officer: bool = False) -> bool:
    """Mark a task as Completed or re-open as Pending."""
    try:
        df = load_todos(season=None, is_officer=is_officer)
        idx = df[df["TaskID"] == task_id].index
        if len(idx) > 0:
            df.loc[idx[0], "Status"] = new_status
            if new_status == "Completed":
                df.loc[idx[0], "CompletedDate"] = date.today().strftime("%Y-%m-%d")
            else:
                df.loc[idx[0], "CompletedDate"] = ""
            save_todos(df, is_officer=is_officer)
            return True
        return False
    except Exception as e:
        print(f"Error setting todo status: {e}")
        return False


def delete_todo(task_id: str, is_officer: bool = False) -> bool:
    """Delete a task permanently."""
    try:
        df = load_todos(season=None, is_officer=is_officer)
        match_idx = df[df["TaskID"] == task_id].index
        if len(match_idx) > 0:
            df = df.drop(match_idx).reset_index(drop=True)
            save_todos(df, is_officer=is_officer)
            return True
        return False
    except Exception as e:
        print(f"Error deleting todo: {e}")
        return False


# --- MERCH TRACKING OPERATIONS ---

def load_merch_adjustments(season: str = None, is_officer: bool = False) -> pd.DataFrame:
    """Load independent merch sales and adjustments."""
    ensure_data_initialized()
    target_file = get_merch_file(is_officer)
    try:
        df = pd.read_csv(target_file)
        if "Season" not in df.columns:
            df["Season"] = "2026-2027"
        if season and season != "All Seasons":
            df = df[df["Season"] == season]
        return df.copy().reset_index(drop=True)
    except Exception as e:
        print(f"Error loading merch adjustments: {e}")
        return pd.DataFrame()


def save_merch_adjustments(df: pd.DataFrame, is_officer: bool = False):
    """Save merch adjustments to CSV."""
    df.to_csv(get_merch_file(is_officer), index=False)


def add_merch_adjustment(item_type: str, size: str, quantity: int, reason: str, logged_by: str,
                         season: str = CURRENT_SEASON, is_officer: bool = False) -> bool:
    """Record an independent merch distribution or restock."""
    try:
        df = load_merch_adjustments(season=None, is_officer=is_officer)
        next_id = f"ADJ-{len(df) + 1:03d}"
        new_adj = pd.DataFrame([{
            "AdjustmentID": next_id,
            "Season": season,
            "Date": date.today().strftime("%Y-%m-%d"),
            "ItemType": item_type,
            "Size": size,
            "Quantity": int(quantity),
            "Reason": reason.strip(),
            "LoggedBy": logged_by.strip()
        }])
        df = pd.concat([df, new_adj], ignore_index=True)
        save_merch_adjustments(df, is_officer=is_officer)
        return True
    except Exception as e:
        print(f"Error adding merch adjustment: {e}")
        return False


def delete_merch_adjustment(adj_id: str, is_officer: bool = False) -> bool:
    """Delete an independent merch adjustment entry."""
    try:
        df = load_merch_adjustments(season=None, is_officer=is_officer)
        idx = df[df["AdjustmentID"] == adj_id].index
        if len(idx) > 0:
            df = df.drop(idx).reset_index(drop=True)
            save_merch_adjustments(df, is_officer=is_officer)
            return True
        return False
    except Exception as e:
        print(f"Error deleting merch adjustment: {e}")
        return False


def get_merch_inventory_summary(season: str = None, is_officer: bool = False) -> dict:
    """
    Calculate full inventory balances for T-Shirts and Sweatshirts by size.
    Integrates membership claims and independent adjustments.
    """
    ensure_data_initialized()
    members_df = load_members(season=season, is_officer=is_officer)
    adjustments_df = load_merch_adjustments(season=season, is_officer=is_officer)

    shirt_rows = []
    total_shirts_init = 0
    total_shirts_claimed = 0
    total_shirts_adj = 0
    total_shirts_avail = 0

    for sz in VALID_SIZES:
        init_qty = INITIAL_SHIRT_INVENTORY.get(sz, 0)
        claimed_qty = len(members_df[members_df["TShirtSize"] == sz]) if not members_df.empty and "TShirtSize" in members_df.columns else 0
        adj_for_sz = 0
        if not adjustments_df.empty:
            match = adjustments_df[(adjustments_df["ItemType"] == "T-Shirt") & (adjustments_df["Size"] == sz)]
            if not match.empty:
                adj_for_sz = int(match["Quantity"].sum())
        
        avail_qty = init_qty - claimed_qty + adj_for_sz

        shirt_rows.append({
            "Size": sz,
            "Initial Stock": init_qty,
            "Claimed via Membership": claimed_qty,
            "Independent Adjustments": adj_for_sz,
            "Remaining Available": avail_qty
        })

        total_shirts_init += init_qty
        total_shirts_claimed += claimed_qty
        total_shirts_adj += adj_for_sz
        total_shirts_avail += avail_qty

    sweatshirt_rows = []
    total_hoodies_init = 0
    total_hoodies_adj = 0
    total_hoodies_avail = 0

    for sz in VALID_SIZES:
        init_qty = INITIAL_SWEATSHIRT_INVENTORY.get(sz, 0)
        adj_for_sz = 0
        if not adjustments_df.empty:
            match = adjustments_df[(adjustments_df["ItemType"] == "Sweatshirt") & (adjustments_df["Size"] == sz)]
            if not match.empty:
                adj_for_sz = int(match["Quantity"].sum())
        
        avail_qty = init_qty + adj_for_sz

        sweatshirt_rows.append({
            "Size": sz,
            "Initial Stock": init_qty,
            "Distributed / Sales": abs(adj_for_sz) if adj_for_sz < 0 else 0,
            "Net Adjustments": adj_for_sz,
            "Remaining Available": avail_qty
        })

        total_hoodies_init += init_qty
        total_hoodies_adj += adj_for_sz
        total_hoodies_avail += avail_qty

    return {
        "shirts_df": pd.DataFrame(shirt_rows),
        "sweatshirts_df": pd.DataFrame(sweatshirt_rows),
        "total_shirts_init": total_shirts_init,
        "total_shirts_claimed": total_shirts_claimed,
        "total_shirts_avail": total_shirts_avail,
        "total_hoodies_init": total_hoodies_init,
        "total_hoodies_avail": total_hoodies_avail
    }


# --- FINANCIAL KPIS (SEASON AWARE) ---

def get_financial_kpis(season: str = None, is_officer: bool = False) -> dict:
    """Calculate core KPIs from the ledger for the specified season."""
    df = load_ledger(season=season, is_officer=is_officer)
    if df.empty:
        return {
            "total_income": 0.0,
            "total_expenses": 0.0,
            "net_balance": 0.0,
            "dues_collected": 0.0,
            "trip_payments": 0.0,
            "transaction_count": 0
        }

    income_df = df[df["Type"] == "Income"]
    expense_df = df[df["Type"] == "Expense"]

    total_income = float(income_df["Amount"].sum())
    total_expenses = float(expense_df["Amount"].sum())
    net_balance = total_income - total_expenses

    dues_collected = float(income_df[income_df["Category"].isin(["Membership", "Membership Dues"])]["Amount"].sum())
    trip_payments = float(income_df[income_df["Category"] == "Trip Payment"]["Amount"].sum())

    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_balance": net_balance,
        "dues_collected": dues_collected,
        "trip_payments": trip_payments,
        "transaction_count": len(df)
    }


# --- EVENT OPERATIONS & UNIFIED CALENDAR (MULTI-SEASON) ---

EVENT_COLS = [
    "EventID", "Season", "Title", "EventType", "StartDate", "EndDate",
    "StartTime", "EndTime", "Location", "Status", "OfficerLead",
    "Description", "RsvpLink"
]


def load_events(season: str = None, is_officer: bool = False) -> pd.DataFrame:
    """Load and normalize event records, optionally filtered by season."""
    ensure_data_initialized()
    if not is_officer:
        if os.path.exists(DEMO_EVENTS_FILE):
            df = pd.read_csv(DEMO_EVENTS_FILE)
        else:
            df = pd.DataFrame(columns=EVENT_COLS)
    else:
        sheet_url = getattr(config, "TRIPS_EVENTS_SHEET_URL", "") or TRIPS_EVENTS_SHEET_URL
        df = None
        if sheet_url:
            gs_df = read_gsheet_worksheet(sheet_url, "Events", ttl=60)
            if gs_df is not None and not gs_df.empty and "Title" in gs_df.columns:
                try:
                    gs_df.to_csv(EVENTS_FILE, index=False)
                except Exception:
                    pass
                df = gs_df

        if df is None or df.empty:
            if os.path.exists(EVENTS_FILE):
                df = pd.read_csv(EVENTS_FILE)
            else:
                df = pd.DataFrame(columns=EVENT_COLS)

    try:
        for col in EVENT_COLS:
            if col not in df.columns:
                df[col] = ""
            df[col] = df[col].fillna("").astype(str)

        df["Date_dt"] = pd.to_datetime(df["StartDate"], errors="coerce")
        df = df.sort_values(by="Date_dt", ascending=True).reset_index(drop=True)

        if season and season != "All Seasons":
            df = df[df["Season"] == season]

        return df.copy().reset_index(drop=True)
    except Exception as e:
        print(f"Error loading events: {e}")
        return pd.DataFrame(columns=EVENT_COLS)


def save_events(df: pd.DataFrame, is_officer: bool = False):
    """Save events dataset to CSV and Google Sheets, preserving standard columns."""
    save_cols = [c for c in EVENT_COLS if c in df.columns]
    save_df = df[save_cols].copy()
    if not is_officer:
        save_df.to_csv(DEMO_EVENTS_FILE, index=False)
        return

    save_df.to_csv(EVENTS_FILE, index=False)
    sheet_url = getattr(config, "TRIPS_EVENTS_SHEET_URL", "") or TRIPS_EVENTS_SHEET_URL
    if sheet_url:
        write_gsheet_worksheet(sheet_url, "Events", save_df)


def add_event(season: str, title: str, event_type: str, start_date: str,
              end_date: str = "", start_time: str = "", end_time: str = "",
              location: str = "", status: str = "Confirmed", officer_lead: str = "",
              description: str = "", rsvp_link: str = "", is_officer: bool = False) -> bool:
    """Add a new event record to the database."""
    try:
        ensure_data_initialized()
        df = load_events(season=None, is_officer=is_officer)

        # Generate sequential EventID
        existing_nums = []
        for eid in df["EventID"].dropna().astype(str):
            m = re.search(r"EVT-(\d+)", eid)
            if m:
                existing_nums.append(int(m.group(1)))
        next_num = max(existing_nums, default=0) + 1
        new_event_id = f"EVT-{next_num:03d}"

        clean_end_date = end_date.strip() if end_date and end_date.strip() else start_date.strip()

        new_row = {
            "EventID": new_event_id,
            "Season": season.strip() if season else CURRENT_SEASON,
            "Title": title.strip(),
            "EventType": event_type.strip() if event_type else "Other",
            "StartDate": start_date.strip(),
            "EndDate": clean_end_date,
            "StartTime": start_time.strip(),
            "EndTime": end_time.strip(),
            "Location": location.strip(),
            "Status": status.strip() if status else "Confirmed",
            "OfficerLead": officer_lead.strip(),
            "Description": description.strip(),
            "RsvpLink": rsvp_link.strip()
        }

        df_updated = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_events(df_updated, is_officer=is_officer)
        return True
    except Exception as e:
        print(f"Error adding event: {e}")
        return False


def update_event_status(event_id: str, new_status: str, is_officer: bool = False) -> bool:
    """Update status of an event in the events CSV."""
    try:
        df = load_events(season=None, is_officer=is_officer)
        idx = df[df["EventID"] == event_id].index
        if len(idx) > 0:
            df.loc[idx[0], "Status"] = new_status.strip()
            save_events(df, is_officer=is_officer)
            return True
        return False
    except Exception as e:
        print(f"Error updating event status: {e}")
        return False


def delete_event(event_id: str, is_officer: bool = False) -> bool:
    """Delete an event from the database by EventID."""
    try:
        df = load_events(season=None, is_officer=is_officer)
        idx = df[df["EventID"] == event_id].index
        if len(idx) > 0:
            df = df.drop(idx).reset_index(drop=True)
            save_events(df, is_officer=is_officer)
            return True
        return False
    except Exception as e:
        print(f"Error deleting event: {e}")
        return False


def generate_google_calendar_url(title: str, start_date: str, end_date: str = "",
                                start_time: str = "", end_time: str = "",
                                location: str = "", description: str = "") -> str:
    """Generate a 1-click 'Add to Google Calendar' template URL."""
    def _parse_d(val):
        if not val or str(val).strip().lower() in ["nan", "none", ""]:
            return None
        s = str(val).strip()
        for fmt in ["%Y-%m-%d", "%m-%d-%Y", "%m/%d/%Y", "%Y/%m/%d"]:
            try:
                return datetime.strptime(s[:10], fmt).date()
            except Exception:
                pass
        return None

    s_d = _parse_d(start_date)
    if not s_d:
        return "https://calendar.google.com/calendar"

    e_d = _parse_d(end_date) if end_date else s_d
    if not e_d:
        e_d = s_d

    fmt_dt = "%Y%m%dT%H%M%S"
    fmt_d = "%Y%m%d"

    is_timed = bool(start_time and str(start_time).strip().lower() not in ["", "none", "all day"])
    if is_timed:
        try:
            clean_st = str(start_time).strip()[:5]
            st_obj = datetime.strptime(clean_st, "%H:%M").time()
            s_dt = datetime.combine(s_d, st_obj)
            if end_time and str(end_time).strip().lower() not in ["", "none"]:
                clean_et = str(end_time).strip()[:5]
                et_obj = datetime.strptime(clean_et, "%H:%M").time()
                e_dt = datetime.combine(e_d, et_obj)
            else:
                e_dt = s_dt + timedelta(hours=1)
            dates_param = f"{s_dt.strftime(fmt_dt)}/{e_dt.strftime(fmt_dt)}"
        except Exception:
            dates_param = f"{s_d.strftime(fmt_d)}/{(e_d + timedelta(days=1)).strftime(fmt_d)}"
    else:
        # All day event: DTEND is exclusive
        dates_param = f"{s_d.strftime(fmt_d)}/{(e_d + timedelta(days=1)).strftime(fmt_d)}"

    params = {
        "action": "TEMPLATE",
        "text": title.strip(),
        "dates": dates_param,
        "details": description.strip(),
        "location": location.strip(),
        "sf": "true",
        "output": "xml"
    }
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(params)


def generate_unified_calendar_ical(events_df: pd.DataFrame = None, trips_df: pd.DataFrame = None,
                                   calendar_name: str = "UCSB Ski Team Schedule") -> str:
    """
    Generate RFC 5545 compliant iCalendar (.ics) string bundling scheduled trips and club events.
    Compatible with Apple Calendar, Google Calendar, and Microsoft Outlook.
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//UCSB Ski and Snowboard Team//Schedule//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{calendar_name}",
        "X-WR-TIMEZONE:America/Los_Angeles"
    ]

    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def _parse_d(val):
        if not val or str(val).strip().lower() in ["nan", "none", ""]:
            return None
        s = str(val).strip()
        for fmt in ["%Y-%m-%d", "%m-%d-%Y", "%m/%d/%Y", "%Y/%m/%d"]:
            try:
                return datetime.strptime(s[:10], fmt).date()
            except Exception:
                pass
        return None

    # 1. Add Trips
    if trips_df is not None and not trips_df.empty:
        for _, row in trips_df.iterrows():
            trip_id = str(row.get("TripID", "")).strip()
            trip_name = str(row.get("Name", "Ski Trip")).strip()
            destination = str(row.get("Destination", "")).strip()
            trip_type = str(row.get("TripType", "Recreational")).strip()
            status = str(row.get("Status", "Confirmed")).strip()
            notes = str(row.get("Notes", "")).strip()
            nights = int(row.get("Nights", 1)) if pd.notnull(row.get("Nights")) else 1

            start_dt = _parse_d(row.get("StartDate"))
            if not start_dt:
                continue

            end_dt = _parse_d(row.get("EndDate"))
            if not end_dt:
                end_dt = start_dt + timedelta(days=nights)

            exclusive_end_dt = end_dt + timedelta(days=1)
            dtstart_str = start_dt.strftime("%Y%m%d")
            dtend_str = exclusive_end_dt.strftime("%Y%m%d")
            uid = f"{trip_id or 'TRIP'}-{dtstart_str}@ucsbskiteam.com"

            date_str = start_dt.strftime("%b %d, %Y") if start_dt == end_dt else f"{start_dt.strftime('%b %d, %Y')} to {end_dt.strftime('%b %d, %Y')}"

            desc_lines = [
                f"Trip: {trip_name}",
                f"Type: {trip_type}",
                f"Destination: {destination}",
                f"Dates: {date_str}",
                f"Status: {status}"
            ]
            if notes and notes.lower() not in ["nan", "none", ""]:
                desc_lines.append(f"Notes: {notes}")

            description = "\\n".join(desc_lines)
            ical_status = "CONFIRMED"
            if status.lower() == "cancelled":
                ical_status = "CANCELLED"
            elif status.lower() == "planning":
                ical_status = "TENTATIVE"

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now_stamp}",
                f"DTSTART;VALUE=DATE:{dtstart_str}",
                f"DTEND;VALUE=DATE:{dtend_str}",
                f"SUMMARY:UCSB Ski Team: {trip_name}",
                f"DESCRIPTION:{description}",
                f"LOCATION:{destination}",
                f"STATUS:{ical_status}",
                "END:VEVENT"
            ])

    # 2. Add Events
    if events_df is not None and not events_df.empty:
        for _, row in events_df.iterrows():
            evt_id = str(row.get("EventID", "")).strip()
            title = str(row.get("Title", "Club Event")).strip()
            evt_type = str(row.get("EventType", "Event")).strip()
            location = str(row.get("Location", "")).strip()
            status = str(row.get("Status", "Confirmed")).strip()
            start_time = str(row.get("StartTime", "")).strip()
            end_time = str(row.get("EndTime", "")).strip()
            officer_lead = str(row.get("OfficerLead", "")).strip()
            desc = str(row.get("Description", "")).strip()
            rsvp = str(row.get("RsvpLink", "")).strip()

            start_dt = _parse_d(row.get("StartDate"))
            if not start_dt:
                continue

            end_dt = _parse_d(row.get("EndDate")) if row.get("EndDate") else start_dt
            if not end_dt:
                end_dt = start_dt

            uid = f"{evt_id or 'EVT'}-{start_dt.strftime('%Y%m%d')}@ucsbskiteam.com"

            desc_lines = [
                f"Event: {title}",
                f"Type: {evt_type}"
            ]
            if officer_lead:
                desc_lines.append(f"Host / Lead: {officer_lead}")
            if location:
                desc_lines.append(f"Location: {location}")
            if desc:
                desc_lines.append(f"Details: {desc}")
            if rsvp:
                desc_lines.append(f"RSVP / Link: {rsvp}")
            desc_lines.append(f"Status: {status}")

            description = "\\n".join(desc_lines)
            ical_status = "CONFIRMED"
            if status.lower() == "cancelled":
                ical_status = "CANCELLED"
            elif status.lower() == "planning":
                ical_status = "TENTATIVE"

            is_timed = bool(start_time and start_time.lower() not in ["", "none", "all day"])
            if is_timed:
                try:
                    clean_st = start_time[:5]
                    st_obj = datetime.strptime(clean_st, "%H:%M").time()
                    s_dt = datetime.combine(start_dt, st_obj)
                    if end_time and end_time.lower() not in ["", "none"]:
                        clean_et = end_time[:5]
                        et_obj = datetime.strptime(clean_et, "%H:%M").time()
                        e_dt = datetime.combine(end_dt, et_obj)
                    else:
                        e_dt = s_dt + timedelta(hours=1)

                    dtstart_str = s_dt.strftime("%Y%m%dT%H%M%S")
                    dtend_str = e_dt.strftime("%Y%m%dT%H%M%S")
                    lines.extend([
                        "BEGIN:VEVENT",
                        f"UID:{uid}",
                        f"DTSTAMP:{now_stamp}",
                        f"DTSTART;TZID=America/Los_Angeles:{dtstart_str}",
                        f"DTEND;TZID=America/Los_Angeles:{dtend_str}",
                        f"SUMMARY:UCSB Ski Team: {title}",
                        f"DESCRIPTION:{description}",
                        f"LOCATION:{location}",
                        f"STATUS:{ical_status}",
                        "END:VEVENT"
                    ])
                except Exception:
                    # Fallback to all-day
                    exclusive_end = end_dt + timedelta(days=1)
                    lines.extend([
                        "BEGIN:VEVENT",
                        f"UID:{uid}",
                        f"DTSTAMP:{now_stamp}",
                        f"DTSTART;VALUE=DATE:{start_dt.strftime('%Y%m%d')}",
                        f"DTEND;VALUE=DATE:{exclusive_end.strftime('%Y%m%d')}",
                        f"SUMMARY:UCSB Ski Team: {title}",
                        f"DESCRIPTION:{description}",
                        f"LOCATION:{location}",
                        f"STATUS:{ical_status}",
                        "END:VEVENT"
                    ])
            else:
                exclusive_end = end_dt + timedelta(days=1)
                lines.extend([
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    f"DTSTAMP:{now_stamp}",
                    f"DTSTART;VALUE=DATE:{start_dt.strftime('%Y%m%d')}",
                    f"DTEND;VALUE=DATE:{exclusive_end.strftime('%Y%m%d')}",
                    f"SUMMARY:UCSB Ski Team: {title}",
                    f"DESCRIPTION:{description}",
                    f"LOCATION:{location}",
                    f"STATUS:{ical_status}",
                    "END:VEVENT"
                ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
