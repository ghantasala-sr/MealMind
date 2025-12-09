import sys
import os
import json

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.db import get_snowpark_session, get_snowflake_connection
from utils.meal_router_agent import MealRouterAgent

def reproduce_loop(session, conn):
    print("\n" + "="*50)
    print("REPRODUCING INFINITE LOOP")
    print("="*50)
    
    try:
        agent = MealRouterAgent(session, conn)
        query = "Nutrition for bhendi"
        print(f"User Input: '{query}'")
        
        # Run chat stream and print updates
        # We expect this to hit recursion limit or loop many times
        count = 0
        for update in agent.run_chat_stream(query, "test_user_loop", [], {}, thread_id="loop_test"):
            if "__STATUS__" in update:
                print(update)
            elif "*** EXECUTING TOOL" in str(update): # If we were capturing stdout, but here we just see status
                pass
            
            # We can't easily see the internal print statements here unless we capture stdout
            # But we can see if it keeps saying "Searching database..."
            if "Searching database" in update:
                count += 1
                print(f"Tool execution count: {count}")
                if count > 5:
                    print("LOOP DETECTED! Stopping early.")
                    break
                    
        return True
    except Exception as e:
        print(f"Reproduction Script Error: {e}")
        return False

def main():
    session = get_snowpark_session()
    conn = get_snowflake_connection()
    if not session:
        print("Failed to get session")
        return
    reproduce_loop(session, conn)

if __name__ == "__main__":
    main()
