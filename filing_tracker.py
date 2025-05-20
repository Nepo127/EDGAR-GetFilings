import os
import sqlite3
import re
from datetime import date, timedelta
from typing import List, Dict, Tuple, Optional, Union, Any

from app_utils import ConfigManager

class FilingTracker:
    """
    A standalone module to track SEC EDGAR filings.
    This tracker maintains a database of file locations and metadata,
    including parsing status.

    This can be used by both downloader and parser modules to track
    which filings have been downloaded and processed.
    """

    def __init__(self, db_path: Optional[str] = None, download_folder: Optional[str] = None, config_path: str = "config.toml") -> None:
        """
        Initialize the filing tracker.

        Args:
            db_path (Optional[str]): Path to the SQLite database file. If None, loaded from config.
            download_folder (Optional[str]): Base folder where filings are downloaded
            config_path (str): Path to the configuration file

        Raises:
            sqlite3.Error: If there's an issue with the database connection
            ValueError: If parameters are invalid or db_path not found
        """
        if db_path is None:
            config = ConfigManager(config_path)
            try:
                db_path = config.get_str("FileTracker", "db_path")
            except Exception as e:
                raise ValueError(f"db_path must be provided or set in [FileTracker] section of config file: {e}")

        if not isinstance(db_path, str):
            raise ValueError(f"db_path must be a string, got {type(db_path).__name__}")

        if download_folder is not None and not isinstance(download_folder, str):
            raise ValueError(f"download_folder must be a string or None, got {type(download_folder).__name__}")

        self.db = sqlite3.connect(db_path)
        self.download_folder = download_folder
        self._setup_database()

    def _setup_database(self) -> None:
        """
        Set up the SQLite database schema for tracking filings
        Creates tables and indexes if they don't exist or migrates from older schema.
        
        Raises:
            sqlite3.Error: If there's an issue with the database operations
        """
        cursor = self.db.cursor()
        
        # Check if we need to migrate from an older schema
        cursor.execute("PRAGMA table_info(filings)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if not columns:
            # Create new table with parsed flag
            cursor.execute('''
            CREATE TABLE filings (
                id INTEGER PRIMARY KEY,
                ticker TEXT,
                filing_type TEXT,
                filing_date DATE,
                file_path TEXT,
                accession_number TEXT,
                download_date DATE,
                parsed INTEGER DEFAULT 0,
                parse_date DATE,
                parse_status TEXT
            )
            ''')
            # Add indexes for better performance
            cursor.execute('CREATE INDEX idx_filing_lookup ON filings (ticker, filing_type, filing_date)')
            cursor.execute('CREATE INDEX idx_parse_status ON filings (parsed)')
            cursor.execute('CREATE INDEX idx_accession ON filings (accession_number)')
            cursor.execute('CREATE INDEX idx_file_path ON filings (file_path)')
        elif 'parsed' not in columns:
            # Migrate schema - add parsed flag and related columns
            cursor.execute('ALTER TABLE filings ADD COLUMN parsed INTEGER DEFAULT 0')
            cursor.execute('ALTER TABLE filings ADD COLUMN parse_date DATE')
            cursor.execute('ALTER TABLE filings ADD COLUMN parse_status TEXT')
            cursor.execute('CREATE INDEX idx_parse_status ON filings (parsed)')
            
            # Add file_path index if it doesn't exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_file_path'")
            if not cursor.fetchone():
                cursor.execute('CREATE INDEX idx_file_path ON filings (file_path)')
            
        self.db.commit()
        
    # File metadata extraction methods
        
    def extract_filing_date(self, filepath: str) -> Optional[date]:
        """
        Extract the filing date from a SEC filing file.
        
        Args:
            filepath (str): Path to the filing file
            
        Returns:
            Optional[date]: The filing date if found, None otherwise
            
        Raises:
            ValueError: If filepath is not a string or the file doesn't exist
        """
        if not isinstance(filepath, str):
            raise ValueError(f"filepath must be a string, got {type(filepath).__name__}")
            
        if not os.path.exists(filepath):
            raise ValueError(f"File does not exist: {filepath}")
            
        from datetime import datetime
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(10000)  # Read the first 10K bytes which should include headers
                
                # Look for FILED AS OF DATE
                match = re.search(r'FILED AS OF DATE:\s*(\d{8})', content)
                if match:
                    return datetime.strptime(match.group(1), "%Y%m%d").date()
                
                # Look for SEC-HEADER date format
                match = re.search(r'<SEC-HEADER>[^:]+:\s*(\d{8})', content)
                if match:
                    return datetime.strptime(match.group(1), "%Y%m%d").date()
                    
                # Look for FILING-DATE or FILING DATE
                match = re.search(r'FILING[- ]DATE:\s*(\d{8})', content, re.IGNORECASE)
                if match:
                    return datetime.strptime(match.group(1), "%Y%m%d").date()
                    
        except Exception as e:
            print(f"Error extracting filing date from {filepath}: {e}")
        return None
        
    def extract_accession_number(self, filepath: str) -> Optional[str]:
        """
        Extract the accession number from a SEC filing file.
        The accession number uniquely identifies a filing in the SEC EDGAR system.
        
        Args:
            filepath (str): Path to the filing file
            
        Returns:
            Optional[str]: The accession number if found, None otherwise
            
        Raises:
            ValueError: If filepath is not a string or the file doesn't exist
        """
        if not isinstance(filepath, str):
            raise ValueError(f"filepath must be a string, got {type(filepath).__name__}")
            
        if not os.path.exists(filepath):
            raise ValueError(f"File does not exist: {filepath}")
            
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(10000)  # Read first 10K bytes
                
                # Look for ACCESSION NUMBER
                match = re.search(r'ACCESSION[ -]NUMBER:\s*(\d+-\d+-\d+)', content, re.IGNORECASE)
                if match:
                    return match.group(1)
                
                # Look in SEC-HEADER format
                match = re.search(r'<SEC-HEADER>(\d+-\d+-\d+)', content)
                if match:
                    return match.group(1)
                    
                # Extract from filename if possible (common pattern)
                if '-' in os.path.basename(filepath):
                    match = re.search(r'(\d+-\d+-\d+)', os.path.basename(filepath))
                    if match:
                        return match.group(1)
                        
        except Exception as e:
            print(f"Error extracting accession number from {filepath}: {e}")
        return None
        
    # Database operations - adding and updating filings
        
    def add_filing(self, ticker: str, filing_type: str, file_path: str, 
                  filing_date: Optional[date] = None, 
                  accession_number: Optional[str] = None,
                  download_date: Optional[date] = None,
                  update_existing: bool = False) -> bool:
        """
        Add a filing to the database or update if it already exists.
        
        Args:
            ticker (str): Stock ticker symbol
            filing_type (str): Filing type (e.g., FILING_10K)
            file_path (str): Path to the filing file
            filing_date (Optional[date]): Filing date. If None, will be extracted from the file.
            accession_number (Optional[str]): Accession number. If None, will be extracted from the file.
            download_date (Optional[date]): Download date. If None, current date is used.
            update_existing (bool): Whether to update an existing entry or skip it
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            ValueError: If required parameters are invalid
            sqlite3.Error: If there's an issue with the database operations
        """
        if not isinstance(ticker, str) or not ticker:
            raise ValueError("ticker must be a non-empty string")
            
        if not isinstance(filing_type, str) or not filing_type:
            raise ValueError("filing_type must be a non-empty string")
            
        if not isinstance(file_path, str) or not file_path:
            raise ValueError("file_path must be a non-empty string")
            
        if filing_date is not None and not isinstance(filing_date, date):
            raise ValueError(f"filing_date must be a date object or None, got {type(filing_date).__name__}")
            
        if not os.path.exists(file_path):
            print(f"Warning: File {file_path} does not exist")
            return False
            
        # Extract data if not provided
        if filing_date is None:
            filing_date = self.extract_filing_date(file_path)
            if filing_date is None:
                print(f"Warning: Could not extract filing date from {file_path}")
                return False
                
        if accession_number is None:
            accession_number = self.extract_accession_number(file_path)
            
        if download_date is None:
            download_date = date.today()
            
        cursor = self.db.cursor()
        
        # Check if this filing already exists in the database
        cursor.execute('''
        SELECT id FROM filings 
        WHERE ticker = ? AND file_path = ?
        ''', (ticker, file_path))
        
        result = cursor.fetchone()
        
        if result:
            if update_existing:
                # Update existing record
                cursor.execute('''
                UPDATE filings 
                SET filing_type = ?, filing_date = ?, accession_number = ?, download_date = ?
                WHERE ticker = ? AND file_path = ?
                ''', (filing_type, filing_date, accession_number, download_date, ticker, file_path))
            else:
                # File already exists and we're not updating, consider this a success
                return True
        else:
            # Insert new record
            cursor.execute('''
            INSERT INTO filings 
            (ticker, filing_type, filing_date, file_path, accession_number, download_date, parsed)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            ''', (ticker, filing_type, filing_date, file_path, accession_number, download_date))
            
        self.db.commit()
        return True
        
    def catalog_filing(self, ticker: str, filing_type: str, filepath: str) -> bool:
        """
        Catalog a filing (extract metadata and add to database).
        Only adds new files to the database - doesn't update existing entries.
        
        Args:
            ticker (str): Stock ticker symbol
            filing_type (str): Filing type
            filepath (str): Path to the filing file
            
        Returns:
            bool: True if successfully added or already exists, False if failed
            
        Raises:
            ValueError: If parameters are invalid
        """
        if not isinstance(ticker, str) or not ticker:
            raise ValueError("ticker must be a non-empty string")
            
        if not isinstance(filing_type, str) or not filing_type:
            raise ValueError("filing_type must be a non-empty string")
            
        if not isinstance(filepath, str) or not filepath:
            raise ValueError("filepath must be a non-empty string")
            
        if not os.path.isfile(filepath):
            print(f"Warning: File {filepath} does not exist or is not a file")
            return False
            
        # Check if file is already in the database
        cursor = self.db.cursor()
        cursor.execute('''
        SELECT id FROM filings 
        WHERE file_path = ?
        ''', (filepath,))
        
        if cursor.fetchone():
            # File already exists in database, no need to update
            return True
            
        # File doesn't exist in database, extract metadata and add it
        filing_date = self.extract_filing_date(filepath)
        accession_number = self.extract_accession_number(filepath)
        
        if filing_date:
            return self.add_filing(
                ticker=ticker,
                filing_type=filing_type,
                file_path=filepath,
                filing_date=filing_date,
                accession_number=accession_number,
                download_date=date.today()
            )
        return False
        
    def catalog_folder(self, ticker: str, filing_type: str, folder_path: str, 
                     update_existing: bool = False) -> int:
        """
        Catalog all filings in a folder.
        
        Args:
            ticker (str): Stock ticker symbol
            filing_type (str): Filing type
            folder_path (str): Path to the folder containing filings
            update_existing (bool): Whether to update existing entries or skip them
            
        Returns:
            int: Number of new filings cataloged (excludes existing ones if update_existing=False)
            
        Raises:
            ValueError: If parameters are invalid
        """
        if not isinstance(ticker, str) or not ticker:
            raise ValueError("ticker must be a non-empty string")
            
        if not isinstance(filing_type, str) or not filing_type:
            raise ValueError("filing_type must be a non-empty string")
            
        if not isinstance(folder_path, str):
            raise ValueError(f"folder_path must be a string, got {type(folder_path).__name__}")
            
        if not os.path.exists(folder_path):
            print(f"Warning: Folder {folder_path} does not exist")
            return 0
            
        if not os.path.isdir(folder_path):
            print(f"Warning: {folder_path} is not a directory")
            return 0
        
        # First, get all existing file paths from the database for this ticker/filing_type
        cursor = self.db.cursor()
        cursor.execute('''
        SELECT file_path FROM filings 
        WHERE ticker = ? AND filing_type = ?
        ''', (ticker, filing_type))
        
        existing_files = set(row[0] for row in cursor.fetchall())
        
        count = 0
        for fname in os.listdir(folder_path):
            fpath = os.path.join(folder_path, fname)
            if os.path.isfile(fpath):
                # Only add new files by default
                if fpath not in existing_files or update_existing:
                    filing_date = self.extract_filing_date(fpath)
                    accession_number = self.extract_accession_number(fpath)
                    
                    if filing_date:
                        success = self.add_filing(
                            ticker=ticker,
                            filing_type=filing_type,
                            file_path=fpath,
                            filing_date=filing_date,
                            accession_number=accession_number,
                            download_date=date.today(),
                            update_existing=update_existing
                        )
                        if success:
                            count += 1
                            
        if count > 0:
            print(f"Cataloged {count} filings for {ticker}/{filing_type}")
        
        return count
        
    # Filing status management methods
        
    def mark_as_parsed(self, file_id: Optional[int] = None, 
                      ticker: Optional[str] = None, 
                      accession_number: Optional[str] = None, 
                      file_path: Optional[str] = None, 
                      status: str = "success", 
                      parse_date: Optional[date] = None) -> bool:
        """
        Mark a filing as parsed. Can identify the filing by id, ticker+accession_number, or file_path.
        
        Args:
            file_id (Optional[int]): Database ID of the filing
            ticker (Optional[str]): Stock ticker symbol
            accession_number (Optional[str]): Accession number
            file_path (Optional[str]): Path to the filing file
            status (str): Parse status (success, partial, failed)
            parse_date (Optional[date]): Parse date. If None, current date is used.
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            ValueError: If required parameters are missing or invalid
            sqlite3.Error: If there's an issue with the database operations
        """
        if file_id is not None and not isinstance(file_id, int):
            raise ValueError(f"file_id must be an integer or None, got {type(file_id).__name__}")
            
        if ticker is not None and not isinstance(ticker, str):
            raise ValueError(f"ticker must be a string or None, got {type(ticker).__name__}")
            
        if accession_number is not None and not isinstance(accession_number, str):
            raise ValueError(f"accession_number must be a string or None, got {type(accession_number).__name__}")
            
        if file_path is not None and not isinstance(file_path, str):
            raise ValueError(f"file_path must be a string or None, got {type(file_path).__name__}")
            
        if not isinstance(status, str):
            raise ValueError(f"status must be a string, got {type(status).__name__}")
            
        if parse_date is not None and not isinstance(parse_date, date):
            raise ValueError(f"parse_date must be a date object or None, got {type(parse_date).__name__}")
            
        if parse_date is None:
            parse_date = date.today()
            
        cursor = self.db.cursor()
        
        if file_id is not None:
            cursor.execute('''
            UPDATE filings 
            SET parsed = 1, parse_date = ?, parse_status = ?
            WHERE id = ?
            ''', (parse_date, status, file_id))
        elif ticker is not None and accession_number is not None:
            cursor.execute('''
            UPDATE filings 
            SET parsed = 1, parse_date = ?, parse_status = ?
            WHERE ticker = ? AND accession_number = ?
            ''', (parse_date, status, ticker, accession_number))
        elif file_path is not None:
            cursor.execute('''
            UPDATE filings 
            SET parsed = 1, parse_date = ?, parse_status = ?
            WHERE file_path = ?
            ''', (parse_date, status, file_path))
        else:
            raise ValueError("Must provide file_id, ticker+accession_number, or file_path")
            
        if cursor.rowcount == 0:
            print(f"Warning: No filing found to mark as parsed")
            return False
            
        self.db.commit()
        return True
        
    def mark_as_unparsed(self, file_id: Optional[int] = None, 
                        ticker: Optional[str] = None, 
                        accession_number: Optional[str] = None, 
                        file_path: Optional[str] = None) -> bool:
        """
        Mark a filing as unparsed (to force re-parsing).
        Can identify the filing by id, ticker+accession_number, or file_path.
        
        Args:
            file_id (Optional[int]): Database ID of the filing
            ticker (Optional[str]): Stock ticker symbol
            accession_number (Optional[str]): Accession number
            file_path (Optional[str]): Path to the filing file
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            ValueError: If required parameters are missing or invalid
            sqlite3.Error: If there's an issue with the database operations
        """
        if file_id is not None and not isinstance(file_id, int):
            raise ValueError(f"file_id must be an integer or None, got {type(file_id).__name__}")
            
        if ticker is not None and not isinstance(ticker, str):
            raise ValueError(f"ticker must be a string or None, got {type(ticker).__name__}")
            
        if accession_number is not None and not isinstance(accession_number, str):
            raise ValueError(f"accession_number must be a string or None, got {type(accession_number).__name__}")
            
        if file_path is not None and not isinstance(file_path, str):
            raise ValueError(f"file_path must be a string or None, got {type(file_path).__name__}")
            
        cursor = self.db.cursor()
        
        if file_id is not None:
            cursor.execute('''
            UPDATE filings 
            SET parsed = 0, parse_date = NULL, parse_status = NULL
            WHERE id = ?
            ''', (file_id,))
        elif ticker is not None and accession_number is not None:
            cursor.execute('''
            UPDATE filings 
            SET parsed = 0, parse_date = NULL, parse_status = NULL
            WHERE ticker = ? AND accession_number = ?
            ''', (ticker, accession_number))
        elif file_path is not None:
            cursor.execute('''
            UPDATE filings 
            SET parsed = 0, parse_date = NULL, parse_status = NULL
            WHERE file_path = ?
            ''', (file_path,))
        else:
            raise ValueError("Must provide file_id, ticker+accession_number, or file_path")
            
        if cursor.rowcount == 0:
            print(f"Warning: No filing found to mark as unparsed")
            return False
            
        self.db.commit()
        return True
        
    # Query methods
        
    def get_filings(self, ticker: Optional[str] = None, 
                   filing_type: Optional[str] = None, 
                   startdate: Optional[date] = None, 
                   enddate: Optional[date] = None, 
                   parsed: Optional[bool] = None, 
                   limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get filings from the database based on various criteria.
        
        Args:
            ticker (Optional[str]): Stock ticker symbol
            filing_type (Optional[str]): Filing type
            startdate (Optional[date]): Start date for filing_date range
            enddate (Optional[date]): End date for filing_date range
            parsed (Optional[bool]): If True, only return parsed filings. 
                                   If False, only return unparsed filings.
                                   If None, return all filings.
            limit (Optional[int]): Maximum number of results to return
            
        Returns:
            List[Dict[str, Any]]: List of dictionaries containing filing information
            
        Raises:
            ValueError: If parameters are invalid
            sqlite3.Error: If there's an issue with the database operations
        """
        if ticker is not None and not isinstance(ticker, str):
            raise ValueError(f"ticker must be a string or None, got {type(ticker).__name__}")
            
        if filing_type is not None and not isinstance(filing_type, str):
            raise ValueError(f"filing_type must be a string or None, got {type(filing_type).__name__}")
            
        if startdate is not None and not isinstance(startdate, date):
            raise ValueError(f"startdate must be a date object or None, got {type(startdate).__name__}")
            
        if enddate is not None and not isinstance(enddate, date):
            raise ValueError(f"enddate must be a date object or None, got {type(enddate).__name__}")
            
        if parsed is not None and not isinstance(parsed, bool):
            raise ValueError(f"parsed must be a boolean or None, got {type(parsed).__name__}")
            
        if limit is not None and (not isinstance(limit, int) or limit <= 0):
            raise ValueError(f"limit must be a positive integer or None, got {limit}")
            
        cursor = self.db.cursor()
        
        query = "SELECT id, ticker, filing_type, filing_date, file_path, accession_number, download_date, parsed, parse_date, parse_status FROM filings WHERE 1=1"
        params = []
        
        if ticker is not None:
            query += " AND ticker = ?"
            params.append(ticker)
            
        if filing_type is not None:
            query += " AND filing_type = ?"
            params.append(filing_type)
            
        if startdate is not None:
            query += " AND filing_date >= ?"
            params.append(startdate)
            
        if enddate is not None:
            query += " AND filing_date <= ?"
            params.append(enddate)
            
        if parsed is not None:
            query += " AND parsed = ?"
            params.append(1 if parsed else 0)
            
        query += " ORDER BY filing_date DESC"
        
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
            
        cursor.execute(query, params)
        
        results: List[Dict[str, Any]] = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'ticker': row[1],
                'filing_type': row[2],
                'filing_date': row[3],
                'file_path': row[4],
                'accession_number': row[5],
                'download_date': row[6],
                'parsed': bool(row[7]),
                'parse_date': row[8],
                'parse_status': row[9]
            })
            
        # Filter out files that don't exist
        results = [r for r in results if os.path.exists(r['file_path'])]
        
        return results
        
    def get_unparsed_filings(self, ticker: Optional[str] = None, 
                            filing_type: Optional[str] = None, 
                            limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get filings that have not been parsed yet.
        
        Args:
            ticker (Optional[str]): Stock ticker symbol
            filing_type (Optional[str]): Filing type
            limit (Optional[int]): Maximum number of results to return
            
        Returns:
            List[Dict[str, Any]]: List of dictionaries containing filing information
            
        Raises:
            ValueError: If parameters are invalid
            sqlite3.Error: If there's an issue with the database operations
        """
        return self.get_filings(ticker=ticker, filing_type=filing_type, parsed=False, limit=limit)
        
    # Batch operations
        
    def sync_all_existing_filings(self, download_folder: Optional[str] = None, 
                                 tickers: Optional[List[str]] = None,
                                 update_existing: bool = False) -> Dict[str, Dict[str, int]]:
        """
        Utility method to scan all existing folders and update the tracker database.
        
        Args:
            download_folder (Optional[str]): Base folder where filings are downloaded.
                                           If None, uses self.download_folder.
            tickers (Optional[List[str]]): List of tickers to sync. If None, scans all
                                         directories in the download folder.
            update_existing (bool): Whether to update timestamps of existing entries
                                   or only add new files
        
        Returns:
            Dict[str, Dict[str, int]]: Summary of cataloged filings by ticker and filing type
            
        Raises:
            ValueError: If parameters are invalid or download folder is not specified
        """
        if download_folder is None:
            download_folder = self.download_folder
            
        if download_folder is None:
            raise ValueError("No download folder specified. Please provide download_folder or initialize with one.")
            
        if tickers is not None and not isinstance(tickers, list):
            raise ValueError(f"tickers must be a list or None, got {type(tickers).__name__}")
            
        if tickers is not None and not all(isinstance(t, str) for t in tickers):
            raise ValueError("All tickers must be strings")
            
        results: Dict[str, Dict[str, int]] = {}
        
        # If no tickers specified, discover all ticker folders
        if tickers is None:
            if os.path.exists(download_folder):
                tickers = [d for d in os.listdir(download_folder) 
                          if os.path.isdir(os.path.join(download_folder, d))]
            else:
                print(f"Download folder {download_folder} does not exist")
                return results
        
        print(f"Syncing existing filings for {len(tickers)} tickers...")
        
        # For each ticker, discover and catalog all filing types
        for ticker in tickers:
            ticker_folder = os.path.join(download_folder, ticker)
            if not os.path.exists(ticker_folder):
                print(f"Ticker folder {ticker_folder} does not exist")
                continue
                
            # Get all filing type folders
            filing_types = [d for d in os.listdir(ticker_folder) 
                           if os.path.isdir(os.path.join(ticker_folder, d))]
            
            ticker_results: Dict[str, int] = {}
            for filing_type_str in filing_types:
                folder_path = os.path.join(ticker_folder, filing_type_str)
                count = self.catalog_folder(ticker, filing_type_str, folder_path, 
                                          update_existing=update_existing)
                ticker_results[filing_type_str] = count
            
            results[ticker] = ticker_results
            
        # Print a summary
        total_files = sum(sum(type_counts.values()) for type_counts in results.values())
        if update_existing:
            print(f"Sync complete. Cataloged/updated {total_files} files across {len(results)} tickers.")
        else:
            print(f"Sync complete. Cataloged {total_files} new files across {len(results)} tickers.")
        
        return results
    
    # Statistics methods
    
    def get_filing_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about filings in the database.
        
        Returns:
            Dict[str, Any]: Statistics about filings
            
        Raises:
            sqlite3.Error: If there's an issue with the database operations
        """
        cursor = self.db.cursor()
        
        stats: Dict[str, Any] = {}
        
        # Total filings
        cursor.execute("SELECT COUNT(*) FROM filings")
        stats['total_filings'] = cursor.fetchone()[0]
        
        # Filings by ticker
        cursor.execute("SELECT ticker, COUNT(*) FROM filings GROUP BY ticker ORDER BY COUNT(*) DESC")
        stats['filings_by_ticker'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Filings by type
        cursor.execute("SELECT filing_type, COUNT(*) FROM filings GROUP BY filing_type ORDER BY COUNT(*) DESC")
        stats['filings_by_type'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Parsed vs unparsed
        cursor.execute("SELECT parsed, COUNT(*) FROM filings GROUP BY parsed")
        parsed_stats = {bool(row[0]): row[1] for row in cursor.fetchall()}
        stats['parsed_filings'] = parsed_stats.get(True, 0)
        stats['unparsed_filings'] = parsed_stats.get(False, 0)
        
        # Parse status breakdown
        cursor.execute("SELECT parse_status, COUNT(*) FROM filings WHERE parsed = 1 GROUP BY parse_status")
        stats['parse_status'] = {row[0] if row[0] else 'unknown': row[1] for row in cursor.fetchall()}
        
        # Date range
        cursor.execute("SELECT MIN(filing_date), MAX(filing_date) FROM filings")
        row = cursor.fetchone()
        stats['first_filing_date'] = row[0]
        stats['last_filing_date'] = row[1]
        
        return stats
    
    # Resource management methods
    
    def close(self) -> None:
        """
        Close the database connection.
        
        It's important to call this method when you're done using the FilingTracker
        to ensure proper cleanup of database resources.
        """
        if self.db:
            self.db.close()
            
    def __del__(self) -> None:
        """
        Destructor to ensure database connection is closed when object is garbage collected.
        """
        self.close()


# Command line interface when run as a script
if __name__ == "__main__":
    import argparse
    import json
    from datetime import datetime
    
    def valid_date(s: str) -> date:
        """
        Convert string to date object for argparse.
        
        Args:
            s (str): Date string in YYYY-MM-DD format
            
        Returns:
            date: Parsed date object
            
        Raises:
            argparse.ArgumentTypeError: If date format is invalid
        """
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            msg = f"Not a valid date: '{s}'. Expected format: YYYY-MM-DD"
            raise argparse.ArgumentTypeError(msg)
    
    parser = argparse.ArgumentParser(
        description="SEC EDGAR Filing Tracker - Utility to manage and track SEC filings"
    )
    parser.add_argument("--db-path", type=str, default="filings_metadata.db", 
                       help="Path to the database file")
    parser.add_argument("--download-folder", type=str, 
                       help="Base folder where filings are downloaded")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Scan existing folders and update the database")
    sync_parser.add_argument("--tickers", type=str, 
                           help="Comma-separated list of tickers to sync")
    sync_parser.add_argument("--update-existing", action="store_true",
                           help="Update metadata for existing files (including download date)")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List filings in the database")
    list_parser.add_argument("--ticker", type=str, help="Filter by ticker symbol")
    list_parser.add_argument("--filing-type", type=str, help="Filter by filing type")
    list_parser.add_argument("--start-date", type=valid_date, help="Start date (YYYY-MM-DD)")
    list_parser.add_argument("--end-date", type=valid_date, help="End date (YYYY-MM-DD)")
    list_parser.add_argument("--parsed", action="store_true", help="Show only parsed filings")
    list_parser.add_argument("--unparsed", action="store_true", help="Show only unparsed filings")
    list_parser.add_argument("--limit", type=int, default=100, 
                           help="Maximum number of results to show")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show statistics about filings in the database")
    stats_parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    # Mark command
    mark_parser = subparsers.add_parser("mark", help="Mark filings as parsed or unparsed")
    mark_parser.add_argument("--ticker", type=str, required=True, help="Ticker symbol")
    mark_parser.add_argument("--accession", type=str, help="Accession number")
    mark_parser.add_argument("--file-path", type=str, help="File path")
    mark_parser.add_argument("--parsed", action="store_true", help="Mark as parsed")
    mark_parser.add_argument("--unparsed", action="store_true", help="Mark as unparsed")
    mark_parser.add_argument("--status", type=str, default="success", 
                           help="Parse status (success, partial, failed)")
    
    args = parser.parse_args()
    
    try:
        tracker = FilingTracker(db_path=args.db_path, download_folder=args.download_folder)
        
        if args.command == "sync":
            tickers = None
            if args.tickers:
                tickers = [t.strip() for t in args.tickers.split(',')]
            results = tracker.sync_all_existing_filings(
                tickers=tickers, 
                update_existing=args.update_existing
            )
            
            # Print detailed summary
            print("\nSync Results Summary:")
            for ticker, type_counts in results.items():
                print(f"{ticker}:")
                for filing_type, count in type_counts.items():
                    print(f"  {filing_type}: {count} filings")
                    
        elif args.command == "list":
            parsed = None
            if args.parsed:
                parsed = True
            elif args.unparsed:
                parsed = False
                
            filings = tracker.get_filings(
                ticker=args.ticker,
                filing_type=args.filing_type,
                startdate=args.start_date,
                enddate=args.end_date,
                parsed=parsed,
                limit=args.limit
            )
            
            if args.json:
                # Convert date objects to strings for JSON serialization
                for filing in filings:
                    for key in ['filing_date', 'download_date', 'parse_date']:
                        if filing[key] is not None:
                            filing[key] = str(filing[key])
                print(json.dumps(filings, indent=2))
            else:
                print(f"Found {len(filings)} filings:")
                for i, filing in enumerate(filings, 1):
                    parsed_status = f"Parsed: {filing['parse_status']} on {filing['parse_date']}" if filing['parsed'] else "Not parsed"
                    print(f"{i}. {filing['ticker']} - {filing['filing_type']} - {filing['filing_date']} - {parsed_status}")
                    print(f"   File: {filing['file_path']}")
                    if filing['accession_number']:
                        print(f"   Accession: {filing['accession_number']}")
                    print()
                    
        elif args.command == "stats":
            stats = tracker.get_filing_statistics()
            
            if args.json:
                # Convert date objects to strings for JSON serialization
                for key in ['first_filing_date', 'last_filing_date']:
                    if stats[key] is not None:
                        stats[key] = str(stats[key])
                print(json.dumps(stats, indent=2))
            else:
                print("Filing Statistics:")
                print(f"Total filings: {stats['total_filings']}")
                print(f"Parsed filings: {stats['parsed_filings']}")
                print(f"Unparsed filings: {stats['unparsed_filings']}")
                print(f"Date range: {stats['first_filing_date']} to {stats['last_filing_date']}")
                
                print("\nTop tickers:")
                for ticker, count in list(stats['filings_by_ticker'].items())[:10]:
                    print(f"  {ticker}: {count} filings")
                    
                print("\nFilings by type:")
                for filing_type, count in stats['filings_by_type'].items():
                    print(f"  {filing_type}: {count} filings")
                    
                if stats.get('parse_status'):
                    print("\nParse status breakdown:")
                    for status, count in stats['parse_status'].items():
                        print(f"  {status}: {count} filings")
                        
        elif args.command == "mark":
            if not (args.parsed or args.unparsed):
                print("Error: Must specify --parsed or --unparsed")
            elif args.parsed and args.unparsed:
                print("Error: Cannot specify both --parsed and --unparsed")
            elif not (args.accession or args.file_path):
                print("Error: Must specify --accession or --file-path")
            else:
                if args.parsed:
                    result = tracker.mark_as_parsed(
                        ticker=args.ticker,
                        accession_number=args.accession,
                        file_path=args.file_path,
                        status=args.status
                    )
                    if result:
                        print(f"Successfully marked filing as parsed with status '{args.status}'")
                    else:
                        print("Failed to mark filing as parsed")
                else:
                    result = tracker.mark_as_unparsed(
                        ticker=args.ticker,
                        accession_number=args.accession,
                        file_path=args.file_path
                    )
                    if result:
                        print("Successfully marked filing as unparsed")
                    else:
                        print("Failed to mark filing as unparsed")
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        if 'tracker' in locals():
            tracker.close()
