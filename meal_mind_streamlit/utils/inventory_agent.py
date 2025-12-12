import json
import re
from typing import List, Dict, Optional
from langchain_community.chat_models import ChatSnowflakeCortex
from langchain.schema import SystemMessage, HumanMessage

class InventoryAgent:
    def __init__(self, session):
        self.session = session
        self.model = ChatSnowflakeCortex(
            session=self.session,
            model="openai-gpt-4.1", # Using a strong model for accurate parsing
            temperature=0.0
        )
        
        self.VALID_CATEGORIES = [
            "Produce", "Dairy & Eggs", "Meat & Seafood", "Pantry", 
            "Frozen", "Beverages", "Snacks", "Spices & Seasonings", "Other"
        ]

    def parse_inventory(self, text: str) -> List[Dict]:
        """
        Parses natural language text into a list of structured inventory items.
        """
        if not text or not text.strip():
            return []

        system_prompt = f"""You are an Inventory Assistant.
Your goal is to parse a user's grocery list or inventory description into structured JSON.

VALID CATEGORIES: {', '.join(self.VALID_CATEGORIES)}

RULES:
1. **Extract Fields:** 'item_name', 'quantity' (number), 'unit', 'category'.
2. **Quantity Logic:**
   - "2 lbs" -> 2.0
   - "half a gallon" -> 0.5
   - "1/2 cup" -> 0.5
   - "a dozen" -> 12.0
   - "milk" (no qty) -> 1.0 (Default)
3. **Unit Logic:**
   - "3 apples" -> unit: "pieces" (Use 'pieces' for countable items)
   - "bag of rice" -> unit: "bag"
   - "box of cereal" -> unit: "box"
   - "milk" -> unit: "gallon" (Infer standard container for liquids)
   - "bread" -> unit: "loaf"
   - "salt", "sugar", "pepper" -> unit: "pack" or "jar" (Default for pantry staples, NOT 'pinch')
   - Normalize: "pound"->"lbs", "tablespoon"->"tbsp", "teaspoon"->"tsp".
4. **Category Logic:**
   - Map to the most specific VALID CATEGORY.
   - "Chicken" -> "Meat & Seafood"
   - "Cheese" -> "Dairy & Eggs"
   - "Rice" -> "Pantry"
5. **Noise Handling:** Ignore filler words like "I have", "some", "maybe", "leftover".
6. **Output:** JSON list of objects ONLY.

FEW-SHOT EXAMPLES:

Input: "I have 2 lbs of chicken breast, a carton of eggs, milk, spinach, and olive oil."
Output:
[
    {{"item_name": "Chicken Breast", "quantity": 2.0, "unit": "lbs", "category": "Meat & Seafood"}},
    {{"item_name": "Eggs", "quantity": 1.0, "unit": "carton", "category": "Dairy & Eggs"}},
    {{"item_name": "Milk", "quantity": 1.0, "unit": "gallon", "category": "Dairy & Eggs"}},
    {{"item_name": "Spinach", "quantity": 1.0, "unit": "bag", "category": "Produce"}},
    {{"item_name": "Olive Oil", "quantity": 1.0, "unit": "bottle", "category": "Pantry"}}
]

Input: "half a gallon of oj, 3 bananas, a bag of rice, and some leftover pizza"
Output:
[
    {{"item_name": "Orange Juice", "quantity": 0.5, "unit": "gallon", "category": "Beverages"}},
    {{"item_name": "Bananas", "quantity": 3.0, "unit": "pieces", "category": "Produce"}},
    {{"item_name": "Rice", "quantity": 1.0, "unit": "bag", "category": "Pantry"}},
    {{"item_name": "Pizza", "quantity": 1.0, "unit": "slice", "category": "Other"}}
]

Input: "1.5 kg tomatoes, 1/4 cup sugar, salt"
Output:
[
    {{"item_name": "Tomatoes", "quantity": 1.5, "unit": "kg", "category": "Produce"}},
    {{"item_name": "Sugar", "quantity": 0.25, "unit": "cup", "category": "Pantry"}},
    {{"item_name": "Salt", "quantity": 1.0, "unit": "pack", "category": "Spices & Seasonings"}}
]
"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=text)
            ]
            
            response = self.model.invoke(messages)
            content = response.content.strip()
            
            # Clean up markdown code blocks if present
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            parsed_data = json.loads(content.strip())
            
            if isinstance(parsed_data, dict):
                parsed_data = [parsed_data]
                
            # Validate and normalize
            normalized = []
            for item in parsed_data:
                # Ensure category is valid
                cat = item.get("category", "Other")
                if cat not in self.VALID_CATEGORIES:
                    cat = "Other"
                
                normalized.append({
                    "Item": item.get("item_name", "Unknown Item"),
                    "Quantity": float(item.get("quantity", 1)),
                    "Unit": item.get("unit", "unit"),
                    "Category": cat
                })
                
            return normalized

        except Exception as e:
            print(f"Error parsing inventory: {e}")
            # Fallback: return the whole text as one item to let user fix it
            return [{
                "Item": text[:50],
                "Quantity": 1.0,
                "Unit": "unit",
                "Category": "Other"
            }]
