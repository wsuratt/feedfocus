"""
Curated list of 50-100 popular topics to pre-populate
Run daily to keep insights fresh
"""

POPULAR_TOPICS = [
    # Work & Career (15 topics)
    "remote work trends",
    "hybrid workplace policies",
    "labor force participation",
    "Gen Z workforce entry",
    "millennial career patterns",
    "boomer retirement trends",
    "workplace culture evolution",
    "employee retention strategies",
    "salary negotiation trends",
    "four-day work week",
    "quiet quitting phenomenon",
    "great resignation analysis",
    "skills-based hiring",
    "gig economy growth",
    "freelance market trends",
    
    # Technology (15 topics)
    "AI agents development",
    "LLM applications enterprise",
    "autonomous AI systems",
    "multimodal AI models",
    "prompt engineering best practices",
    "AI safety research",
    "developer productivity tools",
    "low-code platforms",
    "web3 adoption metrics",
    "cryptocurrency regulation",
    "blockchain enterprise use",
    "decentralized identity",
    "edge computing trends",
    "quantum computing progress",
    "cybersecurity threats 2024",
    
    # Business & Startups (12 topics)
    "startup funding trends",
    "venture capital activity",
    "SaaS growth metrics",
    "product-led growth strategies",
    "B2B sales automation",
    "customer acquisition costs",
    "startup failure rates",
    "unicorn company analysis",
    "bootstrapping vs funding",
    "exit strategies startups",
    "founder mental health",
    "remote-first companies",
    
    # Investing & Economics (10 topics)
    "value investing strategies",
    "growth vs value stocks",
    "market volatility analysis",
    "inflation impact investing",
    "interest rate trends",
    "recession indicators 2024",
    "real estate investment trends",
    "alternative investments",
    "ESG investing growth",
    "cryptocurrency investment",
    
    # Health & Science (12 topics)
    "longevity research breakthroughs",
    "anti-aging clinical trials",
    "healthspan extension",
    "mental health interventions",
    "psychedelic therapy research",
    "GLP-1 drugs impact",
    "obesity treatment innovations",
    "sleep optimization research",
    "microbiome health",
    "personalized medicine",
    "CRISPR applications",
    "mRNA vaccine development",
    
    # Climate & Energy (8 topics)
    "climate technology investments",
    "carbon capture innovations",
    "renewable energy adoption",
    "electric vehicle market",
    "battery technology advances",
    "nuclear fusion progress",
    "sustainable agriculture",
    "climate adaptation strategies",
    
    # Consumer & Culture (12 topics)
    "Gen Z consumer behavior",
    "Gen Z brand loyalty",
    "Gen Z shopping preferences",
    "creator economy growth",
    "influencer marketing ROI",
    "social media algorithm changes",
    "TikTok commerce trends",
    "subscription fatigue",
    "direct-to-consumer brands",
    "sustainable consumer products",
    "luxury goods market",
    "experiential spending trends",
    
    # Education & Learning (8 topics)
    "online education effectiveness",
    "AI tutoring systems",
    "skills gap analysis",
    "lifelong learning trends",
    "bootcamp success rates",
    "degree alternatives",
    "corporate training evolution",
    "micro-credentials adoption",
]

def get_popular_topics() -> list:
    """Return list of popular topics to pre-populate"""
    return POPULAR_TOPICS

def get_core_topics(limit: int = 30) -> list:
    """Get the most important topics for initial deployment"""
    # Prioritize based on broad appeal
    core = [
        # Work (most universal)
        "remote work trends",
        "hybrid workplace policies",
        "labor force participation",
        "Gen Z workforce entry",
        "workplace culture evolution",
        "employee retention strategies",
        "four-day work week",
        "gig economy growth",
        
        # Tech (high interest)
        "AI agents development",
        "LLM applications enterprise",
        "autonomous AI systems",
        "AI safety research",
        "developer productivity tools",
        "cybersecurity threats 2024",
        
        # Business
        "startup funding trends",
        "venture capital activity",
        "SaaS growth metrics",
        "product-led growth strategies",
        "customer acquisition costs",
        
        # Health (growing interest)
        "longevity research breakthroughs",
        "anti-aging clinical trials",
        "mental health interventions",
        "GLP-1 drugs impact",
        
        # Consumer
        "Gen Z consumer behavior",
        "creator economy growth",
        "influencer marketing ROI",
        
        # Investing
        "value investing strategies",
        "market volatility analysis",
        "cryptocurrency investment",
    ]
    
    return core[:limit]


if __name__ == "__main__":
    print(f"Total topics: {len(POPULAR_TOPICS)}")
    print(f"\nCore topics for initial deployment:")
    for i, topic in enumerate(get_core_topics(), 1):
        print(f"  {i}. {topic}")
