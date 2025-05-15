"""
EDGAR Full-Text Filing Parser

Main module that coordinates the parsing of SEC EDGAR filings.
Uses the ConfigManager and LoggingManager for centralized configuration.

Version: 1.3.0
Author: Horia & Matilda
Enhanced by: Claude
"""

from typing import List, Dict, Any, Optional, ClassVar, Tuple
import os
import json
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Import from local modules
from app_utils import ConfigManager, LoggingManager
from edgar_parser.document import DocumentParser
from edgar_parser.tables import TableExtractor
from edgar_parser.sections import SectionExtractor
from edgar_parser.utils import read_file_with_encoding


class EdgarParser:
    """
    EDGAR Full-Text Filing Parser

    Parses SEC EDGAR full-text filing (.txt) documents.
    Extracts tables and document sections with hierarchy.
    Saves structured data to output folders.
    """

    def __init__(self, file_path: str, output_dir: Optional[str] = None, ticker: Optional[str] = None, 
                 log_level: Optional[int] = None, process_all_documents: Optional[bool] = None,
                 config_file: Optional[str] = None) -> None:
        """
        Initializes the EDGAR parser.

        Args:
            file_path (str): Path to the EDGAR filing txt file.
            output_dir (Optional[str]): Output folder. If None, generates from file_path.
            ticker (Optional[str]): Company ticker symbol.
            log_level (Optional[int]): Logging level (default from config)
            process_all_documents (Optional[bool]): If True, process all document sections regardless of type tag.
                                                  If False, only process recognized filing types.
            config_file (Optional[str]): Path to configuration file
        """
        if not isinstance(file_path, str):
            raise TypeError("file_path must be a string.")
        if output_dir is not None and not isinstance(output_dir, str):
            raise TypeError("output_dir must be a string or None.")
        if ticker is not None and not isinstance(ticker, str):
            raise TypeError("ticker must be a string or None.")

        # Load configuration using ConfigManager
        self.config = ConfigManager.get_config(config_file)
        
        # Set up logging using LoggingManager
        self.logger = LoggingManager.get_logger("EdgarParser", self.config, log_level)
        
        # Get parser settings from config
        parser_config = self.config.get("EdgarParser", {})
        
        self.file_path: str = file_path
        self.output_dir: str = output_dir or str(Path(file_path).with_suffix("")) + "_parsed"
        self.ticker: str = ticker or parser_config.get("default_ticker", "UNKNOWN")
        
        # Use parent directory name as ticker if available and no ticker specified
        if self.ticker == "UNKNOWN" and ticker is None:
            parent_dir = Path(file_path).parent.parent.name
            if parent_dir and not parent_dir.startswith("."):
                self.ticker = parent_dir
        
        # Set up directories
        self.tables_dir: str = os.path.join(self.output_dir, "tables")
        self.text_tables_dir: str = os.path.join(self.output_dir, "text_tables")
        self.sections_dir: str = os.path.join(self.output_dir, "sections")
        
        # Default to config value if not provided
        self.process_all_documents: bool = process_all_documents if process_all_documents is not None else \
                                          parser_config.get("process_all_documents", False)
        
        # Additional configuration
        self.batch_config = parser_config.get("BatchProcessing", {})
        self.table_config = parser_config.get("TableProcessing", {})
        
        # Create output directories
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.tables_dir, exist_ok=True)
        os.makedirs(self.text_tables_dir, exist_ok=True)
        os.makedirs(self.sections_dir, exist_ok=True)
        
        # Initialize metadata
        self.metadata: Dict[str, Any] = {}
        
        # Set up parsers
        self.document_parser = DocumentParser(self.config, self.logger)
        self.table_extractor = TableExtractor(self.config, self.logger)
        self.section_extractor = SectionExtractor(self.config, self.logger)
        
        self.logger.info(f"Initialized parser for {file_path} with ticker {self.ticker}")

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
        content, encoding = read_file_with_encoding(self.file_path, self.logger)
        
        # Extract and save header information
        self.metadata = self.document_parser.extract_header_info(content)
        self.metadata["detected_encoding"] = encoding
        self.metadata["file_path"] = self.file_path
        self.metadata["file_size"] = os.path.getsize(self.file_path)
        self.metadata["ticker"] = self.ticker
        self.metadata["parser_version"] = "1.3.0"
        self._save_metadata()
        
        # Split the document into <DOCUMENT> blocks
        documents = self.document_parser.split_documents(content)
        if not documents:
            self.logger.warning("No DOCUMENT sections found in filing. Attempting to parse as single document.")
            documents = [content]  # Treat the entire content as one document

        processed_docs = 0
        for i, doc in enumerate(documents):
            self.logger.info(f"Processing document block {i+1} of {len(documents)}")
            type_tag, text_content, cik = self.document_parser.extract_document_info(doc)
            
            # Update metadata with document info
            if cik and not self.metadata.get("cik"):
                self.metadata["cik"] = cik
            
            # Process document if it's a recognized filing type or if process_all_documents is True
            filing_profiles = self.config.get("EdgarParser", {}).get("FilingTypeProfiles", {})
            recognized_types = [k for k in filing_profiles.keys()]
            
            if self.process_all_documents or type_tag in recognized_types or type_tag == "UNKNOWN":
                self.logger.info(f"Processing {type_tag} document at block {i}")
                
                # Extract tables from HTML
                tables = self.table_extractor.extract_tables_from_html(text_content, type_tag)
                if tables:
                    self._save_tables(tables)
                    self.logger.info(f"Saved {len(tables)} HTML tables")
                else:
                    self.logger.info("No HTML tables found")
                
                # Extract tables from plain text (as fallback)
                text_tables = self.table_extractor.extract_tables_from_text(text_content)
                if text_tables:
                    self._save_text_tables(text_tables)
                    self.logger.info(f"Saved {len(text_tables)} text tables")
                else:
                    self.logger.info("No text tables found")
                
                # Extract document sections
                sections = self.section_extractor.extract_sections_with_hierarchy(text_content, cik, self.ticker)
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
    
    def _save_metadata(self) -> None:
        """Saves metadata to JSON file."""
        metadata_path = os.path.join(self.output_dir, "metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=4, ensure_ascii=False)
        self.logger.debug(f"Saved metadata to {metadata_path}")

    def _save_tables(self, tables: List[Tuple[Optional[str], List[List[str]]]]) -> None:
        """
        Saves extracted HTML tables to CSV files.
        
        Args:
            tables (List[Tuple[Optional[str], List[List[str]]]]): List of (table_name, table_data) tuples
        """
        import pandas as pd
        
        for i, (table_name, table_data) in enumerate(tables):
            if not table_data:
                continue
                
            # Clean up table name for filename
            safe_name = "".join(c if c.isalnum() or c in ['-', '_'] else '_' for c in str(table_name))
            safe_name = safe_name[:50]  # Limit filename length
            
            # Create filename
            filename = f"{safe_name}_{i+1}.csv" if safe_name else f"table_{i+1}.csv"
            filepath = os.path.join(self.tables_dir, filename)
            
            # Convert to DataFrame and save
            try:
                df = pd.DataFrame(table_data)
                # Use first row as header if it seems like a header row
                if len(df) > 1:
                    headers = df.iloc[0]
                    if not all(pd.to_numeric(headers, errors='coerce').notna()):
                        df = pd.DataFrame(table_data[1:], columns=headers)
                        
                df.to_csv(filepath, index=False)
                self.logger.debug(f"Saved table to {filepath}")
            except Exception as e:
                self.logger.error(f"Error saving table {filename}: {e}")

    def _save_text_tables(self, tables: List[Tuple[str, List[List[str]]]]) -> None:
        """
        Saves extracted text tables to CSV files.
        
        Args:
            tables (List[Tuple[str, List[List[str]]]]): List of (table_name, table_data) tuples
        """
        import pandas as pd
        
        for i, (table_name, table_data) in enumerate(tables):
            if not table_data:
                continue
                
            # Clean up table name for filename
            safe_name = "".join(c if c.isalnum() or c in ['-', '_'] else '_' for c in str(table_name))
            safe_name = safe_name[:50]  # Limit filename length
            
            # Create filename
            filename = f"{safe_name}_{i+1}.csv" if safe_name else f"text_table_{i+1}.csv"
            filepath = os.path.join(self.text_tables_dir, filename)
            
            # Convert to DataFrame and save
            try:
                df = pd.DataFrame(table_data)
                df.to_csv(filepath, index=False)
                self.logger.debug(f"Saved text table to {filepath}")
            except Exception as e:
                self.logger.error(f"Error saving text table {filename}: {e}")

    def _save_sections(self, sections: List[Dict[str, Any]]) -> None:
        """
        Saves extracted document sections to JSON files.
        
        Args:
            sections (List[Dict[str, Any]]): List of section dictionaries
        """
        # Write all sections to one JSON file
        all_sections_path = os.path.join(self.sections_dir, "all_sections.json")
        with open(all_sections_path, "w", encoding="utf-8") as f:
            json.dump(sections, f, indent=4, ensure_ascii=False)
            
        # Also write each section to individual files
        for section in sections:
            if "uuid" in section:
                filename = f"section_{section['uuid']}.json"
                filepath = os.path.join(self.sections_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(section, f, indent=4, ensure_ascii=False)
        
        self.logger.debug(f"Saved {len(sections)} sections to {self.sections_dir}")

    @classmethod
    def batch_process(cls, input_dir: str, output_base_dir: Optional[str] = None, 
                      ticker_map: Optional[Dict[str, str]] = None, max_workers: Optional[int] = None,
                      process_all_documents: Optional[bool] = None, config_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Process multiple filings in a directory.

        Args:
            input_dir (str): Directory containing filing files
            output_base_dir (Optional[str]): Base directory for output
            ticker_map (Optional[Dict[str, str]]): Map of folder names to ticker symbols
            max_workers (Optional[int]): Maximum number of concurrent workers
            process_all_documents (Optional[bool]): If True, process all document sections in each filing
            config_file (Optional[str]): Path to configuration file

        Returns:
            Dict[str, Any]: Summary of processing results
        """
        if not os.path.isdir(input_dir):
            raise ValueError(f"Input directory does not exist: {input_dir}")
            
        if output_base_dir is None:
            output_base_dir = os.path.join(input_dir, "parsed_filings")
            
        os.makedirs(output_base_dir, exist_ok=True)
        
        # Load configuration using ConfigManager
        config = ConfigManager.get_config(config_file)
        
        # Get batch processing settings from config
        batch_config = config.get("EdgarParser", {}).get("BatchProcessing", {})
        if max_workers is None:
            max_workers = batch_config.get("max_workers", 4)
            
        # Get process_all_documents setting from config if not provided
        parser_config = config.get("EdgarParser", {})
        if process_all_documents is None:
            process_all_documents = parser_config.get("process_all_documents", False)
            
        # Set up logging for batch processor
        logger = LoggingManager.get_logger("EdgarBatchProcessor", config)
        
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
        logger.info(f"Using {max_workers} worker threads")
        
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
        actual_max_workers = min(max_workers, len(all_files))
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


# Command-line interface section
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="EDGAR Filing Text Parser")
    parser.add_argument("--file", help="Path to EDGAR filing txt file")
    parser.add_argument("--dir", help="Directory containing multiple filings")
    parser.add_argument("--output", help="Output directory")
    parser.add_argument("--ticker", help="Company ticker symbol")
    parser.add_argument("--workers", type=int, help="Number of parallel workers for batch processing")
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
