import streamlit as st
import json
import warnings
import os
from langchain_community.chat_models import ChatSnowflakeCortex
from langchain.schema import SystemMessage, HumanMessage
from utils.mcp_client import MealMindMCPClient

# Suppress the specific warning from ChatSnowflakeCortex about default parameters
warnings.filterwarnings("ignore", message=".*is not default parameter.*")
from utils.db import (
    get_daily_meal_id, 
    get_meal_detail_id, 
    get_meal_detail_by_id,
    update_meal_detail, 
    get_all_meal_details_for_day, 
    update_daily_nutrition
)

class MealAdjustmentAgent:
    """Agent for handling meal changes, replacements, and restaurant entries"""

    def __init__(self, session, conn):
        self.session = session
        self.conn = conn
        try:
            # Initialize Cortex LLM
            # NOTE: We are now using manual MCP retrieval, so we remove cortex_search_service
            self.llm = ChatSnowflakeCortex(
                session=self.session,
                model="openai-gpt-4.1"
            )
            
            # Initialize MCP Client for Context Retrieval
            try:
                account = os.getenv("SNOWFLAKE_ACCOUNT")
                db = os.getenv("SNOWFLAKE_DATABASE")
                schema = os.getenv("SNOWFLAKE_SCHEMA")
                token = self.session.connection.rest.token
                
                if all([account, token, db, schema]):
                    self.mcp_client = MealMindMCPClient(account, token, db, schema)
                else:
                    print("DEBUG: Missing credentials for MCP client in MealAdjustmentAgent")
                    self.mcp_client = None
            except Exception as e:
                print(f"DEBUG: Failed to init MCP client in MealAdjustmentAgent: {e}")
                self.mcp_client = None
                
        except Exception as e:
            st.warning(f"Meal Adjustment Agent LLM init failed: {e}")
            self.llm = None

    def _retrieve_context(self, query: str) -> str:
        """Retrieve relevant food data using MCP"""
        if not self.mcp_client:
            return ""
            
        try:
            # Request specific columns
            columns = [
                "FOOD_NAME", "ENERGY_KCAL", "PROTEIN_G", "CARBOHYDRATE_G", 
                "TOTAL_FAT_G", "FIBER_TOTAL_G", "PRIMARY_INGREDIENT"
            ]
            
            response = self.mcp_client.search_foods(query, columns=columns, limit=5)
            
            if "error" in response:
                print(f"DEBUG: MCP Search Error: {response['error']}")
                return ""
                
            result_content = response.get("result", {}).get("content", [])
            context_parts = []
            
            for item in result_content:
                if item.get("type") == "text":
                    text = item.get("text")
                    try:
                        data = json.loads(text)
                        
                        def format_record(record):
                            if isinstance(record, str): return record
                            parts = []
                            if "FOOD_NAME" in record: parts.append(f"Item: {record['FOOD_NAME']}")
                            nutrients = []
                            if "ENERGY_KCAL" in record: nutrients.append(f"Calories: {record['ENERGY_KCAL']}")
                            if "PROTEIN_G" in record: nutrients.append(f"Protein: {record['PROTEIN_G']}g")
                            if "CARBOHYDRATE_G" in record: nutrients.append(f"Carbs: {record['CARBOHYDRATE_G']}g")
                            if "TOTAL_FAT_G" in record: nutrients.append(f"Fat: {record['TOTAL_FAT_G']}g")
                            if nutrients: parts.append(" | ".join(nutrients))
                            return "\n".join(parts)

                        if isinstance(data, list):
                            for chunk in data: context_parts.append(format_record(chunk))
                        elif isinstance(data, dict):
                             context_parts.append(format_record(data))
                        else:
                            context_parts.append(str(data))
                    except:
                        context_parts.append(text)
                        
            return "\n\n".join(context_parts)
        except Exception as e:
            print(f"DEBUG: MealAdjustment Retrieval Failed: {e}")
            return ""

    def process_request(self, user_input, user_id, date, meal_type, recipe_context=None):
        """
        Process a user's request to change a meal.
        
        Args:
            user_input: The user's description
            user_id: User ID
            date: Date of the meal
            meal_type: Meal type
            recipe_context: Optional generated recipe text with nutrition info
            
        Returns:
            Dict containing status and message
        """
        if not self.llm:
            return {"status": "error", "message": "Agent offline"}

        # 1. Fetch Current Meal Context FIRST
        daily_meal_id = get_daily_meal_id(self.conn, user_id, date)
        if not daily_meal_id:
            return {"status": "error", "message": "No meal plan found for this date."}
        
        detail_id = get_meal_detail_id(self.conn, daily_meal_id, meal_type)
        if not detail_id:
            return {"status": "error", "message": f"No {meal_type} found for this date."}
            
        current_meal = get_meal_detail_by_id(self.conn, detail_id)
        current_meal_context = json.dumps(current_meal, indent=2) if current_meal else "No existing meal data."

        # 2. Retrieve Relevant Food Data via MCP
        print(f"DEBUG: Retrieving context for adjustment: {user_input}")
        retrieved_context = self._retrieve_context(user_input)
        
        # Format Recipe Context if available
        recipe_section = ""
        if recipe_context:
            recipe_section = f"""
        GENERATED RECIPE CONTEXT (PRIORITY):
        {recipe_context}
        
        IMPORTANT: The user just generated this recipe. USE THE NUTRITION VALUES FROM THIS CONTEXT exactly as they appear. Do not use the database values if they differ.
        """

        # 3. Analyze Intent and Generate Data
        system_prompt = f"""You are a nutrition assistant. The user wants to update their {meal_type} for {date}.
        
        CURRENT MEAL DATA:
        {current_meal_context}
        
        {recipe_section}
        
        RELEVANT FOOD DATA (from Database):
        {retrieved_context}
        
        Determine the user's intent:
        1. REPORT: User ate something completely different (overwrite current meal).
        2. REQUEST: User wants a new recipe/alternative (overwrite current meal with new suggestion).
        3. APPEND: User added an item to the current meal (keep existing, add new).
        4. REMOVE: User removed an item from the current meal (keep rest, remove item).
        5. REPLACE: User swapped an item (remove old, add new).
        
        TASK:
        Generate the FULL UPDATED JSON for the meal.
        1. USE CONTEXT: 
           - IF "GENERATED RECIPE CONTEXT" is provided, USE IT as the primary source of truth for nutrition, ingredients, and name.
           - Otherwise, use the RELEVANT FOOD DATA provided above.
        2. UPDATE:
           - If APPEND/REMOVE/REPLACE: Modify the CURRENT MEAL DATA accordingly. Update nutrition, ingredients, and name.
           - If REPORT/REQUEST: Ignore current data and generate new data.
        3. CALCULATE: Calculate the new total nutrition accurately based on the data.
        
        CRITICAL FORMATTING RULES:
        1. Return ONLY valid JSON.
        2. Do NOT use comments (// or #).
        3. Do NOT use arithmetic expressions (e.g., "50 + 20"). Calculate the final value (e.g., "70").
        4. Ensure all keys and string values are enclosed in double quotes.
        
        Return ONLY the JSON.
        """
        
        user_prompt = f"""User Request: "{user_input}"
        
        Format:
        {{
            "intent": "report/request/append/remove/replace",
            "meal_name": "Updated Name",
            "ingredients_with_quantities": [{{"ingredient": "name", "quantity": "amount", "unit": "unit"}}],
            "nutrition": {{
                "calories": 0,
                "protein_g": 0,
                "carbohydrates_g": 0,
                "fat_g": 0,
                "fiber_g": 0
            }},
            "recipe": {{
                "instructions": ["step 1", "step 2"],
                "preparation_time": 0,
                "cooking_time": 0,
                "difficulty_level": "easy/medium/hard"
            }}
        }}
        """
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = self.llm.invoke(messages)
            content = response.content.strip()
            print(f"DEBUG: LLM RAW CONTENT: {content}")
            
            # Robust JSON Extraction
            import re
            
            # 1. Try to find JSON block
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
            
            # 2. Clean up common LLM mistakes
            # Remove trailing commas before closing braces/brackets
            content = re.sub(r',(\s*[}\]])', r'\1', content)
            
            try:
                meal_data = json.loads(content)
            except json.JSONDecodeError:
                # Fallback: Try to use a more aggressive cleanup if standard load fails
                # Sometimes LLMs put comments // or # in JSON
                content = re.sub(r'//.*', '', content)
                content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
                meal_data = json.loads(content)
                
            if not isinstance(meal_data, dict):
                raise ValueError("LLM returned a list or primitive instead of a JSON object")
            
            # 3. Update Database (meal_data is already the full updated state)
            
            # Update the specific meal
            print(f"DEBUG: Updating meal detail {detail_id} with data: {json.dumps(meal_data)[:100]}...")
            success = update_meal_detail(self.conn, detail_id, meal_data)
            print(f"DEBUG: Update success: {success}")
            
            if not success:
                return {"status": "error", "message": "Failed to update meal in database."}
            
            # 3. Recalculate Daily Totals
            all_meals = get_all_meal_details_for_day(self.conn, daily_meal_id)
            
            total_nutrition = {
                "calories": 0,
                "protein_g": 0,
                "carbohydrates_g": 0,
                "fat_g": 0,
                "fiber_g": 0
            }
            
            for meal in all_meals:
                total_nutrition["calories"] += meal.get("calories", 0)
                total_nutrition["protein_g"] += meal.get("protein_g", 0)
                total_nutrition["carbohydrates_g"] += meal.get("carbohydrates_g", 0)
                total_nutrition["fat_g"] += meal.get("fat_g", 0)
                total_nutrition["fiber_g"] += meal.get("fiber_g", 0)
            
            # Round values
            for k, v in total_nutrition.items():
                total_nutrition[k] = round(v, 1)
                
            update_daily_nutrition(self.conn, daily_meal_id, total_nutrition)
            
            msg_action = "added to" if meal_data.get('intent') == 'append' else "updated"
            
            return {
                "status": "success", 
                "message": f"Successfully {msg_action} {meal_type}. New item: {meal_data['meal_name']}.",
                "data": meal_data,
                "new_daily_total": total_nutrition
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Error processing request: {str(e)}"}
