"""
Simple content fetcher using crawl4ai
Extracted from api/agent_runner.py for use in automation
"""

from crawl4ai import AsyncWebCrawler


async def fetch_content_sample(url: str, timeout: int = 30) -> str:
    """
    Fetch web content and convert to markdown
    
    Args:
        url: URL to fetch
        timeout: Timeout in seconds (default 30s)
    
    Returns:
        Markdown content or None if fetch fails
    """
    try:
        if url.lower().endswith('.pdf'):
            return None
            
        async with AsyncWebCrawler(
            browser_type="chromium",
            headless=True,
            verbose=False
        ) as crawler:
            # Add timeout to prevent hanging
            result = await crawler.arun(
                url=url,
                page_timeout=timeout * 1000,  # Convert to milliseconds
                bypass_cache=True
            )
            return result.markdown
    except Exception as e:
        # Show shorter error message
        error_msg = str(e)[:100]
        print(f"  Error fetching {url}: {error_msg}")
        return None
