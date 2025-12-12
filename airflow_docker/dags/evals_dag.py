from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os
import json
import pandas as pd

# Add mounted app directory to path
APP_PATH = '/opt/airflow/meal_mind_streamlit'
sys.path.append(APP_PATH)

# Import Eval Logic (Lazy import inside task to avoid top-level failures if mount is missing)
def run_evals_task(**context):
    from evals.eval_runner import EvalRunner
    from evals.llm_judge import LLMJudge
    from snowflake.connector.pandas_tools import write_pandas
    import snowflake.connector
    
    # 1. Run Evals
    print("Step 1: Running Evals...")
    dataset_path = os.path.join(APP_PATH, 'evals/eval_dataset.json')
    runner = EvalRunner(dataset_path)
    raw_results = runner.run_evals()
    
    # 2. Score Results
    print("Step 2: Scoring Results...")
    judge = LLMJudge()
    scored_results = judge.score_results(raw_results)
    
    # 3. Log to Snowflake
    print("Step 3: Logging to Snowflake...")
    
    # Convert to DataFrame
    df = pd.DataFrame(scored_results)
    df['run_id'] = context['run_id']
    df['execution_date'] = context['ts']
    df['model_version'] = 'v1.0' # Placeholder
    
    # Connect to Snowflake (Env vars should be passed to Docker)
    conn = snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
        database=os.getenv('SNOWFLAKE_DATABASE'),
        schema=os.getenv('SNOWFLAKE_SCHEMA'),
        role=os.getenv('SNOWFLAKE_ROLE')
    )
    
    try:
        # Create table if not exists
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS EVALUATION_LOGS (
            run_id STRING,
            execution_date TIMESTAMP_NTZ,
            model_version STRING,
            id STRING,
            input STRING,
            expected_intent STRING,
            actual_intent STRING,
            actual_response STRING,
            score_accuracy FLOAT,
            score_quality FLOAT,
            judge_reasoning STRING,
            error STRING
        )
        """
        conn.cursor().execute(create_table_sql)
        
        # Write Data
        # Ensure column names match upper case for Snowflake
        df.columns = [c.upper() for c in df.columns]
        success, nchunks, nrows, _ = write_pandas(conn, df, 'EVALUATION_LOGS', auto_create_table=False)
        print(f"Successfully wrote {nrows} rows to Snowflake.")
        
    finally:
        conn.close()

default_args = {
    'owner': 'meal_mind',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'meal_mind_evals_dag',
    default_args=default_args,
    description='Daily automated evaluations for Meal Mind agents',
    schedule_interval='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['evals', 'meal_mind'],
) as dag:

    # Task to verify environment
    def check_requirements_task():
        import sys
        print(f"Python version: {sys.version}")
        
        modules = [
            'streamlit', 'snowflake.snowpark', 'langchain', 
            'langgraph', 'zstandard', 'pydantic'
        ]
        
        missing = []
        for mod in modules:
            try:
                __import__(mod)
                print(f"✅ Found {mod}")
            except ImportError as e:
                print(f"❌ Missing {mod}: {e}")
                missing.append(mod)
                
        if missing:
            raise ImportError(f"Missing required modules: {missing}")
            
    check_requirements = PythonOperator(
        task_id='check_requirements',
        python_callable=check_requirements_task
    )

    run_evals = PythonOperator(
        task_id='run_and_score_evals',
        python_callable=run_evals_task,
        provide_context=True
    )
    
    check_requirements >> run_evals
