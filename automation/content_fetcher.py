"""
Simple content fetcher using crawl4ai
Extracted from api/agent_runner.py for use in automation
"""

import asyncio
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
        
        # Wrap entire crawl in asyncio timeout to prevent hanging
        async def _fetch():
            async with AsyncWebCrawler(
                browser_type="chromium",
                headless=True,
                verbose=False
            ) as crawler:
                result = await crawler.arun(url=url, bypass_cache=True)
                return result.markdown
        
        # Force timeout at application level
        return await asyncio.wait_for(_fetch(), timeout=timeout)
        
    except asyncio.TimeoutError:
        print(f"  Timeout ({timeout}s) fetching {url[:60]}...")
        return None
    except Exception as e:
        # Show shorter error message
        error_msg = str(e)[:100]
        print(f"  Error fetching {url[:60]}...: {error_msg}")
        return None
