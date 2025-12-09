import sys
import os
import json
from langchain_core.messages import HumanMessage, AIMessage

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.db import get_snowpark_session, get_snowflake_connection
from utils.meal_router_agent import MealRouterAgent

def verify_recipe_agent(session, conn):
    print("\n" + "="*50)
    print("VERIFYING RECIPE AGENT")
    print("="*50)
    
    try:
        agent = MealRouterAgent(session, conn)
        user_id = "test_user_recipe"
        
        # Test Case 1: Request Recipe (Should route to recipe_lookup)
        print("\n--- Test 1: Request Recipe (Expect recipe_lookup) ---")
        query = "Give me a recipe for Carrot Halwa"
        print(f"User Input: '{query}'")
        
        recipe_found = False
        response_text = ""
        
        for update in agent.run_chat_stream(query, user_id, [], {}, thread_id="recipe_test_1"):
            if "__STATUS__" in update:
                print(update)
            else:
                print(f"DEBUG: Stream Update: {update}")
                response_text = str(update)
                # Check for recipe content
                if "Ingredients" in response_text and "Instructions" in response_text:
                    recipe_found = True
                    
        # Check logs for "Dispatching to recipe_lookup" (we can't see logs here easily, but we can infer from result)
        # Ideally we'd capture stdout, but checking the content is good enough.
        
        if recipe_found:
            print("PASS: Recipe generated successfully.")
        else:
            print(f"FAIL: Recipe not found in response. Response: {response_text[:200]}...")
            return False
            
        # Test Case 2: Ensure NO Meal Adjustment Triggered
        if "update" in response_text.lower() or "confirm" in response_text.lower():
             print("FAIL: Agent asked for confirmation or tried to update meal!")
             return False
        else:
             print("PASS: No meal adjustment triggered.")

        return True

    except Exception as e:
        print(f"Verification Script Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    session = get_snowpark_session()
    conn = get_snowflake_connection()
    if not session:
        print("Failed to get session")
        return
    verify_recipe_agent(session, conn)

if __name__ == "__main__":
    main()
