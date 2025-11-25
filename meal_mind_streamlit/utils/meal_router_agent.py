import streamlit as st
from typing import Dict, Any, List, TypedDict, Optional, Literal
from langchain_community.chat_models import ChatSnowflakeCortex
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
import json
import re
from datetime import datetime

# ==================== LANGGRAPH STATE ====================
class ChatRouterState(TypedDict):
    user_input: str
    user_id: str
    user_profile: Dict
    inventory_summary: str
    meal_plan_summary: str
    history: List[Any]
    route: Optional[Literal["meal_retrieval", "general_chat", "calorie_estimation"]]
    retrieved_data: Optional[str]
    user_preferences: Optional[Dict]  # Long-term memory
    extracted_feedback: Optional[List[Dict]]  # New feedback from this message
    response: str

# ==================== MULTI-AGENT ROUTER ====================
class MealRouterAgent:
    """Intelligent routing agent that directs queries to specialized agents"""
    
    def __init__(self, session, conn):
        self.session = session
        self.conn = conn
        try:
            # Initialize Cortex Chat Model for routing and responses
            self.chat_model = ChatSnowflakeCortex(
                session=self.session,
                model="llama3.1-70b",
                cortex_search_service="MEAL_MIND"
            )
        except Exception as e:
            st.warning(f"Chat Model initialization failed: {e}")
            self.chat_model = None
        
        # Initialize Feedback Agent for preference extraction
        from utils.feedback_agent import FeedbackAgent
        self.feedback_agent = FeedbackAgent(conn, session)
    
    # ==================== LOAD PREFERENCES NODE ====================
    def node_load_preferences(self, state: ChatRouterState) -> ChatRouterState:
        """Load user preferences from long-term memory"""
        preferences = self.feedback_agent.get_user_preferences(state['user_id'])
        state['user_preferences'] = preferences
        return state
    
    # ==================== EXTRACT FEEDBACK NODE ====================
    def node_extract_feedback(self, state: ChatRouterState) -> ChatRouterState:
        """Extract preferences from user message"""
        extracted = self.feedback_agent.extract_preferences(
            state['user_input'], 
            state['user_id']
        )
        state['extracted_feedback'] = extracted
        return state
    
    # ==================== ROUTING NODE ====================
    def node_route_query(self, state: ChatRouterState) -> ChatRouterState:
        """Analyze user query and determine which agent to route to"""
        user_input = state['user_input'].lower()
        
        # Keywords for meal retrieval
        meal_keywords = [
            'meal', 'recipe', 'breakfast', 'lunch', 'dinner', 'snack',
            'what am i eating', 'what should i eat', 'meal plan',
            'today', 'tomorrow', 'monday', 'tuesday', 'wednesday', 
            'thursday', 'friday', 'saturday', 'sunday',
            'ingredient', 'what can i make', 'show me', 'get me'
        ]
        
        # Keywords for calorie estimation
        estimation_keywords = [
            'estimate', 'calculate', 'buffet', 'restaurant', 'ate', 'eating',
            'how many calories in', 'nutritional info for'
        ]
        
        # Check for estimation intent first (specific overrides)
        if any(keyword in user_input for keyword in estimation_keywords) and not ('my plan' in user_input or 'my meal' in user_input):
            state['route'] = 'calorie_estimation'
        # Then check for retrieval
        elif any(keyword in user_input for keyword in meal_keywords):
            state['route'] = 'meal_retrieval'
        else:
            state['route'] = 'general_chat'
        
        return state
    
    # ==================== MEAL RETRIEVAL NODE ====================
    def node_retrieve_meals(self, state: ChatRouterState) -> ChatRouterState:
        """Retrieve meal information from database based on user query"""
        from utils.db import get_meals_by_criteria, get_meal_details_by_type
        
        user_input = state['user_input'].lower()
        user_id = state['user_id']
        
        try:
            # Extract meal type from query
            meal_type = None
            if 'breakfast' in user_input:
                meal_type = 'breakfast'
            elif 'lunch' in user_input:
                meal_type = 'lunch'
            elif 'dinner' in user_input:
                meal_type = 'dinner'
            elif 'snack' in user_input:
                meal_type = 'snacks'
            
            # Extract day from query
            days_map = {
                'monday': 1, 'tuesday': 2, 'wednesday': 3, 'thursday': 4,
                'friday': 5, 'saturday': 6, 'sunday': 7,
                'today': datetime.now().weekday() + 1
            }
            
            day_number = None
            for day_name, day_num in days_map.items():
                if day_name in user_input:
                    day_number = day_num
                    break
            
            # Query database
            meals = get_meals_by_criteria(self.conn, user_id, day_number, meal_type)
            
            if meals:
                # Format the retrieved data
                formatted_data = "## Retrieved Meals\n\n"
                for meal in meals:
                    formatted_data += f"**{meal.get('meal_name', 'Unknown')}** ({meal.get('meal_type', '').title()})\n"
                    formatted_data += f"- Day: {meal.get('day_name', 'Unknown')}\n"
                    
                    nutrition = meal.get('nutrition', {})
                    if nutrition:
                        formatted_data += f"- Calories: {nutrition.get('calories', 'N/A')} kcal\n"
                        formatted_data += f"- Protein: {nutrition.get('protein_g', 'N/A')}g\n"
                    
                    ingredients = meal.get('ingredients_with_quantities', [])
                    if ingredients:
                        formatted_data += "- Ingredients: " + ", ".join([ing.get('ingredient', '') for ing in ingredients[:5]]) + "\n"
                    
                    formatted_data += "\n"
                
                state['retrieved_data'] = formatted_data
            else:
                state['retrieved_data'] = "No meals found matching your criteria. You may not have an active meal plan."
        
        except Exception as e:
            state['retrieved_data'] = f"Error retrieving meals: {str(e)}"
        
        return state
    
    # ==================== GENERAL CHAT NODE ====================
    def node_general_chat(self, state: ChatRouterState) -> ChatRouterState:
        """Handle general nutrition and cooking questions"""
        user_profile = state['user_profile']
        inventory = state['inventory_summary']
        meal_plan = state['meal_plan_summary']
        history = state['history']
        preferences = state.get('user_preferences', {})
        
        # Format preferences for prompt
        pref_text = self.feedback_agent.format_preferences_for_prompt(preferences)
        
        system_prompt = f"""You are Meal Mind AI, a helpful nutrition and meal planning assistant.

USER PROFILE:
- Name: {user_profile.get('username', 'User')}
- Goal: {user_profile.get('health_goal', 'General Health')}
- Dietary Restrictions: {user_profile.get('dietary_restrictions', 'None')}
- Allergies: {user_profile.get('food_allergies', 'None')}

USER PREFERENCES (LEARNED):
{pref_text}

CURRENT INVENTORY:
{inventory[:500]}...

MEAL PLAN SUMMARY:
{meal_plan[:300]}...

YOUR ROLE:
- Provide nutrition advice and cooking tips considering user preferences
- Answer health and wellness questions
- Be encouraging and supportive
- Keep responses concise and helpful
- IMPORTANT: Respect user dislikes and preferences in your suggestions
"""
        
        # Prepare messages
        messages = [SystemMessage(content=system_prompt)]
        
        # Add history (last 5 messages)
        for msg in history[-5:]:
            messages.append(msg)
        
        # Add current query
        messages.append(HumanMessage(content=state['user_input']))
        
        try:
            if self.chat_model:
                response = self.chat_model.invoke(messages)
                state['response'] = response.content
            else:
                state['response'] = "I'm currently in offline mode. Please check your connection."
        except Exception as e:
            state['response'] = f"I encountered an error: {str(e)}"
        
        return state

    # ==================== CALORIE ESTIMATION NODE ====================
    def node_estimate_calories(self, state: ChatRouterState) -> ChatRouterState:
        """Estimate calories for unstructured food descriptions"""
        user_input = state['user_input']
        
        system_prompt = """You are an expert nutritionist and calorie estimator. 
The user will describe a meal (e.g., from a buffet, restaurant, or home cooking).

Your task is to:
1. Analyze the food items described.
2. Estimate portion sizes if not specified (make reasonable assumptions based on standard servings).
3. Calculate the approximate Calories and Macronutrients (Protein, Carbs, Fat) for each item and the total.
4. Provide a clear breakdown.
5. Offer a brief, non-judgmental health tip regarding this meal.

Format the output using Markdown:
- Use bold for totals.
- Use a list for the breakdown.
"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input)
        ]
        
        try:
            if self.chat_model:
                response = self.chat_model.invoke(messages)
                state['response'] = response.content
            else:
                state['response'] = "I'm offline and cannot estimate calories right now."
        except Exception as e:
            state['response'] = f"Error estimating calories: {str(e)}"
            
        return state
    
    # ==================== RESPONSE GENERATION NODE ====================
    def node_generate_response(self, state: ChatRouterState) -> ChatRouterState:
        """Generate final response using retrieved data if available"""
        
        # If we have retrieved meal data, use it to generate response
        if state.get('retrieved_data'):
            user_profile = state['user_profile']
            
            system_prompt = f"""You are Meal Mind AI. The user asked about their meals and we retrieved this data:

{state['retrieved_data']}

USER PROFILE:
- Goal: {user_profile.get('health_goal', 'General Health')}

Generate a helpful, conversational response that:
1. Presents the meal information clearly
2. Relates it to their health goals
3. Offers any relevant tips or suggestions
4. Keep it concise and friendly
"""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=state['user_input'])
            ]
            
            try:
                if self.chat_model:
                    response = self.chat_model.invoke(messages)
                    state['response'] = response.content
                else:
                    # Fallback to just showing the data
                    state['response'] = state['retrieved_data']
            except Exception as e:
                state['response'] = state['retrieved_data']
        
        # If response is already set from general_chat, keep it
        return state
    
    # ==================== CONDITIONAL EDGES ====================
    def should_retrieve_meals(self, state: ChatRouterState) -> str:
        """Determine next node based on route"""
        if state['route'] == 'meal_retrieval':
            return 'retrieve_meals'
        elif state['route'] == 'calorie_estimation':
            return 'estimate_calories'
        else:
            return 'general_chat'
    
    def should_generate_response(self, state: ChatRouterState) -> str:
        """Check if we need to generate response or already have it"""
        if state['route'] == 'meal_retrieval':
            return 'generate_response'
        else:
            return 'end'
    
    # ==================== BUILD GRAPH ====================
    def build_graph(self):
        """Build the LangGraph workflow with memory integration"""
        workflow = StateGraph(ChatRouterState)
        
        # Add nodes
        workflow.add_node("load_preferences", self.node_load_preferences)
        workflow.add_node("extract_feedback", self.node_extract_feedback)
        workflow.add_node("route_query", self.node_route_query)
        workflow.add_node("retrieve_meals", self.node_retrieve_meals)
        workflow.add_node("estimate_calories", self.node_estimate_calories)
        workflow.add_node("general_chat", self.node_general_chat)
        workflow.add_node("generate_response", self.node_generate_response)
        
        # Add edges - Memory-aware workflow
        workflow.set_entry_point("load_preferences")
        workflow.add_edge("load_preferences", "extract_feedback")
        workflow.add_edge("extract_feedback", "route_query")
        
        # Conditional routing after route_query
        workflow.add_conditional_edges(
            "route_query",
            self.should_retrieve_meals,
            {
                "retrieve_meals": "retrieve_meals",
                "estimate_calories": "estimate_calories",
                "general_chat": "general_chat"
            }
        )
        
        # After retrieve_meals, generate response
        workflow.add_edge("retrieve_meals", "generate_response")
        
        # After generate_response or general_chat, end
        workflow.add_edge("generate_response", END)
        workflow.add_edge("general_chat", END)
        workflow.add_edge("estimate_calories", END)
        
        return workflow.compile()
    
    # ==================== RUN METHODS ====================
    def run_chat(self, user_input: str, user_id: str, history: List[Any], context_data: Dict) -> str:
        """Main entry point to run the multi-agent chat"""
        
        initial_state = ChatRouterState(
            user_input=user_input,
            user_id=user_id,
            user_profile=context_data.get('user_profile', {}),
            inventory_summary=context_data.get('inventory_summary', ''),
            meal_plan_summary=context_data.get('meal_plan_summary', ''),
            history=history,
            route=None,
            retrieved_data=None,
            user_preferences=None,
            extracted_feedback=None,
            response=""
        )
        
        app = self.build_graph()
        result = app.invoke(initial_state)
        
        return result['response']
    
    def run_chat_stream(self, user_input: str, user_id: str, history: List[Any], context_data: Dict):
        """Stream the chat response word by word"""
        
        # Get the full response first
        full_response = self.run_chat(user_input, user_id, history, context_data)
        
        # Stream it word by word
        words = full_response.split()
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
