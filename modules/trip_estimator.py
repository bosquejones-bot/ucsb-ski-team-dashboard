"""
Trip Cost Estimator module for the UCSB Ski Team Dashboard.
Standalone budgeting calculator for forecasting trip costs from UCSB,
cabin rentals, food/alcohol, lift tickets, gas, and break-even ticket pricing.
Destinations: Mammoth, Bear Valley, China Peak, Big Bear, and Palisades.
Price sensitivity curve eliminated per user specification.
Dark theme with the two blue highlight colors.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from utils.data_manager import get_cost_benchmarks
from config import DESTINATIONS, DEFAULT_MPG, DEFAULT_GAS_PRICE, DEFAULT_SEATS_PER_CAR, THEME_COLORS


def render_trip_estimator_tab(is_officer: bool = False):
    st.markdown("## Trip Cost Estimator")
    st.markdown("Interactive financial budgeting calculator for modeling upcoming ski trips departing from **UCSB**.")

    benchmarks = get_cost_benchmarks(is_officer=is_officer)
    dest_options = list(DESTINATIONS.keys())

    # --- HISTORICAL BENCHMARKS CALLOUT ---
    with st.container():
        st.markdown("#### Historical Cost Benchmarks (Derived from Previous Trips)")
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Avg Cabin Cost / Night", f"${benchmarks.get('avg_cabin_per_night', 950):,.0f}")
        b2.metric("Cabin / Person-Night", f"${benchmarks.get('avg_cabin_per_person_night', 35):,.2f}")
        b3.metric("Food & Drinks / Person-Day", f"${benchmarks.get('avg_food_per_person_day', 18.50):,.2f}")
        b4.metric("Fuel Cost / Vehicle-Mile", f"${benchmarks.get('avg_gas_per_car_mile', 0.24):,.2f}")

    st.divider()

    col_inputs, col_results = st.columns([1.2, 1.8])

    with col_inputs:
        st.markdown("##### 1. Itinerary & Destination from UCSB")
        dest_choice = st.selectbox("Destination Resort", dest_options, index=0)
        dest_meta = DESTINATIONS[dest_choice]
        st.caption(dest_meta["description"])

        c_d1, c_d2 = st.columns(2)
        with c_d1:
            default_n = dest_meta["default_nights"]
            nights = st.number_input("Trip Duration (Nights)", min_value=1, max_value=14, value=default_n, step=1)
        with c_d2:
            default_rt = dest_meta["round_trip_miles"]
            round_trip_miles = st.number_input("Round-Trip Miles from UCSB", min_value=10, max_value=3000, value=default_rt, step=10)

        st.markdown("##### 2. Attendees & Carpooling")
        c_att1, c_att2 = st.columns(2)
        with c_att1:
            expected_skiers = st.slider("Expected Skiers", min_value=4, max_value=60, value=24, step=1)
        with c_att2:
            suggested_cars = max(1, int(np.ceil(expected_skiers / DEFAULT_SEATS_PER_CAR)))
            carpools = st.number_input("Carpool Vehicles", min_value=1, max_value=15, value=suggested_cars, step=1)

        passholder_pct = st.slider(
            "Passholders ($0 Lift Ticket)",
            min_value=0, max_value=100, value=85, step=5,
            help="Percentage of attendees who have a season pass (e.g. Ikon/Epic) and do not need lift tickets."
        )
        passholders_count = int(round(expected_skiers * (passholder_pct / 100)))
        non_passholders_count = expected_skiers - passholders_count

        st.markdown("##### 3. Lodging & Provisions")
        suggested_cabin = round(nights * benchmarks.get("avg_cabin_per_night", 950), 2)
        cabin_cost = st.number_input("Cabin / Lodging Rental ($)", min_value=0.0, value=float(suggested_cabin), step=50.0)

        suggested_food = round(expected_skiers * nights * benchmarks.get("avg_food_per_person_day", 18.50), 2)
        food_alcohol_cost = st.number_input("Food & Drinks ($)", min_value=0.0, value=float(suggested_food), step=25.0)

        lift_ticket_price_per_skier = st.number_input(
            "Lift Ticket Price per Non-Passholder ($)",
            min_value=0.0, max_value=500.0, value=120.0, step=10.0,
            help="Applied only to skiers without a season pass."
        )

        st.markdown("##### 4. Travel Costs & Treasury Subsidy")
        c_tr1, c_tr2 = st.columns(2)
        with c_tr1:
            gas_price = st.number_input("Gas Price ($/gal)", min_value=2.0, max_value=10.0, value=DEFAULT_GAS_PRICE, step=0.05)
        with c_tr2:
            mpg = st.number_input("Vehicle MPG", min_value=10.0, max_value=50.0, value=DEFAULT_MPG, step=1.0)

        club_subsidy_per_skier = st.number_input("Club Subsidy per Skier ($)", min_value=0.0, max_value=200.0, value=0.0, step=5.0)

    # --- COST MATH ---
    total_fuel_gallons = (round_trip_miles / mpg) * carpools
    total_gas_cost = total_fuel_gallons * gas_price
    total_lift_tickets_cost = non_passholders_count * lift_ticket_price_per_skier

    fixed_trip_cost = cabin_cost + total_gas_cost
    shared_food_per_skier = food_alcohol_cost / max(1, expected_skiers)
    shared_base_per_skier = (fixed_trip_cost / max(1, expected_skiers)) + shared_food_per_skier

    break_even_passholder = max(0.0, shared_base_per_skier - club_subsidy_per_skier)
    break_even_non_passholder = max(0.0, shared_base_per_skier + lift_ticket_price_per_skier - club_subsidy_per_skier)

    total_gross_cost = cabin_cost + food_alcohol_cost + total_gas_cost + total_lift_tickets_cost
    total_club_subsidy = club_subsidy_per_skier * expected_skiers

    # --- RESULTS COLUMN ---
    with col_results:
        st.markdown("#### Projected Trip Budget and Break-Even Pricing")

        p1, p2, p3 = st.columns(3)
        p1.metric("Passholder Price", f"${break_even_passholder:,.0f}", help="Break-even ticket price for passholders.")
        p2.metric("Non-Passholder Price", f"${break_even_non_passholder:,.0f}", help="Includes lift ticket cost.")
        p3.metric("Total Budget Outflow", f"${total_gross_cost:,.2f}", f"Club covers ${total_club_subsidy:,.0f}" if total_club_subsidy > 0 else "Self-funding")

        # Itemized Breakdown Table
        breakdown_data = [
            {"Expense Item": "Cabin / Lodging", "Calculation Basis": f"{nights} nights", "Total ($)": cabin_cost, "Per Skier ($)": cabin_cost / expected_skiers},
            {"Expense Item": "Food & Drinks", "Calculation Basis": f"Team groceries for {nights} days", "Total ($)": food_alcohol_cost, "Per Skier ($)": food_alcohol_cost / expected_skiers},
            {"Expense Item": "Driving Fuel from UCSB", "Calculation Basis": f"{round_trip_miles} mi RT x {carpools} cars @ ${gas_price}/gal", "Total ($)": total_gas_cost, "Per Skier ($)": total_gas_cost / expected_skiers},
            {"Expense Item": "Lift Tickets (Non-Pass)", "Calculation Basis": f"{non_passholders_count} skiers @ ${lift_ticket_price_per_skier:.0f}", "Total ($)": total_lift_tickets_cost, "Per Skier ($)": total_lift_tickets_cost / expected_skiers},
        ]
        df_breakdown = pd.DataFrame(breakdown_data)

        # Plotly Cost Distribution Bar Chart (Dark theme with the two blues)
        fig_cost = px.bar(
            df_breakdown,
            x="Expense Item",
            y="Total ($)",
            color="Expense Item",
            color_discrete_sequence=[THEME_COLORS["periwinkle"], THEME_COLORS["slate_blue"], "#4a72b8", "#7084b4"],
            title="Itemized Cost Composition"
        )
        fig_cost.update_layout(
            margin=dict(l=10, r=10, t=35, b=10),
            showlegend=False,
            plot_bgcolor=THEME_COLORS["surface_bg"],
            paper_bgcolor=THEME_COLORS["surface_bg"],
            font=dict(color="#f0f4f8"),
            xaxis=dict(gridcolor="#283552"),
            yaxis=dict(gridcolor="#283552")
        )
        st.plotly_chart(fig_cost, use_container_width=True)

        st.markdown("##### Itemized Summary")
        disp_bd = df_breakdown.copy()
        disp_bd["Total ($)"] = disp_bd["Total ($)"].apply(lambda x: f"${x:,.2f}")
        disp_bd["Per Skier ($)"] = disp_bd["Per Skier ($)"].apply(lambda x: f"${x:,.2f}")
        st.dataframe(disp_bd, width="stretch", hide_index=True)
