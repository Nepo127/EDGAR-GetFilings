"""
EDGAR Parser Package

A modular parser for SEC EDGAR filings that extracts tables, sections, and metadata.
"""

from .parser import EdgarParser

__version__ = "1.3.0"
__author__ = "Horia & Matilda, Enhanced by Claude"

def main():
    """Command-line entry point"""
    import sys
    import argparse
    import logging
    
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
        sys.exit(1)
    
    sys.exit(0)
    
# Export main components for easy imports
from .document import DocumentParser
from .tables import TableExtractor
from .sections import SectionExtractor
from .utils import read_file_with_encoding, clean_filename, ensure_dir, get_filing_type_sections
