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

### Updates

- Added some basic filing download tests
