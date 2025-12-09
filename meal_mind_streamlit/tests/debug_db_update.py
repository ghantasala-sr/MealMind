import os
import sys
import json
from dotenv import load_dotenv

# Add project root to path
# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.db import get_snowflake_connection, get_daily_meal_id, get_meal_detail_id, get_meal_detail_by_id, update_meal_detail

def debug_update():
    load_dotenv()
    conn = get_snowflake_connection()
    user_id = 'a744853e-1733-49ef-85d8-d2eb140d197d'
    date = '2025-12-05' # Today
    meal_type = 'breakfast'
    
    print(f"DEBUG: Fetching meal for {date} ({meal_type})...")
    
    daily_meal_id = get_daily_meal_id(conn, user_id, date)
    if not daily_meal_id:
        print("ERROR: No daily_meal_id found!")
        return

    detail_id = get_meal_detail_id(conn, daily_meal_id, meal_type)
    if not detail_id:
        print("ERROR: No detail_id found!")
        return
        
    print(f"DEBUG: Found detail_id: {detail_id}")
    
    current_meal = get_meal_detail_by_id(conn, detail_id)
    print("DEBUG: Current Meal Data in DB:")
    print(json.dumps(current_meal, indent=2))
    
    if "chai" in str(current_meal).lower():
        print("FOUND: 'chai' is in the database record.")
    else:
        print("NOT FOUND: 'chai' is NOT in the database record.")

if __name__ == "__main__":
    debug_update()
