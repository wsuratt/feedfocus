"""
Search provider abstraction for source discovery
Supports DuckDuckGo (free) and Exa AI (faster, paid) providers
Switch via SEARCH_PROVIDER env variable: "duckduckgo" or "exa"
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Protocol
from dotenv import load_dotenv

load_dotenv()


@dataclass
class SearchResult:
    """Standardized search result across all providers"""
    url: str
    title: str
    description: str = ""
    content: Optional[str] = None
    published_date: Optional[datetime] = None
    highlights: List[str] = field(default_factory=list)
    is_preferred_domain: bool = False
    query: str = ""


class SearchProvider(ABC):
    """Abstract base class for search providers"""

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 20,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
    ) -> List[SearchResult]:
        """
        Search for sources matching the query

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            include_domains: Only include results from these domains
            exclude_domains: Exclude results from these domains
            start_date: Only include results published after this date

        Returns:
            List of SearchResult objects
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging"""
        pass

    @property
    @abstractmethod
    def fetches_content(self) -> bool:
        """Whether this provider returns content with search results"""
        pass


class DuckDuckGoProvider(SearchProvider):
    """DuckDuckGo search provider using ddgs library"""

    @property
    def name(self) -> str:
        return "DuckDuckGo"

    @property
    def fetches_content(self) -> bool:
        return False

    async def search(
        self,
        query: str,
        max_results: int = 20,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
    ) -> List[SearchResult]:
        from ddgs import DDGS

        results = []
        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=max_results))

                for result in raw_results:
                    url = result.get('href', '')
                    url_lower = url.lower()

                    if exclude_domains:
                        if any(domain in url_lower for domain in exclude_domains):
                            continue

                    is_preferred = False
                    if include_domains:
                        is_preferred = any(domain in url_lower for domain in include_domains)

                    results.append(SearchResult(
                        url=url,
                        title=result.get('title', ''),
                        description=result.get('body', ''),
                        is_preferred_domain=is_preferred,
                        query=query,
                    ))

        except Exception as e:
            print(f"  DuckDuckGo search error: {e}")

        return results


class ExaProvider(SearchProvider):
    """Exa AI search provider - faster with content fetching included"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("EXA_API_KEY")
        if not self.api_key:
            raise ValueError("EXA_API_KEY environment variable not set")

        try:
            from exa_py import Exa
            self.client = Exa(api_key=self.api_key)
        except ImportError:
            raise ImportError("exa_py package not installed. Run: pip install exa_py")

    @property
    def name(self) -> str:
        return "Exa AI"

    @property
    def fetches_content(self) -> bool:
        return True

    async def search(
        self,
        query: str,
        max_results: int = 20,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
    ) -> List[SearchResult]:
        results = []

        try:
            search_params = {
                "query": query,
                "num_results": max_results,
                "type": "auto",
                "text": True,
                "highlights": True,
            }

            if include_domains:
                search_params["include_domains"] = include_domains

            if exclude_domains:
                search_params["exclude_domains"] = exclude_domains

            if start_date:
                search_params["start_published_date"] = start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")

            response = self.client.search_and_contents(**search_params)

            for result in response.results:
                published_date = None
                if hasattr(result, 'published_date') and result.published_date:
                    try:
                        published_date = datetime.fromisoformat(
                            result.published_date.replace('Z', '+00:00')
                        )
                    except (ValueError, AttributeError):
                        pass

                url_lower = result.url.lower()
                is_preferred = False
                if include_domains:
                    is_preferred = any(domain in url_lower for domain in include_domains)

                highlights = []
                if hasattr(result, 'highlights') and result.highlights:
                    highlights = result.highlights

                results.append(SearchResult(
                    url=result.url,
                    title=getattr(result, 'title', '') or '',
                    description=getattr(result, 'summary', '') or '',
                    content=getattr(result, 'text', None),
                    published_date=published_date,
                    highlights=highlights,
                    is_preferred_domain=is_preferred,
                    query=query,
                ))

        except Exception as e:
            print(f"  Exa search error: {e}")

        return results


def get_search_provider(provider_name: Optional[str] = None) -> SearchProvider:
    """
    Factory function to get the appropriate search provider

    Args:
        provider_name: "duckduckgo" or "exa". If None, reads from SEARCH_PROVIDER env var.

    Returns:
        SearchProvider instance
    """
    if provider_name is None:
        provider_name = os.environ.get("SEARCH_PROVIDER", "duckduckgo").lower()

    provider_name = provider_name.lower().strip()

    if provider_name == "exa":
        return ExaProvider()
    elif provider_name in ("duckduckgo", "ddg"):
        return DuckDuckGoProvider()
    else:
        print(f"  Unknown provider '{provider_name}', defaulting to DuckDuckGo")
        return DuckDuckGoProvider()
