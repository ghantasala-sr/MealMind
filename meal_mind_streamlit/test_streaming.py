
import streamlit as st
from langchain_community.chat_models import ChatSnowflakeCortex
from langchain.schema import HumanMessage
from utils.db import get_snowpark_session
import os
from dotenv import load_dotenv

load_dotenv()

def test_streaming():
    try:
        session = get_snowpark_session()
        chat = ChatSnowflakeCortex(
            session=session,
            model="llama3.1-70b",
            cortex_search_service="MEAL_MIND"
        )
        
        messages = [HumanMessage(content="Count to 5.")]
        print("Starting stream...")
        for chunk in chat.stream(messages):
            print(f"Chunk: {chunk.content}")
        print("Stream finished.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_streaming()
