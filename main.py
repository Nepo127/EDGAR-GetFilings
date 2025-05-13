from datetime import date
import toml
#import date
from secedgar import FilingType, CompanyFilings

# Load configuration from config.toml
config = toml.load("config.toml")
cik = "tsla"
filing_type = FilingType.FILING_10K
startdate = date(2010, 1, 1)
enddate = date(2025, 5, 12)
filing = CompanyFilings(cik_lookup=cik,
                        filing_type=filing_type,
                        start_date=startdate,
                        end_date=enddate,
                        user_agent="Horia Suciu (suciu.horia@gmail.com)")
    #user_agent=config["SEC_EDGAR_USER_AGENT"])
# Todo - use the SEC_EDGAR_USER_AGENT from config.toml
                    
if __name__ == "__main__":
    print("Configuration Loaded:", config)
    print(f"Downloading filings for CIK: {cik}, Type: {filing_type}, Start Date: {startdate}, End Date: {enddate}")
    filing.save("/Users/horiasuciu/Projects/Python/DataCollectionScripts/EDGAR-GetFilings/saved-data")

    #print("Filings downloaded and saved successfully.")
