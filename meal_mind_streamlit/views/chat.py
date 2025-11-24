import streamlit as st
from utils.meal_router_agent import MealRouterAgent
from utils.db import get_user_profile, get_user_inventory, get_latest_meal_plan, get_snowpark_session
from langchain.schema import HumanMessage, AIMessage
import time

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
    
    # Header with better styling
    col1, col2 = st.columns([0.9, 0.1])
    with col1:
        st.title("💬 Chat with Meal Mind")
        st.caption("🤖 Ask questions about your meal plan, inventory, or get personalized cooking tips!")
    with col2:
        if st.button("🗑️", help="Clear chat history"):
            st.session_state.messages = [
                AIMessage(content="Hello! I'm Meal Mind. How can I help you with your nutrition today?")
            ]
            st.rerun()

    st.divider()

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = [
            AIMessage(content="Hello! I'm Meal Mind. How can I help you with your nutrition today?")
        ]

    # Initialize Chat Agent with Router
    if "chat_agent" not in st.session_state:
        session = get_snowpark_session()
        st.session_state.chat_agent = MealRouterAgent(session, conn)

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

    # Chat Input
    if prompt := st.chat_input("What would you like to know?", key="chat_input"):
        # Add user message to state
        st.session_state.messages.append(HumanMessage(content=prompt))
        
        # Display user message immediately
        with message_container:
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)

        # Prepare context data
        try:
            # Fetch fresh context
            with st.spinner("Gathering your data..."):
                user_profile = get_user_profile(conn, user_id)
                inventory_df = get_user_inventory(conn, user_id)
                meal_plan_data = get_latest_meal_plan(conn, user_id)
                
                # Format inventory summary
                if not inventory_df.empty:
                    inv_summary = inventory_df.head(20).to_string()  # Limit for token efficiency
                else:
                    inv_summary = "Inventory is empty."
                
                # Format meal plan summary
                if meal_plan_data:
                    mp_summary = str(meal_plan_data.get('meal_plan', {}).get('week_summary', ''))
                    meal_plan_summary = f"Week Summary: {mp_summary}"
                else:
                    meal_plan_summary = "No active meal plan."

                context_data = {
                    "user_profile": user_profile,
                    "inventory_summary": inv_summary,
                    "meal_plan_summary": meal_plan_summary
                }

            # Get streaming response from agent
            with message_container:
                with st.chat_message("assistant", avatar="🤖"):
                    message_placeholder = st.empty()
                    full_response = ""
                    
                    # Stream the response
                    for chunk in st.session_state.chat_agent.run_chat_stream(
                        user_input=prompt,
                        user_id=user_id,
                        history=st.session_state.messages[:-1],
                        context_data=context_data
                    ):
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")
                        time.sleep(0.02)  # Slight delay for visual effect
                    
                    # Final response without cursor
                    message_placeholder.markdown(full_response)
            
            # Add assistant response to state
            st.session_state.messages.append(AIMessage(content=full_response))
            
        except Exception as e:
            with message_container:
                with st.chat_message("assistant", avatar="🤖"):
                    st.error(f"I encountered an error: {str(e)}")
                    st.info("Please try rephrasing your question or check your connection.")

