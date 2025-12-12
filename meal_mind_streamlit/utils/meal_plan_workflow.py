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
import pandas as pd

# Add project root to path (dynamically finds the parent directory of 'utils')
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.db import get_snowflake_connection, get_snowpark_session
from utils.agent import MealPlanAgentWithExtraction
from utils.feedback_agent import FeedbackAgent


# ==================== HELPER FUNCTION ====================
def fix_day_names_with_start_date(meal_plan_data: Dict[str, Any], start_date) -> Dict[str, Any]:
    """Fix day names in meal plan to match actual dates starting from start_date"""
    try:
        days = meal_plan_data.get('meal_plan', {}).get('days', [])
        # Use provided start_date or default to today
        base_date = start_date if start_date else datetime.now().date()
        # Handle if start_date is a datetime object instead of date
        if hasattr(base_date, 'date'):
            base_date = base_date.date()
        for i, day_data in enumerate(days):
            # Calculate the actual date for this day
            current_date = base_date + timedelta(days=i)
            # Get the correct day name from the date
            correct_day_name = current_date.strftime('%A')
            # Update the day_name in the data
            day_data['day_name'] = correct_day_name
            day_data['day'] = i + 1
        return meal_plan_data
    except Exception as e:
        print(f"Could not fix day names: {e}")
        return meal_plan_data


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
                       daily_calories, daily_protein, daily_carbohydrate, daily_fat, daily_fiber,
                       preferred_cuisines, bmi, activity_level
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
                'daily_fiber': profile_row[12],
                'preferred_cuisines': profile_row[13],
                'bmi': profile_row[14],
                'activity_level': profile_row[15],
                'user_id': user_id
            }
            
            # Get inventory
            cursor.execute("""
                SELECT item_name, quantity, unit, category
                FROM inventory
                WHERE user_id = %s AND quantity > 0
            """, (user_id,))
            
            inventory_by_category = {}
            inventory_list = []
            for row in cursor.fetchall():
                category = row[3] or 'Other'
                if category not in inventory_by_category:
                    inventory_by_category[category] = []
                
                item_data = {
                    'item': row[0],
                    'quantity': row[1],
                    'unit': row[2]
                }
                inventory_by_category[category].append(item_data)
                
                # Also store flat list for DataFrame
                inventory_list.append({
                    'item_name': row[0],
                    'quantity': row[1],
                    'unit': row[2],
                    'category': category
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
            
            # Store raw inventory for DataFrame creation
            state['user_data']['inventory_list'] = inventory_list
            
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
        """Generate meal plan using batched generation (Days 1-4, then 5-7)"""
        if not state['user_data']:
            return state
            
        user_id = state['user_data']['user_id']
        profile = state['user_data']['profile']
        inventory_list = state['user_data'].get('inventory_list', [])
        
        print(f"[AGENT 3] Generating meal plan for {user_id}")
        
        try:
            # Initialize agent
            agent = MealPlanAgentWithExtraction(self.session)
            
            # Create DataFrame from inventory list
            inventory_df = pd.DataFrame(inventory_list)
            
            from utils.helpers import generate_comprehensive_meal_plan_prompt
            
            merged_plan = None
            
            if agent.agent:
                # Batch 1: Days 1-4
                print(f"[AGENT 3] Generating Batch 1 for {user_id}...")
                
                # Get strict start date from schedule
                start_date_obj = state.get('current_user', {}).get('next_plan_date')
                if not start_date_obj:
                    start_date_obj = datetime.now().date()
                
                prompt_1 = generate_comprehensive_meal_plan_prompt(profile, inventory_df, start_day=1, num_days=4, start_date_obj=start_date_obj)
                response_1 = agent.agent.invoke({"input": prompt_1})
                raw_1 = agent.process_agent_response(response_1)
                data_1 = agent.extract_json_from_response(raw_1)
                
                # Extract context from Batch 1
                context_str = ""
                if data_1:
                    try:
                        planned_meals = []
                        days = data_1.get('meal_plan', {}).get('days', [])
                        for day in days:
                            meals = day.get('meals', {})
                            for m_type, m_data in meals.items():
                                if isinstance(m_data, dict) and 'meal_name' in m_data:
                                    planned_meals.append(f"{m_data['meal_name']} ({m_type})")
                        
                        if planned_meals:
                            context_str += "Meals planned so far:\n- " + "\n- ".join(planned_meals)
                    except Exception as e:
                        print(f"Error extracting context: {e}")

                # Batch 2: Days 5-7
                print(f"[AGENT 3] Generating Batch 2 for {user_id}...")
                prompt_2 = generate_comprehensive_meal_plan_prompt(
                    profile, 
                    inventory_df, 
                    start_day=5, 
                    num_days=3, 
                    previous_plan_context=context_str,
                    start_date_obj=start_date_obj
                )
                response_2 = agent.agent.invoke({"input": prompt_2})
                raw_2 = agent.process_agent_response(response_2)
                data_2 = agent.extract_json_from_response(raw_2)
                
                # Merge Results
                if data_1 and data_2:
                    merged_plan = data_1
                    
                    # Ensure structure exists in batch 2
                    days_2 = data_2.get('meal_plan', {}).get('days', [])
                    
                    # Append days from batch 2 to batch 1
                    if 'meal_plan' in merged_plan and 'days' in merged_plan['meal_plan']:
                        merged_plan['meal_plan']['days'].extend(days_2)
                        
                    # Merge shopping lists with quantity summation
                    try:
                        sl_1 = merged_plan.get('recommendations', {}).get('shopping_list_summary', {})
                        sl_2 = data_2.get('recommendations', {}).get('shopping_list_summary', {})
                        
                        if sl_1 and sl_2:
                            for category in ['proteins', 'produce', 'pantry', 'grains', 'vegetables', 'fruits', 'dairy_alternatives']:
                                if category in sl_2:
                                    if category not in sl_1:
                                        sl_1[category] = []
                                    
                                    # Create a map of existing items for easy lookup
                                    existing_items = {item['item'].lower(): item for item in sl_1[category] if 'item' in item}
                                    
                                    for new_item in sl_2[category]:
                                        if 'item' not in new_item:
                                            continue
                                            
                                        name = new_item['item'].lower()
                                        if name in existing_items:
                                            # Update quantity if units match (simple check)
                                            existing = existing_items[name]
                                            # Try to sum quantities if they are numbers
                                            try:
                                                q1 = float(existing.get('quantity_to_purchase', 0))
                                                q2 = float(new_item.get('quantity_to_purchase', 0))
                                                existing['quantity_to_purchase'] = q1 + q2
                                                
                                                # Also sum total needed
                                                t1 = float(existing.get('total_quantity_needed', 0))
                                                t2 = float(new_item.get('total_quantity_needed', 0))
                                                existing['total_quantity_needed'] = t1 + t2
                                            except:
                                                pass # Keep original if parsing fails
                                        else:
                                            # Add new item
                                            sl_1[category].append(new_item)
                                            existing_items[name] = new_item
                            
                            # Sum totals
                            sl_1['total_estimated_cost'] = float(sl_1.get('total_estimated_cost', 0)) + float(sl_2.get('total_estimated_cost', 0))
                            sl_1['total_items_from_inventory'] = int(sl_1.get('total_items_from_inventory', 0)) + int(sl_2.get('total_items_from_inventory', 0))
                            sl_1['total_items_to_purchase'] = int(sl_1.get('total_items_to_purchase', 0)) + int(sl_2.get('total_items_to_purchase', 0))
                    except Exception as e:
                        print(f"Error merging shopping lists: {e}")
                        
                    # Recalculate Week Summary (Averages & Utilization)
                    try:
                        all_days = merged_plan.get('meal_plan', {}).get('days', [])
                        week_summary = merged_plan.get('meal_plan', {}).get('week_summary', {})
                        
                        if all_days:
                            # Recalculate Nutritional Averages
                            total_cals = sum(float(d.get('total_nutrition', {}).get('calories', 0)) for d in all_days)
                            total_prot = sum(float(d.get('total_nutrition', {}).get('protein_g', 0)) for d in all_days)
                            total_carbs = sum(float(d.get('total_nutrition', {}).get('carbohydrates_g', 0)) for d in all_days)
                            total_fat = sum(float(d.get('total_nutrition', {}).get('fat_g', 0)) for d in all_days)
                            total_fiber = sum(float(d.get('total_nutrition', {}).get('fiber_g', 0)) for d in all_days)
                            
                            num_days = len(all_days)
                            week_summary['average_daily_calories'] = int(total_cals / num_days)
                            week_summary['average_daily_protein'] = round(total_prot / num_days, 1)
                            week_summary['average_daily_carbs'] = round(total_carbs / num_days, 1)
                            week_summary['average_daily_fat'] = round(total_fat / num_days, 1)
                            week_summary['average_daily_fiber'] = round(total_fiber / num_days, 1)
                            
                            # Recalculate Inventory Utilization
                            # Utilization = (Items Used / Total Inventory Items) * 100
                            total_inventory_count = len(inventory_df) if not inventory_df.empty else 0
                            items_used_count = int(merged_plan.get('recommendations', {}).get('shopping_list_summary', {}).get('total_items_from_inventory', 0))
                            
                            if total_inventory_count > 0:
                                utilization_rate = (items_used_count / total_inventory_count) * 100
                                week_summary['inventory_utilization_rate'] = round(min(utilization_rate, 100), 1)
                            else:
                                week_summary['inventory_utilization_rate'] = 0
                                
                    except Exception as e:
                        print(f"Error recalculating week summary: {e}")
                        
                    # Validate merged structure
                    if agent.validate_meal_plan_structure(merged_plan):
                        merged_plan = fix_day_names_with_start_date(merged_plan, start_date_obj)
                    else:
                        print("Merged meal plan structure is invalid")
                        merged_plan = None
                else:
                     print("Failed to generate one of the batches")
                     merged_plan = None
            
            if merged_plan:
                state['generated_plan'] = merged_plan
                print(f"[AGENT 3] Successfully generated plan for {user_id}")
            else:
                print(f"[AGENT 3] Failed to generate plan, using mock")
                state['generated_plan'] = agent.generate_mock_meal_plan(profile)
                
            return state
            
        except Exception as e:
            print(f"[AGENT 3] Error generating plan for {user_id}: {e}")
            state['errors'].append({
                'agent': 'generate_plan',
                'user_id': user_id,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            # Fallback to mock on error
            try:
                agent = MealPlanAgentWithExtraction(self.session)
                state['generated_plan'] = agent.generate_mock_meal_plan(profile)
            except:
                state['generated_plan'] = None
            return state

    # ==================== AGENT 3.5: SHOPPING LIST CONSOLIDATOR ====================
    def agent_consolidate_shopping_list(self, state: MealPlanGenerationState) -> MealPlanGenerationState:
        """Consolidate shopping list to merge duplicates and normalize units"""
        if not state.get('generated_plan'):
            return state
            
        print(f"[AGENT 3.5] Consolidating shopping list...")
        
        try:
            plan = state['generated_plan']
            shopping_list = plan.get('recommendations', {}).get('shopping_list_summary', {})
            
            if not shopping_list:
                return state
                
            # Initialize agent
            agent = MealPlanAgentWithExtraction(self.session)
            if not agent.agent:
                return state
                
            prompt = f"""
            Analyze and consolidate this shopping list to merge duplicate items and normalize units.
            
            CURRENT LIST:
            {json.dumps(shopping_list, indent=2)}
            
            INSTRUCTIONS:
            1. Merge items that are the same but named slightly differently (e.g., "Onions" vs "Onion", "2 medium" vs "40g").
            2. If units are compatible (e.g., grams and kg, or count), sum the quantities.
            3. If units are different and hard to convert (e.g., "bunch" vs "g"), keep the most descriptive one or try to estimate.
            4. Ensure the output has the EXACT same JSON structure as the input (keys: proteins, produce, pantry, grains, vegetables, fruits, dairy_alternatives).
            5. Return ONLY the JSON object.
            """
            
            response = agent.agent.invoke({"input": prompt})
            raw_response = agent.process_agent_response(response)
            consolidated_list = agent.extract_json_from_response(raw_response)
            
            if consolidated_list and isinstance(consolidated_list, dict):
                # Update the plan with consolidated list
                state['generated_plan']['recommendations']['shopping_list_summary'] = consolidated_list
                print(f"[AGENT 3.5] Shopping list consolidated successfully")
            else:
                print(f"[AGENT 3.5] Failed to parse consolidated list, keeping original")
                
            return state
            
        except Exception as e:
            print(f"[AGENT 3.5] Error consolidating shopping list: {e}")
            # On error, just return state with original list
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
            
            # Get schedule_id and next_plan_date from user object
            schedule_id = state['current_user'].get('schedule_id')
            next_plan_date = state['current_user'].get('next_plan_date')
            
            save_meal_plan(
                conn=self.conn,
                user_id=user_id,
                schedule_id=schedule_id,
                meal_plan_data=plan,
                start_date=next_plan_date
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
        workflow.add_node("consolidate_list", self.agent_consolidate_shopping_list)
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
        workflow.add_edge("generate_plan", "consolidate_list")
        workflow.add_edge("consolidate_list", "persist_plan")
        
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
