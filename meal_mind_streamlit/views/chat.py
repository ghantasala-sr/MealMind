import streamlit as st
from utils.meal_router_agent import MealRouterAgent
from utils.db import get_user_profile, get_user_inventory, get_latest_meal_plan, get_snowpark_session
from utils.thread_manager import ThreadManager
from utils.feedback_agent import FeedbackAgent
from langchain.schema import HumanMessage, AIMessage
import time

@st.fragment
def render_chat(conn, user_id):
    """Render the enhanced chat interface with intelligent routing"""
    
    # Custom CSS for better chat layout
    st.markdown("""
        <style>
        /* Chat container */
        .stChatMessage {
            padding: 1rem !important;
            border-radius: 0.5rem !important;
            margin-bottom: 0.5rem !important;
        }
        
        /* User message styling */
        .stChatMessage[data-testid="user-message"] {
            background-color: #262730 !important;
        }
        
        /* Assistant message styling */
        .stChatMessage[data-testid="assistant-message"] {
            background-color: #1e1e1e !important;
        }
        
        /* Chat input */
        .stChatInputContainer {
            border-top: 1px solid #2e2e2e !important;
            padding-top: 1rem !important;
        }
        
        /* Improve readability */
        .stChatMessage p {
            line-height: 1.6 !important;
            margin-bottom: 0.5rem !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Thread Management
    thread_mgr = ThreadManager(conn)
    
    # Initialize current thread
    if "current_thread_id" not in st.session_state:
        # Create first thread
        thread_id = thread_mgr.create_thread(user_id)
        st.session_state.current_thread_id = thread_id
    
    # Thread Selector UI
    if "thread_list_cache" not in st.session_state:
        st.session_state.thread_list_cache = thread_mgr.get_user_threads(user_id, limit=3)
    threads = st.session_state.thread_list_cache
    
    col1, col2, col3, col4 = st.columns([0.5, 0.3, 0.1, 0.1])
    with col1:
        st.title("💬 Chat with Meal Mind")
    with col2:
        if threads:
            thread_options = {t['thread_id']: t['title'] for t in threads}
            selected = st.selectbox(
                "Conversation",
                options=list(thread_options.keys()),
                format_func=lambda x: thread_options[x][:30] + "...",
                index=0,
                label_visibility="collapsed"
            )
            if selected != st.session_state.current_thread_id:
                st.session_state.current_thread_id = selected
                # Load messages from database for selected thread
                db_messages = thread_mgr.get_thread_messages(selected)
                st.session_state.messages = []
                for msg in db_messages:
                    if msg['role'] == 'user':
                        st.session_state.messages.append(HumanMessage(content=msg['content']))
                    else:
                        st.session_state.messages.append(AIMessage(content=msg['content']))
                # Add welcome message if no messages
                if not st.session_state.messages:
                    st.session_state.messages = [
                        AIMessage(content="Hello! I'm Meal Mind. How can I help you with your nutrition today?")
                    ]
                st.rerun()
    with col3:
        if st.button("➕", help="New conversation"):
            new_thread = thread_mgr.create_thread(user_id)
            # Invalidate cache so new thread appears
            if "thread_list_cache" in st.session_state:
                del st.session_state.thread_list_cache
            st.session_state.current_thread_id = new_thread
            st.session_state.messages = [
                AIMessage(content="Hello! I'm Meal Mind. How can I help you with your nutrition today?")
            ]
            st.rerun()
    with col4:
        if st.button("🔄", help="Refresh Context (Profile, Inventory, Meal Plan)"):
            # Clear all caches
            if "chat_context_cache" in st.session_state:
                del st.session_state.chat_context_cache
            if "user_preferences_cache" in st.session_state:
                del st.session_state.user_preferences_cache
            if "chat_agent" in st.session_state:
                del st.session_state.chat_agent
            
            # Clear Streamlit data caches for specific functions
            get_user_profile.clear()
            get_user_inventory.clear()
            get_latest_meal_plan.clear()
            
            # Also clear meal plan view caches so updates (like adding food) show up there
            from utils.db import get_daily_meals_for_plan, get_weekly_meal_details
            get_daily_meals_for_plan.clear()
            get_weekly_meal_details.clear()
            
            st.toast("Context refreshed! Reloading...", icon="🔄")
            time.sleep(1)
            st.rerun()
    
    st.caption("🤖 Ask questions about your meal plan, inventory, or get personalized cooking tips!")
    st.divider()

    # Initialize chat history from database
    if "messages" not in st.session_state or len(st.session_state.messages) == 0:
        # Load messages from current thread
        if st.session_state.current_thread_id:
            db_messages = thread_mgr.get_thread_messages(st.session_state.current_thread_id)
            st.session_state.messages = []
            for msg in db_messages:
                if msg['role'] == 'user':
                    st.session_state.messages.append(HumanMessage(content=msg['content']))
                else:
                    st.session_state.messages.append(AIMessage(content=msg['content']))
        
        # Add welcome message if no messages loaded
        if not st.session_state.messages:
            st.session_state.messages = [
                AIMessage(content="Hello! I'm Meal Mind. How can I help you with your nutrition today?")
            ]

    # Initialize Chat Agent with Router (Eager Init will happen inside Agent)
    if "chat_agent" not in st.session_state:
        import importlib
        import utils.chat_agent
        import utils.meal_router_agent
        import utils.meal_adjustment_agent
        
        importlib.reload(utils.chat_agent)
        importlib.reload(utils.meal_adjustment_agent)
        importlib.reload(utils.meal_router_agent)
        
        from utils.meal_router_agent import MealRouterAgent
        
        session = get_snowpark_session()
        st.session_state.chat_agent = MealRouterAgent(session, conn)

    # Initialize Feedback Agent
    if "feedback_agent" not in st.session_state:
        session = get_snowpark_session()
        st.session_state.feedback_agent = FeedbackAgent(conn, session)

    # --- OPTIMIZATION: Pre-load and Cache Context & Preferences ---
    if "chat_context_cache" not in st.session_state or not st.session_state.chat_context_cache:
        with st.spinner("Loading your profile and preferences..."):
            # 1. Load Context (Profile, Inventory, Meal Plan)
            from concurrent.futures import ThreadPoolExecutor
            # from utils.db import get_user_profile, get_user_inventory, get_latest_meal_plan (Already imported globally)
            from utils.db import get_meals_by_criteria # Import this to get detailed meals
            
            # We can also fetch preferences here in parallel
            def get_prefs(agent, uid):
                return agent.get_user_preferences(uid)

            with ThreadPoolExecutor(max_workers=4) as executor:
                future_profile = executor.submit(get_user_profile, conn, user_id)
                future_inventory = executor.submit(get_user_inventory, conn, user_id)
                future_meal_plan = executor.submit(get_latest_meal_plan, conn, user_id)
                # Pass the agent instance directly, don't access st.session_state inside thread
                future_prefs = executor.submit(get_prefs, st.session_state.feedback_agent, user_id)
                # Fetch detailed meals for the week
                future_daily_meals = executor.submit(get_meals_by_criteria, conn, user_id)
                
                user_profile = future_profile.result()
                inventory_df = future_inventory.result()
                meal_plan_data = future_meal_plan.result()
                user_prefs = future_prefs.result()
                daily_meals_list = future_daily_meals.result()
            
            # Format inventory summary
            if not inventory_df.empty:
                inv_summary = inventory_df.head(20).to_string()
            else:
                inv_summary = "Inventory is empty."
            
            # Format meal plan summary
            if meal_plan_data:
                mp_summary = str(meal_plan_data.get('meal_plan', {}).get('week_summary', ''))
                meal_plan_summary = f"Week Summary: {mp_summary}"
                
                # Format daily meals for context
                if daily_meals_list:
                    import json
                    # Group by day
                    days = {}
                    for meal in daily_meals_list:
                        day = meal['day_name']
                        if day not in days:
                            days[day] = []
                        days[day].append(f"{meal['meal_type'].title()}: {meal['meal_name']}")
                    
                    daily_details = "\n".join([f"{day}: {', '.join(meals)}" for day, meals in days.items()])
                    meal_plan_summary += f"\n\nDaily Schedule:\n{daily_details}"
            else:
                meal_plan_summary = "No active meal plan."

            # Store in Session State
            st.session_state.chat_context_cache = {
                "user_profile": user_profile,
                "inventory_summary": inv_summary,
                "meal_plan_summary": meal_plan_summary
            }
            st.session_state.user_preferences_cache = user_prefs
    # -----------------------------------------------------------

    # Create a container for messages
    message_container = st.container(height=500)
    
    with message_container:
        # Display chat messages
        for i, msg in enumerate(st.session_state.messages):
            if isinstance(msg, HumanMessage):
                with st.chat_message("user", avatar="👤"):
                    st.markdown(msg.content)
            elif isinstance(msg, AIMessage):
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(msg.content)
                    
                    # Add feedback buttons (only for AI messages, not the welcome message)
                    if i > 0:  # Skip welcome message
                        col1, col2, col3 = st.columns([0.1, 0.1, 0.8])
                        with col1:
                            if st.button("👍", key=f"like_{i}", help="I like this response"):
                                st.session_state.feedback_agent.save_explicit_feedback(
                                    user_id=user_id,
                                    entity_id=f"msg_{i}",
                                    entity_name=f"Response about: {st.session_state.messages[i-1].content[:30]}...",
                                    entity_type="ai_response",
                                    feedback="like"
                                )
                                st.success("Thanks for the feedback!")
                        with col2:
                            if st.button("👎", key=f"dislike_{i}", help="I don't like this response"):
                                st.session_state.feedback_agent.save_explicit_feedback(
                                    user_id=user_id,
                                    entity_id=f"msg_{i}",
                                    entity_name=f"Response about: {st.session_state.messages[i-1].content[:30]}...",
                                    entity_type="ai_response",
                                    feedback="dislike"
                                )
                                st.warning("Thanks for the feedback! We'll improve.")

    # Chat Input
    if prompt := st.chat_input("What would you like to know?", key="chat_input"):
        # Add user message to state
        st.session_state.messages.append(HumanMessage(content=prompt))
        
        # Display user message immediately (Optimistic UI)
        with message_container:
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)

        # Persist user message to database (Background Thread)
        import threading
        def save_message_bg(thread_id, role, content):
            try:
                # Create a new cursor for the background thread to avoid conflicts
                # Note: Snowflake connection is thread-safe if we use separate cursors
                thread_mgr.add_message(thread_id, role, content)
            except Exception as e:
                print(f"Background save failed: {e}")

        save_thread = threading.Thread(
            target=save_message_bg,
            args=(st.session_state.current_thread_id, "user", prompt)
        )
        save_thread.start()

        # Get streaming response from agent
        try:
            with message_container:
                with st.chat_message("assistant", avatar="🤖"):
                    message_placeholder = st.empty()
                    message_placeholder.markdown("Thinking...")
                    full_response = ""
                    
                    # Stream the response
                    # Pass thread_id for checkpointer
                    for chunk in st.session_state.chat_agent.run_chat_stream(
                        user_input=prompt,
                        user_id=user_id,
                        history=st.session_state.messages[:-1],
                        context_data=st.session_state.chat_context_cache,
                        user_preferences=st.session_state.user_preferences_cache,
                        thread_id=st.session_state.current_thread_id
                    ):
                        if chunk.startswith("__STATUS__:"):
                            status_msg = chunk.replace("__STATUS__: ", "")
                            message_placeholder.markdown(f"*{status_msg}*")
                            # No sleep here for speed
                        else:
                            full_response += chunk
                            message_placeholder.markdown(full_response + "▌")
                            # No sleep here for speed
                    
                    # Final response without cursor
                    message_placeholder.markdown(full_response)
            
            # Add assistant response to state
            st.session_state.messages.append(AIMessage(content=full_response))
            
            # Persist assistant message to database
            thread_mgr.add_message(
                thread_id=st.session_state.current_thread_id,
                role="assistant",
                content=full_response
            )
            
            # Generate thread title if this is the first user message
            if len(st.session_state.messages) == 3:  # Welcome + user + assistant
                thread_mgr.generate_thread_title(
                    thread_id=st.session_state.current_thread_id,
                    first_message=prompt,
                    use_llm=True
                )
            
        except Exception as e:
            with message_container:
                with st.chat_message("assistant", avatar="🤖"):
                    st.error(f"I encountered an error: {str(e)}")
                    st.info("Please try rephrasing your question or check your connection.")

