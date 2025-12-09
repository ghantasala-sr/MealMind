import re
import json

def extract_tool_calls(content):
    print(f"Content: {content}")
    tool_calls = []
    
    # Try finding all JSON-like objects
    # Non-greedy match for {...}
    # This assumes no nested braces, which is true for our simple tool schema
    candidates = re.finditer(r'\{[^{}]*\}', content)
    
    for match in candidates:
        json_str = match.group(0)
        try:
            data = json.loads(json_str)
            if data.get("tool") == "search_foods":
                tool_calls.append(data)
        except json.JSONDecodeError:
            pass
            
    return tool_calls

def test_parsing():
    # Case 1: Single tool call
    text1 = 'I will search for it. {"tool": "search_foods", "query": "apple"}'
    print(f"\nTest 1 (Single): {extract_tool_calls(text1)}")
    
    # Case 2: Multiple tool calls mixed with text (The failure case)
    text2 = """
    Basmati Rice: {"tool": "search_foods", "query": "basmati rice"}
    Vegetables: {"tool": "search_foods", "query": "carrots"} and {"tool": "search_foods", "query": "peas"}
    """
    print(f"\nTest 2 (Multiple): {extract_tool_calls(text2)}")
    
    # Case 3: Invalid JSON
    text3 = 'Some text {"tool": "search_foods", "query": "bad json" without closing brace'
    print(f"\nTest 3 (Invalid): {extract_tool_calls(text3)}")

if __name__ == "__main__":
    test_parsing()
