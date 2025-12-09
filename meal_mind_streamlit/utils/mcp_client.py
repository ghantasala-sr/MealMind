import requests
import json
from typing import Optional, Dict, Any

class MealMindMCPClient:
    """
    Client for interacting with the Meal Mind MCP Server running on Snowflake.
    """
    def __init__(self, account: str, token: str, db: str, schema: str):
        """
        Initialize the MCP Client.
        
        Args:
            account: Snowflake account identifier
            token: OAuth or Session token
            db: Database name where the MCP server is located
            schema: Schema name where the MCP server is located
        """
        self.base_url = f"https://{account}.snowflakecomputing.com"
        self.endpoint = f"/api/v2/databases/{db}/schemas/{schema}/mcp-servers/MEAL_MIND_MCP_SERVER"
        self.headers = {
            "Authorization": f"Snowflake Token=\"{token}\"",
            "Content-Type": "application/json"
        }
        self.request_id = 0
    
    def _call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a JSON-RPC call to the MCP server."""
        self.request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        
        try:
            response = requests.post(
                f"{self.base_url}{self.endpoint}",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"MCP Request Failed: {e}")
            return {"error": {"code": -1, "message": str(e)}}
    
    def initialize(self) -> Dict[str, Any]:
        """Initialize the MCP connection."""
        return self._call("initialize", {"protocolVersion": "2025-06-18"})
    
    def list_tools(self) -> Dict[str, Any]:
        """List available tools on the MCP server."""
        return self._call("tools/list")
    
    def search_foods(self, query: str, columns: Optional[list] = None, limit: int = 10, filter_obj: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Call the 'meal-mind-search' tool.
        
        Args:
            query: Search query string
            columns: Optional list of columns to return
            limit: Number of results to return
            filter_obj: Optional filter object
        """
        args = {"query": query, "limit": limit}
        if columns:
            args["columns"] = columns
        if filter_obj:
            args["filter"] = filter_obj
            
        return self._call("tools/call", {
            "name": "meal-mind-search",
            "arguments": args
        })
