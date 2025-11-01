from __future__ import annotations
import os 
from Utils import get_llm_provider
from langchain_core.tools import tool

# System message for context
system_message = (
    'You are a very technical assistant that is an expert in DevOps '
    'and best practices of CICD pipelines. Make your answers as short and simple as possible.'
)

llm_provider = os.getenv('LLM_PROVIDER', '').upper()
llm = get_llm_provider()
print(f"DevOps Chat with {llm_provider}! Type 'exit' to quit.\n")

# Initialize chat history with system message
chat_history = [('system', system_message)]

while True:
    question = input('You: ')
    if question.lower() in ['exit', 'quit']:
        print('Exiting chat...')
        break

    # Add human message to history
    chat_history.append(('human', question))

    # Invoke the model with full chat history
    ai_msg = llm.invoke(chat_history)

    # Add AI response to history
    chat_history.append(('assistant', ai_msg.content))

    # Print AI response
    print(f"AI: {ai_msg.content}\n")
