import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.db import get_snowpark_session, get_snowflake_connection
from utils.meal_router_agent import MealRouterAgent

def verify_router_full_workflow(session, conn):
    print("\n" + "="*50)
    print("VERIFYING ROUTER FULL WORKFLOW (REGRESSION TEST)")
    print("="*50)
    
    try:
        agent = MealRouterAgent(session, conn)
        user_id = "test_user_regression"
        
        # 1. Test Planning & Meal Adjustment
        # Request: "Add oatmeal to breakfast today"
        print("\n--- Test 1: Planning & Meal Adjustment ---")
        query1 = "Add oatmeal to breakfast today"
        print(f"User Input: '{query1}'")
        
        # We expect the planner to generate a 'meal_adjustment' action
        # and the agent to execute it.
        
        # Mocking the adjustment agent to avoid actual DB writes if possible, 
        # or we just let it run and check the output message.
        # Since we want to verify the *flow*, checking the output message is good enough.
        
        response1 = ""
        for update in agent.run_chat_stream(query1, user_id, [], {}, thread_id="reg_test_1"):
            if "__STATUS__" in update:
                print(update)
            else:
                response1 = update
                
        print(f"Response: {response1[:100]}...")
        if "Adjusting meal" in str(response1) or "added" in str(response1).lower() or "processed" in str(response1).lower():
             print("PASS: Planner routed to adjustment.")
        else:
             print("WARNING: unexpected response for adjustment.")

        # 2. Test Meal Retrieval
        # Request: "What is for breakfast today?"
        print("\n--- Test 2: Meal Retrieval ---")
        query2 = "What is for breakfast today?"
        print(f"User Input: '{query2}'")
        
        response2 = ""
        for update in agent.run_chat_stream(query2, user_id, [], {}, thread_id="reg_test_2"):
            if "__STATUS__" in update:
                print(update)
            else:
                response2 = update
                
        print(f"Response: {response2[:100]}...")
        if "Retrieved Meals" in response2 or "No meals found" in response2:
            print("PASS: Planner routed to retrieval.")
        else:
            print("WARNING: unexpected response for retrieval.")

        # 3. Test Tool Use (Calorie Estimation)
        # Request: "Calories in an apple?"
        print("\n--- Test 3: Tool Use (Calorie Estimation) ---")
        query3 = "Calories in an apple?"
        print(f"User Input: '{query3}'")
        
        tool_used = False
        response3 = ""
        for update in agent.run_chat_stream(query3, user_id, [], {}, thread_id="reg_test_3"):
            if "__STATUS__" in update:
                print(update)
                if "Searching database" in update:
                    tool_used = True
            else:
                response3 = update
                
        print(f"Response: {response3[:100]}...")
        if tool_used:
            print("PASS: Tool execution detected.")
        else:
            print("WARNING: Tool execution NOT detected.")

        return True

    except Exception as e:
        print(f"Regression Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    session = get_snowpark_session()
    conn = get_snowflake_connection()
    
    if not session:
        print("CRITICAL: Failed to get Snowpark Session")
        return
        
    verify_router_full_workflow(session, conn)

if __name__ == "__main__":
    main()
