# test_extraction.py
import asyncio
import json
import re
import sys
import os
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from automation.content_fetcher import fetch_content_sample
from groq import Groq

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
                print(f"      ⚠️  HALLUCINATION DETECTED: {item[:80]}...")
                continue
            
            # For longer insights, verify key terms are in content
            if len(item.split()) > 10:
                # Extract key terms (not common words)
                words = set(item.lower().split())
                stop_words = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or', 'is', 'are', 'was', 'were', 'has', 'have', 'that', 'this', 'with', 'from', 'by', 'should', 'must', 'will', 'can'}
                key_words = words - stop_words
                
                # Check if enough key words are in content
                if len(key_words) > 3:
                    matches = sum(1 for word in key_words if word in content_lower)
                    match_rate = matches / len(key_words)
                    
                    if match_rate < 0.4:  # Less than 40% of key words found
                        print(f"      ⚠️  LIKELY HALLUCINATION ({match_rate:.0%} match): {item[:80]}...")
                        continue
            
            verified_items.append(item)
        
        cleaned[field] = verified_items
    
    return cleaned

def is_extraction_valuable(extracted_data: dict) -> bool:
    """Check if extraction contains actual insights (with 'so what?') vs just facts"""
    
    if not extracted_data:
        return False
    
    # Recognize written numbers
    number_words = {
        'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
        'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety',
        'hundred', 'thousand', 'million', 'billion'
    }
    
    # Count actually valuable insights
    valuable_count = 0
    total_count = 0
    
    for field_name, values in extracted_data.items():
        if not isinstance(values, list):
            continue
        
        for item in values:
            if not isinstance(item, str) or len(item) < 50:
                continue
            
            total_count += 1
            
            # Red flags
            red_flags = [
                '(not explicitly stated',
                '(implied',
                'includes',
                'provides',
                'supports',
                'such as',
                'offers',
                'features',
            ]
            
            if any(flag in item.lower() for flag in red_flags):
                continue
            
            # Check for "so what?"
            has_implication = '→' in item or any(word in item.lower() for word in [
                'means', 'reveals', 'indicates', 'shows', 'signals',
                'opportunity', 'threat', 'requires', 'enables', 'creates',
                'marks', 'represents', 'demonstrates', 'highlights'
            ])
            
            # Good signals (specific, data-driven) - UPDATED
            has_digits = any(char.isdigit() for char in item)
            has_written_numbers = any(word in item.lower().split() for word in number_words)
            has_percentage = '%' in item or 'percent' in item.lower()
            
            has_specific_time = any(term in item.lower() for term in [
                'q1', 'q2', 'q3', 'q4', 
                '2024', '2025', '2023', '2022',
                'january', 'february', 'march', 'april', 'may', 'june',
                'july', 'august', 'september', 'october', 'november', 'december',
                'last year', 'this year', 'past year', 'recent'
            ])
            
            has_comparison = any(word in item.lower() for word in [
                'grew', 'increased', 'decreased', 'from', 'to', 'vs', 
                'compared', 'rose', 'fell', 'declined', 'surged', 'despite',
                'while', 'but', 'however', 'whereas', 'more', 'less', 'higher', 'lower'
            ])
            
            # Must have data (numbers OR comparison) AND implication
            has_data = sum([
                has_digits, 
                has_written_numbers, 
                has_percentage, 
                has_specific_time, 
                has_comparison
            ]) >= 2
            
            if has_data and has_implication:
                valuable_count += 1
    
    if total_count == 0:
        return False
    
    # Accept if we have 4+ good insights (absolute value matters)
    if valuable_count >= 4:
        return True
    
    # Or accept if 3+ insights and 60%+ valuable rate (high purity)
    return valuable_count >= 3 and (valuable_count / total_count) >= 0.6

async def extract_insights_with_validation(url: str, content: str, max_retries: int = 2) -> dict:
    """Extract insights with JSON validation and hallucination removal"""
    
    prompt = f"""
Read this content and extract INSIGHTS - not just facts, but the "so what?" that makes it worth reading.

An insight must answer at least ONE of these:
1. Why does this matter? (Implication)
2. What's surprising or counterintuitive? (Contradiction)
3. What changed and why NOW? (Timing)
4. What's the opportunity or threat? (Action)
5. How do seemingly separate things connect? (Pattern)

EXAMPLES OF GOOD INSIGHTS:
✓ "Gen Z workers surpassed Baby Boomers for the first time in Q3 2023 (18% vs 15% of workforce) → Marks fundamental shift requiring companies to adapt hiring and culture to younger generation's priorities around flexibility and purpose"
  → Has data: Specific numbers and timing
  → Has "so what": Explains why it matters (companies must adapt)

✓ "Despite 80% of companies adopting gen AI, 90% of implementations remain stuck in pilot mode → Reveals massive gap between adoption and business impact, creating opportunity for companies that solve integration challenges"
  → Surprising: High adoption but low impact
  → Has implication: Shows the real challenge and opportunity

✓ "Bachelor's degree attainment rose from 34.4% to 43.6% from Boomers to Millennials → Creates opportunity for skills-based hiring as degree inflation makes credentials less differentiating"
  → Has data: Specific comparison
  → Has implication: What this enables/requires

EXAMPLES OF BAD "INSIGHTS" (just facts without the "so what?"):
✗ "AI adoption is growing" (no data, no implication)
✗ "Gen Z workers are 18% of the labor force" (just a fact)
✗ "Companies use gen AI for various tasks" (generic, no insight)
✗ "Education levels have increased over time" (obvious, no specific data)

CRITICAL RULES:
- Each insight must be a COMPLETE THOUGHT with both DATA and IMPLICATION
- Use "→" to separate the finding from its significance
- Must explain WHY the reader should care
- Must be SPECIFIC with numbers/dates/comparisons
- Must be EXPLICITLY STATED in the content (never infer or imply)
- If the content lacks substantive insights, return empty arrays

Extract:

1. key_insights: Main takeaways that answer "why does this matter?"
   Format: "[Specific finding with data] → [Why it matters / what it means]"

2. surprising_findings: Things that contradict common assumptions
   Format: "[Counterintuitive finding with evidence] → [Why it's surprising / what it reveals]"

3. timing_windows: Why certain opportunities/changes exist NOW specifically
   Format: "[What changed] in [specific time] → [Why this timing matters / what it enables]"

4. implications: What this means for action
   Format: "[Finding with data] → [Opportunity / threat / change required]"

Content (first 8000 characters):
{content[:8000]}

Return ONLY valid JSON with NO additional text before or after:
{{
  "key_insights": ["finding → why it matters"],
  "surprising_findings": ["finding → why surprising"],
  "timing_windows": ["what changed when → why now matters"],
  "implications": ["finding → what to do / what it enables"]
}}
"""
    
    load_dotenv()
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": "Extract INSIGHTS (data + implication), not just facts. Each insight must have the 'so what?' built in. Be strict. Default to empty arrays if content lacks substantive insights. Never infer or imply."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Slightly higher for more natural language
                max_tokens=2500
            )
            
            result = response.choices[0].message.content
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
                print(f"    ⚠️  Retry {attempt + 1}/{max_retries} due to: {e}")
                continue
            else:
                print(f"    ❌ Failed to parse after {max_retries} attempts: {e}")
                return {}
    
    return {}

async def test_extraction(url: str):
    """Test extraction on a single URL"""
    
    print(f"\n{'='*80}")
    print(f"Testing extraction: {url}")
    print('='*80 + "\n")
    
    # 1. Fetch content
    print("1. Fetching content...")
    content = await fetch_content_sample(url)
    
    if not content:
        print("❌ Failed to fetch content")
        return None, False
    
    print(f"✓ Fetched {len(content)} characters\n")
    print("Preview:")
    print(content[:500])
    print("...\n")
    
    # 2. Extract insights
    print("2. Extracting insights...\n")
    insights = await extract_insights_with_validation(url, content)
    
    if not insights:
        print("❌ Extraction failed or produced no insights\n")
        return {}, False
    
    # 3. Display results
    print("3. Extracted insights:\n")
    print(json.dumps(insights, indent=2))
    
    # 4. Quality evaluation
    print("\n4. Quality evaluation:\n")
    
    total_insights = sum(len(v) for v in insights.values() if isinstance(v, list))
    
    if total_insights == 0:
        print("❌ No insights extracted (content may be irrelevant or too generic)")
        return insights, False
    
    good_count = 0
    ok_count = 0
    fact_count = 0
    
    for category, items in insights.items():
        if not isinstance(items, list):
            continue
            
        print(f"\n{category}:")
        for item in items:
            print(f"  • {item}")
            
            # Check for insight qualities
            has_arrow = '→' in item
            has_implication = any(word in item.lower() for word in [
                'means', 'reveals', 'indicates', 'shows', 'signals',
                'opportunity', 'threat', 'requires', 'enables', 'creates',
                'marks', 'represents', 'demonstrates', 'highlights', 'why'
            ])
            
            # Check for data - UPDATED to recognize written numbers
            number_words = ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
                        'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
            
            has_digits = any(char.isdigit() for char in item)
            has_written_numbers = any(word in item.lower().split() for word in number_words)
            has_percentage = '%' in item or 'percent' in item.lower()
            
            has_comparison = any(word in item.lower() for word in [
                'grew', 'increased', 'decreased', 'vs', 'compared to', 'from', 'to',
                'rose', 'fell', 'declined', 'surged', 'despite', 'while', 'but',
                'more', 'less', 'higher', 'lower'
            ])
            
            has_timing = any(word in item.lower() for word in [
                '2024', '2025', '2023', 'q1', 'q2', 'q3', 'q4', 
                'january', 'february', 'march', 'april', 'may', 'june',
                'july', 'august', 'september', 'october', 'november', 'december',
                'last year', 'this year', 'past', 'recent'
            ])
            
            has_data = sum([has_digits, has_written_numbers, has_percentage, has_timing, has_comparison]) >= 2
            is_substantive = len(item) > 50
            
            if has_data and has_implication and is_substantive:
                print(f"    ✓ INSIGHT (data + 'so what?')")
                good_count += 1
            elif has_data and is_substantive:
                print(f"    ○ FACT (has data but missing 'so what?')")
                ok_count += 0.5
                fact_count += 1
            elif has_implication:
                print(f"    ○ CLAIM (has implication but lacks specific data)")
                ok_count += 0.3
            else:
                print(f"    ✗ GENERIC (neither data nor implication)")
    
    # Overall assessment
    is_valuable = is_extraction_valuable(insights)
    
    print(f"\n{'='*80}")
    print(f"Quality Score: {good_count + ok_count:.1f}/{total_insights}")
    print(f"  - {good_count} true insights (data + implication)")
    print(f"  - {fact_count} facts (data without 'so what?')")
    print(f"  - {total_insights - good_count - fact_count} generic/weak")
    print(f"\nOverall: {'✓ VALUABLE' if is_valuable else '✗ NOT VALUABLE'}")
    print(f"{'='*80}\n")
    
    if not is_valuable:
        print("⚠️  QUALITY TOO LOW")
        print("   Reasons:")
        if good_count < 3:
            print(f"   - Only {good_count} true insights (need 3+)")
        if fact_count > good_count:
            print(f"   - Too many facts without 'so what?' ({fact_count} facts vs {good_count} insights)")
        if total_insights > 0 and (good_count / total_insights) < 0.6:
            print(f"   - Only {good_count / total_insights:.0%} are true insights (need 60%+)")
        print("\n   What makes a good insight:")
        print("   ✓ Has specific data (numbers, dates, comparisons)")
        print("   ✓ Explains WHY it matters (implication, opportunity, significance)")
        print("   ✓ Answers 'so what?' for the reader")
        print("\n   Recommendations:")
        print("   - Source may contain only facts, not insights")
        print("   - Try sources with analysis/interpretation (consulting reports, research)")
        print("   - Avoid pure data dumps or news summaries")
    else:
        print("✓ This source produces valuable insights\n")
        print("   These insights answer 'why should I care?' with data and implication.")
    
    return insights, is_valuable

async def batch_test(urls: list):
    """Test extraction on multiple URLs"""
    
    results = []
    
    for i, url in enumerate(urls, 1):
        print(f"\n{'#'*80}")
        print(f"TEST {i}/{len(urls)}")
        print(f"{'#'*80}")
        
        insights, is_valuable = await test_extraction(url)
        
        if insights is None:
            insights = {}
        
        results.append({
            'url': url,
            'valuable': is_valuable,
            'insight_count': sum(len(v) for v in insights.values() if isinstance(v, list))
        })
        
        if i < len(urls):
            input("\nPress Enter to test next URL...")
    
    # Summary
    print(f"\n{'='*80}")
    print("BATCH TEST SUMMARY")
    print(f"{'='*80}\n")
    
    for i, result in enumerate(results, 1):
        status = "✓ GOOD" if result['valuable'] else "✗ POOR"
        print(f"{i}. {status} - {result['insight_count']} insights - {result['url'][:60]}...")
    
    good_count = sum(1 for r in results if r['valuable'])
    print(f"\n{good_count}/{len(results)} sources produced valuable insights")
    print(f"Success rate: {good_count/len(results)*100:.0f}%\n")

if __name__ == "__main__":
    # Test URLs - mix of good and bad sources
    # test_urls = [
    #     # GOOD SOURCES (should produce valuable insights with 'so what?')
    #     "https://www.dol.gov/sites/dolgov/files/ETA/opder/DASP/Trendlines/posts/2024_08/Trendlines_August_2024.html",
    #     "https://www.mckinsey.com/capabilities/quantumblack/our-insights/seizing-the-agentic-ai-advantage",
        
    #     # BAD SOURCES (should be filtered out - just facts or generic)
    #     "https://news.ycombinator.com",
    #     "https://techcrunch.com",
    # ]
    test_urls = [
        # GOOD SOURCES (should produce valuable insights with 'so what?')
        "https://substack.com/inbox/post/177527193",
    ]
    
    import sys
    
    if len(sys.argv) > 1:
        # Single URL test
        url = sys.argv[1]
        asyncio.run(test_extraction(url))
    else:
        # Batch test
        asyncio.run(batch_test(test_urls))