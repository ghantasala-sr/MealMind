import streamlit as st
from typing import Dict, Any, List, TypedDict, Optional
from langchain_community.chat_models import ChatSnowflakeCortex
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
import json

# ==================== LANGGRAPH STATE ====================
class ChatState(TypedDict):
    messages: List[Any]
    user_profile: Dict
    inventory_summary: str
    meal_plan_summary: str
    context: str

# ==================== CHAT AGENT ====================
class ChatAgent:
    """Agent for handling user chat interactions about meal plans and inventory"""

    def __init__(self, session):
        self.session = session
        try:
            # Initialize Cortex Chat Model
            self.chat_model = ChatSnowflakeCortex(
                session=self.session,
                model="llama3.1-70b", # Using a capable model for chat
                cortex_search_service="MEAL_MIND_SEARCH_SERVICE" # Optional: if we have a search service
            )
        except Exception as e:
            st.warning(f"Chat Agent initialization failed: {e}")
            self.chat_model = None

    def get_system_prompt(self, state: ChatState) -> str:
        """Construct the system prompt with context"""
        profile = state.get('user_profile', {})
        inventory = state.get('inventory_summary', 'No inventory data available.')
        meal_plan = state.get('meal_plan_summary', 'No meal plan generated yet.')
        
        system_prompt = f"""
        You are Meal Mind AI, a helpful nutrition and meal planning assistant.
        
        USER PROFILE:
        - Name: {profile.get('username', 'User')}
        - Goal: {profile.get('health_goal', 'General Health')}
        - Dietary Restrictions: {profile.get('dietary_restrictions', 'None')}
        - Allergies: {profile.get('food_allergies', 'None')}
        
        CURRENT INVENTORY SUMMARY:
        {inventory}
        
        CURRENT MEAL PLAN SUMMARY:
        {meal_plan}
        
        YOUR ROLE:
        - Answer questions about the user's meal plan, inventory, and nutrition.
        - Provide cooking tips and recipe suggestions based on available inventory.
        - Be encouraging and supportive of their health goals.
        - If asked about something outside of food/nutrition, politely steer back to the topic.
        - Keep answers concise and helpful.
        """
        return system_prompt

    def node_process_message(self, state: ChatState) -> ChatState:
        """Process the user message and generate a response"""
        messages = state['messages']
        system_prompt = self.get_system_prompt(state)
        
        # Prepare messages for the model
        formatted_messages = [SystemMessage(content=system_prompt)] + messages
        
        try:
            if self.chat_model:
                response = self.chat_model.invoke(formatted_messages)
                # Append AI response to history
                # Note: In a real persistent app we might manage history differently, 
                # but for this session-based chat, we just return the new message.
                return {"messages": [response]} 
            else:
                return {"messages": [AIMessage(content="I'm sorry, I'm currently offline. Please check your connection.")]}
        except Exception as e:
            return {"messages": [AIMessage(content=f"I encountered an error: {str(e)}")]}

    def build_graph(self):
        """Build the LangGraph workflow for chat"""
        workflow = StateGraph(ChatState)
        
        # Add nodes
        workflow.add_node("process_message", self.node_process_message)
        
        # Add edges
        workflow.set_entry_point("process_message")
        workflow.add_edge("process_message", END)
        
        return workflow.compile()

    def run_chat(self, user_input: str, history: List[Any], context_data: Dict) -> str:
        """Main entry point to run the chat"""
        
        # Prepare initial state
        initial_state = {
            "messages": history + [HumanMessage(content=user_input)],
            "user_profile": context_data.get('user_profile', {}),
            "inventory_summary": context_data.get('inventory_summary', ''),
            "meal_plan_summary": context_data.get('meal_plan_summary', ''),
            "context": ""
        }
        
        app = self.build_graph()
        result = app.invoke(initial_state)
        
        # Get the last message (AI response)
        last_message = result['messages'][-1]
        return last_message.content

    def run_chat_stream(self, user_input: str, history: List[Any], context_data: Dict):
        """Stream the chat response character by character"""
        
        # Get the full response first
        full_response = self.run_chat(user_input, history, context_data)
        
        # Stream it character by character
        # Split by words for more natural streaming
        words = full_response.split()
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")

