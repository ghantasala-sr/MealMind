import sys
import os
import json
from langchain_core.messages import HumanMessage, AIMessage

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.db import get_snowpark_session, get_snowflake_connection
from utils.meal_router_agent import MealRouterAgent

def reproduce_planner_ambiguity(session, conn):
    print("\n" + "="*50)
    print("REPRODUCING PLANNER AMBIGUITY")
    print("="*50)
    
    try:
        agent = MealRouterAgent(session, conn)
        user_id = "test_user_ambiguity"
        
        # Simulate conversation history
        # 1. User asks about Veg Pulao
        history = [
            HumanMessage(content="Nutrition for Veg Pulao"),
            AIMessage(content="Veg Pulao is nutritious... Recipe: Rice, Veggies..."),
        ]
        
        # 2. User asks "How about including garlic to it"
        # This should be interpreted as a question about the recipe/nutrition, NOT an update command.
        query = "How about including garlic to it"
        print(f"User Input: '{query}'")
        
        print("\n--- Running Agent ---")
        # We want to inspect the generated plan. 
        # Since we can't easily hook into the internal state here without modifying code,
        # we will look at the output. 
        # If it says "Successfully updated", it failed.
        # If it gives nutrition info/recipe advice, it passed.
        
        response_text = ""
        for update in agent.run_chat_stream(query, user_id, history, {}, thread_id="ambiguity_test"):
            if "__STATUS__" in update:
                print(update)
            else:
                response_text = update
                
        print(f"\nFINAL RESPONSE:\n{response_text[:200]}...")
        
        if "Successfully updated" in response_text or "New item" in response_text:
            print("FAIL: Planner triggered meal update.")
        else:
            print("PASS: Planner treated it as chat/info.")
                    
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
    reproduce_planner_ambiguity(session, conn)

if __name__ == "__main__":
    main()
