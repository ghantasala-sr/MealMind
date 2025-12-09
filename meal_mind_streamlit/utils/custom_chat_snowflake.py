from typing import Any, Dict, Optional
from langchain_snowflake.chat_models import ChatSnowflake
from pydantic import Field

class CustomChatSnowflake(ChatSnowflake):
    """
    Custom subclass of ChatSnowflake to support 'cortex_search_service'
    in the SQL generation options.
    """
    
    cortex_search_service: Optional[str] = Field(default=None)

    def _build_cortex_options_for_sql(self) -> Optional[Dict[str, Any]]:
        """
        Override to inject cortex_search_service into the options dictionary
        passed to SNOWFLAKE.CORTEX.COMPLETE.
        """
        # Get base options (temperature, max_tokens, top_p)
        options = super()._build_cortex_options_for_sql()
        
        if options is None:
            options = {}
        
        # NOTE: cortex_search_service is NOT supported in options for COMPLETE function.
        # Removing it to prevent "invalid options object" error.
        # if self.cortex_search_service:
        #     options["cortex_search_service"] = self.cortex_search_service
            
        return options
