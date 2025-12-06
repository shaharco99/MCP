from __future__ import annotations

import json
import logging
import os
import sys

from Utils import (
    create_tool_message,
    execute_tool,
    extract_tool_info,
    get_llm_provider,
    log_usage_entry,
    normalize_args,
    reset_chat_usage_log,
    system_message
)

LOG_LEVEL = os.getenv('LOG_LEVEL', 'ERROR').upper()
logging.basicConfig(level=logging.LOG_LEVEL)

# Initialize
llm_provider = os.getenv('LLM_PROVIDER', '').upper()
# If user requested GUI, try launching it and exit the CLI
if '--gui' in sys.argv:
    try:
        from ChatGUI import run_gui
        run_gui()
        sys.exit(0)
    except Exception as e:
        logging.error(f"GUI start error: {e}")

try:
    llm = get_llm_provider()
except Exception as e:
    logging.error(f"Error initializing LLM: {e}",)
    sys.exit(1)

logging.info(f"DevOps Chat with {llm_provider}! Type 'exit' to quit.\n")

reset_chat_usage_log()

chat_history = [('system', system_message)]

# Main chat loop
while True:
    try:
        question = input('You: ')
    except (EOFError, KeyboardInterrupt):
        logging.info('\nExiting chat...')
        break

    if question.lower() in ['exit', 'quit']:
        logging.info('Exiting chat...')
        break

    chat_history.append(('human', question))

    # Loop until final response (allows multi-step tool execution chains)
    tool_call_count = 0
    tool_error_count = 0
    while True:
        try:
            ai_msg = llm.invoke(chat_history)
        except Exception as e:
            log_usage_entry(
                mode='chat',
                prompt=question,
                response='',
                ai_msg=None,
                tool_calls=tool_call_count,
                llm=llm,
                extra={
                    'conversation_turns': len(chat_history),
                    'tool_errors': tool_error_count,
                    'error': f"invoke_error: {e}",
                },
            )
            logging.error(f"Error invoking LLM: {e}")
            logging.error('AI: (Error occurred, please try again)\n')
            break

        chat_history.append(ai_msg)

        tool_calls = getattr(ai_msg, 'tool_calls', None) or []

        if not tool_calls:
            # Final response - send to stdout for proper output separation
            response_text = ai_msg.content or ''
            if response_text:
                logging.info(f"AI: {response_text}\n")
            log_usage_entry(
                mode='chat',
                prompt=question,
                response=response_text,
                ai_msg=ai_msg,
                tool_calls=tool_call_count,
                llm=llm,
                extra={
                    'conversation_turns': len(chat_history),
                    'tool_errors': tool_error_count,
                },
            )
            break

        tool_call_count += len(tool_calls)

        # Execute tool calls
        for tool_call in tool_calls:
            try:
                tool_name, tool_args, tool_id = extract_tool_info(tool_call)
                tool_args = normalize_args(tool_args)

                # Log tool usage to stderr (debugging/logging info)
                params_str = json.dumps(tool_args) if tool_args else '{}'
                logging.info(f"tools in use: {tool_name} : parameters : {params_str}\n",)

                # Execute tool and log output to stderr
                result = execute_tool(tool_name, tool_args)
                logging.info(f"Output:\n{result}\n")

                # Add result to history
                chat_history.append(create_tool_message(result, tool_id))
            except Exception as e:
                tool_error_count += 1
                error_msg = f"Error parsing tool call: {e}"
                logging.warning(f"Warning: {error_msg}\n")
                chat_history.append(create_tool_message(error_msg, None))
