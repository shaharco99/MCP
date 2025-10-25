from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
# TODO allow more chats with DevOps context like gimini https://python.langchain.com/docs/integrations/chat/
load_dotenv()
OllamaModel = os.getenv('OllamaModel')

llm = ChatOllama(
    model=OllamaModel,
    temperature=0,
)

# System message for context
system_message = (
    'You are a very technical assistant that is an expert in DevOps '
    'and best practices of CICD pipelines. Make your answers as short and simple as possible.'
)

print("DevOps Chat! Type 'exit' to quit.\n")

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
