"""
Officer To-Do List and Task Delegation module for the UCSB Ski Team Dashboard.
Allows assigning tasks to one or multiple club officers, tracking target dates,
and maintaining a permanent archive of completed tasks.
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils.data_manager import (
    load_todos, add_todo, set_todo_status, delete_todo,
    load_officers, add_officer, delete_officer
)
from config import CURRENT_SEASON, THEME_COLORS


def render_todo_tab(selected_season: str = CURRENT_SEASON, is_officer: bool = False, can_edit: bool = None):
    if can_edit is None:
        can_edit = is_officer

    st.markdown(f"## Officer Task Delegation and To-Do List ({selected_season})")
    st.markdown("Assign club operations tasks to fellow officers, set target deadlines, and track execution across the board.")

    officers_pool = load_officers(is_officer=is_officer)

    # --- MANAGE OFFICER BOARD (ADD / REMOVE OFFICERS) ---
    with st.expander("Manage Officer Board (Add / Remove Officers)", expanded=False):
        if not is_officer:
            st.info("Officer access required to manage the officer board. Enter the officer password in the sidebar to unlock.")
        elif not can_edit:
            st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to add or remove officers.")
        else:
            st.markdown("##### Current Officer Board")
            officers_display = " &bull; ".join([f"`{o}`" for o in officers_pool])
            st.markdown(f"**Active Officers ({len(officers_pool)}):** {officers_display}")
            st.caption("Officers added or removed here update the delegation pool across task creation, task filters, and merch logs.")

            col_add_off, col_del_off = st.columns(2)

            with col_add_off:
                st.markdown("###### Add New Officer")
                with st.form("form_add_officer", clear_on_submit=True):
                    new_officer_name = st.text_input("Officer Name or Role", placeholder="e.g. Taylor Smith, Safety Officer")
                    submit_add_off = st.form_submit_button("Add Officer", width="stretch")
                    if submit_add_off:
                        if not new_officer_name.strip():
                            st.error("Please enter an officer name.")
                        else:
                            ok, msg = add_officer(new_officer_name.strip(), is_officer=is_officer)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)

            with col_del_off:
                st.markdown("###### Remove Existing Officer")
                with st.form("form_delete_officer"):
                    officer_to_remove = st.selectbox("Select Officer to Remove", options=officers_pool)
                    submit_del_off = st.form_submit_button("Remove Officer", type="primary", width="stretch")
                    if submit_del_off:
                        ok, msg = delete_officer(officer_to_remove, is_officer=is_officer)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

    # --- CREATE NEW TASK FORM ---
    with st.expander("Create New Officer Task", expanded=False):
        if not is_officer:
            st.info("Officer access required to assign new tasks. Enter the officer password in the sidebar to unlock.")
        elif not can_edit:
            st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to assign new tasks.")
        else:
            with st.form("form_new_todo", clear_on_submit=True):
                title = st.text_input("Task Title", placeholder="e.g. Confirm cabin booking at Mammoth, Order race bibs")
                description = st.text_area("Task Description & Deliverables", placeholder="Provide relevant details, vendor links, confirmation numbers, or requirements...")

                c_off1, c_off2 = st.columns(2)
                with c_off1:
                    assigned_officers = st.multiselect("Assign Officer(s)", options=officers_pool)
                with c_off2:
                    target_date = st.date_input("Target Completion Date", value=date.today() + timedelta(days=7))

                c_sub1, c_sub2 = st.columns(2)
                with c_sub1:
                    submitted_date = st.date_input("Request Submission Date", value=date.today())
                with c_sub2:
                    notes = st.text_input("Additional Notes / Priority", placeholder="e.g. High priority, budget deadline next week")

                target_todo_season = selected_season if selected_season != "All Seasons" else CURRENT_SEASON
                submit_task = st.form_submit_button("Assign Task", width="stretch")

                if submit_task:
                    if not title.strip():
                        st.error("Please provide a Task Title.")
                    elif not assigned_officers:
                        st.error("Please assign at least one officer.")
                    else:
                        success = add_todo(
                            title=title,
                            description=description,
                            assigned_to_list=assigned_officers,
                            target_date=target_date.strftime("%Y-%m-%d"),
                            submitted_date=submitted_date.strftime("%Y-%m-%d"),
                            notes=notes,
                            season=target_todo_season,
                            is_officer=is_officer
                        )
                        if success:
                            st.success(f"Task '{title}' assigned to {', '.join(assigned_officers)}.")
                            st.rerun()
                        else:
                            st.error("Could not save task. Please try again.")

    st.divider()

    # --- LOAD AND DISPLAY TASKS ---
    all_todos_df = load_todos(season=selected_season, is_officer=is_officer)
    active_todos = all_todos_df[all_todos_df["Status"] == "Pending"] if not all_todos_df.empty else pd.DataFrame()
    completed_todos = all_todos_df[all_todos_df["Status"] == "Completed"] if not all_todos_df.empty else pd.DataFrame()

    # Summary metric cards
    m1, m2, m3 = st.columns(3)
    m1.metric("Active Tasks Pending", f"{len(active_todos)}")
    m2.metric("Archived Completed Tasks", f"{len(completed_todos)}")
    m3.metric("Board Members", f"{len(officers_pool)} Officers")

    # Tabs for Active vs Completed Archive
    tab_active, tab_archive = st.tabs(["Active To-Do List", "Archive of Completed Tasks"])

    # --- ACTIVE TASKS VIEW ---
    with tab_active:
        if active_todos.empty:
            st.info(f"No active tasks pending for season '{selected_season}'. Create a new task above.")
        else:
            # Officer filter
            col_filt1, col_filt2 = st.columns([1.5, 2.5])
            with col_filt1:
                officer_filter = st.selectbox("Filter by Assigned Officer", ["All Officers"] + officers_pool, key="active_officer_filter")

            filtered_active = active_todos.copy()
            if officer_filter != "All Officers":
                filtered_active = filtered_active[filtered_active["AssignedTo"].str.contains(officer_filter, na=False)]

            st.caption(f"Showing **{len(filtered_active)}** active task(s)")

            for _, task in filtered_active.iterrows():
                with st.container():
                    c_card, c_action = st.columns([3, 1])
                    with c_card:
                        st.markdown(f"#### {task['Title']}")
                        st.markdown(f"**Assigned Officers:** `{task['AssignedTo']}`")
                        if str(task['Description']).strip() and str(task['Description']) != 'nan':
                            st.write(task['Description'])
                        st.caption(f"Submitted: {task['SubmittedDate']} &bull; **Target Completion: {task['TargetDate']}** &bull; Season: {task['Season']}")
                        if str(task['Notes']).strip() and str(task['Notes']) != 'nan':
                            st.caption(f"Notes: {task['Notes']}")

                    with c_action:
                        st.write("")
                        st.write("")
                        if st.button("Mark Completed", key=f"btn_done_{task['TaskID']}", type="primary", width="stretch", disabled=not (is_officer and can_edit), help=None if (is_officer and can_edit) else ("Officer editing mode is disabled. Toggle 'Enable Editing Mode' in the sidebar." if is_officer else "Officer access required to complete tasks")):
                            if set_todo_status(task['TaskID'], "Completed", is_officer=is_officer):
                                st.success(f"Task '{task['Title']}' moved to Completed Archive.")
                                st.rerun()

                        with st.popover("Delete Task"):
                            if not is_officer:
                                st.info("Officer access required to delete tasks.")
                            elif not can_edit:
                                st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to delete tasks.")
                            else:
                                st.caption(f"Remove '{task['Title']}'?")
                                if st.button("Confirm Delete", key=f"btn_del_{task['TaskID']}", type="secondary"):
                                    if delete_todo(task['TaskID'], is_officer=is_officer):
                                        st.success("Task deleted.")
                                        st.rerun()

                    st.divider()

    # --- ARCHIVE OF COMPLETED TASKS ---
    with tab_archive:
        if completed_todos.empty:
            st.info("No completed tasks archived yet.")
        else:
            col_arch_filt, _ = st.columns([1.5, 2.5])
            with col_arch_filt:
                arch_officer_filter = st.selectbox("Filter Archive by Officer", ["All Officers"] + officers_pool, key="arch_officer_filter")

            filtered_completed = completed_todos.copy()
            if arch_officer_filter != "All Officers":
                filtered_completed = filtered_completed[filtered_completed["AssignedTo"].str.contains(arch_officer_filter, na=False)]

            st.caption(f"Showing **{len(filtered_completed)}** completed task(s)")

            # Table view of completed archive
            disp_arch = filtered_completed[["TaskID", "Title", "AssignedTo", "SubmittedDate", "TargetDate", "CompletedDate", "Notes"]].copy()
            disp_arch.columns = ["Task ID", "Title", "Assigned Officers", "Submitted", "Target Date", "Completed On", "Notes"]
            st.dataframe(disp_arch, width="stretch", hide_index=True)

            # Detail list with re-open option
            st.markdown("##### Task Archive History")
            for _, task in filtered_completed.iterrows():
                with st.container():
                    c_c1, c_c2 = st.columns([3, 1])
                    with c_c1:
                        st.markdown(f"**{task['Title']}** &bull; Completed On: `{task['CompletedDate']}`")
                        st.caption(f"Assigned to: {task['AssignedTo']} &bull; Submitted: {task['SubmittedDate']} &bull; Target: {task['TargetDate']}")
                        if str(task['Description']).strip() and str(task['Description']) != 'nan':
                            st.caption(task['Description'])
                    with c_c2:
                        st.write("")
                        if st.button("Re-open Task", key=f"reopen_{task['TaskID']}", width="stretch", disabled=not (is_officer and can_edit), help=None if (is_officer and can_edit) else ("Officer editing mode is disabled. Toggle 'Enable Editing Mode' in the sidebar." if is_officer else "Officer access required to re-open tasks")):
                            if set_todo_status(task['TaskID'], "Pending", is_officer=is_officer):
                                st.success("Task re-opened and moved to active list.")
                                st.rerun()
                    st.divider()
