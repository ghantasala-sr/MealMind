import streamlit as st
from utils.api import get_bmi_category

def render_dashboard(conn, user_id):
    st.header("📊 Nutrition Dashboard")

    # Get user profile
    cursor = conn.cursor()
    cursor.execute("""
                   SELECT age,
                          gender,
                          height_cm,
                          weight_kg,
                          bmi,
                          activity_level,
                          health_goal,
                          dietary_restrictions,
                          food_allergies,
                          daily_calories,
                          daily_protein,
                          daily_carbohydrate,
                          daily_fat,
                          daily_fiber,
                          updated_at
                   FROM users
                   WHERE user_id = %s
                   """, (user_id,))
    profile = cursor.fetchone()
    cursor.close()

    if profile:
        st.subheader("Your Nutrition Stats")

        # Stats
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("BMI", f"{profile[4]:.1f}")
        category, emoji = get_bmi_category(profile[4])
        col2.metric("Category", f"{emoji} {category}")
        col3.metric("Activity", profile[5])
        col4.metric("Goal", profile[6])

        # Daily targets
        st.subheader("📋 Daily Targets")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Calories", f"{profile[9]} kcal")
        c2.metric("Protein", f"{profile[10]:.1f} g")
        c3.metric("Carbs", f"{profile[11]:.1f} g")
        c4.metric("Fat", f"{profile[12]:.1f} g")
        c5.metric("Fiber", f"{profile[13]:.1f} g")
    else:
        st.error("Profile not found.")
