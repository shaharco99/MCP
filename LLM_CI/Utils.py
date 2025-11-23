import getpass
import json
import os
import subprocess
import sys

from dotenv import load_dotenv

from Tools import doc_loader

try:
    from langchain_core.messages import ToolMessage
except ImportError:
    ToolMessage = None

# Load environment variables
load_dotenv()

# System message
system_message = (
    'You are a very technical assistant that is an expert in DevOps '
    'and best practices of CICD pipelines. Make your answers as short and simple as possible. '
    'You have access to tools that can help you analyze various file types (PDF, TXT, CSV, JSON, HTML, DOCX, PPTX, XLSX). '
    'When asked about file contents, use the doc_loader tool to search through them.'
)


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
        try:
            choice = int(input('Enter your choice (1-4): ')) - 1
            if choice < 0 or choice >= len(valid_providers):
                raise ValueError("Invalid choice")
        except (ValueError, IndexError):
            print("Invalid choice. Using default provider.", file=sys.stderr)
            llm_provider = valid_providers[0]
        else:
            llm_provider = valid_providers[choice]
        with open('.env', 'a') as f:
            f.write(f"\nLLM_PROVIDER={llm_provider}")

    # Configure LLM based on provider
    if llm_provider == 'OLLAMA':
        from langchain_ollama import ChatOllama
        
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


def normalize_args(args):
    """Convert args to dict format, handling JSON strings."""
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return {}
    return args if isinstance(args, dict) else {}


def create_tool_message(content, tool_id):
    """Create a ToolMessage object or tuple based on availability."""
    if ToolMessage and tool_id:
        return ToolMessage(content=str(content), tool_call_id=tool_id)
    return ('tool', str(content))


def execute_tool(tool_name, tool_args):
    """Execute a tool and return the result."""
    if tool_name == "doc_loader":
        try:
            return doc_loader.invoke(tool_args)
        except Exception as e:
            return f"Error executing doc_loader: {e}"
    return f"Unknown tool: {tool_name}"


def process_prompt(prompt, llm, verbose=False, output_stream=None):
    """
    Process a single prompt and return the response.
    Handles tool calls automatically.
    
    Args:
        prompt: The prompt text to process
        llm: The LLM instance to use
        verbose: If True, print tool execution details
        output_stream: Stream to write verbose output to (default: sys.stderr)
    
    Returns:
        str: The final response from the LLM
    """
    import sys
    if output_stream is None:
        output_stream = sys.stderr
    
    chat_history = [('system', system_message), ('human', prompt)]
    
    # Handle tool calls until final response
    while True:
        ai_msg = llm.invoke(chat_history)
        chat_history.append(ai_msg)

        tool_calls = getattr(ai_msg, "tool_calls", None) or []
        
        if not tool_calls:
            # Final response
            return ai_msg.content if ai_msg.content else "(no response)"

        # Execute tool calls
        for tool_call in tool_calls:
            try:
                tool_name, tool_args, tool_id = extract_tool_info(tool_call)
                tool_args = normalize_args(tool_args)
                
                if verbose:
                    # Print tool usage
                    params_str = json.dumps(tool_args) if tool_args else "{}"
                    print(f"tools in use: {tool_name} : parameters : {params_str}\n", file=output_stream)
                
                # Execute tool
                result = execute_tool(tool_name, tool_args)
                
                if verbose:
                    print(f"Output:\n{result}\n", file=output_stream)
                
                # Add result to history
                chat_history.append(create_tool_message(result, tool_id))
            except Exception as e:
                error_msg = f"Error parsing tool call: {e}"
                chat_history.append(create_tool_message(error_msg, None))