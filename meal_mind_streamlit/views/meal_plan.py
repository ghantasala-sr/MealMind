import streamlit as st
import json
import pandas as pd
from datetime import datetime
from utils.helpers import generate_new_meal_plan
from utils.ui import show_meal_details

def render_meal_plan(conn, user_id):
    """Enhanced meal plan viewer"""
    st.header("🍽️ My Weekly Meal Plan")

    cursor = conn.cursor()

    # Get active meal plan
    cursor.execute("""
                   SELECT p.plan_id,
                          p.plan_name,
                          p.start_date,
                          p.end_date,
                          p.week_summary,
                          p.created_at,
                          p.status
                   FROM meal_plans p
                   WHERE p.user_id = %s
                   ORDER BY p.created_at DESC LIMIT 1
                   """, (user_id,))

    active_plan = cursor.fetchone()

    if not active_plan:
        # No plan - offer to generate
        st.info("📅 You don't have a meal plan yet!")

        if st.button("🎉 Generate My First Meal Plan", type="primary", use_container_width=True):
            generate_new_meal_plan(conn, user_id)
        cursor.close()
        return

    # Display active plan
    plan_id = active_plan[0]
    plan_name = active_plan[1]
    start_date = active_plan[2]
    end_date = active_plan[3]
    week_summary = json.loads(active_plan[4]) if active_plan[4] else {}

    # Header
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        st.subheader(f"📋 {plan_name}")
        days_remaining = (end_date - datetime.now().date()).days
        if days_remaining > 0:
            st.caption(
                f"📅 {start_date.strftime('%B %d')} - {end_date.strftime('%B %d')} • {days_remaining} days remaining")
        else:
            st.caption(f"📅 Plan ended on {end_date.strftime('%B %d')}")

    with col2:
        if week_summary:
            utilization = week_summary.get('inventory_utilization_rate', 0)
            st.metric("Inventory Usage", f"{utilization}%")

    with col3:
        if st.button("🔄 New Plan"):
            generate_new_meal_plan(conn, user_id)

    # Week overview
    if week_summary:
        st.markdown("### 📊 Week Overview")
        metrics_cols = st.columns(5)
        metrics_cols[0].metric("Avg Calories", f"{week_summary.get('average_daily_calories', 0):.0f}")
        metrics_cols[1].metric("Avg Protein", f"{week_summary.get('average_daily_protein', 0):.0f}g")
        metrics_cols[2].metric("Avg Carbs", f"{week_summary.get('average_daily_carbs', 0):.0f}g")
        metrics_cols[3].metric("Avg Fat", f"{week_summary.get('average_daily_fat', 0):.0f}g")
        metrics_cols[4].metric("Avg Fiber", f"{week_summary.get('average_daily_fiber', 0):.0f}g")

    # Get daily meals
    cursor.execute("""
                   SELECT meal_id,
                          day_number,
                          day_name,
                          meal_date,
                          total_nutrition,
                          inventory_impact
                   FROM daily_meals
                   WHERE plan_id = %s
                   ORDER BY day_number
                   """, (plan_id,))

    daily_meals = cursor.fetchall()

    if daily_meals:
        st.markdown("### 📅 Select a Day")

        # Day selector
        day_cols = st.columns(7)
        selected_day = st.session_state.get('selected_meal_day', 0)

        for idx, meal in enumerate(daily_meals):
            with day_cols[idx % 7]:
                if st.button(
                        f"{meal[2][:3]}\n{meal[3].strftime('%d')}",
                        key=f"day_{idx}",
                        use_container_width=True,
                        type="primary" if idx == selected_day else "secondary"
                ):
                    st.session_state.selected_meal_day = idx
                    st.rerun()

        # Display selected day
        selected_meal = daily_meals[selected_day]
        meal_id = selected_meal[0]

        st.markdown(f"### 🍽️ {selected_meal[2]} - {selected_meal[3].strftime('%B %d, %Y')}")

        # Day nutrition
        if selected_meal[4]:
            day_nutrition = json.loads(selected_meal[4])

            col1, col2 = st.columns([3, 1])
            with col1:
                # Progress bars
                calories_pct = (day_nutrition.get('calories', 0) / 2000) * 100
                st.progress(min(calories_pct / 100, 1.0),
                            text=f"Calories: {day_nutrition.get('calories', 0):.0f} kcal")

                protein_pct = (day_nutrition.get('protein_g', 0) / 130) * 100
                st.progress(min(protein_pct / 100, 1.0),
                            text=f"Protein: {day_nutrition.get('protein_g', 0):.0f}g")

            with col2:
                if selected_meal[5]:
                    impact = json.loads(selected_meal[5])
                    st.metric("From Inventory", impact.get('items_used', 0))

        # Get meal details
        cursor.execute("""
                       SELECT meal_type,
                              meal_name,
                              ingredients_with_quantities,
                              recipe,
                              nutrition,
                              preparation_time,
                              cooking_time,
                              servings,
                              serving_size,
                              difficulty_level
                       FROM meal_details
                       WHERE meal_id = %s
                       ORDER BY CASE meal_type
                                    WHEN 'breakfast' THEN 1
                                    WHEN 'lunch' THEN 2
                                    WHEN 'snacks' THEN 3
                                    WHEN 'dinner' THEN 4
                                    END
                       """, (meal_id,))

        meal_details = cursor.fetchall()

        if meal_details:
            # Prepare data for table
            table_data = []
            meal_map = {}
            
            for meal in meal_details:
                # Parse nutrition for display
                calories = 0
                protein = 0
                if meal[4]:
                    nut = json.loads(meal[4])
                    calories = nut.get('calories', 0)
                    protein = nut.get('protein_g', 0)

                row = {
                    "Type": meal[0].title(),
                    "Meal Name": meal[1],
                    "Calories": f"{calories:.0f}",
                    "Protein (g)": f"{protein:.1f}",
                    "Prep Time": f"{meal[5]} min",
                    "Cook Time": f"{meal[6]} min",
                    "Level": meal[9].title()
                }
                table_data.append(row)
                
                # Store full data for dialog
                meal_key = f"{meal[0]}_{meal[1]}"
                meal_map[meal_key] = {
                    "meal_name": meal[1],
                    "ingredients_with_quantities": meal[2],
                    "recipe": meal[3],
                    "nutrition": meal[4],
                    "preparation_time": meal[5],
                    "cooking_time": meal[6],
                    "servings": meal[7],
                    "serving_size": meal[8],
                    "difficulty_level": meal[9]
                }

            # Display interactive table
            st.subheader("📅 Weekly Schedule")
            df = pd.DataFrame(table_data)
            
            # Configure column config
            column_config = {
                "Type": st.column_config.TextColumn("Type", width="small"),
                "Meal Name": st.column_config.TextColumn("Meal Name", width="large"),
                "Calories": st.column_config.NumberColumn("Calories", format="%s kcal"),
                "Protein (g)": st.column_config.NumberColumn("Protein", format="%s g"),
                "Level": st.column_config.TextColumn("Level", width="small"),
            }

            event = st.dataframe(
                df,
                column_config=column_config,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )

            # Handle selection
            if event.selection.rows:
                selected_index = event.selection.rows[0]
                selected_row = df.iloc[selected_index]
                meal_key = f"{selected_row['Type'].lower()}_{selected_row['Meal Name']}"
                
                if meal_key in meal_map:
                    show_meal_details(meal_map[meal_key])

    cursor.close()
