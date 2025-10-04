# Base Search API Class

from abc import ABC, abstractmethod
from typing import List, Optional, Union
from datetime import datetime, timezone, timedelta
import requests
import re
import time
import html
import asyncio
from dateutil import parser as date_parser
from bs4 import BeautifulSoup

from src.models.news import News
from src.core.config import config
from src.core.rate_limiter import get_rate_limiters
from ..logging_service import get_logger

logger = get_logger(__name__)

# Глобальный rate limiter
rate_limiters = get_rate_limiters()


# Base Search Service
class BaseSearchService(ABC):
    """Abstract base class for search API services"""

    def __init__(self):
        self.timeout = config.REQUEST_TIMEOUT
        self.user_agent = config.USER_AGENT
        self.deep_search = config.DEEP_SEARCH
        base_max_results = config.MAX_RESULTS_PER_SOURCE
        self.max_results = base_max_results * 2 if self.deep_search else base_max_results
        base_max_retries = config.MAX_RETRIES
        self.max_retries = base_max_retries + 2 if self.deep_search else base_max_retries
        self.retry_delay = config.RETRY_DELAY
        self.fetch_full_content = config.FETCH_FULL_ARTICLE_CONTENT
        self.preferred_domains = self._parse_domains(config.PREFERRED_NEWS_DOMAINS)

    @abstractmethod
    def search(
        self,
        company_name: str,
        max_results: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[News]:
        """
        Search for news about a company

        Args:
            company_name: Name of the company to search for
            max_results: Maximum number of results to return
            start_date: Optional start date for search results
            end_date: Optional end date for search results

        Returns:
            List of News objects
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the service is properly configured with API keys"""
        pass

    async def _make_request_async(self, url: str, api_name: str, params: dict = None, headers: dict = None) -> Optional[dict]:
        """
        Make HTTP request with rate limiting, error handling and retry logic

        Args:
            url: URL to request
            api_name: API name for rate limiting (e.g., 'google', 'serper')
            params: Query parameters
            headers: HTTP headers

        Returns:
            JSON response or None on error
        """
        default_headers = {'User-Agent': self.user_agent}
        if headers:
            default_headers.update(headers)

        for attempt in range(self.max_retries):
            try:
                # Wait for rate limit
                await rate_limiters.acquire(api_name, wait=True)
                
                logger.debug(
                    "HTTP запрос (попытка %s/%s): %s, params=%s",
                    attempt + 1, self.max_retries, url, params
                )
                response = requests.get(
                    url,
                    params=params,
                    headers=default_headers,
                    timeout=self.timeout
                )
                response.raise_for_status()
                logger.debug(
                    "Получен ответ %s для %s", response.status_code, url
                )
                return response.json()

            except requests.exceptions.RequestException as e:
                is_last_attempt = (attempt == self.max_retries - 1)

                if is_last_attempt:
                    logger.error(
                        "Ошибка HTTP-запроса после %s попыток: %s",
                        self.max_retries, e, exc_info=e
                    )
                    return None
                else:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        "Ошибка HTTP-запроса (попытка %s/%s): %s. Повтор через %s сек",
                        attempt + 1, self.max_retries, e, delay
                    )
                    await asyncio.sleep(delay)

        return None
    
    def _make_request(self, url: str, params: dict = None, headers: dict = None) -> Optional[dict]:
        """
        Synchronous wrapper for _make_request_async (deprecated, use async version)
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Determine API name from URL
        api_name = 'default'
        if 'google' in url:
            api_name = 'google'
        elif 'serper' in url:
            api_name = 'serper'
        elif 'yandex' in url or 'ya.ru' in url:
            api_name = 'yandex'
            
        return loop.run_until_complete(self._make_request_async(url, api_name, params, headers))

    # --- Domain Filtering ---------------------------------------------------

    def _parse_domains(self, domains_str: str) -> List[str]:
        """
        Parse comma-separated domains string into list

        Args:
            domains_str: Comma-separated domains

        Returns:
            List of domain strings
        """
        if not domains_str or not domains_str.strip():
            return []

        domains = [d.strip() for d in domains_str.split(',') if d.strip()]
        return domains

    def _apply_site_filters(self, query: str, domains: Optional[List[str]]) -> str:
        """Apply site-specific filters to query if domains provided."""
        # If domains is explicitly None or empty, don't apply filters
        if domains is None or not domains:
            return query.strip()

        site_operators = " OR ".join([f"site:{domain}" for domain in domains])
        query_part = query.strip()
        return f"({site_operators}) {query_part}".strip() if query_part else f"({site_operators})"

    def _build_site_query(self, subject: str, tail: str = "новости", domains: Optional[List[str]] = None) -> str:
        """
        Build search query with site-specific operators

        Args:
            subject: Core subject to search (company name or phrase)
            tail: Optional suffix to append (e.g. "новости")
            domains: Optional subset of preferred domains to include.
                    If None, no site filters are applied.
                    If empty list, no site filters are applied.
                    If list with domains, site filters are applied.

        Returns:
            Enhanced query string with site operators (or plain query if domains=None)
        """
        components: List[str] = []
        if subject and subject.strip():
            components.append(subject.strip())
        if tail and tail.strip():
            components.append(tail.strip())

        base_query = " ".join(components)
        return self._apply_site_filters(base_query, domains=domains)

    def _get_domain_chunks(self) -> List[Optional[List[str]]]:
        """Return domain subsets to use when building queries."""
        if not self.preferred_domains:
            return [None]
        return [self.preferred_domains]

    def _build_query_variants(self, company_name: str) -> List[str]:
        """Generate query variations to widen search coverage when deep search enabled."""
        domain_chunks = self._get_domain_chunks()
        variations: List[str] = []
        max_query_length = 400  # Yandex and Serper limit

        for domains in domain_chunks:
            base_query = self._build_site_query(company_name, domains=domains)
            variations.append(self._truncate_query(base_query, max_query_length))

            if not self.deep_search:
                continue

            variations.extend([
                self._truncate_query(self._build_site_query(f'"{company_name}"', domains=domains), max_query_length),
                self._truncate_query(self._build_site_query(company_name, tail="", domains=domains), max_query_length),
                self._truncate_query(self._build_site_query(f'"{company_name}"', tail="", domains=domains), max_query_length),
                self._truncate_query(self._apply_site_filters(f"{company_name} пресс релиз", domains=domains), max_query_length),
                self._truncate_query(self._apply_site_filters(f"{company_name} отчёт", domains=domains), max_query_length),
                self._truncate_query(self._apply_site_filters(f"{company_name} инвесторы", domains=domains), max_query_length),
                self._truncate_query(self._apply_site_filters(f"{company_name} news", domains=domains), max_query_length),
                self._truncate_query(self._apply_site_filters(f'"{company_name}" news', domains=domains), max_query_length),
                self._truncate_query(self._apply_site_filters(f"{company_name} press release", domains=domains), max_query_length),
                self._truncate_query(self._apply_site_filters(f"{company_name} earnings", domains=domains), max_query_length),
            ])

        seen = set()
        unique_variations: List[str] = []
        for query in variations:
            normalized = (query or "").strip()
            if normalized and normalized not in seen:
                unique_variations.append(normalized)
                seen.add(normalized)

        # ensure at least a basic query is returned
        if not unique_variations:
            unique_variations.append(company_name)

        return unique_variations

    def _truncate_query(self, query: str, max_length: int) -> str:
        """
        Truncate query to max length while preserving site operators
        
        Args:
            query: Search query
            max_length: Maximum allowed length
            
        Returns:
            Truncated query
        """
        if len(query) <= max_length:
            return query
        
        # If query has site operators, try to reduce domains
        if 'site:' in query:
            # Split into site operators and main query
            parts = query.split(')')
            if len(parts) >= 2:
                site_part = parts[0] + ')'
                main_part = ')'.join(parts[1:])
                
                # If site part is too long, reduce domains
                if len(site_part) > max_length - len(main_part) - 10:
                    # Extract individual site operators
                    sites = [s.strip() for s in site_part.strip('()').split(' OR ') if 'site:' in s]
                    
                    # Reduce number of sites to fit
                    reduced_sites = []
                    current_length = len(main_part) + 10  # reserve space for parentheses and main query
                    
                    for site in sites:
                        if current_length + len(site) + 4 <= max_length:  # +4 for " OR "
                            reduced_sites.append(site)
                            current_length += len(site) + 4
                        else:
                            break
                    
                    if reduced_sites:
                        new_site_part = f"({' OR '.join(reduced_sites)})"
                        return f"{new_site_part}{main_part}".strip()
        
        # Simple truncation if no site operators or can't reduce
        return query[:max_length].strip()

    # --- Text Cleaning ---------------------------------------------------

    def _clean_text(self, text: str) -> str:
        """
        Clean text from HTML entities, special symbols, and extra whitespace

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Decode HTML entities (&amp; -> &, &quot; -> ", etc.)
        text = html.unescape(text)

        # Remove HTML tags (if any left)
        text = re.sub(r'<[^>]+>', '', text)

        # Remove common artifacts
        text = re.sub(r'\xa0', ' ', text)  # Non-breaking space
        text = re.sub(r'\u200b', '', text)  # Zero-width space
        text = re.sub(r'\u200c', '', text)  # Zero-width non-joiner
        text = re.sub(r'\u200d', '', text)  # Zero-width joiner
        text = re.sub(r'\ufeff', '', text)  # Zero-width no-break space (BOM)

        # Remove special quotes and replace with standard ones
        text = re.sub(r'[""„‟]', '"', text)
        text = re.sub(r'[''‚‛]', "'", text)

        # Remove ellipsis artifacts
        text = re.sub(r'\.{3,}', '...', text)
        text = re.sub(r'…+', '...', text)

        # Remove multiple dashes
        text = re.sub(r'[-—–]{2,}', '—', text)

        # Remove control characters (except newlines and tabs)
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)

        # Normalize whitespace
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines to double

        # Remove leading/trailing whitespace on each line
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)

        # Final trim
        text = text.strip()

        return text

    # --- Full Article Extraction ---------------------------------------------------

    def _fetch_full_article_content(self, url: str) -> Optional[str]:
        """
        Fetch and extract full article content from URL using multiple strategies

        Args:
            url: Article URL

        Returns:
            Tuple of (full article text, publish date from HTML) or (None, None) if extraction fails
        """
        try:
            logger.debug("Извлечение полного текста из: %s", url)

            response = requests.get(
                url,
                headers={'User-Agent': self.user_agent},
                timeout=self.timeout,
                allow_redirects=True
            )
            response.raise_for_status()

            html_content = response.content
            soup = BeautifulSoup(html_content, 'html.parser')

            # Try to extract publish date from HTML meta tags
            publish_date = self._extract_date_from_html(soup)

            # Strategy 1: Try trafilatura (best for news articles)
            article_text = self._extract_with_trafilatura(html_content, url)
            
            # Strategy 2: Try JSON-LD structured data
            if not article_text or len(article_text) < 200:
                article_text = self._extract_from_json_ld(soup)
            
            # Strategy 3: Use enhanced BeautifulSoup extraction
            if not article_text or len(article_text) < 200:
                article_text = self._extract_with_beautifulsoup(soup)

            # Clean up and validate result
            if article_text:
                article_text = self._clean_text(article_text)
                if len(article_text) > 100:  # Ensure we got meaningful content
                    logger.debug("Извлечено %s символов из %s", len(article_text), url)
                    return article_text, publish_date

            logger.debug("Не удалось извлечь содержимое из %s", url)
            return None, publish_date

        except Exception as e:
            logger.warning("Ошибка извлечения полного текста из %s: %s", url, e)
            return None, None

    def _extract_with_trafilatura(self, html_content: bytes, url: str) -> Optional[str]:
        """Extract article text using trafilatura library"""
        try:
            import trafilatura
            
            # Extract with all available features
            text = trafilatura.extract(
                html_content,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
                favor_precision=False,  # Favor recall to get more content
                favor_recall=True,
                url=url
            )
            
            if text and len(text) > 200:
                logger.debug("Trafilatura извлёк %s символов", len(text))
                return text
                
        except ImportError:
            logger.debug("Trafilatura не установлен, пропуск")
        except Exception as e:
            logger.debug("Ошибка trafilatura: %s", e)
        
        return None

    def _extract_from_json_ld(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract article text from JSON-LD structured data"""
        try:
            import json
            
            # Find all JSON-LD scripts
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    
                    # Handle both single objects and arrays
                    items = [data] if isinstance(data, dict) else data
                    
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        
                        # Check for NewsArticle, Article, BlogPosting types
                        item_type = item.get('@type', '').lower()
                        if any(t in item_type for t in ['article', 'newsarticle', 'blogposting']):
                            # Try to get article body
                            article_body = item.get('articleBody') or item.get('text')
                            if article_body and len(article_body) > 200:
                                logger.debug("JSON-LD извлёк %s символов", len(article_body))
                                return article_body
                            
                except (json.JSONDecodeError, AttributeError) as e:
                    logger.debug("Ошибка парсинга JSON-LD: %s", e)
                    continue
                    
        except Exception as e:
            logger.debug("Ошибка извлечения JSON-LD: %s", e)
        
        return None

    def _extract_with_beautifulsoup(self, soup: BeautifulSoup) -> Optional[str]:
        """Enhanced BeautifulSoup extraction with aggressive filtering"""
        try:
            # Remove unwanted elements (expanded list)
            for element in soup([
                'script', 'style', 'nav', 'header', 'footer', 'aside',
                'iframe', 'noscript', 'form', 'button', 'input', 'select', 'textarea',
                # Navigation and menus
                '[class*="menu"]', '[class*="nav"]', '[id*="menu"]', '[id*="nav"]',
                '[class*="breadcrumb"]', '[class*="pagination"]',
                # Common ad and social media classes
                '[class*="ad-"]', '[class*="advertisement"]', '[class*="social"]',
                '[class*="share"]', '[class*="comment"]', '[id*="comment"]',
                '[class*="sidebar"]', '[class*="widget"]', '[class*="related"]',
                '[class*="recommend"]', '[class*="promo"]', '[class*="banner"]',
                # Metadata and author info
                '[class*="meta"]', '[class*="author"]', '[class*="byline"]',
                '[class*="tags"]', '[class*="category"]',
                # Footer and copyright
                '[class*="footer"]', '[class*="copyright"]', '[id*="footer"]',
                # Lists of other articles
                '[class*="list"]', '[class*="feed"]', '[class*="grid"]',
                # Subscribe and newsletter
                '[class*="subscribe"]', '[class*="newsletter"]', '[class*="signup"]'
            ]):
                element.decompose()

            # Extended list of article content selectors
            article_selectors = [
                # Semantic HTML5
                'article',
                '[role="main"]',
                'main',
                # Common content classes
                '.article-content',
                '.article__content',
                '.article-body',
                '.article__body',
                '.post-content',
                '.post__content',
                '.entry-content',
                '.news-content',
                '.news__content',
                '.story-body',
                '.story__body',
                '.text-body',
                '.content-body',
                # Generic content areas
                '#content',
                '.content',
                '#main-content',
                '.main-content',
                # Russian news sites specific
                '.article_text',
                '.news_text',
                '.material-text',
                '.publication-text',
                '.text_content',
            ]

            article_text = None
            max_length = 0

            # Try each selector and keep the longest result
            for selector in article_selectors:
                try:
                    article_elem = soup.select_one(selector)
                    if article_elem:
                        # Remove nested navigation/lists within article
                        for nested in article_elem.select('ul, ol, nav, [class*="list"]'):
                            # Keep lists with long text items (real content)
                            if not self._is_content_list(nested):
                                nested.decompose()
                        
                        # Extract text from paragraphs and headings
                        paragraphs = article_elem.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                        if paragraphs:
                            filtered_paragraphs = []
                            for p in paragraphs:
                                text = p.get_text(separator=' ', strip=True)
                                # Skip if too short, too many links, or looks like navigation
                                if (len(text) > 40 and
                                    not self._is_navigation_text(text) and
                                    not self._has_too_many_links(p)):
                                    filtered_paragraphs.append(text)
                            
                            text = '\n\n'.join(filtered_paragraphs)
                            if len(text) > max_length:
                                max_length = len(text)
                                article_text = text
                                if max_length > 500:  # Good enough, stop searching
                                    break
                except Exception as e:
                    logger.debug("Ошибка селектора %s: %s", selector, e)
                    continue

            # Fallback: extract all meaningful paragraphs from body
            if not article_text or len(article_text) < 200:
                body = soup.find('body')
                if body:
                    paragraphs = body.find_all('p')
                    # Filter out short paragraphs, navigation, and link-heavy content
                    meaningful_paragraphs = [
                        p.get_text(separator=' ', strip=True)
                        for p in paragraphs
                        if (p.get_text(strip=True) and
                            len(p.get_text(strip=True)) > 50 and
                            not self._is_navigation_text(p.get_text(strip=True)) and
                            not self._has_too_many_links(p))
                    ]
                    if meaningful_paragraphs:
                        article_text = '\n\n'.join(meaningful_paragraphs)

            if article_text and len(article_text) > 200:
                # Final cleanup: remove isolated dates and metadata
                article_text = self._remove_metadata_noise(article_text)
                logger.debug("BeautifulSoup извлёк %s символов", len(article_text))
                return article_text

        except Exception as e:
            logger.debug("Ошибка BeautifulSoup extraction: %s", e)

        return None

    def _is_content_list(self, list_elem) -> bool:
        """Check if list contains actual content (not navigation)"""
        items = list_elem.find_all('li')
        if not items or len(items) > 20:  # Too many items = likely navigation
            return False
        
        # Check average item length
        total_length = sum(len(item.get_text(strip=True)) for item in items)
        avg_length = total_length / len(items) if items else 0
        return avg_length > 50  # Content items are usually longer

    def _has_too_many_links(self, elem) -> bool:
        """Check if element has too many links (likely navigation)"""
        text = elem.get_text(strip=True)
        if not text:
            return True
        
        links = elem.find_all('a')
        if not links:
            return False
        
        # Calculate ratio of link text to total text
        link_text_length = sum(len(a.get_text(strip=True)) for a in links)
        ratio = link_text_length / len(text) if text else 1
        return ratio > 0.6  # More than 60% links = navigation

    def _is_navigation_text(self, text: str) -> bool:
        """Check if text looks like navigation/menu"""
        text_lower = text.lower().strip()
        
        # Navigation keywords
        nav_keywords = [
            'главное', 'новости', 'главная', 'войти', 'регистрация',
            'подписаться', 'еще материалов', 'читать далее', 'подробнее',
            'все новости', 'все статьи', 'архив', 'рубрики', 'разделы',
            'контакты', 'о проекте', 'реклама', 'вакансии', 'партнеры',
            'политика конфиденциальности', 'пользовательское соглашение',
            'copyright', '©', 'все права защищены', 'редакция', 'подписка'
        ]
        
        # Check if text is mostly navigation keywords
        for keyword in nav_keywords:
            if keyword in text_lower and len(text) < 100:
                return True
        
        # Check for date-only lines
        if re.match(r'^[\d\.\-/\s:]+$', text) and len(text) < 30:
            return True
        
        # Check for short repetitive patterns (menu items)
        if len(text) < 50 and text.count('\n') == 0 and text.count('|') > 2:
            return True
        
        return False

    def _remove_metadata_noise(self, text: str) -> str:
        """Remove isolated metadata and noise from text"""
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip very short lines
            if len(line) < 20:
                continue
            
            # Skip lines that are just dates
            if re.match(r'^[\d\.\-/\s:]+$', line):
                continue
            
            # Skip copyright and footer lines
            if any(keyword in line.lower() for keyword in ['©', 'copyright', 'все права защищены', 'авторское право']):
                continue
            
            # Skip lines with too many numbers (likely metadata)
            num_count = sum(c.isdigit() for c in line)
            if num_count / len(line) > 0.5:
                continue
            
            cleaned_lines.append(line)
        
        return '\n\n'.join(cleaned_lines)

    def _extract_date_from_html(self, soup: BeautifulSoup) -> Optional[datetime]:
        """
        Extract publish date from HTML meta tags

        Args:
            soup: BeautifulSoup object

        Returns:
            Parsed datetime or None
        """
        # Meta tag selectors for date
        date_meta_tags = [
            ('meta', {'property': 'article:published_time'}),
            ('meta', {'property': 'og:published_time'}),
            ('meta', {'name': 'publication_date'}),
            ('meta', {'name': 'publishdate'}),
            ('meta', {'name': 'date'}),
            ('meta', {'itemprop': 'datePublished'}),
            ('time', {'datetime': True}),
        ]

        for tag_name, attrs in date_meta_tags:
            tag = soup.find(tag_name, attrs)
            if tag:
                # Get content from meta or datetime attribute
                date_str = tag.get('content') or tag.get('datetime')
                if date_str:
                    parsed = self._parse_date_value(date_str)
                    if parsed:
                        logger.debug("Дата из HTML meta: %s", parsed)
                        return parsed

        # Try to find date in common article date elements
        date_selectors = [
            '.article-date',
            '.publish-date',
            '.entry-date',
            'time',
            '.date',
        ]

        for selector in date_selectors:
            elem = soup.select_one(selector)
            if elem:
                date_str = elem.get_text(strip=True)
                parsed = self._parse_date_value(date_str)
                if parsed:
                    logger.debug("Дата из HTML элемента %s: %s", selector, parsed)
                    return parsed

        return None

    def _create_news_item(
        self,
        company_name: str,
        title: str,
        content: str,
        url: str,
        source: str,
        publish_date: Optional[datetime] = None
    ) -> News:
        """
        Create News object with common fields

        Args:
            company_name: Company name
            title: News title
            content: News content/snippet
            url: Source URL
            source: Source identifier
            publish_date: Publication date (if None, uses collected_at)

        Returns:
            News object
        """
        collected_at = datetime.now(timezone.utc)

        # Ensure publish_date is timezone-aware
        if publish_date and publish_date.tzinfo is None:
            publish_date = publish_date.replace(tzinfo=timezone.utc)

        # Fallback: if no publish_date found, use collected_at
        if not publish_date:
            publish_date = collected_at

        return News(
            company_name=company_name,
            title=title,
            content=content,
            url=url,
            source=source,
            publish_date=publish_date,
            collected_at=collected_at
        )

    # --- Date helpers ---------------------------------------------------

    def _parse_date_value(self, value: Optional[Union[str, int, float]]) -> Optional[datetime]:
        """Convert API date value (str/number) into timezone-aware datetime."""
        if value is None:
            return None

        if isinstance(value, (int, float)):
            try:
                ts = float(value)
                if ts > 1e12:  # milliseconds
                    ts /= 1000.0
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                return self._validate_date(dt)
            except Exception:
                return None

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None

            # Try Russian date formats first
            russian_date = self._parse_russian_date(text)
            if russian_date:
                return russian_date

            # Try absolute formats (allow fuzzy parsing for embedded dates)
            try:
                dt = date_parser.parse(text, fuzzy=True)
                if dt is not None:
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    # Validate: reject future dates or dates older than 2 years
                    validated = self._validate_date(dt)
                    if validated:
                        return validated
            except Exception:
                pass

            # Relative formats ("3 hours ago", "yesterday")
            return self._parse_relative_date(text)

        return None

    def _validate_date(self, dt: datetime) -> Optional[datetime]:
        """
        Validate parsed date - reject future dates and very old dates

        Args:
            dt: Parsed datetime

        Returns:
            Valid datetime or None
        """
        if not dt:
            return None

        now = datetime.now(timezone.utc)

        # Reject dates from the future (with 1 day tolerance for timezone issues)
        if dt > now + timedelta(days=1):
            logger.debug("Отклонена будущая дата: %s", dt)
            return None

        # Reject dates older than 2 years (likely parsing error)
        two_years_ago = now - timedelta(days=730)
        if dt < two_years_ago:
            logger.debug("Отклонена слишком старая дата: %s", dt)
            return None

        return dt

    def _parse_russian_date(self, text: str) -> Optional[datetime]:
        """
        Parse Russian date formats

        Args:
            text: Date string

        Returns:
            Parsed datetime or None
        """
        now = datetime.now(timezone.utc)
        text_lower = text.lower().strip()

        # Month mapping
        months_ru = {
            'января': 1, 'янв': 1,
            'февраля': 2, 'фев': 2,
            'марта': 3, 'мар': 3,
            'апреля': 4, 'апр': 4,
            'мая': 5, 'май': 5,
            'июня': 6, 'июн': 6,
            'июля': 7, 'июл': 7,
            'августа': 8, 'авг': 8,
            'сентября': 9, 'сен': 9,
            'октября': 10, 'окт': 10,
            'ноября': 11, 'ноя': 11,
            'декабря': 12, 'дек': 12,
        }

        # Format: "16 сентября 2025" или "16 сент 2025"
        pattern1 = r'(\d{1,2})\s+(' + '|'.join(months_ru.keys()) + r')\.?\s+(\d{4})'
        match = re.search(pattern1, text_lower)
        if match:
            day = int(match.group(1))
            month = months_ru[match.group(2).rstrip('.')]
            year = int(match.group(3))
            try:
                dt = datetime(year, month, day, tzinfo=timezone.utc)
                return self._validate_date(dt)
            except ValueError:
                pass

        # Format: "16 сентября" (без года - текущий год)
        pattern2 = r'(\d{1,2})\s+(' + '|'.join(months_ru.keys()) + r')\.?'
        match = re.search(pattern2, text_lower)
        if match:
            day = int(match.group(1))
            month = months_ru[match.group(2).rstrip('.')]
            year = now.year
            try:
                dt = datetime(year, month, day, tzinfo=timezone.utc)
                # If date is in future, use previous year
                if dt > now:
                    dt = dt.replace(year=year - 1)
                return self._validate_date(dt)
            except ValueError:
                pass

        # Format: "16.09.2025" или "16/09/2025"
        pattern3 = r'(\d{1,2})[./](\d{1,2})[./](\d{4})'
        match = re.search(pattern3, text_lower)
        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3))
            try:
                dt = datetime(year, month, day, tzinfo=timezone.utc)
                return self._validate_date(dt)
            except ValueError:
                pass

        # Format: "16.09" (без года)
        pattern4 = r'(\d{1,2})[./](\d{1,2})\b'
        match = re.search(pattern4, text_lower)
        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = now.year
            try:
                dt = datetime(year, month, day, tzinfo=timezone.utc)
                # If date is in future, use previous year
                if dt > now:
                    dt = dt.replace(year=year - 1)
                return self._validate_date(dt)
            except ValueError:
                pass

        return None

    def _parse_relative_date(self, text: str) -> Optional[datetime]:
        normalized = text.lower().strip()
        now = datetime.now(timezone.utc)

        if normalized in {"today", "just now", "now", "сейчас", "прямо сейчас", "только что", "на днях"}:
            return now
        if normalized in {"yesterday", "вчера"}:
            return now - timedelta(days=1)

        if "сегодня" in normalized:
            return now
        if "вчера" in normalized:
            return now - timedelta(days=1)

        match = re.match(r"(?:(\d+)|an|a)\s*([a-z]+)s?\s+ago", normalized)
        if match:
            num_str, unit = match.groups()
            count = int(num_str) if num_str else 1
            unit = unit.rstrip('s')

            multipliers = {
                'second': timedelta(seconds=1),
                'sec': timedelta(seconds=1),
                's': timedelta(seconds=1),
                'minute': timedelta(minutes=1),
                'min': timedelta(minutes=1),
                'hour': timedelta(hours=1),
                'hr': timedelta(hours=1),
                'h': timedelta(hours=1),
                'day': timedelta(days=1),
                'd': timedelta(days=1),
                'week': timedelta(weeks=1),
                'month': timedelta(days=30),
                'year': timedelta(days=365),
            }

            delta = multipliers.get(unit)
            if delta:
                return now - delta * count

        # Some providers use "3h ago", "5d ago" without space
        match = re.match(r"(\d+)([smhdw])\s*ago", normalized)
        if match:
            count = int(match.group(1))
            unit = match.group(2)
            mapping = {
                's': timedelta(seconds=1),
                'm': timedelta(minutes=1),
                'h': timedelta(hours=1),
                'd': timedelta(days=1),
                'w': timedelta(weeks=1),
            }
            delta = mapping.get(unit)
            if delta:
                return now - delta * count

        # Russian relative forms: "3 дня назад", "2 часа назад" etc.
        ru_match = re.search(r"(\d+)\s+(секунд[а-я]*|минут[а-я]*|час[а-я]*|дн[яейь]|сут[ок]|недел[юиь]|месяц[аев]?|год[аоув]?|лет)\s+назад", normalized)
        if ru_match:
            count = int(ru_match.group(1))
            unit = ru_match.group(2)
            ru_mapping = {
                'секунд': timedelta(seconds=1),
                'секунда': timedelta(seconds=1),
                'секунду': timedelta(seconds=1),
                'секундой': timedelta(seconds=1),
                'минут': timedelta(minutes=1),
                'минуту': timedelta(minutes=1),
                'минуты': timedelta(minutes=1),
                'минутой': timedelta(minutes=1),
                'час': timedelta(hours=1),
                'часа': timedelta(hours=1),
                'часов': timedelta(hours=1),
                'день': timedelta(days=1),
                'дня': timedelta(days=1),
                'дней': timedelta(days=1),
                'дн': timedelta(days=1),
                'суток': timedelta(days=1),
                'недель': timedelta(weeks=1),
                'неделю': timedelta(weeks=1),
                'недели': timedelta(weeks=1),
                'месяц': timedelta(days=30),
                'месяца': timedelta(days=30),
                'месяцев': timedelta(days=30),
                'год': timedelta(days=365),
                'года': timedelta(days=365),
                'лет': timedelta(days=365),
            }
            delta = None
            for key, value in ru_mapping.items():
                if unit.startswith(key):
                    delta = value
                    break
            if delta:
                return now - delta * count

        # Compact Russian forms like "3ч назад", "5д назад"
        ru_short = re.search(r"(\d+)([чсмдн])\s*назад", normalized)
        if ru_short:
            count = int(ru_short.group(1))
            unit = ru_short.group(2)
            mapping = {
                'с': timedelta(seconds=1),
                'м': timedelta(minutes=1),
                'ч': timedelta(hours=1),
                'д': timedelta(days=1),
                'н': timedelta(weeks=1),
            }
            delta = mapping.get(unit)
            if delta:
                return now - delta * count

        return None
