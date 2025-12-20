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
    
    from utils.db import get_meal_plan_overview, get_daily_meals_for_plan, get_weekly_meal_details, get_future_meal_plan, get_meal_plan_history
    
    # Check for future plan
    future_plan = get_future_meal_plan(conn, user_id)
    view_plan_id = None
    
    # Header with Select Week aligned on same row
    col_header, col_selector = st.columns([0.6, 0.4])
    
    with col_header:
        st.header("🍽️ My Weekly Meal Plan")
    
    with col_selector:
        history = get_meal_plan_history(conn, user_id)
        if history:
            # Format options for dropdown
            plan_options = {p['plan_id']: f"{p['start_date'].strftime('%b %d')} - {p['end_date'].strftime('%b %d')}" for p in history}
            
            # Find current active plan to set as default
            active_plan_id = next((p['plan_id'] for p in history if p['status'] == 'ACTIVE'), None)
            
            selected_plan_id = st.selectbox(
                "📅 Select Week",
                options=list(plan_options.keys()),
                format_func=lambda x: plan_options[x],
                index=list(plan_options.keys()).index(active_plan_id) if active_plan_id in plan_options else 0,
                key="history_selector"
            )
            
            if selected_plan_id:
                view_plan_id = selected_plan_id

    # Future plan viewing disabled
    
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
    week_summary = active_plan['week_summary'] if active_plan['week_summary'] else {}

    # Date range caption
    days_remaining = (end_date - datetime.now().date()).days
    if days_remaining > 0:
        st.caption(f"📅 {start_date.strftime('%B %d')} - {end_date.strftime('%B %d')} • {days_remaining} days remaining")
    else:
        st.caption(f"📅 Plan ended on {end_date.strftime('%B %d')}")
    
    # Refresh button aligned to the right
    col_spacer, col_refresh = st.columns([4, 1])
    with col_refresh:
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
                        # Helper function to determine color
                        def get_progress_color(actual, target):
                            if target == 0:
                                return "#3b82f6"  # blue
                            ratio = actual / target
                            if ratio > 1.0:
                                return "#f97316"  # orange - above target
                            elif ratio >= 0.95:
                                return "#22c55e"  # green - within ±5%
                            else:
                                return "#3b82f6"  # blue - below target
                        
                        # Get targets from user profile
                        cal_target = user_profile.get('daily_calories', 2000)
                        prot_target = user_profile.get('daily_protein', 130)
                        fat_target = user_profile.get('daily_fat', 70)
                        fiber_target = user_profile.get('daily_fiber', 30)
                        
                        # Calories
                        cal_actual = day_nutrition.get('calories', 0)
                        cal_pct = min((cal_actual / cal_target) * 100 if cal_target else 0, 100)
                        cal_color = get_progress_color(cal_actual, cal_target)
                        st.markdown(f"""
                            <div style="margin-bottom: 10px;">
                                <div style="font-size: 14px; margin-bottom: 4px;">Calories: {cal_actual:.0f} / {cal_target} kcal</div>
                                <div style="background: #374151; border-radius: 4px; height: 8px;">
                                    <div style="background: {cal_color}; width: {cal_pct}%; height: 100%; border-radius: 4px;"></div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        # Protein
                        prot_actual = day_nutrition.get('protein_g', 0)
                        prot_pct = min((prot_actual / prot_target) * 100 if prot_target else 0, 100)
                        prot_color = get_progress_color(prot_actual, prot_target)
                        st.markdown(f"""
                            <div style="margin-bottom: 10px;">
                                <div style="font-size: 14px; margin-bottom: 4px;">Protein: {prot_actual:.0f}g / {prot_target:.0f}g</div>
                                <div style="background: #374151; border-radius: 4px; height: 8px;">
                                    <div style="background: {prot_color}; width: {prot_pct}%; height: 100%; border-radius: 4px;"></div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        # Fat
                        fat_actual = day_nutrition.get('fat_g', 0)
                        fat_pct = min((fat_actual / fat_target) * 100 if fat_target else 0, 100)
                        fat_color = get_progress_color(fat_actual, fat_target)
                        st.markdown(f"""
                            <div style="margin-bottom: 10px;">
                                <div style="font-size: 14px; margin-bottom: 4px;">Fat: {fat_actual:.0f}g / {fat_target:.0f}g</div>
                                <div style="background: #374151; border-radius: 4px; height: 8px;">
                                    <div style="background: {fat_color}; width: {fat_pct}%; height: 100%; border-radius: 4px;"></div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        # Fiber
                        fiber_actual = day_nutrition.get('fiber_g', 0)
                        fiber_pct = min((fiber_actual / fiber_target) * 100 if fiber_target else 0, 100)
                        fiber_color = get_progress_color(fiber_actual, fiber_target)
                        st.markdown(f"""
                            <div style="margin-bottom: 10px;">
                                <div style="font-size: 14px; margin-bottom: 4px;">Fiber: {fiber_actual:.0f}g / {fiber_target:.0f}g</div>
                                <div style="background: #374151; border-radius: 4px; height: 8px;">
                                    <div style="background: {fiber_color}; width: {fiber_pct}%; height: 100%; border-radius: 4px;"></div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)

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
                            calories = float(nut.get('calories') or 0)
                            protein = float(nut.get('protein_g') or 0)
                            fat = float(nut.get('fat_g') or 0)
                            fiber = float(nut.get('fiber_g') or 0)

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

                    # Display selectable table
                    st.subheader("🍴 Today's Meals")
                    st.caption("👆 Click a row to view the recipe")
                    df = pd.DataFrame(table_data)
                    
                    event = st.dataframe(
                        df,
                        column_config={
                            "Type": st.column_config.TextColumn("Type", width="small"),
                            "Meal Name": st.column_config.TextColumn("Meal Name", width="large"),
                            "Calories": st.column_config.TextColumn("Calories"),
                            "Protein (g)": st.column_config.TextColumn("Protein"),
                            "Fat (g)": st.column_config.TextColumn("Fat"),
                            "Fiber (g)": st.column_config.TextColumn("Fiber"),
                        },
                        use_container_width=True,
                        hide_index=True,
                        on_select="rerun",
                        selection_mode="single-row",
                        key=f"meals_table_{meal_id}"
                    )
                    
                    # Show recipe when row is selected
                    if event.selection.rows:
                        selected_index = event.selection.rows[0]
                        selected_row = df.iloc[selected_index]
                        meal_type = selected_row['Type'].lower()
                        meal_key = f"{meal_type}_{selected_row['Meal Name']}"
                        
                        if meal_key in meal_map:
                            meal_info = meal_map[meal_key]
                            
                            st.markdown("---")
                            st.markdown(f"### 📖 Recipe: {selected_row['Meal Name']}")
                            
                            # Prep and cook time
                            time_col1, time_col2, time_col3 = st.columns(3)
                            with time_col1:
                                st.metric("⏱️ Prep Time", f"{meal_info.get('preparation_time', 0)} min")
                            with time_col2:
                                st.metric("🍳 Cook Time", f"{meal_info.get('cooking_time', 0)} min")
                            with time_col3:
                                st.metric("🍽️ Servings", meal_info.get('servings', 1))
                            
                            # Ingredients
                            st.markdown("**🥗 Ingredients**")
                            ingredients = meal_info.get('ingredients_with_quantities', [])
                            if isinstance(ingredients, str):
                                ingredients = json.loads(ingredients)
                            if ingredients:
                                ing_cols = st.columns(2)
                                for idx, ing in enumerate(ingredients):
                                    qty = ing.get('quantity', '')
                                    unit = ing.get('unit', '')
                                    name = ing.get('ingredient', '')
                                    with ing_cols[idx % 2]:
                                        st.markdown(f"• {qty} {unit} {name}")
                            
                            # Recipe steps
                            recipe = meal_info.get('recipe', {})
                            if isinstance(recipe, str):
                                recipe = json.loads(recipe)
                            
                            if recipe:
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    # Prep steps
                                    prep_steps = recipe.get('prep_steps', [])
                                    if prep_steps:
                                        st.markdown("**📝 Preparation**")
                                        for i, step in enumerate(prep_steps, 1):
                                            st.markdown(f"{i}. {step}")
                                
                                with col2:
                                    # Cooking instructions
                                    cooking = recipe.get('cooking_instructions', [])
                                    if cooking:
                                        st.markdown("**👨‍🍳 Cooking Instructions**")
                                        for i, step in enumerate(cooking, 1):
                                            st.markdown(f"{i}. {step}")
                                
                                # Tips
                                tips = recipe.get('tips', [])
                                if tips:
                                    st.markdown("**💡 Tips**")
                                    for tip in tips:
                                        st.info(tip)
                    
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


