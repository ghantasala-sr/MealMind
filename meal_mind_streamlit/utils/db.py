import streamlit as st
import snowflake.connector
from snowflake.snowpark import Session
import os
from dotenv import load_dotenv

load_dotenv()

def create_tables(conn):
    """Create all necessary tables if they don't exist"""
    cursor = conn.cursor()

    try:
        # Users table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS users
                       (
                           user_id VARCHAR(50) PRIMARY KEY,
                           username VARCHAR(100) UNIQUE NOT NULL,
                           password_hash VARCHAR(255) NOT NULL,
                           email VARCHAR(255),
                           age INT,
                           gender VARCHAR(20),
                           height_cm FLOAT,
                           weight_kg FLOAT,
                           bmi FLOAT,
                           life_stage VARCHAR(50),
                           pregnancy_status VARCHAR(50),
                           lactation_status VARCHAR(50),
                           activity_level VARCHAR(50),
                           health_goal VARCHAR(100),
                           dietary_restrictions TEXT,
                           food_allergies TEXT,
                           preferred_cuisines TEXT,
                           daily_calories INT,
                           daily_protein FLOAT,
                           daily_carbohydrate FLOAT,
                           daily_fat FLOAT,
                           daily_fiber FLOAT,
                           profile_completed BOOLEAN DEFAULT FALSE,
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                           last_login TIMESTAMP,
                           updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
                       )
                       """)

        # Planning Schedule
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS planning_schedule
                       (
                           schedule_id VARCHAR(50) PRIMARY KEY,
                           user_id VARCHAR(50) NOT NULL,
                           plan_start_date DATE NOT NULL,
                           plan_end_date DATE NOT NULL,
                           next_plan_date DATE NOT NULL,
                           status VARCHAR(20) DEFAULT 'ACTIVE',
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                           FOREIGN KEY (user_id) REFERENCES users(user_id)
                       )
                       """)

        # Inventory
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS inventory
                       (
                           inventory_id VARCHAR(50) PRIMARY KEY,
                           user_id VARCHAR(50) NOT NULL,
                           item_name VARCHAR(255) NOT NULL,
                           quantity FLOAT NOT NULL,
                           unit VARCHAR(50) NOT NULL,
                           category VARCHAR(100),
                           notes TEXT,
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                           updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                           FOREIGN KEY (user_id) REFERENCES users(user_id)
                       )
                       """)

        # Meal Plans
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS meal_plans
                       (
                           plan_id VARCHAR(50) PRIMARY KEY,
                           user_id VARCHAR(50) NOT NULL,
                           schedule_id VARCHAR(50),
                           plan_name VARCHAR(255),
                           start_date DATE NOT NULL,
                           end_date DATE NOT NULL,
                           week_summary VARIANT,
                           status VARCHAR(20) DEFAULT 'ACTIVE',
                           generated_by VARCHAR(50) DEFAULT 'AGENT',
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                           FOREIGN KEY (user_id) REFERENCES users(user_id),
                           FOREIGN KEY (schedule_id) REFERENCES planning_schedule(schedule_id)
                       )
                       """)

        # Daily Meals
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS daily_meals
                       (
                           meal_id VARCHAR(50) PRIMARY KEY,
                           plan_id VARCHAR(50) NOT NULL,
                           user_id VARCHAR(50) NOT NULL,
                           day_number INT NOT NULL,
                           day_name VARCHAR(20),
                           meal_date DATE,
                           total_nutrition VARIANT,
                           inventory_impact VARIANT,
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                           FOREIGN KEY (plan_id) REFERENCES meal_plans(plan_id),
                           FOREIGN KEY (user_id) REFERENCES users(user_id)
                       )
                       """)

        # Meal Details
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS meal_details
                       (
                           detail_id VARCHAR(50) PRIMARY KEY,
                           meal_id VARCHAR(50) NOT NULL,
                           meal_type VARCHAR(20) NOT NULL,
                           meal_name VARCHAR(255) NOT NULL,
                           ingredients_with_quantities VARIANT,
                           recipe VARIANT,
                           nutrition VARIANT,
                           preparation_time INT,
                           cooking_time INT,
                           servings INT,
                           serving_size VARCHAR(100),
                           difficulty_level VARCHAR(20),
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                           FOREIGN KEY (meal_id) REFERENCES daily_meals(meal_id)
                       )
                       """)

        # Shopping Lists
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS shopping_lists
                       (
                           list_id VARCHAR(50) PRIMARY KEY,
                           plan_id VARCHAR(50) NOT NULL,
                           user_id VARCHAR(50) NOT NULL,
                           shopping_data VARIANT,
                           total_estimated_cost FLOAT,
                           total_items_from_inventory INT,
                           total_items_to_purchase INT,
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                           FOREIGN KEY (plan_id) REFERENCES meal_plans(plan_id),
                           FOREIGN KEY (user_id) REFERENCES users(user_id)
                       )
                       """)

        conn.commit()
        
        # Migration: Add preferred_cuisines if not exists
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN preferred_cuisines TEXT")
            conn.commit()
        except:
            pass # Column likely exists

    except Exception as e:
        st.error(f"Error creating tables: {e}")
    finally:
        cursor.close()


# @st.cache_resource
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


def get_user_profile(conn, user_id):
    """Fetch user profile as a dictionary"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT username, age, gender, height_cm, weight_kg, activity_level, 
                   health_goal, dietary_restrictions, food_allergies, daily_calories
            FROM users 
            WHERE user_id = %s
        """, (user_id,))
        
        row = cursor.fetchone()
        if row:
            columns = [col[0].lower() for col in cursor.description]
            return dict(zip(columns, row))
        return {}
    except Exception as e:
        st.error(f"Error fetching profile: {e}")
        return {}
    finally:
        cursor.close()


def get_user_inventory(conn, user_id):
    """Fetch user inventory as a DataFrame-like string or list"""
    import pandas as pd
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT item_name, quantity, unit, category
            FROM inventory
            WHERE user_id = %s
            ORDER BY category, item_name
        """, (user_id,))
        
        rows = cursor.fetchall()
        if rows:
            df = pd.DataFrame(rows, columns=['Item', 'Qty', 'Unit', 'Category'])
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching inventory: {e}")
        return pd.DataFrame()
    finally:
        cursor.close()


def get_latest_meal_plan(conn, user_id):
    """Fetch the latest active meal plan"""
    import json
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT week_summary, plan_name, start_date, end_date
            FROM meal_plans
            WHERE user_id = %s AND status = 'ACTIVE'
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,))
        
        row = cursor.fetchone()
        if row:
            # week_summary is a VARIANT (JSON)
            week_summary_json = row[0]
            if isinstance(week_summary_json, str):
                try:
                    week_summary = json.loads(week_summary_json)
                except:
                    week_summary = week_summary_json
            else:
                week_summary = week_summary_json

            return {
                "meal_plan": {
                    "week_summary": week_summary,
                    "days": "See daily_meals table for details" # Simplified for summary
                },
                "plan_name": row[1],
                "start_date": str(row[2]),
                "end_date": str(row[3])
            }
        return None
    except Exception as e:
        st.error(f"Error fetching meal plan: {e}")
        return None
    finally:
        cursor.close()


def get_meals_by_criteria(conn, user_id, day_number=None, meal_type=None):
    """Retrieve meals based on day and/or meal type from the latest active meal plan"""
    import json
    try:
        cursor = conn.cursor()
        
        # Build dynamic query
        query = """
            SELECT 
                dm.day_number,
                dm.day_name,
                dm.meal_date,
                md.meal_type,
                md.meal_name,
                md.ingredients_with_quantities,
                md.nutrition,
                md.recipe,
                md.preparation_time,
                md.cooking_time
            FROM daily_meals dm
            JOIN meal_details md ON dm.meal_id = md.meal_id
            JOIN meal_plans mp ON dm.plan_id = mp.plan_id
            WHERE dm.user_id = %s 
            AND mp.status = 'ACTIVE'
        """
        
        params = [user_id]
        
        if day_number is not None:
            query += " AND dm.day_number = %s"
            params.append(day_number)
        
        if meal_type is not None:
            query += " AND md.meal_type = %s"
            params.append(meal_type)
        
        query += " ORDER BY dm.day_number, md.meal_type"
        
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        
        meals = []
        for row in rows:
            # Parse JSON fields
            ingredients = row[5]
            if isinstance(ingredients, str):
                try:
                    ingredients = json.loads(ingredients)
                except:
                    ingredients = []
            
            nutrition = row[6]
            if isinstance(nutrition, str):
                try:
                    nutrition = json.loads(nutrition)
                except:
                    nutrition = {}
            
            recipe = row[7]
            if isinstance(recipe, str):
                try:
                    recipe = json.loads(recipe)
                except:
                    recipe = {}
            
            meal_data = {
                'day_number': row[0],
                'day_name': row[1],
                'meal_date': str(row[2]) if row[2] else None,
                'meal_type': row[3],
                'meal_name': row[4],
                'ingredients_with_quantities': ingredients,
                'nutrition': nutrition,
                'recipe': recipe,
                'preparation_time': row[8],
                'cooking_time': row[9]
            }
            meals.append(meal_data)
        
        return meals
    
    except Exception as e:
        st.error(f"Error retrieving meals: {e}")
        return []
    finally:
        cursor.close()


def get_meal_details_by_type(conn, user_id, meal_type):
    """Get all meals of a specific type (e.g., all breakfasts) from active plan"""
    return get_meals_by_criteria(conn, user_id, day_number=None, meal_type=meal_type)


def search_meals_by_ingredient(conn, user_id, ingredient_name):
    """Search for meals containing a specific ingredient"""
    import json
    try:
        cursor = conn.cursor()
        
        query = """
            SELECT 
                dm.day_name,
                md.meal_type,
                md.meal_name,
                md.ingredients_with_quantities
            FROM daily_meals dm
            JOIN meal_details md ON dm.meal_id = md.meal_id
            JOIN meal_plans mp ON dm.plan_id = mp.plan_id
            WHERE dm.user_id = %s 
            AND mp.status = 'ACTIVE'
        """
        
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        
        matching_meals = []
        for row in rows:
            ingredients = row[3]
            if isinstance(ingredients, str):
                try:
                    ingredients = json.loads(ingredients)
                except:
                    ingredients = []
            
            # Check if ingredient is in this meal
            for ing in ingredients:
                if ingredient_name.lower() in ing.get('ingredient', '').lower():
                    matching_meals.append({
                        'day_name': row[0],
                        'meal_type': row[1],
                        'meal_name': row[2],
                        'matching_ingredient': ing.get('ingredient')
                    })
                    break
        
        return matching_meals
    
    except Exception as e:
        st.error(f"Error searching meals by ingredient: {e}")
        return []
    finally:
        cursor.close()

