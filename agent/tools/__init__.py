"""
Tool registry for the spark-self-heal agent.

Each tool exposes:
  - SCHEMA: a JSON-Schema-compatible dict consumed by Claude's tool API
  - execute(**kwargs): the implementation, returning a JSON-serializable dict
"""

from agent.tools import catalog, failure_record, glue_logs, pipeline_code

TOOLS = [
    failure_record,
    glue_logs,
    catalog,
    pipeline_code,
]

DISPATCH = {tool.SCHEMA["name"]: tool.execute for tool in TOOLS}

SCHEMAS = [tool.SCHEMA for tool in TOOLS]
