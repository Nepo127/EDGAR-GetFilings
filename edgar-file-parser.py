
from typing import List, Tuple, Optional, Dict, ClassVar
import os
import re
import uuid
import json
import pandas as pd
from bs4 import BeautifulSoup


class EdgarParser:
    """
    EDGAR Full-Text Filing Parser

    Parses SEC EDGAR full-text filing (.txt) documents.
    Extracts tables and document sections with hierarchy.
    Saves structured data to output folders.

    Version: 1.0.0
    Author: Horia & Matilda
    """
    FILING_TYPE_PROFILES: ClassVar[Dict[str, List[str]]] = {
        "4": ["ownershipTable", "nonDerivativeTable", "derivativeTable", "signatureTable"],
        "10-K": ["consolidated_balance_sheets", "consolidated_statement_of_financial_position",
                 "consolidated_statements_of_operations", "consolidated_statements_of_income",
                 "consolidated_statements_of_comprehensive_income", "consolidated_statements_of_cash_flows",
                 "consolidated_statements_of_changes_in_equity", "consolidated_statements_of_stockholders_equity",
                 "consolidated_statements_of_shareholders_equity",
                 "consolidated_statements_of_redeemable_noncontrolling_interest_and_equity",
                 "consolidated_statements_of_partners_equity", "consolidated_statements_of_members_equity",
                 "financial_statements", "financial_highlights", "selected_financial_data"],
        "10-Q": ["consolidated_balance_sheets", "consolidated_statements_of_operations",
                 "consolidated_statements_of_cash_flows"],
        "20-F": ["consolidated_balance_sheets", "consolidated_statements_of_operations",
                 "consolidated_statements_of_comprehensive_income", "consolidated_statements_of_cash_flows",
                 "consolidated_statements_of_changes_in_equity"],
        "40-F": ["consolidated_balance_sheets", "consolidated_statements_of_operations",
                 "consolidated_statements_of_comprehensive_income", "consolidated_statements_of_cash_flows",
                 "consolidated_statements_of_changes_in_equity"],
        "8-K": [], "S-1": [], "S-3": [], "S-4": [], "S-8": [], "SC 13D": [], "SC 13G": [], "3": [], "5": [],
        "DEF 14A": []
    }

    def __init__(self, file_path: str, output_dir: Optional[str] = None, ticker: Optional[str] = None) -> None:
        """
        Initializes the EDGAR parser.

        Args:
            file_path (str): Path to the EDGAR filing txt file.
            output_dir (Optional[str]): Output folder. If None, generates from file_path.
            ticker (Optional[str]): Company ticker symbol.
        """
        if not isinstance(file_path, str):
            raise TypeError("file_path must be a string.")
        if output_dir is not None and not isinstance(output_dir, str):
            raise TypeError("output_dir must be a string or None.")
        if ticker is not None and not isinstance(ticker, str):
            raise TypeError("ticker must be a string or None.")

        self.file_path: str = file_path
        self.output_dir: str = output_dir or file_path.replace(".txt", "_parsed")
        self.ticker: str = ticker or os.path.basename(os.path.dirname(os.path.dirname(file_path)))
        self.tables_dir: str = os.path.join(self.output_dir, "tables")

    def parse(self) -> None:
        """
        Main entry point to parse an EDGAR filing txt file.
        Extracts tables and sections and saves them to output folders.
        """
        print(f"Starting parse for file: {self.file_path}")

        if not os.path.isfile(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")

        with open(self.file_path, "r", encoding="latin1") as file:
            content: str = file.read()

        documents: List[str] = self._split_documents(content)
        if not documents:
            raise ValueError("No DOCUMENT sections found in filing.")

        for i, doc in enumerate(documents):
            type_tag, text_content, cik = self._extract_document_info(doc)
            if type_tag in self.FILING_TYPE_PROFILES:
                print(f"Found {type_tag} document at block {i}")
                tables = self._extract_tables_from_html(text_content, type_tag)
                sections = self._extract_sections_with_hierarchy(text_content, cik, self.ticker)
                self._save_tables(tables)
                self._save_sections(sections)
                print(f"All tables and sections saved to {self.output_dir}")
                break

    def _split_documents(self, file_content: str) -> List[str]:
        """
        Splits the file content into individual <DOCUMENT> blocks.

        Args:
            file_content (str): Filing raw content.

        Returns:
            List[str]: List of document blocks.
        """
        return re.findall(r"<DOCUMENT>(.*?)</DOCUMENT>", file_content, re.DOTALL)

    def _extract_document_info(self, document_text: str) -> Tuple[str, str, Optional[str]]:
        """
        Extracts document TYPE, TEXT, and CIK.

        Args:
            document_text (str): Content of a single <DOCUMENT> block.

        Returns:
            Tuple[str, str, Optional[str]]: TYPE, TEXT, CIK
        """
        type_match = re.search(r"<TYPE>(.*?)\n", document_text)
        type_tag = type_match.group(1).strip() if type_match else "UNKNOWN"
        text_match = re.search(r"<TEXT>(.*?)$", document_text, re.DOTALL)
        text_content = text_match.group(1) if text_match else ""
        cik_match = re.search(r"<CIK>(\d+)</CIK>", document_text)
        cik = cik_match.group(1) if cik_match else None
        return type_tag, text_content, cik

    def _extract_tables_from_html(self, html_text: str, filing_type: Optional[str]) -> List[Tuple[Optional[str], List[List[str]]]]:
        """
        Extracts tables from HTML using filing type profiles.

        Args:
            html_text (str): Filing HTML content.
            filing_type (Optional[str]): Filing type (e.g., "10-K").

        Returns:
            List[Tuple[Optional[str], List[List[str]]]]: Extracted tables.
        """
        table_ids = self.FILING_TYPE_PROFILES.get(filing_type, [])
        soup = BeautifulSoup(html_text, "lxml")
        tables = []

        for table_id in table_ids:
            anchor = soup.find(id=table_id)
            parent_table = anchor.find_parent("table") if anchor else None
            if not parent_table and anchor:
                parent_table = anchor.find_next("table")
            if parent_table:
                tables.append((table_id, self._parse_table(parent_table)))

        if not tables:
            for table in soup.find_all("table"):
                tables.append((None, self._parse_table(table)))

        return tables

    def _parse_table(self, table_tag: BeautifulSoup) -> List[List[str]]:
        """
        Converts a <table> tag to a list of lists.

        Args:
            table_tag (BeautifulSoup): The table tag.

        Returns:
            List[List[str]]: Table rows and columns.
        """
        rows = table_tag.find_all("tr")
        return [[col.get_text(strip=True) for col in row.find_all(["td", "th"])] for row in rows]

    def _extract_sections_with_hierarchy(self, html_text: str, cik: Optional[str], ticker: Optional[str]) -> List[Dict[str, str]]:
        """
        Extracts sections based on heading hierarchy h1-h4.

        Args:
            html_text (str): Filing HTML content.
            cik (Optional[str]): Company CIK.
            ticker (Optional[str]): Company ticker.

        Returns:
            List[Dict[str, str]]: Extracted structured sections.
        """
        soup = BeautifulSoup(html_text, "lxml")
        sections = []
        heading_stack = []
        current_section = {"title": "Document Start", "level": 0, "parent_title": None, "content": ""}
        section_counter = 1

        for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
            level = int(tag.name[1])
            title = tag.get_text(strip=True)
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            parent_title = heading_stack[-1][1] if heading_stack else None
            heading_stack.append((level, title))
            if current_section["content"]:
                current_section.update({"uuid": str(uuid.uuid4()), "cik": cik, "ticker": ticker, "section_number": section_counter})
                sections.append(current_section)
                section_counter += 1
            current_section = {"title": title, "level": level, "parent_title": parent_title, "content": ""}
            for sibling in tag.find_next_siblings():
                if sibling.name in ["h1", "h2", "h3", "h4"]:
                    break
                current_section["content"] += sibling.get_text(separator=" ", strip=True) + " "

        if current_section["content"]:
            current_section.update({"uuid": str(uuid.uuid4()), "cik": cik, "ticker": ticker, "section_number": section_counter})
            sections.append(current_section)

        return sections

    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitizes a string to be a valid filename.

        Args:
            name (str): Input string.

        Returns:
            str: Safe filename string.
        """
        return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)

    def _save_tables(self, tables: List[Tuple[Optional[str], List[List[str]]]]) -> None:
        """
        Saves tables as CSV files.

        Args:
            tables (List[Tuple[Optional[str], List[List[str]]]]): Tables to save.
        """
        os.makedirs(self.tables_dir, exist_ok=True)
        for idx, (table_id, table) in enumerate(tables):
            df = pd.DataFrame(table)
            filename = f"{self._sanitize_filename(table_id) if table_id else f'table_{idx+1}'}.csv"
            df.to_csv(os.path.join(self.tables_dir, filename), index=False)
            print(f"Saved table to {os.path.join(self.tables_dir, filename)}")

    def _save_sections(self, sections: List[Dict[str, str]]) -> None:
        """
        Saves extracted sections as JSON.

        Args:
            sections (List[Dict[str, str]]): Sections to save.
        """
        os.makedirs(self.output_dir, exist_ok=True)
        path = os.path.join(self.output_dir, "sections.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sections, f, indent=4, ensure_ascii=False)
        print(f"Saved sections to {path}")
