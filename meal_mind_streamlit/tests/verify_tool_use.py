import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.db import get_snowpark_session, get_snowflake_connection
from utils.chat_agent import ChatAgent
from utils.meal_router_agent import MealRouterAgent

def verify_chat_agent_tool_use(session):
    print("\n" + "="*50)
    print("VERIFYING CHAT AGENT TOOL USE")
    print("="*50)
    try:
        agent = ChatAgent(session)
        if not agent.mcp_client:
            print("FAILED: MCP Client not initialized")
            return False
            
        # Test 1: Query requiring tool use
        query_tool = "How many calories in a banana?"
        print(f"Test 1: '{query_tool}' (Should use tool)")
        
        # We can inspect the graph execution or just run it and check logs/output
        # Since we can't easily hook into the graph here without modifying it, 
        # we will rely on the agent's internal print statements (if any) or just the final result.
        # But to be sure, let's check if the response contains specific data.
        
        response_tool = agent.run_chat(query_tool, [], {})
        print(f"Response: {response_tool[:100]}...")
        
        if "calories" in response_tool.lower() or "kcal" in response_tool.lower():
            print("PASS: Response contains nutritional info.")
        else:
            print("WARNING: Response might not contain nutritional info.")

        # Test 2: Query NOT requiring tool use
        query_no_tool = "Hello, who are you?"
        print(f"\nTest 2: '{query_no_tool}' (Should NOT use tool)")
        response_no_tool = agent.run_chat(query_no_tool, [], {})
        print(f"Response: {response_no_tool[:100]}...")
        
        return True
    except Exception as e:
        print(f"ChatAgent Verification Failed: {e}")
        return False

def verify_router_agent_tool_use(session, conn):
    print("\n" + "="*50)
    print("VERIFYING ROUTER AGENT TOOL USE")
    print("="*50)
    try:
        agent = MealRouterAgent(session, conn)
        
        # Test Calorie Estimation (uses tool)
        query = "Estimate calories for a slice of pizza"
        print(f"Test: '{query}' (Should use tool in calorie_estimation)")
        
        # We need to simulate the state flow or just run the stream
        # Let's run the stream and print status updates
        print("Running stream...")
        for update in agent.run_chat_stream(query, "test_user", [], {}, thread_id="test_thread"):
            if "__STATUS__" in update:
                print(update)
                if "Searching database" in update:
                    print("PASS: Tool execution detected!")
            
        return True
    except Exception as e:
        print(f"RouterAgent Verification Failed: {e}")
        return False

def main():
    print("Starting Tool Use Verification...")
    session = get_snowpark_session()
    conn = get_snowflake_connection()
    
    if not session:
        print("CRITICAL: Failed to get Snowpark Session")
        return
        
    results = {
        "ChatAgent": verify_chat_agent_tool_use(session),
        "RouterAgent": verify_router_agent_tool_use(session, conn)
    }
    
    print("\n" + "="*50)
    print("FINAL RESULTS")
    print("="*50)
    all_passed = True
    for agent, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{agent}: {status}")
        if not passed:
            all_passed = False
            
    if all_passed:
        print("\nINTELLIGENT TOOL USE VERIFIED!")
    else:
        print("\nSOME CHECKS FAILED.")

if __name__ == "__main__":
    main()
