from datetime import date, timedelta
import os
import sys
import re
from typing import List, Dict, Tuple, Optional, Union, Any
from secedgar import FilingType, CompanyFilings
from app_utils import ConfigManager, LoggingManager
from filing_tracker import FilingTracker


class EdgarFilesProvider:
    """
    Provider class for SEC EDGAR filings.
    This class handles downloading and tracking SEC filings.
    """
    
    def __init__(self, config_path: str = "config.toml", db_path: str = "filings_metadata.db") -> None:
        """
        Initialize the files provider.
        
        Args:
            config_path (str): Path to the configuration file
            db_path (str): Path to the SQLite database file
        """
        if not os.path.exists(config_path):
            raise ValueError(f"Config file not found: {config_path}")
            
        self.config = ConfigManager(config_path).get_config()["edgar_file_grabber"]
        self.download_folder = self.config["SEC_FILES_DOWNLOAD_FOLDER"]
        self.user_agent = self.config["SEC_EDGAR_USER_AGENT"]
        
        # Create download folder if it doesn't exist
        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder, exist_ok=True)
            
        self.tracker = FilingTracker(db_path=db_path, download_folder=self.download_folder)
        
    def _download_company_filings(self, ticker: str, filing_type: FilingType, 
                                 startdate: date, enddate: date) -> None:
        """
        Download filings from SEC EDGAR.
        
        Args:
            ticker (str): Stock ticker symbol or CIK
            filing_type (FilingType): Filing type enum
            startdate (date): Start date for filing period
            enddate (date): End date for filing period
            
        Raises:
            ValueError: If invalid parameters are provided
        """
        if not isinstance(ticker, str) or not ticker:
            raise ValueError("Ticker must be a non-empty string")
            
        if not isinstance(filing_type, FilingType):
            raise ValueError(f"filing_type must be a FilingType enum, got {type(filing_type)}")
            
        if not isinstance(startdate, date) or not isinstance(enddate, date):
            raise ValueError("startdate and enddate must be date objects")
            
        if startdate > enddate:
            raise ValueError(f"startdate ({startdate}) must be before enddate ({enddate})")
            
        filing = CompanyFilings(
            cik_lookup=ticker,
            filing_type=filing_type,
            start_date=startdate,
            end_date=enddate,
            user_agent=self.user_agent
        )
        filing.save(self.download_folder)
        print(f"Filings for {ticker} ({filing_type}) downloaded to {self.download_folder}")
        
    def get_missing_ranges(self, ticker: str, filing_type_str: str, 
                          startdate: date, enddate: date) -> List[Tuple[date, date]]:
        """
        Identify missing date ranges that need to be downloaded.
        Uses smart gap detection based on filing type expectations.
        
        Args:
            ticker (str): Stock ticker symbol
            filing_type_str (str): Filing type as string
            startdate (date): Start date
            enddate (date): End date
            
        Returns:
            List[Tuple[date, date]]: List of (start_date, end_date) tuples for missing ranges
            
        Raises:
            ValueError: If invalid parameters are provided
        """
        if not isinstance(ticker, str) or not ticker:
            raise ValueError("Ticker must be a non-empty string")
            
        if not isinstance(filing_type_str, str) or not filing_type_str:
            raise ValueError("filing_type_str must be a non-empty string")
            
        if not isinstance(startdate, date) or not isinstance(enddate, date):
            raise ValueError("startdate and enddate must be date objects")
            
        if startdate > enddate:
            raise ValueError(f"startdate ({startdate}) must be before enddate ({enddate})")
            
        # Get existing filings for this date range
        filings = self.tracker.get_filings(
            ticker=ticker, 
            filing_type=filing_type_str,
            startdate=startdate,
            enddate=enddate
        )
        
        existing_dates = [f['filing_date'] for f in filings]
        
        if not existing_dates:
            # If no files exist for this range, download the whole range
            return [(startdate, enddate)]
            
        # Convert string dates to date objects if needed
        existing_dates = [
            d if not isinstance(d, str) else date.fromisoformat(d)
            for d in existing_dates if d is not None
        ]
            
        # Different filing types have different expected frequencies
        # Use exact FilingType enum name
        if filing_type_str == "FILING_10Q":
            # Quarterly reports
            return self._get_missing_quarterly_ranges(existing_dates, startdate, enddate)
        elif filing_type_str == "FILING_10K":
            # Annual reports
            return self._get_missing_annual_ranges(existing_dates, startdate, enddate)
        else:
            # Default: check for large gaps
            return self._get_missing_gap_ranges(existing_dates, startdate, enddate)
            
    def _get_missing_quarterly_ranges(self, existing_dates: List[date], 
                                     startdate: date, enddate: date) -> List[Tuple[date, date]]:
        """
        Helper to find missing quarters for quarterly reports.
        
        Args:
            existing_dates (List[date]): List of dates for existing filings
            startdate (date): Start date of the search range
            enddate (date): End date of the search range
            
        Returns:
            List[Tuple[date, date]]: List of (start_date, end_date) tuples for missing quarters
            
        Raises:
            ValueError: If input parameters are invalid
            
        Example:
            >>> provider = EdgarFilesProvider()
            >>> existing = [date(2020, 3, 31), date(2020, 9, 30)]
            >>> start = date(2020, 1, 1)
            >>> end = date(2020, 12, 31)
            >>> provider._get_missing_quarterly_ranges(existing, start, end)
            [(date(2020, 4, 1), date(2020, 6, 30)), (date(2020, 10, 1), date(2020, 12, 31))]
        """
        if not all(isinstance(d, date) for d in existing_dates):
            raise ValueError("All existing_dates must be date objects")
            
        if not isinstance(startdate, date) or not isinstance(enddate, date):
            raise ValueError("startdate and enddate must be date objects")
            
        if startdate > enddate:
            raise ValueError(f"startdate ({startdate}) must be before enddate ({enddate})")
            
        # Group by quarter and check for missing quarters
        quarters: Dict[Tuple[int, int], int] = {}
        for d in existing_dates:
            year_q = (d.year, (d.month-1)//3 + 1)
            quarters[year_q] = quarters.get(year_q, 0) + 1
            
        # Generate all quarters in range
        all_quarters: List[Tuple[int, int]] = []
        start_year_q = (startdate.year, (startdate.month-1)//3 + 1)
        end_year_q = (enddate.year, (enddate.month-1)//3 + 1)
        
        y, q = start_year_q
        while (y, q) <= end_year_q:
            all_quarters.append((y, q))
            q += 1
            if q > 4:
                q = 1
                y += 1
                
        # Find missing quarters
        missing_quarters = [qtr for qtr in all_quarters if qtr not in quarters]
        
        # Convert quarters to date ranges
        missing_ranges: List[Tuple[date, date]] = []
        for y, q in missing_quarters:
            q_start = date(y, (q-1)*3+1, 1)
            if q < 4:
                q_end = date(y, q*3+1, 1) - timedelta(days=1)
            else:
                q_end = date(y+1, 1, 1) - timedelta(days=1)
            missing_ranges.append((q_start, q_end))
            
        return missing_ranges
        
    def _get_missing_annual_ranges(self, existing_dates: List[date], 
                                  startdate: date, enddate: date) -> List[Tuple[date, date]]:
        """
        Helper to find missing years for annual reports.
        
        Args:
            existing_dates (List[date]): List of dates for existing filings
            startdate (date): Start date of the search range
            enddate (date): End date of the search range
            
        Returns:
            List[Tuple[date, date]]: List of (start_date, end_date) tuples for missing years
            
        Raises:
            ValueError: If input parameters are invalid
            
        Example:
            >>> provider = EdgarFilesProvider()
            >>> existing = [date(2020, 12, 31), date(2022, 12, 31)]
            >>> start = date(2020, 1, 1)
            >>> end = date(2023, 12, 31)
            >>> provider._get_missing_annual_ranges(existing, start, end)
            [(date(2021, 1, 1), date(2021, 12, 31)), (date(2023, 1, 1), date(2023, 12, 31))]
        """
        if not all(isinstance(d, date) for d in existing_dates):
            raise ValueError("All existing_dates must be date objects")
            
        if not isinstance(startdate, date) or not isinstance(enddate, date):
            raise ValueError("startdate and enddate must be date objects")
            
        if startdate > enddate:
            raise ValueError(f"startdate ({startdate}) must be before enddate ({enddate})")
            
        # Group by year
        years: Dict[int, int] = {}
        for d in existing_dates:
            years[d.year] = years.get(d.year, 0) + 1
            
        # Find missing years
        all_years = range(startdate.year, enddate.year + 1)
        missing_years = [y for y in all_years if y not in years]
        
        # Convert to date ranges
        missing_ranges: List[Tuple[date, date]] = []
        for y in missing_years:
            y_start = date(y, 1, 1)
            y_end = date(y, 12, 31)
            missing_ranges.append((y_start, y_end))
            
        return missing_ranges
        
    def _get_missing_gap_ranges(self, existing_dates: List[date], startdate: date, 
                               enddate: date, gap_days: int = 30) -> List[Tuple[date, date]]:
        """
        Helper to find gaps in more frequent filings (e.g., Form 4, 8-K).
        Identifies date ranges with no filings that exceed a specified gap threshold.
        
        Args:
            existing_dates (List[date]): List of dates for existing filings
            startdate (date): Start date of the search range
            enddate (date): End date of the search range
            gap_days (int, optional): Number of days to consider a significant gap. Defaults to 30.
            
        Returns:
            List[Tuple[date, date]]: List of (start_date, end_date) tuples for missing gaps
            
        Raises:
            ValueError: If input parameters are invalid
            
        Example:
            >>> provider = EdgarFilesProvider()
            >>> existing = [date(2020, 1, 15), date(2020, 3, 1), date(2020, 6, 1)]
            >>> start = date(2020, 1, 1)
            >>> end = date(2020, 12, 31)
            >>> provider._get_missing_gap_ranges(existing, start, end, gap_days=45)
            [(date(2020, 3, 2), date(2020, 5, 31)), (date(2020, 6, 2), date(2020, 12, 31))]
        """
        if not all(isinstance(d, date) for d in existing_dates):
            raise ValueError("All existing_dates must be date objects")
            
        if not isinstance(startdate, date) or not isinstance(enddate, date):
            raise ValueError("startdate and enddate must be date objects")
            
        if startdate > enddate:
            raise ValueError(f"startdate ({startdate}) must be before enddate ({enddate})")
            
        if not isinstance(gap_days, int) or gap_days < 1:
            raise ValueError("gap_days must be a positive integer")
            
        # Sort dates and look for large gaps
        sorted_dates = sorted(existing_dates)
        
        if not sorted_dates:
            return [(startdate, enddate)]
            
        missing_ranges: List[Tuple[date, date]] = []
        
        # Check if we need to download before the first existing date
        if startdate < sorted_dates[0]:
            missing_ranges.append((startdate, sorted_dates[0] - timedelta(days=1)))
        
        # Check for gaps between dates
        for i in range(len(sorted_dates) - 1):
            gap = (sorted_dates[i+1] - sorted_dates[i]).days
            if gap > gap_days:
                gap_start = sorted_dates[i] + timedelta(days=1)
                gap_end = sorted_dates[i+1] - timedelta(days=1)
                missing_ranges.append((gap_start, gap_end))
        
        # Check if we need to download after the last existing date
        if sorted_dates[-1] < enddate:
            missing_ranges.append((sorted_dates[-1] + timedelta(days=1), enddate))
            
        return missing_ranges

    def get_company_filings(self, ticker: str, filing_type: Union[FilingType, str], 
                           startdate: date, enddate: date) -> List[str]:
        """
        Get company filings for the given ticker, filing type, and date range.
        Will return existing files and download any missing ones as needed.
        
        Args:
            ticker (str): Stock ticker symbol or CIK
            filing_type (Union[FilingType, str]): Filing type (FilingType enum or string)
            startdate (date): Start date
            enddate (date): End date
            
        Returns:
            List[str]: List of file paths for the filings
            
        Raises:
            ValueError: If invalid parameters are provided
        """
        if not isinstance(ticker, str) or not ticker:
            raise ValueError("Ticker must be a non-empty string")
            
        if not isinstance(startdate, date) or not isinstance(enddate, date):
            raise ValueError("startdate and enddate must be date objects")
            
        if startdate > enddate:
            raise ValueError(f"startdate ({startdate}) must be before enddate ({enddate})")
            
        # Convert filing_type to proper format
        if isinstance(filing_type, FilingType):
            # Get the enum name (e.g., FILING_10K)
            filing_type_str = None
            for attr in dir(FilingType):
                if not attr.startswith('_') and not callable(getattr(FilingType, attr)):
                    if getattr(FilingType, attr) == filing_type:
                        filing_type_str = attr
                        break
            
            if filing_type_str is None:
                raise ValueError(f"Unknown FilingType enum value: {filing_type}")
                
            filing_type_enum = filing_type
        else:
            # String was passed, try to convert to enum if needed
            filing_type_str = str(filing_type)
            filing_type_enum = self._get_filing_type_enum(filing_type_str)
            
        # If we couldn't map to an enum and need to download, we'll have a problem
        if filing_type_enum is None:
            print(f"Warning: Filing type '{filing_type_str}' is not a valid FilingType enum name.")
            print("Please use exact enum names from FilingType (e.g., 'FILING_10K').")
            print("Will attempt to use existing files only.")
        
        # First, ensure existing filings are cataloged
        ticker_folder = os.path.join(self.download_folder, ticker, filing_type_str)
        if os.path.exists(ticker_folder):
            self.tracker.catalog_folder(ticker, filing_type_str, ticker_folder)
        
        # Check what we already have
        existing_filings = self.tracker.get_filings(
            ticker=ticker,
            filing_type=filing_type_str,
            startdate=startdate,
            enddate=enddate
        )
        
        if existing_filings:
            print(f"Found {len(existing_filings)} existing filings for {ticker} ({filing_type_str}) between {startdate} and {enddate}")
            
        # Check if we need to download any missing ranges
        if filing_type_enum is not None:  # Only download if we have a valid FilingType enum
            missing_ranges = self.get_missing_ranges(ticker, filing_type_str, startdate, enddate)
            
            if missing_ranges:
                print(f"Found {len(missing_ranges)} missing date ranges, downloading...")
                for range_start, range_end in missing_ranges:
                    print(f"Downloading {ticker} {filing_type_str} from {range_start} to {range_end}")
                    self._download_company_filings(ticker, filing_type_enum, range_start, range_end)
                
                # Catalog newly downloaded files
                self.tracker.catalog_folder(ticker, filing_type_str, ticker_folder)
                
                # Update our list of files
                existing_filings = self.tracker.get_filings(
                    ticker=ticker,
                    filing_type=filing_type_str,
                    startdate=startdate,
                    enddate=enddate
                )
        else:
            print("Skipping download step due to unknown filing type.")
        
        return [f['file_path'] for f in existing_filings]
        
    def _get_filing_type_enum(self, filing_type_str: str) -> Optional[FilingType]:
        """
        Map a filing type string to the corresponding FilingType enum.
        Only accepts exact string matches from FilingType enum naming.
        
        Args:
            filing_type_str (str): Filing type as string (must match FilingType enum names)
            
        Returns:
            Optional[FilingType]: The corresponding FilingType enum, or None if not found
            
        Raises:
            ValueError: If filing_type_str is not a string
            
        Example:
            >>> provider = EdgarFilesProvider()
            >>> provider._get_filing_type_enum("FILING_10K")
            <FilingType.FILING_10K: ...>
            >>> provider._get_filing_type_enum("10-K")
            None
            >>> provider._get_filing_type_enum("INVALID")
            None
        """
        if not isinstance(filing_type_str, str):
            raise ValueError(f"filing_type_str must be a string, got {type(filing_type_str).__name__}")
            
        if not filing_type_str:
            return None
            
        # Create a reverse mapping from string names to FilingType enums
        filing_type_map: Dict[str, FilingType] = {}
        
        # Add direct mappings from FilingType enum
        for attr in dir(FilingType):
            if not attr.startswith('_') and not callable(getattr(FilingType, attr)):
                enum_val = getattr(FilingType, attr)
                # Map both with and without the FilingType. prefix
                filing_type_map[attr] = enum_val
                filing_type_map[f"FilingType.{attr}"] = enum_val

        # Try direct match against our mapping
        if filing_type_str in filing_type_map:
            return filing_type_map[filing_type_str]
            
        return None
        
    def get_all_filing_types(self) -> List[str]:
        """
        Get a list of all supported filing types as defined in FilingType enum.
        
        Returns:
            List[str]: List of valid filing type string names
            
        Example:
            >>> provider = EdgarFilesProvider()
            >>> filing_types = provider.get_all_filing_types()
            >>> print(filing_types)
            ['FILING_10K', 'FILING_10Q', 'FILING_4', ...]
        """
        filing_types: List[str] = []
        
        # Add all FilingType enum names
        for attr in dir(FilingType):
            if not attr.startswith('_') and not callable(getattr(FilingType, attr)):
                filing_types.append(attr)
                
        return sorted(filing_types)


def parse_date(date_str: str) -> date:
    """
    Parse date string in YYYY-MM-DD format.
    
    Args:
        date_str (str): Date string in YYYY-MM-DD format
        
    Returns:
        date: Parsed date object
        
    Raises:
        ValueError: If date format is invalid
        
    Example:
        >>> parse_date("2023-01-15")
        datetime.date(2023, 1, 15)
        >>> parse_date("invalid")
        ValueError: Invalid date format: invalid. Use YYYY-MM-DD.
    """
    if not isinstance(date_str, str):
        raise ValueError(f"Expected string, got {type(date_str).__name__}")
        
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Download or list SEC filings for a given ticker and filing type."
    )
    parser.add_argument("--ticker", type=str, help="CIK or ticker symbol")
    parser.add_argument("--filing-type", type=str, help="Filing type (e.g., FILING_10K, FILING_10Q)")
    parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD)")
    
    # For backward compatibility
    parser.add_argument("--start-year", type=int, help="Start year (deprecated, use --start-date)")
    parser.add_argument("--end-year", type=int, help="End year (deprecated, use --end-date)")
    parser.add_argument("--start-month", type=int, default=1, help="Start month (deprecated)")
    parser.add_argument("--start-day", type=int, default=1, help="Start day (deprecated)")
    parser.add_argument("--end-month", type=int, default=12, help="End month (deprecated)")
    parser.add_argument("--end-day", type=int, default=31, help="End day (deprecated)")
    
    parser.add_argument("--db-path", type=str, default="filings_metadata.db", 
                        help="Path to the SQLite database file (default: filings_metadata.db)")
    parser.add_argument("--list", action="store_true", 
                        help="List filings if they exist, otherwise download and list.")
    parser.add_argument("--sync-all", action="store_true", 
                        help="Scan all existing downloaded filings and update the tracker database")
    parser.add_argument("--tickers", type=str, 
                        help="Comma-separated list of tickers to sync (only used with --sync-all)")
    parser.add_argument("--show-filing-types", action="store_true", 
                        help="Show all available filing types")

    args = parser.parse_args()
    
    provider = EdgarFilesProvider(db_path=args.db_path)
    
    # Show filing types and exit
    if args.show_filing_types:
        filing_types = provider.get_all_filing_types()
        print("Available filing types:")
        for name in filing_types:
            print(f"  {name}")
        sys.exit(0)
    
    # Sync all filings and exit
    if args.sync_all:
        tickers = None
        if args.tickers:
            tickers = [t.strip() for t in args.tickers.split(',')]
        results = provider.tracker.sync_all_existing_filings(tickers=tickers)
        
        # Print detailed summary
        print("\nSync Results Summary:")
        for ticker, type_counts in results.items():
            print(f"{ticker}:")
            for filing_type, count in type_counts.items():
                print(f"  {filing_type}: {count} filings")
        sys.exit(0)
    
    # Validate required arguments for normal operation
    if not args.ticker:
        parser.error("--ticker is required")
    if not args.filing_type:
        parser.error("--filing-type is required")
    
    # Handle date arguments
    try:
        if args.start_date:
            startdate = parse_date(args.start_date)
        elif args.start_year:
            startdate = date(args.start_year, args.start_month, args.start_day)
        else:
            startdate = date(2010, 1, 1)  # Default
        
        if args.end_date:
            enddate = parse_date(args.end_date)
        elif args.end_year:
            enddate = date(args.end_year, args.end_month, args.end_day)
        else:
            enddate = date.today()  # Default
    except ValueError as e:
        parser.error(str(e))
    
    # Validate date range
    if startdate > enddate:
        parser.error(f"Start date ({startdate}) must be before end date ({enddate})")
    
    # Validate filing type
    filing_type = args.filing_type
    if provider._get_filing_type_enum(filing_type) is None:
        valid_types = provider.get_all_filing_types()
        parser.error(f"Invalid filing type: {filing_type}. Valid types are: {', '.join(valid_types)}")
    
    try:
        # Get the filings
        files = provider.get_company_filings(args.ticker, filing_type, startdate, enddate)
        print(f"Found {len(files)} filings for {args.ticker} ({filing_type}) between {startdate} and {enddate}")
        
        if args.list and files:
            print("\nList of files:")
            for i, file_path in enumerate(files, 1):
                filing_date = provider.tracker.extract_filing_date(file_path)
                date_str = f" ({filing_date})" if filing_date else ""
                print(f"{i}. {os.path.basename(file_path)}{date_str}")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)(days=1)
        missing_ranges.append((gap_start, gap_end))
        # Check if we need to download after the last existing date
        if sorted_dates[-1] < enddate:
            missing_ranges.append((sorted_dates[-1] + timedelta(days=1), enddate))
        