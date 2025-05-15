"""
EDGAR Section Extractor Module

Extracts document sections with hierarchical structure from SEC EDGAR filings.
"""

from typing import List, Dict, Any, Optional, Tuple
import re
import uuid
import logging
from bs4 import BeautifulSoup


class SectionExtractor:
    """Extracts document sections with hierarchical structure from SEC EDGAR filings."""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger) -> None:
        """
        Initialize the section extractor.
        
        Args:
            config (Dict[str, Any]): Configuration dictionary
            logger (logging.Logger): Logger instance
        """
        self.config = config
        self.logger = logger
    
    def extract_sections_with_hierarchy(self, html_text: str, cik: Optional[str], ticker: Optional[str]) -> List[Dict[str, Any]]:
        """
        Extracts sections based on heading hierarchy h1-h4.

        Args:
            html_text (str): Filing HTML content.
            cik (Optional[str]): Company CIK.
            ticker (Optional[str]): Company ticker.

        Returns:
            List[Dict[str, str]]: Extracted structured sections.
        """
        sections = []
        heading_stack = []
        current_section = {"title": "Document Start", "level": 0, "parent_title": None, "content": ""}
        section_counter = 1
        
        try:
            soup = BeautifulSoup(html_text, "lxml")
        except Exception as e:
            self.logger.warning(f"lxml parsing failed: {e}. Falling back to html.parser")
            soup = BeautifulSoup(html_text, "html.parser")
            
        # Find all heading tags
        heading_tags = soup.find_all(["h1", "h2", "h3", "h4", "h5", "strong", "b"])
        
        # Process HTML content by headings
        for tag in heading_tags:
            # Skip empty headings
            text_content = tag.get_text(strip=True)
            if not text_content:
                continue
                
            # Determine heading level
            if tag.name.startswith('h') and len(tag.name) == 2:
                # Standard heading tags
                level = int(tag.name[1])
            elif tag.name in ['strong', 'b']:
                # Special case: <strong> or <b> might be used as section headers in older filings
                # Check if standalone or in a smaller font/paragraph context
                parent = tag.parent
                if parent and parent.name == 'p' and len(parent.get_text(strip=True)) < 100:
                    level = 3  # Treat as h3 level
                else:
                    continue  # Skip non-heading bold/strong tags
            else:
                continue
                
            # Manage heading hierarchy
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            parent_title = heading_stack[-1][1] if heading_stack else None
            heading_stack.append((level, text_content))
            
            # Save previous section if it has content
            if current_section["content"]:
                # Clean up content
                cleaned_content = self._clean_section_content(current_section["content"])
                if cleaned_content:  # Only save non-empty sections
                    current_section["content"] = cleaned_content
                    current_section.update({
                        "uuid": str(uuid.uuid4()),
                        "cik": cik,
                        "ticker": ticker,
                        "section_number": section_counter
                    })
                    sections.append(current_section)
                    section_counter += 1
                    
            # Start new section
            current_section = {
                "title": text_content,
                "level": level,
                "parent_title": parent_title,
                "content": ""
            }
            
            # Collect content until next heading
            content_elements = []
            sibling = tag.next_sibling
            while sibling:
                if sibling.name in ["h1", "h2", "h3", "h4", "h5"]:
                    break
                if hasattr(sibling, 'get_text'):
                    content_elements.append(sibling.get_text(separator=" ", strip=True))
                elif isinstance(sibling, str) and sibling.strip():
                    content_elements.append(sibling.strip())
                sibling = sibling.next_sibling
                
            current_section["content"] = " ".join(content_elements)
            
        # Save the last section
        if current_section["content"]:
            cleaned_content = self._clean_section_content(current_section["content"])
            if cleaned_content:
                current_section["content"] = cleaned_content
                current_section.update({
                    "uuid": str(uuid.uuid4()),
                    "cik": cik,
                    "ticker": ticker,
                    "section_number": section_counter
                })
                sections.append(current_section)
                
        # If we couldn't extract sections by headings, try fallback approach
        if not sections:
            self.logger.info("No sections found using headings. Trying fallback approach.")
            sections = self._extract_sections_fallback(soup, cik, ticker)
            
        return sections
        
    def _clean_section_content(self, content: str) -> str:
        """
        Cleans section content by removing extra whitespace and normalizing text.
        
        Args:
            content (str): Raw section content
            
        Returns:
            str: Cleaned content
        """
        # Remove extra whitespace and normalize
        cleaned = re.sub(r'\s+', ' ', content).strip()
        
        # Remove common noise patterns
        noise_patterns = [
            r'\[\w+ Top\]',  # Navigation markers
            r'\[Table of Contents\]',
            r'\[Data_Table_start\].*?\[Data_Table_end\]',  # Table markers
            r'Click here to view',  # Interactive elements
        ]
        
        for pattern in noise_patterns:
            cleaned = re.sub(pattern, '', cleaned)
            
        return cleaned
        
    def _extract_sections_fallback(self, soup: BeautifulSoup, cik: Optional[str], ticker: Optional[str]) -> List[Dict[str, str]]:
        """
        Fallback method to extract sections when heading-based extraction fails.
        Uses large paragraphs and divs as section boundaries.
        
        Args:
            soup (BeautifulSoup): HTML soup object
            cik (Optional[str]): Company CIK
            ticker (Optional[str]): Company ticker
            
        Returns:
            List[Dict[str, str]]: Extracted sections
        """
        sections = []
        section_counter = 1
        
        # Look for common section indicators
        section_indicators = [
            "Item 1.", "Item 1A.", "Item 1B.", "Item 2.", "Item 3.", "Item 4.",
            "Item 5.", "Item 6.", "Item 7.", "Item 7A.", "Item 8.", "Item 9.",
            "Item 9A.", "Item 9B.", "Item 10.", "Item 11.", "Item 12.", "Item 13.",
            "Item 14.", "Item 15.",
            "PART I", "PART II", "PART III", "PART IV"
        ]
        
        # First try to find sections by "Item X" patterns (common in 10-K/10-Q)
        for indicator in section_indicators:
            elements = soup.find_all(text=re.compile(rf"{re.escape(indicator)}\s"))
            
            for element in elements:
                parent = element.parent
                if not parent:
                    continue
                    
                title = None
                content = []
                
                # Get the title - either the element itself or its parent's text
                if len(element.strip()) < 100:
                    title = element.strip()
                elif parent and len(parent.get_text(strip=True)) < 100:
                    title = parent.get_text(strip=True)
                    
                if not title:
                    continue
                    
                # Find content - all elements until the next section indicator
                next_elem = parent.next_sibling
                while next_elem:
                    # Stop if we hit another section indicator
                    if hasattr(next_elem, 'get_text'):
                        elem_text = next_elem.get_text(strip=True)
                        if any(ind in elem_text for ind in section_indicators):
                            break
                        content.append(elem_text)
                    elif isinstance(next_elem, str) and next_elem.strip():
                        if any(ind in next_elem for ind in section_indicators):
                            break
                        content.append(next_elem.strip())
                    next_elem = next_elem.next_sibling
                    
                if title and content:
                    content_text = " ".join(content)
                    cleaned_content = self._clean_section_content(content_text)
                    if cleaned_content:
                        sections.append({
                            "title": title,
                            "level": 1 if title.startswith("PART") else 2,
                            "parent_title": None,
                            "content": cleaned_content,
                            "uuid": str(uuid.uuid4()),
                            "cik": cik,
                            "ticker": ticker,
                            "section_number": section_counter
                        })
                        section_counter += 1
        
        # If still no sections, try dividing by large paragraphs
        if not sections:
            # Find all paragraphs
            paragraphs = soup.find_all('p')
            
            # Group into potential sections
            current_section = {
                "title": "Document Content",
                "level": 1,
                "parent_title": None,
                "content": ""
            }
            
            for p in paragraphs:
                text = p.get_text(strip=True)
                if not text:
                    continue
                    
                # If paragraph is short, it might be a heading
                if len(text) < 100 and text.isupper():
                    # Save previous section if it has content
                    if current_section["content"]:
                        cleaned_content = self._clean_section_content(current_section["content"])
                        if cleaned_content:
                            current_section.update({
                                "content": cleaned_content,
                                "uuid": str(uuid.uuid4()),
                                "cik": cik,
                                "ticker": ticker,
                                "section_number": section_counter
                            })
                            sections.append(current_section)
                            section_counter += 1
                            
                        # Start new section
                        current_section = {
                            "title": text,
                            "level": 1,
                            "parent_title": None,
                            "content": ""
                        }
                else:
                    # Add to current section content
                    current_section["content"] += " " + text
                    
            # Save last section
            if current_section["content"]:
                cleaned_content = self._clean_section_content(current_section["content"])
                if cleaned_content:
                    current_section.update({
                        "content": cleaned_content,
                        "uuid": str(uuid.uuid4()),
                        "cik": cik,
                        "ticker": ticker,
                        "section_number": section_counter
                    })
                    sections.append(current_section)
                    
        return sections
