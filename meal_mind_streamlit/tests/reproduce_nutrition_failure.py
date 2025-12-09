import sys
import os
import json
from langchain_core.messages import HumanMessage, AIMessage

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.db import get_snowpark_session, get_snowflake_connection
from utils.meal_router_agent import MealRouterAgent

def reproduce_nutrition_failure(session, conn):
    print("\n" + "="*50)
    print("REPRODUCING NUTRITION FAILURE")
    print("="*50)
    
    try:
        agent = MealRouterAgent(session, conn)
        user_id = "test_user_nutrition"
        
        # Step 1: Ask for Recipe
        print("\n--- Step 1: Ask for Recipe ---")
        query1 = "Give recipe on Chennai style pongal"
        print(f"User: {query1}")
        
        # We don't need to run the full stream, just establish history
        history = [
            HumanMessage(content=query1),
            AIMessage(content="Here is the recipe for Chennai Style Pongal...")
        ]
        
        # Step 2: Ask for Nutrition
        print("\n--- Step 2: Ask for Nutrition (The Failure Point) ---")
        query2 = "Can u give detailed breakdown nutrition for it"
        print(f"User: {query2}")
        
        # Run agent to see Planner output
        # We need to hook into the planner output or infer from the stream
        
        for update in agent.run_chat_stream(query2, user_id, history, {}, thread_id="reproduce_nutrition"):
            if "__STATUS__" in update:
                print(update)
            elif "DEBUG" in str(update): # If we had debug prints enabled
                print(update)
            else:
                # In the real app, we can't easily see the plan unless we added debug prints.
                # But we can infer from the response.
                response = str(update)
                print(f"DEBUG: Stream Update: {response}")
                if "Ingredients" in response and "Instructions" in response and "Calories" not in response:
                    print("FAIL: Agent returned a recipe again!")
                    return False
                elif "Calories" in response and "Protein" in response:
                     print("PASS: Agent returned nutrition info.")
                     if "Would you like to add this" in response:
                         print("PASS: Agent asked to add to meal plan.")
                         return True
                     else:
                         print("FAIL: Agent did NOT ask to add to meal plan.")
                         return False
                     
        # If we get here, we need to check if it actually called tools.
        # Since we can't see internal state easily without debug prints, I'll rely on the output content.
        
        return True

    except Exception as e:
        print(f"Reproduction Script Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    session = get_snowpark_session()
    conn = get_snowflake_connection()
    if not session:
        print("Failed to get session")
        return
    reproduce_nutrition_failure(session, conn)

if __name__ == "__main__":
    main()
