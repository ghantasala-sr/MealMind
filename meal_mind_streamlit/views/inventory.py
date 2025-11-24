import streamlit as st
from utils.helpers import get_inventory_items, add_inventory_item, delete_inventory_item

def render_inventory(conn, user_id):
    st.header("🏪 My Inventory")

    # Add item form
    with st.expander("➕ Add New Item"):
        col1, col2, col3 = st.columns(3)
        with col1:
            item_name = st.text_input("Item Name")
            quantity = st.number_input("Quantity", min_value=0.0, value=1.0)
        with col2:
            unit = st.selectbox("Unit", ["g", "kg", "lbs", "oz", "ml", "L", "cups", "pieces"])
            category = st.selectbox("Category",
                                    ["Proteins", "Grains", "Vegetables", "Fruits", "Dairy", "Other"])
        with col3:
            st.write("")
            st.write("")
            if st.button("Add Item", type="primary"):
                if item_name:
                    if add_inventory_item(conn, user_id, item_name, quantity, unit, category):
                        st.success(f"Added {item_name}")
                        st.rerun()

    # Display inventory
    inventory_df = get_inventory_items(conn, user_id)

    if not inventory_df.empty:
        st.info(f"📦 Total Items: {len(inventory_df)}")

        for category in inventory_df['category'].unique():
            if category:
                with st.expander(
                        f"{category} ({len(inventory_df[inventory_df['category'] == category])} items)"):
                    items = inventory_df[inventory_df['category'] == category]
                    for _, item in items.iterrows():
                        col1, col2, col3 = st.columns([4, 2, 1])
                        with col1:
                            st.write(f"**{item['item_name']}**")
                        with col2:
                            st.write(f"{item['quantity']} {item['unit']}")
                        with col3:
                            if st.button("🗑️", key=f"del_{item['inventory_id']}"):
                                if delete_inventory_item(conn, item['inventory_id']):
                                    st.rerun()
    else:
        st.info("Your inventory is empty. Add items above!")
