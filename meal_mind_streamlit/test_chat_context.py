import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.db import get_snowflake_connection, get_meals_by_criteria, get_latest_meal_plan

def test_context_retrieval():
    load_dotenv()
    conn = get_snowflake_connection()
    user_id = 'a744853e-1733-49ef-85d8-d2eb140d197d'
    
    print(f"Testing context retrieval for user: {user_id}")
    
    # 1. Test get_latest_meal_plan
    print("\n--- Latest Meal Plan ---")
    plan = get_latest_meal_plan(conn, user_id)
    if plan:
        print(f"Plan Name: {plan.get('plan_name')}")
        print(f"Dates: {plan.get('start_date')} to {plan.get('end_date')}")
    else:
        print("No active plan found.")

    # 2. Test get_meals_by_criteria
    print("\n--- Daily Meals ---")
    meals = get_meals_by_criteria(conn, user_id)
    print(f"Found {len(meals)} meals.")
    
    if meals:
        # Group by day to see structure
        days = {}
        for meal in meals:
            day = meal['day_name']
            if day not in days:
                days[day] = []
            days[day].append(f"{meal['meal_type']}: {meal['meal_name']}")
        
        for day, meal_list in days.items():
            print(f"\n{day}:")
            for m in meal_list:
                print(f"  - {m}")
    else:
        print("No meals returned by get_meals_by_criteria.")

if __name__ == "__main__":
    test_context_retrieval()
