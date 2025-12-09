try:
    from langchain_snowflake.chat_models import ChatSnowflake
    print("Successfully imported ChatSnowflake from langchain_snowflake")
    
    llm = ChatSnowflake(
        model="llama3.1-70b",
        account="test",
        user="test",
        password="test", # Dummy values just to test init
        database="test",
        schema="test",
        warehouse="test"
    )
    print("Successfully instantiated ChatSnowflake")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
