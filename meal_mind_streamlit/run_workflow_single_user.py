import sys
import os
import logging
import json
from datetime import datetime
from utils.meal_plan_workflow import MealPlanWorkflow, MealPlanGenerationState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("single_user_runner")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

class SingleUserMealPlanWorkflow(MealPlanWorkflow):
    def __init__(self, target_user_id):
        super().__init__()
        self.target_user_id = target_user_id

    def agent_fetch_users(self, state: MealPlanGenerationState) -> MealPlanGenerationState:
        """Fetch ONLY the specific user"""
        st.info(f"Fetching specific user: {self.target_user_id}")
        
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
                st.success(f"Found user: {self.target_user_id}")
            else:
                st.error(f"User {self.target_user_id} not found or not active in schedule.")
                
            return state
            
        except Exception as e:
            st.error(f"Error fetching users: {e}")
            state['errors'].append({
                'agent': 'fetch_users',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return state
        finally:
            cursor.close()

    def agent_aggregate_user_data(self, state: MealPlanGenerationState) -> MealPlanGenerationState:
        # Call parent method to do the work
        state = super().agent_aggregate_user_data(state)
        
        # Visualize the data
        if state.get('user_data'):
            with st.expander("📊 Extracted User Data", expanded=True):
                st.subheader("Profile")
                st.json(state['user_data']['profile'])
                
                st.subheader("Inventory")
                st.json(state['user_data']['inventory'])
                
                st.subheader("Preferences")
                st.json(state['user_data']['preferences'])
                
                st.subheader("Previous Meals")
                st.write(state['user_data']['previous_meals'])
                
        return state

    def agent_generate_meal_plan(self, state: MealPlanGenerationState) -> MealPlanGenerationState:
        # Call parent method
        state = super().agent_generate_meal_plan(state)
        
        # Visualize the plan
        if state.get('generated_plan'):
            with st.expander("🍳 Generated Meal Plan", expanded=True):
                st.json(state['generated_plan'])
        else:
            st.error("Failed to generate meal plan.")
            
        return state

def main():
    st.title("Single User Meal Plan Generator")
    
    target_user_id = 'a744853e-1733-49ef-85d8-d2eb140d197d'
    st.write(f"**Target User ID:** `{target_user_id}`")
    
    if st.button("Run Workflow"):
        try:
            # Initialize Custom Workflow
            workflow = SingleUserMealPlanWorkflow(target_user_id)
            
            # Run Workflow
            with st.spinner("Running workflow..."):
                result = workflow.run()
            
            # Log Results
            success_count = result.get('success_count', 0)
            failure_count = result.get('failure_count', 0)
            errors = result.get('errors', [])
            
            st.divider()
            if success_count > 0:
                st.success("✅ Workflow Finished Successfully!")
            else:
                st.error("❌ Workflow Failed")
            
            if errors:
                st.error("Encountered errors:")
                st.json(errors)
            
        except Exception as e:
            st.exception(e)

if __name__ == "__main__":
    main()
