"""
EDGAR Document Parser Module

Handles document parsing and extraction of header information from SEC EDGAR filings.
"""

from typing import List, Dict, Any, Optional, Tuple
import re
import logging


class DocumentParser:
    """Handles document parsing and extraction of header information from SEC EDGAR filings."""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger) -> None:
        """
        Initialize the document parser.
        
        Args:
            config (Dict[str, Any]): Configuration dictionary
            logger (logging.Logger): Logger instance
        """
        self.config = config
        self.logger = logger
    
    def extract_header_info(self, content: str) -> Dict[str, Any]:
        """
        Extracts header information from the filing.
        
        Args:
            content (str): Filing content
            
        Returns:
            Dict[str, Any]: Header metadata
        """
        metadata = {}
        
        # Extract common header fields
        header_patterns = {
            "accession_number": r"ACCESSION NUMBER:\s+(\S+)",
            "conformed_period_of_report": r"CONFORMED PERIOD OF REPORT:\s+(\S+)",
            "filed_as_of_date": r"FILED AS OF DATE:\s+(\S+)",
            "date_as_of_change": r"DATE AS OF CHANGE:\s+(\S+)",
            "effectiveness_date": r"EFFECTIVENESS DATE:\s+(\S+)",
            "filer": {
                "company_data": {
                    "company_conformed_name": r"COMPANY CONFORMED NAME:\s+(.+?)$",
                    "central_index_key": r"CENTRAL INDEX KEY:\s+(\d+)",
                    "standard_industrial_classification": r"STANDARD INDUSTRIAL CLASSIFICATION:\s+(.+?)$",
                    "irs_number": r"IRS NUMBER:\s+(\S+)",
                    "fiscal_year_end": r"FISCAL YEAR END:\s+(\S+)",
                },
                "filing_values": {
                    "form_type": r"FORM TYPE:\s+(\S+)",
                    "act": r"ACT:\s+(.+?)$",
                    "file_number": r"FILE NUMBER:\s+(\S+)",
                    "film_number": r"FILM NUMBER:\s+(\S+)",
                }
            }
        }
        
        # First 2000 characters should contain header
        header_text = content[:2000]
        
        # Extract simple fields
        for key, pattern in [(k, v) for k, v in header_patterns.items() if isinstance(v, str)]:
            match = re.search(pattern, header_text, re.MULTILINE)
            if match:
                metadata[key] = match.group(1).strip()
        
        # Extract nested fields
        for main_key, subdict in [(k, v) for k, v in header_patterns.items() if isinstance(v, dict)]:
            metadata[main_key] = {}
            for sub_key, sub_value in subdict.items():
                if isinstance(sub_value, dict):
                    metadata[main_key][sub_key] = {}
                    for sub_sub_key, pattern in sub_value.items():
                        match = re.search(pattern, header_text, re.MULTILINE)
                        if match:
                            metadata[main_key][sub_key][sub_sub_key] = match.group(1).strip()
                else:
                    match = re.search(sub_value, header_text, re.MULTILINE)
                    if match:
                        metadata[main_key][sub_key] = match.group(1).strip()
        
        # Extract form type directly to the main metadata
        if "filer" in metadata and "filing_values" in metadata["filer"] and "form_type" in metadata["filer"]["filing_values"]:
            metadata["form_type"] = metadata["filer"]["filing_values"]["form_type"]
            
        # Extract CIK directly to the main metadata
        if "filer" in metadata and "company_data" in metadata["filer"] and "central_index_key" in metadata["filer"]["company_data"]:
            metadata["cik"] = metadata["filer"]["company_data"]["central_index_key"]
        
        # Parse dates to ISO format where possible
        for date_field in ["conformed_period_of_report", "filed_as_of_date", "date_as_of_change", "effectiveness_date"]:
            if date_field in metadata and metadata[date_field]:
                date_val = metadata[date_field]
                if len(date_val) == 8 and date_val.isdigit():  # YYYYMMDD format
                    try:
                        metadata[date_field] = f"{date_val[:4]}-{date_val[4:6]}-{date_val[6:8]}"
                    except Exception:
                        pass  # Keep original if parsing fails
        
        self.logger.debug(f"Extracted header information with form type: {metadata.get('form_type', 'UNKNOWN')}")
        return metadata
    
    def split_documents(self, file_content: str) -> List[str]:
        """
        Splits the file content into individual <DOCUMENT> blocks.

        Args:
            file_content (str): Filing raw content.

        Returns:
            List[str]: List of document blocks.
        """
        documents = re.findall(r"<DOCUMENT>(.*?)</DOCUMENT>", file_content, re.DOTALL)
        self.logger.info(f"Found {len(documents)} document blocks")
        return documents
    
    def extract_document_info(self, document_text: str) -> Tuple[str, str, Optional[str]]:
        """
        Extracts document TYPE, TEXT, and CIK.

        Args:
            document_text (str): Content of a single <DOCUMENT> block.

        Returns:
            Tuple[str, str, Optional[str]]: TYPE, TEXT, CIK
        """
        type_match = re.search(r"<TYPE>(.*?)\n", document_text)
        type_tag = type_match.group(1).strip() if type_match else "UNKNOWN"
        
        text_match = re.search(r"<TEXT>(.*?)(?:</TEXT>|$)", document_text, re.DOTALL)
        text_content = text_match.group(1) if text_match else document_text
        
        # Look for CIK in multiple formats
        cik_patterns = [
            r"<CIK>(\d+)</CIK>",
            r"CENTRAL INDEX KEY:\s+(\d+)",
            r"CIK=(\d+)",
            r"CIK: (\d+)"
        ]
        
        cik = None
        for pattern in cik_patterns:
            cik_match = re.search(pattern, document_text)
            if cik_match:
                cik = cik_match.group(1)
                break
                
        self.logger.debug(f"Extracted document of type: {type_tag}, CIK: {cik}")
        return type_tag, text_content, cik
