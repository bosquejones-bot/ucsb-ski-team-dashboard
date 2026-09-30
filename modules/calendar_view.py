"""
Calendar View & Event Management module for the UCSB Ski Team Dashboard.
Integrates the official UCSB Ski and Snowboard Team Google Calendar.
In Demo Mode, a sample placeholder calendar is displayed to protect real team data.
When signed in with the officer password, the live team calendar is displayed with full sync links.
Strict rule: No emojis are used across any interface components.
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import urllib.parse
from datetime import datetime, date, timedelta
from config import (
    CURRENT_SEASON, THEME_COLORS,
    GOOGLE_CALENDAR_ID, DEMO_GOOGLE_CALENDAR_ID
)
from utils.data_manager import load_trips


def _parse_date_safe(val):
    """Safely parse a date string into a datetime.date object."""
    if not val or str(val).strip().lower() in ["nan", "none", ""]:
        return None
    s = str(val).strip()
    for fmt in ["%Y-%m-%d", "%m-%d-%Y", "%m/%d/%Y", "%Y/%m/%d"]:
        try:
            return datetime.strptime(s[:10], fmt).date()
        except Exception:
            pass
    return None


def _format_date_range(start_str: str, end_str: str = "") -> str:
    """Format start and end dates into a clean human-readable string without emojis."""
    s_d = _parse_date_safe(start_str)
    if not s_d:
        return start_str or "TBD"
    e_d = _parse_date_safe(end_str) if end_str else None

    if not e_d or s_d == e_d:
        return s_d.strftime("%a, %b %d, %Y")

    if s_d.year == e_d.year:
        if s_d.month == e_d.month:
            return f"{s_d.strftime('%b %d')} - {e_d.strftime('%d, %Y')}"
        return f"{s_d.strftime('%b %d')} - {e_d.strftime('%b %d, %Y')}"
    return f"{s_d.strftime('%b %d, %Y')} - {e_d.strftime('%b %d, %Y')}"


def render_calendar_tab(selected_season: str = CURRENT_SEASON, is_officer: bool = False, can_edit: bool = None):
    """Render the Team Calendar view with Google Calendar embed and Ski Trips overview."""
    if can_edit is None:
        can_edit = is_officer

    st.markdown(f"## Team Calendar & Schedule ({selected_season})")
    st.markdown("All official club meetings, dryland workouts, socials, competitions, and ski trips.")

    # Determine whether to use live team calendar or demo placeholder calendar
    if is_officer:
        active_cal_id = GOOGLE_CALENDAR_ID
        is_demo = False
    else:
        active_cal_id = DEMO_GOOGLE_CALENDAR_ID
        is_demo = True

    # Status / Access control banner
    if is_demo:
        st.info("Demo Mode Active: Displaying a sample placeholder calendar. Enter the officer password in the sidebar to view the live UCSB Ski and Snowboard Team Google Calendar and sync links.")
    else:
        st.success("Officer Mode Active: Connected to the live UCSB Ski and Snowboard Team Google Calendar.")

    # Tabs: Team Google Calendar & Ski Trips Schedule
    tab_gcal, tab_trips = st.tabs([
        "Team Google Calendar",
        "Ski Trips Schedule"
    ])

    # =========================================================================
    # TAB 1: TEAM GOOGLE CALENDAR
    # =========================================================================
    with tab_gcal:
        encoded_cal_id = urllib.parse.quote(active_cal_id)
        gcal_sub_url = f"https://calendar.google.com/calendar/render?cid={encoded_cal_id}"
        gcal_open_url = f"https://calendar.google.com/calendar/u/0/r?cid={encoded_cal_id}"
        ical_http_url = f"https://calendar.google.com/calendar/ical/{encoded_cal_id}/public/basic.ics"
        webcal_url = f"webcal://calendar.google.com/calendar/ical/{encoded_cal_id}/public/basic.ics"

        c_act1, c_act2, c_act3, c_act4 = st.columns([1.5, 1.4, 1.5, 1.6])
        with c_act1:
            if is_officer:
                st.link_button("Subscribe in Google Calendar", gcal_sub_url, width="stretch", help="1-click add to your personal Google Calendar account")
            else:
                st.link_button("Subscribe to Demo Calendar", gcal_sub_url, width="stretch", help="Subscribe to sample calendar (unlock Officer Mode for team calendar)")
        with c_act2:
            st.link_button("Open Full Page", gcal_open_url, width="stretch", help="Open Google Calendar in a full-screen browser tab")
        with c_act3:
            with st.popover("Apple / iPhone Sync", width="stretch"):
                if is_officer:
                    st.markdown("##### Subscribe on Apple Calendar (iPhone / Mac) & Outlook")
                    st.markdown("Click below on your Apple device or copy the subscription feed URL:")
                    st.link_button("Subscribe with Apple Calendar", webcal_url, width="stretch")
                    st.caption("Or paste this URL into Apple Calendar (`File > New Calendar Subscription`) or Outlook:")
                    st.code(ical_http_url, language="text")
                else:
                    st.markdown("##### Apple Calendar / iPhone Sync")
                    st.caption("Enter the officer password in the sidebar to unlock the 1-click subscription link and iCal feed for the live team calendar.")
        with c_act4:
            if is_officer:
                st.link_button("Add Event in Google Cal", "https://calendar.google.com/calendar/u/0/r/eventedit", width="stretch", help="Open Google Calendar to create a new team event")
            else:
                st.caption(f"Placeholder: `{active_cal_id.split('@')[0][:18]}...`")

        if is_officer:
            st.caption("Officer Workflow: All events are created, updated, and deleted directly in Google Calendar (via phone app or desktop). Changes automatically sync live to this dashboard.")

        # Embed Google Calendar with clean display parameters
        embed_src = (
            f"https://calendar.google.com/calendar/embed?"
            f"src={encoded_cal_id}&"
            f"ctz=America%2FLos_Angeles&"
            f"showTitle=0&"
            f"showNav=1&"
            f"showDate=1&"
            f"showPrint=0&"
            f"showTabs=1&"
            f"showCalendars=0&"
            f"showTz=1"
        )

        components.iframe(embed_src, height=750, scrolling=True)

    # =========================================================================
    # TAB 2: SKI TRIPS SCHEDULE (FROM TRIP CREATOR)
    # =========================================================================
    with tab_trips:
        st.markdown(f"### Scheduled Ski Trips ({selected_season})")
        st.markdown("Official multi-day ski trips, training camps, and competitions planned in the Trip Creator.")

        trips_df = load_trips(season=selected_season, is_officer=is_officer)

        if trips_df.empty:
            st.info(f"No ski trips scheduled yet for {selected_season}. Plan upcoming trips under the 'Trip Creator' tab.")
        else:
            for _, tr in trips_df.iterrows():
                with st.container():
                    col_tr1, col_tr2, col_tr3 = st.columns([2.8, 2.2, 1.5])
                    with col_tr1:
                        st.markdown(f"#### {tr.get('Name', 'Ski Trip')}")
                        st.markdown(f"Destination: **{tr.get('Destination', 'TBD')}**")
                        notes_t = str(tr.get('Notes', '')).strip()
                        if notes_t and notes_t.lower() != 'nan':
                            st.caption(f"Notes: {notes_t}")
                    with col_tr2:
                        d_range = _format_date_range(str(tr.get('StartDate', '')), str(tr.get('EndDate', '')))
                        st.markdown(f"**Dates:** {d_range}")
                        st.caption(f"Status: **{tr.get('Status', 'Confirmed')}** | Duration: {tr.get('Nights', 1)} Nights")
                    with col_tr3:
                        tot_cost = float(tr.get('TotalCost', 0)) if pd.notnull(tr.get('TotalCost')) else 0.0
                        att = int(tr.get('Attendees', 1)) if pd.notnull(tr.get('Attendees')) else 1
                        st.metric("Total Budget", f"${tot_cost:,.0f}", f"~${tot_cost/max(1, att):,.0f} / skier")
                    st.divider()

        st.caption("To modify lodging costs, add driver vehicles, or view athlete attendee rosters, head to the 'Trip Creator' tab.")
