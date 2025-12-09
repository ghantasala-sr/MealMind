from snowflake.snowpark import Session
import os
from dotenv import load_dotenv

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

session = get_snowpark_session()
if session:
    print("Session created.")
    try:
        # Try to access connection and token
        if hasattr(session, 'connection'):
            print("session.connection exists")
            conn = session.connection
            if hasattr(conn, 'rest'):
                print("session.connection.rest exists")
                if hasattr(conn.rest, 'token'):
                    print(f"Token found: {len(conn.rest.token)} chars")
                else:
                    print("session.connection.rest.token MISSING")
            else:
                print("session.connection.rest MISSING")
        else:
            print("session.connection MISSING")
            # Inspect dir
            # print(dir(session))
    except Exception as e:
        print(f"Error inspecting session: {e}")
    finally:
        session.close()
