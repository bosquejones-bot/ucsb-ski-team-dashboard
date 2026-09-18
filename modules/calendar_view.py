"""
Calendar View & Event Management module for the UCSB Ski Team Dashboard.
Provides a unified schedule of ski trips and non-trip club events (meetings,
socials, workouts, races, clinics), monthly visual calendar view, in-place
table event editing, 1-click Google Calendar integration, universal .ics export,
and officer event scheduling.
Strict rule: No emojis are used across any interface components.
"""

import streamlit as st
import pandas as pd
import urllib.parse
import calendar as py_calendar
from datetime import datetime, date, timedelta
from config import (
    CURRENT_SEASON, EVENT_TYPES, EVENT_STATUS_OPTIONS,
    TRIP_STATUS_OPTIONS, DESTINATIONS, THEME_COLORS
)
from utils.data_manager import (
    load_events, save_events, add_event, update_event_status, delete_event,
    load_trips, update_trip_status, delete_trip, load_members,
    generate_trips_ical, generate_unified_calendar_ical, generate_google_calendar_url
)


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


def _format_time_range(start_t: str, end_t: str = "") -> str:
    """Format military time strings (e.g. 19:00) into 12-hour AM/PM format."""
    def _conv(t_str):
        if not t_str or str(t_str).strip().lower() in ["nan", "none", "", "all day"]:
            return ""
        clean = str(t_str).strip()[:5]
        try:
            t_obj = datetime.strptime(clean, "%H:%M").time()
            return t_obj.strftime("%I:%M %p").lstrip("0")
        except Exception:
            return t_str

    s_fmt = _conv(start_t)
    e_fmt = _conv(end_t)
    if s_fmt and e_fmt:
        return f"{s_fmt} - {e_fmt}"
    if s_fmt:
        return s_fmt
    return "All Day"


def _get_type_tag(category: str, item_type: str) -> str:
    """Return clean bracketed text tag for item category (no emojis)."""
    if item_type == "Trip":
        return f"[Trip - {category}]"
    cat_lower = str(category).lower()
    if "meeting" in cat_lower:
        return "[Meeting]"
    if "social" in cat_lower:
        return "[Social]"
    if "dryland" in cat_lower or "fitness" in cat_lower or "workout" in cat_lower:
        return "[Dryland]"
    if "comp" in cat_lower or "race" in cat_lower:
        return "[Competition]"
    if "clinic" in cat_lower or "workshop" in cat_lower or "wax" in cat_lower:
        return "[Clinic]"
    if "fundrais" in cat_lower or "merch" in cat_lower:
        return "[Fundraiser]"
    return f"[{category}]"


def render_calendar_tab(selected_season: str = CURRENT_SEASON, is_officer: bool = False, can_edit: bool = None):
    """Render the Team Calendar & Events view with timeline, monthly calendar, and event scheduling."""
    if can_edit is None:
        can_edit = is_officer
    st.markdown(f"## Team Calendar & Events Schedule ({selected_season})")
    st.markdown("All official ski trips, club meetings, socials, dryland workouts, and team activities in one synchronized calendar.")

    # Load data for selected season
    trips_df = load_trips(season=selected_season, is_officer=is_officer)
    events_df = load_events(season=selected_season if selected_season != "All Seasons" else None, is_officer=is_officer)
    dest_options = list(DESTINATIONS.keys()) + ["Other"]

    # Build unified items list for timeline and monthly calendar
    unified_items = []

    # 1. Trips
    if not trips_df.empty:
        for _, trip in trips_df.iterrows():
            s_d = _parse_date_safe(trip.get("StartDate"))
            if not s_d:
                continue
            nights = int(trip.get("Nights", 1)) if pd.notnull(trip.get("Nights")) else 1
            e_d = _parse_date_safe(trip.get("EndDate")) or (s_d + timedelta(days=nights))
            tot_c = float(trip.get("TotalCost", 0)) if pd.notnull(trip.get("TotalCost")) else 0.0
            att = int(trip.get("Attendees", 1)) if pd.notnull(trip.get("Attendees")) else 1
            per_skier = tot_c / max(1, att)

            notes_val = str(trip.get("Notes", "")).strip()
            desc = f"Destination: {trip.get('Destination', '')} | {nights} Nights | Budget: ${tot_c:,.0f} (~${per_skier:,.0f} / skier)"
            if notes_val and notes_val.lower() != "nan":
                desc += f"\nNotes: {notes_val}"

            unified_items.append({
                "ID": str(trip.get("TripID", "")),
                "ItemType": "Trip",
                "Category": str(trip.get("TripType", "Recreational")),
                "Title": str(trip.get("Name", "Ski Trip")),
                "StartDate": str(trip.get("StartDate", "")),
                "EndDate": str(trip.get("EndDate", "")) or e_d.strftime("%Y-%m-%d"),
                "StartDateObj": s_d,
                "EndDateObj": e_d,
                "StartTime": "",
                "EndTime": "",
                "Location": str(trip.get("Destination", "")),
                "Status": str(trip.get("Status", "Confirmed")),
                "Description": desc,
                "RsvpLink": "",
                "Season": str(trip.get("Season", selected_season)),
                "Raw": trip
            })

    # 2. Events
    if not events_df.empty:
        for _, evt in events_df.iterrows():
            s_d = _parse_date_safe(evt.get("StartDate"))
            if not s_d:
                continue
            e_d = _parse_date_safe(evt.get("EndDate")) or s_d

            unified_items.append({
                "ID": str(evt.get("EventID", "")),
                "ItemType": "Event",
                "Category": str(evt.get("EventType", "Other")),
                "Title": str(evt.get("Title", "Club Event")),
                "StartDate": str(evt.get("StartDate", "")),
                "EndDate": str(evt.get("EndDate", "")) or e_d.strftime("%Y-%m-%d"),
                "StartDateObj": s_d,
                "EndDateObj": e_d,
                "StartTime": str(evt.get("StartTime", "")),
                "EndTime": str(evt.get("EndTime", "")),
                "Location": str(evt.get("Location", "")),
                "Status": str(evt.get("Status", "Confirmed")),
                "Description": str(evt.get("Description", "")),
                "RsvpLink": str(evt.get("RsvpLink", "")),
                "Season": str(evt.get("Season", selected_season)),
                "Raw": evt
            })

    # Sort all items chronologically
    unified_items.sort(key=lambda x: (x["StartDateObj"], x["StartTime"] or "00:00"))

    # Three tabs: Master Schedule, Monthly Calendar View, Schedule New Event
    tab_timeline, tab_month, tab_new_event = st.tabs([
        "Master Schedule & Timeline",
        "Monthly Calendar View",
        "Schedule New Event"
    ])

    # =========================================================================
    # TAB 1: MASTER SCHEDULE & TIMELINE (WITH IN-PLACE EVENT EDITING IN TABLE)
    # =========================================================================
    with tab_timeline:
        today = date.today()

        # Find Next Upcoming Item
        upcoming_items = [
            it for it in unified_items
            if it["EndDateObj"] >= today and it["Status"].lower() != "cancelled"
        ]
        next_item = upcoming_items[0] if upcoming_items else None

        # --- NEXT EVENT COUNTDOWN HERO BANNER (NO EMOJIS) ---
        if next_item:
            days_diff = (next_item["StartDateObj"] - today).days
            if next_item["StartDateObj"] <= today <= next_item["EndDateObj"]:
                countdown_badge = '<span style="background: #38a169; color: white; padding: 4px 12px; border-radius: 16px; font-weight: 700; font-size: 0.85rem;">Happening Now</span>'
            elif days_diff == 1:
                countdown_badge = '<span style="background: #4a72b8; color: white; padding: 4px 12px; border-radius: 16px; font-weight: 700; font-size: 0.85rem;">Tomorrow</span>'
            elif days_diff == 0:
                countdown_badge = '<span style="background: #38a169; color: white; padding: 4px 12px; border-radius: 16px; font-weight: 700; font-size: 0.85rem;">Today</span>'
            else:
                countdown_badge = f'<span style="background: #33406a; color: #d9e2ec; padding: 4px 12px; border-radius: 16px; font-weight: 700; font-size: 0.85rem;">In {days_diff} Days</span>'

            tag_label = _get_type_tag(next_item["Category"], next_item["ItemType"])
            tag_badge = f'<span style="background: rgba(74, 114, 184, 0.35); border: 1px solid #4a72b8; color: #d9e2ec; padding: 3px 10px; border-radius: 12px; font-size: 0.85rem; font-weight: 600; margin-right: 8px; vertical-align: middle;">{tag_label}</span>'
            date_display = _format_date_range(next_item["StartDate"], next_item["EndDate"])
            time_display = _format_time_range(next_item["StartTime"], next_item["EndTime"]) if next_item["StartTime"] else ""

            loc_val = str(next_item.get("Location", "")).strip()
            has_loc = bool(loc_val and loc_val.lower() != "nan")

            detail_spans = [f"<span>Date: <strong>{date_display}</strong></span>"]
            if time_display:
                detail_spans.append(f"<span>Time: <strong>{time_display}</strong></span>")
            if has_loc:
                detail_spans.append(f"<span>Location: <strong>{loc_val}</strong></span>")
            details_html = "".join(detail_spans)

            hero_html = (
                '<div style="background: linear-gradient(135deg, rgba(30, 41, 68, 0.95) 0%, rgba(20, 27, 46, 0.95) 100%); '
                'border: 1px solid #4a72b8; border-radius: 12px; padding: 18px 24px; margin-bottom: 24px;">'
                '<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">'
                '<span style="font-size: 0.85rem; font-weight: 600; color: #8ea4c8; text-transform: uppercase; letter-spacing: 0.05em;">Next Upcoming Team Event</span>'
                f'<div>{countdown_badge}</div>'
                '</div>'
                f'<div style="font-size: 1.4rem; font-weight: 700; color: #f0f4f8; margin-bottom: 8px; line-height: 1.3;">'
                f'{tag_badge}{next_item["Title"]}'
                '</div>'
                '<div style="display: flex; gap: 16px; flex-wrap: wrap; font-size: 0.95rem; color: #d9e2ec; margin-bottom: 4px;">'
                f'{details_html}'
                '</div>'
                '</div>'
            )
            st.markdown(hero_html, unsafe_allow_html=True)

            # Quick action buttons for the hero event (no emojis)
            b1, b2, b3 = st.columns([1.6, 1.6, 2.8])
            with b1:
                gcal_hero_url = generate_google_calendar_url(
                    title=f"UCSB Ski Team: {next_item['Title']}",
                    start_date=next_item["StartDate"],
                    end_date=next_item["EndDate"],
                    start_time=next_item["StartTime"],
                    end_time=next_item["EndTime"],
                    location=loc_val if has_loc else "",
                    description=next_item["Description"]
                )
                st.link_button("Add to Google Calendar", gcal_hero_url, width="stretch")
            with b2:
                rsvp_val = str(next_item.get("RsvpLink", "")).strip()
                if has_loc:
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(loc_val)}"
                    st.link_button("Open in Google Maps", maps_url, width="stretch")
                elif rsvp_val and rsvp_val.lower() != "nan":
                    st.link_button("RSVP / Sign Up", rsvp_val, width="stretch")
            with b3:
                pass
            st.write("")
        else:
            no_event_html = (
                '<div style="background: linear-gradient(135deg, rgba(30, 41, 68, 0.6) 0%, rgba(20, 27, 46, 0.6) 100%); '
                'border: 1px dashed #33406a; border-radius: 12px; padding: 18px 24px; margin-bottom: 24px;">'
                '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">'
                '<span style="font-size: 0.85rem; font-weight: 600; color: #8ea4c8; text-transform: uppercase; letter-spacing: 0.05em;">Next Upcoming Team Event</span>'
                '<span style="background: #283552; color: #8ea4c8; padding: 4px 12px; border-radius: 16px; font-weight: 600; font-size: 0.85rem;">No Pending Events</span>'
                '</div>'
                f'<div style="font-size: 1.15rem; font-weight: 600; color: #d9e2ec;">No upcoming events or trips scheduled for season {selected_season}.</div>'
                '<div style="font-size: 0.85rem; color: #8ea4c8; margin-top: 4px;">Switch the viewing season in the sidebar or use Schedule New Event to plan upcoming activities.</div>'
                '</div>'
            )
            st.markdown(no_event_html, unsafe_allow_html=True)

        # --- FILTERS & EXPORT TOOLBAR ---
        col_f1, col_f2, col_view, col_exp = st.columns([1.6, 1.4, 1.4, 1.6])
        all_categories = ["All Categories", "Trips Only"] + EVENT_TYPES
        with col_f1:
            cat_filter = st.selectbox("Filter by Category", all_categories, key="cal_cat_filter")
        with col_f2:
            stat_filter = st.selectbox("Filter by Status", ["All Statuses", "Confirmed", "Planning", "Completed", "Cancelled"], key="cal_stat_filter")
        with col_view:
            view_style = st.radio("Display Format", ["Timeline Cards", "Table View"], horizontal=True, key="cal_view_style")

        # Filter items
        filtered_items = unified_items.copy()
        if cat_filter == "Trips Only":
            filtered_items = [it for it in filtered_items if it["ItemType"] == "Trip"]
        elif cat_filter != "All Categories":
            filtered_items = [it for it in filtered_items if it["Category"] == cat_filter]

        if stat_filter != "All Statuses":
            filtered_items = [it for it in filtered_items if it["Status"].lower() == stat_filter.lower()]

        with col_exp:
            st.write("")
            st.write("")
            cal_title = f"UCSB Ski Team Schedule - {selected_season}" if selected_season != "All Seasons" else "UCSB Ski Team Schedule"
            f_event_ids = {it["ID"] for it in filtered_items if it["ItemType"] == "Event"}
            f_trip_ids = {it["ID"] for it in filtered_items if it["ItemType"] == "Trip"}
            exp_events = events_df[events_df["EventID"].isin(f_event_ids)] if not events_df.empty else None
            exp_trips = trips_df[trips_df["TripID"].isin(f_trip_ids)] if not trips_df.empty else None

            unified_ics_data = generate_unified_calendar_ical(
                events_df=exp_events,
                trips_df=exp_trips,
                calendar_name=cal_title
            )
            season_slug = selected_season.lower().replace(" ", "_").replace("-", "_")
            st.download_button(
                label="Export Calendar (.ics)",
                data=unified_ics_data,
                file_name=f"ucsb_ski_team_schedule_{season_slug}.ics",
                mime="text/calendar",
                use_container_width=True,
                help="Download full team calendar (trips and events) as an RFC 5545 .ics file compatible with Google Calendar, Apple Calendar, and Outlook."
            )

        st.caption(f"Showing **{len(filtered_items)}** scheduled item(s) for season **{selected_season}**")

        if not filtered_items:
            st.info(f"No events or trips match the selected filters for '{selected_season}'.")
        else:
            if view_style == "Table View":
                # =============================================================
                # IN-PLACE EDITABLE EVENTS TABLE + TRIPS TABLE (NO HOST/LEAD)
                # =============================================================
                st.markdown("#### Club Events (Editable in Table)")
                if can_edit:
                    st.caption("Double-click any cell to edit event details in-place. Changes are saved immediately to the events database.")
                else:
                    st.caption("Club events table. Officer login with Editing Mode enabled is required to edit event details.")

                # Filter original events_df based on active category/status filter
                f_event_ids = [it["ID"] for it in filtered_items if it["ItemType"] == "Event"]
                raw_events_season = load_events(season=selected_season if selected_season != "All Seasons" else None, is_officer=is_officer)
                filtered_events_for_edit = raw_events_season[raw_events_season["EventID"].isin(f_event_ids)].copy()

                if filtered_events_for_edit.empty:
                    st.info("No non-trip club events match the current filter.")
                else:
                    # Select columns for editor (strictly NO Host/Lead column)
                    edit_cols = [
                        "EventID", "Title", "EventType", "StartDate", "EndDate",
                        "StartTime", "EndTime", "Location", "Status", "Description", "RsvpLink"
                    ]
                    available_edit_cols = [c for c in edit_cols if c in filtered_events_for_edit.columns]
                    editor_input_df = filtered_events_for_edit[available_edit_cols].copy()

                    # Data editor configuration
                    col_config = {
                        "EventID": st.column_config.TextColumn("ID", disabled=True),
                        "Title": st.column_config.TextColumn("Title", required=True),
                        "EventType": st.column_config.SelectboxColumn("Category", options=EVENT_TYPES, required=True),
                        "StartDate": st.column_config.TextColumn("Start Date (YYYY-MM-DD)", required=True),
                        "EndDate": st.column_config.TextColumn("End Date (YYYY-MM-DD)"),
                        "StartTime": st.column_config.TextColumn("Start Time (HH:MM)"),
                        "EndTime": st.column_config.TextColumn("End Time (HH:MM)"),
                        "Location": st.column_config.TextColumn("Location"),
                        "Status": st.column_config.SelectboxColumn("Status", options=EVENT_STATUS_OPTIONS, required=True),
                        "Description": st.column_config.TextColumn("Description"),
                        "RsvpLink": st.column_config.TextColumn("RSVP / Link")
                    }

                    edited_result = st.data_editor(
                        editor_input_df,
                        column_config=col_config,
                        disabled=not can_edit,
                        width="stretch",
                        hide_index=True,
                        key=f"events_tbl_editor_{selected_season}"
                    )

                    # Persist changes when officer modifies values
                    if can_edit:
                        btn_col, _ = st.columns([1.5, 4.5])
                        with btn_col:
                            if st.button("Save Event Edits", type="primary", use_container_width=True, key="btn_save_tbl_events"):
                                # Merge edits back to master events file
                                all_events_master = load_events(season=None, is_officer=is_officer)
                                for _, e_row in edited_result.iterrows():
                                    eid = str(e_row.get("EventID", "")).strip()
                                    m_idx = all_events_master[all_events_master["EventID"] == eid].index
                                    if len(m_idx) > 0:
                                        for c in available_edit_cols:
                                            if c != "EventID":
                                                all_events_master.at[m_idx[0], c] = str(e_row.get(c, "")).strip()
                                save_events(all_events_master, is_officer=is_officer)
                                st.success("Event details saved successfully.")
                                st.rerun()

                st.divider()

                # --- SCHEDULED TRIPS TABLE (NO HOST/LEAD) ---
                st.markdown("#### Scheduled Ski Trips")
                f_trip_ids = [it["ID"] for it in filtered_items if it["ItemType"] == "Trip"]
                trips_match = trips_df[trips_df["TripID"].isin(f_trip_ids)].copy() if not trips_df.empty else pd.DataFrame()
                if trips_match.empty:
                    st.info("No trips match the current filter.")
                else:
                    trip_disp_cols = ["TripID", "Name", "Destination", "TripType", "StartDate", "EndDate", "Nights", "Attendees", "TotalCost", "Status"]
                    if selected_season == "All Seasons":
                        trip_disp_cols = ["Season"] + trip_disp_cols

                    t_view_df = trips_match[[c for c in trip_disp_cols if c in trips_match.columns]].copy()
                    t_view_df["TotalCost"] = t_view_df["TotalCost"].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "$0.00")
                    t_view_df.columns = [c.replace("TripType", "Type").replace("TotalCost", "Total Budget") for c in t_view_df.columns]
                    st.dataframe(t_view_df, width="stretch", hide_index=True)

            else:
                # =============================================================
                # TIMELINE CARDS VIEW (NO EMOJIS, NO HOST/LEAD)
                # =============================================================
                for it in filtered_items:
                    tag_lbl = _get_type_tag(it["Category"], it["ItemType"])
                    date_lbl = _format_date_range(it["StartDate"], it["EndDate"])
                    time_lbl = _format_time_range(it["StartTime"], it["EndTime"]) if it["StartTime"] else ""
                    is_past = it["EndDateObj"] < today

                    with st.container():
                        c_main, c_actions = st.columns([3.3, 1.3])
                        with c_main:
                            title_prefix = "~~" if is_past else ""
                            title_suffix = "~~ *(Past)*" if is_past else ""
                            st.markdown(f"#### {title_prefix}{it['Title']}{title_suffix}")

                            badge_style = "background: rgba(93, 104, 149, 0.2); border: 1px solid #33406a; color: #8ea4c8;"
                            if it["ItemType"] == "Trip":
                                badge_style = "background: rgba(74, 114, 184, 0.25); border: 1px solid #4a72b8; color: #d9e2ec;"

                            stat_color = "#38a169" if it["Status"] == "Confirmed" else ("#e53e3e" if it["Status"] == "Cancelled" else "#d69e2e")

                            st.markdown(
                                f'<span style="{badge_style} padding: 3px 8px; border-radius: 6px; font-size: 0.8rem; font-weight: 600;">{it["ItemType"]}: {it["Category"]}</span> '
                                f'<span style="background: rgba(255,255,255,0.05); border: 1px solid {stat_color}; color: {stat_color}; padding: 3px 8px; border-radius: 6px; font-size: 0.8rem; font-weight: 600;">{it["Status"]}</span>',
                                unsafe_allow_html=True
                            )

                            # Details (Strictly NO Host/Lead display)
                            detail_items = [f"Date: **{date_lbl}**"]
                            if time_lbl:
                                detail_items.append(f"Time: {time_lbl}")
                            if it["Location"]:
                                detail_items.append(f"Location: {it['Location']}")

                            st.markdown(" &bull; ".join(detail_items))

                            if it["Description"] and str(it["Description"]).strip() and str(it["Description"]).lower() != 'nan':
                                st.caption(it["Description"])

                        with c_actions:
                            st.write("")
                            gcal_url = generate_google_calendar_url(
                                title=f"UCSB Ski Team: {it['Title']}",
                                start_date=it["StartDate"],
                                end_date=it["EndDate"],
                                start_time=it["StartTime"],
                                end_time=it["EndTime"],
                                location=it["Location"],
                                description=it["Description"]
                            )
                            st.link_button("Add to Google Calendar", gcal_url, use_container_width=True, key=f"gcal_btn_{it['ID']}")

                            if it["Location"]:
                                maps_link = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(it['Location'])}"
                                st.link_button("Google Maps", maps_link, use_container_width=True, key=f"maps_btn_{it['ID']}")

                            if it["RsvpLink"]:
                                st.link_button("RSVP / Sign Up", it["RsvpLink"], use_container_width=True, key=f"rsvp_btn_{it['ID']}")

                        st.divider()

    # =========================================================================
    # TAB 2: MONTHLY CALENDAR VIEW (REPLACES ALL SCHEDULED TRIPS)
    # =========================================================================
    with tab_month:
        st.markdown(f"### Monthly Calendar View ({selected_season})")
        st.markdown("Interactive monthly grid displaying all multi-day ski trips and scheduled club events.")

        today = date.today()
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]

        # Determine year options based on selected season
        if selected_season == "2025-2026":
            season_years = [2025, 2026]
        elif selected_season == "2026-2027":
            season_years = [2026, 2027]
        else:
            season_years = [2025, 2026, 2027]

        # Initialize session state keys for month and year navigation
        if "sb_cal_month" not in st.session_state:
            st.session_state["sb_cal_month"] = month_names[today.month - 1]
        if "sb_cal_year" not in st.session_state:
            st.session_state["sb_cal_year"] = today.year if today.year in season_years else season_years[-1]

        all_years = sorted(list(set(season_years + [2024, 2025, 2026, 2027, 2028, today.year, st.session_state["sb_cal_year"]])))

        def _on_prev_click():
            curr_m = month_names.index(st.session_state["sb_cal_month"]) + 1
            curr_y = st.session_state["sb_cal_year"]
            if curr_m == 1:
                st.session_state["sb_cal_month"] = month_names[11]
                st.session_state["sb_cal_year"] = curr_y - 1
            else:
                st.session_state["sb_cal_month"] = month_names[curr_m - 2]

        def _on_next_click():
            curr_m = month_names.index(st.session_state["sb_cal_month"]) + 1
            curr_y = st.session_state["sb_cal_year"]
            if curr_m == 12:
                st.session_state["sb_cal_month"] = month_names[0]
                st.session_state["sb_cal_year"] = curr_y + 1
            else:
                st.session_state["sb_cal_month"] = month_names[curr_m]

        def _on_today_click():
            st.session_state["sb_cal_month"] = month_names[today.month - 1]
            st.session_state["sb_cal_year"] = today.year

        # Month and Year Navigation Controls
        c_prev, c_m_sel, c_y_sel, c_next, c_today = st.columns([1.0, 2.2, 1.8, 1.0, 1.2])

        with c_prev:
            st.write("")
            st.write("")
            st.button("< Prev", key="btn_prev_month", on_click=_on_prev_click, use_container_width=True)

        with c_m_sel:
            st.selectbox("Month", month_names, key="sb_cal_month")

        with c_y_sel:
            if st.session_state["sb_cal_year"] not in all_years:
                all_years.append(st.session_state["sb_cal_year"])
                all_years.sort()
            st.selectbox("Year", all_years, key="sb_cal_year")

        with c_next:
            st.write("")
            st.write("")
            st.button("Next >", key="btn_next_month", on_click=_on_next_click, use_container_width=True)

        with c_today:
            st.write("")
            st.write("")
            st.button("Today", key="btn_today_month", on_click=_on_today_click, use_container_width=True)

        month_label = st.session_state["sb_cal_month"]
        cal_year = st.session_state["sb_cal_year"]
        cal_month = month_names.index(month_label) + 1

        st.markdown(f"#### {month_label} {cal_year}")

        # Calendar matrix with Sunday as first day of the week
        cal_matrix = py_calendar.Calendar(firstweekday=6).monthdayscalendar(cal_year, cal_month)
        weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

        # Day Headers
        hdr_cols = st.columns(7)
        for i, wd in enumerate(weekdays):
            with hdr_cols[i]:
                st.markdown(
                    f"<div style='text-align: center; font-weight: 700; color: #8ea4c8; padding: 6px; background: #171f30; border: 1px solid #283552; border-radius: 6px; margin-bottom: 6px;'>{wd}</div>",
                    unsafe_allow_html=True
                )

        # Helper to find items active on a given date
        def _get_items_for_day(d_obj: date):
            matches = []
            for it in unified_items:
                if it["StartDateObj"] <= d_obj <= it["EndDateObj"]:
                    matches.append(it)
            return matches

        # Render Calendar Grid
        for week in cal_matrix:
            w_cols = st.columns(7)
            for col_idx, day_num in enumerate(week):
                with w_cols[col_idx]:
                    if day_num == 0:
                        st.markdown(
                            "<div style='background: rgba(14, 19, 31, 0.4); border: 1px dashed #283552; border-radius: 8px; min-height: 90px; margin-bottom: 8px;'></div>",
                            unsafe_allow_html=True
                        )
                    else:
                        day_date = date(cal_year, cal_month, day_num)
                        is_today = (day_date == today)
                        active_items = _get_items_for_day(day_date)

                        cell_border = "1px solid #4a72b8" if is_today else "1px solid #283552"
                        cell_bg = "rgba(74, 114, 184, 0.12)" if is_today else "#171f30"

                        today_pill = "<span style='background: #4a72b8; color: white; padding: 1px 5px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; float: right;'>Today</span>" if is_today else ""

                        item_html_parts = []
                        for it in active_items[:3]:
                            if it["ItemType"] == "Trip":
                                item_style = "background: rgba(74, 114, 184, 0.35); border-left: 3px solid #4a72b8; color: #d9e2ec;"
                                item_title = f"[Trip] {it['Title']}"
                            else:
                                item_style = "background: rgba(93, 104, 149, 0.25); border-left: 3px solid #5d6895; color: #f0f4f8;"
                                t_str = f" ({it['StartTime'][:5]})" if it["StartTime"] else ""
                                item_title = f"[{it['Category']}]{t_str} {it['Title']}"

                            item_html_parts.append(
                                f"<div style='{item_style} padding: 2px 5px; border-radius: 3px; font-size: 0.72rem; margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;' title='{it['Title']} - {it['Location']}'>{item_title}</div>"
                            )

                        if len(active_items) > 3:
                            item_html_parts.append(
                                f"<div style='font-size: 0.7rem; color: #8ea4c8; margin-top: 2px;'>+{len(active_items) - 3} more...</div>"
                            )

                        items_content = "".join(item_html_parts)

                        st.markdown(
                            f"""
                            <div style="background: {cell_bg}; border: {cell_border}; border-radius: 8px; padding: 6px; min-height: 90px; margin-bottom: 8px;">
                                <div style="font-weight: 700; font-size: 0.85rem; color: #f0f4f8; margin-bottom: 2px;">
                                    {day_num} {today_pill}
                                </div>
                                {items_content}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

        st.divider()

        # --- DETAILED ACTIVITIES LIST FOR SELECTED MONTH ---
        st.markdown(f"#### Scheduled Activities in {month_label} {cal_year}")
        month_start = date(cal_year, cal_month, 1)
        _, last_day = py_calendar.monthrange(cal_year, cal_month)
        month_end = date(cal_year, cal_month, last_day)

        month_items = [
            it for it in unified_items
            if it["StartDateObj"] <= month_end and it["EndDateObj"] >= month_start
        ]

        if not month_items:
            st.info(f"No events or ski trips scheduled for {month_label} {cal_year}.")
        else:
            for it in month_items:
                tag_lbl = _get_type_tag(it["Category"], it["ItemType"])
                date_lbl = _format_date_range(it["StartDate"], it["EndDate"])
                time_lbl = _format_time_range(it["StartTime"], it["EndTime"]) if it["StartTime"] else ""

                with st.container():
                    c_m1, c_m2 = st.columns([3.3, 1.3])
                    with c_m1:
                        st.markdown(f"**{tag_lbl} {it['Title']}**")
                        detail_strs = [f"Date: **{date_lbl}**"]
                        if time_lbl:
                            detail_strs.append(f"Time: {time_lbl}")
                        if it["Location"]:
                            detail_strs.append(f"Location: {it['Location']}")
                        detail_strs.append(f"Status: {it['Status']}")
                        st.caption(" | ".join(detail_strs))
                        if it["Description"] and str(it["Description"]).strip() and str(it["Description"]).lower() != 'nan':
                            st.write(it["Description"])
                    with c_m2:
                        st.write("")
                        gcal_url = generate_google_calendar_url(
                            title=f"UCSB Ski Team: {it['Title']}",
                            start_date=it["StartDate"],
                            end_date=it["EndDate"],
                            start_time=it["StartTime"],
                            end_time=it["EndTime"],
                            location=it["Location"],
                            description=it["Description"]
                        )
                        st.link_button("Add to Google Calendar", gcal_url, use_container_width=True, key=f"month_gcal_{it['ID']}")
                        if it["Location"]:
                            maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(it['Location'])}"
                            st.link_button("Google Maps", maps_url, use_container_width=True, key=f"month_maps_{it['ID']}")
                    st.divider()

    # =========================================================================
    # TAB 3: SCHEDULE NEW EVENT & MANAGE EVENTS (NO HOST/LEAD, NO EMOJIS)
    # =========================================================================
    with tab_new_event:
        st.markdown(f"### Schedule New Club Event ({selected_season})")
        st.markdown("Create non-trip team events such as club meetings, socials, dryland fitness workouts, race competitions, and wax clinics.")

        if not can_edit:
            st.info("Officer access with Editing Mode enabled is required to schedule club events or manage existing events. Enable Editing Mode in the sidebar.")

        target_season = selected_season if selected_season != "All Seasons" else CURRENT_SEASON

        with st.form("form_create_event", clear_on_submit=True):
            col_t1, col_t2 = st.columns([2.5, 1.5])
            with col_t1:
                evt_title = st.text_input("Event Title *", placeholder="e.g., Fall General Meeting #1, IV Sunset Social, Mammoth Wax Clinic", disabled=not can_edit)
            with col_t2:
                evt_type = st.selectbox("Event Category", EVENT_TYPES, disabled=not can_edit)

            # Dates
            c_d1, c_d2 = st.columns(2)
            with c_d1:
                evt_start_date = st.date_input("Start Date *", value=date.today() + timedelta(days=7), disabled=not can_edit)
            with c_d2:
                evt_end_date = st.date_input("End Date (leave same for single-day events)", value=evt_start_date, disabled=not can_edit)

            # Times
            c_all_day, c_st, c_et = st.columns([1.2, 1.4, 1.4])
            with c_all_day:
                st.write("")
                st.write("")
                is_all_day = st.checkbox("All-day event?", value=False, disabled=not can_edit)
            with c_st:
                default_st = datetime.strptime("19:00", "%H:%M").time()
                evt_st_val = st.time_input("Start Time", value=default_st, disabled=not can_edit or is_all_day)
            with c_et:
                default_et = datetime.strptime("20:30", "%H:%M").time()
                evt_et_val = st.time_input("End Time", value=default_et, disabled=not can_edit or is_all_day)

            # Location (MANUAL FREE-TEXT INPUT - Strictly NO Host/Lead input)
            c_loc, c_stat = st.columns([2.5, 1.5])
            with c_loc:
                evt_location = st.text_input(
                    "Event Location (Enter manually) *",
                    placeholder="e.g., Embarcadero Hall 101, Del Playa Dr, Rec Cen Turf, Rockwood...",
                    help="Enter specific classroom, house, beach, or park. Locations are free-text for maximum flexibility.",
                    disabled=not can_edit
                )
            with c_stat:
                evt_status = st.selectbox("Status", EVENT_STATUS_OPTIONS, index=1, disabled=not can_edit)

            # RSVP Link
            evt_rsvp = st.text_input("RSVP / Ticket / Info Link (Optional)", placeholder="https://forms.gle/... or Instagram post link", disabled=not can_edit)

            # Description
            evt_desc = st.text_area(
                "Event Description & Meeting Agenda",
                placeholder="Details, what to bring, gear requirements, agenda...",
                disabled=not can_edit
            )

            submit_event = st.form_submit_button(
                "Save Event to Schedule",
                type="primary",
                use_container_width=True,
                disabled=not can_edit
            )

            if submit_event:
                if not evt_title.strip():
                    st.error("Please provide an Event Title.")
                else:
                    st_str = "" if is_all_day else evt_st_val.strftime("%H:%M")
                    et_str = "" if is_all_day else evt_et_val.strftime("%H:%M")
                    sd_str = evt_start_date.strftime("%Y-%m-%d")
                    ed_str = evt_end_date.strftime("%Y-%m-%d") if evt_end_date else sd_str

                    ok = add_event(
                        season=target_season,
                        title=evt_title.strip(),
                        event_type=evt_type,
                        start_date=sd_str,
                        end_date=ed_str,
                        start_time=st_str,
                        end_time=et_str,
                        location=evt_location.strip(),
                        status=evt_status,
                        officer_lead="",
                        description=evt_desc.strip(),
                        rsvp_link=evt_rsvp.strip(),
                        is_officer=is_officer
                    )
                    if ok:
                        st.success(f"Event '{evt_title.strip()}' scheduled successfully for season {target_season}!")
                        st.rerun()
                    else:
                        st.error("Could not save event. Please check inputs and try again.")

        st.divider()

        # --- MANAGE EXISTING NON-TRIP EVENTS (NO HOST/LEAD, NO EMOJIS) ---
        st.markdown("#### Manage Existing Events")
        if events_df.empty:
            st.info(f"No non-trip club events logged yet for '{selected_season}'.")
        else:
            for _, evt in events_df.iterrows():
                with st.container():
                    c_ev_info, c_ev_stat, c_ev_del = st.columns([2.8, 1.2, 1.0])
                    with c_ev_info:
                        tag_str = _get_type_tag(evt.get("EventType", ""), "Event")
                        st.markdown(f"**{tag_str} {evt['Title']}**")
                        d_str = _format_date_range(evt.get("StartDate", ""), evt.get("EndDate", ""))
                        t_str = _format_time_range(evt.get("StartTime", ""), evt.get("EndTime", "")) if evt.get("StartTime") else "All Day"
                        loc_str = evt.get("Location", "") or "No location specified"
                        st.caption(f"Date: {d_str} | Time: {t_str} | Location: {loc_str}")
                    with c_ev_stat:
                        curr_stat = str(evt.get("Status", "Confirmed")).strip()
                        stat_opts = [opt for opt in EVENT_STATUS_OPTIONS]
                        if curr_stat and curr_stat not in stat_opts:
                            stat_opts.insert(0, curr_stat)
                        idx_stat = stat_opts.index(curr_stat) if curr_stat in stat_opts else 0
                        new_stat = st.selectbox(
                            "Status",
                            options=stat_opts,
                            index=idx_stat,
                            key=f"manage_evt_stat_{evt['EventID']}_{curr_stat}",
                            disabled=not can_edit
                        )
                        if can_edit and new_stat != curr_stat:
                            if update_event_status(evt["EventID"], new_stat, is_officer=is_officer):
                                st.success(f"Updated {evt['Title']} status to {new_stat}.")
                                st.rerun()
                    with c_ev_del:
                        st.write("")
                        with st.popover("Delete"):
                            if not can_edit:
                                st.info("Officer Editing Mode required to delete events.")
                            else:
                                st.caption(f"Permanently delete '{evt['Title']}'?")
                                if st.button("Confirm Delete", key=f"btn_del_evt_{evt['EventID']}", type="primary"):
                                    if delete_event(evt["EventID"], is_officer=is_officer):
                                        st.success(f"Deleted {evt['Title']}.")
                                        st.rerun()
                                    else:
                                        st.error("Failed to delete event.")
                    st.divider()
