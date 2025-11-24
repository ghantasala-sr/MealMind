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
