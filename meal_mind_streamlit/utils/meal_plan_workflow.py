"""
LangGraph Multi-Agent Meal Plan Generator for Airflow
Handles automated weekly meal plan generation with intelligent retry logic
"""
import sys
import os
from typing import TypedDict, Dict, List, Optional, Any
from datetime import datetime, timedelta
from langgraph.graph import StateGraph, END
import json

# Add project root to path (dynamically finds the parent directory of 'utils')
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.db import get_snowflake_connection, get_snowpark_session
from utils.agent import MealPlanAgentWithExtraction
from utils.feedback_agent import FeedbackAgent


# ==================== STATE DEFINITION ====================
class MealPlanGenerationState(TypedDict):
    """State tracking for meal plan generation workflow"""
    current_date: str
    users_to_process: List[Dict]
    current_user_index: int
    current_user: Optional[Dict]
    user_data: Optional[Dict]  # Profile, feedback, preferences
    generated_plan: Optional[Dict]
    success_count: int
    failure_count: int
    errors: List[Dict]
    retry_count: int


# ==================== MULTI-AGENT WORKFLOW ====================
class MealPlanWorkflow:
    """LangGraph-based multi-agent workflow for meal plan generation"""
    
    def __init__(self):
        self.conn = get_snowflake_connection()
        self.session = get_snowpark_session()
        self.max_retries = 3
    
    # ==================== AGENT 1: USER FETCHER ====================
    def agent_fetch_users(self, state: MealPlanGenerationState) -> MealPlanGenerationState:
        """Fetch all users needing meal plans today"""
        print(f"[AGENT 1] Fetching users needing plans for {state['current_date']}")
        
        cursor = self.conn.cursor()
        try:
            # Removed username from query as it's not in planning_schedule
            cursor.execute("""
                SELECT DISTINCT user_id, next_plan_date, schedule_id
                FROM planning_schedule
                WHERE next_plan_date <= %s
                AND status = 'ACTIVE'
                ORDER BY user_id
            """, (state['current_date'],))
            
            users = []
            seen_users = set()
            for row in cursor.fetchall():
                if row[0] not in seen_users:
                    users.append({
                        'user_id': row[0],
                        'next_plan_date': row[1],
                        'schedule_id': row[2]
                    })
                    seen_users.add(row[0])
            
            state['users_to_process'] = users
            state['current_user_index'] = 0
            
            print(f"[AGENT 1] Found {len(users)} users to process")
            return state
            
        except Exception as e:
            print(f"[AGENT 1] Error fetching users: {e}")
            state['errors'].append({
                'agent': 'fetch_users',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return state
        finally:
            cursor.close()
    
    # ==================== AGENT 2: DATA AGGREGATOR ====================
    def agent_aggregate_user_data(self, state: MealPlanGenerationState) -> MealPlanGenerationState:
        """Gather all user data: profile, preferences, feedback, inventory"""
        if not state['users_to_process'] or state['current_user_index'] >= len(state['users_to_process']):
            return state
        
        user = state['users_to_process'][state['current_user_index']]
        user_id = user['user_id']
        
        print(f"[AGENT 2] Aggregating data for user {user_id}")
        
        cursor = self.conn.cursor()
        try:
            # Get user profile
            cursor.execute("""
                SELECT username, age, gender, height_cm, weight_kg, 
                       health_goal, dietary_restrictions, food_allergies,
                       daily_calories, daily_protein, daily_carbohydrate, daily_fat,
                       preferred_cuisines
                FROM users
                WHERE user_id = %s
            """, (user_id,))
            
            profile_row = cursor.fetchone()
            if not profile_row:
                raise Exception(f"User {user_id} not found")
            
            profile = {
                'username': profile_row[0],
                'age': profile_row[1],
                'gender': profile_row[2],
                'height_cm': profile_row[3],
                'weight_kg': profile_row[4],
                'health_goal': profile_row[5],
                'dietary_restrictions': profile_row[6],
                'food_allergies': profile_row[7],
                'daily_calories': profile_row[8],
                'daily_protein': profile_row[9],
                'daily_carbohydrate': profile_row[10],
                'daily_fat': profile_row[11],
                'preferred_cuisines': profile_row[12]
            }
            
            # Get inventory
            cursor.execute("""
                SELECT item_name, quantity, unit, category
                FROM inventory
                WHERE user_id = %s AND quantity > 0
            """, (user_id,))
            
            inventory_by_category = {}
            for row in cursor.fetchall():
                category = row[3] or 'Other'
                if category not in inventory_by_category:
                    inventory_by_category[category] = []
                inventory_by_category[category].append({
                    'item': row[0],
                    'quantity': row[1],
                    'unit': row[2]
                })
            
            # Get previous week's meals for variety
            cursor.execute("""
                SELECT md.meal_type, md.meal_name
                FROM meal_details md
                JOIN daily_meals dm ON md.meal_id = dm.meal_id
                JOIN meal_plans mp ON dm.plan_id = mp.plan_id
                WHERE mp.user_id = %s
                AND mp.status = 'ACTIVE'
                ORDER BY mp.created_at DESC
                LIMIT 28
            """, (user_id,))
            
            previous_meals = []
            for row in cursor.fetchall():
                previous_meals.append(f"{row[0].title()}: {row[1]}")
            
            # Get user preferences (learned from feedback)
            feedback_agent = FeedbackAgent(self.conn, self.session)
            preferences = feedback_agent.get_user_preferences(user_id)
            
            # Format preferences for prompt
            likes = [p['name'] for p in preferences.get('likes', [])[:5]]
            dislikes = [p['name'] for p in preferences.get('dislikes', [])[:5]]
            cuisines = [p['name'] for p in preferences.get('cuisines', [])[:3]]
            
            # Compile all data
            state['current_user'] = user
            state['user_data'] = {
                'user_id': user_id,
                'profile': profile,
                'preferences': preferences,
                'inventory': inventory_by_category,
                'previous_meals': previous_meals
            }
            
            print(f"[AGENT 2] Aggregated data for {user_id}: {len(inventory_by_category)} inventory categories, {len(preferences.get('likes', []))} likes, {len(previous_meals)} previous meals")
            
            # Build comprehensive prompt
            profile = state['user_data']['profile']
            inventory_by_category = state['user_data']['inventory']
            previous_meals = state['user_data']['previous_meals']
            preferences = state['user_data']['preferences']
            
            # Format preferences
            likes = [p['name'] for p in preferences.get('likes', [])[:5]]
            dislikes = [p['name'] for p in preferences.get('dislikes', [])[:5]]
            cuisines = [p['name'] for p in preferences.get('cuisines', [])[:3]]
            
            prompt = f"""Generate a complete 7-day meal plan for:

IMPORTANT: Today is {datetime.now().strftime('%A, %B %d, %Y')}. 
The meal plan should start from TODAY and continue for 7 days.
Ensure day names match the actual calendar dates (e.g., if today is Friday, day 1 should be Friday, day 2 should be Saturday, etc.).

USER PROFILE:
- User ID: {user_id}
- Age: {profile.get('age')} years
- Gender: {profile.get('gender')}
- Height: {profile.get('height_cm')} cm
- Weight: {profile.get('weight_kg')} kg
- Activity Level: {profile.get('activity_level')}
- Health Goal: {profile.get('health_goal')}
- Dietary Restrictions: {profile.get('dietary_restrictions', 'None')}
- Food Allergies: {profile.get('food_allergies', 'None')}
- Preferred Cuisines: {profile.get('preferred_cuisines', 'Any')}

DAILY NUTRITIONAL TARGETS:
- Calories: {profile.get('daily_calories', 2000)} kcal
- Protein: {profile.get('daily_protein', 130):.1f}g
- Carbohydrates: {profile.get('daily_carbohydrate', 250):.1f}g
- Fat: {profile.get('daily_fat', 70):.1f}g
- Fiber: {profile.get('daily_fiber', 30):.1f}g

LEARNED PREFERENCES (From User Feedback):
- Likes: {', '.join(likes) if likes else 'None recorded'}
- Dislikes (MUST AVOID): {', '.join(dislikes) if dislikes else 'None recorded'}
- Preferred Cuisines: {', '.join(cuisines) if cuisines else profile.get('preferred_cuisines', 'Any')}

PREVIOUS WEEK'S MEALS (For Variety - Do Not Repeat):
{chr(10).join(previous_meals) if previous_meals else 'No previous meal history'}

CURRENT INVENTORY:
{json.dumps(inventory_by_category, indent=2)}

INSTRUCTIONS:
1. Create a detailed 7-day meal plan with complete recipes and inventory optimization
2. Generate plans based ONLY on available inventory where possible
3. If a critical item (like protein source) is missing from inventory, explicitly mention it as a REQUIRED PURCHASE
4. Do NOT estimate costs
5. Strictly follow dietary restrictions and allergies
6. **CRITICAL: Respect learned preferences - incorporate likes and COMPLETELY AVOID all dislikes**
7. **IMPORTANT: Provide variety - avoid repeating meals from the previous week's list**
8. Prioritize recipes from preferred cuisines where possible
9. Ensure each day meets the daily nutritional targets
10. Provide variety throughout the week

Return the meal plan in valid JSON format with this EXACT structure:
{{
  "user_summary": {{
    "user_id": "...",
    "health_goal": "...",
    "daily_targets": {{ "calories": 0, "protein_g": 0, "carbohydrates_g": 0, "fat_g": 0, "fiber_g": 0 }},
    "restrictions": [],
    "allergies": []
  }},
  "meal_plan": {{
    "week_summary": {{
      "average_daily_calories": 0,
      "average_daily_protein": 0,
      "average_daily_carbs": 0,
      "average_daily_fat": 0,
      "average_daily_fiber": 0,
      "inventory_utilization_rate": 0,
      "future_suggestions": [
        {{ "item": "Name", "reason": "Why", "category": "Category", "suggested_quantity": 0, "unit": "unit" }}
      ]
    }},
    "days": [
      {{
        "day": 1,
        "day_name": "Day Name",
        "total_nutrition": {{ "calories": 0, "protein_g": 0, "carbohydrates_g": 0, "fat_g": 0, "fiber_g": 0 }},
        "inventory_impact": {{ "items_used": 0, "new_purchases_needed": 0 }},
        "meals": {{
          "breakfast": {{
            "meal_name": "Name",
            "ingredients_with_quantities": [
              {{ "ingredient": "Name", "quantity": 0, "unit": "unit", "from_inventory": false }}
            ],
            "nutrition": {{ "calories": 0, "protein_g": 0, "carbohydrates_g": 0, "fat_g": 0 }},
            "recipe": {{ "prep_steps": [], "cooking_instructions": [] }}
          }},
          "lunch": {{ "meal_name": "Name", "ingredients_with_quantities": [], "nutrition": {{ "calories": 0, "protein_g": 0, "carbohydrates_g": 0, "fat_g": 0 }}, "recipe": {{ "prep_steps": [], "cooking_instructions": [] }} }},
          "snacks": {{ "meal_name": "Name", "ingredients_with_quantities": [], "nutrition": {{ "calories": 0, "protein_g": 0, "carbohydrates_g": 0, "fat_g": 0 }}, "recipe": {{ "prep_steps": [], "cooking_instructions": [] }} }},
          "dinner": {{ "meal_name": "Name", "ingredients_with_quantities": [], "nutrition": {{ "calories": 0, "protein_g": 0, "carbohydrates_g": 0, "fat_g": 0 }}, "recipe": {{ "prep_steps": [], "cooking_instructions": [] }} }}
        }}
      }}
    ]
  }},
  "recommendations": {{
    "hydration": "...",
    "shopping_list_summary": {{
      "proteins": [{{ "item": "Name", "total_quantity_needed": 0, "quantity_in_inventory": 0, "quantity_to_purchase": 0, "unit": "unit" }}],
      "grains": [], "vegetables": [], "fruits": [], "pantry_items": []
    }}
  }},
  "metadata": {{ "generated_at": "ISO date", "version": "1.0" }}
}}"""

            # Store prompt for next agent
            state['user_data']['prompt'] = prompt
            
            print(f"[AGENT 2] Data aggregation complete for {user_id}")
            return state
            
        except Exception as e:
            print(f"[AGENT 2] Error aggregating data for {user_id}: {e}")
            state['errors'].append({
                'agent': 'aggregate_data',
                'user_id': user_id,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return state

    # ==================== AGENT 3: MEAL PLAN GENERATOR ====================
    def agent_generate_meal_plan(self, state: MealPlanGenerationState) -> MealPlanGenerationState:
        """Generate meal plan using the constructed prompt"""
        if not state['user_data'] or 'prompt' not in state['user_data']:
            return state
            
        user_id = state['user_data']['user_id']
        prompt = state['user_data']['prompt']
        profile = state['user_data']['profile']
        
        print(f"[AGENT 3] Generating meal plan for {user_id}")
        
        try:
            # Initialize agent
            agent = MealPlanAgentWithExtraction(self.session)
            
            # Generate plan
            result = agent.generate_meal_plan(
                prompt=prompt,
                user_profile=profile
            )
            
            if result:
                state['generated_plan'] = result
                print(f"[AGENT 3] Successfully generated plan for {user_id}")
            else:
                raise Exception("Agent returned None")
                
            return state
            
        except Exception as e:
            print(f"[AGENT 3] Error generating plan for {user_id}: {e}")
            state['errors'].append({
                'agent': 'generate_plan',
                'user_id': user_id,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            state['generated_plan'] = None
            return state
    
    # ==================== AGENT 4: PLAN PERSISTER ====================
    def agent_persist_plan(self, state: MealPlanGenerationState) -> MealPlanGenerationState:
        """Save generated plan to database with retry logic"""
        # If no user was processed, skip persistence
        if not state.get('current_user'):
            return state

        if not state['generated_plan'] or not state['user_data']:
            state['retry_count'] += 1
            if state['retry_count'] <= self.max_retries:
                print(f"[AGENT 4] Retry {state['retry_count']}/{self.max_retries}")
                return state
            else:
                state['failure_count'] += 1
                state['retry_count'] = 0
                return state
        
        user_id = state['user_data']['user_id']
        plan = state['generated_plan']
        
        print(f"[AGENT 4] Persisting plan for {user_id}")
        
        cursor = self.conn.cursor()
        try:
            # Save meal plan (using existing helpers)
            from utils.helpers import save_meal_plan
            
            # Get schedule_id from user object
            schedule_id = state['current_user'].get('schedule_id')
            
            save_meal_plan(
                conn=self.conn,
                user_id=user_id,
                schedule_id=schedule_id,
                meal_plan_data=plan
            )
            
            # Update planning_schedule
            next_date = datetime.now().date() + timedelta(days=7)
            
            # Deactivate OTHER schedules to ensure no duplicates
            cursor.execute("""
                UPDATE planning_schedule 
                SET status = 'INACTIVE' 
                WHERE user_id = %s AND schedule_id != %s
            """, (user_id, schedule_id))
            
            # Update current schedule
            cursor.execute("""
                UPDATE planning_schedule
                SET next_plan_date = %s
                WHERE schedule_id = %s
            """, (next_date, schedule_id))
            
            self.conn.commit()
            
            state['success_count'] += 1
            state['retry_count'] = 0
            print(f"[AGENT 4] Successfully saved plan for {user_id}")
            
        except Exception as e:
            print(f"[AGENT 4] Error saving plan for {user_id}: {e}")
            self.conn.rollback()
            
            state['retry_count'] += 1
            if state['retry_count'] > self.max_retries:
                state['failure_count'] += 1
                state['errors'].append({
                    'agent': 'persist_plan',
                    'user_id': user_id,
                    'error': str(e),
                    'retries': self.max_retries,
                    'timestamp': datetime.now().isoformat()
                })
                state['retry_count'] = 0
        finally:
            cursor.close()
        
        return state
    
    # ==================== ROUTING LOGIC ====================
    def check_users_available(self, state: MealPlanGenerationState) -> str:
        """Check if any users were found"""
        if state['users_to_process'] and len(state['users_to_process']) > 0:
            return 'process'
        return 'end'

    def route_next_step(self, state: MealPlanGenerationState) -> str:
        """Decide next step: retry, next user, or end"""
        # Check for retry
        if state['retry_count'] > 0 and state['retry_count'] <= self.max_retries:
            return 'retry'
        
        # Move to next user
        state['current_user_index'] += 1
        state['retry_count'] = 0 # Reset retry count for next user
        state['current_user'] = None # Clear current user
        state['user_data'] = None # Clear user data
        state['generated_plan'] = None # Clear plan
        
        if state['current_user_index'] < len(state['users_to_process']):
            return 'next_user'
        
        return 'complete'
    
    # ==================== BUILD WORKFLOW ====================
    def build_workflow(self):
        """Build LangGraph workflow"""
        workflow = StateGraph(MealPlanGenerationState)
        
        # Add nodes
        workflow.add_node("fetch_users", self.agent_fetch_users)
        workflow.add_node("aggregate_data", self.agent_aggregate_user_data)
        workflow.add_node("generate_plan", self.agent_generate_meal_plan)
        workflow.add_node("persist_plan", self.agent_persist_plan)
        
        # Define edges
        workflow.set_entry_point("fetch_users")
        
        # Conditional edge from fetch_users
        workflow.add_conditional_edges(
            "fetch_users",
            self.check_users_available,
            {
                "process": "aggregate_data",
                "end": END
            }
        )
        
        workflow.add_edge("aggregate_data", "generate_plan")
        workflow.add_edge("generate_plan", "persist_plan")
        
        # Conditional routing from persist
        workflow.add_conditional_edges(
            "persist_plan",
            self.route_next_step,
            {
                "retry": "aggregate_data",  # Retry for same user
                "next_user": "aggregate_data",  # Process next user
                "complete": END
            }
        )
        
        return workflow.compile()
    
    # ==================== RUN METHOD ====================
    def run(self, target_date: str = None):
        """Execute the workflow"""
        if not target_date:
            target_date = datetime.now().date().isoformat()
        
        initial_state = MealPlanGenerationState(
            current_date=target_date,
            users_to_process=[],
            current_user_index=0,
            current_user=None,
            user_data=None,
            generated_plan=None,
            success_count=0,
            failure_count=0,
            errors=[],
            retry_count=0
        )
        
        app = self.build_workflow()
        final_state = app.invoke(initial_state)
        
        return final_state
