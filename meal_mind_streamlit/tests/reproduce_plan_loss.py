import sys
import os
import json
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage, HumanMessage

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.meal_router_agent import MealRouterAgent, ChatRouterState

def reproduce_plan_loss():
    print("\n" + "="*50)
    print("REPRODUCING PLAN LOSS")
    print("="*50)
    
    # Mock LLM
    mock_llm = MagicMock()
    
    # Setup Agent
    class DummyAgent(MealRouterAgent):
        def __init__(self):
            self.chat_model = mock_llm
            self.feedback_agent = MagicMock()
            
    agent = DummyAgent()
    
    # Initial State
    state = ChatRouterState(
        user_input="okra onion curry",
        user_id="test",
        user_profile={},
        inventory_summary="",
        meal_plan_summary="",
        chat_history=[],
        plan=[],
        current_step_index=0,
        retrieved_data=None,
        adjustment_result=None,
        estimation_result=None,
        recipe_result=None,
        final_messages=[],
        monitoring_warnings=[],
        response="",
        tool_calls=[],
        tool_outputs=[],
        active_node=""
    )
    
    # 1. Run Planner
    print("\n--- Step 1: Planner ---")
    # Mock planner response
    mock_llm.invoke.return_value = AIMessage(content='[{"action": "calorie_estimation", "params": {"query": "okra onion curry"}}]')
    
    state = agent.node_planner(state)
    print(f"Plan after Planner: {json.dumps(state.get('plan'), indent=2)}")
    
    if not state.get('plan'):
        print("FAIL: Planner did not set plan")
        return

    # 2. Run Calorie Estimation (Generate Tools)
    print("\n--- Step 2: Calorie Estimation (Tools) ---")
    # Mock tool generation
    mock_llm.invoke.return_value = AIMessage(content='{"tool": "search_foods", "query": "okra"}')
    
    state = agent.node_estimate_calories(state)
    print(f"Plan after Est (Tools): {json.dumps(state.get('plan'), indent=2)}")
    print(f"Tool Calls: {state.get('tool_calls')}")
    
    if not state.get('plan'):
        print("FAIL: Plan lost in Calorie Estimation (Tools)")
        return

    # 3. Run Execute Tools
    print("\n--- Step 3: Execute Tools ---")
    # Mock retrieve_context
    agent._retrieve_context = MagicMock(return_value="Okra info")
    
    state = agent.node_execute_tools(state)
    print(f"Plan after Execute Tools: {json.dumps(state.get('plan'), indent=2)}")
    print(f"Tool Outputs: {state.get('tool_outputs')}")
    
    if not state.get('plan'):
        print("FAIL: Plan lost in Execute Tools")
        return

    # 4. Run Calorie Estimation (Final Answer)
    print("\n--- Step 4: Calorie Estimation (Final) ---")
    # Mock final answer
    mock_llm.invoke.return_value = AIMessage(content="Okra curry has 200 kcal.")
    
    state = agent.node_estimate_calories(state)
    print(f"Plan after Est (Final): {json.dumps(state.get('plan'), indent=2)}")
    print(f"Final Messages: {state.get('final_messages')}")
    
    if not state.get('plan'):
        print("FAIL: Plan lost in Calorie Estimation (Final)")
        return
        
    print("\nSUCCESS: Plan persisted through the flow.")

if __name__ == "__main__":
    reproduce_plan_loss()
