
from datetime import date
import os
from secedgar import FilingType, CompanyFilings
from app_utils import ConfigManager, LoggingManager

class EdgarFileGrabber:
    def __init__(self, config_path="config.toml"):
        self.config = ConfigManager(config_path).get_config()["edgar_file_grabber"]
        self.download_folder = self.config["SEC_FILES_DOWNLOAD_FOLDER"]
        self.user_agent = self.config["SEC_EDGAR_USER_AGENT"]

    def _download_company_filings(self, ticker, filing_type, startdate, enddate):
        filing = CompanyFilings(
            cik_lookup=ticker,
            filing_type=filing_type,
            start_date=startdate,
            end_date=enddate,
            user_agent=self.user_agent
        )
        filing.save(self.download_folder)
        print(f"Filings for {ticker} ({filing_type}) downloaded to {self.download_folder}")

    def get_company_filings(self, ticker, filing_type, startdate, enddate):
        """
        Returns a list of filing files for the given ticker, filing_type, and date range.
        If no files in the date range are found, downloads them and returns the new list.
        The date is determined by parsing the metadata in each file (e.g., FILED AS OF DATE or <SEC-HEADER>...: YYYYMMDD).
        """
        import re
        from datetime import datetime

        def extract_filing_date(filepath):
            # Try to extract date from metadata lines
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        # Look for FILED AS OF DATE: or <SEC-HEADER>...: YYYYMMDD
                        if 'FILED AS OF DATE:' in line:
                            parts = line.split('FILED AS OF DATE:')
                            if len(parts) > 1:
                                date_str = parts[1].strip()[:8]
                                if len(date_str) == 8 and date_str.isdigit():
                                    return datetime.strptime(date_str, "%Y%m%d").date()
                        elif '<SEC-HEADER>' in line and ':' in line:
                            # e.g. <SEC-HEADER>0000950170-23-001409.hdr.sgml : 20230131
                            date_part = line.split(':')[-1].strip()
                            if len(date_part) == 8 and date_part.isdigit():
                                return datetime.strptime(date_part, "%Y%m%d").date()
            except Exception as e:
                pass
            return None

        filing_type_str = str(filing_type).replace("FilingType.", "")
        ticker_folder = os.path.join(self.download_folder, ticker, filing_type_str)
        files_found = []

        if os.path.exists(ticker_folder):
            for fname in os.listdir(ticker_folder):
                fpath = os.path.join(ticker_folder, fname)
                if os.path.isfile(fpath):
                    file_date = extract_filing_date(fpath)
                    if file_date and startdate <= file_date <= enddate:
                        files_found.append(fpath)
        if files_found:
            print(f"Found {len(files_found)} filings for {ticker} in {ticker_folder} within date range {startdate} to {enddate}")
            return files_found
        else:
            print(f"No filings found for {ticker} in {ticker_folder} within date range {startdate} to {enddate}, downloading...")
            self._download_company_filings(ticker, filing_type, startdate, enddate)
            # After download, list again
            files_found = []
            if os.path.exists(ticker_folder):
                for fname in os.listdir(ticker_folder):
                    fpath = os.path.join(ticker_folder, fname)
                    if os.path.isfile(fpath):
                        file_date = extract_filing_date(fpath)
                        if file_date and startdate <= file_date <= enddate:
                            files_found.append(fpath)
            return files_found

if __name__ == "__main__":
    import argparse

    filing_type_map = {
        "10-K": FilingType.FILING_10K,
        "10-Q": FilingType.FILING_10Q,
        "4": FilingType.FILING_4,
        "8-K": FilingType.FILING_8K,
        # Add more mappings as needed
    }

    parser = argparse.ArgumentParser(
        description="Download or list SEC filings for a given ticker and filing type."
    )
    parser.add_argument("--ticker", type=str, default="tsla", help="CIK or ticker symbol (default: tsla)")
    parser.add_argument("--filing-type", type=str, default="4", help="Filing type (e.g., 10-K, 4, etc. Default: 4)")
    parser.add_argument("--start-year", type=int, default=2010, help="Start year (default: 2010)")
    parser.add_argument("--end-year", type=int, default=2025, help="End year (default: 2025)")
    parser.add_argument("--start-month", type=int, default=1, help="Start month (default: 1)")
    parser.add_argument("--start-day", type=int, default=1, help="Start day (default: 1)")
    parser.add_argument("--end-month", type=int, default=5, help="End month (default: 5)")
    parser.add_argument("--end-day", type=int, default=12, help="End day (default: 12)")
    parser.add_argument("--list", action="store_true", help="List filings if they exist, otherwise download and list.")

    args = parser.parse_args()

    grabber = EdgarFileGrabber()
    filing_type = filing_type_map.get(args.filing_type.upper(), FilingType.FILING_4)
    startdate = date(args.start_year, args.start_month, args.start_day)
    enddate = date(args.end_year, args.end_month, args.end_day)

    files = grabber.get_company_filings(args.ticker, filing_type, startdate, enddate)
    print("Files:", files)
