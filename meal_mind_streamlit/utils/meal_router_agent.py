import streamlit as st
import warnings
from typing import Dict, TypedDict, Annotated, List, Union, Any, Optional, Literal
from langchain_community.chat_models import ChatSnowflakeCortex
from langchain.schema import SystemMessage, HumanMessage, AIMessage, BaseMessage
# Suppress the specific warning from ChatSnowflakeCortex about default parameters
warnings.filterwarnings("ignore", message=".*is not default parameter.*")
from langgraph.graph import StateGraph, END
import json
import os
import re
from datetime import datetime
from utils.mcp_client import MealMindMCPClient

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
    recipe_result: Optional[str]
    final_messages: List[BaseMessage]
    monitoring_warnings: List[str]
    response: str # Final text response
    
    # Tool Tracking
    tool_calls: List[Dict]
    tool_outputs: List[Dict]
    active_node: str # To know where to return after tool execution

# ==================== MULTI-AGENT ROUTER ====================
class MealRouterAgent:
    def __init__(self, session, conn):
        self.session = session
        self.conn = conn
        
        # Initialize LLM
        try:
            self.chat_model = ChatSnowflakeCortex(
                session=self.session,
                model="openai-gpt-4.1"
            )
            
            # Initialize MCP Client for Context Retrieval
            try:
                account = os.getenv("SNOWFLAKE_ACCOUNT")
                db = os.getenv("SNOWFLAKE_DATABASE")
                schema = os.getenv("SNOWFLAKE_SCHEMA")
                token = self.session.connection.rest.token
                
                if all([account, token, db, schema]):
                    self.mcp_client = MealMindMCPClient(account, token, db, schema)
                else:
                    print("DEBUG: Missing credentials for MCP client in MealRouterAgent")
                    self.mcp_client = None
            except Exception as e:
                print(f"DEBUG: Failed to init MCP client in MealRouterAgent: {e}")
                self.mcp_client = None
                
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

        from utils.recipe_agent import RecipeAgent
        self.recipe_agent = RecipeAgent(session)

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
        workflow.add_node("execute_tools", self.node_execute_tools)
        workflow.add_node("recipe_lookup", self.node_provide_recipe)
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
                "recipe_lookup": "recipe_lookup",
                "generate_response": "generate_response"
            }
        )
        
        # Conditional Edges from Action Nodes (for Tool Use)
        workflow.add_conditional_edges(
            "calorie_estimation",
            self.decide_next_step_after_action,
            {
                "execute_tools": "execute_tools",
                "planner": "planner"
            }
        )
        
        workflow.add_conditional_edges(
            "general_chat",
            self.decide_next_step_after_action,
            {
                "execute_tools": "execute_tools",
                "generate_response": "generate_response"
            }
        )
        
        # Tool Execution -> Return to Active Node
        workflow.add_conditional_edges(
            "execute_tools",
            self.return_from_tools,
            {
                "calorie_estimation": "calorie_estimation",
                "general_chat": "general_chat"
            }
        )
        
        # Edges from other Action Nodes -> Back to Planner
        workflow.add_edge("meal_retrieval", "planner")
        workflow.add_edge("meal_adjustment", "planner")
        workflow.add_edge("recipe_lookup", "planner")
        
        # Response -> Feedback Extraction -> END
        workflow.add_edge("generate_response", "extract_feedback")
        workflow.add_edge("extract_feedback", END)
        
        # Compile
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        self.app = workflow.compile(checkpointer=checkpointer)

    def _retrieve_context(self, query: str) -> str:
        """Retrieve relevant food data using MCP"""
        if not self.mcp_client:
            return "Error: MCP Client not available."
            
        try:
            # Request specific columns
            columns = [
                "FOOD_NAME", "ENERGY_KCAL", "PROTEIN_G", "CARBOHYDRATE_G", 
                "TOTAL_FAT_G", "FIBER_TOTAL_G", "PRIMARY_INGREDIENT"
            ]
            
            response = self.mcp_client.search_foods(query, columns=columns, limit=5)
            
            if "error" in response:
                return f"Error retrieving data: {response['error']}"
                
            result_content = response.get("result", {}).get("content", [])
            context_parts = []
            
            for item in result_content:
                if item.get("type") == "text":
                    text = item.get("text")
                    try:
                        data = json.loads(text)
                        
                        def format_record(record):
                            if isinstance(record, str): return record
                            parts = []
                            if "FOOD_NAME" in record: parts.append(f"Item: {record['FOOD_NAME']}")
                            nutrients = []
                            if "ENERGY_KCAL" in record: nutrients.append(f"Calories: {record['ENERGY_KCAL']}")
                            if "PROTEIN_G" in record: nutrients.append(f"Protein: {record['PROTEIN_G']}g")
                            if "CARBOHYDRATE_G" in record: nutrients.append(f"Carbs: {record['CARBOHYDRATE_G']}g")
                            if "TOTAL_FAT_G" in record: nutrients.append(f"Fat: {record['TOTAL_FAT_G']}g")
                            if nutrients: parts.append(" | ".join(nutrients))
                            return "\n".join(parts)

                        if isinstance(data, list):
                            for chunk in data: context_parts.append(format_record(chunk))
                        elif isinstance(data, dict):
                             context_parts.append(format_record(data))
                        else:
                            context_parts.append(str(data))
                    except:
                        context_parts.append(text)
                        
            return "\n\n".join(context_parts) if context_parts else "No matching foods found."
        except Exception as e:
            return f"Error executing search: {str(e)}"

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
        return state

    # ==================== PLANNER NODE ====================
    def node_planner(self, state: ChatRouterState) -> ChatRouterState:
        """
        LLM-based Planner.
        """
        print("DEBUG: Entering node_planner")
        
        if not state.get('plan'):
            # RESET TRANSIENT STATE
            # This ensures that results from previous turns (like recipes) don't persist
            # into unrelated new requests.
            state['recipe_result'] = None
            state['adjustment_result'] = None
            state['estimation_result'] = None
            state['retrieved_data'] = None
            state['tool_calls'] = []
            state['tool_outputs'] = []

            
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
               
            3. "calorie_estimation": Estimate calories/nutrition for a food item (not in plan).
               Params: "query" (the food name).
               - Use this when user asks "nutrition for X", "calories in X", or "breakdown of X".
               - If user says "nutrition for it", RESOLVE "it" from history.
               
            4. "general_chat": Greetings, nutrition advice, questions not about the specific meal plan.
               Params: "query".
            
            5. "recipe_lookup": If the user asks for a recipe, ingredients, how to cook something, OR "what can I cook with my ingredients".
               Params: "query" (the dish name or the user's question).
            
            RULES:
            - If the user asks to modify multiple meals (e.g. "Add coffee to breakfast and remove tea from lunch"), create TWO "meal_adjustment" steps.
            - If the user refers to "this", "that", "it", or "the recipe" (e.g., "add this to dinner"), you MUST resolve what they are referring to from the CHAT HISTORY.
              - Example: If the previous message was about "Oatmeal", and user says "add this", the instruction should be "Add Oatmeal".
              - Do NOT pass ambiguous instructions like "add this" or "add the item".
            - DISTINGUISH BETWEEN HYPOTHETICALS AND ACTIONS:
              - "How about adding garlic?", "What if I add cheese?", "Can I add nuts?" -> Use "general_chat" or "calorie_estimation" to discuss the change.
              - "Add garlic to my lunch", "Update lunch with garlic", "I ate garlic" -> CHECK FOR CONFIRMATION.
            - HANDLING PREFERENCES:
              - If the user states a preference (e.g., "I like mushrooms", "I hate onions", "I prefer spicy food"), DO NOT generate a "meal_adjustment".
              - Use "general_chat" to acknowledge the preference. The system will automatically learn it for future plans.
              - Do NOT ask if they want to update the current plan unless they explicitly asked to "add" or "use" it now.
            - CONFIRMATION RULE (STRICT):
              - Before generating a "meal_adjustment" action, check the CHAT HISTORY.
              - If the user has NOT explicitly confirmed (e.g., "Yes", "Do it", "Confirm") in the last message, you MUST output a "general_chat" action with the query: "Please ask the user to confirm if they want to update their [meal]."
              - ONLY generate "meal_adjustment" if the user has confirmed.
            - For "meal_adjustment", the `instruction` parameter must be specific (e.g., "Add 2 slices of pizza", "Replace lunch with Chicken Salad").
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
                # Prepare messages with history
                messages = [SystemMessage(content=system_prompt)]
                
                # Add recent history (last 5 messages) for context resolution
                history = state.get('chat_history', [])
                recent_history = history[-5:]
                for msg in recent_history:
                    messages.append(msg)
                    
                messages.append(HumanMessage(content=user_prompt))
                
                response = self.chat_model.invoke(messages)
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
        
        if action in ["meal_adjustment", "meal_retrieval", "calorie_estimation", "general_chat", "recipe_lookup"]:
            return action
            
        return "general_chat"

    def decide_next_step_after_action(self, state: ChatRouterState) -> str:
        """Decide whether to execute tools or continue"""
        if state.get('tool_calls'):
            return "execute_tools"
        
        # If no tools, where do we go?
        # calorie_estimation -> planner (to next step)
        # general_chat -> generate_response (usually last step)
        
        # We need to know which node we came from, but LangGraph doesn't pass that easily.
        # However, we can infer from the current action in plan.
        
        plan = state.get('plan', [])
        idx = state.get('current_step_index', 0)
        if idx < len(plan):
            action = plan[idx]['action']
            if action == 'calorie_estimation':
                return "planner"
            elif action == 'general_chat':
                return "generate_response"
            elif action == 'recipe_lookup':
                return "generate_response"
        
        return "generate_response"

    def return_from_tools(self, state: ChatRouterState) -> str:
        """Return to the active node after tool execution"""
        active = state.get('active_node')
        if active:
            return active
        return 'general_chat'

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
        
        # Get recipe context if available
        recipe_context = state.get('recipe_result')
        
        result = self.adjustment_agent.process_request(instruction, user_id, date, meal_type, recipe_context)
        
        prev_result = state.get('adjustment_result')
        if prev_result:
            result['message'] = prev_result['message'] + "\n" + result['message']
        
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
                formatted += f"Calories: {m['nutrition']['calories']} | Protein: {m['nutrition']['protein_g']}g\n"
                formatted += f"Ingredients: {', '.join([i['ingredient'] for i in m['ingredients_with_quantities']])}\n\n"
        else:
            formatted = f"No meals found for {meal_type} on {date}.\n"
            
        current_data = state.get('retrieved_data') or ""
        state['retrieved_data'] = current_data + formatted
        
        return state

    def node_provide_recipe(self, state: ChatRouterState) -> ChatRouterState:
        """Execute recipe lookup step"""
        idx = state['current_step_index']
        step = state['plan'][idx]
        params = step['params']
        query = params.get('query')
        
        print(f"DEBUG: Generating recipe for: {query}")
        
        recipe_text = self.recipe_agent.generate_recipe(
            query, 
            state.get('user_preferences'),
            state.get('inventory_summary')
        )
        
        state['recipe_result'] = recipe_text
        return state

    def node_estimate_calories(self, state: ChatRouterState) -> ChatRouterState:
        """Prepare messages for calorie estimation"""
        state['active_node'] = 'calorie_estimation'
        
        # Clear unrelated state to prevent pollution
        state['recipe_result'] = None
        state['adjustment_result'] = None
        state['retrieved_data'] = None
        
        # Get resolved query from planner if available
        idx = state.get('current_step_index', 0)
        plan = state.get('plan', [])
        query_input = state['user_input']
        
        if idx < len(plan):
            step = plan[idx]
            if step['action'] == 'calorie_estimation':
                query_input = step['params'].get('query', state['user_input'])
        
        print(f"DEBUG: node_estimate_calories - Query: '{query_input}'")
        
        system_prompt = f"""You are an expert nutritionist and calorie estimator. 
The user will describe a meal (e.g., from a buffet, restaurant, or home cooking).

TOOLS AVAILABLE:
1. search_foods(query: str): Search for nutritional information about specific foods. Use this when you need to know calories, macros, or ingredients for a food item that is not in the context.

INSTRUCTIONS:
- Use the `search_foods` tool to retrieve nutritional information. Without Exception use this, At maximum, you can use this tool 20 times.
- IF you have already received tool outputs containing the necessary information, DO NOT call the tool again. Proceed to generate the final response.
- **COMPOSITE DISHES (e.g., "Paneer Burji", "Chicken Sandwich"):**
  - Do NOT just search for the full dish name.
  - BREAK IT DOWN into main ingredients.
  - Call `search_foods` for EACH main ingredient separately.
  - Example: For "Paneer Burji", search for "paneer", "onion", "tomato", "ghee".
  - Example: For "Chicken Sandwich", search for "bread", "chicken breast", "lettuce", "mayonnaise".
- **SIMPLE FOODS (e.g., "Apple", "Egg"):**
  - Search for the item directly.
- FORMAT: {{"tool": "search_foods", "query": "ingredient_name"}}
- You can output MULTIPLE tool calls in one response.
- Do NOT output any text before the tool calls.
- Do NOT output anything else if you are calling tools.

- HANDLING SEARCH RESULTS:
  - Aggregate the nutrition from the ingredients to estimate the total for the dish.
  - If multiple variations are returned, choose the most relevant one.
  - Synthesize the information into a helpful response.

- FINAL OUTPUT FORMAT:
  - Do NOT mention "search_foods", "tools", "database", or "I used a tool" in your final response.
  - Present the information naturally as if you already knew it.
  - Show the breakdown of ingredients if applicable.
- Analyze the food items described.
- Estimate portion sizes if not specified.
- Calculate the approximate Calories and Macronutrients.
- Provide a clear breakdown.
- Offer a brief, non-judgmental health tip.

Format the output using Markdown:
- Use bold for totals.
- Use a list for the breakdown.
"""
        
        # Add tool outputs to history
        tool_outputs = state.get('tool_outputs', [])
        messages = [SystemMessage(content=system_prompt)]
        

                
        if tool_outputs:
            for output in tool_outputs:
                messages.append(AIMessage(content=f"Tool Output: {output['result']}"))
                
        messages.append(HumanMessage(content=query_input))
        
        response = self.chat_model.invoke(messages)
        content = response.content.strip()
        
        # Check for tool calls (support multiple)
        found_tools = []
        try:
            candidates = re.finditer(r'\{[^{}]*\}', content)
            for match in candidates:
                try:
                    tool_call = json.loads(match.group(0))
                    if tool_call.get("tool") == "search_foods":
                        found_tools.append(tool_call)
                except:
                    pass
        except:
            pass
            
        if found_tools:
            state['tool_calls'] = found_tools
            return state
                
        state['tool_calls'] = []
        state['final_messages'] = [response]
        return state

    def node_general_chat(self, state: ChatRouterState) -> ChatRouterState:
        """Handle general conversation with full context"""
        state['active_node'] = 'general_chat'
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
- Age: {user_profile.get('age', 'N/A')}
- Gender: {user_profile.get('gender', 'N/A')}
- Goal: {user_profile.get('health_goal', 'General Health')}
- Dietary Restrictions: {user_profile.get('dietary_restrictions', 'None')}
- Allergies: {user_profile.get('food_allergies', 'None')}

DAILY NUTRITIONAL TARGETS (DRI):
- Calories: {user_profile.get('daily_calories', 'N/A')} kcal
- Protein: {user_profile.get('daily_protein', 'N/A')}g
- Carbs: {user_profile.get('daily_carbohydrate', 'N/A')}g
- Fat: {user_profile.get('daily_fat', 'N/A')}g
- Fiber: {user_profile.get('daily_fiber', 'N/A')}g

USER PREFERENCES (LEARNED):
{pref_text}

CURRENT INVENTORY:
{inventory[:500]}...

MEAL PLAN SUMMARY:
{meal_plan[:300]}...

TOOLS AVAILABLE:
1. search_foods(query: str): Search for nutritional information about specific foods. Use this when you need to know calories, macros, or ingredients for a food item that is not in the context.

INSTRUCTIONS:
- Use the `search_foods` tool to verify nutritional claims or get specific data from the database.
- FORMAT: {{"tool": "search_foods", "query": "apple pie"}}
- Do NOT output anything else if you are calling a tool.
- If you have enough information (or after tool use), answer the user directly.
- HANDLING SEARCH RESULTS:
  - If multiple variations are returned (e.g., raw, boiled, fried), choose the most relevant one based on the user's description.
  - If the user didn't specify preparation, present the most common form (e.g., "cooked" or "raw") or briefly summarize the options (e.g., "Raw: 33 kcal, Cooked: 59 kcal").
  - Do NOT simply list the raw database records. Synthesize the information into a helpful response.
- FINAL OUTPUT FORMAT:
  - Do NOT mention "search_foods", "tools", "database", or "I used a tool" in your final response.
  - Present the information naturally as if you already knew it.
- Provide nutrition advice and cooking tips considering user preferences
- Answer health and wellness questions
- Be encouraging and supportive
- Keep responses concise and helpful
- IMPORTANT: Respect user dislikes and preferences in your suggestions
"""
        
        # Prepare messages
        messages = [SystemMessage(content=system_prompt)]
        
        # Add history (last 5 messages)
        recent_history = history[-5:]
        for msg in recent_history:
             messages.append(msg)
             
        # Add tool outputs
        tool_outputs = state.get('tool_outputs', [])
        if tool_outputs:
            for output in tool_outputs:
                messages.append(AIMessage(content=f"Tool Output: {output['result']}"))
        
        # Add current query
        messages.append(HumanMessage(content=query))
        
        response = self.chat_model.invoke(messages)
        content = response.content.strip()
        
        # Check for tool calls (support multiple)
        found_tools = []
        try:
            candidates = re.finditer(r'\{[^{}]*\}', content)
            for match in candidates:
                try:
                    tool_call = json.loads(match.group(0))
                    if tool_call.get("tool") == "search_foods":
                        print(f"\n*** TOOL CALL DETECTED (General Chat): {tool_call} ***\n")
                        found_tools.append(tool_call)
                except:
                    pass
        except:
            pass
            
        if found_tools:
            state['tool_calls'] = found_tools
            return state
            
        state['tool_calls'] = []
        state['final_messages'] = [response]
        return state

    def node_execute_tools(self, state: ChatRouterState) -> ChatRouterState:
        """Execute pending tool calls"""
        tool_calls = state.get('tool_calls', [])
        current_outputs = state.get('tool_outputs', [])
        outputs = []
        
        # Create a set of already executed queries to prevent loops
        executed_queries = {
            (out['tool'], out['query']) for out in current_outputs
        }
        
        for call in tool_calls:
            if call['tool'] == 'search_foods':
                query = call['query']
                
                # Check for duplicates
                if ('search_foods', query) in executed_queries:
                    print(f"\n*** SKIPPING DUPLICATE TOOL CALL: search_foods('{query}') ***\n")
                    outputs.append({
                        "tool": "search_foods", 
                        "query": query, 
                        "result": f"System: You have already searched for '{query}'. Do not search for it again. If no results were found, assume the data is missing."
                    })
                    continue
                
                print(f"DEBUG: Executing search_foods for query: '{query}'")
                print(f"\n*** EXECUTING TOOL: search_foods('{query}') ***\n")
                result = self._retrieve_context(query)
                print(f"DEBUG: search_foods result length: {len(result)}")
                outputs.append({"tool": "search_foods", "query": query, "result": result})
                executed_queries.add(('search_foods', query))
        
        # Append to existing outputs if we are looping
        state['tool_outputs'] = current_outputs + outputs
        state['tool_calls'] = [] # Clear calls
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
            
        # 3. Recipe
        if state.get('recipe_result'):
            response_text += "\n" + state['recipe_result']

        # 4. General Chat
        if state.get('final_messages'):
            response_text += "\n" + state['final_messages'][0].content
            
            # If this was a calorie estimation (which uses general_chat node logic but sets active_node),
            # we might want to ask if they want to add it.
            # But wait, calorie_estimation uses `node_estimate_calories` which calls LLM.
            # The result of `node_estimate_calories` is in `final_messages` because it uses `chat_model.invoke`.
            
            if state.get('active_node') == 'calorie_estimation':
                 response_text += "\n\nWould you like to add this to your meal plan? If so, please confirm."

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
            "response": "",
            "tool_calls": [],
            "tool_outputs": [],
            "active_node": ""
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
                elif key == "execute_tools":
                    yield "__STATUS__: Searching database..."
                elif key == "generate_response":
                    if value.get('response'):
                        final_response = value['response']
                        yield final_response
                        
        if not final_response:
             yield "I completed the task but have no output."
