"""
Example usage of the EDGAR Parser

This script demonstrates how to use the EDGAR Parser to process SEC filings.
"""

import os
import pandas as pd
from edgar_parser import EdgarParser

def example_parse_single_file():
    """Example of parsing a single EDGAR filing."""
    
    # Path to an EDGAR filing text file
    file_path = "path/to/your/filing.txt"
    
    # Create a parser instance
    parser = EdgarParser(
        file_path=file_path, 
        ticker="AAPL",  # Optional: Company ticker symbol
        process_all_documents=True  # Process all document sections regardless of type
    )
    
    # Parse the file
    metadata = parser.parse()
    
    print(f"Processing complete. File: {file_path}")
    print(f"Form type: {metadata.get('form_type', 'UNKNOWN')}")
    print(f"Filing date: {metadata.get('filed_as_of_date', 'UNKNOWN')}")
    print(f"Tables extracted: {metadata.get('tables_count', 0)}")
    print(f"Sections extracted: {metadata.get('sections_count', 0)}")
    
    # Demonstrate accessing the extracted data
    output_dir = parser.output_dir
    
    # List extracted tables
    tables_dir = os.path.join(output_dir, "tables")
    if os.path.exists(tables_dir):
        print("\nExtracted tables:")
        for table_file in os.listdir(tables_dir):
            table_path = os.path.join(tables_dir, table_file)
            # Read the table to display the shape
            df = pd.read_csv(table_path)
            print(f"  - {table_file}: {df.shape[0]} rows x {df.shape[1]} columns")
    
    # List extracted sections
    sections_dir = os.path.join(output_dir, "sections")
    if os.path.exists(sections_dir):
        all_sections_path = os.path.join(sections_dir, "all_sections.json")
        if os.path.exists(all_sections_path):
            import json
            with open(all_sections_path, "r", encoding="utf-8") as f:
                sections = json.load(f)
            print("\nExtracted sections:")
            for section in sections:
                title = section.get("title", "Untitled")
                level = section.get("level", 0)
                content_preview = section.get("content", "")[:50] + "..." if section.get("content") else ""
                print(f"  - {'  ' * (level-1)}{title}: {content_preview}")


def example_batch_processing():
    """Example of batch processing multiple EDGAR filings."""
    
    # Directory containing multiple EDGAR filing text files
    input_dir = "path/to/filings_directory"
    
    # Output directory for processed files
    output_dir = "path/to/output_directory"
    
    # Ticker mapping (optional)
    ticker_map = {
        "apple_inc": "AAPL",
        "microsoft_corp": "MSFT",
        "amazon_com_inc": "AMZN"
    }
    
    # Process all files in the directory
    results = EdgarParser.batch_process(
        input_dir=input_dir,
        output_base_dir=output_dir,
        ticker_map=ticker_map,
        max_workers=4,  # Number of parallel processes
        process_all_documents=True  # Process all document sections
    )
    
    print(f"Batch processing complete!")
    print(f"Total files processed: {results['total_files']}")
    print(f"Successfully processed: {results['successful']}")
    print(f"Failed: {results['failed']}")
    
    # Process results for each file
    if results['successful'] > 0:
        print("\nSuccessfully processed files:")
        for file_result in results['files']:
            if file_result['status'] == 'success':
                file_name = os.path.basename(file_result['file'])
                ticker = file_result['ticker']
                metadata = file_result.get('metadata', {})
                form_type = metadata.get('form_type', 'UNKNOWN')
                tables_count = metadata.get('tables_count', 0)
                
                print(f"  - {file_name} ({ticker}, {form_type}): {tables_count} tables extracted")


if __name__ == "__main__":
    print("EDGAR Parser Examples")
    print("=====================\n")
    
    print("Example 1: Parse Single File")
    print("--------------------------")
    # Uncomment to run the example
    # example_parse_single_file()
    
    print("\nExample 2: Batch Processing")
    print("-------------------------")
    # Uncomment to run the example
    # example_batch_processing()
    
    print("\nTo run the examples, edit this file to point to your EDGAR filings and uncomment the example function calls.")
