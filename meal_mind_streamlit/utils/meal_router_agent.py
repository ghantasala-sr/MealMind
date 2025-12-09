import streamlit as st
import warnings
from typing import Dict, TypedDict, Annotated, List, Union, Any, Optional, Literal
from langchain_community.chat_models import ChatSnowflakeCortex
from langchain.schema import SystemMessage, HumanMessage, AIMessage, BaseMessage
# Suppress the specific warning from ChatSnowflakeCortex about default parameters
warnings.filterwarnings("ignore", message=".*is not default parameter.*")
from langgraph.graph import StateGraph, END
import json
from datetime import datetime

# ==================== LANGGRAPH STATE ====================
class ChatRouterState(TypedDict):
    user_input: str
    user_id: str
    user_profile: Dict
    inventory_summary: str
    meal_plan_summary: str
    chat_history: List[BaseMessage]
    
    # Plan: List of steps to execute
    # Each step: {"action": "meal_adjustment"|"meal_retrieval"|"calorie_estimation"|"general_chat", "params": {...}}
    plan: List[Dict]
    current_step_index: int
    
    # Results
    retrieved_data: Optional[str]
    adjustment_result: Optional[Dict]
    estimation_result: Optional[Dict]
    final_messages: List[BaseMessage]
    monitoring_warnings: List[str]
    response: str # Final text response

# ==================== MULTI-AGENT ROUTER ====================
class MealRouterAgent:
    def __init__(self, session, conn):
        self.session = session
        self.conn = conn
        
        # Initialize LLM
        try:
            self.chat_model = ChatSnowflakeCortex(
                session=self.session,
                model="llama3.1-70b",
                cortex_search_service="MEAL_MIND"
            )
        except Exception as e:
            st.warning(f"Router LLM init failed: {e}")
            self.chat_model = None
            
        # Initialize Sub-Agents
        from utils.meal_adjustment_agent import MealAdjustmentAgent
        self.adjustment_agent = MealAdjustmentAgent(session, conn)
        
        from utils.monitoring_agent import MonitoringAgent
        self.monitoring_agent = MonitoringAgent(conn)
        
        from utils.feedback_agent import FeedbackAgent
        self.feedback_agent = FeedbackAgent(conn, session)

        # Build Graph
        workflow = StateGraph(ChatRouterState)
        
        # Add Nodes
        workflow.add_node("load_preferences", self.node_load_preferences)
        workflow.add_node("extract_feedback", self.node_extract_feedback)
        workflow.add_node("planner", self.node_planner)
        workflow.add_node("meal_retrieval", self.node_retrieve_meals)
        workflow.add_node("meal_adjustment", self.node_adjust_meal)
        workflow.add_node("calorie_estimation", self.node_estimate_calories)
        workflow.add_node("general_chat", self.node_general_chat)
        workflow.add_node("generate_response", self.node_generate_response)
        
        # Set Entry Point
        workflow.set_entry_point("load_preferences")
        
        # Edge: Load Prefs -> Planner
        workflow.add_edge("load_preferences", "planner")
        
        # Conditional Edges from Planner
        workflow.add_conditional_edges(
            "planner",
            self.decide_route,
            {
                "meal_retrieval": "meal_retrieval",
                "meal_adjustment": "meal_adjustment",
                "calorie_estimation": "calorie_estimation",
                "general_chat": "general_chat",
                "generate_response": "generate_response"
            }
        )
        
        # Edges from Action Nodes -> Back to Planner
        workflow.add_edge("meal_retrieval", "planner")
        workflow.add_edge("meal_adjustment", "planner")
        workflow.add_edge("calorie_estimation", "planner")
        workflow.add_edge("general_chat", "generate_response")
        
        # Response -> Feedback Extraction -> END
        workflow.add_edge("generate_response", "extract_feedback")
        workflow.add_edge("extract_feedback", END)
        
        # Compile
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        self.app = workflow.compile(checkpointer=checkpointer)

    # ==================== MEMORY NODES ====================
    def node_load_preferences(self, state: ChatRouterState) -> ChatRouterState:
        """Load user preferences from long-term memory"""
        # If already pre-loaded, skip DB call
        if state.get('user_preferences'):
            return state
            
        preferences = self.feedback_agent.get_user_preferences(state['user_id'])
        state['user_preferences'] = preferences
        return state

    def node_extract_feedback(self, state: ChatRouterState) -> ChatRouterState:
        """Extract preferences from user message"""
        # We can extract from user_input
        extracted = self.feedback_agent.extract_preferences(
            state['user_input'], 
            state['user_id']
        )
        # We don't necessarily need to store it in state unless we want to use it immediately
        # But the agent saves it to DB.
        return state

    # ==================== PLANNER NODE ====================
    def node_planner(self, state: ChatRouterState) -> ChatRouterState:
        """
        LLM-based Planner.
        If plan is empty, generates a plan.
        If plan exists, increments step index.
        """
        print("DEBUG: Entering node_planner")
        
        # If we already have a plan and we are just looping back
        if state.get('plan'):
            # If we are coming back from an action, we need to increment
            # But wait, how do we know if we just started or came back?
            # We can check if we have results for the current step?
            # Or simpler: The action nodes don't increment. Planner increments.
            # But Planner is the entry point.
            # Let's assume if plan is empty, we generate.
            # If plan is NOT empty, we increment.
            
            # BUT: On first run, plan is empty. We generate.
            # Then we return state. The graph goes to decide_route.
            # decide_route sends to Action.
            # Action sends back to Planner.
            # Now plan is NOT empty. We increment.
            
            # Problem: After generation, we are still in Planner. We shouldn't increment yet.
            # We should only increment if we are returning from an action.
            # We can use a flag or check if we have executed the current step.
            pass

        # Logic:
        # 1. If plan is empty: Generate Plan. Set index = 0.
        # 2. If plan is not empty: Increment index.
        
        if not state.get('plan'):
            # Generate Plan
            user_input = state['user_input']
            today = datetime.now().strftime('%A, %B %d, %Y')
            
            system_prompt = f"""You are the Orchestrator for Meal Mind AI.
            Today is {today}.
            
            Your goal is to break down the user's request into a list of executable actions.
            
            Available Actions:
            1. "meal_adjustment": Add, remove, replace, or report food.
               Params: "meal_type" (breakfast/lunch/dinner/snack), "date" (YYYY-MM-DD), "instruction" (what to do).
               
            2. "meal_retrieval": Show meal plan, get recipe, check ingredients.
               Params: "meal_type" (optional), "date" (YYYY-MM-DD).
               
            3. "calorie_estimation": Estimate calories for a generic food item (not in plan).
               Params: "query".
               
            4. "general_chat": Greetings, nutrition advice, questions not about the specific meal plan.
               Params: "query".
            
            RULES:
            - If the user asks to modify multiple meals (e.g. "Add coffee to breakfast and remove tea from lunch"), create TWO "meal_adjustment" steps.
            - If the user asks "What is for lunch and dinner?", create TWO "meal_retrieval" steps.
            - Always extract the DATE relative to {today}.
            - Return ONLY a JSON list of objects.
            """
            
            user_prompt = f"""User Request: "{user_input}"
            
            Output Format:
            [
                {{"action": "meal_adjustment", "params": {{"meal_type": "breakfast", "date": "2025-12-06", "instruction": "Add coffee"}}}},
                ...
            ]
            """
            
            try:
                response = self.chat_model.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt)
                ])
                content = response.content.strip()
                if "```" in content:
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                
                plan = json.loads(content.strip())
                if not isinstance(plan, list):
                    plan = [plan]
                    
                state['plan'] = plan
                state['current_step_index'] = 0
                print(f"DEBUG: Generated Plan: {json.dumps(plan, indent=2)}")
                
            except Exception as e:
                print(f"ERROR: Planner failed: {e}")
                state['plan'] = [{"action": "general_chat", "params": {"query": user_input}}]
                state['current_step_index'] = 0
        else:
            # We are looping back. Increment index.
            state['current_step_index'] += 1
            print(f"DEBUG: Incrementing step to {state['current_step_index']}")
        
        return state

    def decide_route(self, state: ChatRouterState) -> str:
        """Dispatch based on current step in plan"""
        plan = state.get('plan', [])
        idx = state.get('current_step_index', 0)
        
        if idx >= len(plan):
            return "generate_response"
            
        step = plan[idx]
        action = step.get('action')
        
        print(f"DEBUG: Dispatching to {action} (Step {idx+1}/{len(plan)})")
        
        if action in ["meal_adjustment", "meal_retrieval", "calorie_estimation", "general_chat"]:
            return action
            
        return "general_chat"

    # ==================== ACTION NODES ====================
    
    def node_adjust_meal(self, state: ChatRouterState) -> ChatRouterState:
        """Execute meal adjustment step"""
        idx = state['current_step_index']
        step = state['plan'][idx]
        params = step['params']
        
        user_id = state['user_id']
        date = params.get('date', datetime.now().strftime('%Y-%m-%d'))
        meal_type = params.get('meal_type', 'breakfast')
        instruction = params.get('instruction', state['user_input'])
        
        print(f"DEBUG: Adjusting {date} {meal_type}: {instruction}")
        
        result = self.adjustment_agent.process_request(instruction, user_id, date, meal_type)
        
        # Store result. For multi-step, we might want to append.
        # For now, let's append to a list in 'adjustment_result' or just overwrite?
        # The state expects Optional[Dict]. Let's overwrite but maybe append message?
        
        prev_result = state.get('adjustment_result')
        if prev_result:
            # Merge messages
            result['message'] = prev_result['message'] + "\n" + result['message']
            # Keep latest totals
        
        state['adjustment_result'] = result
        
        # Trigger monitoring
        warnings = self.monitoring_agent.monitor_changes(user_id, date)
        state['monitoring_warnings'] = warnings
        
        return state

    def node_retrieve_meals(self, state: ChatRouterState) -> ChatRouterState:
        """Retrieve meal data"""
        from utils.db import get_meals_by_criteria
        
        idx = state['current_step_index']
        step = state['plan'][idx]
        params = step['params']
        
        user_id = state['user_id']
        date = params.get('date')
        meal_type = params.get('meal_type')
        
        meals = get_meals_by_criteria(self.conn, user_id, day_number=None, meal_type=meal_type, meal_date=date)
        
        formatted = ""
        if meals:
            for m in meals:
                formatted += f"**{m['meal_type'].title()} ({m['meal_date']})**\n"
                formatted += f"{m['meal_name']}\n"
                formatted += f"Calories: {m['total_nutrition']['calories']} | Protein: {m['total_nutrition']['protein_g']}g\n"
                formatted += f"Ingredients: {', '.join([i['ingredient'] for i in m['ingredients_with_quantities']])}\n\n"
        else:
            formatted = f"No meals found for {meal_type} on {date}.\n"
            
        current_data = state.get('retrieved_data') or ""
        state['retrieved_data'] = current_data + formatted
        
        return state

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
        
        response = self.chat_model.invoke(messages)
        state['final_messages'] = [response]
        return state

    def node_general_chat(self, state: ChatRouterState) -> ChatRouterState:
        """Handle general conversation with full context"""
        idx = state['current_step_index']
        # If called from planner, use query param, else user_input
        if state.get('plan') and idx < len(state['plan']):
            step = state['plan'][idx]
            query = step['params'].get('query', state['user_input'])
        else:
            query = state['user_input']
        
        user_profile = state['user_profile']
        inventory = state.get('inventory_summary', '')
        meal_plan = state.get('meal_plan_summary', '')
        history = state.get('chat_history', [])
        preferences = state.get('user_preferences', {})
        
        # Format preferences for prompt
        pref_text = self.feedback_agent.format_preferences_for_prompt(preferences)
        
        from datetime import datetime
        current_date_str = datetime.now().strftime('%A, %B %d, %Y')
        
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
        recent_history = history[-5:]
        for msg in recent_history:
             messages.append(msg)
        
        # Add current query
        messages.append(HumanMessage(content=query))
        
        response = self.chat_model.invoke(messages)
        state['final_messages'] = [response]
        return state

    def node_generate_response(self, state: ChatRouterState) -> ChatRouterState:
        response_text = ""
        
        # 1. Adjustments
        if state.get('adjustment_result'):
            res = state['adjustment_result']
            response_text += f"{res['message']}\n\n"
            if 'new_daily_total' in res:
                totals = res['new_daily_total']
                response_text += "**New Daily Total:**\n"
                response_text += f"- Calories: {totals['calories']} kcal\n"
                response_text += f"- Protein: {totals['protein_g']}g\n"
                response_text += f"- Carbs: {totals['carbohydrates_g']}g\n"
                response_text += f"- Fat: {totals['fat_g']}g\n"
                response_text += f"- Fiber: {totals['fiber_g']}g\n"
            
            if state.get('monitoring_warnings'):
                response_text += "\n**Health Alerts:**\n"
                for w in state['monitoring_warnings']:
                    response_text += f"{w}\n"
                    
        # 2. Retrieval
        if state.get('retrieved_data'):
            response_text += "\n**Retrieved Meals:**\n" + state['retrieved_data']
            
        # 3. General Chat
        if state.get('final_messages'):
            response_text += "\n" + state['final_messages'][0].content
            
        if not response_text:
            response_text = "I processed your request."
            
        state['response'] = response_text
        return state

    # ==================== RUN METHODS ====================
    def run_chat_stream(self, user_input: str, user_id: str, history: List[Any], context_data: Dict, user_preferences: Dict = None, thread_id: str = None):
        """Stream the chat response with status updates"""
        
        initial_state = {
            "user_input": user_input,
            "user_id": user_id,
            "user_profile": context_data.get('user_profile', {}),
            "inventory_summary": context_data.get('inventory_summary', ''),
            "meal_plan_summary": context_data.get('meal_plan_summary', ''),
            "chat_history": history,
            "plan": [],
            "current_step_index": 0,
            "retrieved_data": None,
            "adjustment_result": None,
            "estimation_result": None,
            "final_messages": [],
            "monitoring_warnings": [],
            "response": ""
        }
        
        config = {"configurable": {"thread_id": thread_id}} if thread_id else None
        
        final_response = ""
        
        for output in self.app.stream(initial_state, config=config):
            for key, value in output.items():
                if key == "load_preferences":
                    yield "__STATUS__: Loading your preferences..."
                elif key == "extract_feedback":
                    yield "__STATUS__: Learning from your feedback..."
                elif key == "planner":
                    yield "__STATUS__: Planning actions..."
                elif key == "meal_adjustment":
                    yield "__STATUS__: Adjusting meal..."
                elif key == "meal_retrieval":
                    yield "__STATUS__: Retrieving data..."
                elif key == "generate_response":
                    if value.get('response'):
                        final_response = value['response']
                        yield final_response
                        
        if not final_response:
             yield "I completed the task but have no output."
