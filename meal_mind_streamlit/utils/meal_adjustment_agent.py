import streamlit as st
import json
from langchain_community.chat_models import ChatSnowflakeCortex
from langchain.schema import SystemMessage, HumanMessage
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
            self.llm = ChatSnowflakeCortex(
                session=self.session,
                model="llama3.1-70b",
                cortex_search_service="MEAL_MIND"
            )
        except Exception as e:
            st.warning(f"Meal Adjustment Agent LLM init failed: {e}")
            self.llm = None

    def process_request(self, user_input, user_id, date, meal_type):
        """
        Process a user's request to change a meal.
        
        Args:
            user_input: The user's description (e.g., "I ate a burger" or "Give me a pasta recipe")
            user_id: User ID
            date: Date of the meal (YYYY-MM-DD)
            meal_type: breakfast, lunch, dinner, or snacks
            
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

        # 2. Analyze Intent and Generate Data
        system_prompt = f"""You are a nutrition assistant. The user wants to update their {meal_type} for {date}.
        
        CURRENT MEAL DATA:
        {current_meal_context}
        
        Determine the user's intent:
        1. REPORT: User ate something completely different (overwrite current meal).
        2. REQUEST: User wants a new recipe/alternative (overwrite current meal with new suggestion).
        3. APPEND: User added an item to the current meal (keep existing, add new).
        4. REMOVE: User removed an item from the current meal (keep rest, remove item).
        5. REPLACE: User swapped an item (remove old, add new).
        
        TASK:
        Generate the FULL UPDATED JSON for the meal.
        - If APPEND/REMOVE/REPLACE: Modify the CURRENT MEAL DATA accordingly. Update nutrition, ingredients, and name.
        - If REPORT/REQUEST: Ignore current data and generate new data.
        - Calculate the new total nutrition accurately.
        
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
            
            # Clean JSON
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()
            
            meal_data = json.loads(content)
            
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
