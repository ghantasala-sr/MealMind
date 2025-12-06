import json
from typing import Any, Dict, Iterator, List, Optional, Tuple
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple
import snowflake.connector
import uuid

class SnowflakeCheckpointSaver(BaseCheckpointSaver):
    """A checkpoint saver that stores checkpoints in a Snowflake table."""

    def __init__(self, conn):
        super().__init__()
        self.conn = conn

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Get a checkpoint tuple from the database."""
        thread_id = config["configurable"]["thread_id"]
        
        cursor = self.conn.cursor()
        try:
            # Get the latest checkpoint for this thread
            # We order by created_at DESC to get the most recent one
            cursor.execute("""
                SELECT checkpoint_data, checkpoint_id
                FROM thread_checkpoints
                WHERE thread_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (thread_id,))
            
            row = cursor.fetchone()
            if row:
                checkpoint_data_str = row[0]
                checkpoint_id = row[1]
                
                if isinstance(checkpoint_data_str, str):
                    data = json.loads(checkpoint_data_str)
                else:
                    data = checkpoint_data_str
                
                # Reconstruct Checkpoint object
                # Note: This assumes a simple serialization. 
                # In a real production app, you might need more robust serialization/deserialization
                # compatible with LangGraph's internal format.
                # For now, we assume 'checkpoint' and 'metadata' are top-level keys in the JSON.
                
                checkpoint = data.get("checkpoint")
                metadata = data.get("metadata", {})
                parent_config = data.get("parent_config")
                
                return CheckpointTuple(
                    config=config,
                    checkpoint=checkpoint,
                    metadata=metadata,
                    parent_config=parent_config
                )
                
            return None
        except Exception as e:
            print(f"Error getting checkpoint: {e}")
            return None
        finally:
            cursor.close()

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """List checkpoints from the database."""
        # Simplified implementation for now - just returns empty iterator or basic list
        # Full implementation would require complex filtering logic mapping to SQL
        yield from []

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Dict[str, Any],
    ) -> RunnableConfig:
        """Save a checkpoint to the database."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = str(uuid.uuid4())
        
        # Serialize the entire state
        data = {
            "checkpoint": checkpoint,
            "metadata": metadata,
            "parent_config": config,
            "new_versions": new_versions
        }
        
        # Use a custom encoder to handle non-serializable objects if necessary
        # For basic LangGraph state (dicts, lists, strings), default json dump is usually fine
        # but LangChain objects might need serialization.
        # For this implementation, we'll rely on LangGraph's serializable nature or stringify.
        
        # IMPORTANT: LangGraph checkpoints can contain complex objects. 
        # Ideally we should use the serializer provided by LangGraph, but for this custom implementation
        # we will try a best-effort JSON dump.
        
        # To make this robust, we should use the `serde` from BaseCheckpointSaver if available,
        # but BaseCheckpointSaver doesn't enforce a specific serde.
        # We will assume the state is JSON serializable for this specific app (mostly dicts/strings).
        
        try:
            json_data = json.dumps(data, default=str)
        except Exception as e:
            print(f"Serialization warning: {e}")
            json_data = json.dumps(data, default=lambda o: f"<{type(o).__name__}>")

        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO thread_checkpoints (checkpoint_id, thread_id, checkpoint_data)
                SELECT %s, %s, PARSE_JSON(%s)
            """, (checkpoint_id, thread_id, json_data))
            self.conn.commit()
        except Exception as e:
            print(f"Error saving checkpoint: {e}")
        finally:
            cursor.close()
            
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: List[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Store intermediate writes."""
        # Currently a no-op as we don't strictly need to persist intermediate writes for this chat application
        # preventing the NotImplementedError
        pass
