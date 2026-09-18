"""
Trip Planning and Historical Budget Estimator module for the UCSB Ski Team Dashboard.
Models trip costs from UCSB (driving distance, cabin rental, food/alcohol, lift tickets),
learns from past trip receipts, and calculates break-even per-skier pricing.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from utils.data_manager import load_trips, add_trip, get_cost_benchmarks
from config import DESTINATIONS, DEFAULT_MPG, DEFAULT_GAS_PRICE, DEFAULT_SEATS_PER_CAR, THEME_COLORS


def render_trip_planner_tab():
    st.markdown("## Trip Planning and Budget Estimator")
    st.markdown("Calculate accurate trip budgets from **UCSB**, forecast per-skier costs, and leverage historical cost data from previous trips.")

    benchmarks = get_cost_benchmarks()
    trips_df = load_trips()

    # --- HISTORICAL LEARNING BENCHMARKS BANNER ---
    with st.container():
        st.markdown("#### Historical Cost Intelligence (Learned from Past Trips)")
        b1, b2, b3, b4 = st.columns(4)

        b1.metric(
            label="Avg Cabin Cost / Night",
            value=f"${benchmarks.get('avg_cabin_per_night', 950):,.0f}",
            help="Average nightly cabin booking cost across historical trips."
        )

        b2.metric(
            label="Cabin Cost / Person-Night",
            value=f"${benchmarks.get('avg_cabin_per_person_night', 35):,.2f}",
            help="Average lodging cost per attendee per night."
        )

        b3.metric(
            label="Food & Drinks / Person-Day",
            value=f"${benchmarks.get('avg_food_per_person_day', 18.50):,.2f}",
            help="Learned from team Costco, Albertsons, and provisions receipts."
        )

        b4.metric(
            label="Fuel Cost / Car-Mile",
            value=f"${benchmarks.get('avg_gas_per_car_mile', 0.24):,.2f}",
            delta=f"Based on ~{DEFAULT_MPG} MPG and ${DEFAULT_GAS_PRICE}/gal in CA"
        )

    st.divider()

    # --- INTERACTIVE TRIP BUILDER ---
    st.markdown("### Build and Budget a Trip")
    col_inputs, col_results = st.columns([1.2, 1.8])

    with col_inputs:
        st.markdown("##### 1. Destination and Itinerary")
        dest_choice = st.selectbox("Destination from UCSB", list(DESTINATIONS.keys()), index=0)
        dest_info = DESTINATIONS[dest_choice]

        trip_name = st.text_input("Trip Name", value=f"{dest_choice} Weekend 2026")

        c_dates1, c_dates2 = st.columns(2)
        with c_dates1:
            start_date = st.date_input("Start Date", value=date.today() + timedelta(days=30))
        with c_dates2:
            default_n = dest_info["default_nights"]
            nights = st.number_input("Duration (Nights)", min_value=1, max_value=14, value=default_n, step=1)
        end_date = start_date + timedelta(days=int(nights))

        # Driving Distance
        default_rt = dest_info["round_trip_miles"]
        round_trip_miles = st.number_input(
            "Round-Trip Distance from UCSB (Miles)",
            min_value=10, max_value=3000, value=default_rt, step=10,
            help="Includes drive from UCSB/Isla Vista to resort and back."
        )

        st.markdown("##### 2. Attendance and Carpooling")
        c_att1, c_att2 = st.columns(2)
        with c_att1:
            expected_skiers = st.slider("Total Expected Skiers", min_value=4, max_value=60, value=24, step=1)
        with c_att2:
            suggested_cars = max(1, int(np.ceil(expected_skiers / DEFAULT_SEATS_PER_CAR)))
            carpools = st.number_input("Number of Vehicles", min_value=1, max_value=15, value=suggested_cars, step=1)

        passholder_pct = st.slider(
            "Passholders (Ikon / Epic with $0 lift tickets)",
            min_value=0, max_value=100, value=85, step=5,
            help="Percentage of attendees who have a season pass and do not need lift tickets."
        )
        passholders_count = int(round(expected_skiers * (passholder_pct / 100)))
        non_passholders_count = expected_skiers - passholders_count

        st.markdown("##### 3. Expense Estimates")
        suggested_cabin = round(nights * benchmarks.get("avg_cabin_per_night", 950), 2)
        cabin_cost = st.number_input(
            "Total Cabin / Lodging Rental ($)",
            min_value=0.0, max_value=30000.0, value=float(suggested_cabin), step=50.0,
            help=f"Historical benchmark suggestion: ~${suggested_cabin:,.0f} for {nights} nights."
        )

        suggested_food = round(expected_skiers * nights * benchmarks.get("avg_food_per_person_day", 18.50), 2)
        food_alcohol_cost = st.number_input(
            "Food & Drinks Total ($)",
            min_value=0.0, max_value=10000.0, value=float(suggested_food), step=25.0,
            help=f"Historical benchmark suggestion: ~${suggested_food:,.0f} based on team grocery history."
        )

        lift_ticket_price_per_skier = st.number_input(
            "Lift Ticket Price per Non-Passholder ($)",
            min_value=0.0, max_value=500.0, value=120.0, step=10.0,
            help="Only non-passholders pay this; passholders have $0 ticket cost."
        )

        gas_price = st.number_input("Estimated Gas Price ($/gal)", min_value=2.0, max_value=10.0, value=DEFAULT_GAS_PRICE, step=0.05)
        mpg = st.number_input("Average Vehicle MPG", min_value=10.0, max_value=50.0, value=DEFAULT_MPG, step=1.0)

        # Subsidy
        st.markdown("##### 4. Club Treasury Contribution")
        club_subsidy_per_skier = st.number_input("Club Subsidy per Skier ($)", min_value=0.0, max_value=200.0, value=0.0, step=5.0)

    # --- COST CALCULATIONS ---
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

    # --- DISPLAY BUDGET RESULTS ---
    with col_results:
        st.markdown("#### Projected Trip Budget and Break-Even Pricing")

        p1, p2, p3 = st.columns(3)
        p1.metric(
            label="Passholder Price",
            value=f"${break_even_passholder:,.0f}",
            help="Break-even ticket price for skiers with Ikon/Epic passes."
        )
        p2.metric(
            label="Non-Pass Price",
            value=f"${break_even_non_passholder:,.0f}",
            help=f"Includes ${lift_ticket_price_per_skier:,.0f} lift ticket."
        )
        p3.metric(
            label="Total Budget Outflow",
            value=f"${total_gross_cost:,.2f}",
            delta=f"Club covers ${total_club_subsidy:,.0f}" if total_club_subsidy > 0 else "Self-funding",
            delta_color="inverse" if total_club_subsidy > 0 else "normal"
        )

        # Itemized Budget Breakdown Table
        breakdown_data = [
            {"Item": "Cabin Rental", "Basis": f"{nights} nights", "Total Cost ($)": cabin_cost, "Per Person ($)": cabin_cost / expected_skiers},
            {"Item": "Food & Drinks", "Basis": f"Team groceries ({nights} days)", "Total Cost ($)": food_alcohol_cost, "Per Person ($)": food_alcohol_cost / expected_skiers},
            {"Item": "Driving Gas from UCSB", "Basis": f"{round_trip_miles} mi RT x {carpools} cars @ ${gas_price}/gal", "Total Cost ($)": total_gas_cost, "Per Person ($)": total_gas_cost / expected_skiers},
            {"Item": "Lift Tickets (Non-Pass)", "Basis": f"{non_passholders_count} skiers @ ${lift_ticket_price_per_skier:.0f}", "Total Cost ($)": total_lift_tickets_cost, "Per Person ($)": total_lift_tickets_cost / expected_skiers},
        ]
        df_breakdown = pd.DataFrame(breakdown_data)

        # Cost Distribution Bar Chart
        fig_cost = px.bar(
            df_breakdown,
            x="Item",
            y="Total Cost ($)",
            color="Item",
            color_discrete_sequence=[THEME_COLORS["navy"], THEME_COLORS["gold"], THEME_COLORS["light_blue"], THEME_COLORS["coral"]],
            title="Itemized Cost Composition"
        )
        fig_cost.update_layout(
            margin=dict(l=10, r=10, t=35, b=10),
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_cost, use_container_width=True)

        # Attendance Sensitivity Curve
        st.markdown("##### Price Sensitivity vs. Skier Attendance")
        skier_range = list(range(max(6, expected_skiers - 12), expected_skiers + 13, 2))
        sens_data = []
        for n_skiers in skier_range:
            n_cars = max(1, int(np.ceil(n_skiers / DEFAULT_SEATS_PER_CAR)))
            f_cost = (round_trip_miles / mpg) * n_cars * gas_price
            base_p = (cabin_cost + f_cost) / n_skiers + (food_alcohol_cost / n_skiers)
            sens_data.append({
                "Skiers": n_skiers,
                "Passholder Price ($)": round(base_p - club_subsidy_per_skier, 2),
                "Cars Needed": n_cars
            })
        df_sens = pd.DataFrame(sens_data)

        fig_sens = px.line(
            df_sens,
            x="Skiers",
            y="Passholder Price ($)",
            markers=True,
            title="How Per-Skier Cost Drops with More Attendees"
        )
        fig_sens.add_vline(x=expected_skiers, line_dash="dash", line_color="green", annotation_text="Target")
        fig_sens.update_layout(
            margin=dict(l=10, r=10, t=35, b=10),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_sens, use_container_width=True)

        # Save Plan Button
        if st.button("Save this Trip Budget Plan", type="primary", use_container_width=True):
            success = add_trip(
                name=trip_name,
                destination=dest_choice,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                nights=nights,
                miles=round_trip_miles,
                attendees=expected_skiers,
                vehicles=carpools,
                cabin=cabin_cost,
                food=food_alcohol_cost,
                tickets=total_lift_tickets_cost,
                gas=total_gas_cost,
                status="Planning",
                notes=f"Passholder price: ${break_even_passholder:.0f}, Non-passholder: ${break_even_non_passholder:.0f}"
            )
            if success:
                st.success(f"Trip '{trip_name}' has been saved to the database. Future trip benchmarks updated.")
                st.rerun()

    # --- BOTTOM SECTION: HISTORICAL & SAVED TRIPS LOG ---
    st.divider()
    st.markdown("### Past and Upcoming Trips Log")
    if not trips_df.empty:
        display_trips = trips_df[[
            "Name", "Destination", "StartDate", "Nights", "Attendees",
            "CabinCost", "FoodAlcoholCost", "LiftTicketsCost", "GasCost", "TotalCost", "Status"
        ]].copy()
        
        display_trips.columns = [
            "Trip Name", "Destination", "Date", "Nights", "Skiers",
            "Cabin ($)", "Food/Drink ($)", "Tickets ($)", "Gas ($)", "Total Outflow ($)", "Status"
        ]
        
        for c in ["Cabin ($)", "Food/Drink ($)", "Tickets ($)", "Gas ($)", "Total Outflow ($)"]:
            display_trips[c] = display_trips[c].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "$0.00")

        st.dataframe(display_trips, width="stretch", hide_index=True)
    else:
        st.info("No past trips logged yet.")
