"""
Membership and Registration Tracker module for the UCSB Ski Team Dashboard.
Features live in-table interactive checkboxes for Dues Paid and Comp Team,
dropdown for T-Shirt Size (None, S, M, L, XL), and includes membership form Notes.
"""

import streamlit as st
import pandas as pd
from datetime import date
from utils.data_manager import (
    load_members, save_members, add_member, delete_member, delete_multiple_members,
    save_edited_members, fetch_and_sync_google_sheet, parse_and_sync_google_form_df,
    reset_active_season_roster, get_merch_inventory_summary
)
from config import (
    ANNUAL_DUES_AMOUNT, CURRENT_SEASON, SHIRT_SIZES,
    DEFAULT_MEMBERSHIP_FORM_SHEET_URL, SKIBOARD_OPTIONS
)


def render_registration_tab(selected_season: str = CURRENT_SEASON, is_officer: bool = False, can_edit: bool = None):
    if can_edit is None:
        can_edit = is_officer

    st.markdown(f"## Membership and Registration Tracker ({selected_season})")
    st.markdown("Directly click checkboxes and select shirt sizes in the table below. Form notes are tracked in the rightmost column.")

    members_df = load_members(season=selected_season, is_officer=is_officer)

    # --- GOOGLE FORM LIVE SYNC SECTION ---
    with st.expander("Google Forms Live Sync and Import", expanded=False):
        if not is_officer:
            st.info("Officer access required to sync or import Google Form registrations. Enter the officer password in the sidebar to unlock.")
        elif not can_edit:
            st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to sync or import registrations.")
        else:
            st.markdown(
                f"Link your team's Google Form registration responses directly for season **{selected_season if selected_season != 'All Seasons' else CURRENT_SEASON}**. "
                "Google Forms records submissions into a Google Sheet. "
                "Sync directly from the official Google Sheet link below or upload an exported CSV."
            )
            
            tab_url, tab_upload = st.tabs(["Sync via Google Sheet URL", "Upload Google Form CSV"])
            
            with tab_url:
                st.caption("Ensure your Google Sheet is shared as 'Anyone with the link can view'.")
                sheet_url_input = st.text_input(
                    "Google Sheet URL or ID",
                    value=DEFAULT_MEMBERSHIP_FORM_SHEET_URL,
                    help="Pre-filled with the official UCSB Ski and Board Team Member App responses spreadsheet."
                )
                if st.button("Sync Responses from Google Sheet", width="stretch"):
                    if not sheet_url_input.strip():
                        st.error("Please enter a valid Google Sheet URL or ID.")
                    else:
                        target_s = selected_season if selected_season != "All Seasons" else CURRENT_SEASON
                        with st.spinner("Connecting to Google Sheet and syncing new registrations..."):
                            success, message, count = fetch_and_sync_google_sheet(sheet_url_input, target_season=target_s, is_officer=is_officer)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)

            with tab_upload:
                uploaded_file = st.file_uploader("Upload Google Form Responses (.csv)", type=["csv"])
                if uploaded_file is not None:
                    if st.button("Import Uploaded CSV into Current Roster", width="stretch"):
                        target_s = selected_season if selected_season != "All Seasons" else CURRENT_SEASON
                        try:
                            df_uploaded = pd.read_csv(uploaded_file)
                            success, message, count = parse_and_sync_google_form_df(df_uploaded, target_season=target_s, is_officer=is_officer)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                        except Exception as e:
                            st.error(f"Error parsing CSV file: {e}")

    # --- TOP ROW: REGISTRATION METRICS DASHBOARD ---
    total_members = len(members_df)
    paid_members = len(members_df[members_df["DuesPaid"] == True])
    comp_team_count = len(members_df[members_df["CompTeam"] == True])
    shirts_claimed = len(members_df[members_df["TShirtSize"].isin(["S", "M", "L", "XL"])])

    pct_paid = (paid_members / total_members * 100) if total_members > 0 else 0
    projected_dues = total_members * ANNUAL_DUES_AMOUNT
    actual_dues_collected = paid_members * ANNUAL_DUES_AMOUNT

    # Calculate new sign-ups for Card 1 insight
    all_members_df = load_members(season=None, is_officer=is_officer)
    if selected_season != "All Seasons":
        prior_members = all_members_df[all_members_df["Season"] != selected_season]
        prior_names = set(prior_members["Name"].astype(str).str.lower().str.strip())
        current_names = members_df["Name"].astype(str).str.lower().str.strip().tolist()
        new_signups = sum(1 for n in current_names if n not in prior_names)
    else:
        new_signups = len(all_members_df[all_members_df["Season"] == CURRENT_SEASON])

    # Calculate % of total shirts remaining for Card 3 insight
    merch_summary = get_merch_inventory_summary(season=selected_season if selected_season != "All Seasons" else None, is_officer=is_officer)
    total_shirts_init = merch_summary.get("total_shirts_init", 250)
    total_shirts_avail = merch_summary.get("total_shirts_avail", 0)
    pct_shirts_remaining = (total_shirts_avail / total_shirts_init * 100) if total_shirts_init > 0 else 0.0

    # Calculate USCSA Competition Team change over previous season for Card 4 insight
    prev_season = "2025-2026" if selected_season == "2026-2027" else None
    if prev_season:
        prev_members_df = load_members(season=prev_season, is_officer=is_officer)
        prev_comp_count = len(prev_members_df[prev_members_df["CompTeam"] == True])
        comp_diff = comp_team_count - prev_comp_count
        comp_delta_str = f"{comp_diff:+d} vs previous season"
        if comp_diff > 0:
            comp_delta_color = "green"
            comp_delta_arrow = "auto"
        elif comp_diff < 0:
            comp_delta_color = "red"
            comp_delta_arrow = "auto"
        else:
            comp_delta_color = "gray"
            comp_delta_arrow = "off"
    else:
        comp_delta_str = "Baseline season"
        comp_delta_color = "gray"
        comp_delta_arrow = "off"

    m1, m2, m3, m4 = st.columns(4)

    # Insight 1: Green if at least 1 new sign up, else gray
    m1_color = "green" if new_signups >= 1 else "gray"
    m1.metric(
        label="Total Members",
        value=f"{total_members}",
        delta=f"{new_signups} new sign-ups" if total_members > 0 else None,
        delta_color=m1_color,
        delta_arrow="off"
    )

    # Insight 2: Escaped dollar signs to avoid KaTeX green math font; Green if >90%, else red
    m2_color = "green" if pct_paid > 90.0 else "red"
    m2.metric(
        label="Dues Collection Rate",
        value=f"{pct_paid:.1f}%",
        delta=f"\\${actual_dues_collected:,.0f} of \\${projected_dues:,.0f}" if total_members > 0 else None,
        delta_color=m2_color,
        delta_arrow="off"
    )

    # Insight 3: Green if >20% remaining, else red
    m3_color = "green" if pct_shirts_remaining > 20.0 else "red"
    m3.metric(
        label="T-Shirts Claimed",
        value=f"{shirts_claimed}",
        delta=f"{pct_shirts_remaining:.1f}% remaining" if total_shirts_init > 0 else None,
        delta_color=m3_color,
        delta_arrow="off"
    )

    # Insight 4: Red if less competitors vs previous season, green if more
    m4.metric(
        label="USCSA Competition Team",
        value=f"{comp_team_count} Competitors",
        delta=comp_delta_str if total_members > 0 else None,
        delta_color=comp_delta_color,
        delta_arrow=comp_delta_arrow
    )

    st.divider()

    # --- MANUAL MEMBER ENTRY FORM ---
    with st.expander("Register Member Manually", expanded=False):
        if not is_officer:
            st.info("Officer access required to register members manually. Enter the officer password in the sidebar to unlock.")
        elif not can_edit:
            st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to register members manually.")
        else:
            with st.form("add_member_form", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    name = st.text_input("Full Name", placeholder="e.g. Kelly Clark")
                    email = st.text_input("Email", placeholder="e.g. kclark@ucsb.edu")
                    phone = st.text_input("Phone Number", placeholder="e.g. 805-555-1234")

                with c2:
                    year_val = st.selectbox("Academic Year", ["1", "2", "3", "4", "Grad", "Other"], index=0)
                    skiboard_val = st.selectbox("Ski or Board?", ["Ski", "Board", "Both"], index=0)
                    tshirt_size = st.selectbox("Complementary T-Shirt Size", SHIRT_SIZES, index=0)

                with c3:
                    dues_paid = st.checkbox("Dues Paid ($60)", value=True)
                    slack_joined = st.checkbox("Joined Slack", value=False)
                    comp_team = st.checkbox("Competition Team (USCSA Racer)", value=False)
                    notes = st.text_input("Membership Form Notes", placeholder="e.g. Dietary restriction, carpool driver, gear inquiries")

                target_reg_season = selected_season if selected_season != "All Seasons" else CURRENT_SEASON
                submitted = st.form_submit_button("Save Member to Roster", width="stretch")
                if submitted:
                    if not name.strip():
                        st.error("Member Name is required.")
                    else:
                        if add_member(
                            name, email, phone, dues_paid, tshirt_size, comp_team, notes,
                            season=target_reg_season, year=year_val, ski_board=skiboard_val,
                            slack=slack_joined, is_officer=is_officer
                        ):
                            st.success(f"Added '{name}' to the {target_reg_season} roster.")
                            st.rerun()
                        else:
                            st.error("Could not add member. Please try again.")

    # --- DELETE MEMBER FROM ROSTER (BULK OR SINGLE) ---
    with st.expander("Delete Member from Roster", expanded=False):
        if not is_officer:
            st.info("Officer access required to delete members. Enter the officer password in the sidebar to unlock.")
        elif not can_edit:
            st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to delete members.")
        else:
            if members_df.empty:
                st.info(f"No members registered yet in season '{selected_season}' to delete.")
            else:
                st.markdown("**Select Member(s) to Delete from Roster**")
                st.caption(
                    "Deleting a member permanently removes them from the club roster, "
                    "removes any corresponding membership dues entry from the ledger, "
                    "and cleans up their active trip registrations."
                )

                member_del_options = {
                    f"{r['Name']} ({r['MemberID']} • {r['Season']})": r["MemberID"]
                    for _, r in members_df.iterrows()
                }

                selected_del_labels = st.multiselect(
                    "Select Member(s) to Delete",
                    options=list(member_del_options.keys()),
                    key=f"del_mbr_multisel_{selected_season}",
                    help="Search and select one or more members to remove from the team roster."
                )

                if selected_del_labels:
                    st.warning(f"Are you sure you want to permanently delete {len(selected_del_labels)} member(s)? This action cannot be undone.")
                    if st.button(f"Confirm Delete {len(selected_del_labels)} Member(s)", type="primary", key=f"btn_del_mbr_exp_{selected_season}"):
                        ids_to_del = [member_del_options[lbl] for lbl in selected_del_labels]
                        del_count = delete_multiple_members(ids_to_del, is_officer=is_officer)
                        if del_count > 0:
                            st.success(f"Successfully deleted {del_count} member(s) from the roster.")
                            st.rerun()
                        else:
                            st.error("Could not delete selected member(s).")

    # --- ROSTER FILTERS & INTERACTIVE DATA EDITOR ---
    if total_members == 0:
        st.info(f"No members registered yet for season '{selected_season}'. Use the Google Forms sync above or 'Register Member Manually' to begin adding athletes.")
    else:
        f1, f2, f3 = st.columns([2.0, 1.2, 1.2])
        with f1:
            search_query = st.text_input("Search Roster", placeholder="Search by name, email, year, ski/board, note, or trip...")
        with f2:
            dues_filter = st.selectbox("Dues Filter", ["All", "Paid Only", "Unpaid Only"])
        with f3:
            slack_filter = st.selectbox("Slack Filter", ["All", "In Slack Only", "Not in Slack"])

        f4, f5, f6 = st.columns([1.3, 1.3, 1.3])
        with f4:
            skiboard_filter = st.selectbox("Ski / Board", ["All Disciplines", "Ski", "Board", "Both"])
        with f5:
            comp_filter = st.selectbox("Team Division", ["All Athletes", "Comp Team Only", "Rec Skiers Only"])
        with f6:
            shirt_filter = st.selectbox("T-Shirt Filter", ["All", "Sized (S/M/L/XL)", "No Shirt Selected (None)"])

        filtered_members = members_df.copy()

        if dues_filter == "Paid Only":
            filtered_members = filtered_members[filtered_members["DuesPaid"] == True]
        elif dues_filter == "Unpaid Only":
            filtered_members = filtered_members[filtered_members["DuesPaid"] == False]

        if slack_filter == "In Slack Only":
            filtered_members = filtered_members[filtered_members["Slack"] == True]
        elif slack_filter == "Not in Slack":
            filtered_members = filtered_members[filtered_members["Slack"] == False]

        if skiboard_filter != "All Disciplines":
            filtered_members = filtered_members[filtered_members["SkiBoard"].astype(str).str.lower().str.strip() == skiboard_filter.lower().strip()]

        if shirt_filter == "Sized (S/M/L/XL)":
            filtered_members = filtered_members[filtered_members["TShirtSize"].isin(["S", "M", "L", "XL"])]
        elif shirt_filter == "No Shirt Selected (None)":
            filtered_members = filtered_members[~filtered_members["TShirtSize"].isin(["S", "M", "L", "XL"])]

        if comp_filter == "Comp Team Only":
            filtered_members = filtered_members[filtered_members["CompTeam"] == True]
        elif comp_filter == "Rec Skiers Only":
            filtered_members = filtered_members[filtered_members["CompTeam"] == False]

        if search_query.strip():
            q = search_query.strip().lower()
            filtered_members = filtered_members[
                filtered_members["Name"].astype(str).str.lower().str.contains(q, na=False) |
                filtered_members["Email"].astype(str).str.lower().str.contains(q, na=False) |
                filtered_members["Notes"].astype(str).str.lower().str.contains(q, na=False) |
                filtered_members["TripsAttended"].astype(str).str.lower().str.contains(q, na=False) |
                filtered_members["Year"].astype(str).str.lower().str.contains(q, na=False) |
                filtered_members["SkiBoard"].astype(str).str.lower().str.contains(q, na=False)
            ]

        st.caption(f"Showing **{len(filtered_members)}** of **{len(members_df)}** members &bull; *Click checkboxes, select shirt sizes, or edit notes directly inside the table.*")

        # Prepare editable DataFrame with Year, Ski/Board, Slack, TShirtSize dropdown and Notes column
        display_cols = [
            "Name", "Year", "SkiBoard", "Slack", "DuesPaid", "CompTeam",
            "TShirtSize", "Email", "Phone", "TripsAttended", "Notes", "Season", "MemberID"
        ]
        editor_input_df = filtered_members[display_cols].copy()
        editor_input_df.columns = [
            "Name", "Year", "Ski/Board", "Slack", "Dues Paid", "Comp Team",
            "T-Shirt Size", "Email", "Phone", "Trips Attended", "Notes", "Season", "ID"
        ]

        # Ensure strict compatible types for Streamlit data_editor column_configs
        editor_input_df["Dues Paid"] = editor_input_df["Dues Paid"].fillna(False).astype(bool)
        editor_input_df["Slack"] = editor_input_df["Slack"].fillna(False).astype(bool)
        editor_input_df["Comp Team"] = editor_input_df["Comp Team"].fillna(False).astype(bool)
        for txt_col in ["ID", "Season", "Name", "Email", "Phone", "Year", "Ski/Board", "T-Shirt Size", "Trips Attended", "Notes"]:
            editor_input_df[txt_col] = (
                editor_input_df[txt_col]
                .fillna("")
                .astype(str)
                .replace({"nan": "", "None": "", "NaN": ""})
            )

        # In-Table Interactive Checkboxes & Dropdowns via st.data_editor
        edited_roster = st.data_editor(
            editor_input_df,
            column_config={
                "Dues Paid": st.column_config.CheckboxColumn(
                    "Dues Paid",
                    help="Click to mark dues paid ($60)",
                    default=False
                ),
                "Slack": st.column_config.CheckboxColumn(
                    "Slack",
                    help="Click to toggle whether member is in the club Slack",
                    default=False
                ),
                "Comp Team": st.column_config.CheckboxColumn(
                    "Comp Team",
                    help="Click to toggle USCSA competition racer",
                    default=False
                ),
                "Year": st.column_config.TextColumn(
                    "Year",
                    help="College academic year (e.g. 1, 2, 3, 4, Grad)",
                ),
                "Ski/Board": st.column_config.SelectboxColumn(
                    "Ski/Board",
                    help="Primary discipline: Ski, Board, or Both",
                    options=SKIBOARD_OPTIONS,
                    required=False,
                ),
                "T-Shirt Size": st.column_config.SelectboxColumn(
                    "T-Shirt Size",
                    help="Select member's t-shirt size (S, M, L, XL, or None)",
                    options=SHIRT_SIZES,
                    required=True,
                    default="None"
                ),
                "Notes": st.column_config.TextColumn(
                    "Notes",
                    help="Membership form questions, diet, carpools, or comments",
                ),
                "ID": st.column_config.TextColumn("ID", disabled=True),
                "Season": st.column_config.TextColumn("Season", disabled=True),
                "Name": st.column_config.TextColumn("Name"),
                "Email": st.column_config.TextColumn("Email"),
                "Phone": st.column_config.TextColumn("Phone"),
                "Trips Attended": st.column_config.TextColumn("Trips Attended"),
            },
            disabled=["ID", "Season"] if (is_officer and can_edit) else True,
            hide_index=True,
            width="stretch",
            height=450,
            key=f"editor_members_{selected_season}"
        )

        if is_officer and not can_edit:
            st.caption("Officer viewing mode active (read-only). Enable the Editing toggle in the sidebar to edit dues, sizes, or member details.")
        elif not is_officer:
            st.caption("Viewing member roster in read-only mode. Enter the officer password in the sidebar to edit dues, sizes, or member details.")

        # Detect in-table changes and persist immediately
        if is_officer and can_edit and not edited_roster.equals(editor_input_df):
            if save_edited_members(edited_roster, current_view_season=selected_season, is_officer=is_officer):
                st.success("Member updates saved directly to database.")
                st.rerun()

        # CSV Export & Quick Delete Action
        c_exp, c_del = st.columns([2, 1.2])
        with c_exp:
            csv_roster = filtered_members.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Export Member Roster to CSV",
                data=csv_roster,
                file_name=f"ucsb_ski_team_roster_{selected_season}_{date.today().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                width="stretch"
            )
        with c_del:
            with st.popover("Delete a Member", width="stretch"):
                if not is_officer:
                    st.info("Officer access required to delete members. Enter the officer password in the sidebar to unlock.")
                elif not can_edit:
                    st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to delete members.")
                else:
                    st.markdown("**Remove Member from Roster**")
                    st.caption("Permanently remove member and update dues in ledger.")
                    pop_member_map = {
                        f"{r['Name']} ({r['MemberID']})": r["MemberID"]
                        for _, r in filtered_members.iterrows()
                    }
                    if not pop_member_map:
                        st.info("No members available to delete in current view.")
                    else:
                        chosen_pop_lbl = st.selectbox(
                            "Select Member to Remove",
                            options=list(pop_member_map.keys()),
                            key=f"pop_del_mbr_sel_{selected_season}"
                        )
                        if st.button("Confirm Delete Member", type="primary", key=f"btn_pop_del_mbr_{selected_season}", width="stretch"):
                            mid_del = pop_member_map[chosen_pop_lbl]
                            if delete_member(mid_del, is_officer=is_officer):
                                st.success(f"Deleted member {chosen_pop_lbl}.")
                                st.rerun()
                            else:
                                st.error("Could not delete member.")

    # --- SEASON RESET & ARCHIVE MANAGEMENT TOOL ---
    st.divider()
    with st.expander("Season Transition and Roster Reset"):
        if not is_officer:
            st.info("Officer access required for season transition and archiving. Enter the officer password in the sidebar to unlock.")
        elif not can_edit:
            st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to archive and reset roster.")
        else:
            st.markdown(
                "**New Academic Year Transition**  \n"
                "This tool resets the active registration roster for the upcoming season while permanently preserving all past years' member and ledger records. "
                "Previous rosters remain accessible at any time via the season selector in the sidebar."
            )
            c_reset1, c_reset2 = st.columns([2, 1])
            with c_reset1:
                new_season_input = st.text_input("New Season Name", value="2027-2028")
            with c_reset2:
                st.write("")
                st.write("")
                if st.button("Archive and Start New Season", type="secondary"):
                    if new_season_input.strip():
                        success, msg = reset_active_season_roster(new_season_input.strip(), is_officer=is_officer)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
