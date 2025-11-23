from __future__ import annotations

import json
import os
import sys

from Utils import (
    get_llm_provider,
    system_message,
    extract_tool_info,
    normalize_args,
    create_tool_message,
    execute_tool,
)

# Initialize
llm_provider = os.getenv('LLM_PROVIDER', '').upper()
try:
    llm = get_llm_provider()
except Exception as e:
    print(f"Error initializing LLM: {e}", file=sys.stderr)
    sys.exit(1)

print(f"DevOps Chat with {llm_provider}! Type 'exit' to quit.\n", file=sys.stderr)

chat_history = [('system', system_message)]

# Main chat loop
while True:
    try:
        question = input('You: ')
    except (EOFError, KeyboardInterrupt):
        print('\nExiting chat...', file=sys.stderr)
        break
    
    if question.lower() in ['exit', 'quit']:
        print('Exiting chat...', file=sys.stderr)
        break

    chat_history.append(('human', question))

    # Loop until final response (allows multi-step tool execution chains)
    while True:
        try:
            ai_msg = llm.invoke(chat_history)
        except Exception as e:
            print(f"Error invoking LLM: {e}", file=sys.stderr)
            print("AI: (Error occurred, please try again)\n", file=sys.stdout)
            break
        
        chat_history.append(ai_msg)

        tool_calls = getattr(ai_msg, "tool_calls", None) or []
        
        if not tool_calls:
            # Final response - send to stdout for proper output separation
            if ai_msg.content:
                print(f"AI: {ai_msg.content}\n")
            break

        # Execute tool calls
        for tool_call in tool_calls:
            try:
                tool_name, tool_args, tool_id = extract_tool_info(tool_call)
                tool_args = normalize_args(tool_args)
                
                # Log tool usage to stderr (debugging/logging info)
                params_str = json.dumps(tool_args) if tool_args else "{}"
                print(f"tools in use: {tool_name} : parameters : {params_str}\n", file=sys.stderr)
                
                # Execute tool and log output to stderr
                result = execute_tool(tool_name, tool_args)
                print(f"Output:\n{result}\n", file=sys.stderr)
                
                # Add result to history
                chat_history.append(create_tool_message(result, tool_id))
            except Exception as e:
                error_msg = f"Error parsing tool call: {e}"
                print(f"Warning: {error_msg}\n", file=sys.stderr)
                chat_history.append(create_tool_message(error_msg, None))