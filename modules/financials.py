"""
Financial Overview module for the UCSB Ski Team Dashboard.
Renders high-level KPIs, cash flow trends, and expense breakdowns filtered by season.
Dark theme with the two blue highlight colors.
"""

import re
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.data_manager import load_ledger, get_financial_kpis
from config import THEME_COLORS, CURRENT_SEASON


def render_financials_tab(selected_season: str = CURRENT_SEASON, is_officer: bool = False):
    st.markdown(f"## Financial Overview and Season KPIs ({selected_season})")
    st.markdown("High-level snapshot of club cash flow, operating margin, and expenditure breakdowns.")

    ledger_df = load_ledger(season=selected_season, is_officer=is_officer)
    kpis = get_financial_kpis(season=selected_season, is_officer=is_officer)

    # --- TOP ROW: KPI METRIC CARDS ---
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        net_color = "normal" if kpis["net_balance"] >= 0 else "inverse"
        st.metric(
            label="Net Treasury Balance",
            value=f"${kpis['net_balance']:,.2f}",
            delta=f"${kpis['net_balance']:,.2f} Net Operating" if kpis["net_balance"] >= 0 else "-Deficit",
            delta_color=net_color
        )

    with c2:
        st.metric(
            label="Total Season Revenue",
            value=f"${kpis['total_income']:,.2f}",
            delta=f"{len(ledger_df[ledger_df['Type'] == 'Income'])} deposits"
        )

    with c3:
        st.metric(
            label="Total Season Expenses",
            value=f"${kpis['total_expenses']:,.2f}",
            delta=f"{len(ledger_df[ledger_df['Type'] == 'Expense'])} disbursements",
            delta_color="inverse"
        )

    with c4:
        dues_pct = (kpis["dues_collected"] / kpis["total_income"] * 100) if kpis["total_income"] > 0 else 0.0
        st.metric(
            label="Member Dues Collected",
            value=f"${kpis['dues_collected']:,.2f}",
            delta=f"{dues_pct:.1f}% of total income",
            delta_color="off",
            delta_arrow="off"
        )

    st.divider()

    if ledger_df.empty:
        st.info(f"No financial transactions recorded yet for season '{selected_season}'. Use the Ledger tab to add new revenue or expense receipts.")
        return

    # --- ROW 2: MONTHLY CASH FLOW TREND & EXPENSE BREAKDOWN ---
    col_chart1, col_chart2 = st.columns([3, 2])

    with col_chart1:
        if selected_season == "All Seasons":
            st.subheader("Cash Flow Trend by Season")
            seasons_in_data = sorted([s for s in ledger_df["Season"].dropna().unique().tolist() if s != "All Seasons"])
            season_records = []
            for s in seasons_in_data:
                sdf = ledger_df[ledger_df["Season"] == s]
                inc_amt = float(sdf[sdf["Type"] == "Income"]["Amount"].sum())
                exp_amt = float(sdf[sdf["Type"] == "Expense"]["Amount"].sum())
                if inc_amt > 0 or exp_amt > 0:
                    season_records.append({"Season": s, "Type": "Income", "Amount": inc_amt})
                    season_records.append({"Season": s, "Type": "Expense", "Amount": exp_amt})

            season_summary = pd.DataFrame(season_records)
            if not season_summary.empty:
                active_seasons = sorted(list(set(season_summary["Season"].tolist())))
                fig_bar = px.bar(
                    season_summary,
                    x="Season",
                    y="Amount",
                    color="Type",
                    barmode="group",
                    color_discrete_map={"Income": THEME_COLORS["periwinkle"], "Expense": THEME_COLORS["slate_blue"]},
                    category_orders={"Season": active_seasons, "Type": ["Income", "Expense"]},
                    title="Season Inflows vs Outflows ($)",
                    labels={"Amount": "Total USD ($)", "Season": "Season", "Type": "Flow Type"}
                )
                fig_bar.update_layout(
                    margin=dict(l=20, r=20, t=40, b=20),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#f0f4f8")),
                    plot_bgcolor=THEME_COLORS["surface_bg"],
                    paper_bgcolor=THEME_COLORS["surface_bg"],
                    font=dict(color="#f0f4f8"),
                    xaxis=dict(gridcolor="#283552", type="category", categoryorder="array", categoryarray=active_seasons),
                    yaxis=dict(gridcolor="#283552")
                )
                fig_bar.update_traces(
                    hovertemplate="<b>%{x}</b><br>%{fullData.name}: $%{y:,.2f}<extra></extra>"
                )
                st.plotly_chart(fig_bar, width="stretch")
            else:
                st.info("No transaction data available for season cash flow comparison.")
        else:
            st.subheader("Monthly Cash Flow Trend")
            df_monthly = ledger_df.dropna(subset=["Date_dt"]).copy()
            df_monthly["Year"] = df_monthly["Date_dt"].dt.year
            df_monthly["Month"] = df_monthly["Date_dt"].dt.month

            # Determine season start year (e.g., '2025-2026' -> 2025)
            match = re.search(r"(\d{4})", selected_season)
            if match:
                start_year = int(match.group(1))
            else:
                valid_dates = df_monthly["Date_dt"].dropna()
                start_year = int(valid_dates.dt.year.min()) if not valid_dates.empty else 2025

            # Build 12 months in season order starting with September (Sep -> Aug)
            season_months = []
            for m in range(9, 13):
                season_months.append((start_year, m, pd.Timestamp(year=start_year, month=m, day=1).strftime("%b %Y")))
            for m in range(1, 9):
                season_months.append((start_year + 1, m, pd.Timestamp(year=start_year + 1, month=m, day=1).strftime("%b %Y")))

            # Filter only months with flows (Do not include months with no flows, max 12 months)
            active_months = []
            monthly_records = []
            for yr, mo, label in season_months:
                m_df = df_monthly[(df_monthly["Year"] == yr) & (df_monthly["Month"] == mo)]
                if not m_df.empty:
                    inc_amt = float(m_df[m_df["Type"] == "Income"]["Amount"].sum())
                    exp_amt = float(m_df[m_df["Type"] == "Expense"]["Amount"].sum())
                    if inc_amt > 0 or exp_amt > 0:
                        active_months.append(label)
                        monthly_records.append({"Month": label, "Type": "Income", "Amount": inc_amt})
                        monthly_records.append({"Month": label, "Type": "Expense", "Amount": exp_amt})

            monthly_summary = pd.DataFrame(monthly_records)

            if not monthly_summary.empty:
                fig_bar = px.bar(
                    monthly_summary,
                    x="Month",
                    y="Amount",
                    color="Type",
                    barmode="group",
                    color_discrete_map={"Income": THEME_COLORS["periwinkle"], "Expense": THEME_COLORS["slate_blue"]},
                    category_orders={"Month": active_months, "Type": ["Income", "Expense"]},
                    title=f"Monthly Inflows vs Outflows - {selected_season} ($)",
                    labels={"Amount": "Total USD ($)", "Month": "Month", "Type": "Flow Type"}
                )
                fig_bar.update_layout(
                    margin=dict(l=20, r=20, t=40, b=20),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#f0f4f8")),
                    plot_bgcolor=THEME_COLORS["surface_bg"],
                    paper_bgcolor=THEME_COLORS["surface_bg"],
                    font=dict(color="#f0f4f8"),
                    xaxis=dict(gridcolor="#283552", type="category", categoryorder="array", categoryarray=active_months),
                    yaxis=dict(gridcolor="#283552")
                )
                fig_bar.update_traces(
                    hovertemplate="<b>%{x}</b><br>%{fullData.name}: $%{y:,.2f}<extra></extra>"
                )
                st.plotly_chart(fig_bar, width="stretch")
            else:
                st.info(f"No dated transactions with cash flows recorded for season '{selected_season}'.")

    with col_chart2:
        st.subheader("Expense Breakdown by Category")
        expense_df = ledger_df[ledger_df["Type"] == "Expense"]
        if not expense_df.empty:
            cat_summary = expense_df.groupby("Category")["Amount"].sum().reset_index()
            cat_summary = cat_summary.sort_values(by="Amount", ascending=False)

            fig_donut = px.pie(
                cat_summary,
                values="Amount",
                names="Category",
                hole=0.45,
                color_discrete_sequence=[THEME_COLORS["periwinkle"], THEME_COLORS["slate_blue"], "#4a72b8", "#6c88c7", "#9bb2df"],
                title="Expense Allocations"
            )
            fig_donut.update_traces(textposition='inside', textinfo='percent+label', textfont_color="#ffffff")
            fig_donut.update_layout(
                margin=dict(l=20, r=20, t=40, b=20),
                showlegend=False,
                plot_bgcolor=THEME_COLORS["surface_bg"],
                paper_bgcolor=THEME_COLORS["surface_bg"],
                font=dict(color="#f0f4f8")
            )
            st.plotly_chart(fig_donut, width="stretch")
        else:
            st.info("No expense transactions recorded.")

    # --- ROW 3: MAJOR OUTFLOWS & INCOME CHANNELS ---
    st.divider()
    c_left, c_right = st.columns(2)

    with c_left:
        st.subheader("Trip and Housing Cost Analysis")
        trip_expenses = ledger_df[ledger_df["Category"].isin(["Housing/Rental", "Food/Drink (Trip)", "USCSA"])].copy()
        if not trip_expenses.empty:
            trip_by_cat = trip_expenses.groupby("Category")["Amount"].agg(["sum", "count"]).reset_index()
            trip_by_cat.columns = ["Category", "Total Spent ($)", "Transaction Count"]
            trip_by_cat["Total Spent ($)"] = trip_by_cat["Total Spent ($)"].apply(lambda x: f"${x:,.2f}")
            st.dataframe(trip_by_cat, width="stretch", hide_index=True)
            st.caption("Includes cabin rentals, team grocery/provisions, and USCSA race registrations.")
        else:
            st.info("No specific trip expenses logged yet.")

    with c_right:
        st.subheader("Revenue Stream Highlights")
        income_df = ledger_df[ledger_df["Type"] == "Income"].copy()
        if not income_df.empty:
            inc_by_cat = income_df.groupby("Category")["Amount"].agg(["sum", "count"]).reset_index()
            inc_by_cat.columns = ["Revenue Source", "Total Received ($)", "Deposits"]
            inc_by_cat = inc_by_cat.sort_values(by="Deposits", ascending=False)
            inc_by_cat["Total Received ($)"] = inc_by_cat["Total Received ($)"].apply(lambda x: f"${x:,.2f}")
            st.dataframe(inc_by_cat, width="stretch", hide_index=True)
            st.caption("Trip payments and membership dues make up the majority of club operating revenue.")
        else:
            st.info("No income data logged yet.")
