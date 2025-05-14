from typing import List, Tuple, Optional, Dict, ClassVar, Any, Iterator, Union
import os
import re
import uuid
import json
import pandas as pd
from bs4 import BeautifulSoup
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import chardet
import tomli  # For reading TOML files


class EdgarParser:
    """
    EDGAR Full-Text Filing Parser

    Parses SEC EDGAR full-text filing (.txt) documents.
    Extracts tables and document sections with hierarchy.
    Saves structured data to output folders.

    Version: 1.2.0
    Author: Horia & Matilda
    Enhanced by: Claude
    """
    FILING_TYPE_PROFILES: ClassVar[Dict[str, List[str]]] = {
        # Annual Reports
        "10-K": [
            # Balance Sheets
            "consolidated_balance_sheets", "consolidated_statement_of_financial_position",
            "balance_sheets", "statement_of_financial_position", "balance_sheet",
            
            # Income Statements
            "consolidated_statements_of_operations", "consolidated_statements_of_income",
            "statements_of_operations", "statements_of_income", "income_statements",
            "consolidated_statements_of_earnings", "statements_of_earnings",
            "consolidated_statements_of_comprehensive_income", "statements_of_comprehensive_income",
            
            # Cash Flow Statements
            "consolidated_statements_of_cash_flows", "statements_of_cash_flows", "cash_flow_statements",
            
            # Equity Statements
            "consolidated_statements_of_changes_in_equity", "statements_of_changes_in_equity",
            "consolidated_statements_of_stockholders_equity", "statements_of_stockholders_equity",
            "consolidated_statements_of_shareholders_equity", "statements_of_shareholders_equity",
            "consolidated_statements_of_redeemable_noncontrolling_interest_and_equity",
            "consolidated_statements_of_partners_equity", "statements_of_partners_equity",
            "consolidated_statements_of_members_equity", "statements_of_members_equity",
            
            # Other Financial Tables
            "financial_statements", "financial_highlights", "selected_financial_data",
            "financial_data", "ratio_of_earnings", "unaudited_quarterly_financial_data",
            "summary_of_significant_accounting_policies",
            
            # Notes and Supplemental Tables
            "notes_to_consolidated_financial_statements", "notes_to_financial_statements",
            "schedule_of_valuation_and_qualifying_accounts", 
            "summary_of_quarterly_financial_data",
            "schedule_of_investee_earnings"
        ],
        
        # Quarterly Reports
        "10-Q": [
            # Balance Sheets
            "consolidated_balance_sheets", "balance_sheets", "statement_of_financial_position",
            "consolidated_statement_of_financial_position",
            
            # Income Statements
            "consolidated_statements_of_operations", "statements_of_operations",
            "consolidated_statements_of_income", "statements_of_income",
            "consolidated_statements_of_earnings", "statements_of_earnings",
            "consolidated_statements_of_comprehensive_income", "statements_of_comprehensive_income",
            
            # Cash Flow Statements
            "consolidated_statements_of_cash_flows", "statements_of_cash_flows",
            
            # Equity Statements
            "consolidated_statements_of_changes_in_equity", "statements_of_changes_in_equity",
            "consolidated_statements_of_stockholders_equity", "statements_of_stockholders_equity",
            "consolidated_statements_of_shareholders_equity", "statements_of_shareholders_equity",
            
            # Management Discussion
            "management_discussion_and_analysis", "management_discussion"
        ],
        
        # Current Reports
        "8-K": [
            "financial_statements", "pro_forma_financial_information", "exhibits",
            "signature", "press_release", "material_agreement_table", "amendments_table"
        ],
        
        # Foreign Annual Reports
        "20-F": [
            "consolidated_balance_sheets", "balance_sheets", "statement_of_financial_position",
            "consolidated_statements_of_operations", "statements_of_operations",
            "consolidated_statements_of_income", "statements_of_income",
            "consolidated_statements_of_comprehensive_income", "statements_of_comprehensive_income",
            "consolidated_statements_of_cash_flows", "statements_of_cash_flows",
            "consolidated_statements_of_changes_in_equity", "statements_of_changes_in_equity",
            "exchange_rates", "selected_financial_data", "operating_and_financial_review"
        ],
        
        # Canadian Annual Reports
        "40-F": [
            "consolidated_balance_sheets", "balance_sheets", "statement_of_financial_position",
            "consolidated_statements_of_operations", "statements_of_operations",
            "consolidated_statements_of_income", "statements_of_income",
            "consolidated_statements_of_comprehensive_income", "statements_of_comprehensive_income",
            "consolidated_statements_of_cash_flows", "statements_of_cash_flows",
            "consolidated_statements_of_changes_in_equity", "statements_of_changes_in_equity"
        ],
        
        # Registration Statements
        "S-1": [
            "summary_financial_data", "capitalization", "dilution", "financial_statements",
            "balance_sheets", "statements_of_operations", "statements_of_cash_flows",
            "use_of_proceeds", "underwriting"
        ],
        "S-3": [
            "summary_financial_data", "capitalization", "ratio_of_earnings", "use_of_proceeds",
            "plan_of_distribution", "prospectus_summary"
        ],
        "S-4": [
            "summary_financial_data", "selected_financial_data", "unaudited_pro_forma",
            "comparative_per_share_data", "risk_factors", "the_merger", "the_companies"
        ],
        "S-8": [
            "employee_benefit_plan", "interests_of_named_experts", "plan_information"
        ],
        "S-11": [
            "summary_financial_data", "selected_financial_data", "distribution_policy",
            "dilution", "capitalization", "prior_performance"
        ],
        "F-1": [
            "summary_financial_data", "capitalization", "dilution", "financial_statements", 
            "exchange_rates", "enforceability_of_civil_liabilities"
        ],
        "F-3": [
            "summary_financial_data", "capitalization", "ratio_of_earnings", 
            "exchange_rates", "use_of_proceeds"
        ],
        "F-4": [
            "summary_financial_data", "selected_financial_data", "unaudited_pro_forma",
            "comparative_per_share_data", "exchange_rates", "the_merger"
        ],
        
        # Ownership Forms
        "3": [
            "ownershipTable", "nonDerivativeTable", "derivativeTable", "signatureTable"
        ],
        "4": [
            "ownershipTable", "nonDerivativeTable", "derivativeTable", "signatureTable"
        ],
        "5": [
            "ownershipTable", "nonDerivativeTable", "derivativeTable", "signatureTable"
        ],
        "13F": [
            "informationTable", "summaryTable", "signatureBlock"
        ],
        "13F-HR": [
            "informationTable", "coverPage", "signatureBlock"
        ],
        "13F-NT": [
            "coverPage", "signatureBlock"
        ],
        
        # Beneficial Ownership Reports
        "SC 13D": [
            "transactionTable", "ownershipTable", "signatureTable"
        ],
        "SC 13G": [
            "ownershipTable", "signatureTable"
        ],
        
        # Proxy Statements
        "DEF 14A": [
            "summary_compensation_table", "director_compensation", "outstanding_equity_awards",
            "security_ownership", "performance_graph", "audit_fees", "compensation_committee_report",
            "proposal_table", "beneficial_ownership", "executive_compensation", "option_exercises"
        ],
        "PRE 14A": [
            "summary_compensation_table", "director_compensation", "outstanding_equity_awards",
            "security_ownership", "performance_graph", "audit_fees", "compensation_committee_report"
        ],
        
        # Tender Offer Statements
        "SC TO-I": [
            "summary_term_sheet", "tender_offer_terms", "source_and_amount_of_funds"
        ],
        "SC TO-T": [
            "summary_term_sheet", "tender_offer_terms", "source_and_amount_of_funds"
        ],
        
        # Annual Reports for Employee Stock Purchase, Savings and Similar Plans
        "11-K": [
            "financial_statements", "schedule_of_assets", "schedule_of_reportable_transactions",
            "net_assets_available_for_benefits", "changes_in_net_assets"
        ],
        
        # Notifications of Late Filing
        "NT 10-K": [
            "notification_table", "explanation_narrative"
        ],
        "NT 10-Q": [
            "notification_table", "explanation_narrative"
        ],
        
        # Foreign Forms
        "6-K": [
            "financial_statements", "management_report", "financial_highlights",
            "financial_data", "press_release"
        ],
        
        # Miscellaneous
        "10-K/A": [  # Amendment to 10-K
            "consolidated_balance_sheets", "consolidated_statements_of_operations",
            "consolidated_statements_of_cash_flows", "explanation_of_amendment"
        ],
        "10-Q/A": [  # Amendment to 10-Q
            "consolidated_balance_sheets", "consolidated_statements_of_operations",
            "consolidated_statements_of_cash_flows", "explanation_of_amendment"
        ],
        "8-K/A": [  # Amendment to 8-K
            "explanation_of_amendment", "revised_disclosure"
        ],
        "424B1": [  # Prospectus
            "summary_table", "risk_factors", "use_of_proceeds", "capitalization",
            "dilution", "underwriting", "plan_of_distribution"
        ],
        "424B2": [  # Prospectus
            "summary_table", "risk_factors", "use_of_proceeds", "capitalization",
            "description_of_securities"
        ],
        "424B3": [  # Prospectus
            "summary_table", "risk_factors", "use_of_proceeds", "plan_of_distribution"
        ],
        "424B4": [  # Prospectus
            "summary_table", "risk_factors", "use_of_proceeds", "capitalization",
            "dilution", "underwriting", "plan_of_distribution"
        ],
        "424B5": [  # Prospectus
            "summary_table", "risk_factors", "use_of_proceeds", "description_of_securities"
        ],
        "PX14A6G": [  # Notice of Exempt Solicitation
            "solicitation_notice", "proposal_table", "supporting_statement"
        ],
        "DEFA14A": [  # Definitive Additional Materials
            "additional_soliciting_material", "voting_instructions"
        ],
        "DEFM14A": [  # Merger Proxy Statement
            "summary_term_sheet", "the_merger", "merger_agreement_summary",
            "comparison_of_stockholder_rights", "voting_securities"
        ],
        "DEFR14A": [  # Revised Definitive Proxy Statement
            "summary_compensation_table", "director_compensation", "outstanding_equity_awards",
            "revision_explanation"
        ],
        "N-CSR": [  # Investment Company Act Reports
            "schedule_of_investments", "statement_of_assets", "statement_of_operations",
            "financial_highlights"
        ],
        "N-PORT": [  # Monthly Portfolio Investments Report
            "general_information", "portfolio_investments", "explanatory_notes"
        ],
        "N-PX": [  # Annual Report of Proxy Voting Record
            "proxy_voting_record", "voting_summary"
        ]
    }
    
    # Common patterns for table detection in plain text
    TEXT_TABLE_PATTERNS: ClassVar[List[str]] = [
        r"^\s*[-+]{3,}\s+[-+]{3,}",  # Table with --- separator rows
        r"^\s*[|]{1}\s+.*\s+[|]{1}$",  # Table with | separators
        r"^\s*\w+\s+\d+\s+\d+\s+\d+\s+\d+",  # Financial tables with numbers
    ]

    # def __init__(self, file_path: str, output_dir: Optional[str] = None, ticker: Optional[str] = None, 
    #              log_level: Optional[int] = None, process_all_documents: bool = False,
    #              config_file: Optional[str] = None) -> None:
    #     """
    #     Initializes the EDGAR parser.

    #     Args:
    #         file_path (str): Path to the EDGAR filing txt file.
    #         output_dir (Optional[str]): Output folder. If None, generates from file_path.
    #         ticker (Optional[str]): Company ticker symbol.
    #         log_level (Optional[int]): Logging level (default from config or logging.INFO)
    #         process_all_documents (bool): If True, process all document sections regardless of type tag.
    #                                      If False, only process recognized filing types.
    #         config_file (Optional[str]): Path to configuration file (default: "config.toml" in current dir)
    #     """
    #     if not isinstance(file_path, str):
    #         raise TypeError("file_path must be a string.")
    #     if output_dir is not None and not isinstance(output_dir, str):
    #         raise TypeError("output_dir must be a string or None.")
    #     if ticker is not None and not isinstance(ticker, str):
    #         raise TypeError("ticker must be a string or None.")

    #     # Load configuration
    #     self.config = self._load_config(config_file)
        
    #     # Set up logging from config
    #     log_config = self.config.get("Logging", {})
    #     if log_level is None:
    #         log_level = log_config.get("level", logging.INFO)
        
    #     # Create logger
    #     self.logger = self._setup_logger(log_level, log_config)

    #     self.file_path: str = file_path
    #     self.output_dir: str = output_dir or str(Path(file_path).with_suffix("")) + "_parsed"
    #     self.ticker: str = ticker or Path(file_path).parent.parent.name
    #     self.tables_dir: str = os.path.join(self.output_dir, "tables")
    #     self.text_tables_dir: str = os.path.join(self.output_dir, "text_tables")
    #     self.metadata: Dict[str, Any] = {}
    #     self.process_all_documents: bool = process_all_documents
        
    #     # Create output directories
    #     os.makedirs(self.output_dir, exist_ok=True)
    #     os.makedirs(self.tables_dir, exist_ok=True)
    #     os.makedirs(self.text_tables_dir, exist_ok=True)
        
    def _load_config(self, config_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration from TOML file.
        
        Args:
            config_file (Optional[str]): Path to configuration file
            
        Returns:
            Dict[str, Any]: Configuration dictionary
        """
        config = {}
        
        # Default config file paths to try
        config_paths = [
            config_file,  # User-specified path
            "config.toml",  # Current directory
            os.path.join(os.path.dirname(__file__), "config.toml"),  # Module directory
            os.path.expanduser("~/.config/edgar_parser/config.toml")  # User config directory
        ]
        
        # Try to load from config files
        for path in config_paths:
            if path and os.path.isfile(path):
                try:
                    with open(path, "rb") as f:
                        config = tomli.load(f)
                    break
                except Exception as e:
                    # Continue to next config path on error
                    pass
                    
        return config
        
    def _setup_logger(self, log_level: int, log_config: Dict[str, Any]) -> logging.Logger:
        """
        Set up logger with configuration.
        
        Args:
            log_level (int): Logging level
            log_config (Dict[str, Any]): Logging configuration
            
        Returns:
            logging.Logger: Configured logger
        """
        logger = logging.getLogger("EdgarParser")
        logger.setLevel(log_level)
        
        # Clear existing handlers
        if logger.handlers:
            logger.handlers.clear()
            
        # Configure console handler
        if log_config.get("console_output", True):
            console_handler = logging.StreamHandler()
            console_format = log_config.get("console_format", 
                                          '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_formatter = logging.Formatter(console_format)
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
            
        # Configure file handler if enabled
        if log_config.get("file_output", False):
            log_file = log_config.get("log_file", "edgar_parser.log")
            file_handler = logging.FileHandler(log_file)
            file_format = log_config.get("file_format", 
                                       '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_formatter = logging.Formatter(file_format)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            
        return logger

    def parse(self) -> Dict[str, Any]:
        """
        Main entry point to parse an EDGAR filing txt file.
        Extracts tables and sections and saves them to output folders.
        
        Returns:
            Dict[str, Any]: Metadata about the parsed filing
        """
        self.logger.info(f"Starting parse for file: {self.file_path}")

        if not os.path.isfile(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")

        # Detect encoding and read file
        content = self._read_file_with_encoding()
        
        # Extract and save header information
        self.metadata = self._extract_header_info(content)
        self._save_metadata()
        
        documents = self._split_documents(content)
        if not documents:
            self.logger.warning("No DOCUMENT sections found in filing. Attempting to parse as single document.")
            documents = [content]  # Treat the entire content as one document

        processed_docs = 0
        for i, doc in enumerate(documents):
            self.logger.info(f"Processing document block {i+1} of {len(documents)}")
            type_tag, text_content, cik = self._extract_document_info(doc)
            
            # Update metadata with document info
            if cik and not self.metadata.get("cik"):
                self.metadata["cik"] = cik
            
            # Process document if it's a recognized filing type or if process_all_documents is True
            if self.process_all_documents or type_tag in self.FILING_TYPE_PROFILES or type_tag == "UNKNOWN":
                self.logger.info(f"Processing {type_tag} document at block {i}")
                
                # Extract tables from HTML
                tables = self._extract_tables_from_html(text_content, type_tag)
                if tables:
                    self._save_tables(tables)
                    self.logger.info(f"Saved {len(tables)} HTML tables")
                else:
                    self.logger.info("No HTML tables found")
                
                # Extract tables from plain text (as fallback)
                text_tables = self._extract_tables_from_text(text_content)
                if text_tables:
                    self._save_text_tables(text_tables)
                    self.logger.info(f"Saved {len(text_tables)} text tables")
                else:
                    self.logger.info("No text tables found")
                
                # Extract document sections
                sections = self._extract_sections_with_hierarchy(text_content, cik, self.ticker)
                if sections:
                    self._save_sections(sections)
                    self.logger.info(f"Saved {len(sections)} sections")
                else:
                    self.logger.info("No sections found")
                
                # Update metadata
                self.metadata["document_types"] = self.metadata.get("document_types", []) + [type_tag]
                self.metadata["tables_count"] = self.metadata.get("tables_count", 0) + len(tables) + len(text_tables)
                self.metadata["sections_count"] = self.metadata.get("sections_count", 0) + len(sections)
                
                processed_docs += 1
            else:
                self.logger.debug(f"Skipping document with type: {type_tag} (use process_all_documents=True to process all types)")
        
        self._save_metadata()  # Save updated metadata
        
        if processed_docs == 0:
            self.logger.warning("No documents were processed. If using selective processing, try process_all_documents=True")
        else:
            self.logger.info(f"Successfully processed {processed_docs} documents")
            self.logger.info(f"All data saved to {self.output_dir}")
            
        return self.metadata

    def _read_file_with_encoding(self) -> str:
        """
        Reads file content with proper encoding detection.
        
        Returns:
            str: File content with proper encoding
        """
        # First try to detect encoding
        with open(self.file_path, 'rb') as raw_file:
            raw_data = raw_file.read(min(1024*1024, os.path.getsize(self.file_path)))  # Read up to 1MB for detection
            result = chardet.detect(raw_data)
            encoding = result['encoding']
            confidence = result['confidence']
            
        # Try detected encoding, falling back to latin1 and utf-8 if needed
        encodings_to_try = [encoding, 'latin1', 'utf-8']
        
        for enc in encodings_to_try:
            try:
                with open(self.file_path, 'r', encoding=enc) as file:
                    content = file.read()
                self.logger.info(f"Successfully read file with {enc} encoding (confidence: {confidence if enc == encoding else 'fallback'})")
                self.metadata["detected_encoding"] = enc
                return content
            except UnicodeDecodeError:
                self.logger.warning(f"Failed to decode with {enc}, trying next encoding")
        
        # If all fail, use latin1 with error handling
        with open(self.file_path, 'r', encoding='latin1', errors='replace') as file:
            content = file.read()
        self.logger.warning("Used latin1 with error replacement as last resort")
        self.metadata["detected_encoding"] = "latin1 (with errors)"
        return content

    def _extract_header_info(self, content: str) -> Dict[str, Any]:
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
                        
        # Add file metadata
        metadata["file_path"] = self.file_path
        metadata["file_size"] = os.path.getsize(self.file_path)
        metadata["ticker"] = self.ticker
        metadata["parser_version"] = "1.1.0"
                        
        return metadata

    def _save_metadata(self) -> None:
        """Saves metadata to JSON file."""
        metadata_path = os.path.join(self.output_dir, "metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=4, ensure_ascii=False)
        self.logger.debug(f"Saved metadata to {metadata_path}")

    def _split_documents(self, file_content: str) -> List[str]:
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
        
    def _extract_tables_from_text(self, text_content: str) -> List[Tuple[str, List[List[str]]]]:
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
                        if any(re.match(pattern, lines[j]) for pattern in self.TEXT_TABLE_PATTERNS):
                            in_table = True
                            break
                    break
            
            # Check if the line matches a table pattern
            if any(re.match(pattern, line) for pattern in self.TEXT_TABLE_PATTERNS):
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
                    if cells and len(cells) >= len(current_table[0])-2:  # Allow for some variation
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
        sections = []
        heading_stack = []
        current_section = {"title": "Document Start", "level": 0, "parent_title": None, "content": ""}
        section_counter = 1
        
        try:
            soup = BeautifulSoup(html_text, "lxml")
        except Exception as e:
            self.logger.warning(f"lxml parsing failed: {e}. Falling back to html.parser")
            soup = BeautifulSoup(html_text, "html.parser")
            
        # Find all heading tags
        heading_tags = soup.find_all(["h1", "h2", "h3", "h4", "h5", "strong", "b"])
        
        # Process HTML content by headings
        for tag in heading_tags:
            # Skip empty headings
            text_content = tag.get_text(strip=True)
            if not text_content:
                continue
                
            # Determine heading level
            if tag.name.startswith('h') and len(tag.name) == 2:
                # Standard heading tags
                level = int(tag.name[1])
            elif tag.name in ['strong', 'b']:
                # Special case: <strong> or <b> might be used as section headers in older filings
                # Check if standalone or in a smaller font/paragraph context
                parent = tag.parent
                if parent and parent.name == 'p' and len(parent.get_text(strip=True)) < 100:
                    level = 3  # Treat as h3 level
                else:
                    continue  # Skip non-heading bold/strong tags
            else:
                continue
                
            # Manage heading hierarchy
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            parent_title = heading_stack[-1][1] if heading_stack else None
            heading_stack.append((level, text_content))
            
            # Save previous section if it has content
            if current_section["content"]:
                # Clean up content
                cleaned_content = self._clean_section_content(current_section["content"])
                if cleaned_content:  # Only save non-empty sections
                    current_section["content"] = cleaned_content
                    current_section.update({
                        "uuid": str(uuid.uuid4()),
                        "cik": cik,
                        "ticker": ticker,
                        "section_number": section_counter
                    })
                    sections.append(current_section)
                    section_counter += 1
                    
            # Start new section
            current_section = {
                "title": text_content,
                "level": level,
                "parent_title": parent_title,
                "content": ""
            }
            
            # Collect content until next heading
            content_elements = []
            sibling = tag.next_sibling
            while sibling:
                if sibling.name in ["h1", "h2", "h3", "h4", "h5"]:
                    break
                if hasattr(sibling, 'get_text'):
                    content_elements.append(sibling.get_text(separator=" ", strip=True))
                elif isinstance(sibling, str) and sibling.strip():
                    content_elements.append(sibling.strip())
                sibling = sibling.next_sibling
                
            current_section["content"] = " ".join(content_elements)
            
        # Save the last section
        if current_section["content"]:
            cleaned_content = self._clean_section_content(current_section["content"])
            if cleaned_content:
                current_section["content"] = cleaned_content
                current_section.update({
                    "uuid": str(uuid.uuid4()),
                    "cik": cik,
                    "ticker": ticker,
                    "section_number": section_counter
                })
                sections.append(current_section)
                
        # If we couldn't extract sections by headings, try fallback approach
        if not sections:
            self.logger.info("No sections found using headings. Trying fallback approach.")
            sections = self._extract_sections_fallback(soup, cik, ticker)
            
        return sections
        
    def _clean_section_content(self, content: str) -> str:
        """
        Cleans section content by removing extra whitespace and normalizing text.
        
        Args:
            content (str): Raw section content
            
        Returns:
            str: Cleaned content
        """
        # Remove extra whitespace and normalize
        cleaned = re.sub(r'\s+', ' ', content).strip()
        
        # Remove common noise patterns
        noise_patterns = [
            r'\[\w+ Top\]',  # Navigation markers
            r'\[Table of Contents\]',
            r'\[Data_Table_start\].*?\[Data_Table_end\]',  # Table markers
            r'Click here to view',  # Interactive elements
        ]
        
        for pattern in noise_patterns:
            cleaned = re.sub(pattern, '', cleaned)
            
        return cleaned
        
    def _extract_sections_fallback(self, soup: BeautifulSoup, cik: Optional[str], ticker: Optional[str]) -> List[Dict[str, str]]:
        """
        Fallback method to extract sections when heading-based extraction fails.
        Uses large paragraphs and divs as section boundaries.
        
        Args:
            soup (BeautifulSoup): HTML soup object
            cik (Optional[str]): Company CIK
            ticker (Optional[str]): Company ticker
            
        Returns:
            List[Dict[str, str]]: Extracted sections
        """
        sections = []
        section_counter = 1
        
        # Look for common section indicators
        section_indicators = [
            "Item 1.", "Item 1A.", "Item 1B.", "Item 2.", "Item 3.", "Item 4.",
            "Item 5.", "Item 6.", "Item 7.", "Item 7A.", "Item 8.", "Item 9.",
            "Item 9A.", "Item 9B.", "Item 10.", "Item 11.", "Item 12.", "Item 13.",
            "Item 14.", "Item 15.",
            "PART I", "PART II", "PART III", "PART IV"
        ]
        
        # First try to find sections by "Item X" patterns (common in 10-K/10-Q)
        for indicator in section_indicators:
            elements = soup.find_all(text=re.compile(rf"{re.escape(indicator)}\s"))
            
            for element in elements:
                parent = element.parent
                if not parent:
                    continue
                    
                title = None
                content = []
                
                # Get the title - either the element itself or its parent's text
                if len(element.strip()) < 100:
                    title = element.strip()
                elif parent and len(parent.get_text(strip=True)) < 100:
                    title = parent.get_text(strip=True)
                    
                if not title:
                    continue
                    
                # Find content - all elements until the next section indicator
                next_elem = parent.next_sibling
                while next_elem:
                    # Stop if we hit another section indicator
                    if hasattr(next_elem, 'get_text'):
                        elem_text = next_elem.get_text(strip=True)
                        if any(ind in elem_text for ind in section_indicators):
                            break
                        content.append(elem_text)
                    elif isinstance(next_elem, str) and next_elem.strip():
                        if any(ind in next_elem for ind in section_indicators):
                            break
                        content.append(next_elem.strip())
                    next_elem = next_elem.next_sibling
                    
                if title and content:
                    content_text = " ".join(content)
                    cleaned_content = self._clean_section_content(content_text)
                    if cleaned_content:
                        sections.append({
                            "title": title,
                            "level": 1 if title.startswith("PART") else 2,
                            "parent_title": None,
                            "content": cleaned_content,
                            "uuid": str(uuid.uuid4()),
                            "cik": cik,
                            "ticker": ticker,
                            "section_number": section_counter
                        })
                        section_counter += 1
        
        # If still no sections, try dividing by large paragraphs
        if not sections:
            # Find all paragraphs
            paragraphs = soup.find_all('p')
            
            # Group into potential sections
            current_section = {
                "title": "Document Content",
                "level": 1,
                "parent_title": None,
                "content": ""
            }
            
            for p in paragraphs:
                text = p.get_text(strip=True)
                if not text:
                    continue
                    
                # If paragraph is short, it might be a heading
                if len(text) < 100 and text.isupper():
                    # Save previous section if it has content
                    if current_section["content"]:
                        cleaned_content = self._clean_section_content(current_section["content"])
                        if cleaned_content:
                            current_section.update({
                                "content": cleaned_content,
                                "uuid": str(uuid.uuid4()),
                                "cik": cik,
                                "ticker": ticker,
                                "section_number": section_counter
                            })
                            sections.append(current_section)
                            section_counter += 1
                            
                        # Start new section
                        current_section = {
                            "title": text,
                            "level": 1,
                            "parent_title": None,
                            "content": ""
                        }
                else:
                    # Add to current section content
                    current_section["content"] += " " + text
                    
            # Save last section
            if current_section["content"]:
                cleaned_content = self._clean_section_content(current_section["content"])
                if cleaned_content:
                    current_section.update({
                        "content": cleaned_content,
                        "uuid": str(uuid.uuid4()),
                        "cik": cik,
                        "ticker": ticker,
                        "section_number": section_counter
                    })
                    sections.append(current_section)
                    
        return sections
    
    @classmethod
    def batch_process(cls, input_dir: str, output_base_dir: Optional[str] = None, 
                  ticker_map: Optional[Dict[str, str]] = None, max_workers: int = 4,
                  process_all_documents: bool = False, config_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Process multiple filings in a directory.

        Args:
            input_dir (str): Directory containing filing files
            output_base_dir (Optional[str]): Base directory for output
            ticker_map (Optional[Dict[str, str]]): Map of folder names to ticker symbols
            max_workers (int): Maximum number of concurrent workers
            process_all_documents (bool): If True, process all document sections in each filing
            config_file (Optional[str]): Path to configuration file

        Returns:
            Dict[str, Any]: Summary of processing results
        """
        if not os.path.isdir(input_dir):
            raise ValueError(f"Input directory does not exist: {input_dir}")
            
        if output_base_dir is None:
            output_base_dir = os.path.join(input_dir, "parsed_filings")
            
        os.makedirs(output_base_dir, exist_ok=True)
        
        # Load configuration
        config = {}
        if config_file and os.path.isfile(config_file):
            try:
                with open(config_file, "rb") as f:
                    config = tomli.load(f)
            except Exception as e:
                pass
        
        # Get batch processing settings from config
        batch_config = config.get("BatchProcessing", {})
        if "max_workers" not in batch_config:
            batch_config["max_workers"] = max_workers
            
        # Set up logging for batch processor
        log_config = config.get("Logging", {})
        logger = logging.getLogger("EdgarBatchProcessor")
        logger.setLevel(log_config.get("level", logging.INFO))
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(log_config.get("console_format",
                                                      '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
            # Add file logging if configured
            if log_config.get("file_output", False):
                log_file = log_config.get("log_file", "edgar_batch.log")
                file_handler = logging.FileHandler(log_file)
                file_formatter = logging.Formatter(log_config.get("file_format",
                                                              '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
                file_handler.setFormatter(file_formatter)
                logger.addHandler(file_handler)
        
        # Find all txt files in the input directory and subdirectories
        all_files = []
        for root, _, files in os.walk(input_dir):
            for file in files:
                if file.endswith('.txt'):
                    all_files.append(os.path.join(root, file))
                    
        if not all_files:
            raise ValueError(f"No .txt files found in {input_dir}")
            
        logger.info(f"Found {len(all_files)} text files to process")
        logger.info(f"Process all documents: {process_all_documents}")
        logger.info(f"Using {batch_config['max_workers']} worker threads")
        
        results = {
            "total_files": len(all_files),
            "successful": 0,
            "failed": 0,
            "files": []
        }
        
        # Function to process one file
        def process_file(file_path: str) -> Dict[str, Any]:
            rel_path = os.path.relpath(file_path, input_dir)
            parent_dir = os.path.dirname(os.path.dirname(file_path))
            dir_name = os.path.basename(parent_dir)
            
            # Determine ticker
            ticker = None
            if ticker_map and dir_name in ticker_map:
                ticker = ticker_map[dir_name]
                
            # Determine output directory
            rel_output_dir = os.path.dirname(rel_path)
            output_dir = os.path.join(output_base_dir, rel_output_dir, 
                                      os.path.splitext(os.path.basename(file_path))[0] + "_parsed")
                
            file_result = {
                "file": file_path,
                "ticker": ticker,
                "status": "unknown",
                "error": None
            }
            
            try:
                parser = cls(file_path, output_dir, ticker, log_level=logging.WARNING, 
                            process_all_documents=process_all_documents, config_file=config_file)
                metadata = parser.parse()
                file_result["status"] = "success"
                file_result["metadata"] = metadata
                logger.info(f"Successfully processed: {file_path}")
                return file_result
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                file_result["status"] = "failed"
                file_result["error"] = str(e)
                return file_result
        
        # Process files with ThreadPoolExecutor
        actual_max_workers = min(batch_config["max_workers"], len(all_files))
        with ThreadPoolExecutor(max_workers=actual_max_workers) as executor:
            file_results = list(executor.map(process_file, all_files))
            
        # Compile results
        for result in file_results:
            results["files"].append(result)
            if result["status"] == "success":
                results["successful"] += 1
            else:
                results["failed"] += 1
                
        # Save summary
        summary_path = os.path.join(output_base_dir, "processing_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4)
            
        logger.info(f"Batch processing complete. Processed {results['total_files']} files: "
                   f"{results['successful']} successful, {results['failed']} failed.")
        logger.info(f"Summary saved to {summary_path}")
        
        return results
    
    def _setup_logger(self, log_level: int, log_config: Dict[str, Any]) -> logging.Logger:
        """
        Set up logger with configuration.
        
        Args:
            log_level (int): Logging level
            log_config (Dict[str, Any]): Logging configuration
            
        Returns:
            logging.Logger: Configured logger
        """
        logger = logging.getLogger("EdgarParser")
        logger.setLevel(log_level)
        
        # Clear existing handlers
        if logger.handlers:
            logger.handlers.clear()
            
        # Configure console handler
        if log_config.get("console_output", True):
            console_handler = logging.StreamHandler()
            console_format = log_config.get("console_format", 
                                        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_formatter = logging.Formatter(console_format)
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
            
        # Configure file handler if enabled
        if log_config.get("file_output", False):
            log_file = log_config.get("log_file", "edgar_parser.log")
            file_handler = logging.FileHandler(log_file)
            file_format = log_config.get("file_format", 
                                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_formatter = logging.Formatter(file_format)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            
        return logger

    def _load_config(self, config_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration from TOML file.
        
        Args:
            config_file (Optional[str]): Path to configuration file
            
        Returns:
            Dict[str, Any]: Configuration dictionary
        """
        config = {}
        
        # Default config file paths to try
        config_paths = [
            config_file,  # User-specified path
            "config.toml",  # Current directory
            os.path.join(os.path.dirname(__file__), "config.toml"),  # Module directory
            os.path.expanduser("~/.config/edgar_parser/config.toml")  # User config directory
        ]
        
        # Try to load from config files
        for path in config_paths:
            if path and os.path.isfile(path):
                try:
                    with open(path, "rb") as f:
                        config = tomli.load(f)
                    break
                except Exception as e:
                    # Continue to next config path on error
                    pass
                    
        return config


    def __init__(self, file_path: str, output_dir: Optional[str] = None, ticker: Optional[str] = None, 
                log_level: Optional[int] = None, process_all_documents: bool = False,
                config_file: Optional[str] = None) -> None:
        """
        Initializes the EDGAR parser.

        Args:
            file_path (str): Path to the EDGAR filing txt file.
            output_dir (Optional[str]): Output folder. If None, generates from file_path.
            ticker (Optional[str]): Company ticker symbol.
            log_level (Optional[int]): Logging level (default from config or logging.INFO)
            process_all_documents (bool): If True, process all document sections regardless of type tag.
                                        If False, only process recognized filing types.
            config_file (Optional[str]): Path to configuration file (default: "config.toml" in current dir)
        """
        if not isinstance(file_path, str):
            raise TypeError("file_path must be a string.")
        if output_dir is not None and not isinstance(output_dir, str):
            raise TypeError("output_dir must be a string or None.")
        if ticker is not None and not isinstance(ticker, str):
            raise TypeError("ticker must be a string or None.")

        # Load configuration
        self.config = self._load_config(config_file)
        
        # Set up logging from config
        log_config = self.config.get("Logging", {})
        if log_level is None:
            log_level = log_config.get("level", logging.INFO)
        
        # Create logger
        self.logger = self._setup_logger(log_level, log_config)

        self.file_path: str = file_path
        self.output_dir: str = output_dir or str(Path(file_path).with_suffix("")) + "_parsed"
        self.ticker: str = ticker or Path(file_path).parent.parent.name
        self.tables_dir: str = os.path.join(self.output_dir, "tables")
        self.text_tables_dir: str = os.path.join(self.output_dir, "text_tables")
        self.metadata: Dict[str, Any] = {}
        self.process_all_documents: bool = process_all_documents
        
        # Create output directories
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.tables_dir, exist_ok=True)
        os.makedirs(self.text_tables_dir, exist_ok=True)

# Command-line interface section
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="EDGAR Filing Text Parser")
    parser.add_argument("--file", help="Path to EDGAR filing txt file")
    parser.add_argument("--dir", help="Directory containing multiple filings")
    parser.add_argument("--output", help="Output directory")
    parser.add_argument("--ticker", help="Company ticker symbol")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers for batch processing")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--process-all", action="store_true", help="Process all document sections regardless of type")
    parser.add_argument("--config", help="Path to configuration file")
    
    args = parser.parse_args()
    
    log_level = logging.DEBUG if args.verbose else logging.INFO
    
    if args.file:
        # Single file mode
        file_parser = EdgarParser(args.file, args.output, args.ticker, log_level=log_level, 
                                 process_all_documents=args.process_all, config_file=args.config)
        file_parser.parse()
    elif args.dir:
        # Batch mode
        EdgarParser.batch_process(
            args.dir, 
            args.output, 
            max_workers=args.workers,
            process_all_documents=args.process_all,
            config_file=args.config
        )
    else:
        parser.print_help()