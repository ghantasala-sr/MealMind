import sys
import os
import json
from langchain_core.messages import HumanMessage, AIMessage

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.db import get_snowpark_session, get_snowflake_connection
from utils.meal_router_agent import MealRouterAgent

def verify_recipe_inventory(session, conn):
    print("\n" + "="*50)
    print("VERIFYING RECIPE INVENTORY INTEGRATION")
    print("="*50)
    
    try:
        agent = MealRouterAgent(session, conn)
        user_id = "test_user_inventory"
        
        # Mock Inventory
        mock_inventory = "Tomatoes, Basil, Mozzarella Cheese, Baguette"
        
        # Test Case 1: Request Recipe with Inventory Context
        print("\n--- Test 1: 'What can I cook?' (Expect Inventory Usage) ---")
        query = "What can I cook with my ingredients?"
        print(f"User Input: '{query}'")
        print(f"Mock Inventory: {mock_inventory}")
        
        # Manually inject inventory into context_data for the test
        context_data = {
            'inventory_summary': mock_inventory,
            'user_profile': {},
            'meal_plan_summary': ''
        }
        
        recipe_found = False
        response_text = ""
        
        for update in agent.run_chat_stream(query, user_id, [], context_data, thread_id="inventory_test_1"):
            if "__STATUS__" in update:
                print(update)
            else:
                response_text = str(update)
                # Check for recipe content and inventory items
                if "Ingredients" in response_text and "Instructions" in response_text:
                    recipe_found = True
                    
        if recipe_found:
            print("PASS: Recipe generated.")
            
            # Check if it suggested something relevant (e.g., Bruschetta or Caprese)
            lower_resp = response_text.lower()
            if "tomato" in lower_resp and "basil" in lower_resp:
                print("PASS: Recipe used inventory ingredients (Tomato, Basil).")
            else:
                print("FAIL: Recipe did not seem to use inventory ingredients.")
                print(f"Response Preview: {response_text[:200]}...")
                return False
        else:
            print(f"FAIL: Recipe not found in response. Response: {response_text[:200]}...")
            return False

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
    verify_recipe_inventory(session, conn)

if __name__ == "__main__":
    main()
