"""
Meal Mind - AI-Powered Personalized Nutrition Intelligence System
Complete Application with Snowflake Agent Integration and JSON Extraction
"""

import streamlit as st
import snowflake.connector
from snowflake.snowpark import Session
import pandas as pd
import requests
import hashlib
from datetime import datetime, timedelta
import uuid
import json
import os
import re
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from langchain_community.chat_models import ChatSnowflakeCortex
from langchain_snowflake.agents import SnowflakeCortexAgent
from langchain.schema import HumanMessage, SystemMessage

load_dotenv()

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="Meal Mind - AI Nutrition Planner",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==================== CUSTOM CSS ====================
st.markdown("""
<style>
    .meal-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        color: #31333F;
    }
    .meal-card h4 {
        color: #31333F !important;
        margin: 0;
    }
    .nutrition-badge {
        display: inline-block;
        padding: 5px 10px;
        margin: 2px;
        background-color: #e9ecef;
        border-radius: 15px;
        font-size: 12px;
        color: #31333F;
    }
    .recipe-step {
        padding: 8px;
        margin: 5px 0;
        background-color: #ffffff;
        border-left: 3px solid #007bff;
        color: #31333F;
    }
    .inventory-item {
        background-color: #f0f2f5;
        padding: 10px;
        border-radius: 8px;
        margin: 5px 0;
        color: #31333F;
    }
    .progress-indicator {
        padding: 10px;
        background-color: #e7f3ff;
        border-radius: 5px;
        margin: 10px 0;
        color: #31333F;
    }
</style>
""", unsafe_allow_html=True)


# ==================== DATABASE SETUP ====================
def create_tables(conn):
    """Create all necessary tables if they don't exist"""
    cursor = conn.cursor()

    try:
        # Users table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS users
                       (
                           user_id
                           VARCHAR
                       (
                           50
                       ) PRIMARY KEY,
                           username VARCHAR
                       (
                           100
                       ) UNIQUE NOT NULL,
                           password_hash VARCHAR
                       (
                           255
                       ) NOT NULL,
                           email VARCHAR
                       (
                           255
                       ),
                           age INT,
                           gender VARCHAR
                       (
                           20
                       ),
                           height_cm FLOAT,
                           weight_kg FLOAT,
                           bmi FLOAT,
                           life_stage VARCHAR
                       (
                           50
                       ),
                           pregnancy_status VARCHAR
                       (
                           50
                       ),
                           lactation_status VARCHAR
                       (
                           50
                       ),
                           activity_level VARCHAR
                       (
                           50
                       ),
                           health_goal VARCHAR
                       (
                           100
                       ),
                           dietary_restrictions TEXT,
                           food_allergies TEXT,
                           daily_calories INT,
                           daily_protein FLOAT,
                           daily_carbohydrate FLOAT,
                           daily_fat FLOAT,
                           daily_fiber FLOAT,
                           profile_completed BOOLEAN DEFAULT FALSE,
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       (
                       ),
                           last_login TIMESTAMP,
                           updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       (
                       )
                           )
                       """)

        # Planning Schedule
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS planning_schedule
                       (
                           schedule_id
                           VARCHAR
                       (
                           50
                       ) PRIMARY KEY,
                           user_id VARCHAR
                       (
                           50
                       ) NOT NULL,
                           plan_start_date DATE NOT NULL,
                           plan_end_date DATE NOT NULL,
                           next_plan_date DATE NOT NULL,
                           status VARCHAR
                       (
                           20
                       ) DEFAULT 'ACTIVE',
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       (
                       ),
                           FOREIGN KEY
                       (
                           user_id
                       ) REFERENCES users
                       (
                           user_id
                       )
                           )
                       """)

        # Inventory
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS inventory
                       (
                           inventory_id
                           VARCHAR
                       (
                           50
                       ) PRIMARY KEY,
                           user_id VARCHAR
                       (
                           50
                       ) NOT NULL,
                           item_name VARCHAR
                       (
                           255
                       ) NOT NULL,
                           quantity FLOAT NOT NULL,
                           unit VARCHAR
                       (
                           50
                       ) NOT NULL,
                           category VARCHAR
                       (
                           100
                       ),
                           notes TEXT,
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       (
                       ),
                           updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       (
                       ),
                           FOREIGN KEY
                       (
                           user_id
                       ) REFERENCES users
                       (
                           user_id
                       )
                           )
                       """)

        # Meal Plans
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS meal_plans
                       (
                           plan_id
                           VARCHAR
                       (
                           50
                       ) PRIMARY KEY,
                           user_id VARCHAR
                       (
                           50
                       ) NOT NULL,
                           schedule_id VARCHAR
                       (
                           50
                       ),
                           plan_name VARCHAR
                       (
                           255
                       ),
                           start_date DATE NOT NULL,
                           end_date DATE NOT NULL,
                           week_summary VARIANT,
                           status VARCHAR
                       (
                           20
                       ) DEFAULT 'ACTIVE',
                           generated_by VARCHAR
                       (
                           50
                       ) DEFAULT 'AGENT',
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       (
                       ),
                           FOREIGN KEY
                       (
                           user_id
                       ) REFERENCES users
                       (
                           user_id
                       ),
                           FOREIGN KEY
                       (
                           schedule_id
                       ) REFERENCES planning_schedule
                       (
                           schedule_id
                       )
                           )
                       """)

        # Daily Meals
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS daily_meals
                       (
                           meal_id
                           VARCHAR
                       (
                           50
                       ) PRIMARY KEY,
                           plan_id VARCHAR
                       (
                           50
                       ) NOT NULL,
                           user_id VARCHAR
                       (
                           50
                       ) NOT NULL,
                           day_number INT NOT NULL,
                           day_name VARCHAR
                       (
                           20
                       ),
                           meal_date DATE,
                           total_nutrition VARIANT,
                           inventory_impact VARIANT,
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       (
                       ),
                           FOREIGN KEY
                       (
                           plan_id
                       ) REFERENCES meal_plans
                       (
                           plan_id
                       ),
                           FOREIGN KEY
                       (
                           user_id
                       ) REFERENCES users
                       (
                           user_id
                       )
                           )
                       """)

        # Meal Details
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS meal_details
                       (
                           detail_id
                           VARCHAR
                       (
                           50
                       ) PRIMARY KEY,
                           meal_id VARCHAR
                       (
                           50
                       ) NOT NULL,
                           meal_type VARCHAR
                       (
                           20
                       ) NOT NULL,
                           meal_name VARCHAR
                       (
                           255
                       ) NOT NULL,
                           ingredients_with_quantities VARIANT,
                           recipe VARIANT,
                           nutrition VARIANT,
                           preparation_time INT,
                           cooking_time INT,
                           servings INT,
                           serving_size VARCHAR
                       (
                           100
                       ),
                           difficulty_level VARCHAR
                       (
                           20
                       ),
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       (
                       ),
                           FOREIGN KEY
                       (
                           meal_id
                       ) REFERENCES daily_meals
                       (
                           meal_id
                       )
                           )
                       """)

        # Shopping Lists
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS shopping_lists
                       (
                           list_id
                           VARCHAR
                       (
                           50
                       ) PRIMARY KEY,
                           plan_id VARCHAR
                       (
                           50
                       ) NOT NULL,
                           user_id VARCHAR
                       (
                           50
                       ) NOT NULL,
                           shopping_data VARIANT,
                           total_estimated_cost FLOAT,
                           total_items_from_inventory INT,
                           total_items_to_purchase INT,
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       (
                       ),
                           FOREIGN KEY
                       (
                           plan_id
                       ) REFERENCES meal_plans
                       (
                           plan_id
                       ),
                           FOREIGN KEY
                       (
                           user_id
                       ) REFERENCES users
                       (
                           user_id
                       )
                           )
                       """)

        conn.commit()
    except Exception as e:
        st.error(f"Error creating tables: {e}")
    finally:
        cursor.close()


# ==================== CONNECTION ====================
@st.cache_resource
def get_snowflake_connection():
    """Get Snowflake connection"""
    try:
        conn = snowflake.connector.connect(
            user=os.getenv('SNOWFLAKE_USER'),
            account=os.getenv('SNOWFLAKE_ACCOUNT'),
            password=os.getenv('SNOWFLAKE_PASSWORD'),
            warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
            database=os.getenv('SNOWFLAKE_DATABASE'),
            schema=os.getenv('SNOWFLAKE_SCHEMA')
        )
        create_tables(conn)
        return conn
    except Exception as e:
        st.error(f"Failed to connect to Snowflake: {e}")
        st.stop()


@st.cache_resource
def get_snowpark_session():
    """Get Snowpark Session"""
    try:
        connection_params = {
            "user": os.getenv('SNOWFLAKE_USER'),
            "account": os.getenv('SNOWFLAKE_ACCOUNT'),
            "password": os.getenv('SNOWFLAKE_PASSWORD'),
            "warehouse": os.getenv('SNOWFLAKE_WAREHOUSE'),
            "database": os.getenv('SNOWFLAKE_DATABASE'),
            "schema": os.getenv('SNOWFLAKE_SCHEMA'),
            "role": os.getenv('SNOWFLAKE_ROLE')
        }
        session = Session.builder.configs(connection_params).create()
        return session
    except Exception as e:
        st.error(f"Failed to create Snowpark Session: {e}")
        st.stop()


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
                "plan_id": str(uuid.uuid4()),
                "version": "1.0",
                "agent_version": "MOCK_v1",
                "inventory_snapshot_id": str(uuid.uuid4()),
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
            "meal_id": str(uuid.uuid4()),
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


# ==================== AUTHENTICATION ====================
def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def create_user_account(conn, username, password, email=None):
    """Create new user account"""
    cursor = conn.cursor()
    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)

    try:
        cursor.execute("""
                       INSERT INTO users (user_id, username, password_hash, email, profile_completed)
                       VALUES (%s, %s, %s, %s, FALSE)
                       """, (user_id, username, password_hash, email))
        conn.commit()
        cursor.close()
        return True, user_id
    except Exception as e:
        cursor.close()
        if "unique constraint" in str(e).lower():
            return False, "Username already exists"
        return False, str(e)


def authenticate_user(conn, username, password):
    """Authenticate user login"""
    cursor = conn.cursor()
    password_hash = hash_password(password)

    cursor.execute("""
                   SELECT user_id, username, profile_completed
                   FROM users
                   WHERE username = %s
                     AND password_hash = %s
                   """, (username, password_hash))

    result = cursor.fetchone()

    if result:
        cursor.execute("""
                       UPDATE users
                       SET last_login = CURRENT_TIMESTAMP()
                       WHERE user_id = %s
                       """, (result[0],))
        conn.commit()
        cursor.close()
        return True, result[0], result[1], result[2]

    cursor.close()
    return False, None, None, None


# ==================== NUTRITION API ====================
RAPIDAPI_KEY = "aa03950e0emshbe5be62d4b8a130p10ba64jsn7ada38029b57"
RAPIDAPI_HOST = "nutrition-calculator.p.rapidapi.com"


def get_nutrition_info_from_api(age, gender, height_cm, weight_kg, activity_level, pregnancy, lactation):
    """Get DRI nutrition info from RapidAPI"""
    url = "https://nutrition-calculator.p.rapidapi.com/api/nutrition-info"

    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }

    total_inches = height_cm / 2.54
    feet = int(total_inches // 12)
    inches = int(total_inches % 12)
    lbs = int(weight_kg * 2.20462)

    activity_map = {
        "Sedentary": "Sedentary",
        "Lightly active": "Light",
        "Moderately active": "Moderate",
        "Very active": "Active",
        "Extremely active": "Very Active"
    }

    params = {
        "measurement_units": "std",
        "sex": gender.lower(),
        "age_value": str(age),
        "age_type": "yrs",
        "feet": str(feet),
        "inches": str(inches),
        "lbs": str(lbs),
        "activity_level": activity_map.get(activity_level, "Moderate")
    }

    if pregnancy != "Not Pregnant":
        params["pregnancy_status"] = "pregnant"
        if "1st" in pregnancy:
            params["trimester"] = "1"
        elif "2nd" in pregnancy:
            params["trimester"] = "2"
        elif "3rd" in pregnancy:
            params["trimester"] = "3"

    if lactation != "Not Lactating":
        params["lactation_status"] = "lactating"

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def parse_macro_value(macro_table, nutrient_name):
    """Extract nutrient value from macronutrients table"""
    try:
        for row in macro_table[1:]:
            if row[0] == nutrient_name:
                value_str = row[1]
                if '-' in value_str:
                    first_value = value_str.split('-')[0].strip().split()[0]
                    return float(first_value.replace(',', ''))
                else:
                    value = value_str.split()[0]
                    return float(value.replace(',', ''))
        return 0
    except:
        return 0


def calculate_manual(age, gender, weight, height, activity, goal):
    """Manual calculation as backup"""
    height_m = height / 100
    bmi = round(weight / (height_m ** 2), 1)

    if gender == "Male":
        bmr = 88.362 + (13.397 * weight) + (4.799 * height) - (5.677 * age)
    else:
        bmr = 447.593 + (9.247 * weight) + (3.098 * height) - (4.330 * age)

    multipliers = {
        "Sedentary": 1.2,
        "Lightly active": 1.375,
        "Moderately active": 1.55,
        "Very active": 1.725,
        "Extremely active": 1.9
    }

    calories = int(bmr * multipliers.get(activity, 1.2))

    if goal == "Weight Loss":
        calories -= 500
    elif goal in ["Weight Gain", "Muscle Gain"]:
        calories += 500

    protein = round(weight * 1.6, 1)
    fat = round((calories * 0.25) / 9, 1)
    carbs = round((calories - (protein * 4) - (fat * 9)) / 4, 1)

    return {
        'bmi': bmi,
        'daily_calories': calories,
        'daily_protein': protein,
        'daily_carbohydrate': carbs,
        'daily_fat': fat,
        'daily_fiber': 30
    }


def get_bmi_category(bmi):
    """Categorize BMI"""
    try:
        bmi_val = float(bmi) if isinstance(bmi, str) else bmi
        if bmi_val < 18.5:
            return "Underweight", "🔵"
        elif 18.5 <= bmi_val < 25:
            return "Normal Weight", "🟢"
        elif 25 <= bmi_val < 30:
            return "Overweight", "🟡"
        else:
            return "Obese", "🔴"
    except:
        return "Unknown", "⚪"


# ==================== HELPER FUNCTIONS ====================
def generate_comprehensive_meal_plan_prompt(user_profile, inventory_df):
    """Generate comprehensive prompt for the agent"""

    inventory_by_category = {}
    if not inventory_df.empty:
        for _, item in inventory_df.iterrows():
            category = item['category'] or 'Other'
            if category not in inventory_by_category:
                inventory_by_category[category] = []
            inventory_by_category[category].append({
                'item': item['item_name'],
                'quantity': item['quantity'],
                'unit': item['unit']
            })

    prompt = f"""Generate a complete 7-day meal plan for:

IMPORTANT: Today is {datetime.now().strftime('%A, %B %d, %Y')}. 
The meal plan should start from TODAY and continue for 7 days.
Ensure day names match the actual calendar dates (e.g., if today is Friday, day 1 should be Friday, day 2 should be Saturday, etc.).

USER PROFILE:
- User ID: {user_profile['user_id']}
- Age: {user_profile['age']} years
- Gender: {user_profile['gender']}
- Height: {user_profile['height_cm']} cm
- Weight: {user_profile['weight_kg']} kg
- BMI: {user_profile['bmi']:.1f}
- Activity Level: {user_profile['activity_level']}
- Health Goal: {user_profile['health_goal']}
- Dietary Restrictions: {user_profile['dietary_restrictions']}
- Food Allergies: {user_profile['food_allergies']}

DAILY NUTRITIONAL TARGETS:
- Calories: {user_profile['daily_calories']} kcal
- Protein: {user_profile['daily_protein']:.1f}g
- Carbohydrates: {user_profile['daily_carbohydrate']:.1f}g
- Fat: {user_profile['daily_fat']:.1f}g
- Fiber: {user_profile['daily_fiber']:.1f}g

CURRENT INVENTORY:
{json.dumps(inventory_by_category, indent=2)}

Create a detailed 7-day meal plan with complete recipes and inventory optimization.
Generate plans based ONLY on available inventory where possible.
If a critical item (like protein source) is missing from inventory, explicitly mention it as a REQUIRED PURCHASE.
Do NOT estimate costs.
Strictly follow dietary restrictions and allergies.

ALSO GENERATE:
"future_suggestions": A list of 5-10 items to buy for NEXT week to improve variety.
- Ensure these items are NOT currently in inventory.
- Strictly respect allergies/restrictions.
- EXPLICITLY link each suggestion to the user's health goal ({user_profile['health_goal']}) and activity level ({user_profile['activity_level']}).
  Example: "Since your goal is Muscle Gain, buy Greek Yogurt for high protein."
- Format: [{{"item": "Name", "reason": "Why (linking to goal)", "category": "Category", "suggested_quantity": 0, "unit": "unit"}}]

Return the meal plan in valid JSON format."""

    return prompt


def save_meal_plan(conn, user_id, schedule_id, meal_plan_data):
    """Save the generated meal plan to database"""
    cursor = conn.cursor()
    plan_id = str(uuid.uuid4())

    try:
        # Save main meal plan
        cursor.execute("""
                       INSERT INTO meal_plans (plan_id, user_id, schedule_id, plan_name,
                                               start_date, end_date, week_summary, status)
                       SELECT %s, %s, %s, %s, %s, %s, PARSE_JSON(%s), %s
                       """, (
                           plan_id,
                           user_id,
                           schedule_id,
                           f"Week of {datetime.now().strftime('%B %d, %Y')}",
                           datetime.now().date(),
                           datetime.now().date() + timedelta(days=7),
                           json.dumps({
                               **meal_plan_data.get('meal_plan', {}).get('week_summary', {}),
                               'future_suggestions': meal_plan_data.get('future_suggestions', [])
                           }),
                           'ACTIVE'
                       ))

        # Save daily meals
        days_data = meal_plan_data.get('meal_plan', {}).get('days', [])

        for day_data in days_data:
            meal_id = str(uuid.uuid4())

            cursor.execute("""
                           INSERT INTO daily_meals (meal_id, plan_id, user_id, day_number, day_name,
                                                    meal_date, total_nutrition, inventory_impact)
                           SELECT %s, %s, %s, %s, %s, %s, PARSE_JSON(%s), PARSE_JSON(%s)
                           """, (
                               meal_id,
                               plan_id,
                               user_id,
                               day_data.get('day', 0),
                               day_data.get('day_name', ''),
                               datetime.now().date() + timedelta(days=day_data.get('day', 1) - 1),
                               json.dumps(day_data.get('total_nutrition', {})),
                               json.dumps(day_data.get('inventory_impact', {}))
                           ))

            # Save meal details
            meals = day_data.get('meals', {})
            for meal_type in ['breakfast', 'lunch', 'dinner', 'snacks']:
                if meal_type in meals:
                    meal_detail = meals[meal_type]
                    detail_id = str(uuid.uuid4())

                    cursor.execute("""
                                   INSERT INTO meal_details (detail_id, meal_id, meal_type, meal_name,
                                                             ingredients_with_quantities, recipe, nutrition,
                                                             preparation_time, cooking_time, servings,
                                                             serving_size, difficulty_level)
                                   SELECT %s, %s, %s, %s, PARSE_JSON(%s), PARSE_JSON(%s), PARSE_JSON(%s), %s, %s, %s, %s, %s
                                   """, (
                                       detail_id,
                                       meal_id,
                                       meal_type,
                                       meal_detail.get('meal_name', 'Unknown Meal'),
                                       json.dumps(meal_detail.get('ingredients_with_quantities', [])),
                                       json.dumps(meal_detail.get('recipe', {})),
                                       json.dumps(meal_detail.get('nutrition', {})),
                                       meal_detail.get('preparation_time', 0),
                                       meal_detail.get('cooking_time', 0),
                                       meal_detail.get('servings', 1),
                                       meal_detail.get('serving_size', '1 serving'),
                                       meal_detail.get('recipe', {}).get('difficulty_level', 'medium')
                                   ))

        # Save shopping list
        shopping_data = meal_plan_data.get('recommendations', {}).get('shopping_list_summary', {})
        if shopping_data:
            list_id = str(uuid.uuid4())
            cursor.execute("""
                           INSERT INTO shopping_lists (list_id, plan_id, user_id, shopping_data,
                                                       total_estimated_cost, total_items_from_inventory,
                                                       total_items_to_purchase)
                           SELECT %s, %s, %s, PARSE_JSON(%s), %s, %s, %s
                           """, (
                               list_id,
                               plan_id,
                               user_id,
                               json.dumps(shopping_data),
                               shopping_data.get('total_estimated_cost', 0),
                               shopping_data.get('total_items_from_inventory', 0),
                               shopping_data.get('total_items_to_purchase', 0)
                           ))

        conn.commit()
        cursor.close()
        return plan_id
    except Exception as e:
        cursor.close()
        st.error(f"Error saving meal plan: {e}")
        return None


def get_inventory_items(conn, user_id):
    """Get all inventory items for a user"""
    cursor = conn.cursor()
    cursor.execute("""
                   SELECT inventory_id, item_name, quantity, unit, category, notes, updated_at
                   FROM inventory
                   WHERE user_id = %s
                   ORDER BY category, item_name
                   """, (user_id,))
    result = cursor.fetchall()
    cursor.close()

    if result:
        columns = ['inventory_id', 'item_name', 'quantity', 'unit', 'category', 'notes', 'updated_at']
        return pd.DataFrame(result, columns=columns)
    return pd.DataFrame()


def add_inventory_item(conn, user_id, item_name, quantity, unit, category=None, notes=None):
    """Add inventory item"""
    cursor = conn.cursor()
    inventory_id = str(uuid.uuid4())

    try:
        cursor.execute("""
                       INSERT INTO inventory (inventory_id, user_id, item_name, quantity, unit, category, notes)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       """, (inventory_id, user_id, item_name, quantity, unit, category, notes))
        conn.commit()
        cursor.close()
        return True
    except:
        cursor.close()
        return False


def delete_inventory_item(conn, inventory_id):
    """Delete inventory item"""
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM inventory WHERE inventory_id = %s", (inventory_id,))
        conn.commit()
        cursor.close()
        return True
    except:
        cursor.close()
        return False


def update_plan_suggestions(conn, plan_id, suggestions):
    """Update the week_summary with new suggestions"""
    cursor = conn.cursor()
    try:
        # First get existing summary
        cursor.execute("SELECT week_summary FROM meal_plans WHERE plan_id = %s", (plan_id,))
        result = cursor.fetchone()
        if result and result[0]:
            summary = json.loads(result[0])
            summary['future_suggestions'] = suggestions
            
            # Update
            cursor.execute("""
                           UPDATE meal_plans 
                           SET week_summary = PARSE_JSON(%s)
                           WHERE plan_id = %s
                           """, (json.dumps(summary), plan_id))
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Error updating suggestions: {e}")
    finally:
        cursor.close()
    return False


@st.dialog("🍽️ Meal Details")
def show_meal_details(meal_data):
    """Show meal details in a dialog"""
    st.subheader(meal_data['meal_name'])
    
    # Quick stats
    stat_cols = st.columns(4)
    stat_cols[0].metric("⏱️ Prep", f"{meal_data['preparation_time']} min")
    stat_cols[1].metric("🔥 Cook", f"{meal_data['cooking_time']} min")
    stat_cols[2].metric("🍽️ Servings", meal_data['servings'])
    
    difficulty_colors = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}
    level = meal_data['difficulty_level']
    stat_cols[3].metric("Level", f"{difficulty_colors.get(level, '⚪')} {level}")

    # Nutrition
    if meal_data['nutrition']:
        nutrition = json.loads(meal_data['nutrition'])
        st.markdown("**Nutrition:**")
        nutrition_html = ""
        for key, value in nutrition.items():
            label = key.replace('_g', '').replace('_', ' ').title()
            nutrition_html += f"<span class='nutrition-badge'>{label}: {value:.1f}{'g' if '_g' in key else ''}</span>"
        st.markdown(nutrition_html, unsafe_allow_html=True)

    # Ingredients
    if meal_data['ingredients_with_quantities']:
        ingredients = json.loads(meal_data['ingredients_with_quantities'])
        st.markdown("### 📦 Ingredients")
        for ing in ingredients:
            icon = "✅" if ing.get('from_inventory', False) else "🛒"
            st.write(f"{icon} **{ing.get('quantity', '')} {ing.get('unit', '')}** {ing.get('ingredient', '')}")

    # Recipe
    if meal_data['recipe']:
        recipe = json.loads(meal_data['recipe'])
        st.markdown("### 👨‍🍳 Full Recipe")
        
        if recipe.get('equipment_needed'):
            st.markdown("**🔧 Equipment:**")
            equipment_html = ""
            for item in recipe['equipment_needed']:
                equipment_html += f"<span class='nutrition-badge'>{item}</span>"
            st.markdown(equipment_html, unsafe_allow_html=True)
            st.write("")

        if recipe.get('prep_steps'):
            st.markdown("**📋 Preparation:**")
            for i, step in enumerate(recipe['prep_steps'], 1):
                st.markdown(f"{i}. {step}")

        if recipe.get('cooking_instructions'):
            st.markdown("**🍳 Cooking:**")
            for i, step in enumerate(recipe['cooking_instructions'], 1):
                st.markdown(f"<div class='recipe-step'><b>Step {i}:</b> {step}</div>", unsafe_allow_html=True)

        if recipe.get('tips'):
            st.info("💡 **Tips:**\n" + "\n".join([f"• {tip}" for tip in recipe['tips']]))


# ==================== SHOPPING & SUGGESTIONS ====================
def shopping_list_viewer(conn, user_id):
    """View shopping list for active plan"""
    st.header("🛒 Shopping List")
    
    cursor = conn.cursor()
    cursor.execute("""
                   SELECT s.shopping_data, p.plan_name
                   FROM shopping_lists s
                   JOIN meal_plans p ON s.plan_id = p.plan_id
                   WHERE s.user_id = %s AND p.status = 'ACTIVE'
                   ORDER BY s.created_at DESC LIMIT 1
                   """, (user_id,))
    result = cursor.fetchone()
    cursor.close()

    if not result:
        st.info("No active shopping list found. Generate a meal plan first!")
        return

    shopping_data = json.loads(result[0])
    plan_name = result[1]
    
    st.caption(f"For: {plan_name}")

    if not shopping_data:
        st.success("🎉 Nothing to buy! You have everything in stock.")
        return

    # Display by category
    categories = {
        "Proteins": shopping_data.get('proteins', []),
        "Grains": shopping_data.get('grains', []),
        "Vegetables": shopping_data.get('vegetables', []),
        "Fruits": shopping_data.get('fruits', []),
        "Dairy/Alt": shopping_data.get('dairy_alternatives', []),
        "Pantry": shopping_data.get('pantry_items', [])
    }

    for cat, items in categories.items():
        if items:
            st.subheader(cat)
            for item in items:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{item['item']}**")
                with col2:
                    st.write(f"{item['quantity_to_purchase']} {item['unit']}")
            st.divider()


def suggestions_viewer(conn, user_id):
    """View suggestions for next week"""
    st.header("💡 Suggestions for Next Week")
    st.info("Items to add variety to your future meals!")

    cursor = conn.cursor()
    cursor.execute("""
                   SELECT week_summary, plan_id, plan_name
                   FROM meal_plans
                   WHERE user_id = %s AND status = 'ACTIVE'
                   ORDER BY created_at DESC LIMIT 1
                   """, (user_id,))
    result = cursor.fetchone()
    
    if not result:
        st.warning("Generate a meal plan to get suggestions!")
        cursor.close()
        return

    week_summary = json.loads(result[0])
    plan_id = result[1]
    plan_name = result[2]
    suggestions = week_summary.get('future_suggestions', [])
    
    # Generate button
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"For Plan: {plan_name}")
    with col2:
        if st.button("✨ Generate Smart Suggestions", help="Generate new suggestions based on your goals"):
            with st.spinner("Analyzing your plan and goals..."):
                # Get user profile
                cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                user_row = cursor.fetchone()
                # (Simplified profile reconstruction for brevity, assuming standard columns)
                # Ideally we reuse a get_user_profile function, but we'll reconstruct essential parts
                user_profile = {
                    'health_goal': user_row[13], # Adjust index based on table schema
                    'activity_level': user_row[12],
                    'dietary_restrictions': user_row[14],
                    'food_allergies': user_row[15]
                }
                
                # Get plan summary (simplified)
                plan_summary = f"Plan: {plan_name}. Current inventory utilization: {week_summary.get('inventory_utilization_rate', 0)}%"
                
                # Call agent
                session = get_snowpark_session()
                agent = MealPlanAgentWithExtraction(session)
                new_suggestions = agent.generate_standalone_suggestions(user_profile, plan_summary)
                
                if new_suggestions:
                    if update_plan_suggestions(conn, plan_id, new_suggestions):
                        st.success("Suggestions updated!")
                        st.rerun()
                else:
                    st.error("Could not generate suggestions. Try again.")
    
    cursor.close()

    if not suggestions:
        st.info("No suggestions available yet. Click the button above to generate them!")
        return

    for i, item in enumerate(suggestions):
        with st.container():
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.write(f"**{item.get('item', 'Unknown')}**")
                st.caption(f"Reason: {item.get('reason', '')}")
            with col2:
                st.write(f"Category: {item.get('category', 'General')}")
                st.write(f"Qty: {item.get('suggested_quantity', 1)} {item.get('unit', 'unit')}")
            with col3:
                if st.button("➕ Add", key=f"sugg_{i}"):
                    if add_inventory_item(conn, user_id, item.get('item'), 
                                       item.get('suggested_quantity', 1), 
                                       item.get('unit', 'unit'), 
                                       item.get('category', 'Other')):
                        st.toast(f"Added {item.get('item')} to inventory!")
            st.divider()


# ==================== MEAL PLAN VIEWER ====================
def meal_plan_viewer(conn, user_id):
    """Enhanced meal plan viewer"""
    st.header("🍽️ My Weekly Meal Plan")

    cursor = conn.cursor()

    # Get active meal plan
    cursor.execute("""
                   SELECT p.plan_id,
                          p.plan_name,
                          p.start_date,
                          p.end_date,
                          p.week_summary,
                          p.created_at,
                          p.status
                   FROM meal_plans p
                   WHERE p.user_id = %s
                   ORDER BY p.created_at DESC LIMIT 1
                   """, (user_id,))

    active_plan = cursor.fetchone()

    if not active_plan:
        # No plan - offer to generate
        st.info("📅 You don't have a meal plan yet!")

        if st.button("🎉 Generate My First Meal Plan", type="primary", use_container_width=True):
            generate_new_meal_plan(conn, user_id)
        cursor.close()
        return

    # Display active plan
    plan_id = active_plan[0]
    plan_name = active_plan[1]
    start_date = active_plan[2]
    end_date = active_plan[3]
    week_summary = json.loads(active_plan[4]) if active_plan[4] else {}

    # Header
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        st.subheader(f"📋 {plan_name}")
        days_remaining = (end_date - datetime.now().date()).days
        if days_remaining > 0:
            st.caption(
                f"📅 {start_date.strftime('%B %d')} - {end_date.strftime('%B %d')} • {days_remaining} days remaining")
        else:
            st.caption(f"📅 Plan ended on {end_date.strftime('%B %d')}")

    with col2:
        if week_summary:
            utilization = week_summary.get('inventory_utilization_rate', 0)
            st.metric("Inventory Usage", f"{utilization}%")

    with col3:
        if st.button("🔄 New Plan"):
            generate_new_meal_plan(conn, user_id)

    # Week overview
    if week_summary:
        st.markdown("### 📊 Week Overview")
        metrics_cols = st.columns(5)
        metrics_cols[0].metric("Avg Calories", f"{week_summary.get('average_daily_calories', 0):.0f}")
        metrics_cols[1].metric("Avg Protein", f"{week_summary.get('average_daily_protein', 0):.0f}g")
        metrics_cols[2].metric("Avg Carbs", f"{week_summary.get('average_daily_carbs', 0):.0f}g")
        metrics_cols[3].metric("Avg Fat", f"{week_summary.get('average_daily_fat', 0):.0f}g")
        metrics_cols[4].metric("Avg Fiber", f"{week_summary.get('average_daily_fiber', 0):.0f}g")

    # Get daily meals
    cursor.execute("""
                   SELECT meal_id,
                          day_number,
                          day_name,
                          meal_date,
                          total_nutrition,
                          inventory_impact
                   FROM daily_meals
                   WHERE plan_id = %s
                   ORDER BY day_number
                   """, (plan_id,))

    daily_meals = cursor.fetchall()

    if daily_meals:
        st.markdown("### 📅 Select a Day")

        # Day selector
        day_cols = st.columns(7)
        selected_day = st.session_state.get('selected_meal_day', 0)

        for idx, meal in enumerate(daily_meals):
            with day_cols[idx % 7]:
                if st.button(
                        f"{meal[2][:3]}\n{meal[3].strftime('%d')}",
                        key=f"day_{idx}",
                        use_container_width=True,
                        type="primary" if idx == selected_day else "secondary"
                ):
                    st.session_state.selected_meal_day = idx
                    st.rerun()

        # Display selected day
        selected_meal = daily_meals[selected_day]
        meal_id = selected_meal[0]

        st.markdown(f"### 🍽️ {selected_meal[2]} - {selected_meal[3].strftime('%B %d, %Y')}")

        # Day nutrition
        if selected_meal[4]:
            day_nutrition = json.loads(selected_meal[4])

            col1, col2 = st.columns([3, 1])
            with col1:
                # Progress bars
                calories_pct = (day_nutrition.get('calories', 0) / 2000) * 100
                st.progress(min(calories_pct / 100, 1.0),
                            text=f"Calories: {day_nutrition.get('calories', 0):.0f} kcal")

                protein_pct = (day_nutrition.get('protein_g', 0) / 130) * 100
                st.progress(min(protein_pct / 100, 1.0),
                            text=f"Protein: {day_nutrition.get('protein_g', 0):.0f}g")

            with col2:
                if selected_meal[5]:
                    impact = json.loads(selected_meal[5])
                    st.metric("From Inventory", impact.get('items_used', 0))

        # Get meal details
        cursor.execute("""
                       SELECT meal_type,
                              meal_name,
                              ingredients_with_quantities,
                              recipe,
                              nutrition,
                              preparation_time,
                              cooking_time,
                              servings,
                              serving_size,
                              difficulty_level
                       FROM meal_details
                       WHERE meal_id = %s
                       ORDER BY CASE meal_type
                                    WHEN 'breakfast' THEN 1
                                    WHEN 'lunch' THEN 2
                                    WHEN 'snacks' THEN 3
                                    WHEN 'dinner' THEN 4
                                    END
                       """, (meal_id,))

        meal_details = cursor.fetchall()

        if meal_details:
            # Prepare data for table
            table_data = []
            meal_map = {}
            
            for meal in meal_details:
                # Parse nutrition for display
                calories = 0
                protein = 0
                if meal[4]:
                    nut = json.loads(meal[4])
                    calories = nut.get('calories', 0)
                    protein = nut.get('protein_g', 0)

                row = {
                    "Type": meal[0].title(),
                    "Meal Name": meal[1],
                    "Calories": f"{calories:.0f}",
                    "Protein (g)": f"{protein:.1f}",
                    "Prep Time": f"{meal[5]} min",
                    "Cook Time": f"{meal[6]} min",
                    "Level": meal[9].title()
                }
                table_data.append(row)
                
                # Store full data for dialog
                meal_key = f"{meal[0]}_{meal[1]}"
                meal_map[meal_key] = {
                    "meal_name": meal[1],
                    "ingredients_with_quantities": meal[2],
                    "recipe": meal[3],
                    "nutrition": meal[4],
                    "preparation_time": meal[5],
                    "cooking_time": meal[6],
                    "servings": meal[7],
                    "serving_size": meal[8],
                    "difficulty_level": meal[9]
                }

            # Display interactive table
            st.subheader("📅 Weekly Schedule")
            df = pd.DataFrame(table_data)
            
            # Configure column config
            column_config = {
                "Type": st.column_config.TextColumn("Type", width="small"),
                "Meal Name": st.column_config.TextColumn("Meal Name", width="large"),
                "Calories": st.column_config.NumberColumn("Calories", format="%s kcal"),
                "Protein (g)": st.column_config.NumberColumn("Protein", format="%s g"),
                "Level": st.column_config.TextColumn("Level", width="small"),
            }

            event = st.dataframe(
                df,
                column_config=column_config,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )

            # Handle selection
            if event.selection.rows:
                selected_index = event.selection.rows[0]
                selected_row = df.iloc[selected_index]
                meal_key = f"{selected_row['Type'].lower()}_{selected_row['Meal Name']}"
                
                if meal_key in meal_map:
                    show_meal_details(meal_map[meal_key])

    cursor.close()


def generate_new_meal_plan(conn, user_id):
    """Generate a new meal plan"""
    with st.spinner("Creating your personalized meal plan..."):
        cursor = conn.cursor()

        # Get user profile
        cursor.execute("""
                       SELECT age,
                              gender,
                              height_cm,
                              weight_kg,
                              bmi,
                              activity_level,
                              health_goal,
                              dietary_restrictions,
                              food_allergies,
                              daily_calories,
                              daily_protein,
                              daily_carbohydrate,
                              daily_fat,
                              daily_fiber
                       FROM users
                       WHERE user_id = %s
                       """, (user_id,))

        profile_data = cursor.fetchone()

        if profile_data:
            user_profile = {
                'user_id': user_id,
                'age': profile_data[0],
                'gender': profile_data[1],
                'height_cm': profile_data[2],
                'weight_kg': profile_data[3],
                'bmi': profile_data[4],
                'activity_level': profile_data[5],
                'health_goal': profile_data[6],
                'dietary_restrictions': profile_data[7] or 'None',
                'food_allergies': profile_data[8] or 'None',
                'daily_calories': profile_data[9],
                'daily_protein': profile_data[10],
                'daily_carbohydrate': profile_data[11],
                'daily_fat': profile_data[12],
                'daily_fiber': profile_data[13]
            }

            # Get inventory
            inventory_df = get_inventory_items(conn, user_id)

            # Generate prompt
            prompt = generate_comprehensive_meal_plan_prompt(user_profile, inventory_df)

            # Call agent
            session = get_snowpark_session()
            agent = MealPlanAgentWithExtraction(session)
            meal_plan_data = agent.generate_meal_plan(prompt, user_profile)

            if meal_plan_data:
                # Create schedule
                schedule_id = str(uuid.uuid4())
                tomorrow = datetime.now().date() + timedelta(days=1)
                plan_end = tomorrow + timedelta(days=7)

                cursor.execute("""
                               INSERT INTO planning_schedule (schedule_id, user_id, plan_start_date,
                                                              plan_end_date, next_plan_date, status)
                               VALUES (%s, %s, %s, %s, %s, 'ACTIVE')
                               """, (schedule_id, user_id, tomorrow, plan_end, tomorrow + timedelta(days=5)))

                # Save meal plan
                plan_id = save_meal_plan(conn, user_id, schedule_id, meal_plan_data)

                if plan_id:
                    conn.commit()
                    st.success("✅ Your meal plan has been generated!")
                    st.rerun()
                else:
                    st.error("Failed to save meal plan")

        cursor.close()


# ==================== PROFILE SETUP WIZARD ====================
def profile_setup_wizard(conn, user_id):
    """Multi-step wizard for profile setup"""
    st.title("🍽️ Complete Your Nutrition Profile")

    total_steps = 7
    current_step = st.session_state.get('setup_step', 1)
    progress = current_step / total_steps
    st.progress(progress)
    st.write(f"Step {current_step} of {total_steps}")

    if 'form_data' not in st.session_state:
        st.session_state.form_data = {}
    if 'inventory_items' not in st.session_state:
        st.session_state.inventory_items = []

    # STEP 1: Personal Information
    if current_step == 1:
        st.header("Step 1: Personal Information")

        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input("Age", min_value=1, max_value=120,
                                  value=st.session_state.form_data.get('age', 25))
            gender = st.selectbox("Gender", ["Male", "Female"])

        with col2:
            height = st.number_input("Height (cm)", min_value=100, max_value=250,
                                     value=st.session_state.form_data.get('height', 170))
            weight = st.number_input("Weight (kg)", min_value=30.0, max_value=300.0,
                                     value=st.session_state.form_data.get('weight', 70.0))

        if st.button("Next →", type="primary"):
            st.session_state.form_data.update({
                'age': age, 'gender': gender, 'height': height, 'weight': weight
            })
            st.session_state.setup_step = 2
            st.rerun()

    # STEP 2: Life Stage
    elif current_step == 2:
        st.header("Step 2: Life Stage")

        life_stage = st.selectbox("Life Stage",
                                  ["Adult (19-30)", "Adult (31-50)", "Adult (51-70)", "Adult (70+)"])

        if st.session_state.form_data.get('gender') == 'Female':
            pregnancy = st.selectbox("Pregnancy Status",
                                     ["Not Pregnant", "1st Trimester", "2nd Trimester", "3rd Trimester"])
            lactation = st.selectbox("Lactation Status",
                                     ["Not Lactating", "0-6 months", "7-12 months"])
        else:
            pregnancy = "Not Pregnant"
            lactation = "Not Lactating"

        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Previous"):
                st.session_state.setup_step = 1
                st.rerun()
        with col2:
            if st.button("Next →", type="primary"):
                st.session_state.form_data.update({
                    'life_stage': life_stage, 'pregnancy': pregnancy, 'lactation': lactation
                })
                st.session_state.setup_step = 3
                st.rerun()

    # STEP 3: Activity & Goals
    elif current_step == 3:
        st.header("Step 3: Activity Level & Health Goals")

        activity = st.selectbox("Activity Level",
                                ["Sedentary", "Lightly active", "Moderately active", "Very active", "Extremely active"])

        goal = st.selectbox("Primary Health Goal",
                            ["Weight Loss", "Weight Maintenance", "Muscle Gain", "Athletic Performance",
                             "General Health"])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Previous"):
                st.session_state.setup_step = 2
                st.rerun()
        with col2:
            if st.button("Next →", type="primary"):
                st.session_state.form_data.update({
                    'activity': activity, 'goal': goal
                })
                st.session_state.setup_step = 4
                st.rerun()

    # STEP 4: Dietary Preferences
    elif current_step == 4:
        st.header("Step 4: Dietary Restrictions & Allergies")

        restrictions = st.multiselect("Dietary Restrictions (optional)",
                                      ["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "Keto",
                                       "Low-Sodium", "Low-Carb", "Paleo"])

        allergies = st.multiselect("Food Allergies (optional)",
                                   ["Peanuts", "Tree Nuts", "Milk", "Eggs", "Fish",
                                    "Shellfish", "Soy", "Wheat", "Sesame"])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Previous"):
                st.session_state.setup_step = 3
                st.rerun()
        with col2:
            if st.button("Calculate My DRI →", type="primary"):
                st.session_state.form_data.update({
                    'restrictions': restrictions, 'allergies': allergies
                })
                st.session_state.setup_step = 5
                st.rerun()

    # STEP 5: Calculate DRI
    elif current_step == 5:
        st.header("Step 5: Your Personalized Nutrition Plan")

        with st.spinner("Calculating your nutrition targets..."):
            data = st.session_state.form_data

            api_data = get_nutrition_info_from_api(
                data['age'], data['gender'], data['height'], data['weight'],
                data['activity'], data.get('pregnancy', 'Not Pregnant'),
                data.get('lactation', 'Not Lactating')
            )

            if api_data:
                bmi = api_data.get('BMI_EER', {}).get('BMI', '0')
                calories_str = api_data.get('BMI_EER', {}).get('Estimated Daily Caloric Needs', '2000 kcal/day')
                calories = int(calories_str.replace(',', '').split()[0])
                macro_table = api_data.get('macronutrients_table', {}).get('macronutrients-table', [])

                targets = {
                    'bmi': float(bmi),
                    'daily_calories': calories,
                    'daily_protein': parse_macro_value(macro_table, 'Protein'),
                    'daily_carbohydrate': parse_macro_value(macro_table, 'Carbohydrate'),
                    'daily_fat': parse_macro_value(macro_table, 'Fat'),
                    'daily_fiber': parse_macro_value(macro_table, 'Total Fiber')
                }
            else:
                targets = calculate_manual(
                    data['age'], data['gender'], data['weight'],
                    data['height'], data['activity'], data['goal']
                )

            st.session_state.form_data['targets'] = targets

        st.success("✅ Your nutrition targets are ready!")

        # Display results
        col1, col2 = st.columns(2)
        category, emoji = get_bmi_category(targets['bmi'])
        col1.metric("BMI", f"{targets['bmi']:.1f}")
        col2.metric("Category", f"{emoji} {category}")

        st.subheader("🎯 Daily Nutrition Targets")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Calories", f"{targets['daily_calories']} kcal")
        c2.metric("Protein", f"{targets['daily_protein']:.1f} g")
        c3.metric("Carbs", f"{targets['daily_carbohydrate']:.1f} g")
        c4.metric("Fat", f"{targets['daily_fat']:.1f} g")
        c5.metric("Fiber", f"{targets['daily_fiber']:.1f} g")

        if st.button("Next → Add Inventory", type="primary", use_container_width=True):
            st.session_state.setup_step = 6
            st.rerun()

    # STEP 6: Add Inventory
    elif current_step == 6:
        st.header("Step 6: Add Your Food Inventory (Optional)")
        st.info("Adding inventory helps create meal plans using what you have!")

        UNITS = ["g", "kg", "lbs", "oz", "ml", "L", "cups", "pieces", "dozen"]
        CATEGORIES = ["Proteins", "Grains", "Vegetables", "Fruits", "Dairy", "Pantry Items", "Other"]

        with st.expander("➕ Add Items", expanded=True):
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

            with col1:
                item_name = st.text_input("Item Name")
            with col2:
                quantity = st.number_input("Quantity", min_value=0.0, value=1.0)
            with col3:
                unit = st.selectbox("Unit", UNITS)
            with col4:
                category = st.selectbox("Category", CATEGORIES)

            if st.button("Add Item"):
                if item_name:
                    st.session_state.inventory_items.append({
                        'name': item_name,
                        'quantity': quantity,
                        'unit': unit,
                        'category': category
                    })
                    st.success(f"Added {item_name}")
                    st.rerun()

        # Display items
        if st.session_state.inventory_items:
            st.subheader("Your Inventory:")
            for item in st.session_state.inventory_items:
                st.write(f"• {item['name']}: {item['quantity']} {item['unit']} ({item['category']})")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Previous"):
                st.session_state.setup_step = 5
                st.rerun()
        with col2:
            if st.button("Next → Generate Meal Plan", type="primary"):
                if len(st.session_state.inventory_items) < 10:
                    st.error(f"Please add at least 10 items to your inventory to generate a plan. (Current: {len(st.session_state.inventory_items)})")
                else:
                    st.session_state.setup_step = 7
                    st.rerun()

    # STEP 7: Generate First Meal Plan
    elif current_step == 7:
        st.header("Step 7: Generate Your First Meal Plan")

        st.write("### Your meal plan will include:")
        st.write("✅ 7 days of balanced meals")
        st.write("✅ Complete recipes with instructions")
        st.write("✅ Meals using your inventory")
        st.write("✅ Shopping list for additional items")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("← Previous"):
                st.session_state.setup_step = 6
                st.rerun()

        with col2:
            if st.button("🚀 Complete Setup & Generate Plan", type="primary"):
                with st.spinner("Setting up your profile and generating meal plan..."):
                    cursor = conn.cursor()
                    data = st.session_state.form_data
                    targets = data['targets']

                    try:
                        # Save profile
                        cursor.execute("""
                                       UPDATE users
                                       SET age                  = %s,
                                           gender               = %s,
                                           height_cm            = %s,
                                           weight_kg            = %s,
                                           bmi                  = %s,
                                           life_stage           = %s,
                                           pregnancy_status     = %s,
                                           lactation_status     = %s,
                                           activity_level       = %s,
                                           health_goal          = %s,
                                           dietary_restrictions = %s,
                                           food_allergies       = %s,
                                           daily_calories       = %s,
                                           daily_protein        = %s,
                                           daily_carbohydrate   = %s,
                                           daily_fat            = %s,
                                           daily_fiber          = %s,
                                           profile_completed    = TRUE,
                                           updated_at           = CURRENT_TIMESTAMP()
                                       WHERE user_id = %s
                                       """, (
                                           data['age'], data['gender'], data['height'], data['weight'], targets['bmi'],
                                           data['life_stage'], data.get('pregnancy', 'Not Pregnant'),
                                           data.get('lactation', 'Not Lactating'),
                                           data['activity'], data['goal'],
                                           ', '.join(data.get('restrictions', [])) or 'None',
                                           ', '.join(data.get('allergies', [])) or 'None',
                                           targets['daily_calories'], targets['daily_protein'],
                                           targets['daily_carbohydrate'], targets['daily_fat'], targets['daily_fiber'],
                                           user_id
                                       ))

                        # Save inventory
                        for item in st.session_state.inventory_items:
                            add_inventory_item(conn, user_id, item['name'],
                                               item['quantity'], item['unit'], item['category'])

                        conn.commit()

                        # Clear setup state
                        del st.session_state['setup_step']
                        del st.session_state['form_data']
                        del st.session_state['inventory_items']
                        st.session_state.profile_completed = True

                        st.success("🎉 Setup complete!")
                        st.balloons()
                        st.rerun()

                    except Exception as e:
                        st.error(f"Error: {e}")
                    finally:
                        cursor.close()


# ==================== MAIN DASHBOARD ====================
def main_dashboard(conn, user_id, username):
    """Main application dashboard"""

    # Header
    col1, col2 = st.columns([6, 1])
    with col1:
        st.title(f"🍽️ Welcome, {username}!")
    with col2:
        if st.button("Logout"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    # Get user profile
    cursor = conn.cursor()
    cursor.execute("""
                   SELECT age,
                          gender,
                          height_cm,
                          weight_kg,
                          bmi,
                          activity_level,
                          health_goal,
                          dietary_restrictions,
                          food_allergies,
                          daily_calories,
                          daily_protein,
                          daily_carbohydrate,
                          daily_fat,
                          daily_fiber,
                          updated_at
                   FROM users
                   WHERE user_id = %s
                   """, (user_id,))
    profile = cursor.fetchone()
    cursor.close()

    if profile:
        tabs = st.tabs(["📊 Dashboard", "🍽️ Meal Plan", "🛒 Shopping List", "💡 Suggestions", "🏪 Inventory", "⚙️ Profile"])

        with tabs[0]:
            st.header("Your Nutrition Dashboard")

            # Stats
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("BMI", f"{profile[4]:.1f}")
            category, emoji = get_bmi_category(profile[4])
            col2.metric("Category", f"{emoji} {category}")
            col3.metric("Activity", profile[5])
            col4.metric("Goal", profile[6])

            # Daily targets
            st.subheader("📋 Daily Targets")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Calories", f"{profile[9]} kcal")
            c2.metric("Protein", f"{profile[10]:.1f} g")
            c3.metric("Carbs", f"{profile[11]:.1f} g")
            c4.metric("Fat", f"{profile[12]:.1f} g")
            c5.metric("Fiber", f"{profile[13]:.1f} g")

        with tabs[1]:
            meal_plan_viewer(conn, user_id)

        with tabs[2]:
            shopping_list_viewer(conn, user_id)

        with tabs[3]:
            suggestions_viewer(conn, user_id)

        with tabs[4]:
            st.header("🏪 My Inventory")

            # Add item form
            with st.expander("➕ Add New Item"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    item_name = st.text_input("Item Name")
                    quantity = st.number_input("Quantity", min_value=0.0, value=1.0)
                with col2:
                    unit = st.selectbox("Unit", ["g", "kg", "lbs", "oz", "ml", "L", "cups", "pieces"])
                    category = st.selectbox("Category",
                                            ["Proteins", "Grains", "Vegetables", "Fruits", "Dairy", "Other"])
                with col3:
                    st.write("")
                    st.write("")
                    if st.button("Add Item", type="primary"):
                        if item_name:
                            if add_inventory_item(conn, user_id, item_name, quantity, unit, category):
                                st.success(f"Added {item_name}")
                                st.rerun()

            # Display inventory
            inventory_df = get_inventory_items(conn, user_id)

            if not inventory_df.empty:
                st.info(f"📦 Total Items: {len(inventory_df)}")

                for category in inventory_df['category'].unique():
                    if category:
                        with st.expander(
                                f"{category} ({len(inventory_df[inventory_df['category'] == category])} items)"):
                            items = inventory_df[inventory_df['category'] == category]
                            for _, item in items.iterrows():
                                col1, col2, col3 = st.columns([4, 2, 1])
                                with col1:
                                    st.write(f"**{item['item_name']}**")
                                with col2:
                                    st.write(f"{item['quantity']} {item['unit']}")
                                with col3:
                                    if st.button("🗑️", key=f"del_{item['inventory_id']}"):
                                        if delete_inventory_item(conn, item['inventory_id']):
                                            st.rerun()
            else:
                st.info("Your inventory is empty. Add items above!")

        with tabs[5]:
            st.header("⚙️ Update Profile")
            st.info("Update your profile to recalculate nutrition targets.")

            # Update form would go here


# ==================== MAIN APPLICATION ====================
def main():
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.profile_completed = False

    # Connect to database
    try:
        conn = get_snowflake_connection()
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        st.stop()

    # AUTHENTICATION FLOW
    if not st.session_state.authenticated:
        st.title("🍽️ Meal Mind - AI-Powered Nutrition Intelligence")
        st.markdown("*Your personalized meal planning assistant powered by USDA nutrition data*")

        tab1, tab2 = st.tabs(["🔑 Login", "📝 Sign Up"])

        with tab1:
            st.subheader("Welcome Back!")
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", type="primary", use_container_width=True)

                if submitted:
                    if username and password:
                        success, user_id, user, profile_completed = authenticate_user(conn, username, password)
                        if success:
                            st.session_state.authenticated = True
                            st.session_state.user_id = user_id
                            st.session_state.username = user
                            st.session_state.profile_completed = profile_completed
                            st.success("Login successful!")
                            st.rerun()
                        else:
                            st.error("Invalid credentials")
                    else:
                        st.warning("Please enter both username and password")

        with tab2:
            st.subheader("Create Your Account")
            with st.form("signup_form"):
                new_username = st.text_input("Choose Username")
                new_email = st.text_input("Email (optional)")
                new_password = st.text_input("Choose Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")

                st.info("📋 After signup, we'll guide you through profile setup and meal plan generation!")

                submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)

                if submitted:
                    if new_username and new_password:
                        if new_password != confirm_password:
                            st.error("Passwords don't match")
                        elif len(new_password) < 6:
                            st.error("Password must be at least 6 characters")
                        else:
                            success, result = create_user_account(conn, new_username, new_password, new_email)
                            if success:
                                st.session_state.authenticated = True
                                st.session_state.user_id = result
                                st.session_state.username = new_username
                                st.session_state.profile_completed = False
                                st.session_state.setup_step = 1
                                st.success("Account created!")
                                st.rerun()
                            else:
                                st.error(f"Failed: {result}")
                    else:
                        st.warning("Please fill in required fields")

    # PROFILE SETUP OR DASHBOARD
    else:
        if not st.session_state.profile_completed:
            profile_setup_wizard(conn, st.session_state.user_id)
        else:
            main_dashboard(conn, st.session_state.user_id, st.session_state.username)


if __name__ == "__main__":
    main()