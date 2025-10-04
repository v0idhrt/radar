# News Deduplication Utilities

from typing import List, Dict
from difflib import SequenceMatcher
from urllib.parse import urlparse
import hashlib

from src.models.news import News


# URL Normalization
def normalize_url(url: str) -> str:
    """
    Normalize URL for comparison

    Args:
        url: URL to normalize

    Returns:
        Normalized URL
    """
    parsed = urlparse(url)
    # Remove www, trailing slashes, query params
    domain = parsed.netloc.replace('www.', '')
    path = parsed.path.rstrip('/')
    return f"{parsed.scheme}://{domain}{path}"


# Text Similarity
def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate text similarity using SequenceMatcher

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score (0.0 to 1.0)
    """
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


# Deduplication by URL
def deduplicate_by_url(news_list: List[News]) -> List[News]:
    """
    Remove duplicate news items by URL

    Args:
        news_list: List of news items

    Returns:
        Deduplicated list
    """
    seen_urls = set()
    deduplicated = []

    for news in news_list:
        normalized = normalize_url(news.url)
        if normalized not in seen_urls:
            seen_urls.add(normalized)
            deduplicated.append(news)

    return deduplicated


# Deduplication by Content Similarity with clustering
def deduplicate_by_content(news_list: List[News], threshold: float = 0.85) -> List[News]:
    """
    Remove duplicate news by content similarity and assign dedup_group

    Args:
        news_list: List of news items
        threshold: Similarity threshold (0.0 to 1.0)

    Returns:
        Deduplicated list with dedup_group assigned
    """
    deduplicated = []
    dedup_groups: Dict[int, str] = {}  # index -> group_id

    for i, news in enumerate(news_list):
        is_duplicate = False
        matched_group = None

        for j, existing in enumerate(deduplicated):
            # Compare titles and content
            title_sim = calculate_similarity(news.title, existing.title)
            content_sim = calculate_similarity(news.content, existing.content)

            # If both are similar, consider as duplicate
            if title_sim >= threshold or content_sim >= threshold:
                is_duplicate = True
                # Get the group of the matched item
                matched_group = dedup_groups.get(j)
                break

        if not is_duplicate:
            # Create new dedup_group for this item
            group_id = _generate_group_id(news.url, news.title)
            news.dedup_group = group_id
            dedup_groups[len(deduplicated)] = group_id
            deduplicated.append(news)
        else:
            # This is a duplicate, assign it to the matched group
            if matched_group:
                news.dedup_group = matched_group

    return deduplicated


def _generate_group_id(url: str, title: str) -> str:
    """Generate unique group ID based on URL and title"""
    content = f"{url}|{title}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()[:16]


# Full Deduplication
def deduplicate_news(news_list: List[News], similarity_threshold: float = 0.85) -> List[News]:
    """
    Comprehensive deduplication by URL and content with dedup_group assignment

    Args:
        news_list: List of news items
        similarity_threshold: Content similarity threshold

    Returns:
        Fully deduplicated list with dedup_group assigned
    """
    # First pass: Remove exact URL duplicates and assign initial dedup_groups
    url_deduplicated = []
    url_groups: Dict[str, str] = {}  # normalized_url -> group_id
    
    for news in news_list:
        normalized = normalize_url(news.url)
        if normalized not in url_groups:
            # New unique URL
            group_id = _generate_group_id(news.url, news.title)
            news.dedup_group = group_id
            url_groups[normalized] = group_id
            url_deduplicated.append(news)
        else:
            # Duplicate URL - assign to same group
            news.dedup_group = url_groups[normalized]

    # Second pass: Remove content duplicates and merge dedup_groups
    content_deduplicated = deduplicate_by_content(url_deduplicated, similarity_threshold)

    return content_deduplicated


# Sort by Relevance
def sort_by_relevance(news_list: List[News]) -> List[News]:
    """
    Sort news by relevance score and date

    Args:
        news_list: List of news items

    Returns:
        Sorted list
    """
    return sorted(
        news_list,
        key=lambda x: (
            x.relevance_score or 0,
            x.publish_date or x.collected_at
        ),
        reverse=True
    )
