import json
import os
import sys
from typing import List, Dict, Any

# Add parent directory to path to import utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.meal_router_agent import MealRouterAgent, ChatRouterState
from langchain_core.messages import HumanMessage

class EvalRunner:
    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        with open(dataset_path, 'r') as f:
            self.dataset = json.load(f)
        
        # Initialize Agent
        # Mocking session state for initialization if needed, 
        # but MealRouterAgent mainly needs a model.
        # We assume environment variables (SNOWFLAKE credentials) are set.
        # Initialize Snowflake Session
        from snowflake.snowpark import Session
        
        connection_params = {
            "account": os.getenv("SNOWFLAKE_ACCOUNT"),
            "user": os.getenv("SNOWFLAKE_USER"),
            "password": os.getenv("SNOWFLAKE_PASSWORD"),
            "role": os.getenv("SNOWFLAKE_ROLE"),
            "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
            "database": os.getenv("SNOWFLAKE_DATABASE"),
            "schema": os.getenv("SNOWFLAKE_SCHEMA"),
        }
        
        try:
            self.session = Session.builder.configs(connection_params).create()
            # Create a mock connection object for compatibility if needed, 
            # or just pass session.connection if MealRouterAgent uses it.
            # MealRouterAgent uses self.conn for some DB ops? 
            # It seems MealRouterAgent takes (session, conn).
            # Usually conn is snowflake.connector.connect().
            # But session.connection is a Snowpark connection.
            # Let's check MealRouterAgent usage.
            # It uses self.conn for get_meals_by_criteria (utils.db).
            # utils.db expects a snowflake connector connection (cursor).
            # We can get it from session.connection.
            self.conn = self.session.connection
        except Exception as e:
            print(f"Failed to create Snowflake session: {e}")
            self.session = None
            self.conn = None

        self.agent = MealRouterAgent(self.session, self.conn)

    def run_evals(self) -> List[Dict[str, Any]]:
        results = []
        print(f"Starting evaluation of {len(self.dataset)} test cases...")
        
        for case in self.dataset:
            print(f"Running Case ID: {case['id']} ({case['category']})")
            
            # Prepare State
            initial_state: ChatRouterState = {
                "user_input": case['input'],
                "user_id": "test_user",
                "chat_history": [],
                "user_profile": {"name": "Test User"}, # Mock profile
                "user_preferences": {},
                "inventory_summary": "Apples, Milk, Eggs", # Mock inventory
                "plan": [],
                "tool_calls": [],
                "tool_outputs": [],
                "final_messages": [],
                "response": None
            }
            
            try:
                # Run Agent
                # The agent is a compiled graph, we invoke it.
                # Note: MealRouterAgent.graph is the compiled runnable.
                # Pass thread_id for checkpointer
                config = {"configurable": {"thread_id": case['id']}}
                final_state = self.agent.app.invoke(initial_state, config=config)
                
                # Extract Results
                actual_plan = final_state.get('plan', [])
                actual_response = final_state.get('response', "NO_RESPONSE")
                
                # Determine Intent (First action in plan)
                actual_intent = actual_plan[0]['action'] if actual_plan else "unknown"
                
                result = {
                    "id": case['id'],
                    "input": case['input'],
                    "expected_intent": case['expected_intent'],
                    "actual_intent": actual_intent,
                    "actual_response": actual_response,
                    "error": None
                }
                
            except Exception as e:
                print(f"Error in case {case['id']}: {e}")
                result = {
                    "id": case['id'],
                    "input": case['input'],
                    "expected_intent": case['expected_intent'],
                    "actual_intent": "ERROR",
                    "actual_response": str(e),
                    "error": str(e)
                }
            
            results.append(result)
            
        return results

if __name__ == "__main__":
    # Local Test
    runner = EvalRunner("evals/eval_dataset.json")
    results = runner.run_evals()
    print(json.dumps(results, indent=2))
