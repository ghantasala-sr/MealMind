import sys
import os
from datetime import datetime, timedelta, date
import pandas as pd
import json

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helpers import generate_comprehensive_meal_plan_prompt
from utils.agent import MealPlanAgentWithExtraction

def test_prompt_generation_dates():
    print("\n=== Testing Prompt Generation Dates ===")
    
    # Mock data
    user_profile = {
        'user_id': 'test_user',
        'age': 30,
        'gender': 'Male',
        'height_cm': 180,
        'weight_kg': 75,
        'bmi': 23.1,
        'activity_level': 'Moderate',
        'health_goal': 'Maintenance',
        'dietary_restrictions': 'None',
        'food_allergies': 'None',
        'daily_calories': 2000,
        'daily_protein': 150,
        'daily_carbohydrate': 200,
        'daily_fat': 65,
        'daily_fiber': 30
    }
    inventory_df = pd.DataFrame()
    
    # Test 1: Default (Today)
    print("Test 1: Default Start Date (Today)")
    prompt_default = generate_comprehensive_meal_plan_prompt(user_profile, inventory_df, start_day=1, num_days=7)
    today = datetime.now().date()
    expected_start = today.strftime('%A, %B %d, %Y')
    if expected_start in prompt_default:
        print(f"✅ PASS: Prompt contains correct default start date: {expected_start}")
    else:
        print(f"❌ FAIL: Prompt missing default start date {expected_start}")

    # Test 2: Explicit Start Date (Future)
    print("\nTest 2: Explicit Start Date (Future)")
    future_date = today + timedelta(days=10)
    prompt_future = generate_comprehensive_meal_plan_prompt(user_profile, inventory_df, start_day=1, num_days=7, start_date_obj=future_date)
    expected_future_start = future_date.strftime('%A, %B %d, %Y')
    
    if expected_future_start in prompt_future:
        print(f"✅ PASS: Prompt contains correct explicit start date: {expected_future_start}")
    else:
        print(f"❌ FAIL: Prompt missing explicit start date {expected_future_start}")
        
    # Test 3: Explicit Start Date + Batch Offset
    print("\nTest 3: Explicit Start Date + Batch Offset (Day 5)")
    # If start_day=5, the prompt should say "starts on [future_date + 4 days]"
    prompt_batch = generate_comprehensive_meal_plan_prompt(user_profile, inventory_df, start_day=5, num_days=3, start_date_obj=future_date)
    batch_start_date = future_date + timedelta(days=4) # Day 5 is 4 days after Day 1
    expected_batch_start = batch_start_date.strftime('%A, %B %d, %Y')
    
    if expected_batch_start in prompt_batch:
        print(f"✅ PASS: Prompt contains correct batch start date: {expected_batch_start}")
    else:
        print(f"❌ FAIL: Prompt missing batch start date {expected_batch_start}")

def test_fix_day_names():
    print("\n=== Testing fix_day_names_in_plan ===")
    
    agent = MealPlanAgentWithExtraction(session=None) # Mock session
    
    # Mock meal plan data
    meal_plan_data = {
        "meal_plan": {
            "days": [
                {"day": 1, "day_name": "WrongName", "meals": {}},
                {"day": 2, "day_name": "WrongName", "meals": {}},
                {"day": 3, "day_name": "WrongName", "meals": {}}
            ]
        }
    }
    
    # Test 1: Default (Today)
    print("Test 1: Default Start Date (Today)")
    fixed_default = agent.fix_day_names_in_plan(meal_plan_data.copy())
    today = datetime.now().date()
    expected_day1 = today.strftime('%A')
    expected_date1 = today.isoformat()
    
    if fixed_default['meal_plan']['days'][0]['day_name'] == expected_day1:
        print(f"✅ PASS: Day 1 name correct: {expected_day1}")
    else:
        print(f"❌ FAIL: Day 1 name incorrect. Got {fixed_default['meal_plan']['days'][0]['day_name']}, expected {expected_day1}")
        
    if fixed_default['meal_plan']['days'][0].get('date') == expected_date1:
        print(f"✅ PASS: Day 1 date correct: {expected_date1}")
    else:
        print(f"❌ FAIL: Day 1 date incorrect. Got {fixed_default['meal_plan']['days'][0].get('date')}, expected {expected_date1}")

    # Test 2: Explicit Start Date (Future)
    print("\nTest 2: Explicit Start Date (Future)")
    future_date = today + timedelta(days=5)
    fixed_future = agent.fix_day_names_in_plan(meal_plan_data.copy(), start_date=future_date)
    
    expected_future_day1 = future_date.strftime('%A')
    expected_future_date1 = future_date.isoformat()
    
    if fixed_future['meal_plan']['days'][0]['day_name'] == expected_future_day1:
        print(f"✅ PASS: Future Day 1 name correct: {expected_future_day1}")
    else:
        print(f"❌ FAIL: Future Day 1 name incorrect. Got {fixed_future['meal_plan']['days'][0]['day_name']}, expected {expected_future_day1}")

    if fixed_future['meal_plan']['days'][0].get('date') == expected_future_date1:
        print(f"✅ PASS: Future Day 1 date correct: {expected_future_date1}")
    else:
        print(f"❌ FAIL: Future Day 1 date incorrect. Got {fixed_future['meal_plan']['days'][0].get('date')}, expected {expected_future_date1}")

if __name__ == "__main__":
    try:
        test_prompt_generation_dates()
        test_fix_day_names()
        print("\n✨ All tests completed!")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
