"""
Merch Tracking module for the UCSB Ski Team Dashboard.
Manages inventory for T-Shirts (40 S, 100 M, 70 L, 40 XL) and Sweatshirts (10 S, 28 M, 14 L, 8 XL).
Reflects membership form claims dynamically and supports independent sales, giveaways, and restocks.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from utils.data_manager import (
    get_merch_inventory_summary, load_merch_adjustments,
    add_merch_adjustment, delete_merch_adjustment, load_officers
)
from config import VALID_SIZES, CURRENT_SEASON, THEME_COLORS


def render_merch_tab(selected_season: str = CURRENT_SEASON, is_officer: bool = False, can_edit: bool = None):
    if can_edit is None:
        can_edit = is_officer

    st.markdown(f"## Merch Inventory and Distribution Tracker ({selected_season})")
    st.markdown("Track team t-shirt collections and sweatshirt distributions in real time, connecting membership claims with independent gear sales.")

    summary = get_merch_inventory_summary(season=selected_season if selected_season != "All Seasons" else None, is_officer=is_officer)
    shirts_df = summary["shirts_df"]
    sweatshirts_df = summary["sweatshirts_df"]

    # --- TOP METRICS ROW ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(
            label="T-Shirts Remaining",
            value=f"{summary['total_shirts_avail']} / {summary['total_shirts_init']}",
            delta=f"{summary['total_shirts_claimed']} claimed via dues"
        )
    with c2:
        st.metric(
            label="Sweatshirts Remaining",
            value=f"{summary['total_hoodies_avail']} / {summary['total_hoodies_init']}",
            delta=f"{summary['total_hoodies_init'] - summary['total_hoodies_avail']} distributed"
        )
    with c3:
        st.metric(
            label="T-Shirt Inventory Pool",
            value="250 Total",
            delta="40 S • 100 M • 70 L • 40 XL"
        )
    with c4:
        st.metric(
            label="Sweatshirt Inventory Pool",
            value="60 Total",
            delta="10 S • 28 M • 14 L • 8 XL"
        )

    st.divider()

    # --- INDEPENDENT MERCH LOGGER FORM ---
    with st.expander("Record Independent Sale / Gear Distribution / Restock", expanded=False):
        if not is_officer:
            st.info("Officer access required to record merch adjustments. Enter the officer password in the sidebar to unlock.")
        elif not can_edit:
            st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to record merch adjustments.")
        else:
            st.markdown("*Use this form to log extra sales, officer gear, alumni purchases, or restocks independently from the membership tracker.*")
            with st.form("independent_merch_form", clear_on_submit=True):
                f1, f2, f3 = st.columns(3)
                with f1:
                    item_type = st.selectbox("Merch Item", ["T-Shirt", "Sweatshirt"])
                    size = st.selectbox("Size", VALID_SIZES, index=1)

                with f2:
                    action_type = st.radio("Action", ["Sold / Handed Out (Deduct Stock)", "Restock / Return (Add Stock)"], horizontal=False)
                    qty = st.number_input("Quantity", min_value=1, max_value=100, value=1, step=1)

                with f3:
                    reason = st.text_input("Recipient / Reason", placeholder="e.g. Sold to alumnus at meeting, extra driver hoodie")
                    officer_pool = load_officers(is_officer=is_officer)
                    logged_by = st.selectbox("Logged By Officer", officer_pool)

                target_merch_season = selected_season if selected_season != "All Seasons" else CURRENT_SEASON
                submit_adj = st.form_submit_button("Record Merch Transaction", use_container_width=True)

                if submit_adj:
                    signed_qty = -int(qty) if "Deduct" in action_type else int(qty)
                    success = add_merch_adjustment(
                        item_type=item_type,
                        size=size,
                        quantity=signed_qty,
                        reason=reason if reason.strip() else f"{item_type} {size} {action_type.split()[0]}",
                        logged_by=logged_by,
                        season=target_merch_season,
                        is_officer=is_officer
                    )
                    if success:
                        st.success(f"Recorded {abs(signed_qty)} {item_type} ({size}) transaction.")
                        st.rerun()
                    else:
                        st.error("Failed to record adjustment. Please try again.")

    # --- INVENTORY BREAKDOWNS (T-SHIRTS & SWEATSHIRTS) ---
    col_tshirt, col_hoodie = st.columns(2)

    with col_tshirt:
        st.subheader("T-Shirt Inventory (by Size)")
        st.caption("Auto-deducts sizes chosen in the Membership Tracker and applies independent adjustments.")
        
        # Display table
        st.dataframe(shirts_df, width="stretch", hide_index=True)

        # Bar chart showing remaining stock vs claimed
        fig_shirts = px.bar(
            shirts_df,
            x="Size",
            y=["Remaining Available", "Claimed via Membership"],
            barmode="stack",
            color_discrete_map={
                "Remaining Available": THEME_COLORS["periwinkle"],
                "Claimed via Membership": THEME_COLORS["slate_blue"]
            },
            title="T-Shirt Stock by Size"
        )
        fig_shirts.update_layout(
            margin=dict(l=10, r=10, t=35, b=10),
            plot_bgcolor=THEME_COLORS["surface_bg"],
            paper_bgcolor=THEME_COLORS["surface_bg"],
            font=dict(color="#f0f4f8"),
            xaxis=dict(gridcolor="#283552"),
            yaxis=dict(gridcolor="#283552"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_shirts, use_container_width=True)

    with col_hoodie:
        st.subheader("Sweatshirt Inventory (by Size)")
        st.caption("Tracks hoodies (10 S, 28 M, 14 L, 8 XL) sold or distributed independently.")
        
        st.dataframe(sweatshirts_df, width="stretch", hide_index=True)

        fig_hoodies = px.bar(
            sweatshirts_df,
            x="Size",
            y=["Remaining Available", "Distributed / Sales"],
            barmode="stack",
            color_discrete_map={
                "Remaining Available": "#4a72b8",
                "Distributed / Sales": THEME_COLORS["slate_blue"]
            },
            title="Sweatshirt Stock by Size"
        )
        fig_hoodies.update_layout(
            margin=dict(l=10, r=10, t=35, b=10),
            plot_bgcolor=THEME_COLORS["surface_bg"],
            paper_bgcolor=THEME_COLORS["surface_bg"],
            font=dict(color="#f0f4f8"),
            xaxis=dict(gridcolor="#283552"),
            yaxis=dict(gridcolor="#283552"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_hoodies, use_container_width=True)

    st.divider()

    # --- INDEPENDENT MERCH TRANSACTIONS LOG ---
    st.subheader("Independent Gear Transactions Log")
    adjustments_df = load_merch_adjustments(season=selected_season if selected_season != "All Seasons" else None, is_officer=is_officer)

    if adjustments_df.empty:
        st.info("No independent merch transactions recorded yet for this season.")
    else:
        c_tbl, c_del = st.columns([3.5, 1.5])
        with c_tbl:
            disp_adj = adjustments_df[["Date", "ItemType", "Size", "Quantity", "Reason", "LoggedBy"]].copy()
            disp_adj.columns = ["Date", "Item", "Size", "Qty Change", "Reason / Recipient", "Logged By"]
            st.dataframe(disp_adj, width="stretch", hide_index=True)

        with c_del:
            with st.popover("Delete an Adjustment Entry"):
                if not is_officer:
                    st.info("Officer access required to delete merch records. Enter the officer password in the sidebar to unlock.")
                elif not can_edit:
                    st.info("Officer editing mode is currently disabled. Toggle 'Enable Editing Mode' in the sidebar to delete merch records.")
                else:
                    st.markdown("**Remove Entry**")
                    adj_opts = {f"{r['AdjustmentID']}: {r['ItemType']} {r['Size']} ({r['Quantity']}) - {r['LoggedBy']}": r["AdjustmentID"] for _, r in adjustments_df.iterrows()}
                    chosen_adj = st.selectbox("Select Record", list(adj_opts.keys()))
                    if st.button("Confirm Delete", type="primary"):
                        del_id = adj_opts[chosen_adj]
                        if delete_merch_adjustment(del_id, is_officer=is_officer):
                            st.success("Entry removed and inventory recalculated.")
                            st.rerun()
                        else:
                            st.error("Could not delete record.")
