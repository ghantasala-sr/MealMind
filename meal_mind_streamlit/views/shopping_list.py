import streamlit as st
import json

def render_shopping_list(conn, user_id):
    """View shopping list for active plan"""
    st.header("🛒 Shopping List")
    
    from utils.db import get_meal_plan_history
    
    # History Selection
    col_hist1, col_hist2 = st.columns([0.7, 0.3])
    selected_plan_id = None
    
    with col_hist2:
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
                key="sl_history_selector"
            )
    
    cursor = conn.cursor()
    
    if selected_plan_id:
        # Fetch specific plan
        cursor.execute("""
                       SELECT s.shopping_data, p.plan_name
                       FROM shopping_lists s
                       JOIN meal_plans p ON s.plan_id = p.plan_id
                       WHERE s.user_id = %s AND p.plan_id = %s
                       ORDER BY s.created_at DESC LIMIT 1
                       """, (user_id, selected_plan_id))
    else:
        # Default to active
        cursor.execute("""
                       SELECT s.shopping_data, p.plan_name
                       FROM shopping_lists s
                       JOIN meal_plans p ON s.plan_id = p.plan_id
                       WHERE s.user_id = %s AND p.status = 'ACTIVE'
                       ORDER BY s.created_at DESC LIMIT 1
                       """, (user_id,))
                       
    result = cursor.fetchone()
    cursor.close()

    if not result:
        st.info("No active shopping list found. Generate a meal plan first!")
        return

    shopping_data = json.loads(result[0])
    plan_name = result[1]
    
    st.caption(f"For: {plan_name}")

    if not shopping_data:
        st.success("🎉 Nothing to buy! You have everything in stock.")
        return

    # Display by category
    categories = {
        "Proteins": shopping_data.get('proteins', []),
        "Grains": shopping_data.get('grains', []),
        "Vegetables": shopping_data.get('vegetables', []),
        "Fruits": shopping_data.get('fruits', []),
        "Dairy/Alt": shopping_data.get('dairy_alternatives', []),
        "Pantry": shopping_data.get('pantry_items', [])
    }

    for cat, items in categories.items():
        if items:
            st.subheader(cat)
            for item in items:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{item['item']}**")
                with col2:
                    st.write(f"{item['quantity_to_purchase']} {item['unit']}")
            st.divider()
