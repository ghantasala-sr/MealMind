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
    route: Optional[Literal["meal_retrieval", "general_chat", "calorie_estimation", "meal_adjustment"]]
    retrieved_data: Optional[str]
    user_preferences: Optional[Dict]  # Long-term memory
    extracted_feedback: Optional[List[Dict]]  # New feedback from this message
    response: str
    final_messages: Optional[List[Any]] # Messages prepared for the LLM
    adjustment_result: Optional[Dict] # Result from adjustment agent
    monitoring_warnings: Optional[List[str]] # Warnings from monitoring agent

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
                cortex_search_service="MEAL_MIND",
                streaming=True
            )
        except Exception as e:
            st.warning(f"Chat Model initialization failed: {e}")
            self.chat_model = None
        
        # Initialize Agents (Eager Load)
        from utils.feedback_agent import FeedbackAgent
        from utils.meal_adjustment_agent import MealAdjustmentAgent
        from utils.monitoring_agent import MonitoringAgent
        
        self.feedback_agent = FeedbackAgent(self.conn, self.session)
        self.adjustment_agent = MealAdjustmentAgent(self.session, self.conn)
        self.monitoring_agent = MonitoringAgent(self.conn)
    
    
    # ==================== LOAD PREFERENCES NODE ====================
    def node_load_preferences(self, state: ChatRouterState) -> ChatRouterState:
        """Load user preferences from long-term memory"""
        # If already pre-loaded, skip DB call
        if state.get('user_preferences'):
            return state
            
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
            'estimate', 'calculate', 'how many calories in', 'nutritional info for'
        ]
        
        # Keywords for meal adjustment/reporting
        adjustment_keywords = [
            'add', 'remove', 'delete', 'change', 'replace', 'swap', 'instead', 'don\'t want', 'ate', 'had', 'went to', 
            'buffet', 'restaurant', 'eaten', 'drank', 'consumed'
        ]
        
        # Check for adjustment/reporting first
        # We need to be careful not to catch questions like "What did I have?"
        is_adjustment_intent = False
        if any(keyword in user_input for keyword in adjustment_keywords) and \
           any(meal in user_input for meal in ['breakfast', 'lunch', 'dinner', 'snack', 'meal']):
            is_adjustment_intent = True
            
            # Exception: If it's a question containing "what", it's likely retrieval
            # unless it explicitly asks to change/replace
            if 'what' in user_input and not any(k in user_input for k in ['change', 'replace', 'swap', 'add', 'instead']):
                is_adjustment_intent = False

        if is_adjustment_intent:
            state['route'] = 'meal_adjustment'
            
        # Check for estimation intent
        elif any(keyword in user_input for keyword in estimation_keywords) and not ('my plan' in user_input or 'my meal' in user_input):
            state['route'] = 'calorie_estimation'
            
        # Then check for retrieval
        elif any(keyword in user_input for keyword in meal_keywords):
            state['route'] = 'meal_retrieval'
            
        else:
            state['route'] = 'general_chat'
        
        # DEBUG: Print routing decision
        print(f"DEBUG: Routing query '{user_input}' -> {state['route']}")
        
        return state
    
    # ==================== MEAL RETRIEVAL NODE ====================
    def node_retrieve_meals(self, state: ChatRouterState) -> ChatRouterState:
        """Retrieve meal information from database based on user query"""
        print("DEBUG: Entering node_retrieve_meals")
        from utils.db import get_meals_by_criteria
        import json
        from datetime import datetime
        
        user_input = state['user_input'].lower()
        user_id = state['user_id']
        
        try:
            # 1. Try Rule-Based Extraction
            meal_type = None
            if 'breakfast' in user_input:
                meal_type = 'breakfast'
            elif 'lunch' in user_input:
                meal_type = 'lunch'
            elif 'dinner' in user_input:
                meal_type = 'dinner'
            elif 'snack' in user_input:
                meal_type = 'snacks'
            
            # Calculate dates instead of day numbers
            from datetime import timedelta
            today = datetime.now()
            target_date = None
            
            if 'today' in user_input:
                target_date = today
            elif 'tomorrow' in user_input:
                target_date = today + timedelta(days=1)
            else:
                # Check for day names
                weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                for i, day in enumerate(weekdays):
                    if day in user_input:
                        # Find the next occurrence of this day (or today if it matches)
                        current_weekday = today.weekday()
                        days_ahead = i - current_weekday
                        if days_ahead < 0: # Target day already passed this week, assume next week? 
                            # Or maybe the user means "last Monday"? 
                            # For meal planning, usually means upcoming.
                            days_ahead += 7
                        target_date = today + timedelta(days=days_ahead)
                        break
            
            meal_date = None
            if target_date:
                meal_date = target_date.strftime('%Y-%m-%d')
            
            # 2. If Rule-Based failed to find a specific day, try LLM Extraction for Dates
            # We only do this if we have a chat model available
            if meal_date is None and self.chat_model:
                try:
                    extraction_prompt = f"""
                    Extract the date and meal type from the user query.
                    Query: "{state['user_input']}"
                    
                    Return ONLY a JSON object with keys:
                    - "date": YYYY-MM-DD format (or null if not found). Assume current year {datetime.now().year} if not specified.
                    - "meal_type": breakfast, lunch, dinner, snacks (or null if not found)
                    """
                    
                    response = self.chat_model.invoke([HumanMessage(content=extraction_prompt)])
                    content = response.content.strip()
                    # Clean up markdown code blocks if present
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0].strip()
                        
                    extracted = json.loads(content)
                    
                    if extracted.get('date'):
                        meal_date = extracted['date']
                    
                    # If we didn't find meal_type via rules, use LLM result
                    if not meal_type and extracted.get('meal_type'):
                        meal_type = extracted['meal_type']
                        
                except Exception as e:
                    print(f"LLM Extraction failed: {e}")
                    # Fallback to ignoring date
            
            # 3. Query Database
            # Pass meal_date if we found one, otherwise get_meals_by_criteria might return all or default
            # We explicitly set day_number to None to avoid the mismatch issue
            meals = get_meals_by_criteria(self.conn, user_id, day_number=None, meal_type=meal_type, meal_date=meal_date)
            
            if meals:
                # Format the retrieved data
                formatted_data = "## Retrieved Meals\n\n"
                for meal in meals:
                    formatted_data += f"**{meal.get('meal_name', 'Unknown')}** ({meal.get('meal_type', '').title()})\n"
                    if meal.get('meal_date'):
                        formatted_data += f"- Date: {meal.get('meal_date')}\n"
                    else:
                        formatted_data += f"- Day: {meal.get('day_name', 'Unknown')}\n"
                    
                    nutrition = meal.get('nutrition', {})
                    if nutrition:
                        formatted_data += f"- Calories: {nutrition.get('calories', 'N/A')} kcal\n"
                        formatted_data += f"- Protein: {nutrition.get('protein_g', 'N/A')}g\n"
                    
                    ingredients = meal.get('ingredients_with_quantities', [])
                    if ingredients:
                        formatted_data += "- Ingredients: " + ", ".join([ing.get('ingredient', '') for ing in ingredients[:5]]) + "\n"
                    
                    formatted_data += "\n"
                
                # Update state
                new_state = state.copy()
                new_state['retrieved_data'] = formatted_data
                return new_state
            else:
                new_state = state.copy()
                new_state['retrieved_data'] = "No meals found matching your criteria. You may not have an active meal plan for this date."
                return new_state
        
        except Exception as e:
            new_state = state.copy()
            new_state['retrieved_data'] = f"Error retrieving meals: {str(e)}"
            return new_state
    
    # ==================== MEAL ADJUSTMENT NODE ====================
    def node_adjust_meal(self, state: ChatRouterState) -> ChatRouterState:
        """Handle meal changes and restaurant entries"""
        import json
        from datetime import datetime
        
        user_input = state['user_input'].lower()
        user_id = state['user_id']
        
        # 1. Try Rule-Based Extraction
        meal_type = 'lunch' # Default
        if 'breakfast' in user_input: meal_type = 'breakfast'
        elif 'dinner' in user_input: meal_type = 'dinner'
        elif 'snack' in user_input: meal_type = 'snacks'
        
        date = datetime.now().strftime('%Y-%m-%d')
        
        # 2. Try LLM Extraction for Date if keywords suggest a specific date
        # Keywords: month names, numbers, "tomorrow", "yesterday"
        date_indicators = [
            'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
            'tomorrow', 'yesterday', 'next', 'last', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'
        ]
        
        if any(indicator in user_input for indicator in date_indicators) and self.chat_model:
            try:
                extraction_prompt = f"""
                Extract the date and meal type from the user query for a meal update.
                Query: "{state['user_input']}"
                
                Return ONLY a JSON object with keys:
                - "date": YYYY-MM-DD format (or null if not found). Assume current year {datetime.now().year} if not specified.
                - "meal_type": breakfast, lunch, dinner, snacks (or null if not found)
                """
                
                response = self.chat_model.invoke([HumanMessage(content=extraction_prompt)])
                content = response.content.strip()
                # Clean up markdown code blocks if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                    
                extracted = json.loads(content)
                
                if extracted.get('date'):
                    date = extracted['date']
                
                if extracted.get('meal_type'):
                    meal_type = extracted['meal_type']
                    
            except Exception as e:
                print(f"LLM Adjustment Extraction failed: {e}")
                # Fallback to default date/type
        
        result = self.adjustment_agent.process_request(
            user_input, user_id, date, meal_type
        )
        
        # Create a new state copy to ensure updates are detected
        new_state = state.copy()
        new_state['adjustment_result'] = result
        
        # If successful, we should also set a response message
        if result.get('status') == 'success':
            new_state['response'] = result.get('message')
            new_state['final_messages'] = None # No need for further LLM generation
        else:
            # If failed, let the LLM explain or just show the error
            new_state['response'] = result.get('message')
            new_state['final_messages'] = None
            
        return new_state

    # ==================== MONITORING NODE ====================
    def node_monitor_changes(self, state: ChatRouterState) -> ChatRouterState:
        """Monitor changes and generate warnings"""
        if state.get('adjustment_result', {}).get('status') == 'success':
            user_id = state['user_id']
            date = datetime.now().strftime('%Y-%m-%d')
            
            warnings = self.monitoring_agent.monitor_changes(user_id, date)
            state['monitoring_warnings'] = warnings
            
        return state

    # ==================== GENERAL CHAT NODE ====================
    def node_general_chat(self, state: ChatRouterState) -> ChatRouterState:
        """Prepare messages for general chat"""
        user_profile = state['user_profile']
        inventory = state['inventory_summary']
        meal_plan = state['meal_plan_summary']
        history = state['history']
        preferences = state.get('user_preferences', {})
        
        # Format preferences for prompt
        pref_text = self.feedback_agent.format_preferences_for_prompt(preferences)
        
        from datetime import datetime
        current_date_str = datetime.now().strftime('%A, %B %d, %Y')
        
        # DEBUG: Print date to terminal
        print(f"DEBUG: ROUTER SYSTEM DATE IS {current_date_str}")
        
        system_prompt = f"""You are Meal Mind AI, a helpful nutrition and meal planning assistant.

TODAY'S DATE: {current_date_str}

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
- CRITICAL: STRICTLY respect the user's dietary restrictions and allergies. NEVER suggest foods they cannot eat.
"""
        
        # Prepare messages
        messages = [SystemMessage(content=system_prompt)]
        
        # Add history (last 5 messages)
        # Filter history to ensure valid sequence (System -> User -> AI -> User...)
        # specifically, we cannot have System -> AI. The first history msg must be Human.
        
        recent_history = history[-5:]
        start_index = 0
        
        # Skip leading AI messages in the history chunk
        for i, msg in enumerate(recent_history):
            if isinstance(msg, HumanMessage):
                start_index = i
                break
            if i == len(recent_history) - 1:
                start_index = len(recent_history) # Skip all if no HumanMessage found
        
        for msg in recent_history[start_index:]:
            messages.append(msg)
        
        # Add current query
        messages.append(HumanMessage(content=state['user_input']))
        
        # Return full state copy to ensure update is detected
        new_state = state.copy()
        new_state['final_messages'] = messages
        return new_state

    # ==================== CALORIE ESTIMATION NODE ====================
    def node_estimate_calories(self, state: ChatRouterState) -> ChatRouterState:
        """Prepare messages for calorie estimation"""
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
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input)
        ]
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input)
        ]
        
        new_state = state.copy()
        new_state['final_messages'] = messages
        return new_state
    
    # ==================== RESPONSE GENERATION NODE ====================
    def node_generate_response(self, state: ChatRouterState) -> ChatRouterState:
        """Prepare messages for retrieval/adjustment response"""
        
        # Case 1: Adjustment Result
        if state.get('adjustment_result'):
            result = state['adjustment_result']
            warnings = state.get('monitoring_warnings', [])
            
            if result['status'] == 'success':
                response = f"✅ {result['message']}\n\n"
                response += "**New Daily Total:**\n"
                totals = result['new_daily_total']
                response += f"- Calories: {totals['calories']} kcal\n"
                response += f"- Protein: {totals['protein_g']}g\n"
                response += f"- Carbs: {totals['carbohydrates_g']}g\n"
                response += f"- Fat: {totals['fat_g']}g\n"
                response += f"- Fiber: {totals['fiber_g']}g\n"
                
                if warnings:
                    response += "\n**Health Alerts:**\n"
                    for w in warnings:
                        response += f"{w}\n"
            else:
                response = f"❌ {result['message']}"
                
            # For adjustment, we don't need LLM, just return the static response
            # We can signal this by setting response directly and final_messages to None
            # For adjustment, we don't need LLM, just return the static response
            # We can signal this by setting response directly and final_messages to None
            # For adjustment, we don't need LLM, just return the static response
            # We can signal this by setting response directly and final_messages to None
            new_state = state.copy()
            new_state['response'] = response
            new_state['final_messages'] = None
            return new_state

        # Case 2: Retrieved Meal Data
        if state.get('retrieved_data'):
            user_profile = state['user_profile']
            
            from datetime import datetime
            current_date_str = datetime.now().strftime('%A, %B %d, %Y')
            
            system_prompt = f"""You are Meal Mind AI. The user asked about their meals and we retrieved this data:

TODAY'S DATE: {current_date_str}

{state['retrieved_data']}

USER PROFILE:
- Goal: {user_profile.get('health_goal', 'General Health')}
- Dietary Restrictions: {user_profile.get('dietary_restrictions', 'None')}
- Allergies: {user_profile.get('food_allergies', 'None')}

Generate a helpful, conversational response that:
1. Presents the meal information clearly
2. Relates it to their health goals
3. Offers any relevant tips or suggestions
4. Keep it concise and friendly
5. CRITICAL: STRICTLY respect the user's dietary restrictions and allergies. NEVER suggest foods they cannot eat.
"""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=state['user_input'])
            ]
            
            new_state = state.copy()
            new_state['final_messages'] = messages
            return new_state
        
        return state
    
    # ==================== CONDITIONAL EDGES ====================
    def should_retrieve_meals(self, state: ChatRouterState) -> str:
        """Determine next node based on route"""
        if state['route'] == 'meal_retrieval':
            return 'retrieve_meals'
        elif state['route'] == 'calorie_estimation':
            return 'estimate_calories'
        elif state['route'] == 'meal_adjustment':
            return 'adjust_meal'
        else:
            return 'general_chat'
    
    # ==================== BUILD GRAPH ====================
    def build_graph(self, thread_id: str = None):
        """Build the LangGraph workflow with memory integration"""
        from utils.checkpoint import SnowflakeCheckpointSaver
        
        workflow = StateGraph(ChatRouterState)
        
        # Add nodes
        workflow.add_node("load_preferences", self.node_load_preferences)
        workflow.add_node("extract_feedback", self.node_extract_feedback)
        workflow.add_node("route_query", self.node_route_query)
        workflow.add_node("retrieve_meals", self.node_retrieve_meals)
        workflow.add_node("estimate_calories", self.node_estimate_calories)
        workflow.add_node("adjust_meal", self.node_adjust_meal)
        workflow.add_node("monitor_changes", self.node_monitor_changes)
        workflow.add_node("general_chat", self.node_general_chat)
        workflow.add_node("generate_response", self.node_generate_response)
        
        # Add edges - Memory-aware workflow
        # OPTIMIZATION: load_preferences -> route_query (skip extraction for speed)
        workflow.set_entry_point("load_preferences")
        workflow.add_edge("load_preferences", "route_query")
        
        # Conditional routing after route_query
        workflow.add_conditional_edges(
            "route_query",
            self.should_retrieve_meals,
            {
                "retrieve_meals": "retrieve_meals",
                "estimate_calories": "estimate_calories",
                "adjust_meal": "adjust_meal",
                "general_chat": "general_chat"
            }
        )
        
        # Meal Adjustment Flow
        workflow.add_edge("adjust_meal", "monitor_changes")
        workflow.add_edge("monitor_changes", "generate_response")
        
        # Meal Retrieval Flow
        workflow.add_edge("retrieve_meals", "generate_response")
        
        # OPTIMIZATION: Run extraction AFTER response generation (Background)
        # All paths lead to extract_feedback before END
        workflow.add_edge("generate_response", "extract_feedback")
        workflow.add_edge("general_chat", "extract_feedback")
        workflow.add_edge("estimate_calories", "extract_feedback")
        
        workflow.add_edge("extract_feedback", END)
        
        # Initialize Checkpointer
        # Use MemorySaver for speed, we will handle persistence separately or optimize SnowflakeSaver later
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        
        return workflow.compile(checkpointer=checkpointer)
    
    # ==================== RUN METHODS ====================
    def run_chat(self, user_input: str, user_id: str, history: List[Any], context_data: Dict, thread_id: str = None) -> str:
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
            response="",
            adjustment_result=None,
            monitoring_warnings=None
        )
        
        app = self.build_graph(thread_id)
        
        config = {"configurable": {"thread_id": thread_id}} if thread_id else None
        
        result = app.invoke(initial_state, config=config)
        
        return result['response']
    
    def run_chat_stream(self, user_input: str, user_id: str, history: List[Any], context_data: Dict, user_preferences: Dict = None, thread_id: str = None):
        """Stream the chat response with status updates"""
        
        initial_state = ChatRouterState(
            user_input=user_input,
            user_id=user_id,
            user_profile=context_data.get('user_profile', {}),
            inventory_summary=context_data.get('inventory_summary', ''),
            meal_plan_summary=context_data.get('meal_plan_summary', ''),
            history=history,
            route=None,
            retrieved_data=None,
            user_preferences=user_preferences, # Pre-loaded preferences
            extracted_feedback=None,
            response="",
            adjustment_result=None,
            monitoring_warnings=None
        )
        
        app = self.build_graph(thread_id)
        
        config = {"configurable": {"thread_id": thread_id}} if thread_id else None
        
        # Stream execution steps
        final_response = ""
        response_yielded = False
        final_messages = None
        
        # 1. Run the Graph (Preprocessing Phase)
        # The graph will prepare the prompt/messages but NOT call the LLM
        for output in app.stream(initial_state, config=config):
            for key, value in output.items():
                
                # Check if we have prepared messages
                if value and 'final_messages' in value and value['final_messages']:
                    final_messages = value['final_messages']
                
                # Check if we have a static response (e.g. from adjustment)
                if 'response' in value and value['response']:
                    final_response = value['response']
                    yield final_response
                    response_yielded = True
                    
                # Yield status updates
                if not response_yielded:
                    if key == "load_preferences":
                        yield "__STATUS__: Loading your preferences..."
                    elif key == "extract_feedback":
                        yield "__STATUS__: Analyzing your input..."
                    elif key == "route_query":
                        route = value.get('route')
                        if route == 'meal_retrieval':
                            yield "__STATUS__: Searching your meal plan..."
                        elif route == 'calorie_estimation':
                            yield "__STATUS__: Analyzing food items..."
                        elif route == 'meal_adjustment':
                            yield "__STATUS__: Processing meal adjustment..."
                        else:
                            yield "__STATUS__: Thinking..."
                    elif key == "retrieve_meals":
                        yield "__STATUS__: Preparing response..."
                    elif key == "estimate_calories":
                        yield "__STATUS__: Preparing response..."
                    elif key == "adjust_meal":
                        yield "__STATUS__: Verifying health constraints..."
                    elif key == "monitor_changes":
                        yield "__STATUS__: Preparing response..."

        # 2. Stream the LLM Response (Streaming Phase)
        # If we have prepared messages and no response yet, stream the LLM
        if final_messages and not response_yielded:
            try:
                if self.chat_model:
                    for token in self.chat_model.stream(final_messages):
                        content = token.content
                        if content:
                            final_response += content
                            yield content
                            response_yielded = True
                else:
                    yield "I'm currently in offline mode."
                    final_response = "I'm currently in offline mode."
            except Exception as e:
                err_msg = f"Error generating response: {str(e)}"
                yield err_msg
                final_response = err_msg
        else:
            # Fallback if no messages and no response
            pass

        # 3. Fallback if no messages and no response
        if not response_yielded and not final_response:
            final_response = "I couldn't generate a response. Please try again."
            yield final_response
            
        # 4. Post-Processing (Update State/DB if needed)
        # We might want to update the graph state with the final response for memory
        # But since we handle persistence in the UI layer (views/chat.py), this is optional here.
        # However, if we want extract_feedback to work on the response, we might need to run it now.
        # But extract_feedback currently only uses user_input, so we are good.

