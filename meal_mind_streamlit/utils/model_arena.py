import time
import json
import streamlit as st
import warnings
from typing import Dict, List, Any
from utils.custom_chat_snowflake import CustomChatSnowflake
from langchain.schema import SystemMessage, HumanMessage

# Suppress the specific warning from ChatSnowflakeCortex about default parameters
warnings.filterwarnings("ignore", message=".*is not default parameter.*")

class ModelArena:
    """
    Arena to compare multiple LLMs on performance and quality metrics.
    """
    
    MODELS = {
        "Meta (Llama 3.1 70B)": "llama3.1-70b",
        "Anthropic (Claude 3.5 Sonnet)": "claude-3-5-sonnet",
        "Mistral (Large 2)": "mistral-large2",
        "Snowflake (Arctic)": "snowflake-arctic",
        "OpenAI (GPT 4.1)": "openai-gpt-4.1"
    }
    
    JUDGE_MODEL = "claude-sonnet-4-5"
    
    def __init__(self, session):
        self.session = session

    def _retrieve_cortex_search(self, query: str) -> str:
        """Fetch context from Cortex Search Service using MCP"""
        try:
            import os
            import json
            from utils.mcp_client import MealMindMCPClient
            
            # Get credentials and context
            account = os.getenv("SNOWFLAKE_ACCOUNT")
            db = os.getenv("SNOWFLAKE_DATABASE")
            schema = os.getenv("SNOWFLAKE_SCHEMA")
            
            # Get session token from Snowpark session
            # session.connection returns the snowflake-connector-python connection object
            token = self.session.connection.rest.token
            
            if not all([account, token, db, schema]):
                print("DEBUG: Missing credentials for MCP client")
                return ""
                
            # Initialize MCP Client
            client = MealMindMCPClient(account, token, db, schema)
            
            # Perform search
            # We can limit to 5 results as before
            print(f"DEBUG: MCP Search Input Query: '{query}'")
            
            columns = [
                "FOOD_ID", "FOOD_RECORD_ID", "FOOD_NAME", "PRIMARY_INGREDIENT", 
                "SECONDARY_INGREDIENT", "ENERGY_KCAL", "PROTEIN_G", "CARBOHYDRATE_G", 
                "FIBER_TOTAL_G", "TOTAL_FAT_G", "SODIUM_MG", "PROTEIN_PCT", 
                "IS_APPROPRIATE_PORTION"
            ]
            
            response = client.search_foods(query, columns=columns, limit=5)
            print(f"DEBUG: MCP Search Output Response: {json.dumps(response, indent=2)}")
            
            if "error" in response:
                print(f"DEBUG: MCP Search Error: {response['error']}")
                return ""
                
            result_content = response.get("result", {}).get("content", [])
            
            context_parts = []
            for item in result_content:
                if item.get("type") == "text":
                    text = item.get("text")
                    # With specific columns, the text might be a JSON string representation of the row
                    # or a list of such strings.
                    try:
                        import json
                        data = json.loads(text)
                        
                        # Helper to format a single record
                        def format_record(record):
                            # If record is a string (which shouldn't happen if we parsed it), return it
                            if isinstance(record, str):
                                return record
                            
                            # Format nicely
                            parts = []
                            if "FOOD_NAME" in record:
                                parts.append(f"Food: {record['FOOD_NAME']}")
                            
                            # Add nutritional info
                            nutrients = []
                            if "ENERGY_KCAL" in record: nutrients.append(f"Calories: {record['ENERGY_KCAL']} kcal")
                            if "PROTEIN_G" in record: nutrients.append(f"Protein: {record['PROTEIN_G']}g")
                            if "CARBOHYDRATE_G" in record: nutrients.append(f"Carbs: {record['CARBOHYDRATE_G']}g")
                            if "TOTAL_FAT_G" in record: nutrients.append(f"Fat: {record['TOTAL_FAT_G']}g")
                            if "FIBER_TOTAL_G" in record: nutrients.append(f"Fiber: {record['FIBER_TOTAL_G']}g")
                            
                            if nutrients:
                                parts.append(" | ".join(nutrients))
                                
                            # Add other details if relevant
                            if "PRIMARY_INGREDIENT" in record and record["PRIMARY_INGREDIENT"]:
                                parts.append(f"Main Ingredient: {record['PRIMARY_INGREDIENT']}")
                                
                            return "\n".join(parts)

                        if isinstance(data, list):
                            for chunk in data:
                                context_parts.append(format_record(chunk))
                        elif isinstance(data, dict):
                             context_parts.append(format_record(data))
                        else:
                            context_parts.append(str(data))
                    except:
                        context_parts.append(text)
                        
            return "\n\n".join(context_parts)
            
        except Exception as e:
            print(f"DEBUG: Cortex Search Failed: {e}")
            return ""

    def _evaluate_groundedness(self, response_text: str, context: str) -> Dict[str, Any]:
        """
        Evaluate the groundedness of the response based on the context using the Judge LLM.
        """
        try:
            judge = CustomChatSnowflake(
                session=self.session,
                model=self.JUDGE_MODEL
            )
            
            prompt = f"""
            You are an impartial judge evaluating the quality of an answer given a context.
            
            CONTEXT:
            {context}
            
            ANSWER:
            {response_text}
            
            Task:
            1. Rate the answer on a scale of 1 to 10 based on how well it is supported by the context.
            2. Provide a brief explanation.
            
            Format your response as a JSON object with keys: "score" (integer) and "explanation" (string).
            """
            
            eval_response = judge.invoke([HumanMessage(content=prompt)])
            content = eval_response.content
            
            # Parse JSON from response
            try:
                # Clean up potential markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                    
                result = json.loads(content.strip())
                return result
            except:
                # Fallback parsing
                import re
                score_match = re.search(r'"score":\s*(\d+)', content)
                score = int(score_match.group(1)) if score_match else 0
                return {"score": score, "explanation": content}
                
        except Exception as e:
            print(f"DEBUG: Evaluation Failed: {e}")
            return {"score": 0, "explanation": f"Evaluation failed: {e}"}

    def run_comparison(self, prompt: str, model_context: str = None, ground_truth: str = None) -> List[Dict[str, Any]]:
        """
        Run the prompt against all models and evaluate.
        
        Args:
            prompt: The user query.
            model_context: Optional context to provide to the model (RAG). 
                           If None, will attempt to retrieve from Cortex Search.
            ground_truth: Optional context to use for Evaluation (Judge).
                          If None, will use model_context.
        """
        results = []
        
        # 1. Determine Model Context (RAG)
        if model_context:
            context_for_model = model_context
            retrieved_from_search = False
        else:
            with st.spinner("Retrieving context from Cortex Search..."):
                context_for_model = self._retrieve_cortex_search(prompt)
                retrieved_from_search = True
        
        # 2. Determine Ground Truth (Judge)
        context_for_judge = ground_truth if ground_truth else context_for_model
            
        total_models = len(self.MODELS)
        
        for i, (name, model_id) in enumerate(self.MODELS.items()):
            result = {
                "model_name": name,
                "model_id": model_id,
                "latency": 0,
                "response": "",
                "groundedness_score": 0,
                "explanation": "",
                "citations": [],
                "citation_count": 0
            }
            
            try:
                # Init Model
                llm = CustomChatSnowflake(
                    session=self.session,
                    model=model_id
                )
                
                # Construct Prompt with Context
                full_prompt = f"""
                Context information is below.
                ---------------------
                {context_for_model}
                ---------------------
                Given the context information and not prior knowledge, answer the query.
                Query: {prompt}
                """
                
                start_time = time.time()
                response = llm.invoke([HumanMessage(content=full_prompt)])
                end_time = time.time()
                
                result["latency"] = round(end_time - start_time, 2)
                result["response"] = response.content
                
                # Token Usage
                usage = response.usage_metadata or {}
                result["input_tokens"] = usage.get("input_tokens", 0)
                result["output_tokens"] = usage.get("output_tokens", 0)
                
                # Debug Metadata & Citations
                meta = response.response_metadata or {}
                # Since we are doing manual RAG, citations might not be populated by Cortex automatically
                # unless we parse them or if SEARCH_PREVIEW returns them and we pass them somehow.
                # For now, we track if we used search.
                if retrieved_from_search and context_for_model:
                     result["citation_count"] = 1 # Indicator that search was used
                
                print(f"DEBUG: {model_id} Metadata: {meta}")
                
                # Evaluate
                eval_result = self._evaluate_groundedness(response.content, context_for_judge)
                result["groundedness_score"] = eval_result.get("score", 0)
                result["explanation"] = eval_result.get("explanation", "")
                
            except Exception as e:
                result["response"] = f"Error: {str(e)}"
                print(f"DEBUG: Model Run Failed: {e}")
            
            results.append(result)
            
        return results, context_for_judge

    def run_batch_evaluation(self, df) -> List[Dict[str, Any]]:
        """Run evaluation on a batch of food items from a DataFrame"""
        all_results = []
        
        total_items = len(df)
        main_progress = st.progress(0, text="Batch Evaluation Progress")
        log_container = st.expander("📜 Live Execution Logs", expanded=True)
        
        for index, row in df.iterrows():
            food_name = row['FOOD_NAME']
            
            # Construct Prompt
            prompt = f"How much protein, calories, carbs, and fat is in 100g of {food_name}? Please provide the exact values."
            
            # Construct Context from CSV Data
            context = (
                f"Food Item: {food_name}\n"
                f"Serving Size: {row.get('SERVING_SIZE', '100g')}\n"
                f"Calories: {row.get('ENERGY_KCAL', 'N/A')} kcal\n"
                f"Protein: {row.get('PROTEIN_G', 'N/A')} g\n"
                f"Carbohydrates: {row.get('CARBOHYDRATE_G', 'N/A')} g\n"
                f"Total Fat: {row.get('TOTAL_FAT_G', 'N/A')} g\n"
                f"Fiber: {row.get('FIBER_TOTAL_G', 'N/A')} g\n"
                f"Sugars: {row.get('SUGARS_TOTAL_G', 'N/A')} g\n"
                f"Sodium: {row.get('SODIUM_MG', 'N/A')} mg\n"
            )
            
            with log_container:
                st.markdown(f"**[{index+1}/{total_items}] Evaluating: `{food_name}`**")
                st.text(f"Context: {context.replace(chr(10), ', ')}")
            
            # Run Comparison for this item
            # model_context=None -> Triggers Cortex Search retrieval
            # ground_truth=context -> Uses CSV data for Judge evaluation
            item_results, _ = self.run_comparison(prompt, model_context=None, ground_truth=context)
            
            # Add metadata to results
            for res in item_results:
                res['food_name'] = food_name
                res['prompt'] = prompt
                res['ground_truth_context'] = context
                all_results.append(res)
                
                with log_container:
                    st.caption(f"  - {res['model_name']}: Score {res['groundedness_score']}/10 ({res['latency']}s)")
                    print(f"DEBUG: {food_name} | {res['model_name']} | Score: {res['groundedness_score']} | Latency: {res['latency']}")
                
            main_progress.progress((index + 1) / total_items, text=f"Evaluated {index + 1}/{total_items}: {food_name}")
            
        return all_results
