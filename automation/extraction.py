"""
Production extraction module for insights
Based on test_extraction.py but designed for production use
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import urlparse
from anthropic import Anthropic
import os
from dotenv import load_dotenv
import requests
import io
from automation.training_logger import log_extraction

# Load environment variables
load_dotenv()

# Try to import PDF libraries
try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("⚠️  PyPDF2 not installed - PDF extraction disabled. Install with: pip install PyPDF2")


def remove_hallucinated_content(insights: dict, original_content: str) -> dict:
    """Remove insights that don't appear in the original content"""
    
    content_lower = original_content.lower()
    cleaned = {}
    
    for field, items in insights.items():
        if not isinstance(items, list):
            cleaned[field] = items
            continue
        
        verified_items = []
        for item in items:
            if not isinstance(item, str):
                verified_items.append(item)
                continue
            
            # Skip obvious hallucinations
            if any(phrase in item.lower() for phrase in [
                "(not explicitly stated",
                "(implied",
                "according to the report's focus",
                "as suggested by",
                "it can be inferred",
                "suggests that",
                "implies that"
            ]):
                continue
            
            # For longer insights, verify key terms are in content
            if len(item.split()) > 10:
                words = set(item.lower().split())
                stop_words = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or', 'is', 'are', 'was', 'were', 'has', 'have', 'that', 'this', 'with', 'from', 'by', 'should', 'must', 'will', 'can'}
                key_words = words - stop_words
                
                # Check if enough key words are in content
                if len(key_words) > 3:
                    matches = sum(1 for word in key_words if word in content_lower)
                    match_rate = matches / len(key_words)
                    
                    if match_rate < 0.3:  # Less than 30% match = likely hallucinated
                        continue
            
            verified_items.append(item)
        
        cleaned[field] = verified_items
    
    return cleaned


def is_extraction_valuable(extracted_data: dict) -> bool:
    """Check if extraction contains actual insights (with 'so what?') vs just facts"""
    
    if not extracted_data:
        return False
    
    valuable_count = 0
    total_count = 0
    
    for category, items in extracted_data.items():
        if not isinstance(items, list):
            continue
        
        for item in items:
            if not isinstance(item, str):
                continue
            
            total_count += 1
            
            # Check for "so what?" indicators
            has_arrow = '→' in item
            has_implication = any(word in item.lower() for word in [
                'because', 'therefore', 'reveals', 'suggests', 'indicates', 
                'marks', 'creates opportunity', 'requires', 'means', 'shows',
                'enables', 'allows', 'forces', 'drives'
            ])
            
            # Check for specificity indicators
            has_numbers = bool(re.search(r'\d+', item))
            has_dates = bool(re.search(r'\b(20\d{2}|Q[1-4]|\d{4})\b', item))
            has_comparison = any(word in item.lower() for word in [
                'vs', 'versus', 'compared', 'than', 'while', 'but', 'however',
                'despite', 'although', 'whereas'
            ])
            
            # Count as valuable if it has "so what?" AND specificity
            if has_arrow and (has_numbers or has_dates or has_comparison):
                valuable_count += 1
            elif has_implication and has_numbers:
                valuable_count += 1
    
    if total_count == 0:
        return False
    
    # Need at least 2 valuable insights and 50%+ valuable rate
    if valuable_count >= 2 and (valuable_count / total_count) >= 0.5:
        return True
    
    # Or accept if 3+ insights and 60%+ valuable rate (high purity)
    return valuable_count >= 3 and (valuable_count / total_count) >= 0.6


async def extract_insights_with_validation(url: str, content: str, max_retries: int = 2) -> dict:
    """Extract insights with JSON validation and hallucination removal"""
    
    prompt = f"""
Extract ACTIONABLE INSIGHTS from this content - not stats or facts, but insights that change how someone thinks or acts.

CRITICAL: Extract insights that answer "So what?" and "Now what?" - focus on WHY and HOW, not just WHAT.

EXAMPLES OF GOOD INSIGHTS (Actionable, synthesized, non-obvious):
✓ "Gitlab runs 2,000 remote employees with zero offices by using async communication and transparent documentation - their entire company handbook is public, revealing that 70% of decisions don't need meetings when context is well-documented"
  → Strategic insight: HOW a company solves a problem
  → Actionable: You can adopt their approach
  
✓ "Buffett is buying Japanese trading houses at 8-10x earnings while similar US companies trade at 20x because Japanese investors systematically undervalue stable businesses - he's exploiting a structural arbitrage where these companies generate 15%+ ROE but trade below book value"
  → Strategic + tactical: WHY he's doing it + WHAT the opportunity is
  → Includes specific companies and numbers

✓ "Companies are quietly doing 'silent layoffs' by forcing return-to-office, saving on severance while maintaining positive PR - data shows 30-40% attrition when mandating full-time office, effectively self-selecting for exits without layoff announcements"
  → Counterintuitive: Reveals hidden strategy
  → Explains mechanism and outcome

EXAMPLES OF BAD EXTRACTIONS (Just stats, no insight):
✗ "85% of employees feel more productive remotely" (fact without context)
✗ "Remote work increased 159% in 2 years" (stat without implication)
✗ "Value stocks outperformed by 15%" (number without WHY or HOW)

DO NOT EXTRACT:
✗ Bare statistics without explanation (just numbers with no insight)
✗ Obvious facts everyone knows ("Pandemic caused remote work", "Gen Z wants flexibility")
✗ Generic advice without proof ("Set clear goals", "Use time-tracking tools")
✗ Promotional content (companies describing their own product)
✗ Marketing language ("empowers", "simplifies", "our platform", "our clients")
✗ Vendor case studies (client testimonials, "25% increase with our product")
✗ Website metadata, survey descriptions, or study summaries
✗ Generic lists of tips or best practices

⚠️ CRITICAL: If a company is describing its OWN product/service, DO NOT extract it.
   Examples to REJECT:
   - "Vloggi empowers companies to collect user-generated videos..."
   - "AgilityPortal's platform simplifies employee onboarding..."
   - "Flexisource IT's productivity tips for remote work..."
   
   These are SALES PITCHES, not insights.

Extract insights in these categories:

1. STRATEGIC_INSIGHTS
   How successful people/companies approach this topic with specific strategies (not generic advice)
   Must include WHO is doing WHAT and WHY it works
   Format: 2-3 sentences with specific examples and reasoning
   Example: "Basecamp went remote-first in 2014 and grew 300% with half the industry turnover by implementing async-first communication and 4-day work weeks in summer. Their key insight: eliminating meetings freed 15-20 hours per week for deep work, which they found mattered more than collaboration for creative work."

2. COUNTERINTUITIVE
   Things that challenge conventional wisdom with explanation of WHY
   Must include the surprise + the mechanism/reasoning
   Format: State the surprising finding, then explain what it reveals
   Example: "Remote workers are MORE likely to get promoted because their work is more visible in writing and async communication creates better documentation of contributions - companies with strong remote cultures see 25% higher promotion rates for remote vs office workers."

3. TACTICAL_PLAYBOOKS
   Specific frameworks, checklists, processes that are proven to work
   Must be concrete and actionable (not vague advice)
   Format: Step-by-step or framework with specific details
   Example: "Buffett's Japanese stock playbook: 1) Find stable oligopolies with 10+ year track records, 2) Verify FCF generation and 15%+ ROE, 3) Buy below 12x earnings, 4) Use yen debt to finance purchases (borrow at 0.5%, earn 15%+ returns), 5) Hold indefinitely. This works in Japan because local institutions can't buy foreign stocks, creating persistent undervaluation."

4. EMERGING_PATTERNS
   Early signals of change that most people are missing
   What smart people/companies are doing now before it's obvious
   Format: Identify the pattern + explain why it matters early
   Example: "Top ML engineers are leaving FAANG for AI agent startups despite 50% pay cuts - signal that insiders believe the agent ecosystem will be as large as the app ecosystem within 3-5 years. Sequoia data shows seed funding for agent companies up 400% YoY."

5. CASE_STUDIES
   Real examples with specific numbers and outcomes
   Must explain what happened, why, and what it means
   Format: Company/person + what they did + results + lesson
   Example: "Shopify built an AI agent for customer service that handles 60% of tickets, but the key wasn't the AI - it was redesigning workflows first. They standardized 200 common requests into templates, THEN automated them, achieving 85% resolution vs 40% for competitors who automated without redesigning."

CRITICAL RULES:
- Every insight must answer "So what?" and "Now what?"
- Focus on WHY and HOW, not just WHAT
- Include specific names, companies, numbers when available
- 2-3 sentences minimum to provide context
- Avoid generic platitudes and obvious facts
- Each insight should be surprising or actionable
- REJECT promotional content - if a company is describing its own product, it's not an insight
- REJECT obvious statements - would this surprise a reasonably informed person? If NO, don't extract
- REJECT generic advice - must have specific examples, numbers, or proof
- When in doubt, default to EMPTY arrays - quality over quantity

Content (first 10000 characters):
{content[:10000]}

Return ONLY valid JSON with NO additional text before or after:
{{
  "strategic_insights": ["insight with WHO, WHAT, WHY"],
  "counterintuitive": ["surprising finding with explanation"],
  "tactical_playbooks": ["specific framework or process"],
  "emerging_patterns": ["early signal with context"],
  "case_studies": ["real example with numbers and outcome"]
}}
"""
    
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    system_prompt = """You are an expert at extracting ACTIONABLE INSIGHTS, not stats or promotional content. Focus on WHY and HOW, not just WHAT. Extract strategic approaches, counterintuitive findings, tactical frameworks, emerging patterns, and case studies. Every insight must answer 'So what?' and 'Now what?'. Be EXTREMELY strict - reject bare statistics, obvious facts, generic advice, and ANY promotional content where a company describes its own product. Reject obvious statements that everyone knows (e.g., 'Gen Z wants flexibility'). Only extract insights that would make someone think differently or act differently. Default to empty arrays if content lacks synthesis, actionability, or contains marketing language. Quality over quantity - better to extract nothing than extract promotional fluff."""
    
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                temperature=0.3,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            result = response.content[0].text
            result = result.replace("```json", "").replace("```", "").strip()
            
            # Try to extract JSON if it's wrapped in text
            if not result.startswith('{'):
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    result = json_match.group(0)
                else:
                    raise ValueError("No JSON found in response")
            
            # Parse JSON
            insights = json.loads(result)
            
            # Validate structure
            if not isinstance(insights, dict):
                raise ValueError("Response is not a JSON object")
            
            # Remove hallucinated content
            insights = remove_hallucinated_content(insights, content)
            
            return insights
            
        except (json.JSONDecodeError, ValueError) as e:
            if attempt < max_retries - 1:
                print(f"      ⚠️  Retry {attempt + 1}/{max_retries} due to: {e}")
                continue
            else:
                print(f"      ❌ Failed to parse after {max_retries} attempts")
                return {}
    
    return {}


def extract_pdf_text(url: str) -> Optional[str]:
    """Extract text from PDF URL"""
    
    if not PDF_SUPPORT:
        print(f"  ⚠️  Cannot extract PDF (PyPDF2 not installed): {url[:60]}...")
        return None
    
    try:
        print(f"  📄 Downloading PDF: {url[:60]}...")
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        # Read PDF
        pdf_file = io.BytesIO(response.content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        # Extract text from all pages
        text_parts = []
        num_pages = len(pdf_reader.pages)
        print(f"  📄 Extracting text from {num_pages} pages...")
        
        for page_num, page in enumerate(pdf_reader.pages):
            try:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            except Exception as e:
                print(f"  ⚠️  Failed to extract page {page_num + 1}: {e}")
                continue
        
        full_text = "\n\n".join(text_parts)
        
        if not full_text or len(full_text) < 100:
            print(f"  ⚠️  PDF text extraction yielded little content ({len(full_text)} chars)")
            return None
        
        print(f"  ✅ Extracted {len(full_text)} characters from PDF")
        return full_text
        
    except requests.RequestException as e:
        print(f"  ❌ Failed to download PDF: {e}")
        return None
    except Exception as e:
        print(f"  ❌ Failed to extract PDF text: {e}")
        return None


async def extract_from_url(url: str, topic: Optional[str] = None) -> Optional[Dict]:
    """
    Main production extraction function
    Fetches content and extracts insights from web pages or PDFs
    
    Args:
        url: Source URL to extract from
        topic: Optional topic for training data logging
    
    Returns dict with:
        - status: 'success' | 'failed'
        - url: source URL
        - source_domain: extracted domain
        - insights: dict of categorized insights
        - insight_count: total insights
        - extracted_at: ISO timestamp
        - quality_score: 0-100 score
    """
    
    try:
        # Check if URL is a PDF
        is_pdf = url.lower().endswith('.pdf')
        
        # 1. Fetch content
        if is_pdf:
            content = extract_pdf_text(url)
        else:
            # Import here to avoid circular dependencies
            from automation.content_fetcher import fetch_content_sample
            content = await fetch_content_sample(url)
        
        if not content:
            return {
                'status': 'failed',
                'url': url,
                'error': 'Failed to fetch content'
            }
        
        # 2. Extract insights
        insights = await extract_insights_with_validation(url, content)
        
        if not insights:
            return {
                'status': 'failed',
                'url': url,
                'error': 'Extraction produced no insights'
            }
        
        # 3. Calculate quality score
        is_valuable = is_extraction_valuable(insights)
        
        # Count insights
        insight_count = sum(
            len(items) for items in insights.values()
            if isinstance(items, list)
        )
        
        # Basic quality score
        quality_score = 0
        if is_valuable:
            quality_score = min(100, 50 + (insight_count * 10))  # 50 base + 10 per insight
        else:
            quality_score = min(50, insight_count * 10)  # Lower score if not valuable
        
        # Extract domain
        parsed = urlparse(url)
        source_domain = parsed.netloc.replace('www.', '')
        
        # Log for training data (async, non-blocking)
        if topic:
            try:
                # Flatten insights for logging
                insight_list = []
                for category, items in insights.items():
                    if isinstance(items, list):
                        for item in items:
                            insight_list.append({"text": item, "category": category})
                
                log_extraction(
                    topic=topic,
                    source_url=url,
                    source_content=content[:8000],  # First 8K chars
                    extracted_insights=insight_list,
                    quality_score=quality_score,
                    passed_filters=is_valuable
                )
            except Exception as e:
                # Don't fail extraction if logging fails
                pass
        
        return {
            'status': 'success',
            'url': url,
            'source_domain': source_domain,
            'insights': insights,
            'insight_count': insight_count,
            'quality_score': quality_score,
            'extracted_at': datetime.now().isoformat(),
            'is_valuable': is_valuable
        }
        
    except Exception as e:
        return {
            'status': 'failed',
            'url': url,
            'error': str(e)
        }


# For backwards compatibility
async def extract_and_evaluate_source(url: str) -> Optional[Dict]:
    """Alias for extract_from_url"""
    return await extract_from_url(url)
