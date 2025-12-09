import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.meal_router_agent import MealRouterAgent, ChatRouterState
from langchain_core.messages import HumanMessage

def reproduce_recursion_loop():
    print("\n" + "="*50)
    print("REPRODUCING RECURSION LOOP")
    print("="*50)
    
    # We need a mock session/conn or try to use real ones if available
    # Since we are testing the logic loop, we might need the real LLM to see if it keeps requesting tools.
    # We can use the real agent if credentials are set.
    
    from utils.db import get_snowpark_session, get_snowflake_connection
    session = get_snowpark_session()
    conn = get_snowflake_connection()
    
    if not session:
        print("SKIP: No Snowflake session available for reproduction.")
        return

    agent = MealRouterAgent(session, conn)
    
    # Initial State
    state = ChatRouterState(
        user_input="detailed nutrition info for motichoor ladoo",
        user_id="test_user_recursion",
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
    
    # We want to simulate the flow starting from planner -> calorie_estimation
    # But running the full graph might be slow/complex.
    # Let's manually run the planner to get the plan, then run calorie_estimation loop.
    
    print("Running Planner...")
    state = agent.node_planner(state)
    print(f"Plan: {json.dumps(state['plan'], indent=2)}")
    
    if not state['plan'] or state['plan'][0]['action'] != 'calorie_estimation':
        print("FAIL: Planner did not route to calorie_estimation")
        return

    # Now run calorie_estimation
    print("\nRunning Calorie Estimation (Step 1)...")
    state['current_step_index'] = 0
    state = agent.node_estimate_calories(state)
    
    print(f"Tool Calls 1: {state.get('tool_calls')}")
    
    if not state.get('tool_calls'):
        print("FAIL: No tool calls generated in step 1")
        return
        
    # Simulate Tool Execution (Mocking the results to save time/calls)
    print("\nSimulating Tool Execution...")
    tool_outputs = []
    for call in state['tool_calls']:
        tool_outputs.append({
            "tool": call['tool'],
            "query": call['query'],
            "result": f"Mock nutrition data for {call['query']}: 100 kcal"
        })
    state['tool_outputs'] = tool_outputs
    state['tool_calls'] = [] # Clear calls after execution
    
    # Run Calorie Estimation AGAIN (Step 2)
    # This is where it should aggregate, but user says it loops.
    print("\nRunning Calorie Estimation (Step 2 - After Tools)...")
    state = agent.node_estimate_calories(state)
    
    print(f"Tool Calls 2: {state.get('tool_calls')}")
    print(f"Estimation Result: {state.get('estimation_result')}")
    
    if state.get('tool_calls'):
        print("\nFAIL: Agent requested tools AGAIN instead of aggregating!")
        print("Loop detected.")
    elif state.get('estimation_result'):
        print("\nSUCCESS: Agent aggregated results.")
    else:
        print("\nUNKNOWN: Agent did neither?")

if __name__ == "__main__":
    reproduce_recursion_loop()
