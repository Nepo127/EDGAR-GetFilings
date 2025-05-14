"""
EDGAR Full-Text Filing Parser

This module parses SEC EDGAR full-text filing (.txt) documents. It extracts:
1. Tables based on known table IDs for specific filing types.
2. Filing document sections with heading hierarchy, parent-child relationships, UUIDs, and metadata.

The module saves extracted data into a structured folder alongside the original file.
This tool is designed for use in large-scale batch filing processing and downstream
analytics or retrieval augmented generation (RAG) pipelines.

Version: 1.0.0
Author: Horia & Matilda
"""

__version__ = "1.0.0"

from bs4 import BeautifulSoup
import re
import pandas as pd
from typing import List, Tuple, Optional, Dict
import os

# -----------------------------------
# STEP 1: Load the file and split into DOCUMENT blocks
# -----------------------------------

def split_documents(file_content: str) -> List[str]:
    """
    Splits the entire EDGAR txt file content into individual <DOCUMENT> blocks.

    Args:
        file_content (str): Raw text content of the filing.

    Returns:
        List[str]: List of individual document content blocks.
    """
    """
    Splits the entire EDGAR txt file content into individual <DOCUMENT> blocks.
    Returns a list of document content strings.
    """
    return re.findall(r"<DOCUMENT>(.*?)</DOCUMENT>", file_content, re.DOTALL)

# -----------------------------------
# STEP 2: Extract TYPE and TEXT content from each DOCUMENT
# -----------------------------------

def extract_document_info(document_text: str) -> Tuple[str, str, Optional[str]]:
    """
    Extracts the TYPE, TEXT, and CIK values from a document block.

    Args:
        document_text (str): Text content of a <DOCUMENT> block.

    Returns:
        Tuple[str, str, Optional[str]]: Document type, document HTML text, and CIK.
    """
    """
    Extracts the TYPE, TEXT, and CIK values from a document block.
    TYPE indicates the document type (e.g., 10-K).
    TEXT is the HTML body of the filing.
    CIK is the Central Index Key identifier for the company.
    """
    type_match = re.search(r"<TYPE>(.*?)\n", document_text)
    type_tag: str = type_match.group(1).strip() if type_match else "UNKNOWN"

    text_match = re.search(r"<TEXT>(.*?)$", document_text, re.DOTALL)
    text_content: str = text_match.group(1) if text_match else ""
    cik_match = re.search(r"<CIK>(\d+)</CIK>", document_text)
    cik: Optional[str] = cik_match.group(1) if cik_match else None

    return type_tag, text_content

# -----------------------------------
# STEP 3: Extract key financial tables using known IDs or fallback to all tables
# -----------------------------------

def extract_tables_from_html(html_text: str, filing_type: Optional[str] = None) -> List[Tuple[Optional[str], List[List[str]]]]:
    """
    Extracts key financial tables from filing HTML content.

    Args:
        html_text (str): HTML content of the filing.

    Returns:
        List[Tuple[Optional[str], List[List[str]]]]: List of tuples containing table IDs and table data.
    """
    """
    Extracts key financial tables from filing HTML content.
    Searches by known SEC table IDs first; falls back to all tables if no match.
    Returns a list of tuples: (table_id, table_data).
    """
    FILING_TYPE_PROFILES: Dict[str, List[str]] = {
        "4": [
            "ownershipTable",
            "nonDerivativeTable",
            "derivativeTable",
            "signatureTable"
        ],
        "10-K": [
            "consolidated_balance_sheets",
            "consolidated_statement_of_financial_position",
            "consolidated_statements_of_operations",
            "consolidated_statements_of_income",
            "consolidated_statements_of_comprehensive_income",
            "consolidated_statements_of_cash_flows",
            "consolidated_statements_of_changes_in_equity",
            "consolidated_statements_of_stockholders_equity",
            "consolidated_statements_of_shareholders_equity",
            "consolidated_statements_of_redeemable_noncontrolling_interest_and_equity",
            "consolidated_statements_of_partners_equity",
            "consolidated_statements_of_members_equity",
            "financial_statements",
            "financial_highlights",
            "selected_financial_data"
        ],
        "10-Q": [
            "consolidated_balance_sheets",
            "consolidated_statements_of_operations",
            "consolidated_statements_of_cash_flows"
        ],
        "20-F": [
            "consolidated_balance_sheets",
            "consolidated_statements_of_operations",
            "consolidated_statements_of_comprehensive_income",
            "consolidated_statements_of_cash_flows",
            "consolidated_statements_of_changes_in_equity"
        ],
        "40-F": [
            "consolidated_balance_sheets",
            "consolidated_statements_of_operations",
            "consolidated_statements_of_comprehensive_income",
            "consolidated_statements_of_cash_flows",
            "consolidated_statements_of_changes_in_equity"
        ],
        "8-K": [],
        "S-1": [],
        "S-3": [],
        "S-4": [],
        "S-8": [],
        "SC 13D": [],
        "SC 13G": [],
        "3": [
            "ownershipTable",
            "nonDerivativeTable",
            "derivativeTable",
            "signatureTable"
        ],
        "4": [],
        "5": [
            "ownershipTable",
            "nonDerivativeTable",
            "derivativeTable",
            "signatureTable"
        ],
        "DEF 14A": []
    }

    table_ids = FILING_TYPE_PROFILES.get(filing_type, [])

    soup: BeautifulSoup = BeautifulSoup(html_text, "lxml")
    table_data: List[Tuple[Optional[str], List[List[str]]]] = []

    for table_id in FINANCIAL_TABLE_IDS:
        anchor = soup.find(id=table_id)
        if anchor:
            parent_table = anchor.find_parent("table")
            if not parent_table:
                parent_table = anchor.find_next("table")
            if parent_table:
                rows = parent_table.find_all("tr")
                table_matrix: List[List[str]] = []
                for row in rows:
                    cols = row.find_all(["td", "th"])
                    cols_text: List[str] = [col.get_text(strip=True) for col in cols]
                    table_matrix.append(cols_text)
                table_data.append((table_id, table_matrix))

    if not table_data:
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            table_matrix: List[List[str]] = []
            for row in rows:
                cols = row.find_all(["td", "th"])
                cols_text: List[str] = [col.get_text(strip=True) for col in cols]
                table_matrix.append(cols_text)
            table_data.append((None, table_matrix))

    return table_data

# -----------------------------------
# STEP 4: Extract hierarchical text sections for LLM/RAG
# -----------------------------------

import uuid


def extract_sections_with_hierarchy(html_text: str, cik: Optional[str] = None, ticker: Optional[str] = None) -> List[Dict[str, str]]:
    if not isinstance(html_text, str):
        raise TypeError("html_text must be a string.")
    if cik is not None and not isinstance(cik, str):
        raise TypeError("cik must be a string or None.")
    if ticker is not None and not isinstance(ticker, str):
        raise TypeError("ticker must be a string or None.")
    """
    Extracts filing sections based on heading hierarchy (h1-h4).

    Args:
        html_text (str): HTML content of the filing.
        cik (Optional[str]): Company CIK identifier.
        ticker (Optional[str]): Company ticker symbol.

    Returns:
        List[Dict[str, str]]: List of structured section dictionaries with hierarchy and metadata.
    """
    """
    Extracts filing sections based on heading hierarchy (h1-h4).
    Adds parent-child relationships, uuid, cik, ticker, and section_number to each section.
    Returns a list of structured section dictionaries.
    """
    soup: BeautifulSoup = BeautifulSoup(html_text, "lxml")
    sections: List[Dict[str, str]] = []
    heading_stack: List[Tuple[int, str]] = []
    current_section: Dict[str, Optional[str]] = {
        "title": "Document Start",
        "level": 0,
        "parent_title": None,
        "content": ""
    }

    section_counter = 1  # <-- NEW: for section_number

    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        level = int(tag.name[1])
        title = tag.get_text(strip=True)

        while heading_stack and heading_stack[-1][0] >= level:
            heading_stack.pop()
        parent_title = heading_stack[-1][1] if heading_stack else None
        heading_stack.append((level, title))

        if current_section["content"]:
            current_section["uuid"] = str(uuid.uuid4())
            current_section["cik"] = cik
            current_section["ticker"] = ticker
            current_section["section_number"] = section_counter
            sections.append(current_section)
            section_counter += 1

        current_section = {
            "title": title,
            "level": level,
            "parent_title": parent_title,
            "content": ""
        }

        for sibling in tag.find_next_siblings():
            if sibling.name in ["h1", "h2", "h3", "h4"]:
                break
            current_section["content"] += sibling.get_text(separator=" ", strip=True) + " "

    if current_section["content"]:
        current_section["uuid"] = str(uuid.uuid4())
        current_section["cik"] = cik
        current_section["ticker"] = ticker
        current_section["section_number"] = section_counter
        sections.append(current_section)

    return sections

# -----------------------------------
# STEP 5: Save extracted tables to files
# -----------------------------------

def sanitize_filename(name: str) -> str:
    """
    Cleans file names by replacing any unsafe characters with underscores.

    Args:
        name (str): Original filename.

    Returns:
        str: Sanitized safe filename.
    """
    """
    Cleans file names by replacing any unsafe characters with underscores.
    """
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)

def save_tables(tables: List[Tuple[Optional[str], List[List[str]]]], output_dir: str) -> None:
    """
    Saves extracted financial tables as individual CSV files in the target folder.

    Args:
        tables (List[Tuple[Optional[str], List[List[str]]]]): Extracted table data.
        output_dir (str): Path to the folder where CSV files will be saved.
    """
    """
    Saves extracted financial tables as individual CSV files in the target folder.
    """
    os.makedirs(output_dir, exist_ok=True)
    for idx, (table_id, table) in enumerate(tables):
        df: pd.DataFrame = pd.DataFrame(table)
        sanitized_id = sanitize_filename(table_id) if table_id else f'table_{idx+1}'
        file_name = f"{sanitized_id}.csv"
        file_path = os.path.join(output_dir, file_name)
        df.to_csv(file_path, index=False)

# -----------------------------------
# MAIN: Full Parser
# -----------------------------------

def parse_edgar_txt_file(file_path: str, output_dir: Optional[str] = None, ticker: Optional[str] = None) -> None:
    if not isinstance(file_path, str):
        raise TypeError("file_path must be a string.")
    if output_dir is not None and not isinstance(output_dir, str):
        raise TypeError("output_dir must be a string or None.")
    if ticker is not None and not isinstance(ticker, str):
        raise TypeError("ticker must be a string or None.")
    """
    Parses a full EDGAR txt file, extracts tables and sections, saves results to structured folders.

    Args:
        file_path (str): Path to the input EDGAR txt file.
        output_dir (Optional[str]): Folder for parsed output (default is <input_file>_parsed).
        ticker (Optional[str]): Ticker symbol of the company. If None, attempts to infer from path.

    Raises:
        FileNotFoundError: If the input file does not exist.
        ValueError: If the txt file does not contain any DOCUMENT sections.

    Returns:
        None
    """
    """
    Main entry point to parse an EDGAR filing txt file.

    Args:
        file_path (str): Path to the EDGAR filing txt file.
        output_dir (Optional[str]): Path where parsed outputs will be stored. Defaults to None.
        ticker (Optional[str]): Company ticker symbol. If not provided, it is inferred from the path.

    Returns:
        None
    """
    """
    Main entry point to parse an EDGAR filing txt file.
    Extracts tables and sections from any supported SEC filing document.
    Outputs data into a clean parsed package folder structure.
    """
    if ticker is None:
        ticker = os.path.basename(os.path.dirname(os.path.dirname(file_path)))
    if output_dir is None:
        output_dir = file_path.replace(".txt", "_parsed")
    tables_dir = os.path.join(output_dir, "tables")

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="latin1") as file:
        content: str = file.read()

    documents: List[str] = split_documents(content)
    if not documents:
        raise ValueError("No DOCUMENT sections found in filing.")

    for i, doc in enumerate(documents):
        #type_tag, text_content = extract_document_info(doc)
        type_tag, text_content, cik = extract_document_info(doc)

        if type_tag in FILING_TYPE_PROFILES:
            print(f"Found {type_tag} document at block {i}")
            tables = extract_tables_from_html(text_content, filing_type=type_tag)
            sections = extract_sections_with_hierarchy(text_content, cik=cik, ticker=ticker)

            for j, (table_id, table) in enumerate(tables):
                df = pd.DataFrame(table)
                print(f"\nTable {j+1} ({table_id if table_id else 'no ID'}):", df.head(), sep="\n")

            save_tables(tables, tables_dir)

            # Save sections for LLM/RAG
            sections_path = os.path.join(output_dir, "sections.json")
            import json
            with open(sections_path, "w", encoding="utf-8") as f:
                json.dump(sections, f, indent=4, ensure_ascii=False)
            print(f"All tables and sections saved to {output_dir}")
            break

# -----------------------------------
# Example Usage
# -----------------------------------

if __name__ == "__main__":
    parse_edgar_txt_file("0001193125-13-096241.txt")
