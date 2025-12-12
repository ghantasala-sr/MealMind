import streamlit as st
from utils.api import calculate_nutrition_targets
from utils.feedback_agent import FeedbackAgent
from utils.db import get_snowpark_session

def render_profile(conn, user_id):
    st.header("⚙️ Update Profile")

    # Get user profile
    cursor = conn.cursor()
    cursor.execute("""
                   SELECT age,
                          gender,
                          height_cm,
                          weight_kg,
                          bmi,
                          activity_level,
                          health_goal,
                          dietary_restrictions,
                          food_allergies,
                          daily_calories,
                          daily_protein,
                          daily_carbohydrate,
                          daily_fat,
                          daily_fiber,
                          updated_at,
                          preferred_cuisines
                   FROM users
                   WHERE user_id = %s
                   """, (user_id,))
    profile = cursor.fetchone()
    cursor.close()

    if profile:
        with st.form("update_profile_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_weight = st.number_input("Weight (kg)", value=float(profile[3]), min_value=30.0, max_value=300.0)
                new_height = st.number_input("Height (cm)", value=float(profile[2]), min_value=100.0, max_value=250.0)
                new_age = st.number_input("Age", value=int(profile[0]), min_value=18, max_value=120)
            with col2:
                new_gender = st.selectbox("Gender", ["Male", "Female"], index=0 if profile[1] == "Male" else 1)
                # Helper to find index safely
                activity_options = ["Sedentary", "Lightly Active", "Moderately Active", "Very Active", "Super Active"]
                try:
                    # Try exact match first, then case-insensitive
                    if profile[5] in activity_options:
                        act_idx = activity_options.index(profile[5])
                    else:
                        act_idx = next(i for i, v in enumerate(activity_options) if v.lower() == profile[5].lower())
                except StopIteration:
                    act_idx = 0
                    
                new_activity = st.selectbox("Activity Level", activity_options, index=act_idx)

                goal_options = ["Lose Weight", "Maintain Weight", "Gain Muscle"]
                try:
                    if profile[6] in goal_options:
                        goal_idx = goal_options.index(profile[6])
                    else:
                        goal_idx = next(i for i, v in enumerate(goal_options) if v.lower() == profile[6].lower())
                except StopIteration:
                    goal_idx = 0
                    
                new_goal = st.selectbox("Health Goal", goal_options, index=goal_idx)

            # Parse existing lists
            current_restrictions = [x.strip() for x in profile[7].split(',')] if profile[7] and profile[7] != 'None' else []
            current_allergies = [x.strip() for x in profile[8].split(',')] if profile[8] and profile[8] != 'None' else []
            
            new_restrictions = st.multiselect("Dietary Restrictions", 
                                            ["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "Keto", "Paleo", "Halal", "Kosher"],
                                            default=[r for r in current_restrictions if r in ["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "Keto", "Paleo", "Halal", "Kosher"]])
            
            new_allergies = st.multiselect("Food Allergies",
                                         ["Peanuts", "Tree Nuts", "Milk", "Eggs", "Fish", "Shellfish", "Soy", "Wheat", "Sesame"],
                                         default=[a for a in current_allergies if a in ["Peanuts", "Tree Nuts", "Milk", "Eggs", "Fish", "Shellfish", "Soy", "Wheat", "Sesame"]])

            # Handle cuisines
            current_cuisines_str = profile[15] if len(profile) > 15 else None
            current_cuisines = [x.strip() for x in current_cuisines_str.split(',')] if current_cuisines_str and current_cuisines_str != 'Any' else []
            
            new_cuisines = st.multiselect("Preferred Cuisines",
                                        ["Italian", "Mexican", "Indian", "Chinese", "Japanese", 
                                         "Mediterranean", "American", "Thai", "French", "Korean"],
                                        default=[c for c in current_cuisines if c in ["Italian", "Mexican", "Indian", "Chinese", "Japanese", 
                                         "Mediterranean", "American", "Thai", "French", "Korean"]])
            
            submitted = st.form_submit_button("Update Profile")
            
            if submitted:
                # Recalculate
                targets = calculate_nutrition_targets(new_age, new_gender, new_weight, new_height, new_activity, new_goal)
                
                # Update DB
                try:
                    u_cursor = conn.cursor()
                    u_cursor.execute("""
                        UPDATE users 
                        SET age=%s, gender=%s, height_cm=%s, weight_kg=%s, bmi=%s, 
                            activity_level=%s, health_goal=%s, 
                            dietary_restrictions=%s, food_allergies=%s, preferred_cuisines=%s,
                            daily_calories=%s, daily_protein=%s, daily_carbohydrate=%s, daily_fat=%s, daily_fiber=%s,
                            updated_at=CURRENT_TIMESTAMP()
                        WHERE user_id=%s
                    """, (
                        new_age, new_gender, new_height, new_weight, targets['bmi'],
                        new_activity, new_goal,
                        ', '.join(new_restrictions) or 'None',
                        ', '.join(new_allergies) or 'None',
                        ', '.join(new_cuisines) or 'Any',
                        targets['daily_calories'], targets['daily_protein'], targets['daily_carbohydrate'], targets['daily_fat'], targets['daily_fiber'],
                        user_id
                    ))
                    conn.commit()
                    u_cursor.close()
                    st.success("Profile updated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error updating profile: {e}")
    
    # Learned Preferences Section
    st.divider()
    
    pref_col1, pref_col2 = st.columns([4, 1])
    with pref_col1:
        st.header("🧠 Learned Preferences")
        st.caption("Automatically tracked from your conversations")
    with pref_col2:
        if st.button("🔄 Refresh", key="refresh_preferences"):
            st.rerun()
    
    # Get feedback agent
    session = get_snowpark_session()
    feedback_agent = FeedbackAgent(conn, session)
    
    # Fetch user preferences
    preferences = feedback_agent.get_user_preferences(user_id)
    
    # Display in tabs
    tab1, tab2, tab3, tab4 = st.tabs(["👍 Likes", "👎 Dislikes", "🍽️ Cuisines", "🥗 Dietary"])
    
    with tab1:
        if preferences.get('likes'):
            for pref in preferences['likes']:
                col1, col2, col3 = st.columns([0.5, 0.3, 0.2])
                with col1:
                    st.markdown(f"**{pref['name'].title()}**")
                with col2:
                    confidence = int(pref.get('confidence', 0) * 100)
                    st.progress(confidence / 100, text=f"{confidence}%")
                with col3:
                    st.caption(f"×{pref.get('frequency', 1)}")
        else:
            st.info("No likes recorded yet. Chat with Meal Mind and mention foods you enjoy!")
    
    with tab2:
        if preferences.get('dislikes'):
            for pref in preferences['dislikes']:
                col1, col2, col3 = st.columns([0.5, 0.3, 0.2])
                with col1:
                    st.markdown(f"**{pref['name'].title()}**")
                with col2:
                    confidence = int(pref.get('confidence', 0) * 100)
                    st.progress(confidence / 100, text=f"{confidence}%")
                with col3:
                    st.caption(f"×{pref.get('frequency', 1)}")
        else:
            st.info("No dislikes recorded yet. Mention foods you avoid in conversations!")
    
    with tab3:
        if preferences.get('cuisines'):
            for pref in preferences['cuisines']:
                col1, col2, col3 = st.columns([0.5, 0.3, 0.2])
                with col1:
                    st.markdown(f"**{pref['name'].title()}**")
                with col2:
                    confidence = int(pref.get('confidence', 0) * 100)
                    st.progress(confidence / 100, text=f"{confidence}%")
                with col3:
                    st.caption(f"×{pref.get('frequency', 1)}")
        else:
            st.info("No cuisine preferences yet. Tell us what you want to try!")
    
    with tab4:
        if preferences.get('dietary'):
            for pref in preferences['dietary']:
                col1, col2, col3 = st.columns([0.5, 0.3, 0.2])
                with col1:
                    st.markdown(f"**{pref['name'].title()}**")
                with col2:
                    confidence = int(pref.get('confidence', 0) * 100)
                    st.progress(confidence / 100, text=f"{confidence}%")
                with col3:
                    st.caption(f"×{pref.get('frequency', 1)}")
        else:
            st.info("No dietary preferences learned yet.")
