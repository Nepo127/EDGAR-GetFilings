# EDGAR Filing Text Parser

A robust and versatile tool for parsing SEC EDGAR filings in text format, designed to handle pre-XBRL era filings.

![Version](https://img.shields.io/badge/version-1.2.0-blue)
![Python](https://img.shields.io/badge/python-3.6%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- Parses SEC EDGAR filings in traditional text format (.txt)
- Extracts HTML tables and plain text tables
- Identifies document sections with hierarchical structure
- Handles different filing types (10-K, 10-Q, Form 4, etc.)
- Includes smart encoding detection for older filings
- Supports batch processing for multiple files
- Detailed logging and error handling
- Robust fallback mechanisms for non-standard filings
- Configuration file support for customizing behavior

## Requirements

```
Python 3.6+
beautifulsoup4
lxml
pandas
chardet
tomli (Python <3.11) or tomllib (Python 3.11+)
```

## Installation

1. Clone this repository or download the source files.
2. Install the required dependencies:

```bash
pip install beautifulsoup4 lxml pandas chardet tomli
```

## Command Line Interface

The parser can be used as a command-line tool:

```bash
# Parse a single filing
python edgar_parser.py --file /path/to/filing.txt --ticker AAPL

# Parse a single filing and process ALL document sections (including exhibits)
python edgar_parser.py --file /path/to/filing.txt --process-all

# Process a directory of filings
python edgar_parser.py --dir /path/to/filings/directory --output /path/to/output --workers 8

# Process a directory with all document sections and verbose logging
python edgar_parser.py --dir /path/to/filings/directory --process-all --verbose

# Use a custom configuration file
python edgar_parser.py --file /path/to/filing.txt --config /path/to/config.toml
```

## Usage as a Library

```python
from edgar_parser import EdgarParser

# Parse a single filing (only recognized document types)
parser = EdgarParser(
    file_path="/path/to/filing.txt",
    output_dir="/path/to/output",
    ticker="AAPL"
)
metadata = parser.parse()

# Parse a single filing (ALL document sections)
parser = EdgarParser(
    file_path="/path/to/filing.txt",
    output_dir="/path/to/output",
    ticker="AAPL",
    process_all_documents=True  # Process all document sections
)
metadata = parser.parse()

# Use a custom configuration file
parser = EdgarParser(
    file_path="/path/to/filing.txt",
    output_dir="/path/to/output",
    config_file="/path/to/config.toml"
)

# Batch process a directory
results = EdgarParser.batch_process(
    input_dir="/path/to/filings/directory",
    output_base_dir="/path/to/output",
    max_workers=4,
    process_all_documents=True,  # Optional: process all document sections
    config_file="/path/to/config.toml"  # Optional: custom configuration
)
```

## Output Structure

For each processed filing, the following structure is created:

```
output_dir/
├── metadata.json               # Filing metadata
├── sections.json               # All extracted sections
├── sections/                   # Individual section text files
│   ├── 1_Introduction.txt
│   ├── 2_Management_Discussion.txt
│   └── ...
├── tables/                     # HTML tables as CSV/Excel
│   ├── balance_sheet.csv
│   ├── income_statement.csv
│   └── ...
└── text_tables/                # Plain text tables as CSV
    ├── financial_highlights.csv
    └── ...
```

## Configuration File

The parser supports configuration via a TOML file. By default, it looks for `config.toml` in the current directory, but you can specify a custom path using the `--config` argument.

### Example Configuration

```toml
# EDGAR Parser Configuration File

[Logging]
# Available log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
level = "INFO"

# Console output settings
console_output = true
console_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# File output settings
file_output = false
log_file = "edgar_parser.log"
file_format = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"

[BatchProcessing]
# Maximum number of parallel workers
max_workers = 4
```

## Document Processing Options

### Selective vs Complete Processing

By default, the parser only processes recognized filing types (10-K, 10-Q, Form 4, etc.) and skips exhibits, attachments, and other supplementary materials. This selective approach:

1. Improves memory efficiency
2. Reduces processing time
3. Results in cleaner, more relevant output

However, for some use cases, you might need to process ALL document sections in a filing. The parser provides the `process_all_documents` option for this purpose:

```python
# Process all document sections, including exhibits, attachments, etc.
parser = EdgarParser(
    file_path="/path/to/filing.txt",
    process_all_documents=True
)
```

## Comprehensive Filing Type Support

The parser includes detailed profiles for all common SEC filing types, including:

### Annual Reports
- **10-K**: Annual reports with comprehensive financial statements
- **20-F**: Foreign annual reports
- **40-F**: Canadian annual reports

### Quarterly Reports
- **10-Q**: Quarterly financial reports

### Ownership Forms
- **Form 3**: Initial ownership statements
- **Form 4**: Changes in ownership
- **Form 5**: Annual ownership summaries
- **13F**: Institutional investment manager holdings

### Registration Statements
- **S-1**: Initial public offerings (IPOs)
- **S-3**: Simplified registration
- **S-4**: Mergers and acquisitions
- **S-8**: Employee benefit plans
- **F-1, F-3, F-4**: Foreign issuer equivalents

### Proxy Statements
- **DEF 14A**: Definitive proxy statements
- **PRE 14A**: Preliminary proxy statements

### Current Reports
- **8-K**: Current reports on material events

### Other Specialized Forms
- **SC 13D/G**: Beneficial ownership reports
- **11-K**: Employee stock purchase plans
- **NT 10-K/Q**: Notifications of late filing
- **424B1-5**: Prospectus filings
- **6-K**: Foreign current reports
- **N-CSR, N-PORT, N-PX**: Investment company reports

## Advanced Usage

### Ticker Mapping for Batch Processing

When processing multiple filings, you can provide a ticker mapping dictionary:

```python
ticker_map = {
    "0000320193": "AAPL",
    "0001318605": "TSLA"
}

EdgarParser.batch_process(
    input_dir="/path/to/filings",
    ticker_map=ticker_map
)
```

### Custom Filing Type Profiles

You can extend or customize filing type profiles:

```python
# Add custom table identifiers for an existing form type
parser = EdgarParser(file_path)
parser.FILING_TYPE_PROFILES["10-K"].append("summary_of_executive_compensation")

# Add a new form type
parser.FILING_TYPE_PROFILES["N-1A"] = ["fund_summary", "investment_strategies", "fee_table"]
```

## Troubleshooting

### Common Issues

1. **Encoding Problems**: Older EDGAR filings sometimes use non-standard encodings. The parser attempts to auto-detect the encoding, but you may see replacement characters in some cases.

2. **Malformed HTML**: Some filings contain non-standard or malformed HTML. The parser includes fallback mechanisms, but extremely corrupted filings may not parse correctly.

3. **Memory Usage**: Large filings can consume significant memory. Consider using the single-file mode for very large files or adjust the `max_workers` parameter for batch processing.

### Solutions

- Try the `--verbose` flag to see detailed logging information
- Enable file logging via the configuration file to capture processing details
- Check the generated metadata.json file for parsing statistics
- For completely failed filings, examine the error message in the processing summary

## License

This software is provided under the MIT License.

## Credits

Developed by Horia & Matilda  
Enhanced by Claude

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes.
