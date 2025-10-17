from __future__ import annotations

import os
from typing import List

from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama


load_dotenv()
OllamaModel = os.getenv('OllamaModel')


@tool
def validate_user(user_id: int, addresses: List[str]) -> bool:
    """Validate user using historical addresses.

    Args:
        user_id (int): the user ID.
        addresses (List[str]): Previous addresses as a list of strings.
    """
    return True


llm = ChatOllama(
    model={OllamaModel},
    validate_model_on_init=True,
    temperature=0,
).bind_tools([validate_user])

result = llm.invoke(
    'Could you validate user 123? They previously lived at '
    '123 Fake St in Boston MA and 234 Pretend Boulevard in '
    'Houston TX.'
)

if isinstance(result, AIMessage) and result.tool_calls:
    print(result.tool_calls)
