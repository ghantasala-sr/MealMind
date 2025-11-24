import streamlit as st
import json
from utils.db import get_snowpark_session
from utils.helpers import add_inventory_item, update_plan_suggestions
from utils.agent import MealPlanAgentWithExtraction

def render_suggestions(conn, user_id):
    """View suggestions for next week"""
    st.header("💡 Suggestions for Next Week")
    st.info("Items to add variety to your future meals!")

    cursor = conn.cursor()
    cursor.execute("""
                   SELECT week_summary, plan_id, plan_name
                   FROM meal_plans
                   WHERE user_id = %s AND status = 'ACTIVE'
                   ORDER BY created_at DESC LIMIT 1
                   """, (user_id,))
    result = cursor.fetchone()
    
    if not result:
        st.warning("Generate a meal plan to get suggestions!")
        cursor.close()
        return

    week_summary = json.loads(result[0])
    plan_id = result[1]
    plan_name = result[2]
    suggestions = week_summary.get('future_suggestions', [])
    
    # Generate button
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"For Plan: {plan_name}")
    with col2:
        if st.button("✨ Generate Smart Suggestions", help="Generate new suggestions based on your goals"):
            with st.spinner("Analyzing your plan and goals..."):
                # Get user profile
                cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                user_row = cursor.fetchone()
                
                user_profile = {
                    'health_goal': user_row[13], 
                    'activity_level': user_row[12],
                    'dietary_restrictions': user_row[14],
                    'food_allergies': user_row[15],
                    'preferred_cuisines': user_row[16] if len(user_row) > 16 else 'Any'
                }
                
                # Get plan summary (simplified)
                plan_summary = f"Plan: {plan_name}. Current inventory utilization: {week_summary.get('inventory_utilization_rate', 0)}%"
                
                # Call agent
                session = get_snowpark_session()
                agent = MealPlanAgentWithExtraction(session)
                new_suggestions = agent.generate_standalone_suggestions(user_profile, plan_summary)
                
                if new_suggestions:
                    if update_plan_suggestions(conn, plan_id, new_suggestions):
                        st.success("Suggestions updated!")
                        st.rerun()
                else:
                    st.error("Could not generate suggestions. Try again.")
    
    cursor.close()

    if not suggestions:
        st.info("No suggestions available yet. Click the button above to generate them!")
        return

    for i, item in enumerate(suggestions):
        with st.container():
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.write(f"**{item.get('item', 'Unknown')}**")
                st.caption(f"Reason: {item.get('reason', '')}")
            with col2:
                st.write(f"Category: {item.get('category', 'General')}")
                st.write(f"Qty: {item.get('suggested_quantity', 1)} {item.get('unit', 'unit')}")
            with col3:
                if st.button("➕ Add", key=f"sugg_{i}"):
                    if add_inventory_item(conn, user_id, item.get('item'), 
                                       item.get('suggested_quantity', 1), 
                                       item.get('unit', 'unit'), 
                                       item.get('category', 'Other')):
                        st.toast(f"Added {item.get('item')} to inventory!")
            st.divider()
