from __future__ import annotations

import getpass
import os
import subprocess
import sys

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def install_package(package):
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', package])
        print(f"Successfully installed {package}")
    except subprocess.CalledProcessError:
        print(f"Failed to install {package}")
        sys.exit(1)


def get_api_key(provider):
    key = os.environ.get(f"{provider}_API_KEY")
    if not key:
        key = getpass.getpass(f"Enter API key for {provider}: ")
        with open('.env', 'a') as f:
            f.write(f"\n{provider}_API_KEY={key}")
    return key


# Get LLM provider from environment or user input
llm_provider = os.getenv('LLM_PROVIDER', '').upper()
valid_providers = ['OLLAMA', 'OPENAI', 'GOOGLE', 'ANTHROPIC']

if llm_provider not in valid_providers:
    print('Please choose an LLM provider:')
    for i, provider in enumerate(valid_providers, 1):
        print(f"{i}. {provider}")
    choice = int(input('Enter your choice (1-4): ')) - 1
    llm_provider = valid_providers[choice]
    with open('.env', 'a') as f:
        f.write(f"\nLLM_PROVIDER={llm_provider}")

# Configure LLM based on provider
if llm_provider == 'OLLAMA':
    from langchain_ollama import ChatOllama
    model = os.getenv('OLLAMA_MODEL', 'llama2')
    llm = ChatOllama(model=model, temperature=0)

elif llm_provider == 'OPENAI':
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        install_package('langchain-openai')
        from langchain_openai import ChatOpenAI

    api_key = get_api_key('OPENAI')
    model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
    llm = ChatOpenAI(api_key=api_key, model=model, temperature=0)

elif llm_provider == 'GOOGLE':
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError:
        install_package('langchain-google-genai')
        from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = get_api_key('GOOGLE')
    model = os.getenv('GOOGLE_MODEL', 'gemini-pro')
    llm = ChatGoogleGenerativeAI(api_key=api_key, model=model, temperature=0)

elif llm_provider == 'ANTHROPIC':
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        install_package('langchain-anthropic')
        from langchain_anthropic import ChatAnthropic

    api_key = get_api_key('ANTHROPIC')
    model = os.getenv('ANTHROPIC_MODEL', 'claude-2')
    llm = ChatAnthropic(api_key=api_key, model=model, temperature=0)

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
