import streamlit as st
from utils.api import get_nutrition_info_from_api, parse_macro_value, calculate_manual, calculate_nutrition_targets, get_bmi_category
from utils.helpers import add_inventory_item, generate_comprehensive_meal_plan_prompt, save_meal_plan
from utils.agent import MealPlanAgentWithExtraction, MealPlanState
from utils.db import get_snowpark_session
import pandas as pd
import uuid
import random
from datetime import datetime, timedelta

def profile_setup_wizard(conn, user_id):
    """Multi-step wizard for profile setup"""
    st.title("🍽️ Complete Your Nutrition Profile")

    # Total steps is now fixed at 6 for everyone
    total_steps = 6
    current_step = st.session_state.get('setup_step', 1)
    display_step = current_step

    progress = display_step / total_steps
    st.progress(progress)
    st.write(f"Step {display_step} of {total_steps}")

    if 'form_data' not in st.session_state:
        st.session_state.form_data = {}
    if 'inventory_items' not in st.session_state:
        st.session_state.inventory_items = []

    # STEP 1: Personal Information
    if current_step == 1:
        st.header(f"Step {display_step}: Personal Information")

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
            # Calculate Life Stage automatically
            if age <= 30:
                life_stage = "Adult (19-30)"
            elif age <= 50:
                life_stage = "Adult (31-50)"
            elif age <= 70:
                life_stage = "Adult (51-70)"
            else:
                life_stage = "Adult (70+)"

            st.session_state.form_data.update({
                'age': age, 'gender': gender, 'height': height, 'weight': weight,
                'life_stage': life_stage,
                # Default pregnancy/lactation to No for everyone (backend requirement)
                'pregnancy': "Not Pregnant",
                'lactation': "Not Lactating"
            })
            
            # Jump straight to Activity (Step 2)
            st.session_state.setup_step = 2
            st.rerun()



    # STEP 2: Activity & Goals
    elif current_step == 2:
        st.header(f"Step {display_step}: Activity Level & Health Goals")

        activity = st.selectbox("Activity Level",
                                ["Sedentary", "Lightly active", "Moderately active", "Very active", "Extremely active"])

        goal = st.selectbox("Primary Health Goal",
                            ["Weight Loss", "Weight Maintenance", "Muscle Gain", "Athletic Performance",
                             "General Health"])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Previous"):
                st.session_state.setup_step = 1
                st.rerun()
        with col2:
            if st.button("Next →", type="primary"):
                st.session_state.form_data.update({
                    'activity': activity, 'goal': goal
                })
                st.session_state.setup_step = 3
                st.rerun()

    # STEP 3: Dietary Preferences
    elif current_step == 3:
        st.header(f"Step {display_step}: Dietary Restrictions & Allergies")

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
                st.session_state.setup_step = 2
                st.rerun()
        with col2:
            if st.button("Calculate My DRI →", type="primary"):
                st.session_state.form_data.update({
                    'restrictions': restrictions, 'allergies': allergies, 'cuisines': cuisines
                })
                st.session_state.setup_step = 4
                st.rerun()

    # STEP 4: Calculate DRI
    elif current_step == 4:
        st.header(f"Step {display_step}: Your Personalized Nutrition Plan")

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
            st.session_state.setup_step = 5
            st.rerun()

    # STEP 5: Add Inventory
    elif current_step == 5:
        st.header(f"Step {display_step}: Add Your Food Inventory (Optional)")
        st.info("Adding inventory helps create meal plans using what you have!")

        UNITS = sorted(["g", "kg", "lbs", "oz", "ml", "L", "cups", "pieces", "dozen", "pack", "can", "jar", "slice", "gallon", "carton", "bottle", "bag", "box", "bunch", "pinch", "tbsp", "tsp", "loaf", "stick", "bar", "container"])
        CATEGORIES = ["Produce", "Dairy & Eggs", "Meat & Seafood", "Pantry", "Frozen", "Beverages", "Snacks", "Spices & Seasonings", "Other"]

        tab1, tab2 = st.tabs(["📝 Manual Entry", "📋 Bulk Paste (AI)"])

        # --- TAB 1: MANUAL ENTRY ---
        with tab1:
            with st.expander("➕ Add Single Item", expanded=True):
                col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
                with col1:
                    item_name = st.text_input("Item Name", key="manual_name")
                with col2:
                    quantity = st.number_input("Quantity", min_value=0.0, value=1.0, key="manual_qty")
                with col3:
                    unit = st.selectbox("Unit", UNITS, key="manual_unit")
                with col4:
                    category = st.selectbox("Category", CATEGORIES, key="manual_cat")

                if st.button("Add Item", key="add_manual"):
                    if item_name:
                        st.session_state.inventory_items.append({
                            'name': item_name,
                            'quantity': quantity,
                            'unit': unit,
                            'category': category
                        })
                        st.success(f"Added {item_name}")
                        st.rerun()

        # --- TAB 2: BULK PASTE ---
        with tab2:
            st.write("Paste your grocery list below (e.g., 'milk, 2 eggs, bread'). AI will organize it for you!")
            bulk_text = st.text_area("Inventory List", height=150, placeholder="Example:\n- 1 gallon milk\n- 2 lbs chicken breast\n- 5 apples\n- Rice")
            
            if st.button("✨ Analyze Inventory"):
                if bulk_text:
                    with st.spinner("AI is parsing your list..."):
                        try:
                            # Initialize Agent
                            from snowflake.snowpark import Session
                            import os
                            
                            # Try to get existing session or create new
                            connection_params = {
                                "account": os.getenv("SNOWFLAKE_ACCOUNT"),
                                "user": os.getenv("SNOWFLAKE_USER"),
                                "password": os.getenv("SNOWFLAKE_PASSWORD"),
                                "role": os.getenv("SNOWFLAKE_ROLE"),
                                "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
                                "database": os.getenv("SNOWFLAKE_DATABASE"),
                                "schema": os.getenv("SNOWFLAKE_SCHEMA"),
                            }
                            # Filter None values
                            connection_params = {k: v for k, v in connection_params.items() if v}
                            
                            session = Session.builder.configs(connection_params).create()
                            
                            from utils.inventory_agent import InventoryAgent
                            agent = InventoryAgent(session)
                            parsed_items = agent.parse_inventory(bulk_text)
                            
                            st.session_state['parsed_inventory_cache'] = parsed_items
                            session.close()
                            
                        except Exception as e:
                            st.error(f"AI Parsing failed: {e}")

            # Display Editable Table if data exists
            if 'parsed_inventory_cache' in st.session_state and st.session_state['parsed_inventory_cache']:
                st.subheader("Review & Edit")
                
                edited_df = st.data_editor(
                    st.session_state['parsed_inventory_cache'],
                    num_rows="dynamic",
                    column_config={
                        "Category": st.column_config.SelectboxColumn(
                            "Category",
                            help="Select the category",
                            width="medium",
                            options=CATEGORIES,
                            required=True,
                        ),
                        "Unit": st.column_config.SelectboxColumn(
                            "Unit",
                            options=UNITS,
                            required=True
                        )
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                if st.button("✅ Confirm & Add All"):
                    count = 0
                    for item in edited_df:
                        # item is a dict from the data_editor (list of dicts)
                        st.session_state.inventory_items.append({
                            'name': item['Item'],
                            'quantity': float(item['Quantity']),
                            'unit': item['Unit'],
                            'category': item['Category']
                        })
                        count += 1
                    
                    st.success(f"Successfully added {count} items!")
                    del st.session_state['parsed_inventory_cache'] # Clear cache
                    st.rerun()


        # Display items (Shared View)
        if st.session_state.inventory_items:
            st.divider()
            st.subheader(f"Your Inventory ({len(st.session_state.inventory_items)} items):")
            
            # Show as an editable dataframe to allow deletion/modification
            # Show as an editable dataframe to allow deletion/modification
            df_inv = pd.DataFrame(st.session_state.inventory_items)
            
            edited_final_df = st.data_editor(
                df_inv,
                num_rows="dynamic", # Allows adding and deleting rows
                column_config={
                    "category": st.column_config.SelectboxColumn(
                        "Category",
                        options=CATEGORIES,
                        required=True,
                    ),
                    "unit": st.column_config.SelectboxColumn(
                        "Unit",
                        options=UNITS,
                        required=True
                    )
                },
                use_container_width=True,
                hide_index=True,
                key="final_inventory_editor"
            )
            
            # Sync changes back to session state
            # This runs on every interaction with the data_editor
            if not edited_final_df.equals(df_inv):
                st.session_state.inventory_items = edited_final_df.to_dict('records')
                st.rerun()
            
            if st.button("Clear All Items", type="secondary"):
                st.session_state.inventory_items = []
                st.rerun()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Previous"):
                st.session_state.setup_step = 4
                st.rerun()
        with col2:
            if st.button("Next → Generate Meal Plan", type="primary"):
                if len(st.session_state.inventory_items) < 10:
                    st.error(f"Please add at least 10 items to your inventory to generate a plan. (Current: {len(st.session_state.inventory_items)})")
                else:
                    st.session_state.setup_step = 6
                    st.rerun()

    # STEP 6: Generate First Meal Plan
    elif current_step == 6:
        st.header(f"Step {display_step}: Generate Your First Meal Plan")

        st.write("### Your meal plan will include:")
        st.write("✅ 7 days of balanced meals")
        st.write("✅ Complete recipes with instructions")
        st.write("✅ Meals using your inventory")
        st.write("✅ Shopping list for additional items")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("← Previous"):
                st.session_state.setup_step = 5
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

                        # --- GENERATE MEAL PLAN ---
                        # Interactive Loading State
                        tips = [
                            "Did you know? Meal planning can reduce food waste by up to 30%!",
                            "Chef's Tip: Roasting vegetables brings out their natural sweetness.",
                            "Nutrition Fact: Protein helps keep you full longer than carbohydrates.",
                            "Pro Tip: Batch cooking grains on Sunday saves time all week.",
                            "Fun Fact: Avocados have more potassium than bananas!",
                            "Chef's Secret: A squeeze of lemon can brighten up almost any dish.",
                            "Hydration Hack: Eating water-rich foods like cucumber counts towards your intake!"
                        ]
                        random_tip = random.choice(tips)
                        
                        st.info(f"💡 **While you wait:** {random_tip}")

                        with st.status("🍳 **Chef is firing up the kitchen...**", expanded=True) as status:
                            
                            # 1. Prepare User Profile
                            status.write("📝 Analyzing your nutrition profile...")
                            user_profile = {
                                'user_id': user_id,
                                'age': data['age'],
                                'gender': data['gender'],
                                'height_cm': data['height'],
                                'weight_kg': data['weight'],
                                'bmi': targets['bmi'],
                                'activity_level': data['activity'],
                                'health_goal': data['goal'],
                                'dietary_restrictions': ', '.join(data.get('restrictions', [])) or 'None',
                                'food_allergies': ', '.join(data.get('allergies', [])) or 'None',
                                'preferred_cuisines': ', '.join(data.get('cuisines', [])) or 'Any',
                                'daily_calories': targets['daily_calories'],
                                'daily_protein': targets['daily_protein'],
                                'daily_carbohydrate': targets['daily_carbohydrate'],
                                'daily_fat': targets['daily_fat'],
                                'daily_fiber': targets['daily_fiber']
                            }

                            # 2. Prepare Inventory
                            status.write("📦 Checking your pantry inventory...")
                            if st.session_state.inventory_items:
                                inventory_df = pd.DataFrame(st.session_state.inventory_items)
                                # Ensure columns match what helper expects (item_name, quantity, unit, category)
                                if 'name' in inventory_df.columns:
                                    inventory_df = inventory_df.rename(columns={'name': 'item_name'})
                            else:
                                inventory_df = pd.DataFrame(columns=['item_name', 'quantity', 'unit', 'category'])

                            # 3. Generate Prompt
                            status.write("🧠 Crafting the perfect prompt for our AI Chef...")
                            prompt = generate_comprehensive_meal_plan_prompt(user_profile, inventory_df)

                            # 4. Initialize Agent
                            session = get_snowpark_session()
                            agent = MealPlanAgentWithExtraction(session)
                            
                            # 5. Build & Invoke Workflow
                            status.write("🤖 **AI Chef is cooking up your plan... (This is the magic part!)**")
                            initial_state = MealPlanState(
                                user_profile=user_profile,
                                inventory_df=inventory_df,
                                prompt=prompt,
                                meal_plan_json=None,
                                suggestions_json=None,
                                error=None
                            )
                            
                            workflow = agent.build_graph()
                            final_state = workflow.invoke(initial_state)
                            
                            meal_plan_data = final_state.get('meal_plan_json')
                            suggestions = final_state.get('suggestions_json')

                            if meal_plan_data:
                                status.write("💾 Saving your personalized menu...")
                                # Merge suggestions
                                if suggestions:
                                    meal_plan_data['future_suggestions'] = suggestions

                                # 6. Create Schedule
                                schedule_id = str(uuid.uuid4())
                                tomorrow = datetime.now().date() + timedelta(days=1)
                                plan_end = tomorrow + timedelta(days=7)

                                # Deactivate old schedules
                                cursor.execute("UPDATE planning_schedule SET status = 'INACTIVE' WHERE user_id = %s", (user_id,))

                                cursor.execute("""
                                               INSERT INTO planning_schedule (schedule_id, user_id, plan_start_date,
                                                                              plan_end_date, next_plan_date, status)
                                               VALUES (%s, %s, %s, %s, %s, 'ACTIVE')
                                               """, (schedule_id, user_id, tomorrow, plan_end, tomorrow + timedelta(days=5)))

                                # 7. Save Plan
                                plan_id = save_meal_plan(conn, user_id, schedule_id, meal_plan_data)
                                
                                if plan_id:
                                    conn.commit()
                                    status.update(label="✅ **Dinner is served! (Plan Generated)**", state="complete", expanded=False)
                                    st.success("✅ Meal Plan Generated Successfully!")
                                else:
                                    status.update(label="❌ **Something went wrong saving the plan.**", state="error")
                                    st.error("Failed to save meal plan.")
                            else:
                                status.update(label="❌ **The Chef burned the meal (Generation Failed).**", state="error")
                                st.error("Failed to generate meal plan. You can try generating one from the dashboard later.")

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
