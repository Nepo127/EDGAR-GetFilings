from bs4 import BeautifulSoup
import re
import pandas as pd
from typing import List, Tuple, Optional, Dict
import os

# -----------------------------------
# STEP 1: Load the file and split into DOCUMENT blocks
# -----------------------------------

def split_documents(file_content: str) -> List[str]:
    return re.findall(r"<DOCUMENT>(.*?)</DOCUMENT>", file_content, re.DOTALL)

# -----------------------------------
# STEP 2: Extract TYPE and TEXT content from each DOCUMENT
# -----------------------------------

def extract_document_info(document_text: str) -> Tuple[str, str]:
    type_match = re.search(r"<TYPE>(.*?)\n", document_text)
    type_tag: str = type_match.group(1).strip() if type_match else "UNKNOWN"

    text_match = re.search(r"<TEXT>(.*?)$", document_text, re.DOTALL)
    text_content: str = text_match.group(1) if text_match else ""

    return type_tag, text_content

# -----------------------------------
# STEP 3: Extract key financial tables using known IDs or fallback to all tables
# -----------------------------------

def extract_tables_from_html(html_text: str) -> List[Tuple[Optional[str], List[List[str]]]]:
    FINANCIAL_TABLE_IDS: List[str] = [
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
    ]

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

def extract_sections_with_hierarchy(html_text: str) -> List[Dict[str, str]]:
    soup: BeautifulSoup = BeautifulSoup(html_text, "lxml")
    sections: List[Dict[str, str]] = []
    current_section = {"title": "Document Start", "content": ""}

    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        text = tag.get_text(strip=True)
        if current_section["content"]:
            sections.append(current_section)
        current_section = {"title": text, "content": ""}
        for sibling in tag.find_next_siblings():
            if sibling.name in ["h1", "h2", "h3", "h4"]:
                break
            current_section["content"] += sibling.get_text(separator=" ", strip=True) + " "

    if current_section["content"]:
        sections.append(current_section)

    return sections

# -----------------------------------
# STEP 5: Save extracted tables to files
# -----------------------------------

def sanitize_filename(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)

def save_tables(tables: List[Tuple[Optional[str], List[List[str]]]], output_dir: str) -> None:
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

def parse_edgar_txt_file(file_path: str, output_dir: str = "extracted_tables") -> None:
    with open(file_path, "r", encoding="latin1") as file:
        content: str = file.read()

    documents: List[str] = split_documents(content)

    for i, doc in enumerate(documents):
        type_tag, text_content = extract_document_info(doc)

        if type_tag == "10-K":
            print(f"Found 10-K document at block {i}")
            tables = extract_tables_from_html(text_content)
            sections = extract_sections_with_hierarchy(text_content)

            for j, (table_id, table) in enumerate(tables):
                df = pd.DataFrame(table)
                print(f"\nTable {j+1} ({table_id if table_id else 'no ID'}):", df.head(), sep="\n")

            save_tables(tables, output_dir)

            # Save sections for LLM/RAG
            sections_path = os.path.join(output_dir, "sections.json")
            pd.DataFrame(sections).to_json(sections_path, orient="records", indent=4)
            print(f"All tables and sections saved to {output_dir}")
            break

# -----------------------------------
# Example Usage
# -----------------------------------

if __name__ == "__main__":
    parse_edgar_txt_file("0001193125-13-096241.txt")
