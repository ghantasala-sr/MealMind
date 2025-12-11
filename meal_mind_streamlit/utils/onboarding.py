import streamlit as st
from utils.api import get_nutrition_info_from_api, parse_macro_value, calculate_manual, calculate_nutrition_targets, get_bmi_category
from utils.helpers import add_inventory_item

def profile_setup_wizard(conn, user_id):
    """Multi-step wizard for profile setup"""
    st.title("🍽️ Complete Your Nutrition Profile")

    total_steps = 7
    current_step = st.session_state.get('setup_step', 1)
    progress = current_step / total_steps
    st.progress(progress)
    st.write(f"Step {current_step} of {total_steps}")

    if 'form_data' not in st.session_state:
        st.session_state.form_data = {}
    if 'inventory_items' not in st.session_state:
        st.session_state.inventory_items = []

    # STEP 1: Personal Information
    if current_step == 1:
        st.header("Step 1: Personal Information")

        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input("Age", min_value=1, max_value=120,
                                  value=st.session_state.form_data.get('age', 25))
            gender = st.selectbox("Gender", ["Male", "Female"])

        with col2:
            height = st.number_input("Height (cm)", min_value=100, max_value=250,
                                     value=st.session_state.form_data.get('height', 170))
            weight = st.number_input("Weight (kg)", min_value=30.0, max_value=300.0,
                                     value=st.session_state.form_data.get('weight', 70.0))

        if st.button("Next →", type="primary"):
            st.session_state.form_data.update({
                'age': age, 'gender': gender, 'height': height, 'weight': weight
            })
            st.session_state.setup_step = 2
            st.rerun()

    # STEP 2: Life Stage
    elif current_step == 2:
        st.header("Step 2: Life Stage")

        life_stage = st.selectbox("Life Stage",
                                  ["Adult (19-30)", "Adult (31-50)", "Adult (51-70)", "Adult (70+)"])

        if st.session_state.form_data.get('gender') == 'Female':
            pregnancy = st.selectbox("Pregnancy Status",
                                     ["Not Pregnant", "1st Trimester", "2nd Trimester", "3rd Trimester"])
            lactation = st.selectbox("Lactation Status",
                                     ["Not Lactating", "0-6 months", "7-12 months"])
        else:
            pregnancy = "Not Pregnant"
            lactation = "Not Lactating"

        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Previous"):
                st.session_state.setup_step = 1
                st.rerun()
        with col2:
            if st.button("Next →", type="primary"):
                st.session_state.form_data.update({
                    'life_stage': life_stage, 'pregnancy': pregnancy, 'lactation': lactation
                })
                st.session_state.setup_step = 3
                st.rerun()

    # STEP 3: Activity & Goals
    elif current_step == 3:
        st.header("Step 3: Activity Level & Health Goals")

        activity = st.selectbox("Activity Level",
                                ["Sedentary", "Lightly active", "Moderately active", "Very active", "Extremely active"])

        goal = st.selectbox("Primary Health Goal",
                            ["Weight Loss", "Weight Maintenance", "Muscle Gain", "Athletic Performance",
                             "General Health"])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Previous"):
                st.session_state.setup_step = 2
                st.rerun()
        with col2:
            if st.button("Next →", type="primary"):
                st.session_state.form_data.update({
                    'activity': activity, 'goal': goal
                })
                st.session_state.setup_step = 4
                st.rerun()

    # STEP 4: Dietary Preferences
    elif current_step == 4:
        st.header("Step 4: Dietary Restrictions & Allergies")

        restrictions = st.multiselect("Dietary Restrictions (optional)",
                                      ["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "Keto",
                                       "Low-Sodium", "Low-Carb", "Paleo"])

        allergies = st.multiselect("Food Allergies (optional)",
                                   ["Peanuts", "Tree Nuts", "Milk", "Eggs", "Fish",
                                    "Shellfish", "Soy", "Wheat", "Sesame"])

        cuisines = st.multiselect("Preferred Cuisines (optional)",
                                  ["Italian", "Mexican", "Indian", "Chinese", "Japanese", 
                                   "Mediterranean", "American", "Thai", "French", "Korean"])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Previous"):
                st.session_state.setup_step = 3
                st.rerun()
        with col2:
            if st.button("Calculate My DRI →", type="primary"):
                st.session_state.form_data.update({
                    'restrictions': restrictions, 'allergies': allergies, 'cuisines': cuisines
                })
                st.session_state.setup_step = 5
                st.rerun()

    # STEP 5: Calculate DRI
    elif current_step == 5:
        st.header("Step 5: Your Personalized Nutrition Plan")

        with st.spinner("Calculating your nutrition targets..."):
            data = st.session_state.form_data

            api_data = get_nutrition_info_from_api(
                data['age'], data['gender'], data['height'], data['weight'],
                data['activity'], data.get('pregnancy', 'Not Pregnant'),
                data.get('lactation', 'Not Lactating')
            )

            if api_data:
                bmi = api_data.get('BMI_EER', {}).get('BMI', '0')
                calories_str = api_data.get('BMI_EER', {}).get('Estimated Daily Caloric Needs', '2000 kcal/day')
                calories = int(calories_str.replace(',', '').split()[0])
                macro_table = api_data.get('macronutrients_table', {}).get('macronutrients-table', [])

                targets = {
                    'bmi': float(bmi),
                    'daily_calories': calories,
                    'daily_protein': parse_macro_value(macro_table, 'Protein'),
                    'daily_carbohydrate': parse_macro_value(macro_table, 'Carbohydrate'),
                    'daily_fat': parse_macro_value(macro_table, 'Fat'),
                    'daily_fiber': parse_macro_value(macro_table, 'Total Fiber')
                }
            else:
                targets = calculate_manual(
                    data['age'], data['gender'], data['weight'],
                    data['height'], data['activity'], data['goal']
                )

            st.session_state.form_data['targets'] = targets

        st.success("✅ Your nutrition targets are ready!")

        # Display results
        col1, col2 = st.columns(2)
        category, emoji = get_bmi_category(targets['bmi'])
        col1.metric("BMI", f"{targets['bmi']:.1f}")
        col2.metric("Category", f"{emoji} {category}")

        st.subheader("🎯 Daily Nutrition Targets")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Calories", f"{targets['daily_calories']} kcal")
        c2.metric("Protein", f"{targets['daily_protein']:.1f} g")
        c3.metric("Carbs", f"{targets['daily_carbohydrate']:.1f} g")
        c4.metric("Fat", f"{targets['daily_fat']:.1f} g")
        c5.metric("Fiber", f"{targets['daily_fiber']:.1f} g")

        if st.button("Next → Add Inventory", type="primary", use_container_width=True):
            st.session_state.setup_step = 6
            st.rerun()

    # STEP 6: Add Inventory
    elif current_step == 6:
        st.header("Step 6: Add Your Food Inventory (Optional)")
        st.info("Adding inventory helps create meal plans using what you have!")

        UNITS = ["g", "kg", "lbs", "oz", "ml", "L", "cups", "pieces", "dozen"]
        CATEGORIES = ["Proteins", "Grains", "Vegetables", "Fruits", "Dairy", "Pantry Items", "Other"]

        with st.expander("➕ Add Items", expanded=True):
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

            with col1:
                item_name = st.text_input("Item Name")
            with col2:
                quantity = st.number_input("Quantity", min_value=0.0, value=1.0)
            with col3:
                unit = st.selectbox("Unit", UNITS)
            with col4:
                category = st.selectbox("Category", CATEGORIES)

            if st.button("Add Item"):
                if item_name:
                    # Check for duplicate items
                    existing_names = [item['name'].lower() for item in st.session_state.inventory_items]
                    if item_name.lower() in existing_names:
                        st.session_state.duplicate_warning = item_name
                    else:
                        st.session_state.inventory_items.append({
                            'name': item_name,
                            'quantity': quantity,
                            'unit': unit,
                            'category': category
                        })
                        st.success(f"Added {item_name}")
                        st.rerun()

            # Show warning with option to add anyway
            if st.session_state.get('duplicate_warning'):
                warned_item = st.session_state.duplicate_warning
                st.warning(f"⚠️ '{warned_item}' is already in your inventory!")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("Add Anyway", type="primary"):
                        st.session_state.inventory_items.append({
                            'name': item_name,
                            'quantity': quantity,
                            'unit': unit,
                            'category': category
                        })
                        st.session_state.duplicate_warning = None
                        st.success(f"Added {warned_item}")
                        st.rerun()
                with col_no:
                    if st.button("Cancel"):
                        st.session_state.duplicate_warning = None
                        st.rerun()

        # Display items
        if st.session_state.inventory_items:
            st.subheader("Your Inventory:")
            for item in st.session_state.inventory_items:
                st.write(f"• {item['name']}: {item['quantity']} {item['unit']} ({item['category']})")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Previous"):
                st.session_state.setup_step = 5
                st.rerun()
        with col2:
            if st.button("Next → Generate Meal Plan", type="primary"):
                if len(st.session_state.inventory_items) < 10:
                    st.error(f"Please add at least 10 items to your inventory to generate a plan. (Current: {len(st.session_state.inventory_items)})")
                else:
                    st.session_state.setup_step = 7
                    st.rerun()

    # STEP 7: Generate First Meal Plan
    elif current_step == 7:
        st.header("Step 7: Generate Your First Meal Plan")

        st.write("### Your meal plan will include:")
        st.write("✅ 7 days of balanced meals")
        st.write("✅ Complete recipes with instructions")
        st.write("✅ Meals using your inventory")
        st.write("✅ Shopping list for additional items")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("← Previous"):
                st.session_state.setup_step = 6
                st.rerun()

        with col2:
            if st.button("🚀 Complete Setup & Generate Plan", type="primary"):
                with st.spinner("Setting up your profile and generating meal plan..."):
                    cursor = conn.cursor()
                    data = st.session_state.form_data
                    targets = data['targets']

                    try:
                        # Save profile
                        cursor.execute("""
                                       UPDATE users
                                       SET age                  = %s,
                                           gender               = %s,
                                           height_cm            = %s,
                                           weight_kg            = %s,
                                           bmi                  = %s,
                                           life_stage           = %s,
                                           pregnancy_status     = %s,
                                           lactation_status     = %s,
                                           activity_level       = %s,
                                           health_goal          = %s,
                                           dietary_restrictions = %s,
                                           food_allergies       = %s,
                                           preferred_cuisines   = %s,
                                           daily_calories       = %s,
                                           daily_protein        = %s,
                                           daily_carbohydrate   = %s,
                                           daily_fat            = %s,
                                           daily_fiber          = %s,
                                           profile_completed    = TRUE,
                                           updated_at           = CURRENT_TIMESTAMP()
                                       WHERE user_id = %s
                                       """, (
                                           data['age'], data['gender'], data['height'], data['weight'], targets['bmi'],
                                           data['life_stage'], data.get('pregnancy', 'Not Pregnant'),
                                           data.get('lactation', 'Not Lactating'),
                                           data['activity'], data['goal'],
                                           ', '.join(data.get('restrictions', [])) or 'None',
                                           ', '.join(data.get('allergies', [])) or 'None',
                                           ', '.join(data.get('cuisines', [])) or 'Any',
                                           targets['daily_calories'], targets['daily_protein'],
                                           targets['daily_carbohydrate'], targets['daily_fat'], targets['daily_fiber'],
                                           user_id
                                       ))

                        # Save inventory
                        for item in st.session_state.inventory_items:
                            add_inventory_item(conn, user_id, item['name'],
                                               item['quantity'], item['unit'], item['category'])

                        conn.commit()

                        # Clear setup state
                        del st.session_state['setup_step']
                        del st.session_state['form_data']
                        del st.session_state['inventory_items']
                        st.session_state.profile_completed = True

                        st.success("🎉 Setup complete!")
                        st.balloons()
                        st.rerun()

                    except Exception as e:
                        st.error(f"Error: {e}")
                    finally:
                        cursor.close()
                        