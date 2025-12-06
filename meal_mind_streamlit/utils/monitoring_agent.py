import streamlit as st
import json
from utils.db import get_user_profile, get_daily_meal_id

class MonitoringAgent:
    """Agent for monitoring nutritional changes and providing health warnings"""

    def __init__(self, conn):
        self.conn = conn

    def monitor_changes(self, user_id, date):
        """
        Check if the day's nutrition is within acceptable limits of the user's goals.
        
        Args:
            user_id: User ID
            date: Date to check (YYYY-MM-DD)
            
        Returns:
            List of warning/suggestion strings
        """
        try:
            # 1. Get User Goals
            profile = get_user_profile(self.conn, user_id)
            if not profile:
                return []
            
            target_calories = profile.get('daily_calories', 2000)
            target_protein = profile.get('daily_protein', 0)
            target_carbs = profile.get('daily_carbohydrate', 0)
            target_fat = profile.get('daily_fat', 0)
            
            # 2. Get Actual Daily Totals
            daily_meal_id = get_daily_meal_id(self.conn, user_id, date)
            if not daily_meal_id:
                return []
            
            cursor = self.conn.cursor()
            cursor.execute("SELECT total_nutrition FROM daily_meals WHERE meal_id = %s", (daily_meal_id,))
            result = cursor.fetchone()
            cursor.close()
            
            if not result or not result[0]:
                return []
                
            actual = json.loads(result[0]) if isinstance(result[0], str) else result[0]
            
            # 3. Compare and Generate Warnings
            warnings = []
            
            # Calorie Check (Threshold: +/- 10%)
            cal_diff = actual.get('calories', 0) - target_calories
            cal_percent = (cal_diff / target_calories) * 100 if target_calories > 0 else 0
            
            if cal_percent > 10:
                warnings.append(f"⚠️ **Calorie Alert**: You are {int(cal_diff)} kcal ({int(cal_percent)}%) over your daily target.")
                warnings.append("💡 *Suggestion*: Consider a lighter dinner or skipping a snack to balance this out.")
            elif cal_percent < -20:
                warnings.append(f"⚠️ **Calorie Alert**: You are {int(abs(cal_diff))} kcal under your target. Make sure to eat enough!")
            
            # Macro Checks (Threshold: +/- 20%)
            # Protein
            prot_diff = actual.get('protein_g', 0) - target_protein
            if target_protein > 0 and (prot_diff / target_protein) < -0.2:
                 warnings.append(f"⚠️ **Protein Alert**: You're low on protein today ({int(actual.get('protein_g', 0))}g vs {int(target_protein)}g).")
            
            # Carbs
            carb_diff = actual.get('carbohydrates_g', 0) - target_carbs
            if target_carbs > 0 and (carb_diff / target_carbs) > 0.2:
                 warnings.append(f"⚠️ **Carb Alert**: High carbohydrate intake today.")
            
            # Fat
            fat_diff = actual.get('fat_g', 0) - target_fat
            if target_fat > 0 and (fat_diff / target_fat) > 0.2:
                 warnings.append(f"⚠️ **Fat Alert**: High fat intake today.")

            return warnings

        except Exception as e:
            st.error(f"Monitoring Agent Error: {e}")
            return []
