import streamlit as st
from dotenv import load_dotenv
from utils.db import get_snowflake_connection
from utils.auth import authenticate_user, create_user_account
from utils.ui import apply_custom_css
from utils.onboarding import profile_setup_wizard

# Import views
from views.dashboard import render_dashboard
from views.meal_plan import render_meal_plan
from views.shopping_list import render_shopping_list
from views.suggestions import render_suggestions
from views.inventory import render_inventory
from views.profile import render_profile
from views.chat import render_chat

load_dotenv()

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="Meal Mind - AI Nutrition Planner",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

apply_custom_css()

def main():
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.profile_completed = False

    # Connect to database
    try:
        conn = get_snowflake_connection()
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        st.stop()

    # AUTHENTICATION FLOW
    if not st.session_state.authenticated:
        st.title("🍽️ Meal Mind - AI-Powered Nutrition Intelligence")
        st.markdown("*Your personalized meal planning assistant powered by USDA nutrition data*")

        tab1, tab2 = st.tabs(["🔑 Login", "📝 Sign Up"])

        with tab1:
            st.subheader("Welcome Back!")
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", type="primary", use_container_width=True)

                if submitted:
                    if username and password:
                        success, user_id, user, profile_completed = authenticate_user(conn, username, password)
                        if success:
                            st.session_state.authenticated = True
                            st.session_state.user_id = user_id
                            st.session_state.username = user
                            st.session_state.profile_completed = profile_completed
                            st.success("Login successful!")
                            st.rerun()
                        else:
                            st.error("Invalid credentials")
                    else:
                        st.warning("Please enter both username and password")

        with tab2:
            st.subheader("Create Your Account")
            with st.form("signup_form"):
                new_username = st.text_input("Choose Username")
                new_email = st.text_input("Email (optional)")
                new_password = st.text_input("Choose Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")

                st.info("📋 After signup, we'll guide you through profile setup and meal plan generation!")

                submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)

                if submitted:
                    if new_username and new_password:
                        if new_password != confirm_password:
                            st.error("Passwords don't match")
                        elif len(new_password) < 6:
                            st.error("Password must be at least 6 characters")
                        else:
                            success, result = create_user_account(conn, new_username, new_password, new_email)
                            if success:
                                st.session_state.authenticated = True
                                st.session_state.user_id = result
                                st.session_state.username = new_username
                                st.session_state.profile_completed = False
                                st.session_state.setup_step = 1
                                st.success("Account created!")
                                st.rerun()
                            else:
                                st.error(f"Failed: {result}")
                    else:
                        st.warning("Please fill in required fields")

    # PROFILE SETUP OR DASHBOARD
    else:
        if not st.session_state.profile_completed:
            profile_setup_wizard(conn, st.session_state.user_id)
        else:
            # Main Dashboard with Tabs
            st.title(f"🍽️ Welcome, {st.session_state.username}!")
            
            if st.button("Logout", key="logout_btn"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

            # Create tabs
            tab_dashboard, tab_meal_plan, tab_shopping, tab_suggestions, tab_inventory, tab_chat, tab_profile = st.tabs([
                "📊 Dashboard", 
                "🍽️ Meal Plan", 
                "🛒 Shopping List", 
                "💡 Suggestions", 
                "🏪 Inventory", 
                "💬 Chat",
                "⚙️ Profile"
            ])

            with tab_dashboard:
                render_dashboard(conn, st.session_state.user_id)
            
            with tab_meal_plan:
                render_meal_plan(conn, st.session_state.user_id)
                
            with tab_shopping:
                render_shopping_list(conn, st.session_state.user_id)
                
            with tab_suggestions:
                render_suggestions(conn, st.session_state.user_id)
                
            with tab_inventory:
                render_inventory(conn, st.session_state.user_id)

            with tab_chat:
                render_chat(conn, st.session_state.user_id)
                
            with tab_profile:
                render_profile(conn, st.session_state.user_id)


if __name__ == "__main__":
    main()
