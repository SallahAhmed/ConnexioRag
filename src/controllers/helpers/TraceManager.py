import time
import json
import logging
from typing import Dict, Any, List

class TraceManager:
    """
    A lightweight internal tracer for RAG steps, providing observability
    into generation latency, tool usage, sizes, etc.
    """
    def __init__(self):
        self.logger = logging.getLogger("RAG_Tracer")
        self.logger.setLevel(logging.INFO)
        # Assuming console handler is registered elsewhere, or we just log to standard output.
        self.traces: Dict[str, Any] = {}

    def start_trace(self, trace_id: str, action_name: str, metadata: dict = None):
        if trace_id not in self.traces:
            self.traces[trace_id] = {
                "trace_id": trace_id,
                "created_at": time.time(),
                "steps": []
            }
        
        step_id = f"step_{len(self.traces[trace_id]['steps']) + 1}"
        self.traces[trace_id]['steps'].append({
            "step_id": step_id,
            "action_name": action_name,
            "start_time": time.time(),
            "metadata": metadata or {}
        })
        return step_id

    def end_trace(self, trace_id: str, step_id: str, output: Any = None, usage: dict = None):
        if trace_id in self.traces:
            for step in self.traces[trace_id]["steps"]:
                if step["step_id"] == step_id:
                    step["end_time"] = time.time()
                    step["duration_ms"] = (step["end_time"] - step["start_time"]) * 1000
                    step["output_summary"] = str(output)[:200] if output else None
                    if usage:
                        step["usage"] = usage
                    self.logger.info(f"[TRACE] {step['action_name']} completed in {step['duration_ms']:.2f}ms")
                    break
        
    def export_trace(self, trace_id: str) -> str:
        if trace_id in self.traces:
            return json.dumps(self.traces[trace_id], indent=2)
        return "{}"

# Singleton pattern for easy import
tracer = TraceManager()
