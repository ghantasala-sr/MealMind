import streamlit as st
from typing import Dict, Any, List, TypedDict, Optional
from langchain_community.chat_models import ChatSnowflakeCortex
from langchain.schema import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END
import json
import os
import re
from utils.mcp_client import MealMindMCPClient

# ==================== LANGGRAPH STATE ====================
class ChatState(TypedDict):
    messages: List[BaseMessage]
    user_profile: Dict
    inventory_summary: str
    meal_plan_summary: str
    context: str
    tool_calls: List[Dict] # To track pending tool calls
    tool_outputs: List[Dict] # To track tool results

# ==================== CHAT AGENT ====================
class ChatAgent:
    """Agent for handling user chat interactions about meal plans and inventory"""

    def __init__(self, session):
        self.session = session
        try:
            # Initialize Cortex Chat Model
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
                    print("DEBUG: Missing credentials for MCP client in ChatAgent")
                    self.mcp_client = None
            except Exception as e:
                print(f"DEBUG: Failed to init MCP client in ChatAgent: {e}")
                self.mcp_client = None
                
        except Exception as e:
            st.warning(f"Chat Agent initialization failed: {e}")
            self.chat_model = None

    def _retrieve_context(self, query: str) -> str:
        """Retrieve relevant context using MCP"""
        if not self.mcp_client:
            return "Error: MCP Client not available."
            
        try:
            # Request specific columns for better context
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
                            if "FOOD_NAME" in record: parts.append(f"Food: {record['FOOD_NAME']}")
                            nutrients = []
                            if "ENERGY_KCAL" in record: nutrients.append(f"{record['ENERGY_KCAL']} kcal")
                            if "PROTEIN_G" in record: nutrients.append(f"P: {record['PROTEIN_G']}g")
                            if "CARBOHYDRATE_G" in record: nutrients.append(f"C: {record['CARBOHYDRATE_G']}g")
                            if "TOTAL_FAT_G" in record: nutrients.append(f"F: {record['TOTAL_FAT_G']}g")
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

    def get_system_prompt(self, state: ChatState) -> str:
        """Construct the system prompt with context"""
        profile = state.get('user_profile', {})
        inventory = state.get('inventory_summary', 'No inventory data available.')
        meal_plan = state.get('meal_plan_summary', 'No meal plan generated yet.')
        
        from datetime import datetime
        current_date_str = datetime.now().strftime('%A, %B %d, %Y')

        system_prompt = f"""
        You are Meal Mind AI, a helpful nutrition and meal planning assistant.
        
        TODAY'S DATE: {current_date_str}
        
        USER PROFILE:
        - Name: {profile.get('username', 'User')}
        - Goal: {profile.get('health_goal', 'General Health')}
        - Dietary Restrictions: {profile.get('dietary_restrictions', 'None')}
        - Allergies: {profile.get('food_allergies', 'None')}
        
        CURRENT INVENTORY SUMMARY:
        {inventory}
        
        CURRENT MEAL PLAN SUMMARY:
        {meal_plan}
        
        TOOLS AVAILABLE:
        1. search_foods(query: str): Search for nutritional information about specific foods. Use this when you need to know calories, macros, or ingredients for a food item that is not in the context.
        
        INSTRUCTIONS:
        - If you need to search for food data to answer the user's question, output a JSON object with the tool call.
        - FORMAT: {{"tool": "search_foods", "query": "apple pie"}}
        - Do NOT output anything else if you are calling a tool.
        - If you have enough information, answer the user directly.
        - HANDLING SEARCH RESULTS:
          - If multiple variations are returned (e.g., raw, boiled, fried), choose the most relevant one based on the user's description.
          - If the user didn't specify preparation, present the most common form (e.g., "cooked" or "raw") or briefly summarize the options (e.g., "Raw: 33 kcal, Cooked: 59 kcal").
          - If the user didn't specify preparation, present the most common form (e.g., "cooked" or "raw") or briefly summarize the options (e.g., "Raw: 33 kcal, Cooked: 59 kcal").
          - Do NOT simply list the raw database records. Synthesize the information into a helpful response.
        - FINAL OUTPUT FORMAT:
          - Do NOT mention "search_foods", "tools", "database", or "I used a tool" in your final response.
          - Present the information naturally as if you already knew it.
        - If the user asks about their meal plan or inventory, use the provided summaries.
        - Be encouraging and supportive.
        """
        return system_prompt

    def node_process_message(self, state: ChatState) -> ChatState:
        """Process the user message and generate a response"""
        messages = state['messages']
        system_prompt = self.get_system_prompt(state)
        
        # Add tool outputs to history if any
        tool_outputs = state.get('tool_outputs', [])
        history_with_tools = list(messages)
        
        if tool_outputs:
            for output in tool_outputs:
                history_with_tools.append(AIMessage(content=f"Tool Output: {output['result']}"))
        
        # Prepare messages for the model
        formatted_messages = [SystemMessage(content=system_prompt)] + history_with_tools
        
        try:
            if self.chat_model:
                response = self.chat_model.invoke(formatted_messages)
                content = response.content.strip()
                
                # Check for tool calls (support multiple)
                found_tools = []
                try:
                    candidates = re.finditer(r'\{[^{}]*\}', content)
                    for match in candidates:
                        try:
                            tool_call = json.loads(match.group(0))
                            if tool_call.get("tool") == "search_foods":
                                print(f"\n*** TOOL CALL DETECTED: {tool_call} ***\n")
                                found_tools.append(tool_call)
                        except:
                            pass
                except:
                    pass
                    
                if found_tools:
                    return {"tool_calls": found_tools}
                
                # If no valid tool call, return response
                return {"messages": [response], "tool_calls": []} 
            else:
                return {"messages": [AIMessage(content="I'm sorry, I'm currently offline. Please check your connection.")], "tool_calls": []}
        except Exception as e:
            return {"messages": [AIMessage(content=f"I encountered an error: {str(e)}")], "tool_calls": []}

    def node_execute_tools(self, state: ChatState) -> ChatState:
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
                
                print(f"\n*** EXECUTING TOOL: search_foods('{query}') ***\n")
                result = self._retrieve_context(query)
                outputs.append({"tool": "search_foods", "query": query, "result": result})
                executed_queries.add(('search_foods', query))
                
        # Append to existing outputs
        state['tool_outputs'] = current_outputs + outputs
        state['tool_calls'] = []
        return state

    def decide_next_step(self, state: ChatState) -> str:
        """Decide whether to execute tools or end"""
        if state.get('tool_calls'):
            return "execute_tools"
        return END

    def build_graph(self):
        """Build the LangGraph workflow for chat"""
        workflow = StateGraph(ChatState)
        
        # Add nodes
        workflow.add_node("process_message", self.node_process_message)
        workflow.add_node("execute_tools", self.node_execute_tools)
        
        # Add edges
        workflow.set_entry_point("process_message")
        
        workflow.add_conditional_edges(
            "process_message",
            self.decide_next_step,
            {
                "execute_tools": "execute_tools",
                END: END
            }
        )
        
        workflow.add_edge("execute_tools", "process_message")
        
        return workflow.compile()

    def run_chat(self, user_input: str, history: List[Any], context_data: Dict) -> str:
        """Main entry point to run the chat"""
        
        # Prepare initial state
        initial_state = {
            "messages": history + [HumanMessage(content=user_input)],
            "user_profile": context_data.get('user_profile', {}),
            "inventory_summary": context_data.get('inventory_summary', ''),
            "meal_plan_summary": context_data.get('meal_plan_summary', ''),
            "context": "",
            "tool_calls": [],
            "tool_outputs": []
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

