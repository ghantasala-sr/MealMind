import streamlit as st
import json
import os
from langchain_community.chat_models import ChatSnowflakeCortex
from langchain.schema import SystemMessage, HumanMessage

class RecipeAgent:
    """Agent for generating detailed recipes"""

    def __init__(self, session):
        self.session = session
        try:
            self.llm = ChatSnowflakeCortex(
                session=self.session,
                model="openai-gpt-4.1",
                temperature=0.7
            )
        except Exception as e:
            st.warning(f"Recipe Agent LLM init failed: {e}")
            self.llm = None

    def generate_recipe(self, query: str, user_preferences: dict = None, inventory_summary: str = None) -> str:
        """Generate a detailed recipe based on the query and inventory"""
        if not self.llm:
            return "Recipe Agent is not available."

        prefs_text = ""
        if user_preferences:
            if user_preferences.get('dietary_restrictions'):
                prefs_text += f"- Dietary Restrictions: {user_preferences['dietary_restrictions']}\n"
            if user_preferences.get('food_allergies'):
                prefs_text += f"- Allergies: {user_preferences['food_allergies']}\n"
            if user_preferences.get('preferred_cuisines'):
                prefs_text += f"- Preferred Cuisines: {user_preferences['preferred_cuisines']}\n"

        inventory_text = ""
        if inventory_summary:
            inventory_text = f"\nCURRENT INVENTORY:\n{inventory_summary}\n"

        system_prompt = f"""You are an expert Chef and Nutritionist.
Your task is to provide a detailed, delicious, and easy-to-follow recipe based on the user's request.

USER PREFERENCES:
{prefs_text}
{inventory_text}
INSTRUCTIONS:
1.  **Prioritize Inventory**: If the user asks "what can I cook" or for a general recipe, TRY to use ingredients from the CURRENT INVENTORY.
2.  **Recipe Name**: Clear and appetizing title.
3.  **Description**: Brief description of the dish.
4.  **Ingredients**: List of ingredients with precise quantities.
5.  **Instructions**: Step-by-step cooking instructions.
6.  **Tips**: Chef's tips for better flavor or easier cooking.
7.  **Nutrition Estimate**: Approximate calories and macros per serving.

FORMAT:
Use Markdown formatting.
- Use **Bold** for headers.
- Use lists for ingredients and steps.
- Make it look professional and clean.

If the user asks for a specific variation (e.g., "healthy", "spicy"), adapt the recipe accordingly.
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query)
        ]

        try:
            response = self.llm.invoke(messages)
            return response.content.strip()
        except Exception as e:
            return f"Error generating recipe: {e}"
