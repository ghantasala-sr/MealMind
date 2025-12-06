import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
from langchain_community.chat_models import ChatSnowflakeCortex
from utils.db import get_snowpark_session
from langchain.schema import HumanMessage
import time

# Mock Streamlit secrets if needed (or rely on env vars/local config)
# Assuming get_snowpark_session works in this environment

def test_streaming():
    print("Initializing Session...")
    session = get_snowpark_session()
    
    print("\n--- Test 1: With cortex_search_service ---")
    try:
        chat = ChatSnowflakeCortex(
            session=session,
            model="llama3.1-70b",
            cortex_search_service="MEAL_MIND",
            streaming=True
        )
        print("Streaming response...")
        start = time.time()
        chunk_count = 0
        for chunk in chat.stream([HumanMessage(content="Count from 1 to 10.")]):
            print(f"Chunk: {chunk.content}", end="|", flush=True)
            chunk_count += 1
        print(f"\nTotal chunks: {chunk_count}")
        print(f"Time: {time.time() - start:.2f}s")
    except Exception as e:
        print(f"Error: {e}")

    print("\n--- Test 2: WITHOUT cortex_search_service ---")
    try:
        chat_no_rag = ChatSnowflakeCortex(
            session=session,
            model="llama3.1-70b"
            # No search service
        )
        print("Streaming response...")
        start = time.time()
        chunk_count = 0
        for chunk in chat_no_rag.stream([HumanMessage(content="Count from 1 to 10.")]):
            print(f"Chunk: {chunk.content}", end="|", flush=True)
            chunk_count += 1
        print(f"\nTotal chunks: {chunk_count}")
        print(f"Time: {time.time() - start:.2f}s")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_streaming()
