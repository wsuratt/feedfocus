"""
Production source discovery module
Discovers and previews high-quality sources using dynamic search queries
"""

import asyncio
import re
from datetime import datetime
from ddgs import DDGS
from automation.content_fetcher import fetch_content_sample

# Tier 1 domains (highest quality - government, research, quality analysis)
TIER_1_DOMAINS = [
    # Government
    'bls.gov', 'census.gov', 'gao.gov', 'fed.gov', 'nih.gov',
    
    # Academic/Research
    'arxiv.org', 'nber.org', 'ssrn.com', 'pubmed.gov',
    
    # Think tanks
    'pewresearch.org', 'brookings.edu', 'rand.org', 'carnegieendowment.org',
    
    # Quality consulting
    'mckinsey.com', 'bcg.com', 'bain.com', 'deloitte.com',
    
    # Research institutions
    'research.google', 'microsoft.com/research', 'stanford.edu', 'mit.edu'
]

# Tier 2 domains (good quality - quality media, industry analysis, long-form)
TIER_2_DOMAINS = [
    # Quality media
    'economist.com', 'ft.com', 'wsj.com', 'bloomberg.com', 'reuters.com',
    
    # Industry analysis
    'gartner.com', 'forrester.com', 'gallup.com', 'statista.com',
    
    # Tech analysis
    'techcrunch.com', 'theverge.com', 'arstechnica.com',
    
    # Long-form analysis (high signal for insights)
    'substack.com', 'stratechery.com', 'notboring.co',
    'a16z.com', 'sequoiacap.com', 'ycombinator.com',
    
    # Company engineering blogs (tactical insights)
    'engineering.', 'blog.', 'stripe.com/blog', 'shopify.engineering',
    'netflix.com/tech', 'github.blog', 'gitlab.com/blog'
]

# Combined preferred domains
PREFERRED_DOMAINS = TIER_1_DOMAINS + TIER_2_DOMAINS

# Banned domains (social media, low-quality, promotional)
BANNED_DOMAINS = [
    # Social media
    'youtube.com', 'facebook.com', 'twitter.com', 'instagram.com',
    'pinterest.com', 'tiktok.com', 'reddit.com', 'quora.com', 'zhihu.com',
    
    # Reference sites (not original research)
    'wikipedia.org', 'wikihow.com',
    
    # Job boards (promotional, not insights)
    'weworkremotely.com', 'indeed.com', 'linkedin.com/jobs', 'glassdoor.com',
    
    # Vendor/SaaS promotional sites (CRITICAL - these slip through as "insights")
    'flexisourceit.com', 'flexisourceit.com.au',
    'agilityportal.io', 'agilityportal.com',
    'vloggi.com',
    'engagedly.com',
    'hybridhero.com',
    'connecteam.com',
    'monday.com',
    'asana.com/resources',
    'notion.so/blog',
    'slack.com/blog',  # Promotional, not engineering
    'zoom.us/blog',    # Marketing blog
    'trello.com/blog',
    
    # Employee monitoring/productivity vendors (self-promotional)
    'prodoscore.com',
    'activtrak.com',
    'hubstaff.com',
    'timедoctor.com',
    'workpuls.com',
    'teramind.com',
    
    # Low-quality/promotional
    'desktime.com', 'findstack.com', 'passivesecrets.com',
    'conexisvmssoftware.com', 'softwareadvice.com',
    
    # SEO content farms
    'medium.com', 'forbes.com/sites', 'entrepreneur.com',
    
    # Aggregators
    'feedly.com', 'flipboard.com'
]

# Recency configuration (dynamic based on current date)
CURRENT_YEAR = datetime.now().year
RECENCY_CONFIG = {
    "prefer_recent": True,
    "current_year": CURRENT_YEAR,
    "acceptable_years": [CURRENT_YEAR - 2, CURRENT_YEAR - 1, CURRENT_YEAR],  # Last 3 years
    "stale_penalty": -50,
}


def detect_recency(content: str, url: str) -> tuple:
    """
    Detect publication date/recency from content and URL
    Returns: (recency_score, detected_year)
    """
    detected_years = set()
    
    # Pattern 1: Year patterns
    year_patterns = [
        r'\b(202[0-9])\b',
        r'\b(20[12][0-9])\b',
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? (202[0-9])',
    ]
    
    for pattern in year_patterns:
        matches = re.findall(pattern, content[:3000], re.IGNORECASE)
        for match in matches:
            try:
                year = int(match)
                if 2010 <= year <= 2025:
                    detected_years.add(year)
            except:
                continue
    
    # Pattern 2: Check URL for year
    url_year_match = re.search(r'/(202[0-9])/', url)
    if url_year_match:
        detected_years.add(int(url_year_match.group(1)))
    
    # Pattern 3: Common date formats
    date_formats = [
        r'Published:?\s*.*?(202[0-9])',
        r'Updated:?\s*.*?(202[0-9])',
        r'Posted:?\s*.*?(202[0-9])',
    ]
    
    for pattern in date_formats:
        match = re.search(pattern, content[:3000], re.IGNORECASE)
        if match:
            detected_years.add(int(match.group(1)))
    
    if not detected_years:
        return (RECENCY_CONFIG['stale_penalty'], None)
    
    most_recent_year = max(detected_years)
    current_year = RECENCY_CONFIG['current_year']
    
    # Calculate recency score (dynamic based on year difference)
    year_diff = current_year - most_recent_year
    
    if year_diff == 0:
        # Current year content (most valuable)
        recency_score = 30
    elif year_diff == -1:
        # Next year (future-dated content, still relevant)
        recency_score = 10
    elif year_diff == 1:
        # Last year content
        recency_score = 20
    elif year_diff == 2:
        # Two years old
        recency_score = 5
    elif most_recent_year in RECENCY_CONFIG['acceptable_years']:
        # Within acceptable range
        recency_score = 5
    else:
        # Stale content
        recency_score = RECENCY_CONFIG['stale_penalty']
    
    return (recency_score, most_recent_year)


async def preview_source(candidate: dict) -> dict:
    """Preview a source and calculate quality score"""
    url = candidate['url']
    
    try:
        content = await fetch_content_sample(url)
        
        if not content or len(content) < 200:
            return {**candidate, 'quality_score': 0}
        
        # Base quality score
        quality_score = 50
        
        # Domain tier bonuses
        url_lower = url.lower()
        is_tier_1 = any(domain in url_lower for domain in TIER_1_DOMAINS)
        is_tier_2 = any(domain in url_lower for domain in TIER_2_DOMAINS)
        
        if is_tier_1:
            quality_score += 50  # Tier 1 = highest priority
        elif is_tier_2:
            quality_score += 30  # Tier 2 = good quality
        elif candidate.get('is_preferred_domain'):
            quality_score += 20  # Legacy preferred
        
        # Content length bonus (longer = more likely to have synthesis/insights)
        if len(content) > 5000:
            quality_score += 30  # Long-form analysis
        elif len(content) > 3000:
            quality_score += 20  # Medium depth
        elif len(content) > 1500:
            quality_score += 10  # Short form
        
        # Insight indicators (favor synthesis over raw data)
        insight_indicators = [
            # Strategic/tactical
            'strategy', 'approach', 'framework', 'playbook', 'how to',
            'case study', 'example', 'implemented', 'we built', 'our approach',
            # Analysis
            'because', 'why', 'reveals', 'shows that', 'this means',
            'the key insight', 'counterintuitive', 'surprising',
            # Depth
            'deep dive', 'analysis', 'explained', 'breakdown'
        ]
        content_lower = content.lower()
        insight_matches = sum(1 for indicator in insight_indicators if indicator in content_lower)
        quality_score += min(insight_matches * 4, 25)  # Higher bonus for insight signals
        
        # Recency check
        recency_score, detected_year = detect_recency(content, url)
        quality_score += recency_score
        
        result = {
            **candidate,
            'quality_score': max(0, quality_score),
            'content_length': len(content),
        }
        
        if detected_year:
            result['detected_year'] = detected_year
        
        return result
        
    except Exception as e:
        return {**candidate, 'quality_score': 0, 'error': str(e)}


async def discover_sources_with_queries(queries: list, max_results: int = 50) -> list:
    """
    Core production discovery function - searches, filters, and previews sources
    
    Args:
        queries: List of search query strings
        max_results: Max sources to return
    
    Returns:
        List of previewed sources with quality scores
    """
    
    candidates = []
    seen_urls = set()
    
    # Search using all queries
    for query in queries:
        print(f"Searching: {query}")
        
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=20))
                
                for result in results:
                    url = result['href']
                    
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    
                    # Filter by domain
                    is_preferred = any(domain in url.lower() for domain in PREFERRED_DOMAINS)
                    is_banned = any(domain in url.lower() for domain in BANNED_DOMAINS)
                    
                    if is_banned:
                        continue
                    
                    candidates.append({
                        'url': url,
                        'title': result['title'],
                        'description': result.get('body', ''),
                        'is_preferred_domain': is_preferred,
                        'query': query
                    })
                    
        except Exception as e:
            print(f"  Error searching: {e}")
    
    print(f"\nFound {len(candidates)} candidate sources")
    print(f"  Preferred domains: {sum(1 for c in candidates if c['is_preferred_domain'])}")
    print(f"  Other domains: {sum(1 for c in candidates if not c['is_preferred_domain'])}")
    
    # Preview sources
    total_to_preview = min(len(candidates), max_results)
    print(f"Previewing quality scores for {total_to_preview} sources...")
    print(f"  (This may take 2-5 minutes for large batches)\n")
    
    previewed = []
    for idx, candidate in enumerate(candidates[:max_results], 1):
        try:
            # Progress update every 10 sources
            if idx % 10 == 0 or idx == 1:
                print(f"  Progress: {idx}/{total_to_preview} sources previewed...")
            
            preview = await preview_source(candidate)
            if preview.get('quality_score', 0) > 0:
                previewed.append(preview)
        except Exception as e:
            # Log failures for debugging
            if idx % 10 == 0:
                print(f"  (Skipped {sum(1 for _ in range(max(0, idx-10), idx) if True)} failed sources)")
            pass
    
    print(f"✓ Completed preview: {len(previewed)} quality sources found\n")
    
    # Sort by quality score
    previewed.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
    
    return previewed
