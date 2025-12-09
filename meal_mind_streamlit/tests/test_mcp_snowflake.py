import requests
import json
import os

class MealMindMCPClient:
    def __init__(self, account, token, db, schema):
        self.base_url = f"https://{account}.snowflakecomputing.com"
        self.endpoint = f"/api/v2/databases/{db}/schemas/{schema}/mcp-servers/MEAL_MIND_MCP_SERVER"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self.request_id = 0
    
    def _call(self, method, params=None):
        self.request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        response = requests.post(
            f"{self.base_url}{self.endpoint}",
            headers=self.headers,
            json=payload
        )
        return response.json()
    
    def initialize(self):
        return self._call("initialize", {"protocolVersion": "2025-06-18"})
    
    def list_tools(self):
        return self._call("tools/list")
    
    def search_foods(self, query, columns=None, limit=10, filter_obj=None):
        args = {"query": query, "limit": limit}
        if columns:
            args["columns"] = columns
        if filter_obj:
            args["filter"] = filter_obj
        return self._call("tools/call", {
            "name": "meal-mind-search",
            "arguments": args
        })

# Usage
import os
import snowflake.connector
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_snowflake_connection():
    try:
        conn = snowflake.connector.connect(
            user=os.getenv('SNOWFLAKE_USER'),
            account=os.getenv('SNOWFLAKE_ACCOUNT'),
            password=os.getenv('SNOWFLAKE_PASSWORD'),
            warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
            database=os.getenv('SNOWFLAKE_DATABASE'),
            schema=os.getenv('SNOWFLAKE_SCHEMA'),
            role=os.getenv('SNOWFLAKE_ROLE')
        )
        return conn
    except Exception as e:
        print(f"Failed to connect to Snowflake: {e}")
        return None

def main():
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    db = os.getenv("SNOWFLAKE_DATABASE")
    schema = os.getenv("SNOWFLAKE_SCHEMA")
    
    print(f"DEBUG: DB={db}, SCHEMA={schema}")
    
    if not account:
        print("Error: SNOWFLAKE_ACCOUNT not found in environment variables.")
        return

    print("Connecting to Snowflake to get session token...")
    conn = get_snowflake_connection()
    if not conn:
        return

    # Extract session token
    # The session token is available in conn.rest.token
    token = conn.rest.token
    print(f"Got session token (len={len(token)})")
    
    # Close connection (we just needed the token, but keep it open if session depends on it? 
    # Usually session stays alive for a bit, but closing conn might kill it. 
    # Let's keep it open or just rely on the token validity.)
    # conn.close() 

    print("Initializing MCP Client...")
    # Note: The user's class uses "Bearer {token}". 
    # For session tokens, it should often be "Snowflake Token=\"{token}\"".
    # We will monkey-patch or modify the class instance to fix the header if needed.
    
    client = MealMindMCPClient(account, token, db, schema)
    
    # Update header for session token usage
    client.headers["Authorization"] = f"Snowflake Token=\"{token}\""
    
    try:
        print("Calling initialize...")
        init_res = client.initialize()
        print("Initialize result:", json.dumps(init_res, indent=2))
        
        print("\nSearching foods...")
        results = client.search_foods("low carb vegetables", limit=5)
        print("Search results:", json.dumps(results, indent=2))
        
    except Exception as e:
        print(f"Error during MCP call: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
