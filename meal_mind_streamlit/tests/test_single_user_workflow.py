import sys
import os
import logging
import json
from datetime import datetime

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Mock streamlit if not installed/running to avoid import errors in utils
try:
    import streamlit as st
except ImportError:
    from unittest.mock import MagicMock
    sys.modules['streamlit'] = MagicMock()

from utils.meal_plan_workflow import MealPlanWorkflow, MealPlanGenerationState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_runner")

class TestSingleUserWorkflow(MealPlanWorkflow):
    def __init__(self, target_user_id):
        super().__init__()
        self.target_user_id = target_user_id

    def agent_fetch_users(self, state: MealPlanGenerationState) -> MealPlanGenerationState:
        """Fetch ONLY the specific user"""
        print(f"\n[TEST] Fetching specific user: {self.target_user_id}")
        
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT user_id, next_plan_date, schedule_id
                FROM planning_schedule
                WHERE user_id = %s
                AND status = 'ACTIVE'
            """, (self.target_user_id,))
            
            users = []
            row = cursor.fetchone()
            if row:
                users.append({
                    'user_id': row[0],
                    'next_plan_date': row[1],
                    'schedule_id': row[2]
                })
            
            state['users_to_process'] = users
            state['current_user_index'] = 0
            
            if users:
                print(f"[TEST] Found user: {self.target_user_id}")
            else:
                print(f"[TEST] User {self.target_user_id} not found or not active in schedule.")
                
            return state
            
        except Exception as e:
            print(f"[TEST] Error fetching users: {e}")
            state['errors'].append({
                'agent': 'fetch_users',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return state
        finally:
            cursor.close()

    def agent_generate_meal_plan(self, state: MealPlanGenerationState) -> MealPlanGenerationState:
        # Call parent method
        state = super().agent_generate_meal_plan(state)
        
        # Print summary of generation
        if state.get('generated_plan'):
            plan = state['generated_plan']
            week_summary = plan.get('meal_plan', {}).get('week_summary', {})
            print("\n[TEST] ✅ Meal Plan Generated Successfully!")
            print(f"  - Days Generated: {len(plan.get('meal_plan', {}).get('days', []))}")
            print(f"  - Inventory Utilization: {week_summary.get('inventory_utilization_rate')}%")
            print(f"  - Avg Calories: {week_summary.get('average_daily_calories')}")
        else:
            print("\n[TEST] ❌ Failed to generate meal plan.")
            
        return state

def main():
    # Use the user ID from the existing run_workflow_single_user.py
    target_user_id = 'a744853e-1733-49ef-85d8-d2eb140d197d'
    
    print(f"Starting Test Workflow for User: {target_user_id}")
    
    try:
        workflow = TestSingleUserWorkflow(target_user_id)
        result = workflow.run()
        
        success_count = result.get('success_count', 0)
        
        print("\n" + "="*30)
        if success_count > 0:
            print("TEST PASSED: Workflow completed successfully.")
        else:
            print("TEST FAILED: Workflow did not complete successfully.")
            if result.get('errors'):
                print("Errors encountered:")
                print(json.dumps(result['errors'], indent=2))
        print("="*30 + "\n")
            
    except Exception as e:
        print(f"Test Execution Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
