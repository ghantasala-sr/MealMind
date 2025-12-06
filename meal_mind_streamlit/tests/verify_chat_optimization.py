import sys
import os
import time
import json
from concurrent.futures import ThreadPoolExecutor

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db import get_snowflake_connection, get_snowpark_session, get_user_profile, get_user_inventory, get_latest_meal_plan
from utils.meal_router_agent import MealRouterAgent
from utils.checkpoint import SnowflakeCheckpointSaver

def test_parallel_loading(conn, user_id):
    print("\n--- Testing Parallel Context Loading ---")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_profile = executor.submit(get_user_profile, conn, user_id)
        future_inventory = executor.submit(get_user_inventory, conn, user_id)
        future_meal_plan = executor.submit(get_latest_meal_plan, conn, user_id)
        
        user_profile = future_profile.result()
        inventory_df = future_inventory.result()
        meal_plan_data = future_meal_plan.result()
        
    end_time = time.time()
    print(f"Parallel loading took: {end_time - start_time:.4f} seconds")
    print(f"Profile loaded: {bool(user_profile)}")
    print(f"Inventory loaded: {not inventory_df.empty}")
    print(f"Meal plan loaded: {bool(meal_plan_data)}")

def test_chat_agent_stream(conn, session, user_id):
    print("\n--- Testing Chat Agent Stream & Checkpointing ---")
    agent = MealRouterAgent(session, conn)
    
    # Mock context data
    # Mock context and preferences
    context_data = {
        "user_profile": {"username": "TestUser"},
        "inventory_summary": "Apples, Bananas",
        "meal_plan_summary": "No active plan"
    }
    user_prefs = {"likes": [{"name": "Pizza", "type": "food"}]}

    print("\n--- Testing Chat Agent Stream & Checkpointing ---")
    thread_id = f"test_thread_{int(time.time())}"
    print(f"Using Thread ID: {thread_id}")
    
    print("Starting stream...")
    start_time = time.time()
    
    response_received = False
    extraction_seen = False
    chunk_count = 0
    
    for chunk in agent.run_chat_stream(
        user_input="I love pasta!", 
        user_id=user_id, 
        history=[], 
        context_data=context_data,
        user_preferences=user_prefs,
        thread_id=thread_id
    ):
        if chunk.startswith("__STATUS__:"):
            print(f"Status: {chunk}")
            if "Analyzing your input" in chunk:
                extraction_seen = True
        else:
            response_received = True
            chunk_count += 1
            # print(f"Chunk: {chunk}") # Debug
            
    end_time = time.time()
    print(f"Stream finished in: {end_time - start_time:.4f} seconds")
    print(f"Total response chunks: {chunk_count}")
    
    if chunk_count > 5:
        print("✅ SUCCESS: Token streaming active!")
    else:
        print("❌ FAILURE: Response received in too few chunks (likely not streaming tokens).")
        
    if not extraction_seen:
        # Note: With the new flow, extraction runs in the graph BEFORE streaming starts
        # So we might see the status update before the response.
        # Wait, extract_feedback is AFTER generate_response in the graph.
        # But generate_response is now prepare_response (instant).
        # So extraction happens fast.
        # Status updates for extraction should be yielded during the graph loop.
        print("❌ FAILURE: Extraction status not seen!")
    else:
        print("✅ SUCCESS: Extraction status seen.")
    
    # Verify checkpoint
    print("\nVerifying Checkpoint...")
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM thread_checkpoints WHERE thread_id = %s", (thread_id,))
    count = cursor.fetchone()[0]
    print(f"Checkpoints found for thread {thread_id}: {count}")
    
    if count > 0:
        print("✅ Checkpointing successful!")
    else:
        print("❌ Checkpointing failed!")

if __name__ == "__main__":
    try:
        conn = get_snowflake_connection()
        session = get_snowpark_session()
        
        # Use a dummy user ID or fetch one
        user_id = "test_user_id" 
        
        test_parallel_loading(conn, user_id)
        test_chat_agent_stream(conn, session, user_id)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Test failed: {repr(e)}")
