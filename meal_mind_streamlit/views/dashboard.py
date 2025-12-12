import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from utils.api import get_bmi_category

def get_weekly_nutrition_history(conn, user_id, num_weeks=4):
    """Fetch nutrition data for the past N weeks"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                mp.start_date,
                mp.end_date,
                dm.meal_date,
                dm.total_nutrition
            FROM daily_meals dm
            JOIN meal_plans mp ON dm.plan_id = mp.plan_id
            WHERE dm.user_id = %s
            AND dm.meal_date >= DATEADD(week, -%s, CURRENT_DATE())
            ORDER BY dm.meal_date DESC
        """, (user_id, num_weeks))
        
        rows = cursor.fetchall()
        data = []
        for row in rows:
            nutrition = row[3]
            if isinstance(nutrition, str):
                try:
                    nutrition = json.loads(nutrition)
                except:
                    nutrition = {}
            elif nutrition is None:
                nutrition = {}
            
            data.append({
                'date': row[2],
                'calories': nutrition.get('calories', 0),
                'protein': nutrition.get('protein_g', 0),
                'carbs': nutrition.get('carbohydrates_g', 0),
                'fat': nutrition.get('fat_g', 0),
                'fiber': nutrition.get('fiber_g', 0)
            })
        
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()
    finally:
        cursor.close()

def get_weekly_averages(conn, user_id):
    """Get average nutrition per week for comparison"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                DATE_TRUNC('week', dm.meal_date) as week_start,
                AVG(PARSE_JSON(dm.total_nutrition):calories::FLOAT) as avg_calories,
                AVG(PARSE_JSON(dm.total_nutrition):protein_g::FLOAT) as avg_protein,
                AVG(PARSE_JSON(dm.total_nutrition):carbohydrates_g::FLOAT) as avg_carbs,
                AVG(PARSE_JSON(dm.total_nutrition):fat_g::FLOAT) as avg_fat,
                AVG(PARSE_JSON(dm.total_nutrition):fiber_g::FLOAT) as avg_fiber
            FROM daily_meals dm
            JOIN meal_plans mp ON dm.plan_id = mp.plan_id
            WHERE dm.user_id = %s
            AND dm.meal_date >= DATEADD(week, -4, CURRENT_DATE())
            GROUP BY DATE_TRUNC('week', dm.meal_date)
            ORDER BY week_start DESC
            LIMIT 4
        """, (user_id,))
        
        rows = cursor.fetchall()
        data = []
        for row in rows:
            data.append({
                'week': row[0].strftime('%b %d') if row[0] else 'Unknown',
                'calories': float(row[1] or 0),
                'protein': float(row[2] or 0),
                'carbs': float(row[3] or 0),
                'fat': float(row[4] or 0),
                'fiber': float(row[5] or 0)
            })
        
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()
    finally:
        cursor.close()

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
        
        # Analytics Section
        st.divider()
        st.subheader("📈 Nutrition Analytics")
        
        # Fetch weekly averages
        weekly_df = get_weekly_averages(conn, user_id)
        daily_df = get_weekly_nutrition_history(conn, user_id)
        
        if not weekly_df.empty:
            # Charts side by side
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                st.markdown("##### Weekly Calorie Trends")
                chart_data = weekly_df[['week', 'calories']].copy()
                chart_data = chart_data.iloc[::-1]  # Reverse to show oldest first
                st.bar_chart(
                    chart_data.set_index('week')['calories'],
                    use_container_width=True,
                    color="#4CAF50"
                )
            
            with chart_col2:
                st.markdown("##### Macronutrient Comparison")
                macro_data = weekly_df[['week', 'protein', 'carbs', 'fat']].copy()
                macro_data = macro_data.iloc[::-1]  # Reverse
                macro_data = macro_data.set_index('week')
                st.bar_chart(macro_data, use_container_width=True)
            
            # Weekly Stats Comparison
            st.markdown("##### Week-over-Week Comparison")
            
            if len(weekly_df) >= 2:
                current_week = weekly_df.iloc[0]
                prev_week = weekly_df.iloc[1]
                
                comp_cols = st.columns(5)
                
                # Calculate deltas
                cal_delta = current_week['calories'] - prev_week['calories']
                prot_delta = current_week['protein'] - prev_week['protein']
                carb_delta = current_week['carbs'] - prev_week['carbs']
                fat_delta = current_week['fat'] - prev_week['fat']
                fiber_delta = current_week['fiber'] - prev_week['fiber']
                
                comp_cols[0].metric(
                    "Avg Calories", 
                    f"{current_week['calories']:.0f}",
                    delta=f"{cal_delta:+.0f}"
                )
                comp_cols[1].metric(
                    "Avg Protein", 
                    f"{current_week['protein']:.1f}g",
                    delta=f"{prot_delta:+.1f}g"
                )
                comp_cols[2].metric(
                    "Avg Carbs", 
                    f"{current_week['carbs']:.1f}g",
                    delta=f"{carb_delta:+.1f}g"
                )
                comp_cols[3].metric(
                    "Avg Fat", 
                    f"{current_week['fat']:.1f}g",
                    delta=f"{fat_delta:+.1f}g"
                )
                comp_cols[4].metric(
                    "Avg Fiber", 
                    f"{current_week['fiber']:.1f}g",
                    delta=f"{fiber_delta:+.1f}g"
                )
            else:
                st.info("Need at least 2 weeks of data for comparison")
        
        # Daily Trend Line Chart
        if not daily_df.empty:
            st.markdown("##### Daily Calorie Trend (Last 4 Weeks)")
            
            daily_chart = daily_df[['date', 'calories']].copy()
            daily_chart = daily_chart.sort_values('date')
            daily_chart = daily_chart.set_index('date')
            
            st.line_chart(daily_chart, use_container_width=True, color="#FF6B6B")
            
            # Target line reference
            st.caption(f"🎯 Your daily target: {profile['daily_calories']} kcal")
        
        if weekly_df.empty and daily_df.empty:
            st.info("📊 No nutrition history yet. Generate a meal plan to start tracking!")
            
    else:
        st.error("Profile not found.")
