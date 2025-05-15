"""
EDGAR Table Extractor Module

Extracts tables from both HTML and plain text in SEC EDGAR filings.
"""

from typing import List, Dict, Any, Optional, Tuple
import re
import logging
from bs4 import BeautifulSoup


class TableExtractor:
    """Extracts HTML and plain text tables from EDGAR filings."""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger) -> None:
        """
        Initialize the table extractor.
        
        Args:
            config (Dict[str, Any]): Configuration dictionary
            logger (logging.Logger): Logger instance
        """
        self.config = config
        self.logger = logger
        
        # Load table patterns from config
        table_config = config.get("EdgarParser", {}).get("TextTablePatterns", {})
        self.text_table_patterns = table_config.get("patterns", [
            r"^\s*[-+]{3,}\s+[-+]{3,}",  # Table with --- separator rows
            r"^\s*[|]{1}\s+.*\s+[|]{1}$",  # Table with | separators
            r"^\s*\w+\s+\d+\s+\d+\s+\d+\s+\d+",  # Financial tables with numbers
        ])
        
        # Load filing type profiles from config
        self.filing_type_profiles = {}
        profiles_config = config.get("EdgarParser", {}).get("FilingTypeProfiles", {})
        for filing_type, profile in profiles_config.items():
            profile_sections = []
            for section_type, sections in profile.items():
                if isinstance(sections, list):
                    profile_sections.extend(sections)
            self.filing_type_profiles[filing_type] = profile_sections
    
    def extract_tables_from_html(self, html_text: str, filing_type: Optional[str]) -> List[Tuple[Optional[str], List[List[str]]]]:
        """
        Extracts tables from HTML using filing type profiles.

        Args:
            html_text (str): Filing HTML content.
            filing_type (Optional[str]): Filing type (e.g., "10-K").

        Returns:
            List[Tuple[Optional[str], List[List[str]]]]: Extracted tables.
        """
        table_ids = self.filing_type_profiles.get(filing_type, [])
        tables = []
        
        try:
            # Try to parse with lxml first (faster)
            soup = BeautifulSoup(html_text, "lxml")
        except Exception as e:
            self.logger.warning(f"lxml parsing failed: {e}. Falling back to html.parser")
            soup = BeautifulSoup(html_text, "html.parser")
            
        # First try to find tables by ID
        for table_id in table_ids:
            try:
                anchor = soup.find(id=table_id)
                if anchor:
                    parent_table = anchor.find_parent("table") 
                    if not parent_table:
                        parent_table = anchor.find_next("table")
                    if parent_table:
                        parsed_table = self._parse_table(parent_table)
                        if parsed_table and len(parsed_table) > 1:  # Only include if has more than header
                            tables.append((table_id, parsed_table))
                            self.logger.debug(f"Found table by ID: {table_id}")
            except Exception as e:
                self.logger.warning(f"Error finding table by ID {table_id}: {e}")
                
        # Look for tables by common financial statement names in captions or text
        if not tables:
            financial_statement_keywords = [
                "balance sheet", "statement of operations", "income statement",
                "statement of cash flow", "statement of equity", "financial position"
            ]
            
            # Find potential table titles or captions
            for kw in financial_statement_keywords:
                # Check for text mentioning the keyword near tables
                elements = soup.find_all(text=re.compile(kw, re.IGNORECASE))
                for element in elements:
                    try:
                        # Look at parent and siblings for tables
                        parent = element.parent
                        if parent:
                            # Try to find associated table
                            table = parent.find_next("table")
                            if table:
                                parsed_table = self._parse_table(table)
                                if parsed_table and len(parsed_table) > 1:
                                    table_name = element.get_text(strip=True)
                                    tables.append((table_name, parsed_table))
                                    self.logger.debug(f"Found table by keyword: {kw}")
                    except Exception as e:
                        self.logger.warning(f"Error finding table by keyword {kw}: {e}")
        
        # If still no tables found, get all tables
        if not tables:
            all_tables = soup.find_all("table")
            for i, table in enumerate(all_tables):
                try:
                    parsed_table = self._parse_table(table)
                    # Skip very small tables (likely not actual data tables)
                    if parsed_table and len(parsed_table) > 1 and any(len(row) > 1 for row in parsed_table):
                        # Try to find a nearby title for the table
                        title = self._find_table_title(table)
                        table_name = title if title else f"table_{i+1}"
                        tables.append((table_name, parsed_table))
                except Exception as e:
                    self.logger.warning(f"Error parsing table {i}: {e}")
                    
        self.logger.info(f"Extracted {len(tables)} tables from HTML")
        return tables

    def _find_table_title(self, table_tag: BeautifulSoup) -> Optional[str]:
        """
        Attempts to find a title for a table by looking at preceding elements.
        
        Args:
            table_tag (BeautifulSoup): The table tag.
            
        Returns:
            Optional[str]: Table title if found, None otherwise.
        """
        # Look at caption first
        caption = table_tag.find("caption")
        if caption:
            return caption.get_text(strip=True)
            
        # Look at preceding elements
        for i in range(3):  # Check up to 3 preceding elements
            prev_sib = table_tag
            for _ in range(i+1):
                prev_sib = prev_sib.previous_sibling
                if not prev_sib:
                    break
                    
            if prev_sib and hasattr(prev_sib, 'name'):
                if prev_sib.name in ['h1', 'h2', 'h3', 'h4', 'p', 'div', 'strong', 'b']:
                    text = prev_sib.get_text(strip=True)
                    if text and 5 < len(text) < 200:  # Reasonable title length
                        return text
        
        return None
        
    def extract_tables_from_text(self, text_content: str) -> List[Tuple[str, List[List[str]]]]:
        """
        Extracts tables from plain text using regex patterns.
        
        Args:
            text_content (str): Text content of document.
            
        Returns:
            List[Tuple[str, List[List[str]]]]: Extracted text tables.
        """
        # Split the content into lines
        lines = text_content.split('\n')
        tables = []
        current_table = []
        current_table_name = None
        in_table = False
        
        # Patterns for financial tables
        financial_table_headers = [
            "balance sheet", "statement of operations", "income statement",
            "statement of cash flow", "statement of equity", "financial position",
            "statement of earnings", "statement of financial condition"
        ]
        
        for i, line in enumerate(lines):
            # Check if line could be a table header
            for keyword in financial_table_headers:
                if keyword.lower() in line.lower():
                    if in_table and current_table:
                        # Save previous table if we're finding a new one
                        if len(current_table) > 2:  # At least 3 rows to be a valid table
                            tables.append((current_table_name or f"text_table_{len(tables)+1}", current_table))
                        current_table = []
                    
                    current_table_name = line.strip()
                    # Look ahead for table start
                    for j in range(i+1, min(i+20, len(lines))):
                        # Check if any of the table patterns match
                        if any(re.match(pattern, lines[j]) for pattern in self.text_table_patterns):
                            in_table = True
                            break
                    break
            
            # Check if the line matches a table pattern
            if any(re.match(pattern, line) for pattern in self.text_table_patterns):
                if not in_table:
                    in_table = True
                    if current_table_name is None:
                        # Look back for a potential table name
                        for j in range(max(0, i-5), i):
                            if len(lines[j].strip()) > 0 and len(lines[j].strip()) < 100:
                                current_table_name = lines[j].strip()
                                break
                
                # Process the table line
                cells = self._split_text_table_row(line)
                if cells:
                    current_table.append(cells)
            elif in_table:
                # Check if we're at the end of the table
                if not line.strip() or (len(current_table) > 0 and len(line) < len(min(current_table, key=len))/2):
                    # Empty line or much shorter line could signal end of table
                    consecutive_empty = 1
                    for j in range(i+1, min(i+4, len(lines))):
                        if not lines[j].strip():
                            consecutive_empty += 1
                        else:
                            break
                    
                    if consecutive_empty >= 2:
                        # Likely end of table
                        if len(current_table) > 2:  # At least 3 rows to be a valid table
                            tables.append((current_table_name or f"text_table_{len(tables)+1}", current_table))
                        current_table = []
                        current_table_name = None
                        in_table = False
                else:
                    # Still in table but not a typical line, try to parse it anyway
                    cells = self._split_text_table_row(line)
                    if cells and len(cells) >= len(current_table[0])-2 if current_table else False:  # Allow for some variation
                        current_table.append(cells)
        
        # Don't forget to save the last table if we're still processing one
        if in_table and len(current_table) > 2:
            tables.append((current_table_name or f"text_table_{len(tables)+1}", current_table))
            
        self.logger.info(f"Extracted {len(tables)} tables from plain text")
        return tables
    
    def _split_text_table_row(self, line: str) -> List[str]:
        """
        Splits a line of text into table cells.
        
        Args:
            line (str): Line of text
            
        Returns:
            List[str]: List of cell values
        """
        # Check for pipe-delimited format
        if '|' in line:
            cells = [cell.strip() for cell in line.split('|') if cell.strip()]
            return cells
            
        # Check for fixed-width format by looking for multiple spaces
        cells = re.split(r'\s{2,}', line.strip())
        if len(cells) > 1:
            return [cell.strip() for cell in cells if cell.strip()]
            
        # Try comma-separated values
        if ',' in line and line.count(',') > 1:
            cells = [cell.strip() for cell in line.split(',')]
            return cells
            
        # Split based on consistent spacing in financial tables
        # This is the most challenging case and may need refinement
        # Simple implementation: split on 3+ spaces
        cells = re.split(r'\s{3,}', line.strip())
        if len(cells) > 1:
            return [cell.strip() for cell in cells if cell.strip()]
            
        return []

    def _parse_table(self, table_tag: BeautifulSoup) -> List[List[str]]:
        """
        Converts a <table> tag to a list of lists.

        Args:
            table_tag (BeautifulSoup): The table tag.

        Returns:
            List[List[str]]: Table rows and columns.
        """
        try:
            rows = table_tag.find_all("tr")
            parsed_rows = []
            for row in rows:
                cols = row.find_all(["td", "th"])
                # Skip empty rows
                if not cols:
                    continue
                    
                # Process row cells
                row_data = []
                for col in cols:
                    # Handle colspan and rowspan
                    colspan = int(col.get('colspan', 1))
                    
                    # Get text content, normalizing whitespace
                    text = col.get_text(strip=True)
                    text = re.sub(r'\s+', ' ', text)
                    
                    # Add the cell text
                    row_data.append(text)
                    
                    # Add empty cells for additional columns if colspan > 1
                    row_data.extend([''] * (colspan - 1))
                    
                parsed_rows.append(row_data)
                
            # Normalize row lengths
            if parsed_rows:
                max_cols = max(len(row) for row in parsed_rows)
                normalized_rows = [row + [''] * (max_cols - len(row)) for row in parsed_rows]
                return normalized_rows
            return []
        except Exception as e:
            self.logger.error(f"Error parsing table: {e}")
            return []
