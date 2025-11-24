import streamlit as st
import json

def render_shopping_list(conn, user_id):
    """View shopping list for active plan"""
    st.header("🛒 Shopping List")
    
    cursor = conn.cursor()
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
