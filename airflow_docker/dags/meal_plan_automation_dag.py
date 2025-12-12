from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os

# Add mounted app directory to path
APP_PATH = '/opt/airflow/meal_mind_streamlit'
if APP_PATH not in sys.path:
    sys.path.append(APP_PATH)

def run_meal_plan_automation(**context):
    """
    Execute the Meal Plan Generation Workflow.
    This function lazy-imports the workflow to ensure paths are set up correctly
    within the Airflow worker environment.
    """
    print("Starting Meal Plan Automation Task...")
    
    try:
        from utils.meal_plan_workflow import MealPlanWorkflow
        
        # Initialize workflow
        workflow = MealPlanWorkflow()
        
        # Run workflow for today's date
        target_date = datetime.now().date().isoformat()
        print(f"Running workflow for date: {target_date}")
        
        final_state = workflow.run(target_date=target_date)
        
        # Log results
        success_count = final_state.get('success_count', 0)
        failure_count = final_state.get('failure_count', 0)
        errors = final_state.get('errors', [])
        
        print(f"Workflow Complete. Success: {success_count}, Failures: {failure_count}")
        
        if errors:
            print("Errors encountered:")
            for err in errors:
                print(f" - {err}")
                
        if failure_count > 0:
            raise Exception(f"Workflow completed with {failure_count} failures.")
            
    except ImportError as e:
        print(f"Error importing workflow: {e}")
        print(f"Current Path: {sys.path}")
        raise e
    except Exception as e:
        print(f"Error executing workflow: {e}")
        raise e

default_args = {
    'owner': 'meal_mind',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'meal_mind_automation_dag',
    default_args=default_args,
    description='Automated Weekly Meal Plan Generator',
    schedule_interval='@daily', # Run once a day
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['automation', 'meal_mind'],
) as dag:

    # Task to verify environment (Optional but helpful for debugging)
    def check_env_task():
        import sys
        print(f"Python version: {sys.version}")
        print(f"System Path: {sys.path}")
        try:
            import utils.meal_plan_workflow
            print("✅ Successfully found utils.meal_plan_workflow")
        except ImportError as e:
            print(f"❌ Could not import utils.meal_plan_workflow: {e}")
            
    check_env = PythonOperator(
        task_id='check_environment',
        python_callable=check_env_task
    )

    run_automation = PythonOperator(
        task_id='run_meal_plan_generation',
        python_callable=run_meal_plan_automation,
        provide_context=True
    )
    
    check_env >> run_automation
