import streamlit as st
import json
import uuid
import pandas as pd
from datetime import datetime, timedelta
from utils.agent import MealPlanAgentWithExtraction, MealPlanState
from utils.db import get_snowpark_session

def generate_comprehensive_meal_plan_prompt(user_profile, inventory_df, start_day=1, num_days=7, previous_plan_context=None):
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

    # Calculate dates for the prompt
    start_date = datetime.now().date() + timedelta(days=start_day-1)
    end_date = start_date + timedelta(days=num_days-1)
    
    # Context section if provided
    context_section = ""
    if previous_plan_context:
        context_section = f"""
CONTEXT FROM PREVIOUS DAYS (ALREADY PLANNED):
{previous_plan_context}
IMPORTANT: 
- Do NOT repeat the main meals listed above (try to offer variety).
- Note the inventory items already used above; ensure we don't exceed available quantities if possible.
"""

    prompt = f"""Generate a detailed meal plan for {num_days} days, from Day {start_day} to Day {start_day + num_days - 1}.

IMPORTANT: The plan starts on {start_date.strftime('%A, %B %d, %Y')} (Day {start_day}) and ends on {end_date.strftime('%A, %B %d, %Y')}.
Ensure day names match these actual calendar dates.
{context_section}
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
- Preferred Cuisines: {user_profile.get('preferred_cuisines', 'Any')}

DAILY NUTRITIONAL TARGETS:
- Calories: {user_profile['daily_calories']} kcal
- Protein: {user_profile['daily_protein']:.1f}g
- Carbohydrates: {user_profile['daily_carbohydrate']:.1f}g
- Fat: {user_profile['daily_fat']:.1f}g
- Fiber: {user_profile['daily_fiber']:.1f}g

CURRENT INVENTORY:
{json.dumps(inventory_by_category, indent=2)}

Create a detailed meal plan for these {num_days} days with complete recipes and inventory optimization.
Generate plans based ONLY on available inventory where possible.
If a critical item (like protein source) is missing from inventory, explicitly mention it as a REQUIRED PURCHASE.
Strictly follow dietary restrictions and allergies.
Prioritize recipes from the user's preferred cuisines ({user_profile.get('preferred_cuisines', 'Any')}) where possible.

Return the meal plan in valid JSON format with this EXACT structure:
{{
  "user_summary": {{
    "user_id": "{user_profile['user_id']}",
    "health_goal": "{user_profile['health_goal']}",
    ...
  }},
  "meal_plan": {{
    "week_summary": {{
      "average_daily_calories": 0,
      "inventory_utilization_rate": 0,
      "future_suggestions": []
    }},
    "days": [
      {{
        "day": {start_day},
        "day_name": "{start_date.strftime('%A')}",
        "total_nutrition": {{ "calories": 0, "protein_g": 0, "carbohydrates_g": 0, "fat_g": 0, "fiber_g": 0 }},
        "inventory_impact": {{ "items_used": 0, "new_purchases_needed": 0 }},
        "meals": {{
          "breakfast": {{
            "meal_name": "Name",
            "ingredients_with_quantities": [
              {{ "ingredient": "Name", "quantity": 0, "unit": "g", "from_inventory": true/false }}
            ],
            "recipe": {{ "prep_steps": [], "cooking_instructions": [] }},
            "nutrition": {{ "calories": 0, "protein_g": 0, ... }}
          }},
          "lunch": {{ ... }},
          "dinner": {{ ... }},
          "snacks": {{ ... }}
        }}
      }}
    ]
  }},
  "recommendations": {{
    "shopping_list_summary": {{
      "proteins": [], "produce": [], "pantry": [],
      "total_items_from_inventory": 0,
      "total_items_to_purchase": 0
    }}
  }}
}}
"""

    return prompt

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
                               float(shopping_data.get('total_estimated_cost', 0)) if isinstance(shopping_data.get('total_estimated_cost'), (int, float)) else 0.0,
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


@st.cache_data(ttl=600)
def get_inventory_items(_conn, user_id):
    """Get all inventory items for a user"""
    cursor = _conn.cursor()
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
                              preferred_cuisines,
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
                'preferred_cuisines': profile_data[9] or 'Any',
                'daily_calories': profile_data[10],
                'daily_protein': profile_data[11],
                'daily_carbohydrate': profile_data[12],
                'daily_fat': profile_data[13],
                'daily_fiber': profile_data[14]
            }

            # Get inventory
            inventory_df = get_inventory_items(conn, user_id)

            # Generate prompt
            prompt = generate_comprehensive_meal_plan_prompt(user_profile, inventory_df)

            # Call agent with LangGraph
            session = get_snowpark_session()
            agent = MealPlanAgentWithExtraction(session)
            
            # Initialize state
            initial_state = MealPlanState(
                user_profile=user_profile,
                inventory_df=inventory_df,
                prompt=prompt,
                meal_plan_json=None,
                suggestions_json=None,
                error=None
            )
            
            # Build and invoke graph
            workflow = agent.build_graph()
            final_state = workflow.invoke(initial_state)
            
            meal_plan_data = final_state.get('meal_plan_json')
            suggestions = final_state.get('suggestions_json')

            if meal_plan_data:
                # Merge suggestions into the plan data structure
                if suggestions:
                    meal_plan_data['future_suggestions'] = suggestions

                # Create schedule
                schedule_id = str(uuid.uuid4())
                tomorrow = datetime.now().date() + timedelta(days=1)
                plan_end = tomorrow + timedelta(days=7)

                # Deactivate old schedules
                cursor.execute("UPDATE planning_schedule SET status = 'INACTIVE' WHERE user_id = %s", (user_id,))

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
