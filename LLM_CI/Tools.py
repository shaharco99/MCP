from __future__ import annotations

import os
from typing import Optional

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.tools import tool


@tool
def doc_loader(pdf_name: str, search_query: Optional[str] = None, line_number: Optional[int] = None) -> str:
    """
    Load and read/search a PDF file from the *current directory*.

    Args:
        pdf_name: Name of the PDF file (e.g. "file.pdf")
        search_query: Optional text to search for
        line_number: Optional specific line number to return

    Returns:
        str: The requested content or search results
    """
    try:
        # Build full path in current folder
        pdf_path = os.path.join(os.getcwd(), pdf_name)

        # Load PDF
        loader = PyPDFLoader(pdf_path)
        pages = loader.load_and_split()

        # Return line number
        if line_number is not None:
            all_text = "\n".join(p.page_content for p in pages)
            lines = all_text.splitlines()
            if 1 <= line_number <= len(lines):
                return lines[line_number - 1]
            return f"Error: Line {line_number} not found"

        # Search query
        if search_query:
            results = []
            for i, page in enumerate(pages):
                if search_query.lower() in page.page_content.lower():
                    results.append(f"Page {i+1}:\n{page.page_content}")

            if results:
                return "\n\n".join(results)
            return f"No results found for: {search_query}"

        # Full content
        return "\n".join(page.page_content for page in pages)

    except FileNotFoundError:
        return f"Error: PDF '{pdf_name}' not found in current directory"
    except Exception as e:
        return f"Error reading PDF: {e}"

