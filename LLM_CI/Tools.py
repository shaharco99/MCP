from __future__ import annotations

import os
from typing import Optional

from langchain_community.document_loaders import BSHTMLLoader
from langchain_community.document_loaders import CSVLoader
from langchain_community.document_loaders import JSONLoader
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders import TextLoader
from langchain_core.tools import tool

# Try to import optional loaders
try:
    from langchain_community.document_loaders import Docx2txtLoader
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    from langchain_community.document_loaders import UnstructuredPowerPointLoader
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

try:
    from langchain_community.document_loaders import UnstructuredExcelLoader
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False


def get_loader_for_file(file_path):
    """Return appropriate loader based on file extension."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.pdf':
        return PyPDFLoader(file_path)
    elif ext == '.txt' or ext == '.md':
        return TextLoader(file_path)
    elif ext == '.csv':
        return CSVLoader(file_path)
    elif ext == '.json':
        # JSONLoader with simple schema - works for most JSON files
        try:
            return JSONLoader(file_path, jq_schema='.')
        except Exception:
            # Fallback to TextLoader if JSONLoader fails (e.g., invalid JSON schema)
            return TextLoader(file_path)
    elif ext == '.html' or ext == '.htm':
        return BSHTMLLoader(file_path)
    elif ext == '.docx' and DOCX_AVAILABLE:
        return Docx2txtLoader(file_path)
    elif ext == '.pptx' and PPTX_AVAILABLE:
        return UnstructuredPowerPointLoader(file_path)
    elif ext in ['.xlsx', '.xls'] and XLSX_AVAILABLE:
        return UnstructuredExcelLoader(file_path)
    else:
        # Try text loader as fallback
        return TextLoader(file_path)


@tool
def doc_loader(file_name: str, search_query: Optional[str] = None, line_number: Optional[int] = None) -> str:
    """
    Load and read/search various file types from the *current directory*.

    Supported file types:
    - PDF (.pdf)
    - Text (.txt, .md)
    - CSV (.csv)
    - JSON (.json)
    - HTML (.html, .htm)
    - Word Documents (.docx) - requires python-docx
    - PowerPoint (.pptx) - requires unstructured
    - Excel (.xlsx, .xls) - requires unstructured

    Args:
        file_name: Name of the file (e.g. "file.pdf", "document.txt", "data.csv")
        search_query: Optional text to search for
        line_number: Optional specific line number to return

    Returns:
        str: The requested content or search results
    """
    try:
        # Build full path in current folder
        file_path = os.path.join(os.getcwd(), file_name)

        if not os.path.exists(file_path):
            return f"Error: File '{file_name}' not found in current directory"

        # Get appropriate loader
        try:
            loader = get_loader_for_file(file_path)
        except ImportError as e:
            return f"Error: Required package not installed for this file type: {e}"

        # Load documents
        try:
            documents = loader.load()
        except Exception as e:
            return f"Error loading file: {e}"

        # Return line number
        if line_number is not None:
            all_text = '\n'.join(doc.page_content for doc in documents)
            lines = all_text.splitlines()
            if 1 <= line_number <= len(lines):
                return lines[line_number - 1]
            return f"Error: Line {line_number} not found"

        # Search query
        if search_query:
            results = []
            for i, doc in enumerate(documents):
                if search_query.lower() in doc.page_content.lower():
                    results.append(f"Section {i + 1}:\n{doc.page_content}")

            if results:
                return '\n\n'.join(results)
            return f"No results found for: {search_query}"

        # Full content
        return '\n'.join(doc.page_content for doc in documents)

    except FileNotFoundError:
        return f"Error: File '{file_name}' not found in current directory"
    except Exception as e:
        return f"Error reading file: {e}"
