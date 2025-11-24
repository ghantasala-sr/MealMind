import streamlit as st
import json

def apply_custom_css():
    """Apply custom CSS styles"""
    st.markdown("""
    <style>
        .meal-card {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            color: #31333F;
        }
        .meal-card h4 {
            color: #31333F !important;
            margin: 0;
        }
        .nutrition-badge {
            display: inline-block;
            padding: 5px 10px;
            margin: 2px;
            background-color: #e9ecef;
            border-radius: 15px;
            font-size: 12px;
            color: #31333F;
        }
        .recipe-step {
            padding: 8px;
            margin: 5px 0;
            background-color: #ffffff;
            border-left: 3px solid #007bff;
            color: #31333F;
        }
        .inventory-item {
            background-color: #f0f2f5;
            padding: 10px;
            border-radius: 8px;
            margin: 5px 0;
            color: #31333F;
        }
        .progress-indicator {
            padding: 10px;
            background-color: #e7f3ff;
            border-radius: 5px;
            margin: 10px 0;
            color: #31333F;
        }
    </style>
    """, unsafe_allow_html=True)


@st.dialog("🍽️ Meal Details")
def show_meal_details(meal_data):
    """Show meal details in a dialog"""
    st.subheader(meal_data['meal_name'])
    
    # Quick stats
    stat_cols = st.columns(4)
    stat_cols[0].metric("⏱️ Prep", f"{meal_data['preparation_time']} min")
    stat_cols[1].metric("🔥 Cook", f"{meal_data['cooking_time']} min")
    stat_cols[2].metric("🍽️ Servings", meal_data['servings'])
    
    difficulty_colors = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}
    level = meal_data['difficulty_level']
    stat_cols[3].metric("Level", f"{difficulty_colors.get(level, '⚪')} {level}")

    # Nutrition
    if meal_data['nutrition']:
        nutrition = json.loads(meal_data['nutrition']) if isinstance(meal_data['nutrition'], str) else meal_data['nutrition']
        st.markdown("**Nutrition:**")
        nutrition_html = ""
        for key, value in nutrition.items():
            label = key.replace('_g', '').replace('_', ' ').title()
            nutrition_html += f"<span class='nutrition-badge'>{label}: {value:.1f}{'g' if '_g' in key else ''}</span>"
        st.markdown(nutrition_html, unsafe_allow_html=True)

    # Ingredients
    if meal_data['ingredients_with_quantities']:
        ingredients = json.loads(meal_data['ingredients_with_quantities']) if isinstance(meal_data['ingredients_with_quantities'], str) else meal_data['ingredients_with_quantities']
        st.markdown("### 📦 Ingredients")
        for ing in ingredients:
            icon = "✅" if ing.get('from_inventory', False) else "🛒"
            st.write(f"{icon} **{ing.get('quantity', '')} {ing.get('unit', '')}** {ing.get('ingredient', '')}")

    # Recipe
    if meal_data['recipe']:
        recipe = json.loads(meal_data['recipe']) if isinstance(meal_data['recipe'], str) else meal_data['recipe']
        st.markdown("### 👨‍🍳 Full Recipe")
        
        if recipe.get('equipment_needed'):
            st.markdown("**🔧 Equipment:**")
            equipment_html = ""
            for item in recipe['equipment_needed']:
                equipment_html += f"<span class='nutrition-badge'>{item}</span>"
            st.markdown(equipment_html, unsafe_allow_html=True)
            st.write("")

        if recipe.get('prep_steps'):
            st.markdown("**📋 Preparation:**")
            for i, step in enumerate(recipe['prep_steps'], 1):
                st.markdown(f"{i}. {step}")

        if recipe.get('cooking_instructions'):
            st.markdown("**🍳 Cooking:**")
            for i, step in enumerate(recipe['cooking_instructions'], 1):
                st.markdown(f"<div class='recipe-step'><b>Step {i}:</b> {step}</div>", unsafe_allow_html=True)

        if recipe.get('tips'):
            st.info("💡 **Tips:**\n" + "\n".join([f"• {tip}" for tip in recipe['tips']]))
