import sys
import os
import json
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.meal_router_agent import MealRouterAgent, ChatRouterState

def verify_planner_loop_fix():
    print("\n" + "="*50)
    print("VERIFYING PLANNER LOOP FIX")
    print("="*50)
    
    # Setup Agent
    agent = MealRouterAgent(None, None)
    
    # Scenario:
    # 1. Plan was lost (empty).
    # 2. But we have 'final_messages' from a previous step (indicating we just finished work).
    # 3. node_planner should NOT re-generate plan. It should return state as is.
    
    state = ChatRouterState(
        user_input="okra onion curry",
        user_id="test",
        user_profile={},
        inventory_summary="",
        meal_plan_summary="",
        chat_history=[],
        plan=[], # LOST PLAN
        current_step_index=0,
        retrieved_data=None,
        adjustment_result=None,
        estimation_result=None,
        recipe_result=None,
        final_messages=[AIMessage(content="Okra curry is 200 kcal.")], # WORK DONE
        monitoring_warnings=[],
        response="",
        tool_calls=[],
        tool_outputs=[],
        active_node=""
    )
    
    print("Running node_planner with LOST PLAN but EXISTING RESULTS...")
    new_state = agent.node_planner(state)
    
    # Check if plan was re-generated
    if new_state.get('plan'):
        print(f"FAIL: Planner re-generated plan: {new_state.get('plan')}")
    else:
        print("SUCCESS: Planner did NOT re-generate plan.")
        
    # Check if results were preserved
    if new_state.get('final_messages'):
        print("SUCCESS: Results preserved.")
    else:
        print("FAIL: Results were cleared.")

    # Check routing
    # If plan is empty, decide_route should go to generate_response
    route = agent.decide_route(new_state)
    print(f"Route: {route}")
    
    if route == "generate_response":
        print("SUCCESS: Routing to generate_response.")
    else:
        print(f"FAIL: Routing to {route}")

if __name__ == "__main__":
    verify_planner_loop_fix()
