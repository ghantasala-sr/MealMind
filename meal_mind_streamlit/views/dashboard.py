import streamlit as st
from utils.api import get_bmi_category

def render_dashboard(conn, user_id):
    st.header("📊 Nutrition Dashboard")

    from utils.db import get_dashboard_stats
    profile = get_dashboard_stats(conn, user_id)

    if profile:
        st.subheader("Your Nutrition Stats")

        # Stats
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("BMI", f"{profile['bmi']:.1f}")
        category, emoji = get_bmi_category(profile['bmi'])
        col2.metric("Category", f"{emoji} {category}")
        col3.metric("Activity", profile['activity_level'])
        col4.metric("Goal", profile['health_goal'])

        # Daily targets
        st.subheader("📋 Daily Targets")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Calories", f"{profile['daily_calories']} kcal")
        c2.metric("Protein", f"{profile['daily_protein']:.1f} g")
        c3.metric("Carbs", f"{profile['daily_carbohydrate']:.1f} g")
        c4.metric("Fat", f"{profile['daily_fat']:.1f} g")
        c5.metric("Fiber", f"{profile['daily_fiber']:.1f} g")
    else:
        st.error("Profile not found.")
