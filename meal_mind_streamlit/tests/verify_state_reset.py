import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.meal_router_agent import MealRouterAgent, ChatRouterState

def verify_state_reset():
    print("\n" + "="*50)
    print("VERIFYING STATE RESET IN PLANNER")
    print("="*50)
    
    # Mock State
    state = ChatRouterState(
        user_input="I like chocolates",
        user_id="test_user",
        user_profile={},
        inventory_summary="",
        meal_plan_summary="",
        chat_history=[],
        plan=[], # Empty plan triggers the planner logic
        current_step_index=0,
        retrieved_data="Old Data",
        adjustment_result={"status": "success"},
        estimation_result={"calories": 100},
        recipe_result="Old Recipe: Pongal",
        final_messages=[],
        monitoring_warnings=[],
        response="",
        tool_calls=[],
        tool_outputs=[],
        active_node=""
    )
    
    print("INITIAL STATE (Simulating start of Turn 2):")
    print(f"recipe_result: {state.get('recipe_result')}")
    print(f"adjustment_result: {state.get('adjustment_result')}")
    
    # We need to instantiate the agent to call the node method
    # We can mock session/conn as None since node_planner mainly uses LLM which we might need to mock or just check the logic before LLM call?
    # Actually, node_planner calls LLM immediately.
    # To avoid making a real LLM call (which costs money and time), we can inspect the code logic OR
    # we can try to run it and catch the error if LLM fails, but check if state was modified BEFORE the error.
    
    # However, the state reset happens BEFORE the LLM call.
    # So if we can just run the function up to that point... we can't easily partial run.
    
    # Let's try to run it. If it fails at LLM init or invoke, we check if state was mutated.
    # But `node_planner` takes `state` and returns `state`.
    # If it crashes inside, we won't get the return value.
    # But `state` is a dict (mutable), so if it's modified in place before the crash, we might see it?
    # No, `node_planner` receives `state` as argument.
    
    # Let's try to mock the `chat_model` to avoid actual call.
    
    class MockLLM:
        def invoke(self, messages):
            # Return a dummy plan
            return type('obj', (object,), {'content': '[{"action": "general_chat", "params": {"query": "chocolates"}}]'})
            
    # Mock Agent
    class MockAgent:
        def __init__(self):
            self.chat_model = MockLLM()
            self.feedback_agent = None # Not used in planner directly usually
            
        def node_planner(self, state):
            # Copy-paste the logic or import it?
            # We want to test the ACTUAL code.
            # So we should instantiate the REAL MealRouterAgent but patch its LLM.
            pass

    # Real instantiation with None params (might fail in init)
    try:
        agent = MealRouterAgent(None, None)
    except Exception as e:
        print(f"Agent init failed as expected: {e}")
        # We can't easily instantiate the real agent without valid session/conn because of the init logic.
        # But we can import the class and patch the method? No.
        
        # Let's just create a dummy instance and attach the method?
        # The method `node_planner` is an instance method.
        # We can call `MealRouterAgent.node_planner(dummy_self, state)`
        
        pass

    # Create a dummy self
    class DummySelf:
        def __init__(self):
            self.chat_model = MockLLM()
            
    dummy_agent = DummySelf()
    
    # Call the unbound method with dummy_self
    print("\nCalling node_planner...")
    try:
        # We need to bind the method or call it from the class
        # But node_planner uses `self.chat_model`.
        
        # Let's dynamically assign the method to our dummy object to be safe
        dummy_agent.node_planner = MealRouterAgent.node_planner.__get__(dummy_agent, DummySelf)
        
        # Run
        new_state = dummy_agent.node_planner(state)
        
        print("\nPOST-EXECUTION STATE:")
        print(f"recipe_result: {new_state.get('recipe_result')}")
        print(f"adjustment_result: {new_state.get('adjustment_result')}")
        
        if new_state.get('recipe_result') is None and new_state.get('adjustment_result') is None:
            print("\nSUCCESS: State was reset!")
        else:
            print("\nFAILURE: State was NOT reset.")
            
    except Exception as e:
        print(f"Execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_state_reset()
