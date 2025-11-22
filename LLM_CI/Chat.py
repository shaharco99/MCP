from __future__ import annotations
import os 
import json
from Utils import get_llm_provider
from Tools import doc_loader
try:
    from langchain_core.messages import ToolMessage
except ImportError:
    ToolMessage = None

# System message
system_message = (
    'You are a very technical assistant that is an expert in DevOps '
    'and best practices of CICD pipelines. Make your answers as short and simple as possible. '
    'You have access to tools that can help you analyze PDF documents. '
    'When asked about PDF contents, use the doc_loader tool to search through them.'
)

# Helper function to extract tool call info
def extract_tool_info(tool_call):
    """Extract tool name, args, and ID from a tool call object or dict."""
    if hasattr(tool_call, 'name'):
        return tool_call.name, getattr(tool_call, 'args', {}), getattr(tool_call, 'id', None)
    elif isinstance(tool_call, dict):
        name = tool_call.get("name") or tool_call.get("tool")
        args = tool_call.get("args") or tool_call.get("arguments", {})
        tool_id = tool_call.get("id") or tool_call.get("tool_call_id")
        return name, args, tool_id
    else:
        name = getattr(tool_call, "name", None) or getattr(tool_call, "tool", "unknown")
        args = getattr(tool_call, "args", {}) or getattr(tool_call, "arguments", {})
        tool_id = getattr(tool_call, "id", None) or getattr(tool_call, "tool_call_id", None)
        return name, args, tool_id

# Helper function to normalize tool args
def normalize_args(args):
    """Convert args to dict format, handling JSON strings."""
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return {}
    return args if isinstance(args, dict) else {}

# Helper function to create tool message
def create_tool_message(content, tool_id):
    """Create a ToolMessage object or tuple based on availability."""
    if ToolMessage and tool_id:
        return ToolMessage(content=str(content), tool_call_id=tool_id)
    return ('tool', str(content))

# Helper function to execute tool
def execute_tool(tool_name, tool_args):
    """Execute a tool and return the result."""
    if tool_name == "doc_loader":
        try:
            return doc_loader.invoke(tool_args)
        except Exception as e:
            return f"Error executing doc_loader: {e}"
    return f"Unknown tool: {tool_name}"

# Initialize
llm_provider = os.getenv('LLM_PROVIDER', '').upper()
llm = get_llm_provider()
print(f"DevOps Chat with {llm_provider}! Type 'exit' to quit.\n")

chat_history = [('system', system_message)]

# Main chat loop
while True:
    question = input('You: ')
    if question.lower() in ['exit', 'quit']:
        print('Exiting chat...')
        break

    chat_history.append(('human', question))

    # Handle tool calls until final response
    while True:
        ai_msg = llm.invoke(chat_history)
        chat_history.append(ai_msg)

        tool_calls = getattr(ai_msg, "tool_calls", None) or []
        
        if not tool_calls:
            # Final response
            if ai_msg.content:
                print(f"AI: {ai_msg.content}\n")
            break

        # Execute tool calls
        for tool_call in tool_calls:
            try:
                tool_name, tool_args, tool_id = extract_tool_info(tool_call)
                tool_args = normalize_args(tool_args)
                
                # Print tool usage
                params_str = json.dumps(tool_args) if tool_args else "{}"
                print(f"tools i use: {tool_name} : parameters : {params_str}\n")
                
                # Execute tool and print output
                result = execute_tool(tool_name, tool_args)
                print(f"Output:\n{result}\n")
                
                # Add result to history
                chat_history.append(create_tool_message(result, tool_id))
            except Exception as e:
                error_msg = f"Error parsing tool call: {e}"
                chat_history.append(create_tool_message(error_msg, None))