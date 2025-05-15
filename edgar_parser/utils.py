"""
EDGAR Parser Utilities Module

Utility functions for the EDGAR parser.
"""

from typing import Tuple, List, Dict, Any, Optional
import os
import chardet
import logging


def read_file_with_encoding(file_path: str, logger: logging.Logger) -> Tuple[str, str]:
    """
    Reads file content with proper encoding detection.
    
    Args:
        file_path (str): Path to the file
        logger (logging.Logger): Logger instance
        
    Returns:
        Tuple[str, str]: File content and detected encoding
    """
    # First try to detect encoding
    with open(file_path, 'rb') as raw_file:
        raw_data = raw_file.read(min(1024*1024, os.path.getsize(file_path)))  # Read up to 1MB for detection
        result = chardet.detect(raw_data)
        encoding = result['encoding']
        confidence = result['confidence']
        
    # Try detected encoding, falling back to latin1 and utf-8 if needed
    encodings_to_try = [encoding, 'latin1', 'utf-8']
    
    for enc in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=enc) as file:
                content = file.read()
            logger.info(f"Successfully read file with {enc} encoding (confidence: {confidence if enc == encoding else 'fallback'})")
            return content, enc
        except UnicodeDecodeError:
            logger.warning(f"Failed to decode with {enc}, trying next encoding")
    
    # If all fail, use latin1 with error handling
    with open(file_path, 'r', encoding='latin1', errors='replace') as file:
        content = file.read()
    logger.warning("Used latin1 with error replacement as last resort")
    return content, "latin1 (with errors)"


def clean_filename(name: str, max_length: int = 50) -> str:
    """
    Creates a clean, safe filename from a string.
    
    Args:
        name (str): Original name
        max_length (int): Maximum filename length
        
    Returns:
        str: Clean filename
    """
    # Replace non-alphanumeric characters with underscores
    safe_name = "".join(c if c.isalnum() or c in ['-', '_'] else '_' for c in str(name))
    
    # Limit length
    return safe_name[:max_length]

# ToDo: Refactor the package code to use those functions. Currently they are not user since similar code exists inline in edgar_parese package files 
def ensure_dir(directory: str) -> None:
    """
    Ensures a directory exists, creating it if necessary.
    
    Args:
        directory (str): Directory path
    """
    os.makedirs(directory, exist_ok=True)


def get_filing_type_sections(config: Dict[str, Any], filing_type: str) -> List[str]:
    """
    Gets the section names for a specific filing type from config.
    
    Args:
        config (Dict[str, Any]): Configuration dictionary
        filing_type (str): Filing type code (e.g., "10-K")
        
    Returns:
        List[str]: List of section names
    """
    sections = []
    filing_profiles = config.get("EdgarParser", {}).get("FilingTypeProfiles", {})
    
    if filing_type in filing_profiles:
        profile = filing_profiles[filing_type]
        for section_type, section_names in profile.items():
            if isinstance(section_names, list):
                sections.extend(section_names)
                
    return sections
