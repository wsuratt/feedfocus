"""
Simple content fetcher using crawl4ai
Extracted from api/agent_runner.py for use in automation
"""

from crawl4ai import AsyncWebCrawler


async def fetch_content_sample(url: str) -> str:
    """
    Fetch web content and convert to markdown
    
    Args:
        url: URL to fetch
    
    Returns:
        Markdown content or None if fetch fails
    """
    try:
        if url.lower().endswith('.pdf'):
            return None
            
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            return result.markdown
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None
