from __future__ import annotations
import os 
import json
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