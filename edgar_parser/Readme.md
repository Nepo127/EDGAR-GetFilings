# EDGAR Parser

A tool for parsing SEC EDGAR full-text filing (.txt) documents, extracting tables, sections, and metadata.

## Structure

The EDGAR Parser has been restructured into modular components:

- `edgar_parser.py`: Main module that coordinates parsing and provides the CLI interface
- `edgar_parser_document.py`: Handles document parsing and header extraction
- `edgar_parser_tables.py`: Extracts tables from HTML and plain text
- `edgar_parser_sections.py`: Extracts document sections with hierarchical structure
- `edgar_parser_utils.py`: Utility functions shared across modules
- `config_manager.py`: Centralized configuration management
- `logger_manager.py`: Centralized logging configuration

## Configuration

The parser uses a TOML configuration file (`config.toml`) with sections for:

- `Logging`: Controls logging behavior
- `EdgarParser`: Main parser settings
  - `BatchProcessing`: Settings for batch processing
  - `TableProcessing`: Table extraction settings
  - `TextTablePatterns`: Patterns for detecting text tables
  - `FilingTypeProfiles`: Filing-type specific section identifiers

## Usage

### Command Line Interface

```bash
# Parse a single file
python edgar_parser.py --file path/to/filing.txt --output output_dir --ticker AAPL

# Process a directory of filings
python edgar_parser.py --dir path/to/filings_dir --output output_base_dir --workers 8

# Enable verbose logging
python edgar_parser.py --file path/to/filing.txt --verbose

# Process all document sections regardless of type
python edgar_parser.py --file path/to/filing.txt --process-all

# Specify a custom configuration file
python edgar_parser.py --file path/to/filing.txt --config path/to/custom_config.toml
```

### Python API

```python
from edgar_parser import EdgarParser

# Parse a single file
parser = EdgarParser(
    file_path="path/to/filing.txt", 
    output_dir="output_dir", 
    ticker="AAPL",
    process_all_documents=True,
    config_file="path/to/config.toml"
)
metadata = parser.parse()

# Batch process multiple filings
results = EdgarParser.batch_process(
    input_dir="path/to/filings_dir",
    output_base_dir="output_base_dir",
    max_workers=8,
    process_all_documents=True,
    config_file="path/to/config.toml"
)
```

## Output Structure

For each processed filing, the parser creates:

- `metadata.json`: Contains filing metadata and processing statistics
- `tables/`: Directory containing CSV files of extracted HTML tables
- `text_tables/`: Directory containing CSV files of tables extracted from plain text
- `sections/`: Directory containing JSON files of document sections

## Dependencies

- Beautiful Soup 4 (with lxml parser): HTML parsing
- pandas: Table operations
- chardet: Character encoding detection
- tomli: TOML configuration parsing

## Extended Configuration

The parser behavior can be customized through the `config.toml` file:

```toml
[EdgarParser]
process_all_documents = false
default_ticker = "UNKNOWN"

[EdgarParser.BatchProcessing]
max_workers = 4
memory_optimize = true
chunk_size = 1048576  # 1MB in bytes

[EdgarParser.TableProcessing]
extract_html_tables = true
extract_text_tables = true
max_tables_per_document = 100

[EdgarParser.TextTablePatterns]
patterns = [
    "^\\s*[-+]{3,}\\s+[-+]{3,}",
    "^\\s*[|]{1}\\s+.*\\s+[|]{1}$",
    "^\\s*\\w+\\s+\\d+\\s+\\d+\\s+\\d+\\s+\\d+"
]

[Logging]
level = "INFO"
console_output = true
file_output = false
log_file = "edgar_parser.log"
```

## Filing Types

The parser is configured to recognize and process various SEC filing types, including:
- Annual Reports (10-K)
- Quarterly Reports (10-Q)
- Current Reports (8-K)
- Registration Statements (S-1, S-3, etc.)
- Proxy Statements (DEF 14A)
- And many others as defined in the configuration
