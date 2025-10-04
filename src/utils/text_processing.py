# Text Processing Utilities

import re
from typing import Optional


# HTML Tag Removal
def strip_html_tags(text: str) -> str:
    """
    Remove HTML tags from text

    Args:
        text: Text with HTML tags

    Returns:
        Clean text
    """
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


# Text Cleaning
def clean_text(text: str) -> str:
    """
    Clean and normalize text

    Args:
        text: Raw text

    Returns:
        Cleaned text
    """
    # Remove HTML tags
    text = strip_html_tags(text)

    # Remove extra whitespace
    text = ' '.join(text.split())

    # Remove special characters but keep punctuation
    text = re.sub(r'[^\w\s\.\,\!\?\-\:\;\']', '', text)

    return text.strip()


# Extract Domain from URL
def extract_domain(url: str) -> Optional[str]:
    """
    Extract domain from URL

    Args:
        url: Full URL

    Returns:
        Domain name or None
    """
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        return domain
    except:
        return None


# Truncate Text
def truncate_text(text: str, max_length: int = 500, suffix: str = '...') -> str:
    """
    Truncate text to maximum length

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)].rsplit(' ', 1)[0] + suffix


# Calculate Relevance Score
def calculate_relevance(title: str, content: str, company_name: str) -> float:
    """
    Calculate relevance score based on keyword matching

    Args:
        title: News title
        content: News content
        company_name: Company name to match

    Returns:
        Relevance score (0.0 to 1.0)
    """
    score = 0.0
    company_lower = company_name.lower()

    # Title contains company name (high weight)
    if company_lower in title.lower():
        score += 0.5

    # Content contains company name
    content_lower = content.lower()
    occurrences = content_lower.count(company_lower)

    if occurrences > 0:
        score += min(0.5, occurrences * 0.1)

    return min(score, 1.0)
