import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.db import get_snowpark_session, get_snowflake_connection
from utils.chat_agent import ChatAgent
from utils.evaluation_agent import NutritionEvaluationAgent
from utils.meal_adjustment_agent import MealAdjustmentAgent
from utils.meal_router_agent import MealRouterAgent

def verify_chat_agent(session):
    print("\n" + "="*50)
    print("VERIFYING CHAT AGENT")
    print("="*50)
    try:
        agent = ChatAgent(session)
        if not agent.mcp_client:
            print("FAILED: MCP Client not initialized in ChatAgent")
            return False
            
        print("MCP Client initialized successfully.")
        
        # Test Retrieval
        query = "How much protein in a chicken breast?"
        print(f"Testing retrieval with query: '{query}'")
        context = agent._retrieve_context(query)
        print(f"Retrieved Context Length: {len(context)}")
        if len(context) > 0:
            print("Context retrieval SUCCESS")
            print(f"Sample Context: {context[:100]}...")
        else:
            print("Context retrieval FAILED (Empty)")
            
        return True
    except Exception as e:
        print(f"ChatAgent Verification Failed: {e}")
        return False

def verify_evaluation_agent(session):
    print("\n" + "="*50)
    print("VERIFYING NUTRITION EVALUATION AGENT")
    print("="*50)
    try:
        agent = NutritionEvaluationAgent(session)
        if not agent.mcp_client:
            print("FAILED: MCP Client not initialized in NutritionEvaluationAgent")
            return False
            
        print("MCP Client initialized successfully.")
        
        # Test Retrieval
        food = "Apple"
        print(f"Testing ground truth retrieval for: '{food}'")
        context = agent._retrieve_ground_truth(food)
        print(f"Retrieved Context Length: {len(context)}")
        if len(context) > 0 and "No matching food" not in context:
            print("Ground truth retrieval SUCCESS")
            print(f"Sample Context: {context[:100]}...")
        else:
            print(f"Ground truth retrieval WARNING: {context}")
            
        return True
    except Exception as e:
        print(f"NutritionEvaluationAgent Verification Failed: {e}")
        return False

def verify_adjustment_agent(session, conn):
    print("\n" + "="*50)
    print("VERIFYING MEAL ADJUSTMENT AGENT")
    print("="*50)
    try:
        agent = MealAdjustmentAgent(session, conn)
        if not agent.mcp_client:
            print("FAILED: MCP Client not initialized in MealAdjustmentAgent")
            return False
            
        print("MCP Client initialized successfully.")
        
        # Test Retrieval
        query = "I ate a banana"
        print(f"Testing context retrieval for: '{query}'")
        context = agent._retrieve_context(query)
        print(f"Retrieved Context Length: {len(context)}")
        if len(context) > 0:
            print("Context retrieval SUCCESS")
            print(f"Sample Context: {context[:100]}...")
        else:
            print("Context retrieval FAILED (Empty)")
            
        return True
    except Exception as e:
        print(f"MealAdjustmentAgent Verification Failed: {e}")
        return False

def verify_router_agent(session, conn):
    print("\n" + "="*50)
    print("VERIFYING MEAL ROUTER AGENT")
    print("="*50)
    try:
        agent = MealRouterAgent(session, conn)
        if not agent.mcp_client:
            print("FAILED: MCP Client not initialized in MealRouterAgent")
            return False
            
        print("MCP Client initialized successfully.")
        
        # Test Retrieval
        query = "Is pizza healthy?"
        print(f"Testing context retrieval for: '{query}'")
        context = agent._retrieve_context(query)
        print(f"Retrieved Context Length: {len(context)}")
        if len(context) > 0:
            print("Context retrieval SUCCESS")
            print(f"Sample Context: {context[:100]}...")
        else:
            print("Context retrieval FAILED (Empty)")
            
        return True
    except Exception as e:
        print(f"MealRouterAgent Verification Failed: {e}")
        return False

def main():
    print("Starting Verification...")
    session = get_snowpark_session()
    conn = get_snowflake_connection()
    
    if not session:
        print("CRITICAL: Failed to get Snowpark Session")
        return
        
    results = {
        "ChatAgent": verify_chat_agent(session),
        "EvaluationAgent": verify_evaluation_agent(session),
        "AdjustmentAgent": verify_adjustment_agent(session, conn),
        "RouterAgent": verify_router_agent(session, conn)
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
        print("\nALL AGENTS VERIFIED SUCCESSFULLY!")
    else:
        print("\nSOME AGENTS FAILED VERIFICATION.")

if __name__ == "__main__":
    main()
