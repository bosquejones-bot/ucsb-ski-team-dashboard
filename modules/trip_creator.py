"""
Trip Creator and Operations Manager module for the UCSB Ski Team Dashboard.
Allows creating trips with built-in Google Form sign-up generation,
and managing trip attendees in similar fashion to the membership tracker
with in-table interactive Payment Received checkboxes.
"""

import streamlit as st
import pandas as pd
import json
import re
from datetime import date, timedelta
from utils.data_manager import (
    load_trips, load_members, add_created_trip, delete_trip,
    load_trip_signups, save_edited_trip_signups,
    fetch_and_sync_trip_form_sheet, parse_and_sync_trip_form_df,
    add_trip_attendee, delete_trip_attendee, delete_multiple_trip_attendees,
    record_trip_payment_in_ledger, remove_trip_payment_from_ledger,
    update_trip_status, generate_trips_ical
)
from config import (
    DESTINATIONS, TRIP_TYPES, TRIP_STATUS_OPTIONS, DEFAULT_MPG, DEFAULT_GAS_PRICE,
    DEFAULT_SEATS_PER_CAR, CURRENT_SEASON, THEME_COLORS,
    DEFAULT_TRIP_DRIVER_OPTIONS
)


def extract_driver_capacity(driving_val) -> int:
    """
    Extracts passenger capacity as an integer from driving capacity strings.
    Returns 0 if non-driver, cannot drive, or empty.
    """
    if pd.isna(driving_val):
        return 0
    s = str(driving_val).strip()
    if not s:
        return 0
    s_lower = s.lower()
    if (
        "cannot" in s_lower
        or "can't" in s_lower
        or "no car" in s_lower
        or "don't have" in s_lower
        or s_lower in ["no", "none", "nan", "0", "false"]
    ):
        return 0
    m = re.search(r'(\d+)', s)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return 0
    if "can drive" in s_lower or "drive" in s_lower or "yes" in s_lower:
        return 1
    return 0


def generate_driver_sheet_script(trip_name: str, drivers: list) -> str:
    """
    Generates a Google Apps Script that creates a formatted Google Sheet
    for driver carpools with the exact columns:
    Driver, Phone Number, # of Passengers, Departure Time,
    Passenger 1, Passenger 2, Passenger 3, Passenger 4.

    Only attendees who have signed up to drive for this trip are added.
    Passenger columns are blank for attendees to write their names.
    Passenger columns are filled red (#ea4335) if that driver cannot take that many passengers.
    """
    clean_trip_name = str(trip_name).strip() if trip_name else "Trip"
    sheet_title = f"UCSB Ski Team - {clean_trip_name} - Driver Sign-Up Sheet"

    headers = [
        "Driver",
        "Phone Number",
        "# of Passengers",
        "Departure Time",
        "Passenger 1",
        "Passenger 2",
        "Passenger 3",
        "Passenger 4"
    ]

    data_rows = []
    bg_rows = []

    for d in drivers:
        name = str(d.get("name", "")).strip()
        phone = str(d.get("phone", "")).strip()
        cap = int(d.get("capacity", 0))

        if cap <= 0:
            continue

        # 8 columns: Driver, Phone, Capacity, Departure Time (blank), Passenger 1-4 (blank)
        row_vals = [name, phone, cap, "", "", "", "", ""]
        data_rows.append(row_vals)

        # Background fills: #ea4335 for passenger columns exceeding driver capacity
        row_bgs = [
            "#ffffff",  # Driver
            "#ffffff",  # Phone Number
            "#ffffff",  # # of Passengers
            "#ffffff",  # Departure Time
            "#ffffff" if cap >= 1 else "#ea4335",  # Passenger 1
            "#ffffff" if cap >= 2 else "#ea4335",  # Passenger 2
            "#ffffff" if cap >= 3 else "#ea4335",  # Passenger 3
            "#ffffff" if cap >= 4 else "#ea4335",  # Passenger 4
        ]
        bg_rows.append(row_bgs)

    data_json = json.dumps(data_rows, indent=4)
    bg_json = json.dumps(bg_rows, indent=4)
    headers_json = json.dumps(headers)

    script_code = f"""/**
 * UCSB Ski & Snowboard Team - Driver Sign-Up & Carpool Sheet Generator
 * Generated for: {clean_trip_name}
 *
 * HOW TO USE:
 * 1. Open https://script.google.com and click 'New project'.
 * 2. Paste this entire code block into the editor (replacing Code.gs).
 * 3. Click 'Run' (createDriverSignUpSheet). Grant permissions if prompted.
 * 4. The script creates the formatted Google Sheet in your Google Drive and logs the URL below.
 */

function createDriverSignUpSheet() {{
  var tripName = {json.dumps(clean_trip_name)};
  var spreadsheetTitle = {json.dumps(sheet_title)};

  // Create Google Spreadsheet
  var ss = SpreadsheetApp.create(spreadsheetTitle);
  var sheet = ss.getActiveSheet();
  sheet.setName("Driver Sign-Up & Carpools");

  // 8 Required Columns
  var headers = {headers_json};

  // Set and style headers
  var headerRange = sheet.getRange(1, 1, 1, headers.length);
  headerRange.setValues([headers]);
  headerRange.setBackground("#1d273d")
             .setFontColor("#ffffff")
             .setFontWeight("bold")
             .setFontSize(11)
             .setHorizontalAlignment("center")
             .setVerticalAlignment("middle");
  sheet.setRowHeight(1, 38);
  sheet.setFrozenRows(1);

  // Populate confirmed drivers and red background fills
  var driverData = {data_json};
  var driverBackgrounds = {bg_json};

  if (driverData.length > 0) {{
    var numRows = driverData.length;
    var numCols = headers.length;
    var dataRange = sheet.getRange(2, 1, numRows, numCols);

    dataRange.setValues(driverData);
    dataRange.setBackgrounds(driverBackgrounds);
    dataRange.setVerticalAlignment("middle");
    dataRange.setFontSize(10);

    // Clean table border styling
    dataRange.setBorder(true, true, true, true, true, true, "#d9d9d9", SpreadsheetApp.BorderStyle.SOLID);

    // Text Alignments
    sheet.getRange(2, 1, numRows, 1).setHorizontalAlignment("left");   // Driver Name
    sheet.getRange(2, 2, numRows, 1).setHorizontalAlignment("center"); // Phone Number
    sheet.getRange(2, 3, numRows, 1).setHorizontalAlignment("center"); // # of Passengers
    sheet.getRange(2, 4, numRows, 1).setHorizontalAlignment("center"); // Departure Time
    sheet.getRange(2, 5, numRows, 4).setHorizontalAlignment("center"); // Passenger 1 - 4

    for (var r = 2; r <= numRows + 1; r++) {{
      sheet.setRowHeight(r, 30);
    }}
  }}

  // Set comfortable column widths
  for (var col = 1; col <= headers.length; col++) {{
    sheet.autoResizeColumn(col);
  }}
  var minWidths = [180, 140, 130, 140, 140, 140, 140, 140];
  for (var i = 0; i < minWidths.length; i++) {{
    var currW = sheet.getColumnWidth(i + 1);
    if (currW < minWidths[i]) {{
      sheet.setColumnWidth(i + 1, minWidths[i]);
    }}
  }}

  var fileUrl = ss.getUrl();
  Logger.log("=== Driver Sign-Up Sheet Created Successfully ===");
  Logger.log("Trip: " + tripName);
  Logger.log("Google Sheet URL: " + fileUrl);
  return fileUrl;
}}
"""
    return script_code


def _render_create_trip_form(selected_season: str, dest_options: list, is_officer: bool = False, can_edit: bool = None):
    if can_edit is None:
        can_edit = is_officer
    show_script = st.session_state.get("trip_created_show_script", False)

    if show_script:
        saved_name = st.session_state.get("just_created_trip_name", "Trip")
        saved_season = st.session_state.get("just_created_trip_season", selected_season)
        c_succ, c_btn = st.columns([3.5, 1.2])
        with c_succ:
            st.success(f"Trip '{saved_name}' created successfully for season {saved_season}! Review your Google Form details and copy the pre-built Apps Script below.")
        with c_btn:
            if st.button("Create Another Trip", key="btn_create_another", width="stretch"):
                st.session_state["trip_created_show_script"] = False
                st.rerun()

    st.markdown(
        "Configure trip logistics, budget costs, and customize the built-in Google Form sign-up template. "
        "All form details and default fields are fully editable."
    )

    with st.expander("1. Trip Details & Budget Logistics", expanded=not show_script):
        c1, c2, c3 = st.columns(3)

        with c1:
            destination_choice = st.selectbox("Destination", dest_options, index=0, key="ct_dest")
            if destination_choice == "Other":
                custom_destination = st.text_input("Specify Destination Name", placeholder="e.g. June Mountain, Mt. Baldy", key="ct_custom_dest")
                final_destination = custom_destination.strip() if custom_destination.strip() else "Other"
                default_nights = 3
                autofill_miles = 0
            else:
                final_destination = destination_choice
                dest_meta = DESTINATIONS[destination_choice]
                default_nights = dest_meta["default_nights"]
                autofill_miles = dest_meta["round_trip_miles"]

            trip_type = st.radio("Trip Type", TRIP_TYPES, horizontal=True, key="ct_type")
            if trip_type == "Competition":
                target_s = selected_season if selected_season != "All Seasons" else CURRENT_SEASON
                comp_m = load_members(season=target_s, is_officer=is_officer)
                comp_m = comp_m[comp_m["CompTeam"] == True]
                if comp_m.empty:
                    all_m = load_members(season=None, is_officer=is_officer)
                    comp_m = all_m[all_m["CompTeam"] == True]
                st.info(f"**Comp Trip**: All **{len(comp_m)}** member(s) on the Competition Team will be automatically added to this trip roster.")

        with c2:
            default_trip_name = f"{final_destination} Weekend 2026" if final_destination != "Other" else "Ski Team Trip 2026"
            trip_name = st.text_input("Trip Name", value=default_trip_name, key=f"ct_name_{final_destination}")
            status = st.selectbox("Trip Status", ["Planning", "Confirmed", "Completed", "Cancelled"], index=0, key="ct_status")

        with c3:
            col_sd, col_ed = st.columns(2)
            with col_sd:
                start_date = st.date_input("Start Date *", value=date.today() + timedelta(days=21), key="ct_start")
            with col_ed:
                if "ct_prev_start" not in st.session_state:
                    st.session_state["ct_prev_start"] = start_date

                if st.session_state["ct_prev_start"] != start_date:
                    st.session_state["ct_prev_start"] = start_date
                    st.session_state["ct_end"] = start_date
                elif "ct_end" in st.session_state and st.session_state["ct_end"] < start_date:
                    st.session_state["ct_end"] = start_date

                saved_ed = st.session_state.get("ct_end", start_date + timedelta(days=default_nights))
                if saved_ed < start_date:
                    saved_ed = start_date
                end_date = st.date_input("End Date *", value=saved_ed, min_value=start_date, key="ct_end")
            nights = max(0, (end_date - start_date).days)
            st.caption(f"Trip Duration: **{nights} night(s)** &bull; Return on {end_date.strftime('%a, %b %d')}")

        c_att1, c_att2, c_att3 = st.columns(3)
        with c_att1:
            attendees_count = st.number_input("Expected Attendees", min_value=1, max_value=100, value=24, step=1, key="ct_att")
        with c_att2:
            default_cars = max(1, int(attendees_count // DEFAULT_SEATS_PER_CAR) + (1 if attendees_count % DEFAULT_SEATS_PER_CAR else 0))
            vehicles = st.number_input("Vehicles / Carpools", min_value=1, max_value=25, value=default_cars, step=1, key="ct_veh")
        with c_att3:
            # Auto fill the Round-Trip Distance from UCSB based on destination's distance; Other does not autofill (0)
            miles = st.number_input(
                "Round-Trip Distance from UCSB (Miles)",
                min_value=0,
                max_value=5000,
                value=autofill_miles,
                step=10,
                key=f"ct_miles_{destination_choice}"
            )

        st.markdown("##### Budget Breakdown")
        if trip_type == "Competition":
            st.caption("Enter gross estimated costs below. Use the checkboxes to designate items covered by UCSB.")
            c_c1, c_c2 = st.columns(2)
            with c_c1:
                cabin_cost = st.number_input("Cabin / Housing ($)", min_value=0.0, value=2400.0, step=50.0, key="ct_cabin")
                school_covers_cabin = st.checkbox("UCSB covers Housing", value=False, key="ct_sc_cabin")
            with c_c2:
                food_cost = st.number_input("Food & Drinks ($)", min_value=0.0, value=400.0, step=25.0, key="ct_food")
                school_covers_food = st.checkbox("UCSB covers Food & Drinks", value=False, key="ct_sc_food")

            c_c3, c_c4, c_c5 = st.columns(3)
            with c_c3:
                ticket_price = st.number_input(
                    "Ticket Price ($ / Skier)",
                    min_value=0.0,
                    value=120.0,
                    step=10.0,
                    help="Per-competitor lift ticket price.",
                    key="ct_tix_price"
                )
            with c_c4:
                # Lift Tickets calculation in budget breakdown is expected attendees times ticket price
                calc_lift_tickets = float(round(attendees_count * ticket_price, 2))
                lift_tickets = st.number_input(
                    "Lift Tickets ($)",
                    min_value=0.0,
                    value=calc_lift_tickets,
                    step=50.0,
                    help=f"Calculated as {attendees_count} expected attendees x ${ticket_price:,.2f} ticket price.",
                    key=f"ct_tix_{attendees_count}_{ticket_price}"
                )
                school_covers_tickets = st.checkbox("UCSB covers Lift Tickets", value=False, key="ct_sc_tickets")
            with c_c5:
                # Calculate Estimated Gas using round trip miles times 0.70 times amount of vehicles
                calc_gas = float(round(miles * 0.70 * vehicles, 2))
                gas_cost = st.number_input(
                    "Estimated Gas ($)",
                    min_value=0.0,
                    value=calc_gas,
                    step=20.0,
                    help=f"Calculated as $0.70/mile x {miles} RT miles x {vehicles} vehicle(s).",
                    key=f"ct_gas_{destination_choice}_{miles}_{vehicles}"
                )
                school_covers_gas = st.checkbox("UCSB covers Gas", value=False, key="ct_sc_gas")

            covered_items = []
            school_funding_amount = 0.0
            if school_covers_cabin:
                covered_items.append("Housing")
                school_funding_amount += cabin_cost
            if school_covers_food:
                covered_items.append("Food")
                school_funding_amount += food_cost
            if school_covers_tickets:
                covered_items.append("Lift Tickets")
                school_funding_amount += lift_tickets
            if school_covers_gas:
                covered_items.append("Gas")
                school_funding_amount += gas_cost

            school_coverage_details = ", ".join(covered_items)
            total_trip_cost = cabin_cost + food_cost + lift_tickets + gas_cost
            net_trip_cost = max(0.0, total_trip_cost - school_funding_amount)
            calculated_ticket_price = net_trip_cost / max(1, attendees_count)

            st.write("")
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Gross Budget (Grant Requisition)", f"${total_trip_cost:,.2f}", help="Total expenditure proposal for UCSB.")
            b2.metric("UCSB Subsidy", f"${school_funding_amount:,.2f}", delta=f"{len(covered_items)} item(s) covered" if covered_items else None)
            b3.metric("Net Team Outflow", f"${net_trip_cost:,.2f}", help="Remaining balance paid by club dues or athletes.")
            b4.metric("Fee / Competitor", f"${calculated_ticket_price:,.2f}", help="Per-person share charged to participating competitors.")
        else:
            # Recreational trip: Lift Tickets ($) and Estimated Gas ($) not available
            c_c1, c_c2 = st.columns(2)
            with c_c1:
                cabin_cost = st.number_input("Cabin / Housing ($)", min_value=0.0, value=2400.0, step=50.0, key="ct_cabin")
            with c_c2:
                food_cost = st.number_input("Food & Drinks ($)", min_value=0.0, value=400.0, step=25.0, key="ct_food")
            ticket_price = 0.0
            lift_tickets = 0.0
            gas_cost = 0.0
            school_funding_amount = 0.0
            school_coverage_details = ""
            total_trip_cost = cabin_cost + food_cost + lift_tickets + gas_cost
            net_trip_cost = total_trip_cost
            calculated_ticket_price = total_trip_cost / max(1, attendees_count)
            st.caption("*Lift Tickets and Estimated Gas options are only available for competition trips.*")
            st.caption(f"Estimated Total Trip Outflow: **\\${total_trip_cost:,.2f}** &bull; Calculated Per-Skier Share: **\\${calculated_ticket_price:,.2f}**")

        trip_notes = st.text_input("Internal Trip Notes", placeholder="e.g. Leaving IV Friday afternoon, condo reservation #1234", key="ct_notes")

    st.divider()

    default_title = f"UCSB Ski Team - {trip_name.strip()} Sign-Up"
    default_desc = (
        f"Welcome to the official sign-up for the {trip_name.strip()} to {final_destination}!\n\n"
        f"Trip Details:\n"
        f"- Destination: {final_destination}\n"
        f"- Dates: {start_date} to {end_date} ({nights} nights)\n"
        f"- Price: ${calculated_ticket_price:,.0f} per skier (includes cabin lodging and team food/drink)\n\n"
        f"Payment Instructions:\n"
        f"Zelle ucsbskiteam (preferred method) or Venmo @ucsbskiteam."
    )

    # --- STEP 2: BUILT-IN GOOGLE FORM SIGN-UP GENERATOR ---
    with st.expander("2. Built-in Google Form Sign-Up Generator (Editable Details)", expanded=not show_script):
        st.markdown("Review and edit all details that will appear on the Google Form sign-up sheet for this trip.")

        c_f1, c_f2 = st.columns([2, 1])
        with c_f1:
            form_title_input = st.text_input("Google Form Title (Editable)", value=default_title, key=f"form_title_{final_destination}")
        with c_f2:
            form_price_input = st.number_input("Form Display Price per Skier ($)", min_value=0.0, value=float(round(calculated_ticket_price, 0)), step=5.0, key=f"form_price_{calculated_ticket_price}")

        form_desc_input = st.text_area(
            "Form Header Description & Instructions (Editable)",
            value=default_desc,
            height=160,
            key=f"form_desc_{final_destination}_{start_date}_{nights}_{calculated_ticket_price}"
        )

        st.markdown("##### Default Response Fields (Customizable Sign-Up Fields)")
        st.caption("Customize the fields athletes fill out when signing up. Add new fields, edit questions, or remove fields below.")

        default_form_fields = [
            {"Field": "Full Name", "Format": "Short Answer", "Required": True, "Detail": "Athlete first and last name"},
            {"Field": "Phone Number", "Format": "Short Answer", "Required": True, "Detail": "Cell phone for carpool group chat"},
            {"Field": "If you can drive (and how many passengers accounting for gear)", "Format": "Multiple Choice", "Required": True, "Detail": "Cannot drive / 1 passenger + gear / 2 passengers + gear / 3 passengers + gear / 4+ passengers + gear"},
            {"Field": "Questions or Concerns?", "Format": "Paragraph", "Required": False, "Detail": "Dietary requests, gear questions, or schedule notes"}
        ]

        if "trip_form_fields" not in st.session_state or not isinstance(st.session_state["trip_form_fields"], list):
            st.session_state["trip_form_fields"] = [dict(f) for f in default_form_fields]

        df_form_fields = pd.DataFrame(st.session_state["trip_form_fields"])

        edited_fields_df = st.data_editor(
            df_form_fields,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            key="editor_trip_form_fields",
            column_config={
                "Field": st.column_config.TextColumn("Field / Question Title", required=True),
                "Format": st.column_config.SelectboxColumn(
                    "Format",
                    options=["Short Answer", "Paragraph", "Multiple Choice", "Checkboxes", "Dropdown", "Date"],
                    required=True,
                    default="Short Answer"
                ),
                "Required": st.column_config.CheckboxColumn("Required", default=True),
                "Detail": st.column_config.TextColumn("Detail / Choices / Help Text")
            }
        )

        # Sync editor changes back to session state
        if not edited_fields_df.empty:
            updated_records = edited_fields_df.dropna(subset=["Field"]).to_dict(orient="records")
            st.session_state["trip_form_fields"] = updated_records

        # Field management quick actions: Add New Field, Delete Field, and Reset
        c_f_add, c_f_del, c_f_rst = st.columns([1.5, 1.5, 1])
        with c_f_add:
            with st.popover("Add New Field"):
                st.markdown("**Add Field to Sign-Up Form**")
                new_f_name = st.text_input("Field Title", placeholder="e.g. Emergency Contact, Skill Level", key="new_f_title")
                new_f_type = st.selectbox(
                    "Field Format",
                    ["Short Answer", "Paragraph", "Multiple Choice", "Checkboxes", "Dropdown", "Date"],
                    key="new_f_type"
                )
                new_f_req = st.checkbox("Required Field", value=True, key="new_f_req")
                new_f_detail = st.text_input(
                    "Detail / Choices / Placeholder",
                    placeholder="For choices, separate by slash: Option A / Option B",
                    key="new_f_detail"
                )
                if st.button("Add Field to Form", type="primary", key="btn_add_form_field", width="stretch"):
                    if new_f_name.strip():
                        st.session_state["trip_form_fields"].append({
                            "Field": new_f_name.strip(),
                            "Format": new_f_type,
                            "Required": new_f_req,
                            "Detail": new_f_detail.strip()
                        })
                        st.success(f"Added '{new_f_name.strip()}' to form fields.")
                        st.rerun()
                    else:
                        st.error("Please enter a field title.")

        with c_f_del:
            with st.popover("Delete a Field"):
                st.markdown("**Remove Field from Form**")
                curr_fields = [f.get("Field", "") for f in st.session_state["trip_form_fields"] if f.get("Field")]
                if curr_fields:
                    f_to_del = st.selectbox("Select Field to Delete", curr_fields, key="sel_f_del")
                    if st.button("Confirm Delete Field", type="primary", key="btn_del_field", width="stretch"):
                        st.session_state["trip_form_fields"] = [
                            f for f in st.session_state["trip_form_fields"] if f.get("Field") != f_to_del
                        ]
                        st.success(f"Removed '{f_to_del}'.")
                        st.rerun()
                else:
                    st.info("No fields to remove.")

        with c_f_rst:
            if st.button("Reset Defaults", help="Reset to standard 4 response fields", width="stretch", key="btn_reset_fields"):
                st.session_state["trip_form_fields"] = [dict(f) for f in default_form_fields]
                st.success("Form fields reset to default.")
                st.rerun()

        target_trip_season = selected_season if selected_season != "All Seasons" else CURRENT_SEASON
        submit_trip = st.button("Save Trip & Generate Google Form", type="primary", width="stretch", key="btn_save_trip_gen")

        if submit_trip:
            final_name = trip_name.strip() if trip_name.strip() else f"{final_destination} {trip_type} Trip"
            success = add_created_trip(
                name=final_name,
                destination=final_destination,
                trip_type=trip_type,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                nights=nights,
                miles=miles,
                attendees=attendees_count,
                vehicles=vehicles,
                cabin=cabin_cost,
                food=food_cost,
                tickets=lift_tickets,
                gas=gas_cost,
                attendee_roster=[],
                status=status,
                notes=trip_notes,
                season=target_trip_season,
                is_officer=is_officer,
                school_funding=school_funding_amount,
                net_cost=net_trip_cost,
                school_coverage_details=school_coverage_details
            )
            if success:
                st.session_state["trip_created_show_script"] = True
                st.session_state["just_created_trip_name"] = final_name
                st.session_state["just_created_trip_season"] = target_trip_season
                st.session_state["just_created_trip_title"] = form_title_input
                st.session_state["just_created_trip_desc"] = form_desc_input
                st.rerun()
            else:
                st.error("Failed to save trip. Please try again.")

    # Display Google Apps Script if trip was just created or when viewing form generator
    active_form_title = st.session_state.get("just_created_trip_title", default_title)
    active_form_desc = st.session_state.get("just_created_trip_desc", default_desc)

    st.markdown("#### 1-Click Google Apps Script Generator")
    st.markdown("Use this script to create the Google Form in your Google Drive with all fields pre-built.")

    active_fields = st.session_state.get("trip_form_fields", default_form_fields)
    apps_script_items = []

    for i, fld in enumerate(active_fields, start=1):
        f_name = str(fld.get("Field", "")).strip()
        if not f_name or f_name.lower() == "nan":
            continue
        f_type = str(fld.get("Format", "Short Answer")).strip()
        f_req = "true" if bool(fld.get("Required", False)) else "false"
        f_detail = str(fld.get("Detail", "")).strip()
        if f_detail.lower() == "nan":
            f_detail = ""

        help_text_clause = f'.setHelpText({json.dumps(f_detail)})' if f_detail and f_type not in ["Multiple Choice", "Checkboxes", "Dropdown"] else ""

        if f_type == "Short Answer":
            apps_script_items.append(
                f'  // Field {i}: {f_name}\n'
                f'  form.addTextItem().setTitle({json.dumps(f_name)}){help_text_clause}.setRequired({f_req});'
            )
        elif f_type == "Paragraph":
            apps_script_items.append(
                f'  // Field {i}: {f_name}\n'
                f'  form.addParagraphTextItem().setTitle({json.dumps(f_name)}){help_text_clause}.setRequired({f_req});'
            )
        elif f_type in ["Multiple Choice", "Checkboxes", "Dropdown"]:
            raw_choices = []
            if "/" in f_detail:
                raw_choices = [c.strip() for c in f_detail.split("/") if c.strip()]
            elif "," in f_detail:
                raw_choices = [c.strip() for c in f_detail.split(",") if c.strip()]
            elif f_detail:
                raw_choices = [f_detail]
            else:
                raw_choices = ["Option 1", "Option 2"]

            choices_lines = ",\n".join([f'      item{i}.createChoice({json.dumps(ch)})' for ch in raw_choices])

            if f_type == "Multiple Choice":
                item_method = "addMultipleChoiceItem"
            elif f_type == "Checkboxes":
                item_method = "addCheckboxItem"
            else:
                item_method = "addListItem"

            apps_script_items.append(
                f'  // Field {i}: {f_name}\n'
                f'  var item{i} = form.{item_method}();\n'
                f'  item{i}.setTitle({json.dumps(f_name)})\n'
                f'    .setChoices([\n{choices_lines}\n    ])\n'
                f'    .setRequired({f_req});'
            )
        elif f_type == "Date":
            apps_script_items.append(
                f'  // Field {i}: {f_name}\n'
                f'  form.addDateItem().setTitle({json.dumps(f_name)}){help_text_clause}.setRequired({f_req});'
            )
        else:
            apps_script_items.append(
                f'  // Field {i}: {f_name}\n'
                f'  form.addTextItem().setTitle({json.dumps(f_name)}){help_text_clause}.setRequired({f_req});'
            )

    fields_script_body = "\n\n".join(apps_script_items)

    script_code = f"""function createTripForm() {{
  var form = FormApp.create({json.dumps(active_form_title)});
  form.setDescription({repr(active_form_desc)});
  
{fields_script_body}
  
  Logger.log("Edit Form: " + form.getEditUrl());
  Logger.log("Published Form: " + form.getPublishedUrl());
}}"""

    with st.expander("View 1-Click Google Apps Script Code", expanded=show_script):
        st.markdown(
            "1. Open [script.google.com](https://script.google.com) and click **New project**.\n"
            "2. Paste the code below and click **Run**.\n"
            "3. Your Google Form is created instantly in your Google Drive!"
        )
        st.code(script_code, language="javascript")


def render_trip_creator_tab(selected_season: str = CURRENT_SEASON, is_officer: bool = False, can_edit: bool = None):
    if can_edit is None:
        can_edit = is_officer

    st.markdown(f"## Trip Creator and Operations Manager ({selected_season})")
    st.markdown("Create official team trips with custom Google Forms, manage driver capacities, and track athlete payments.")

    dest_options = list(DESTINATIONS.keys()) + ["Other"]
    members_df = load_members(season=selected_season if selected_season != "All Seasons" else None, is_officer=is_officer)
    available_member_names = sorted(members_df["Name"].dropna().unique().tolist())
    trips_df = load_trips(season=selected_season, is_officer=is_officer)

    # --- TOP TABS: 1. OPERATIONS & ATTENDEE TRACKER, 2. CREATE NEW TRIP & FORM ---
    tab_attendees, tab_create_trip = st.tabs([
        "Trip Operations & Attendee Tracker",
        "Create New Trip & Sign-Up Form"
    ])

    # ==========================================
    # TAB 1: TRIP OPERATIONS & ATTENDEE TRACKER
    # (Structured similar to the Membership Tracker)
    # ==========================================
    with tab_attendees:
        st.markdown(f"### Trip Operations & Attendee Tracker ({selected_season})")
        st.markdown("Track attending athletes, driver carpool capacities, and toggle payment status directly in the table below.")

        if trips_df.empty:
            st.info(f"No trips scheduled yet for season '{selected_season}'. Create a trip first in the 'Create New Trip & Sign-Up Form' tab.")
        else:
            # Trip selector
            trip_choice_map = {f"{r['Name']} ({r['Destination']})": r["TripID"] for _, r in trips_df.iterrows()}
            trip_choice_keys = list(trip_choice_map.keys())

            # Validate op_sel_trip in session state
            if "op_sel_trip" in st.session_state and st.session_state["op_sel_trip"] not in trip_choice_keys:
                st.session_state["op_sel_trip"] = trip_choice_keys[0] if trip_choice_keys else ""

            selected_trip_label = st.selectbox("Select Trip to Manage", trip_choice_keys, key="op_sel_trip")
            selected_trip_id = trip_choice_map[selected_trip_label]
            selected_trip_row = trips_df[trips_df["TripID"] == selected_trip_id].iloc[0]

            # Signups data for this trip
            signups_df = load_trip_signups(trip_id_or_name=selected_trip_id, is_officer=is_officer)

            # --- TOP ROW: OPERATIONS METRICS DASHBOARD ---
            total_signups = len(signups_df)
            target_attendees = max(1, int(selected_trip_row.get("Attendees", 1)))
            target_vehicles = max(1, int(selected_trip_row.get("Vehicles", 1)))
            total_cost = float(selected_trip_row.get("TotalCost", 0.0))
            school_funding = float(selected_trip_row.get("SchoolFunding", 0.0)) if pd.notnull(selected_trip_row.get("SchoolFunding")) else 0.0
            net_cost = float(selected_trip_row.get("NetCost", total_cost - school_funding)) if pd.notnull(selected_trip_row.get("NetCost")) else max(0.0, total_cost - school_funding)
            approx_ticket_price = net_cost / target_attendees

            paid_df = signups_df[signups_df["PaymentReceived"] == True] if not signups_df.empty else pd.DataFrame()
            paid_count = len(paid_df)
            unpaid_count = total_signups - paid_count

            # Drivers parsing: attendees who signed up to drive for this trip (capacity >= 1)
            driver_records = []
            if not signups_df.empty:
                for _, r in signups_df.iterrows():
                    cap = extract_driver_capacity(r.get("DrivingCapacity", ""))
                    if cap > 0:
                        d_name = str(r.get("Name", "")).strip()
                        d_phone = str(r.get("Phone", "")).strip()
                        if d_phone.lower() == "nan":
                            d_phone = ""
                        driver_records.append({
                            "name": d_name,
                            "phone": d_phone,
                            "capacity": cap,
                            "raw_capacity": str(r.get("DrivingCapacity", ""))
                        })
            drivers_count = len(driver_records)
            total_driver_seats = sum(d["capacity"] for d in driver_records)
            driver_script_code = generate_driver_sheet_script(selected_trip_row["Name"], driver_records)
            slug_trip_name = selected_trip_row["Name"].lower().replace(" ", "_")

            cost_per_person_str = f"${approx_ticket_price:,.0f}" if approx_ticket_price == int(approx_ticket_price) else f"${approx_ticket_price:,.2f}"

            m1, m2, m3, m4 = st.columns(4)
            m1.metric(
                label="Total Attending Athletes",
                value=f"{total_signups} skiers"
            )
            m2.metric(
                label="Fee per Competitor" if selected_trip_row.get("TripType") == "Competition" else "Trip Cost per Person",
                value=cost_per_person_str,
                delta=f"-${school_funding:,.0f} school funded" if school_funding > 0 else None,
                delta_color="normal"
            )
            m3.metric(
                label="Driver Capacity Available",
                value=f"{drivers_count} Drivers" if total_driver_seats == 0 else f"{drivers_count} Drivers ({total_driver_seats} seats)"
            )
            m4.metric(
                label="Pending Payments",
                value=f"{unpaid_count} Unpaid"
            )

            st.divider()

            # --- GOOGLE FORMS LIVE SYNC SECTION FOR THIS TRIP ---
            with st.expander(f"Google Forms Live Sync & CSV Import for {selected_trip_row['Name']}", expanded=False):
                if not is_officer:
                    st.info("Officer access required to sync trip sign-ups. Enter the officer password in the sidebar to unlock.")
                elif not can_edit:
                    st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to sync trip sign-ups.")
                else:
                    st.markdown(
                        f"Sync responses from the Google Form sign-up sheet for **{selected_trip_row['Name']}**. "
                        "Make sure the response sheet is shared as 'Anyone with the link can view'."
                    )
                    tab_s_url, tab_s_upload = st.tabs(["Sync via Google Sheet URL", "Upload Response CSV"])

                    with tab_s_url:
                        trip_sheet_url = st.text_input(
                            "Trip Sign-Up Google Sheet URL or ID",
                            placeholder="https://docs.google.com/spreadsheets/d/YOUR_TRIP_SHEET_ID/edit#gid=...",
                            key=f"ts_url_{selected_trip_id}"
                        )
                        if st.button("Sync Sign-Up Responses from Sheet", key=f"btn_sync_{selected_trip_id}", width="stretch"):
                            if not trip_sheet_url.strip():
                                st.error("Please enter a valid Google Sheet URL.")
                            else:
                                with st.spinner("Connecting and syncing trip sign-ups..."):
                                    success, msg, count = fetch_and_sync_trip_form_sheet(
                                        trip_sheet_url,
                                        trip_id=selected_trip_id,
                                        trip_name=selected_trip_row['Name'],
                                        season=selected_trip_row['Season'],
                                        is_officer=is_officer
                                    )
                                    if success:
                                        st.success(msg)
                                        st.rerun()
                                    else:
                                        st.error(msg)

                    with tab_s_upload:
                        trip_csv_file = st.file_uploader(f"Upload Responses CSV for {selected_trip_row['Name']}", type=["csv"], key=f"trip_csv_{selected_trip_id}")
                        if trip_csv_file is not None:
                            if st.button("Import Uploaded CSV", key=f"btn_csv_{selected_trip_id}", width="stretch"):
                                try:
                                    df_uploaded_trip = pd.read_csv(trip_csv_file)
                                    success, msg, count = parse_and_sync_trip_form_df(
                                        df_uploaded_trip,
                                        trip_id=selected_trip_id,
                                        trip_name=selected_trip_row['Name'],
                                        season=selected_trip_row['Season'],
                                        is_officer=is_officer
                                    )
                                    if success:
                                        st.success(msg)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                                except Exception as e:
                                    st.error(f"Error parsing CSV: {e}")

            # --- MANUAL ATTENDEE ENTRY (ONLY ACTIVE REGISTERED MEMBERS) ---
            with st.expander(f"Add Registered Member to {selected_trip_row['Name']}", expanded=False):
                if not is_officer:
                    st.info("Officer access required to add members to trips. Enter the officer password in the sidebar to unlock.")
                elif not can_edit:
                    st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to add members to trips.")
                else:
                    trip_season = selected_trip_row.get("Season", CURRENT_SEASON)
                    active_members_df = load_members(season=trip_season if trip_season != "All Seasons" else None, is_officer=is_officer)
                    if active_members_df.empty:
                        active_members_df = load_members(season=None, is_officer=is_officer)

                    all_member_names = sorted(active_members_df["Name"].dropna().unique().tolist())

                    if not all_member_names:
                        st.warning("No registered members found. Attendees must be active club members. Please add members to Membership Tracking first.")
                    else:
                        st.caption("Select a registered club member to add them to this trip roster. Only active members can be added.")
                        chosen_member = st.selectbox(
                            "Select Active Member (Searchable)",
                            options=["-- Select Active Member --"] + all_member_names,
                            key=f"sel_active_member_{selected_trip_id}",
                            help="Type to search among all registered club members.",
                            filter_mode="fuzzy"
                        )
                        if chosen_member and chosen_member != "-- Select Active Member --":
                            m_matches = active_members_df[active_members_df["Name"] == chosen_member]
                            m_row = m_matches.iloc[0] if not m_matches.empty else None
                            default_phone = str(m_row.get("Phone", "")) if m_row is not None and pd.notnull(m_row.get("Phone")) else ""
                            if default_phone.lower() == "nan":
                                default_phone = ""

                            # Check if member is already signed up for this trip
                            is_already_signed_up = not signups_df.empty and (
                                signups_df["Name"].astype(str).str.lower().str.strip() == chosen_member.lower().strip()
                            ).any()

                            if is_already_signed_up:
                                st.warning(f"'{chosen_member}' is already registered on the roster for {selected_trip_row['Name']}.")
                            else:
                                with st.form(f"add_attendee_form_{selected_trip_id}_{chosen_member.replace(' ', '_')}"):
                                    c_a1, c_a2 = st.columns(2)
                                    with c_a1:
                                        st.text_input("Active Member", value=chosen_member, disabled=True, help="Verified active member.")
                                        att_phone = st.text_input("Phone Number", value=default_phone, help="Pre-filled from membership profile; update if needed.")
                                    with c_a2:
                                        att_drive = st.selectbox(
                                            "If you can drive (and how many passengers accounting for gear)",
                                            DEFAULT_TRIP_DRIVER_OPTIONS,
                                            index=0
                                        )
                                        att_paid = st.checkbox("Payment Received", value=False)

                                    att_questions = st.text_input("Questions or Concerns?", placeholder="e.g. Vegetarian meal request, snowboard rack, leaving IV Friday 4 PM")

                                    submit_att = st.form_submit_button(f"Save {chosen_member} to Trip Roster", width="stretch")
                                    if submit_att:
                                        final_phone = att_phone.strip() if att_phone.strip() else default_phone
                                        ok = add_trip_attendee(
                                            trip_id=selected_trip_id,
                                            trip_name=selected_trip_row['Name'],
                                            name=chosen_member,
                                            phone=final_phone,
                                            driving_capacity=att_drive,
                                            questions=att_questions,
                                            payment_received=att_paid,
                                            season=selected_trip_row['Season'],
                                            is_officer=is_officer
                                        )
                                        if ok:
                                            st.success(f"Added '{chosen_member}' to {selected_trip_row['Name']} and updated Membership Tracking.")
                                            st.rerun()
                                        else:
                                            st.error("Could not add attendee.")

            # --- DRIVER SIGN-UP SHEET GENERATOR (GOOGLE APPS SCRIPT) ---
            with st.expander(f"Driver Sign-Up Sheet Generator (Google Apps Script) - {selected_trip_row['Name']}", expanded=False):
                st.markdown(
                    f"Generate a pre-formatted Google Sheet for **{selected_trip_row['Name']}** carpools and driver assignments. "
                    "The Google Apps Script automatically populates confirmed drivers, phone numbers, and passenger capacities, "
                    "and fills unavailable passenger slots in **red**."
                )

                c_ds1, c_ds2, c_ds3 = st.columns(3)
                c_ds1.metric("Confirmed Drivers", f"{drivers_count} drivers")
                c_ds2.metric("Total Passenger Capacity", f"{total_driver_seats} seats")
                c_ds3.metric("Target Vehicles Needed", f"{target_vehicles} cars")

                if driver_records:
                    st.markdown("##### Confirmed Drivers Roster & Capacity Preview")
                    preview_rows = []
                    for d in driver_records:
                        cap = d["capacity"]
                        preview_rows.append({
                            "Driver": d["name"],
                            "Phone Number": d["phone"],
                            "# of Passengers": cap,
                            "Departure Time": "",
                            "Passenger 1": "Open" if cap >= 1 else "Unavailable (Red)",
                            "Passenger 2": "Open" if cap >= 2 else "Unavailable (Red)",
                            "Passenger 3": "Open" if cap >= 3 else "Unavailable (Red)",
                            "Passenger 4": "Open" if cap >= 4 else "Unavailable (Red)",
                        })
                    df_driver_preview = pd.DataFrame(preview_rows)
                    st.dataframe(df_driver_preview, width="stretch", hide_index=True)
                else:
                    st.info(
                        f"No attendees have signed up as drivers for '{selected_trip_row['Name']}' yet. "
                        "(Attendees must have a driving capacity of 1+ passengers in the roster). "
                        "You can still generate a blank template sheet using the script below, or add drivers first."
                    )

                st.markdown("##### 1-Click Google Apps Script Code")
                st.markdown(
                    "1. Open [script.google.com](https://script.google.com) and click **New project**.\n"
                    "2. Paste the code below and click **Run** (function `createDriverSignUpSheet`).\n"
                    "3. Open the newly created Google Sheet from the Execution Log link in your Google Drive!"
                )
                st.code(driver_script_code, language="javascript")

                st.download_button(
                    label=f"Download Driver Sheet Script (.js)",
                    data=driver_script_code,
                    file_name=f"create_driver_sheet_{slug_trip_name}.js",
                    mime="application/javascript",
                    key=f"dl_driver_script_exp_{selected_trip_id}"
                )

            # --- ATTENDEE ROSTER FILTERS & INTERACTIVE TABLE ---
            if total_signups == 0:
                st.info(f"No attendees registered yet for '{selected_trip_row['Name']}'. Use Google Forms sync above or 'Add Attendee Manually' to begin building the roster.")
            else:
                f_search, f_pay, f_driver = st.columns([2.2, 1.2, 1.2])
                with f_search:
                    search_q = st.text_input("Search Trip Attendees", placeholder="Search by name, phone, driving notes, or questions...", key=f"sq_{selected_trip_id}")
                with f_pay:
                    pay_filter = st.selectbox("Payment Status", ["All", "Paid Only", "Unpaid Only"], key=f"pf_{selected_trip_id}")
                with f_driver:
                    driver_filter = st.selectbox("Driver Status", ["All", "Drivers Only", "Non-Drivers Only"], key=f"df_{selected_trip_id}")

                filtered_signups = signups_df.copy()

                if pay_filter == "Paid Only":
                    filtered_signups = filtered_signups[filtered_signups["PaymentReceived"] == True]
                elif pay_filter == "Unpaid Only":
                    filtered_signups = filtered_signups[filtered_signups["PaymentReceived"] == False]

                if driver_filter == "Drivers Only":
                    filtered_signups = filtered_signups[~filtered_signups["DrivingCapacity"].astype(str).str.lower().str.strip().isin(["cannot drive", "no", "nan", ""])]
                elif driver_filter == "Non-Drivers Only":
                    filtered_signups = filtered_signups[filtered_signups["DrivingCapacity"].astype(str).str.lower().str.strip().isin(["cannot drive", "no", "nan", ""])]

                if search_q.strip():
                    q = search_q.strip().lower()
                    filtered_signups = filtered_signups[
                        filtered_signups["Name"].astype(str).str.lower().str.contains(q, na=False) |
                        filtered_signups["Phone"].astype(str).str.lower().str.contains(q, na=False) |
                        filtered_signups["DrivingCapacity"].astype(str).str.lower().str.contains(q, na=False) |
                        filtered_signups["Questions"].astype(str).str.lower().str.contains(q, na=False)
                    ]

                st.caption(f"Showing **{len(filtered_signups)}** of **{total_signups}** attendees &bull; *Toggle the Payment Received checkbox directly inside the table.*")

                # Prepare editable DataFrame with trip sign-up fields
                display_cols = ["SignupID", "PaymentReceived", "Name", "Phone", "DrivingCapacity", "Questions", "SignupDate"]
                editor_signups = filtered_signups[display_cols].copy()
                editor_signups.columns = [
                    "ID", "Payment Received", "Name", "Phone",
                    "If you can drive (and how many passengers accounting for gear)",
                    "Questions or Concerns?", "Sign-Up Date"
                ]

                # Ensure strict compatible types for Streamlit data_editor column_configs
                editor_signups["Payment Received"] = editor_signups["Payment Received"].fillna(False).astype(bool)
                for txt_col in ["ID", "Name", "Phone", "Questions or Concerns?", "Sign-Up Date"]:
                    editor_signups[txt_col] = (
                        editor_signups[txt_col]
                        .fillna("")
                        .astype(str)
                        .replace({"nan": "", "None": "", "NaN": ""})
                    )

                def _clean_driver_val(v):
                    s = str(v).strip() if pd.notnull(v) else ""
                    if s in DEFAULT_TRIP_DRIVER_OPTIONS:
                        return s
                    for opt in DEFAULT_TRIP_DRIVER_OPTIONS:
                        if s and (s.lower() in opt.lower() or opt.lower() in s.lower()):
                            return opt
                    return DEFAULT_TRIP_DRIVER_OPTIONS[0]

                driver_col_name = "If you can drive (and how many passengers accounting for gear)"
                editor_signups[driver_col_name] = (
                    editor_signups[driver_col_name]
                    .apply(_clean_driver_val)
                    .astype(str)
                )

                edited_signups_result = st.data_editor(
                    editor_signups,
                    column_config={
                        "Payment Received": st.column_config.CheckboxColumn(
                            "Payment Received",
                            help="Check when athlete sends payment via Venmo/Zelle",
                            default=False
                        ),
                        "ID": st.column_config.TextColumn("ID", disabled=True),
                        "Name": st.column_config.TextColumn("Name", disabled=True),
                        "Phone": st.column_config.TextColumn("Phone"),
                        "If you can drive (and how many passengers accounting for gear)": st.column_config.SelectboxColumn(
                            "If you can drive (and how many passengers accounting for gear)",
                            options=DEFAULT_TRIP_DRIVER_OPTIONS,
                            required=True
                        ),
                        "Questions or Concerns?": st.column_config.TextColumn(
                            "Questions or Concerns?",
                            help="Dietary restrictions, carpool notes, or gear questions",
                        ),
                        "Sign-Up Date": st.column_config.TextColumn("Sign-Up Date", disabled=True)
                    },
                    disabled=["ID", "Name", "Sign-Up Date"] if (is_officer and can_edit) else True,
                    hide_index=True,
                    width="stretch",
                    height=420,
                    key=f"editor_trip_signups_{selected_trip_id}"
                )

                if is_officer and not can_edit:
                    st.caption("Officer viewing mode active (read-only). Enable the Editing toggle in the sidebar to edit payments or driver capacities.")
                elif not is_officer:
                    st.caption("Viewing trip roster in read-only mode. Enter the officer password in the sidebar to edit payments or driver capacities.")

                if is_officer and can_edit and not edited_signups_result.equals(editor_signups):
                    if save_edited_trip_signups(edited_signups_result, selected_trip_id, is_officer=is_officer):
                        st.success("Attendee updates and payment status saved directly to database.")
                        st.rerun()

                # Action Bar: CSV Export, Driver Sheet Script Popover & Multi-Attendee Removal
                c_exp, c_drv, c_rem = st.columns([2.0, 1.8, 1.2])
                with c_exp:
                    csv_signups = filtered_signups.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label=f"Export Attendee Roster to CSV",
                        data=csv_signups,
                        file_name=f"trip_roster_{selected_trip_row['Name'].lower().replace(' ', '_')}_{date.today().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        key=f"dl_roster_{selected_trip_id}"
                    )
                with c_drv:
                    with st.popover("Driver Sheet Script"):
                        st.markdown(f"**Driver Sign-Up Sheet ({selected_trip_row['Name']})**")
                        st.caption(f"**{drivers_count}** driver(s) registered ({total_driver_seats} total seats).")
                        st.code(driver_script_code, language="javascript")
                        st.download_button(
                            label="Download Script (.js)",
                            data=driver_script_code,
                            file_name=f"create_driver_sheet_{slug_trip_name}.js",
                            mime="application/javascript",
                            key=f"dl_driver_script_pop_{selected_trip_id}"
                        )
                with c_rem:
                    with st.popover("Remove Attendees"):
                        if not is_officer:
                            st.info("Officer access required to remove attendees. Enter the officer password in the sidebar to unlock.")
                        elif not can_edit:
                            st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to remove attendees.")
                        else:
                            st.markdown("**Remove Trip Attendees**")
                            att_remove_map = {}
                            seen_names = set()
                            if not signups_df.empty:
                                for _, r in signups_df.iterrows():
                                    s_name = str(r.get("Name", "")).strip()
                                    s_id = str(r.get("SignupID", "")).strip()
                                    if s_name:
                                        att_remove_map[f"{s_name} ({s_id})"] = {"signup_id": s_id, "name": s_name}
                                        seen_names.add(s_name.lower())

                            # Also include athletes listed in AttendeeRoster who don't have a SignupID
                            roster_str = str(selected_trip_row.get("AttendeeRoster", "")).strip()
                            if roster_str and roster_str.lower() not in ["nan", "none", "0.0", "0"]:
                                for r_name in roster_str.split(","):
                                    c_name = r_name.strip()
                                    if c_name and c_name.lower() not in ["nan", "none", "0.0", "0"]:
                                        if c_name.lower() not in seen_names:
                                            att_remove_map[f"{c_name} (Roster)"] = {"signup_id": None, "name": c_name}
                                            seen_names.add(c_name.lower())

                            if att_remove_map:
                                chosen_att_labels = st.multiselect(
                                    "Select Attendee(s) to Remove",
                                    options=list(att_remove_map.keys()),
                                    key=f"sel_rem_multi_{selected_trip_id}",
                                    help="Select one or more attendees to remove from this trip."
                                )
                                if chosen_att_labels:
                                    st.caption(f"Selected **{len(chosen_att_labels)}** attendee(s) for removal.")
                                    if st.button(f"Confirm Remove ({len(chosen_att_labels)})", type="primary", key=f"btn_confirm_rem_{selected_trip_id}"):
                                        rem_items = [att_remove_map[label] for label in chosen_att_labels]
                                        removed_count = delete_multiple_trip_attendees(
                                            rem_items,
                                            trip_id=selected_trip_id,
                                            trip_name=selected_trip_row["Name"],
                                            season=selected_trip_row.get("Season"),
                                            is_officer=is_officer
                                        )
                                        if removed_count > 0:
                                            st.success(f"Removed {removed_count} attendee(s) from {selected_trip_row['Name']}.")
                                            st.rerun()
                                        else:
                                            st.error("Could not remove attendees.")
                            else:
                                st.info("No attendees available to remove.")

            # Summary Card & Delete Trip Action
            st.divider()
            c_card1, c_card_stat, c_card2 = st.columns([2.5, 1.2, 0.9])
            with c_card1:
                st.markdown(f"#### {selected_trip_row['Name']} &bull; Details & Budget")
                st.markdown(
                    f"**Destination:** {selected_trip_row['Destination']} &bull; "
                    f"**Type:** `{selected_trip_row.get('TripType', 'Recreational')}` &bull; "
                    f"**Dates:** {selected_trip_row['StartDate']} to {selected_trip_row.get('EndDate', '')} ({selected_trip_row['Nights']} nights)"
                )
                cabin_c = float(selected_trip_row.get('CabinCost', 0))
                food_c = float(selected_trip_row.get('FoodAlcoholCost', 0))
                gas_c = float(selected_trip_row.get('GasCost', 0))
                tickets_c = float(selected_trip_row.get('LiftTicketsCost', 0))
                total_c = float(selected_trip_row.get('TotalCost', 0))
                funding_c = float(selected_trip_row.get('SchoolFunding', 0)) if pd.notnull(selected_trip_row.get('SchoolFunding')) else 0.0
                net_c = float(selected_trip_row.get('NetCost', total_c - funding_c)) if pd.notnull(selected_trip_row.get('NetCost')) else max(0.0, total_c - funding_c)
                cov_det = str(selected_trip_row.get('SchoolCoverageDetails', '')).strip()

                budget_parts = [
                    f"Cabin \\${cabin_c:,.0f}",
                    f"Food & Drink \\${food_c:,.0f}"
                ]
                if gas_c > 0:
                    budget_parts.append(f"Gas \\${gas_c:,.0f}")
                if tickets_c > 0:
                    budget_parts.append(f"Tickets \\${tickets_c:,.0f}")
                if funding_c > 0:
                    budget_parts.append(f"Gross \\${total_c:,.0f}")
                    budget_parts.append(f"School Subsidy -\\${funding_c:,.0f}")
                    budget_parts.append(f"Net Team Cost \\${net_c:,.0f} (~\\${approx_ticket_price:,.0f} / competitor)")
                else:
                    budget_parts.append(f"Total \\${total_c:,.0f} (~\\${approx_ticket_price:,.0f} / skier)")

                st.caption("Budget: " + " | ".join(budget_parts))
                if funding_c > 0 and cov_det:
                    st.caption(f"*School Coverage Items: {cov_det}*")
            with c_card_stat:
                st.write("")
                curr_op_stat = str(selected_trip_row.get("Status", "Planning")).strip()
                op_stat_opts = [opt for opt in TRIP_STATUS_OPTIONS]
                if curr_op_stat and curr_op_stat not in op_stat_opts:
                    op_stat_opts.insert(0, curr_op_stat)
                op_stat_idx = op_stat_opts.index(curr_op_stat) if curr_op_stat in op_stat_opts else 0
                new_op_stat = st.selectbox(
                    "Trip Status",
                    options=op_stat_opts,
                    index=op_stat_idx,
                    key=f"op_status_sel_{selected_trip_id}_{curr_op_stat}",
                    disabled=not (is_officer and can_edit),
                    help="Update trip status." if (is_officer and can_edit) else ("Officer editing mode is disabled. Toggle 'Enable Editing Mode' in the sidebar." if is_officer else "Officer access required to change trip status.")
                )
                if is_officer and can_edit and new_op_stat != curr_op_stat:
                    if update_trip_status(selected_trip_id, new_op_stat, is_officer=is_officer):
                        st.success(f"Trip status updated to '{new_op_stat}'.")
                        st.rerun()
            with c_card2:
                st.write("")
                st.write("")
                with st.popover("Delete Entire Trip"):
                    if not is_officer:
                        st.info("Officer access required to delete trips. Enter the officer password in the sidebar to unlock.")
                    elif not can_edit:
                        st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to delete trips.")
                    else:
                        st.caption(f"Delete {selected_trip_row['Name']} and remove all sign-ups?")
                        if st.button("Yes, Delete Trip", key=f"del_trip_full_{selected_trip_id}", type="primary"):
                            if delete_trip(selected_trip_id, is_officer=is_officer):
                                st.success("Trip deleted.")
                                st.rerun()

    # ==========================================
    # TAB 2: CREATE NEW TRIP & SIGN-UP FORM
    # (With Built-in Google Form Sign-Up Generator)
    # ==========================================
    with tab_create_trip:
        st.markdown(f"### Create New Trip & Google Form Sign-Up ({selected_season})")
        if not is_officer:
            st.info("Officer access required to create trips and generate sign-up forms. Enter the officer password in the sidebar to unlock.")
        elif not can_edit:
            st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to create new trips and generate sign-up forms.")
        else:
            _render_create_trip_form(selected_season, dest_options, is_officer=is_officer, can_edit=can_edit)

