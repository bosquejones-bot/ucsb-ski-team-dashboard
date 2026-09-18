"""
Ledger module for the UCSB Ski Team Dashboard.
Provides an interactive transaction table filtered by season, searching,
CSV export, and an easy-to-use Officer Entry Form.
"""

import streamlit as st
import pandas as pd
from datetime import date
from utils.data_manager import (
    load_ledger, add_transaction, delete_transaction, save_edited_ledger, load_officers,
    sync_ledger_from_google_sheet, import_ledger_dataframe, get_master_ledger_csv_bytes
)
import config
from config import (
    INCOME_CATEGORIES, EXPENSE_CATEGORIES, ALL_CATEGORIES, CURRENT_SEASON, AVAILABLE_SEASONS
)

DEFAULT_LEDGER_SHEET_URL = getattr(config, "DEFAULT_LEDGER_SHEET_URL", "")


def render_ledger_tab(selected_season: str = CURRENT_SEASON, is_officer: bool = False, can_edit: bool = None):
    if can_edit is None:
        can_edit = is_officer

    st.markdown(f"## Financial Ledger and Officer Entry Portal ({selected_season})")
    st.markdown("View transactions for the selected season, search receipts, and record team revenues or disbursements.")

    # --- OFFICER TRANSACTION ENTRY FORM ---
    with st.expander("Log New Transaction (Officer Entry Form)", expanded=False):
        if not is_officer:
            st.info("Officer access required to record new transactions. Enter the officer password in the sidebar to unlock.")
        elif not can_edit:
            st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to log new transactions.")
        else:
            st.markdown(f"*Record new receipts or revenues for season {selected_season if selected_season != 'All Seasons' else CURRENT_SEASON}.*")
            
            officers_list = load_officers(is_officer=is_officer)
            if not officers_list:
                officers_list = ["President", "Vice President", "Treasurer", "Trip Lead"]

            with st.form("new_transaction_form", clear_on_submit=True):
                r1_col1, r1_col2, r1_col3 = st.columns(3)
                with r1_col1:
                    entry_date = st.date_input("Transaction Date", value=date.today())
                with r1_col2:
                    trans_type = st.radio("Transaction Type", ["Expense", "Income"], horizontal=True)
                with r1_col3:
                    categories = EXPENSE_CATEGORIES if trans_type == "Expense" else INCOME_CATEGORIES
                    category = st.selectbox("Category", categories)

                r2_col1, r2_col2, r2_col3 = st.columns(3)
                with r2_col1:
                    entity = st.text_input("Entity / Payer / Vendor", placeholder="e.g. Costco, Team Officer, Albertsons")
                with r2_col2:
                    amount = st.number_input("Amount ($ USD)", min_value=0.01, max_value=50000.0, step=1.00, value=50.00)
                with r2_col3:
                    logged_by = st.selectbox("Logged By Officer", officers_list)

                notes = st.text_input("Notes / Description", placeholder="e.g. Mammoth trip cabin deposit, team snacks")

                target_entry_season = selected_season if selected_season != "All Seasons" else CURRENT_SEASON
                submit_button = st.form_submit_button("Record Transaction", use_container_width=True)

                if submit_button:
                    if not entity.strip():
                        st.error("Please provide an Entity / Payer / Vendor name.")
                    else:
                        date_str = entry_date.strftime("%m-%d-%Y")
                        success = add_transaction(
                            date_str, entity, amount, category, notes, trans_type,
                            season=target_entry_season, is_officer=is_officer, logged_by=logged_by
                        )
                        if success:
                            st.success(f"Successfully recorded {trans_type} of ${amount:,.2f} for '{entity}' logged by {logged_by} in {target_entry_season}.")
                            st.rerun()
                        else:
                            st.error("Failed to save transaction. Please try again.")

    # --- GOOGLE SHEETS LIVE SYNC AND CSV BACKUP ---
    with st.expander("Google Sheets Live Sync and CSV Ledger Backup", expanded=False):
        if not is_officer:
            st.info("Officer access required to synchronize Google Sheets or restore CSV backups. Enter the officer password in the sidebar to unlock.")
        elif not can_edit:
            st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to sync Google Sheets or restore CSV backups.")
        else:
            st.markdown(
                "Keep your financial ledger securely synced with a private Google Sheet or import/export CSV backups. "
                "No transaction data is stored in the public GitHub repository."
            )
            tab_sheet, tab_upload_csv, tab_backup = st.tabs([
                "Sync via Google Sheet",
                "Upload / Restore CSV",
                "Export Master Ledger Backup"
            ])

            with tab_sheet:
                st.caption(
                    "Link your master financial Google Sheet. Ensure your sheet sharing is set to "
                    "'Anyone with the link can view' so the cloud server can read records."
                )
                sheet_url_input = st.text_input(
                    "Google Sheet URL or Spreadsheet ID",
                    value=DEFAULT_LEDGER_SHEET_URL,
                    placeholder="https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit#gid=0",
                    help="Configured securely via LEDGER_SHEET_URL in Streamlit secrets."
                )
                sync_mode = st.radio(
                    "Sync Action",
                    ["Replace Entire Ledger (Recommended for Master Google Sheet)", "Append New Transactions Only"],
                    index=0,
                    horizontal=True,
                    key="sheet_sync_mode_radio"
                )
                mode_val = "replace" if "Replace" in sync_mode else "append"

                if st.button("Sync Ledger from Google Sheet", use_container_width=True):
                    if not sheet_url_input.strip():
                        st.error("Please enter a valid Google Sheet URL or ID.")
                    else:
                        with st.spinner("Connecting to Google Sheet and synchronizing transactions..."):
                            success, message, count = sync_ledger_from_google_sheet(
                                sheet_url_input, mode=mode_val, is_officer=is_officer
                            )
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)

            with tab_upload_csv:
                st.caption("Upload a full ledger CSV or exported transactions file to restore records directly.")
                uploaded_csv = st.file_uploader("Upload Ledger CSV File", type=["csv"], key="ledger_csv_uploader")
                upload_mode = st.radio(
                    "Import Action",
                    ["Replace Entire Ledger", "Append New Transactions Only"],
                    index=0,
                    horizontal=True,
                    key="csv_upload_mode_radio"
                )
                mode_upload_val = "replace" if "Replace" in upload_mode else "append"

                if uploaded_csv is not None:
                    if st.button("Import Uploaded CSV into Master Ledger", use_container_width=True):
                        try:
                            df_uploaded = pd.read_csv(uploaded_csv)
                            with st.spinner("Processing and validating transactions..."):
                                success, message, count = import_ledger_dataframe(
                                    df_uploaded, mode=mode_upload_val, is_officer=is_officer
                                )
                                if success:
                                    st.success(message)
                                    st.rerun()
                                else:
                                    st.error(message)
                        except Exception as e:
                            st.error(f"Error reading uploaded CSV file: {e}")

            with tab_backup:
                st.markdown("**Download Complete Master Ledger (All Seasons)**")
                st.caption(
                    "Download the entire team financial ledger (including all historical and current season transactions) "
                    "as a clean CSV. You can open this in Excel or upload it directly into Google Drive to create your master Google Sheet."
                )
                master_csv_bytes = get_master_ledger_csv_bytes(is_officer=is_officer)
                total_master_rows = len(load_ledger(season=None, is_officer=is_officer))
                st.download_button(
                    label=f"Download Master Ledger CSV ({total_master_rows:,} Records)",
                    data=master_csv_bytes,
                    file_name=f"ucsb_ski_team_master_ledger_all_seasons_{date.today().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    help="Export all records across all seasons to set up your Google Sheet or keep an offline backup."
                )

    st.divider()

    # --- LEDGER VIEW & FILTERS ---
    full_ledger = load_ledger(season=None, is_officer=is_officer).copy()
    full_ledger["Row"] = full_ledger.index

    if selected_season != "All Seasons":
        ledger_df = full_ledger[full_ledger["Season"] == selected_season].copy()
    else:
        ledger_df = full_ledger.copy()

    if ledger_df.empty:
        st.info(f"The ledger currently has 0 transactions for season '{selected_season}'. Use the form above to add a new transaction.")
        return

    # Filters row
    col_search, col_type, col_cat = st.columns([2, 1, 1.5])

    with col_search:
        search_query = st.text_input("Search Entity or Notes", placeholder="Type name, vendor, note...")

    with col_type:
        type_filter = st.selectbox("Type Filter", ["All", "Income", "Expense"])

    with col_cat:
        cat_options = ["All Categories"] + sorted(list(ledger_df["Category"].dropna().unique()))
        cat_filter = st.selectbox("Category Filter", cat_options)

    # Filter dataframe
    filtered_df = ledger_df.copy()

    if type_filter != "All":
        filtered_df = filtered_df[filtered_df["Type"] == type_filter]

    if cat_filter != "All Categories":
        filtered_df = filtered_df[filtered_df["Category"] == cat_filter]

    if "LoggedBy" not in filtered_df.columns:
        filtered_df["LoggedBy"] = ""
    filtered_df["LoggedBy"] = filtered_df["LoggedBy"].fillna("")

    if search_query.strip():
        q = search_query.strip().lower()
        filtered_df = filtered_df[
            filtered_df["Entity"].astype(str).str.lower().str.contains(q, na=False) |
            filtered_df["Notes"].astype(str).str.lower().str.contains(q, na=False) |
            filtered_df["Category"].astype(str).str.lower().str.contains(q, na=False) |
            filtered_df["LoggedBy"].astype(str).str.lower().str.contains(q, na=False)
        ]

    # Summary metrics for current filtered view
    total_in = filtered_df[filtered_df["Type"] == "Income"]["Amount"].sum()
    total_out = filtered_df[filtered_df["Type"] == "Expense"]["Amount"].sum()
    net_filtered = total_in - total_out

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Rows Displayed", f"{len(filtered_df):,} of {len(ledger_df):,}")
    m2.metric("Filtered Inflow", f"${total_in:,.2f}")
    m3.metric("Filtered Outflow", f"${total_out:,.2f}")
    m4.metric("Net Selection", f"${net_filtered:,.2f}")

    # Editable Transaction Table with all fields editable
    cols_to_show = ["Row", "Season", "Date", "Entity", "Type", "Category", "Amount", "LoggedBy", "Notes"]
    display_df = filtered_df[cols_to_show].copy()
    display_df["Amount"] = pd.to_numeric(display_df["Amount"], errors="coerce").fillna(0.0)

    officers_list = load_officers(is_officer=is_officer)
    if not officers_list:
        officers_list = ["President", "Vice President", "Treasurer", "Trip Lead"]

    if is_officer and can_edit:
        st.caption("All fields below are directly editable. Click any cell to modify Date, Entity, Type, Category, Amount, Logged By, Notes, or Season. Edits save automatically.")
    elif is_officer:
        st.caption("Officer viewing mode active (read-only). Enable the Editing toggle in the sidebar to modify transaction details directly.")
    else:
        st.caption("Viewing ledger in read-only mode. Enter the officer password in the sidebar to edit transactions.")

    disabled_cols = ["Row"] if (is_officer and can_edit) else True

    edited_ledger = st.data_editor(
        display_df,
        column_config={
            "Row": st.column_config.NumberColumn(
                "Row",
                help="Row ID in master ledger (read-only index)",
                disabled=True,
            ),
            "Season": st.column_config.SelectboxColumn(
                "Season",
                help="Academic season for this transaction",
                options=AVAILABLE_SEASONS,
                required=True,
            ),
            "Date": st.column_config.TextColumn(
                "Date",
                help="Transaction date in MM-DD-YYYY format",
                required=True,
            ),
            "Entity": st.column_config.TextColumn(
                "Entity / Vendor / Payer",
                help="Person, store, or vendor name",
                required=True,
            ),
            "Type": st.column_config.SelectboxColumn(
                "Type",
                help="Transaction classification",
                options=["Expense", "Income"],
                required=True,
            ),
            "Category": st.column_config.SelectboxColumn(
                "Category",
                help="Financial ledger category",
                options=ALL_CATEGORIES,
                required=True,
            ),
            "Amount": st.column_config.NumberColumn(
                "Amount ($)",
                help="Transaction dollar amount in USD",
                min_value=0.01,
                max_value=100000.0,
                step=0.01,
                format="$%.2f",
                required=True,
            ),
            "LoggedBy": st.column_config.SelectboxColumn(
                "Logged By Officer",
                help="Officer who recorded or authorized this transaction",
                options=officers_list,
            ),
            "Notes": st.column_config.TextColumn(
                "Notes / Description",
                help="Receipt memo, expense description, or notes",
            ),
        },
        disabled=disabled_cols,
        hide_index=True,
        width="stretch",
        height=480,
        key=f"editor_ledger_{selected_season}_{type_filter}_{cat_filter}"
    )

    # Detect in-table changes and persist immediately
    if is_officer and can_edit and not edited_ledger.equals(display_df):
        if save_edited_ledger(edited_ledger, is_officer=is_officer):
            st.success("Ledger entry updated successfully.")
            st.rerun()
        else:
            st.error("Failed to save changes to the ledger.")

    # Export & Management Tools
    col_dl, col_del = st.columns([3, 1])
    with col_dl:
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            export_cols = [c for c in filtered_df.columns if c not in ["Row", "Date_dt"]]
            csv_data = filtered_df[export_cols].to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"Export Filtered View ({len(filtered_df):,} Rows)",
                data=csv_data,
                file_name=f"ucsb_ski_team_ledger_{selected_season}_{date.today().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                help="Download currently filtered records for audit or quick inspection."
            )
        with dl_col2:
            master_csv = get_master_ledger_csv_bytes(is_officer=is_officer)
            st.download_button(
                label=f"Export Master Ledger ({len(full_ledger):,} Rows)",
                data=master_csv,
                file_name=f"ucsb_ski_team_master_ledger_all_seasons_{date.today().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                help="Download complete historical master ledger across all seasons."
            )

    with col_del:
        with st.popover("Treasurer Actions"):
            if not is_officer:
                st.info("Officer access required to delete transactions. Enter the officer password in the sidebar to unlock.")
            elif not can_edit:
                st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to delete transactions.")
            else:
                st.markdown("**Delete a Transaction**")
                st.caption("Select a transaction to remove by its row number:")

                available_rows = filtered_df["Row"].tolist() if not filtered_df.empty else ledger_df["Row"].tolist()
                if available_rows:
                    selected_del_row = st.selectbox(
                        "Select Row to Delete",
                        options=available_rows,
                        format_func=lambda idx: (
                            f"Row {idx}: {full_ledger.loc[idx, 'Date']} | "
                            f"{full_ledger.loc[idx, 'Entity']} | "
                            f"${full_ledger.loc[idx, 'Amount']:,.2f} | "
                            f"{full_ledger.loc[idx, 'Category']}"
                        )
                    )

                    target_trans = full_ledger.loc[selected_del_row]
                    st.caption(
                        f"**Pending Deletion:** Row {selected_del_row} &bull; "
                        f"{target_trans['Date']} &bull; {target_trans['Entity']} &bull; "
                        f"{target_trans['Type']} &bull; ${target_trans['Amount']:,.2f} &bull; {target_trans['Category']}"
                    )

                    if st.button("Confirm Delete", type="primary", use_container_width=True):
                        if delete_transaction(int(selected_del_row), is_officer=is_officer):
                            st.success(f"Row {selected_del_row} deleted successfully.")
                            st.rerun()
                        else:
                            st.error(f"Failed to delete row {selected_del_row}.")
                else:
                    st.caption("No rows available to delete in this view.")
