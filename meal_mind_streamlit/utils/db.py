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

        # Conversation Threads for Memory System
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS conversation_threads
                       (
                           thread_id VARCHAR(50) PRIMARY KEY,
                           user_id VARCHAR(50) NOT NULL,
                           title VARCHAR(255),
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                           last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                           message_count INT DEFAULT 0,
                           is_active BOOLEAN DEFAULT TRUE,
                           summary TEXT,
                           FOREIGN KEY (user_id) REFERENCES users(user_id)
                       )
                       """)

        # Thread Messages
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS thread_messages
                       (
                           message_id VARCHAR(50) PRIMARY KEY,
                           thread_id VARCHAR(50) NOT NULL,
                           role VARCHAR(20) NOT NULL,
                           content TEXT NOT NULL,
                           timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                           metadata VARIANT,
                           FOREIGN KEY (thread_id) REFERENCES conversation_threads(thread_id)
                       )
                       """)

        # Thread Checkpoints for LangGraph
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS thread_checkpoints
                       (
                           checkpoint_id VARCHAR(50) PRIMARY KEY,
                           thread_id VARCHAR(50) NOT NULL,
                           checkpoint_data VARIANT,
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                           FOREIGN KEY (thread_id) REFERENCES conversation_threads(thread_id)
                       )
                       """)

        # User Feedback (Likes/Dislikes)
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS user_feedback
                       (
                           feedback_id VARCHAR(50) PRIMARY KEY,
                           user_id VARCHAR(50) NOT NULL,
                           feedback_type VARCHAR(50),
                           entity_type VARCHAR(50),
                           entity_id VARCHAR(50),
                           entity_name VARCHAR(255),
                           sentiment VARCHAR(20),
                           intensity INT,
                           context TEXT,
                           extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                           source VARCHAR(50),
                           FOREIGN KEY (user_id) REFERENCES users(user_id)
                       )
                       """)

        # User Preferences (Long-term Memory)
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS user_preferences
                       (
                           preference_id VARCHAR(50) PRIMARY KEY,
                           user_id VARCHAR(50) NOT NULL,
                           preference_type VARCHAR(50),
                           preference_key VARCHAR(255),
                           preference_value TEXT,
                           confidence_score FLOAT,
                           frequency INT DEFAULT 1,
                           last_mentioned TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                           expires_at TIMESTAMP,
                           is_active BOOLEAN DEFAULT TRUE,
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


@st.cache_data(ttl=600)
def get_user_profile(_conn, user_id):
    """Fetch user profile as a dictionary"""
    try:
        cursor = _conn.cursor()
        cursor.execute("""
            SELECT username, age, gender, height_cm, weight_kg, bmi, activity_level, 
                   health_goal, dietary_restrictions, food_allergies, daily_calories,
                   daily_protein, daily_carbohydrate, daily_fat, daily_fiber, updated_at
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



@st.cache_data(ttl=60)
def get_user_inventory(_conn, user_id):
    """Fetch user inventory as a DataFrame-like string or list"""
    import pandas as pd
    try:
        cursor = _conn.cursor()
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



@st.cache_data(ttl=60)
def get_latest_meal_plan(_conn, user_id):
    """Fetch the latest active meal plan"""
    import json
    try:
        cursor = _conn.cursor()
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


def get_meals_by_criteria(conn, user_id, day_number=None, meal_type=None, meal_date=None):
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
            
        if meal_date is not None:
            query += " AND dm.meal_date = %s"
            params.append(meal_date)
        
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


def get_meals_by_date(conn, user_id, meal_date=None, meal_type=None):
    """
    Get meals by specific date (for historical queries like 'What did I eat last Monday?')
    
    Args:
        conn: Database connection
        user_id: User ID
        meal_date: Specific date (YYYY-MM-DD) or None for most recent
        meal_type: breakfast, lunch, dinner, snacks, or None for all
    
    Returns:
        List of meal dictionaries with full details
    """
    import json
    cursor = conn.cursor()
    try:
        query = """
            SELECT 
                md.meal_type,
                md.meal_name,
                md.ingredients_with_quantities,
                md.recipe,
                md.nutrition,
                md.preparation_time,
                md.cooking_time,
                md.servings,
                md.difficulty_level,
                dm.meal_date,
                dm.day_name
            FROM meal_details md
            JOIN daily_meals dm ON md.meal_id = dm.meal_id
            JOIN meal_plans mp ON dm.plan_id = mp.plan_id
            WHERE mp.user_id = %s
        """
        
        params = [user_id]
        
        if meal_date:
            query += " AND dm.meal_date = %s"
            params.append(meal_date)
        else:
            # Get most recent meals
            query += " AND mp.status = 'ACTIVE'"
        
        if meal_type:
            query += " AND md.meal_type = %s"
            params.append(meal_type.lower())
        
        query += " ORDER BY dm.meal_date DESC, md.meal_type"
        
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        
        meals = []
        for row in rows:
            meal = {
                'meal_type': row[0],
                'meal_name': row[1],
                'ingredients': json.loads(row[2]) if row[2] else [],
                'recipe': json.loads(row[3]) if row[3] else {},
                'nutrition': json.loads(row[4]) if row[4] else {},
                'preparation_time': row[5],
                'cooking_time': row[6],
                'servings': row[7],
                'difficulty_level': row[8],
                'meal_date': row[9],
                'day_name': row[10]
            }
            meals.append(meal)
        
        return meals
    
    except Exception as e:
        st.error(f"Error fetching meals by date: {e}")
        return []
    finally:
        cursor.close()


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


def get_daily_meal_id(conn, user_id, date):
    """Get the meal_id (daily record) for a specific date"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT meal_id 
            FROM daily_meals 
            WHERE user_id = %s AND meal_date = %s
        """, (user_id, date))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        st.error(f"Error fetching daily meal ID: {e}")
        return None
    finally:
        cursor.close()


def get_meal_detail_id(conn, daily_meal_id, meal_type):
    """Get the detail_id for a specific meal type on a specific day"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT detail_id 
            FROM meal_details 
            WHERE meal_id = %s AND meal_type = %s
        """, (daily_meal_id, meal_type))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        st.error(f"Error fetching meal detail ID: {e}")
        return None
    finally:
        cursor.close()

def get_meal_detail_by_id(conn, detail_id):
    """Get full meal details by detail_id"""
    import json
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                meal_name,
                ingredients_with_quantities,
                recipe,
                nutrition,
                preparation_time,
                cooking_time,
                servings,
                difficulty_level
            FROM meal_details 
            WHERE detail_id = %s
        """, (detail_id,))
        row = cursor.fetchone()
        
        if row:
            return {
                'meal_name': row[0],
                'ingredients_with_quantities': json.loads(row[1]) if row[1] else [],
                'recipe': json.loads(row[2]) if row[2] else {},
                'nutrition': json.loads(row[3]) if row[3] else {},
                'preparation_time': row[4],
                'cooking_time': row[5],
                'servings': row[6],
                'difficulty_level': row[7]
            }
        return None
    except Exception as e:
        st.error(f"Error fetching meal detail: {e}")
        return None
    finally:
        cursor.close()


def update_meal_detail(conn, detail_id, meal_data):
    """Update a specific meal's details (recipe, nutrition, etc.)"""
    import json
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE meal_details 
            SET meal_name = %s,
                ingredients_with_quantities = PARSE_JSON(%s),
                recipe = PARSE_JSON(%s),
                nutrition = PARSE_JSON(%s),
                preparation_time = %s,
                cooking_time = %s,
                servings = %s,
                difficulty_level = %s
            WHERE detail_id = %s
        """, (
            meal_data.get('meal_name'),
            json.dumps(meal_data.get('ingredients_with_quantities', [])),
            json.dumps(meal_data.get('recipe', {})),
            json.dumps(meal_data.get('nutrition', {})),
            meal_data.get('preparation_time', 0),
            meal_data.get('cooking_time', 0),
            meal_data.get('servings', 1),
            meal_data.get('difficulty_level', 'medium'),
            detail_id
        ))

        
        if cursor.rowcount == 0:
            print(f"WARNING: update_meal_detail updated 0 rows for detail_id {detail_id}")
            return False
            
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error updating meal detail: {e}")
        return False
    finally:
        cursor.close()


def get_all_meal_details_for_day(conn, daily_meal_id):
    """Get all meal details for a specific day to recalculate totals"""
    import json
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT nutrition 
            FROM meal_details 
            WHERE meal_id = %s
        """, (daily_meal_id,))
        rows = cursor.fetchall()
        
        meals_nutrition = []
        for row in rows:
            if row[0]:
                try:
                    meals_nutrition.append(json.loads(row[0]) if isinstance(row[0], str) else row[0])
                except:
                    pass
        return meals_nutrition
    except Exception as e:
        st.error(f"Error fetching daily meals for recalculation: {e}")
        return []
    finally:
        cursor.close()


def update_daily_nutrition(conn, daily_meal_id, total_nutrition):
    """Update the total nutrition for a day"""
    import json
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE daily_meals 
            SET total_nutrition = PARSE_JSON(%s)
            WHERE meal_id = %s
        """, (json.dumps(total_nutrition), daily_meal_id))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error updating daily nutrition: {e}")
        return False
    finally:
        cursor.close()
@st.cache_data(ttl=600)
def get_dashboard_stats(_conn, user_id):
    """Fetch dashboard stats efficiently"""
    return get_user_profile(_conn, user_id)

@st.cache_data(ttl=600)
def get_meal_plan_overview(_conn, user_id, specific_plan_id=None):
    """Fetch active meal plan overview"""
    import json
    try:
        cursor = _conn.cursor()
        
        if specific_plan_id:
            cursor.execute("""
                SELECT p.plan_id,
                       p.plan_name,
                       p.start_date,
                       p.end_date,
                       p.week_summary,
                       p.created_at,
                       p.status
                FROM meal_plans p
                WHERE p.plan_id = %s AND p.user_id = %s
            """, (specific_plan_id, user_id))
        else:
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
                ORDER BY 
                    CASE 
                        WHEN CURRENT_DATE() BETWEEN p.start_date AND p.end_date THEN 1 
                        ELSE 2 
                    END,
                    p.created_at DESC 
                LIMIT 1
            """, (user_id,))
        
        row = cursor.fetchone()
        if row:
            columns = [col[0].lower() for col in cursor.description]
            return dict(zip(columns, row))
        return None
    except Exception as e:
        st.error(f"Error fetching meal plan overview: {e}")
        return None
    finally:
        cursor.close()

def get_future_meal_plan(_conn, user_id):
    """Check if a future meal plan exists"""
    try:
        cursor = _conn.cursor()
        cursor.execute("""
            SELECT plan_id, start_date
            FROM meal_plans
            WHERE user_id = %s
            AND start_date > CURRENT_DATE()
            ORDER BY start_date ASC
            LIMIT 1
        """, (user_id,))
        row = cursor.fetchone()
        if row:
            return {'plan_id': row[0], 'start_date': row[1]}
        return None
    except Exception as e:
        return None
    finally:
        cursor.close()

@st.cache_data(ttl=600)
def get_daily_meals_for_plan(_conn, plan_id):
    """Fetch daily meals for a specific plan"""
    try:
        cursor = _conn.cursor()
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
        
        rows = cursor.fetchall()
        if rows:
            columns = [col[0].lower() for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        return []
    except Exception as e:
        st.error(f"Error fetching daily meals: {e}")
        return []
    finally:
        cursor.close()

@st.cache_data(ttl=600)
def get_meal_details_for_day_view(_conn, meal_id):
    """Fetch meal details for a specific day"""
    try:
        cursor = _conn.cursor()
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
        
        rows = cursor.fetchall()
        if rows:
            columns = [col[0].lower() for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        return []
    except Exception as e:
        st.error(f"Error fetching meal details: {e}")
        return []
    finally:
        cursor.close()

@st.cache_data(ttl=600)
def get_weekly_meal_details(_conn, plan_id):
    """Fetch ALL meal details for a specific plan (optimized for fast day switching)"""
    try:
        cursor = _conn.cursor()
        cursor.execute("""
            SELECT dm.day_number,
                   dm.meal_id,
                   md.meal_type,
                   md.meal_name,
                   md.ingredients_with_quantities,
                   md.recipe,
                   md.nutrition,
                   md.preparation_time,
                   md.cooking_time,
                   md.servings,
                   md.serving_size,
                   md.difficulty_level
            FROM daily_meals dm
            JOIN meal_details md ON dm.meal_id = md.meal_id
            WHERE dm.plan_id = %s
            ORDER BY dm.day_number, 
                     CASE md.meal_type
                         WHEN 'breakfast' THEN 1
                         WHEN 'lunch' THEN 2
                         WHEN 'snacks' THEN 3
                         WHEN 'dinner' THEN 4
                     END
        """, (plan_id,))
        
        rows = cursor.fetchall()
        if rows:
            columns = [col[0].lower() for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        return []
    except Exception as e:
        st.error(f"Error fetching weekly meal details: {e}")
        return []
    finally:
        cursor.close()
