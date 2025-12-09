import streamlit as st
import json
import pandas as pd
from datetime import datetime
from utils.helpers import generate_new_meal_plan
from utils.ui import show_meal_details
from utils.feedback_agent import FeedbackAgent
from utils.db import get_snowpark_session

def render_meal_plan(conn, user_id):
    """Enhanced meal plan viewer"""
    st.header("🍽️ My Weekly Meal Plan")

    from utils.db import get_meal_plan_overview, get_daily_meals_for_plan, get_weekly_meal_details, get_future_meal_plan
    
    # Check for future plan
    future_plan = get_future_meal_plan(conn, user_id)
    view_plan_id = None
    
    if future_plan:
        if st.session_state.get('viewing_future_plan'):
            st.success(f"📅 Viewing Future Plan (Starts {future_plan['start_date'].strftime('%B %d')})")
            if st.button("⬅️ Back to Current Plan"):
                st.session_state['viewing_future_plan'] = False
                st.rerun()
            view_plan_id = future_plan['plan_id']
        else:
            st.info(f"🚀 Your next meal plan (starting {future_plan['start_date'].strftime('%B %d')}) is ready!")
            if st.button("👀 View Next Week's Plan"):
                st.session_state['viewing_future_plan'] = True
                st.rerun()
    
    active_plan = get_meal_plan_overview(conn, user_id, specific_plan_id=view_plan_id)

    if not active_plan:
        # No plan - offer to generate
        st.info("📅 You don't have a meal plan yet!")

        if st.button("🎉 Generate My First Meal Plan", type="primary", use_container_width=True):
            generate_new_meal_plan(conn, user_id)
        return

    # Display active plan
    plan_id = active_plan['plan_id']
    plan_name = active_plan['plan_name']
    start_date = active_plan['start_date']
    end_date = active_plan['end_date']
    week_summary = json.loads(active_plan['week_summary']) if active_plan['week_summary'] else {}

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
            
        if st.button("🔄 Refresh"):
            get_meal_plan_overview.clear()
            get_daily_meals_for_plan.clear()
            get_weekly_meal_details.clear()
            st.rerun()

    # Get daily meals first to calculate dynamic averages
    daily_meals = get_daily_meals_for_plan(conn, plan_id)
    
    # Calculate dynamic averages from current daily data
    current_stats = {
        "calories": 0, "protein": 0, "carbohydrates": 0, "fat": 0, "fiber": 0
    }
    days_count = len(daily_meals) if daily_meals else 1
    
    if daily_meals:
        for day in daily_meals:
            if day.get('total_nutrition'):
                try:
                    nut = json.loads(day['total_nutrition'])
                    current_stats["calories"] += nut.get('calories', 0)
                    current_stats["protein"] += nut.get('protein_g', 0)
                    current_stats["carbohydrates"] += nut.get('carbohydrates_g', 0)
                    current_stats["fat"] += nut.get('fat_g', 0)
                    current_stats["fiber"] += nut.get('fiber_g', 0)
                except:
                    pass
        
        # Calculate averages
        for k in current_stats:
            current_stats[k] = current_stats[k] / days_count

    # Get user profile for targets
    from utils.db import get_user_profile
    user_profile = get_user_profile(conn, user_id)
    
    # Week overview
    st.markdown("### 📊 Week Overview (Avg / Target)")
    metrics_cols = st.columns(5)
    
    metrics_cols[0].metric("Calories", f"{current_stats['calories']:.0f} / {user_profile.get('daily_calories', 2000)}")
    metrics_cols[1].metric("Protein", f"{current_stats['protein']:.0f}g / {user_profile.get('daily_protein', 0):.0f}g")
    metrics_cols[2].metric("Carbs", f"{current_stats['carbohydrates']:.0f}g / {user_profile.get('daily_carbohydrate', 0):.0f}g")
    metrics_cols[3].metric("Fat", f"{current_stats['fat']:.0f}g / {user_profile.get('daily_fat', 0):.0f}g")
    metrics_cols[4].metric("Fiber", f"{current_stats['fiber']:.0f}g / {user_profile.get('daily_fiber', 0):.0f}g")

    if daily_meals:
        # Create tabs for each day
        day_tabs = st.tabs([f"{m['day_name'][:3]} {m['meal_date'].strftime('%d')}" for m in daily_meals])
        
        # Get all meal details once
        all_weekly_details = get_weekly_meal_details(conn, plan_id)

        for i, tab in enumerate(day_tabs):
            with tab:
                selected_meal = daily_meals[i]
                meal_id = selected_meal['meal_id']

                st.markdown(f"### 🍽️ {selected_meal['day_name']} - {selected_meal['meal_date'].strftime('%B %d, %Y')}")

                # Day nutrition
                if selected_meal['total_nutrition']:
                    day_nutrition = json.loads(selected_meal['total_nutrition'])

                    col1, col2 = st.columns([3, 1])
                    with col1:
                        # Progress bars
                        calories_pct = (day_nutrition.get('calories', 0) / 2000) * 100
                        st.progress(min(calories_pct / 100, 1.0),
                                    text=f"Calories: {day_nutrition.get('calories', 0):.0f} kcal")

                        protein_pct = (day_nutrition.get('protein_g', 0) / 130) * 100
                        st.progress(min(protein_pct / 100, 1.0),
                                    text=f"Protein: {day_nutrition.get('protein_g', 0):.0f}g")
                                    
                        fat_pct = (day_nutrition.get('fat_g', 0) / 70) * 100
                        st.progress(min(fat_pct / 100, 1.0),
                                    text=f"Fat: {day_nutrition.get('fat_g', 0):.0f}g")
                                    
                        fiber_pct = (day_nutrition.get('fiber_g', 0) / 30) * 100
                        st.progress(min(fiber_pct / 100, 1.0),
                                    text=f"Fiber: {day_nutrition.get('fiber_g', 0):.0f}g")

                    with col2:
                        if selected_meal['inventory_impact']:
                            impact = json.loads(selected_meal['inventory_impact'])
                            st.metric("From Inventory", impact.get('items_used', 0))

                # Filter details for this day
                target_day_number = selected_meal['day_number']
                meal_details = [m for m in all_weekly_details if m['day_number'] == target_day_number]

                if meal_details:
                    # Prepare data for table
                    table_data = []
                    meal_map = {}
                    
                    for meal in meal_details:
                        # Parse nutrition for display
                        calories = 0
                        protein = 0
                        fat = 0
                        fiber = 0
                        if meal['nutrition']:
                            nut = json.loads(meal['nutrition'])
                            calories = nut.get('calories', 0)
                            protein = nut.get('protein_g', 0)
                            fat = nut.get('fat_g', 0)
                            fiber = nut.get('fiber_g', 0)

                        row = {
                            "Type": meal['meal_type'].title(),
                            "Meal Name": meal['meal_name'],
                            "Calories": f"{calories:.0f}",
                            "Protein (g)": f"{protein:.1f}",
                            "Fat (g)": f"{fat:.1f}",
                            "Fiber (g)": f"{fiber:.1f}"
                        }
                        table_data.append(row)
                        
                        # Store full data for dialog
                        meal_key = f"{meal['meal_type']}_{meal['meal_name']}"
                        meal_map[meal_key] = {
                            "meal_name": meal['meal_name'],
                            "ingredients_with_quantities": meal['ingredients_with_quantities'],
                            "recipe": meal['recipe'],
                            "nutrition": meal['nutrition'],
                            "preparation_time": meal['preparation_time'],
                            "cooking_time": meal['cooking_time'],
                            "servings": meal['servings'],
                            "serving_size": meal['serving_size'],
                            "difficulty_level": meal['difficulty_level']
                        }

                    # Display interactive table
                    st.subheader("📅 Daily Schedule")
                    df = pd.DataFrame(table_data)
                    
                    # Configure column config
                    column_config = {
                        "Type": st.column_config.TextColumn("Type", width="small"),
                        "Meal Name": st.column_config.TextColumn("Meal Name", width="large"),
                        "Calories": st.column_config.NumberColumn("Calories", format="%s kcal"),
                        "Protein (g)": st.column_config.NumberColumn("Protein", format="%s g"),
                        "Fat (g)": st.column_config.NumberColumn("Fat", format="%s g"),
                        "Fiber (g)": st.column_config.NumberColumn("Fiber", format="%s g"),
                    }

                    event = st.dataframe(
                        df,
                        column_config=column_config,
                        use_container_width=True,
                        hide_index=True,
                        on_select="rerun",
                        selection_mode="single-row",
                        key=f"df_{meal_id}" # Unique key per tab
                    )

                    # Handle selection
                    if event.selection.rows:
                        selected_index = event.selection.rows[0]
                        selected_row = df.iloc[selected_index]
                        meal_key = f"{selected_row['Type'].lower()}_{selected_row['Meal Name']}"
                        
                        if meal_key in meal_map:
                            show_meal_details(meal_map[meal_key])
                    
                    # Meal Feedback Section
                    st.divider()
                    st.subheader("💭 Rate Your Meals")
                    st.caption("Help us learn your preferences by rating each meal")
                    
                    # Initialize feedback agent
                    session = get_snowpark_session()
                    feedback_agent = FeedbackAgent(conn, session)
                    
                    # Display feedback buttons for each meal
                    for idx, meal in enumerate(meal_details):
                        meal_type = meal['meal_type']
                        meal_name = meal['meal_name']
                        
                        col1, col2, col3, col4 = st.columns([0.4, 0.3, 0.1, 0.1])
                        
                        with col1:
                            st.markdown(f"**{meal_type.title()}:** {meal_name}")
                        
                        with col2:
                            # Parse nutrition for calories display
                            if meal['nutrition']:
                                nut = json.loads(meal['nutrition'])
                                st.caption(f"{nut.get('calories', 0):.0f} kcal")
                        
                        with col3:
                            if st.button("👍", key=f"like_meal_{meal_id}_{idx}", help="I like this meal"):
                                # Save feedback for the meal with ingredients in context
                                ingredients_list = []
                                if meal['ingredients_with_quantities']:  # ingredients_with_quantities
                                    ingredients = json.loads(meal['ingredients_with_quantities']) if isinstance(meal['ingredients_with_quantities'], str) else meal['ingredients_with_quantities']
                                    ingredients_list = [ing.get('ingredient', '') for ing in ingredients[:5]]
                                
                                # Use shorter entity_id - just meal type + index
                                feedback_agent.save_explicit_feedback(
                                    user_id=user_id,
                                    entity_id=f"{meal_type}_{idx}",
                                    entity_name=meal_name,
                                    entity_type="meal",
                                    feedback="like"
                                )
                                st.success("✓ Saved!", icon="👍")
                        
                        with col4:
                            if st.button("👎", key=f"dislike_meal_{meal_id}_{idx}", help="I don't like this meal"):
                                # Save feedback for the meal with ingredients in context
                                ingredients_list = []
                                if meal['ingredients_with_quantities']:
                                    ingredients = json.loads(meal['ingredients_with_quantities']) if isinstance(meal['ingredients_with_quantities'], str) else meal['ingredients_with_quantities']
                                    ingredients_list = [ing.get('ingredient', '') for ing in ingredients[:5]]
                                
                                # Use shorter entity_id - just meal type + index
                                feedback_agent.save_explicit_feedback(
                                    user_id=user_id,
                                    entity_id=f"{meal_type}_{idx}",
                                    entity_name=meal_name,
                                    entity_type="meal",
                                    feedback="dislike"
                                )
                                st.warning("✓ Noted", icon="👎")


