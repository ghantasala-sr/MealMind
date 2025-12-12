import streamlit as st
import json

def apply_custom_css():
    """Apply custom CSS styles with a premium, modern aesthetic"""
    st.markdown("""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    
    <style>
        :root {
            /* BRAND PALETTE */
            
            /* Primary Brand: Deep Forest Green (Text & Headers) */
            --primary-color: #2D4A3E; 
            --primary-hover: #1F332B; 
            
            /* Action Color: Terracotta/Burnt Orange (Buttons/Badges) */
            --secondary-color: #E65100;
            --action-color: #D84315; 
            
            /* Backgrounds: Warm Cream/Ivory */
            --bg-color: #FFF8E7; 
            --surface-color: #FEFDF5; /* Soft Off-White */
            
            /* Typography */
            --text-primary: #2D4A3E; /* Deep Forest Green */
            --text-secondary: #4A5D53; /* Muted Green-Gray */
            --border-color: #E0DCCD;
            
            /* Accents */
            --accent-green: #558B2F; /* Leaf Green */
            --accent-red: #C62828; /* Strawberry Red */
            
            /* Shadows */
            --shadow-sm: 0 1px 2px 0 rgba(45, 74, 62, 0.05);
            --shadow-md: 0 4px 6px -1px rgba(45, 74, 62, 0.1), 0 2px 4px -1px rgba(45, 74, 62, 0.06);
            --shadow-lg: 0 10px 15px -3px rgba(45, 74, 62, 0.1), 0 4px 6px -2px rgba(45, 74, 62, 0.05);
        }
        /* Global Typography - FORCE COLOR OVERRIDES */
        html, body, [class*="css"], .stMarkdown, .stText, p, .stTextInput, .stButton {
            font-family: 'Outfit', sans-serif !important;
            color: var(--text-primary) !important;
        }
        /* Headers */
        h1, h2, h3, h4, h5, h6, .stHeading {
            font-family: 'Outfit', sans-serif !important;
            font-weight: 700;
            color: var(--text-primary) !important;
        }
        
        /* Input Labels */
        .stTextInput label, .stSelectbox label, .stNumberInput label {
            color: var(--text-secondary) !important;
            font-weight: 600;
        }
        /* Main App Background */
        .stApp {
            background-color: var(--bg-color);
            background-image: radial-gradient(#F3E5AB 1px, transparent 1px);
            background-size: 20px 20px;
        }
        
        /* Streamlit Container Adjustments */
        .block-container {
            padding-top: 3rem;
            padding-bottom: 3rem;
        }
        /* Cards & Containers */
        .stCard, .meal-card {
            background-color: var(--surface-color);
            border-radius: 12px;
            padding: 20px;
            box-shadow: var(--shadow-md);
            border: 1px solid var(--border-color);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        
        .meal-card:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }
        .meal-card h4 {
            color: var(--text-primary) !important;
            margin: 0;
        }
        /* Inventory Items */
        .inventory-item {
            background-color: var(--surface-color);
            border-left: 4px solid var(--primary-color);
            padding: 12px;
            margin: 8px 0;
            border-radius: 6px;
            box-shadow: var(--shadow-sm);
        }
        /* Badges & Tags */
        .nutrition-badge {
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            margin: 2px;
            background-color: #EEF2FF;
            color: var(--primary-color);
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 500;
            border: 1px solid #E0E7FF;
        }
        /* Standard Buttons (Secondary/Outline) - Reset to Light Style */
        .stButton > button {
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.2s;
            border: 1px solid var(--border-color);
            padding: 0.5rem 1rem;
            background-color: var(--surface-color) !important;
            color: var(--text-primary) !important;
            box-shadow: var(--shadow-sm); 
        }
        .stButton > button:hover {
            border-color: var(--action-color);
            color: var(--action-color) !important;
            background-color: #FFF3E0 !important;
            transform: translateY(-1px);
        }
        
        /* PRIMARY Action Buttons (Login, Next, Save) - FORCE ORANGE */
        div[data-testid="stButton"] button[kind="primary"],
        div[data-testid="stFormSubmitButton"] > button {
            background-color: var(--action-color) !important;
            color: white !important; 
            box-shadow: 0 4px 6px rgba(216, 67, 21, 0.2);
            font-weight: 600;
            border: none;
        }
        
        div[data-testid="stButton"] button[kind="primary"]:hover,
        div[data-testid="stFormSubmitButton"] > button:hover {
            opacity: 0.9;
            transform: translateY(-1px);
            background-color: #BF360C !important;
            color: white !important;
        }
        /* Dataframe Header Styling */
        [data-testid="stDataFrame"] thead th {
             background-color: var(--action-color) !important;
             color: white !important;
        }
        
        /* Force remove any borders from dataframe */
        [data-testid="stDataFrame"] {
            border: none !important;
            box-shadow: none !important;
        }
        
        /* Force Sidebar to be Cream */
        section[data-testid="stSidebar"] {
            background-color: var(--bg-color) !important;
        }
        
        /* Inputs */
        .stTextInput > div > div > input {
            border-radius: 8px;
            border-color: var(--border-color);
            padding: 10px;
            background-color: var(--surface-color);
            color: var(--text-primary);
        }
        .stTextInput > div > div > input:focus {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 1px var(--primary-color);
        }
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 20px;
            border-bottom: 2px solid var(--border-color);
            background-color: transparent;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            border-radius: 8px 8px 0 0;
            gap: 1px;
            padding: 0px 20px;
            font-weight: 600;
            font-family: 'Outfit', sans-serif;
            color: var(--text-secondary);
        }
        .stTabs [aria-selected="true"] {
            background-color: transparent;
            color: var(--primary-color);
            border-bottom: 4px solid var(--primary-color);
        }
        /* Recipe Steps */
        .recipe-step {
            display: flex;
            align-items: flex-start;
            padding: 12px;
            margin: 8px 0;
            background-color: var(--bg-color);
            border-radius: 8px;
            border-left: 3px solid #8B5CF6;
        }
        /* Metrics */
        [data-testid="stMetricValue"] {
            font-family: 'Outfit', sans-serif;
            color: var(--primary-color);
        }
        /* Chat Messages */
        .chat-message-user {
            background-color: var(--primary-color);
            color: white;
            padding: 12px 16px;
            border-radius: 12px 12px 0 12px;
            margin: 8px 0;
            max-width: 80%;
            margin-left: auto;
        }
        .chat-message-ai {
            background-color: white;
            border: 1px solid var(--border-color);
            padding: 12px 16px;
            border-radius: 12px 12px 12px 0;
            margin: 8px 0;
            max-width: 80%;
            margin-right: auto;
            box-shadow: var(--shadow-sm);
        }
        /* Progress Indicator */
        .progress-indicator {
            padding: 10px;
            background-color: #e7f3ff;
            border-radius: 5px;
            margin: 10px 0;
            color: var(--text-primary);
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
