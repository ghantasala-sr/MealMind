import sys
import os
import json
import re
from langchain_core.messages import HumanMessage

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.db import get_snowpark_session, get_snowflake_connection
from utils.meal_router_agent import MealRouterAgent

def verify_nutrition_breakdown(session, conn):
    print("\n" + "="*50)
    print("VERIFYING MULTI-STEP NUTRITION BREAKDOWN")
    print("="*50)
    
    try:
        agent = MealRouterAgent(session, conn)
        user_id = "test_user_breakdown"
        query = "nutrition for paneer burji"
        
        print(f"User Input: '{query}'")
        
        tool_calls_detected = []
        response_text = ""
        
        # Run the stream
        for update in agent.run_chat_stream(query, user_id, [], {}, thread_id="breakdown_test"):
            if "__STATUS__" in update:
                print(update)
            else:
                response_text = str(update)
                # We can try to parse debug prints if we were capturing stdout, but here we can check the response
                # or rely on the console output for manual verification.
                # However, we can also check if the response mentions the ingredients.
        
        print("\nFinal Response Preview:")
        print(response_text[:500])
        
        # Check if response mentions ingredients, implying breakdown
        ingredients = ["paneer", "onion", "tomato"]
        found_ingredients = [ing for ing in ingredients if ing in response_text.lower()]
        
        if len(found_ingredients) >= 2:
             print(f"\nPASS: Response mentions ingredients: {found_ingredients}")
        else:
             print(f"\nFAIL: Response does not seem to mention ingredients. Found: {found_ingredients}")
             
        # Ideally we want to see multiple tool calls in the logs.
        print("\nCHECK CONSOLE LOGS for multiple '*** TOOL CALL DETECTED ***' messages.")

    except Exception as e:
        print(f"Verification Script Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    session = get_snowpark_session()
    conn = get_snowflake_connection()
    if not session:
        print("Failed to get session")
        return
    verify_nutrition_breakdown(session, conn)

if __name__ == "__main__":
    main()
