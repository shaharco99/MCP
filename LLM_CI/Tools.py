from __future__ import annotations

import os
from typing import Optional
import ast
import re

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


@tool
def code_reviewer(file_name: str, scope: Optional[str] = None, line_number: Optional[int] = None) -> str:
    """
    Read-only code review tool for Python files.

    - Supports only `.py` files and will not modify any files.
    - Performs static checks using AST and simple heuristics:
      * Syntax errors
      * TODO/FIXME comments
      * Mutable default args
      * Bare `except:` handlers
      * `print()` usage (suggest logging)
      * Long functions (>120 lines)
      * Missing docstrings
      * Missing parameter type hints (heuristic)
      * Approximate unused imports

    Args:
        file_name: filename relative to current working directory
        scope: optional scope string (ignored for now)
        line_number: if provided, return that specific line

    Returns:
        str: human-readable review notes (read-only)
    """
    try:
        file_path = os.path.join(os.getcwd(), file_name)
        if not os.path.exists(file_path):
            return f"Error: File '{file_name}' not found in current directory"

        if not file_path.endswith('.py'):
            return "Error: code_reviewer only supports Python (.py) files"

        try:
            with open(file_path, 'r', encoding='utf-8') as fh:
                source = fh.read()
        except Exception as e:
            return f"Error reading file: {e}"

        if line_number is not None:
            lines = source.splitlines()
            if 1 <= line_number <= len(lines):
                return lines[line_number - 1]
            return f"Error: Line {line_number} not found"

        issues = []

        # Find TODO/FIXME comments
        for i, line in enumerate(source.splitlines(), start=1):
            if 'TODO' in line or 'FIXME' in line:
                issues.append((i, 'TODO/FIXME found', line.strip()))

        # Parse AST to find structural issues
        try:
            tree = ast.parse(source, filename=file_name)
        except SyntaxError as se:
            return f"SyntaxError: {se.msg} (line {se.lineno})"

        # Mutable default args, long functions, missing docstrings, missing type hints
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Mutable defaults
                for default in getattr(node.args, 'defaults', []):
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        issues.append((node.lineno, 'Mutable default argument', f"Function '{node.name}' has a mutable default argument"))

                # Function length (requires Python that sets end_lineno)
                end = getattr(node, 'end_lineno', None)
                if end:
                    length = end - node.lineno + 1
                    if length > 120:
                        issues.append((node.lineno, 'Long function', f"Function '{node.name}' is {length} lines long"))

                # Missing docstring
                if ast.get_docstring(node) is None:
                    issues.append((node.lineno, 'Missing docstring', f"Function '{node.name}' has no docstring"))

                # Heuristic: missing parameter annotations
                params = getattr(node.args, 'args', [])
                if params:
                    has_ann = any(getattr(p, 'annotation', None) is not None for p in params)
                    if not has_ann:
                        issues.append((node.lineno, 'Missing type hints', f"Function '{node.name}' has no parameter type annotations (heuristic)"))

            # Bare except handlers
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    issues.append((getattr(node, 'lineno', 1), 'Bare except', 'Use specific exception types instead of bare except'))

            # print() usage detection
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == 'print':
                    issues.append((getattr(node, 'lineno', 1), 'Print used', 'Consider using logging instead of print()'))

        # Approximate unused imports by comparing imported names to used names
        import_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    import_names.add(n.asname or n.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                for n in node.names:
                    import_names.add(n.asname or n.name)

        used_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)

        unused = sorted(name for name in import_names if name not in used_names)
        for name in unused:
            issues.append((1, 'Unused import', f"Imported name '{name}' appears unused (heuristic)"))

        if not issues:
            return 'No issues found. (read-only review)'

        # Format issues into readable output
        issues_sorted = sorted(issues, key=lambda x: x[0] if isinstance(x[0], int) else 0)
        out = ['Code review (read-only):']
        for lineno, kind, msg in issues_sorted:
            out.append(f"- Line {lineno}: {kind} — {msg}")

        return '\n'.join(out)
    except Exception as e:
        return f"Error running code_reviewer: {e}"
