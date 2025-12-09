import os
import sys
from dotenv import load_dotenv

# Add project root to path
# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.db import get_snowflake_connection

def check_day_mapping():
    load_dotenv()
    conn = get_snowflake_connection()
    user_id = 'a744853e-1733-49ef-85d8-d2eb140d197d'
    
    cursor = conn.cursor()
    query = """
        SELECT dm.day_number, dm.day_name, dm.meal_date
        FROM daily_meals dm
        JOIN meal_plans mp ON dm.plan_id = mp.plan_id
        WHERE dm.user_id = %s AND mp.status = 'ACTIVE'
        GROUP BY dm.day_number, dm.day_name, dm.meal_date
        ORDER BY dm.day_number
    """
    cursor.execute(query, (user_id,))
    rows = cursor.fetchall()
    
    print(f"{'Day Num':<10} | {'Day Name':<15} | {'Date':<15}")
    print("-" * 45)
    for row in rows:
        print(f"{row[0]:<10} | {row[1]:<15} | {row[2]}")

if __name__ == "__main__":
    check_day_mapping()
