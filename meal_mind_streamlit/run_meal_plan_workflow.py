import sys
import os
import logging
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("manual_workflow_runner")

# Add project root to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from utils.meal_plan_workflow import MealPlanWorkflow
except ImportError as e:
    logger.error(f"Failed to import MealPlanWorkflow: {e}")
    sys.exit(1)

def main():
    logger.info("Starting manual meal plan workflow execution...")
    
    try:
        # Initialize Workflow
        workflow = MealPlanWorkflow()
        
        # Run Workflow
        # You can optionally pass a target_date here, e.g., workflow.run(target_date="2023-10-27")
        # Default is today's date
        result = workflow.run()
        
        # Log Results
        success_count = result.get('success_count', 0)
        failure_count = result.get('failure_count', 0)
        errors = result.get('errors', [])
        
        logger.info("--- WORKFLOW FINISHED ---")
        logger.info(f"Success Count: {success_count}")
        logger.info(f"Failure Count: {failure_count}")
        
        if errors:
            logger.error("Encountered errors:")
            for i, err in enumerate(errors, 1):
                logger.error(f"Error {i}: {json.dumps(err, default=str, indent=2)}")
        
    except Exception as e:
        logger.exception(f"Critical failure during execution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
