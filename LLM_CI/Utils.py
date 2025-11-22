from dotenv import load_dotenv

import getpass
import os
import subprocess
import sys
from Tools import doc_loader

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

def get_llm_provider(tools=None):
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
        import subprocess
        
        model = os.getenv('OLLAMA_MODEL', 'llama2')
        
        # Check if model exists, if not pull it
        try:
            result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=10)
            if model not in result.stdout:
                print(f"Model '{model}' not found locally. Pulling it now...")
                subprocess.run(['ollama', 'pull', model], check=True, timeout=300)
                print(f"Successfully pulled '{model}'")
        except subprocess.TimeoutExpired:
            print(f"Warning: Timeout checking/pulling Ollama model '{model}'")
        except FileNotFoundError:
            print("Warning: Ollama CLI not found. Make sure Ollama is installed and in PATH")
        except Exception as e:
            print(f"Warning: Could not verify/pull model: {str(e)}")
        
        llm = ChatOllama(model=model, temperature=0).bind_tools([doc_loader] if tools is None else tools)

    elif llm_provider == 'OPENAI':
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            install_package('langchain-openai')
            from langchain_openai import ChatOpenAI

        api_key = get_api_key('OPENAI')
        model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
        llm = ChatOpenAI(api_key=api_key, model=model, temperature=0).bind_tools([doc_loader] if tools is None else tools)

    elif llm_provider == 'GOOGLE':
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            install_package('langchain-google-genai')
            from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = get_api_key('GOOGLE')
        model = os.getenv('GOOGLE_MODEL', 'gemini-pro')
        llm = ChatGoogleGenerativeAI(api_key=api_key, model=model, temperature=0).bind_tools([doc_loader] if tools is None else tools)

    elif llm_provider == 'ANTHROPIC':
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            install_package('langchain-anthropic')
            from langchain_anthropic import ChatAnthropic

        api_key = get_api_key('ANTHROPIC')
        model = os.getenv('ANTHROPIC_MODEL', 'claude-2')
        llm = ChatAnthropic(api_key=api_key, model=model, temperature=0).bind_tools([doc_loader] if tools is None else tools)
    return llm