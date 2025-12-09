import sys
import os
import json
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.meal_router_agent import MealRouterAgent, ChatRouterState

def verify_recursion_fix_mock():
    print("\n" + "="*50)
    print("VERIFYING RECURSION FIX (MOCK LLM)")
    print("="*50)
    
    # Mock LLM
    mock_llm = MagicMock()
    
    # Scenario:
    # 1. First call: Returns tool calls for 'sugar' and 'ghee'.
    # 2. Second call (Retry 1): Returns SAME tool calls (stubborn).
    # 3. Third call (Retry 2 - forced): Returns text "Okay, here is the info."
    
    # But wait, my logic is:
    # Loop attempt 0:
    #   LLM returns duplicates.
    #   Code detects duplicates.
    #   Code appends error message.
    #   Continues to attempt 1.
    # Loop attempt 1:
    #   LLM returns text (hopefully).
    
    # So I need to mock the sequence of responses.
    
    # Response 1: Duplicate tools
    response_duplicate = AIMessage(content='{"tool": "search_foods", "query": "sugar"} {"tool": "search_foods", "query": "ghee"}')
    
    # Response 2: Final Answer
    response_final = AIMessage(content="Based on the sugar and ghee, the calories are 500.")
    
    mock_llm.invoke.side_effect = [response_duplicate, response_final]
    
    # Setup Agent with Mock LLM
    # We need to bypass init which requires real creds usually
    class DummyAgent(MealRouterAgent):
        def __init__(self):
            self.chat_model = mock_llm
            
    agent = DummyAgent()
    
    # Setup State with EXISTING tool outputs (simulating Step 2 of the loop)
    state = ChatRouterState(
        user_input="motichoor ladoo",
        user_id="test",
        user_profile={},
        inventory_summary="",
        meal_plan_summary="",
        chat_history=[],
        plan=[{"action": "calorie_estimation", "params": {"query": "motichoor ladoo"}}],
        current_step_index=0,
        retrieved_data=None,
        adjustment_result=None,
        estimation_result=None,
        recipe_result=None,
        final_messages=[],
        monitoring_warnings=[],
        response="",
        tool_calls=[],
        tool_outputs=[
            {"tool": "search_foods", "query": "sugar", "result": "Sugar data"},
            {"tool": "search_foods", "query": "ghee", "result": "Ghee data"}
        ],
        active_node=""
    )
    
    print("Running node_estimate_calories with existing outputs...")
    new_state = agent.node_estimate_calories(state)
    
    print(f"\nResulting Tool Calls: {new_state.get('tool_calls')}")
    print(f"Resulting Final Messages: {new_state.get('final_messages')}")
    
    # Verification
    if not new_state.get('tool_calls') and new_state.get('final_messages'):
        msg_content = new_state['final_messages'][0].content
        if "Based on the sugar" in msg_content:
            print("\nSUCCESS: Loop broken, final answer returned.")
        else:
            print(f"\nPARTIAL SUCCESS: Loop broken, but unexpected message: {msg_content}")
    else:
        print("\nFAIL: Still returning tool calls or no message.")

if __name__ == "__main__":
    verify_recursion_fix_mock()
