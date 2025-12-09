from snowflake.snowpark import Session
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path to allow importing utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.model_arena import ModelArena

load_dotenv()

def get_snowpark_session():
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
        print(f"Failed to create Snowpark Session: {e}")
        return None

def main():
    print("Creating Snowpark Session...")
    session = get_snowpark_session()
    if not session:
        return

    try:
        print("Initializing ModelArena...")
        arena = ModelArena(session)
        
        query = "low carb vegetables"
        print(f"Testing _retrieve_cortex_search with query: '{query}'")
        
        context = arena._retrieve_cortex_search(query)
        
        print("\n" + "="*50)
        print("RETRIEVED CONTEXT:")
        print("="*50)
        print(context)
        print("="*50)
        
        if context:
            print("\nSUCCESS: Context retrieved via MCP!")
        else:
            print("\nFAILURE: No context retrieved.")
            
    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    main()
