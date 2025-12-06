from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.exceptions import AirflowException
from datetime import datetime, timedelta
import sys
import os
import logging
import json

# ==============================================================================
# CONFIGURATION & LOGGING SETUP
# ==============================================================================
# Configure logging to show up in Airflow logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("meal_mind_dag")

# DYNAMICALLY GET PROJECT ROOT
# This gets the directory where this DAG file is located (e.g., /opt/airflow/dags/meal_mind_streamlit)
# This ensures it works in Docker, Local, or any other environment without manual changes.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Add project root to python path
if PROJECT_ROOT not in sys.path:
    logger.info(f"Adding {PROJECT_ROOT} to sys.path")
    sys.path.insert(0, PROJECT_ROOT)
else:
    logger.info(f"{PROJECT_ROOT} already in sys.path")

# Log current environment details for debugging
logger.info(f"Current Working Directory: {os.getcwd()}")
logger.info(f"Python Path: {sys.path}")

# Attempt imports
try:
    from utils.meal_plan_workflow import MealPlanWorkflow
    from utils.db import get_snowflake_connection
    logger.info("Successfully imported MealPlanWorkflow and db utils")
    IMPORTS_SUCCESS = True
except ImportError as e:
    logger.error(f"CRITICAL: Error importing project modules: {e}")
    IMPORTS_SUCCESS = False
    MealPlanWorkflow = None

# ==============================================================================
# TASKS
# ==============================================================================

def check_environment_setup(**context):
    """
    Task 1: Verify environment, imports, and database connection.
    Fails fast if the setup is incorrect.
    """
    logger.info("=== STARTING ENVIRONMENT CHECK ===")
    
    # 1. Check Imports
    if not IMPORTS_SUCCESS:
        raise AirflowException(
            f"Import failed. Ensure code is deployed to {PROJECT_ROOT} "
            "and contains 'utils' package."
        )
    
    # 2. Check Database Connection
    try:
        logger.info("Testing Snowflake connection...")
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT current_version()")
        version = cursor.fetchone()[0]
        logger.info(f"Snowflake Connection Successful! Version: {version}")
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Database Connection Failed: {e}")
        raise AirflowException(f"Database check failed: {e}")

    logger.info("=== ENVIRONMENT CHECK PASSED ===")


def run_meal_plan_generation(**context):
    """
    Task 2: Execute the Meal Plan Generation Workflow.
    """
    logger.info("=== STARTING MEAL PLAN GENERATION ===")
    
    if not MealPlanWorkflow:
        raise AirflowException("MealPlanWorkflow class is not available.")

    try:
        # Initialize Workflow
        logger.info("Initializing MealPlanWorkflow...")
        workflow = MealPlanWorkflow()
        
        # Run Workflow
        logger.info("Executing workflow.run()...")
        result = workflow.run()
        
        # Log Results
        success_count = result.get('success_count', 0)
        failure_count = result.get('failure_count', 0)
        errors = result.get('errors', [])
        
        logger.info("--- WORKFLOW FINISHED ---")
        logger.info(f"Success Count: {success_count}")
        logger.info(f"Failure Count: {failure_count}")
        
        # Log detailed errors if any
        if errors:
            logger.error("Encountered the following errors during execution:")
            for i, err in enumerate(errors, 1):
                logger.error(f"Error {i}: {json.dumps(err, default=str)}")
        
        # Fail the task if there were ANY failures or NO successes (assuming we expected work)
        # Adjust logic based on business rules. Here we fail if there are explicit failures.
        if failure_count > 0:
            raise AirflowException(
                f"Workflow completed with {failure_count} failures. Check logs for details."
            )
            
        if success_count == 0 and failure_count == 0:
            logger.warning("Workflow ran but processed 0 users. Is this expected?")

        return result

    except Exception as e:
        logger.exception("Unhandled exception during workflow execution")
        raise AirflowException(f"Critical Workflow Failure: {e}")


# ==============================================================================
# DAG DEFINITION
# ==============================================================================
default_args = {
    'owner': 'meal_mind',
    'depends_on_past': False,
    'email_on_failure': False, # Set to True and configure SMTP if needed
    'email_on_retry': False,
    'retries': 0, # Disable retries for debugging to see immediate failures
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'meal_mind_weekly_generator_debug', # Renamed for clarity
    default_args=default_args,
    description='Generate weekly meal plans with enhanced debugging',
    schedule_interval='0 6 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['meal_mind', 'debug', 'production'],
) as dag:

    # Task 1: Check Environment
    check_env_task = PythonOperator(
        task_id='check_environment_setup',
        python_callable=check_environment_setup,
        provide_context=True
    )

    # Task 2: Generate Plans
    generate_task = PythonOperator(
        task_id='generate_meal_plans',
        python_callable=run_meal_plan_generation,
        provide_context=True
    )

    # Define Dependency
    check_env_task >> generate_task
