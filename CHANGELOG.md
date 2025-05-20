<!-- markdownlint-disable MD024 -->

# Changelog

## [Unreleased]

### Added

- Created a `main.py` file with a basic "Hello, World!" script.
- Added a `requirements.txt` file with `uvicorn` and `secedgar` as dependencies.
- Created a `.github/copilot-instructions.md` file for workspace-specific Copilot instructions.
- Added a `README.md` file with setup and usage instructions.
- Created a `.vscode/tasks.json` file to run the `main.py` script.
- Set up a virtual environment using the UV utility.
- Installed the `secedgar` package.
- Created a `config.py` file for storing configuration variables.
- Replaced `config.py` with a `config.toml` file for configuration.
- Updated `main.py` to load and print configuration from `config.toml`.
- Installed the `toml` package for parsing TOML files.
- Added `edgar-file-parser.py` for parsing EDGAR filings and extracting financial tables.
- Updated `requirements.txt` to include `beautifulsoup4`, `pandas`, and `lxml`.

### Removed

- Deleted the `config.py` file as it was replaced by `config.toml`.

### Renamed

- Renamed `edgar-file-parser.py to edgar_parser.py

### Updates

- Added some basic filing download tests

## EDGAR Parser Changelog

### Version 1.2.0 (Current)

#### Configuration System

- Added TOML configuration file support using `tomli`
- Implemented hierarchical configuration search in multiple locations
- Added logging configuration options (console/file output, formats, levels)
- Added batch processing configuration options

#### Batch Processing

- Enhanced batch processing method with configuration support
- Added dynamic worker count adjustment
- Improved error handling and reporting
- Added comprehensive progress logging

#### Document Processing

- Added option to process all document types (`process_all_documents`)
- Enhanced document type detection
- Added fallback mechanisms for malformed documents

#### Command Line Interface

- Added `--config` parameter for specifying configuration file
- Added `--process-all` flag to process all document sections
- Enhanced help text and error messages

### Version 1.1.0

#### Filing Type Profiles

- Expanded filing type profiles to cover 40+ SEC forms
- Added extensive table identifiers for each filing type
- Organized financial table identifiers by category
- Added support for specialized forms (11-K, 13F, etc.)

#### Table Extraction

- Added plain text table extraction
- Enhanced table title detection
- Added support for both CSV and Excel output formats
- Improved header detection in tables

#### Section Extraction

- Added fallback mechanisms for when heading tags aren't available
- Added "Item X" section detection for 10-K/10-Q filings
- Added content cleaning to remove navigation elements
- Added individual section files for easier access

#### Memory Optimization

- Implemented chunked file reading
- Added selective document processing
- Improved memory management with early data release
- Enhanced BeautifulSoup usage

### Version 1.0.0 (Initial)

#### Core Functionality

- Basic parsing of EDGAR filing txt files
- Extraction of HTML tables based on filing type
- Section extraction based on heading hierarchy
- Single file processing

#### Organization

- Input/output directory handling
- Basic error handling
- Simple command-line interface

#### Document Processing

- Basic document type detection
- Selective processing of recognized filing types
- Simple file saving mechanisms

#### Notable Features

- Type annotations throughout
- Support for major filing types (10-K, 10-Q, Form 4)
- Table identification based on IDs
- Heading-based section extraction

### Updates:

#### May 19th Updates

Added:

- edgar_file_provider.py - a class that provide the files requested. Internally this class will determine if the files exist already or need to be downloaded.
- filing_tracker.py - thsi class implement the management of the files downloaded and parsed since inception. This is going ot be used by both file-provider and the file-parser modules

Updated:

- config.toml - created filing_tracker config section.
