import streamlit as st
import json
import re
from typing import Dict, Any, Optional, List, TypedDict
from langchain_community.chat_models import ChatSnowflakeCortex
from langchain_snowflake.agents import SnowflakeCortexAgent
from langchain.schema import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from datetime import datetime, timedelta

# ==================== LANGGRAPH STATE ====================
class MealPlanState(TypedDict):
    user_profile: Dict
    inventory_df: Any # pd.DataFrame
    prompt: str
    meal_plan_json: Optional[Dict]
    suggestions_json: Optional[List]
    error: Optional[str]


# ==================== MEAL PLAN AGENT WITH JSON EXTRACTION ====================
class MealPlanAgentWithExtraction:
    """Enhanced agent that uses ChatSnowflakeCortex to extract clean JSON from agent responses"""

    def __init__(self, session):
        self.session = session

        try:
            # Initialize the main agent
            # Connecting to existing Cortex Agent in Snowflake
            self.agent = SnowflakeCortexAgent(
                session=self.session,
                name="MEAL_GENERATION",
                database="MEAL_MIND_COMBINED",
                schema="RAW_SCHEMA"
            )
        except Exception as e:
            st.warning(f"Agent initialization failed: {e}. Using fallback mode.")
            self.agent = None

    def process_agent_response(self, response: Any) -> str:
        """Process agent response to get clean output"""
        
        # 1. Extract raw content/data
        data = response
        if hasattr(response, 'content'):
            data = response.content
        elif hasattr(response, 'return_values'):
            data = response.return_values.get('output', str(response))
        elif isinstance(response, dict) and 'output' in response:
            data = response['output']
            
        # 2. If data is already a list, process it
        if isinstance(data, list):
            return self._process_list_response(data)
            
        # 3. If data is a string, it might be a JSON string of a list
        if isinstance(data, str):
            try:
                # Try to parse string as JSON
                parsed = json.loads(data)
                if isinstance(parsed, list):
                    return self._process_list_response(parsed)
            except:
                # Not valid JSON, try ast.literal_eval for python-style lists
                try:
                    import ast
                    parsed = ast.literal_eval(data)
                    if isinstance(parsed, list):
                        return self._process_list_response(parsed)
                except:
                    pass
                
        # 4. Fallback: treat as string and clean it
        return self._clean_string_response(str(data))

    def _process_list_response(self, data: List[Dict[str, Any]]) -> str:
        """Process list response (agent steps)"""
        results = []
        for item in data:
            if isinstance(item, dict):
                # Handle thinking blocks - SKIP THEM
                if 'thinking' in item:
                    continue
                
                # Handle tool_use blocks - SKIP THEM
                elif 'tool_use' in item:
                    continue

                # Handle tool_result blocks - SKIP THEM (we only want final answer)
                elif 'tool_result' in item:
                    continue

                # Handle direct content
                elif 'content' in item:
                    content = item['content']
                    if isinstance(content, list):
                        for content_item in content:
                            if isinstance(content_item, dict) and 'text' in content_item:
                                results.append(content_item['text'])
                            elif isinstance(content_item, str):
                                results.append(content_item)
                    elif isinstance(content, str):
                        results.append(content)
                elif 'text' in item:
                    results.append(item['text'])

        combined_text = '\n\n'.join(results) if results else "No clear response found"
        return self._clean_string_response(combined_text)

    def _clean_string_response(self, content: str) -> str:
        """Clean string response"""
        # Remove markdown code blocks
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)
        
        # Remove any remaining thinking blocks if they leaked into string
        content = re.sub(r'\[\'thinking\'.*?\]', '', content, flags=re.DOTALL)
        
        return content.strip()

    def extract_json_from_response(self, raw_response: str) -> Optional[Any]:
        """Extract JSON from response string"""
        try:
            # Clean up the string first
            cleaned = raw_response.strip()
            
            # Try parsing the whole string first
            try:
                return json.loads(cleaned)
            except:
                pass

            # Try to find a list block [...]
            list_match = re.search(r'\[.*\]', cleaned, re.DOTALL)
            if list_match:
                try:
                    return json.loads(list_match.group())
                except:
                    pass

            # Try to find an object block {...}
            obj_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if obj_match:
                try:
                    return json.loads(obj_match.group())
                except:
                    pass
            
            return None
        except Exception as e:
            print(f"JSON Extraction Error: {e}")
            print(f"Failed to parse string: {raw_response[:500]}...") 
            return None

    def validate_meal_plan_structure(self, meal_plan_data: Dict[str, Any]) -> bool:
        """Validate meal plan structure"""
        required_keys = ['user_summary', 'meal_plan', 'recommendations', 'metadata']

        for key in required_keys:
            if key not in meal_plan_data:
                return False

        if 'days' not in meal_plan_data.get('meal_plan', {}):
            return False

        days = meal_plan_data['meal_plan'].get('days', [])
        if len(days) < 1:
            return False

        return True

    def fix_day_names_in_plan(self, meal_plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fix day names in meal plan to match actual dates starting from today"""
        try:
            days = meal_plan_data.get('meal_plan', {}).get('days', [])
            for i, day_data in enumerate(days):
                # Calculate the actual date for this day
                current_date = datetime.now().date() + timedelta(days=i)
                # Get the correct day name from the date
                correct_day_name = current_date.strftime('%A')
                # Update the day_name in the data
                day_data['day_name'] = correct_day_name
                day_data['day'] = i + 1
            return meal_plan_data
        except Exception as e:
            st.warning(f"Could not fix day names: {e}")
            return meal_plan_data

    def generate_meal_plan(self, prompt: str, user_profile: Dict) -> Optional[Dict[str, Any]]:
        """Main method to generate meal plan with JSON extraction"""

        try:
            # Try agent if available
            if self.agent:
                with st.spinner("🤖 Consulting the meal planning agent..."):
                    agent_response = self.agent.invoke({"input": prompt})
                    
                    # Process response to get clean text
                    raw_response = self.process_agent_response(agent_response)

                    with st.spinner("📝 Parsing meal plan data..."):
                        meal_plan_data = self.extract_json_from_response(raw_response)

                    if meal_plan_data and self.validate_meal_plan_structure(meal_plan_data):
                        # Post-process to fix day names to match actual dates
                        meal_plan_data = self.fix_day_names_in_plan(meal_plan_data)
                        return meal_plan_data
                    else:
                        st.error("Could not parse valid JSON from agent response.")
                        with st.expander("Debug: Raw Agent Response"):
                            st.code(raw_response)
                        return None

            # If agent is not available or no valid response, return None
            return None

        except Exception as e:
            st.error(f"Error in meal plan generation: {e}")
            return self.generate_mock_meal_plan(user_profile)

    def generate_standalone_suggestions(self, user_profile: Dict, current_plan_summary: str) -> List[Dict]:
        """Generate suggestions for an existing plan"""
        prompt = f"""
        Based on the user's profile and their current meal plan, suggest 5-10 inventory items for NEXT week.
        
        USER PROFILE:
        - Goal: {user_profile['health_goal']}
        - Activity: {user_profile['activity_level']}
        - Restrictions: {user_profile['dietary_restrictions']}
        - Allergies: {user_profile['food_allergies']}
        
        CURRENT PLAN SUMMARY:
        {current_plan_summary}
        
        TASK:
        Generate a list of 5-10 items to buy for NEXT week to improve variety and hit their goals.
        - Ensure these items are NOT currently in inventory (assume current plan uses most of it).
        - Strictly respect allergies/restrictions.
        - EXPLICITLY link each suggestion to the user's health goal.
        
        Return ONLY a JSON list of objects with this format:
        [{{"item": "Name", "reason": "Why (linking to goal)", "category": "Category", "suggested_quantity": 0, "unit": "unit"}}]
        """
        
        try:
            if self.agent:
                response = self.agent.invoke({"input": prompt})
                raw_response = self.process_agent_response(response)
                data = self.extract_json_from_response(raw_response)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and 'future_suggestions' in data:
                    return data['future_suggestions']
            return []
        except Exception as e:
            st.error(f"Error generating suggestions: {e}")
            return []

    # ==================== LANGGRAPH NODES ====================
    def node_generate_plan(self, state: MealPlanState) -> MealPlanState:
        """Node 1: Generate the core meal plan"""
        print("--- Node: Generate Meal Plan ---")
        try:
            prompt = state['prompt']
            user_profile = state['user_profile']
            
            if self.agent:
                response = self.agent.invoke({"input": prompt})
                raw_response = self.process_agent_response(response)
                meal_plan_data = self.extract_json_from_response(raw_response)
                
                if meal_plan_data and self.validate_meal_plan_structure(meal_plan_data):
                    meal_plan_data = self.fix_day_names_in_plan(meal_plan_data)
                    state['meal_plan_json'] = meal_plan_data
                else:
                    state['error'] = "Failed to parse meal plan JSON"
            else:
                # Fallback to mock
                state['meal_plan_json'] = self.generate_mock_meal_plan(user_profile)
                
        except Exception as e:
            state['error'] = str(e)
            state['meal_plan_json'] = self.generate_mock_meal_plan(state['user_profile'])
            
        return state

    def node_generate_suggestions(self, state: MealPlanState) -> MealPlanState:
        """Node 2: Generate suggestions based on the plan"""
        print("--- Node: Generate Suggestions ---")
        
        # If plan generation failed or we are using mock, we might skip or use mock suggestions
        if state.get('error') or not state.get('meal_plan_json'):
            # If mock plan was generated in previous step, we can still generate suggestions or mock them
            pass

        try:
            user_profile = state['user_profile']
            meal_plan = state['meal_plan_json']
            
            if not meal_plan:
                print("No meal plan generated, skipping suggestions.")
                state['suggestions_json'] = []
                return state
            
            # Create a summary of the generated plan
            week_summary = meal_plan.get('meal_plan', {}).get('week_summary', {})
            utilization = week_summary.get('inventory_utilization_rate', 0)
            plan_summary = f"Current Plan Inventory Utilization: {utilization}%. The plan covers 7 days."
            
            # Reuse the standalone logic
            suggestions = self.generate_standalone_suggestions(user_profile, plan_summary)
            state['suggestions_json'] = suggestions
            
        except Exception as e:
            print(f"Error in suggestion node: {e}")
            state['suggestions_json'] = []
            
        return state

    def build_graph(self):
        """Build the LangGraph workflow"""
        workflow = StateGraph(MealPlanState)
        
        # Add nodes
        workflow.add_node("generate_plan", self.node_generate_plan)
        workflow.add_node("generate_suggestions", self.node_generate_suggestions)
        
        # Add edges
        workflow.set_entry_point("generate_plan")
        workflow.add_edge("generate_plan", "generate_suggestions")
        workflow.add_edge("generate_suggestions", END)
        
        return workflow.compile()

    def generate_mock_meal_plan(self, user_profile: Dict) -> Dict[str, Any]:
        """Generate a realistic mock meal plan"""
        days = []
        
        # Calculate day names based on actual dates starting from today
        for i in range(7):
            current_date = datetime.now().date() + timedelta(days=i)
            day_name = current_date.strftime('%A')  # Get the actual day name (Monday, Tuesday, etc.)
            
            days.append({
                "day": i + 1,
                "day_name": day_name,
                "total_nutrition": {
                    "calories": user_profile['daily_calories'],
                    "protein_g": user_profile['daily_protein'],
                    "carbohydrates_g": user_profile['daily_carbohydrate'],
                    "fat_g": user_profile['daily_fat'],
                    "fiber_g": user_profile['daily_fiber']
                },
                "inventory_impact": {
                    "items_used": 5,
                    "new_purchases_needed": 8
                },
                "meals": {
                    "breakfast": self.create_sample_meal("breakfast", user_profile),
                    "lunch": self.create_sample_meal("lunch", user_profile),
                    "snacks": self.create_sample_meal("snacks", user_profile),
                    "dinner": self.create_sample_meal("dinner", user_profile)
                }
            })

        return {
            "user_summary": {
                "user_id": user_profile.get('user_id', ''),
                "health_goal": user_profile.get('health_goal', 'General Health'),
                "daily_targets": {
                    "calories": user_profile['daily_calories'],
                    "protein_g": user_profile['daily_protein'],
                    "carbohydrates_g": user_profile['daily_carbohydrate'],
                    "fat_g": user_profile['daily_fat'],
                    "fiber_g": user_profile['daily_fiber']
                },
                "restrictions": user_profile.get('dietary_restrictions', '').split(', '),
                "allergies": user_profile.get('food_allergies', '').split(', '),
                "inventory_summary": {
                    "total_items": 25,
                    "categories_available": ["Proteins", "Grains", "Vegetables", "Fruits"],
                    "inventory_value": 85.50
                }
            },
            "meal_plan": {
                "week_summary": {
                    "average_daily_calories": user_profile['daily_calories'],
                    "average_daily_protein": user_profile['daily_protein'],
                    "average_daily_carbs": user_profile['daily_carbohydrate'],
                    "average_daily_fat": user_profile['daily_fat'],
                    "average_daily_fiber": user_profile['daily_fiber'],
                    "total_inventory_items_used": 35,
                    "inventory_utilization_rate": 65,
                    "future_suggestions": [
                        {"item": "Avocado", "reason": "Healthy fats for breakfast variety", "category": "Produce", "suggested_quantity": 2, "unit": "pieces"},
                        {"item": "Sweet Potato", "reason": "Complex carbs alternative", "category": "Produce", "suggested_quantity": 1, "unit": "kg"},
                        {"item": "Almonds", "reason": "Protein-rich snack", "category": "Pantry", "suggested_quantity": 200, "unit": "g"}
                    ]
                },
                "days": days
            },
            "recommendations": {
                "hydration": f"Drink {int(user_profile.get('weight_kg', 70) * 35)}ml of water daily",
                "meal_prep_tips": [
                    "Prep vegetables on Sunday for the week",
                    "Cook grains in bulk and portion them",
                    "Marinate proteins the night before"
                ],
                "substitution_options": [
                    "Swap chicken for turkey or tofu",
                    "Replace rice with quinoa for more protein"
                ],
                "weekly_prep_schedule": {
                    "sunday_prep": ["Wash and chop vegetables", "Cook grains", "Prepare marinades"],
                    "wednesday_prep": ["Refresh vegetable prep", "Prepare snacks"]
                },
                "inventory_usage": {
                    "high_quantity_items_used": [],
                    "total_inventory_utilized": 65,
                    "waste_reduction_achieved": 85
                },
                "shopping_list_summary": {
                    "proteins": [
                        {"item": "Salmon", "total_quantity_needed": 540, "quantity_in_inventory": 0,
                         "quantity_to_purchase": 540, "unit": "g"}
                    ],
                    "grains": [
                        {"item": "Quinoa", "total_quantity_needed": 300, "quantity_in_inventory": 100,
                         "quantity_to_purchase": 200, "unit": "g"}
                    ],
                    "vegetables": [],
                    "fruits": [],
                    "dairy_alternatives": [],
                    "pantry_items": [],
                    "total_items_from_inventory": 15,
                    "total_items_to_purchase": 25
                },
                "batch_cooking_suggestions": [
                    "Cook all grains at once",
                    "Grill proteins for first 3 days"
                ]
            },
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "plan_id": "mock_id",
                "version": "1.0",
                "agent_version": "MOCK_v1",
                "inventory_snapshot_id": "mock_inv_id",
                "projected_inventory_status": {
                    "items_to_be_consumed": 35,
                    "items_to_be_purchased": 25,
                    "inventory_efficiency_score": 65
                }
            }
        }

    def create_sample_meal(self, meal_type: str, user_profile: Dict) -> Dict:
        """Create a sample meal based on type"""
        meal_templates = {
            "breakfast": {
                "name": "Protein Oatmeal Bowl",
                "prep": 5, "cook": 10,
                "calories": int(user_profile['daily_calories'] * 0.25),
                "protein": int(user_profile['daily_protein'] * 0.25)
            },
            "lunch": {
                "name": "Grilled Chicken Salad",
                "prep": 15, "cook": 15,
                "calories": int(user_profile['daily_calories'] * 0.35),
                "protein": int(user_profile['daily_protein'] * 0.35)
            },
            "snacks": {
                "name": "Greek Yogurt with Berries",
                "prep": 2, "cook": 0,
                "calories": int(user_profile['daily_calories'] * 0.10),
                "protein": int(user_profile['daily_protein'] * 0.10)
            },
            "dinner": {
                "name": "Baked Salmon with Vegetables",
                "prep": 15, "cook": 25,
                "calories": int(user_profile['daily_calories'] * 0.30),
                "protein": int(user_profile['daily_protein'] * 0.30)
            }
        }

        template = meal_templates.get(meal_type, meal_templates["lunch"])

        return {
            "meal_name": template["name"],
            "meal_id": "mock_meal_id",
            "ingredients_with_quantities": [
                {"ingredient": "Main protein", "quantity": 150, "unit": "g", "from_inventory": False,
                 "inventory_item_id": None},
                {"ingredient": "Vegetables", "quantity": 200, "unit": "g", "from_inventory": True,
                 "inventory_item_id": "inv_123"},
                {"ingredient": "Grains/Carbs", "quantity": 100, "unit": "g", "from_inventory": False,
                 "inventory_item_id": None}
            ],
            "preparation_time": template["prep"],
            "cooking_time": template["cook"],
            "nutrition": {
                "calories": template["calories"],
                "protein_g": template["protein"],
                "carbohydrates_g": template["calories"] * 0.5 / 4,
                "fat_g": template["calories"] * 0.3 / 9,
                "fiber_g": 8
            },
            "serving_size": "1 serving",
            "servings": 1,
            "recipe": {
                "prep_steps": [
                    "Gather all ingredients",
                    "Wash and chop vegetables",
                    "Season proteins"
                ],
                "cooking_instructions": [
                    "Preheat cooking surface",
                    "Cook protein to safe temperature",
                    "Prepare sides",
                    "Plate and serve"
                ],
                "equipment_needed": ["Pan", "Cutting board", "Knife"],
                "difficulty_level": "easy",
                "tips": ["Prep ahead for faster cooking", "Season to taste"]
            }
        }
