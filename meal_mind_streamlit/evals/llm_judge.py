import json
import os
import sys
from typing import List, Dict, Any

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.custom_chat_snowflake import ChatSnowflake
from langchain_core.messages import SystemMessage, HumanMessage

class LLMJudge:
    def __init__(self):
        # Use a strong model for judging
        self.llm = ChatSnowflake(
            model="claude-4-sonnet", # or 'mistral-large'
            temperature=0.0
        )

    def score_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        print("Starting LLM Judge Scoring...")
        scored_results = []
        
        for res in results:
            if res.get('error'):
                res['score_accuracy'] = 0
                res['score_quality'] = 0
                res['judge_reasoning'] = "Execution Error"
                scored_results.append(res)
                continue
                
            print(f"Judging Case ID: {res['id']}")
            
            prompt = f"""
            You are an expert AI Judge. Evaluate the following agent interaction.
            
            User Input: "{res['input']}"
            Expected Intent: "{res['expected_intent']}"
            Actual Intent: "{res['actual_intent']}"
            Actual Response: "{res['actual_response']}"
            
            Task:
            1. Intent Accuracy: Did the agent choose the correct action? (1 = Yes, 0 = No)
            2. Response Quality: Is the response helpful, accurate, and relevant? (1-5 scale)
            
            Output JSON ONLY:
            {{
                "accuracy": <0 or 1>,
                "quality": <1-5>,
                "reasoning": "<brief explanation>"
            }}
            """
            
            try:
                response = self.llm.invoke([HumanMessage(content=prompt)])
                content = response.content.strip()
                # Clean up markdown code blocks if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                    
                score_data = json.loads(content)
                
                res['score_accuracy'] = score_data.get('accuracy', 0)
                res['score_quality'] = score_data.get('quality', 0)
                res['judge_reasoning'] = score_data.get('reasoning', "No reasoning provided")
                
            except Exception as e:
                print(f"Error judging case {res['id']}: {e}")
                res['score_accuracy'] = 0
                res['score_quality'] = 0
                res['judge_reasoning'] = f"Judge Error: {str(e)}"
            
            scored_results.append(res)
            
        return scored_results

if __name__ == "__main__":
    # Local Test (Mock input)
    mock_results = [{
        "id": "test_001",
        "input": "Calories in apple",
        "expected_intent": "calorie_estimation",
        "actual_intent": "calorie_estimation",
        "actual_response": "An apple has about 95 calories."
    }]
    judge = LLMJudge()
    scored = judge.score_results(mock_results)
    print(json.dumps(scored, indent=2))
