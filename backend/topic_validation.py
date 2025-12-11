"""Topic validation with rule-based and optional SLM semantic checks."""

import re
from typing import Tuple

from backend.utils.logger import setup_logger

logger = setup_logger(__name__)

slm_pipeline = None
slm_fallback_mode = False


def init_slm(model_name: str = "meta-llama/Llama-3.2-1B-Instruct") -> bool:
    """Initialize the SLM pipeline for topic validation."""
    global slm_pipeline, slm_fallback_mode

    try:
        from transformers import pipeline

        logger.info(f"Loading SLM for topic validation: {model_name}")

        slm_pipeline = pipeline(
            "text-generation",
            model=model_name,
            device="cpu",
            max_length=150,
            do_sample=False,
            temperature=0.1
        )

        logger.info("Topic validation SLM loaded successfully")
        slm_fallback_mode = False
        return True

    except Exception as e:
        logger.error(f"Failed to load SLM: {e}")
        logger.warning("Falling back to strict rule-based validation")
        slm_fallback_mode = True
        return False


def basic_validation(topic: str) -> Tuple[bool, str, bool]:
    """
    Fast rule-based validation.

    Returns: (is_valid, error_message, needs_slm_check)
    """
    topic = topic.strip()

    if len(topic) < 2:
        return False, "Topic too short (minimum 2 characters)", False

    if len(topic) > 50:
        return False, "Topic too long (maximum 50 characters)", False

    if not re.match(r'^[a-zA-Z0-9\s\-\'&]+$', topic):
        return False, "Only letters, numbers, spaces, and hyphens allowed", False

    banned = ['test', 'asdf', 'qwerty', 'xxx', 'xxxx', 'fuck', 'shit', 'demo', 'example']
    if topic.lower() in banned:
        return False, "Invalid topic name", False

    if topic.replace(' ', '').replace('-', '').isdigit():
        return False, "Topic cannot be only numbers", False

    return True, "", True


def validate_with_slm(topic: str) -> Tuple[bool, str, str]:
    """SLM semantic validation. Returns: (is_valid, error_message, suggestion)"""
    global slm_pipeline, slm_fallback_mode

    if slm_fallback_mode or slm_pipeline is None:
        return fallback_validation(topic)

    try:
        prompt = f"""Is "{topic}" a valid topic for a content feed?

Valid examples: AI agents, startup fundraising, DeFi, Web3, Y Combinator, machine learning
Invalid examples: asdf jkl, stuff and things, random gibberish, blah blah blah

Rules:
- Accept real topics, even emerging/niche ones
- Accept standard acronyms (AI, ML, SaaS, B2B, HR, PR, SEO, etc.)
- Accept compound topics (e.g., "startup fundraising for B2B SaaS")
- Reject gibberish or random characters
- Reject overly vague terms like "stuff", "things", "content"
- Reject single letters unless they're standard acronyms

Respond ONLY in this exact format:
VALID or INVALID
Reason: [brief explanation]
Suggestion: [improved topic if invalid, or "none"]"""

        # Generate response
        response = slm_pipeline(
            prompt,
            max_new_tokens=60,
            return_full_text=False
        )[0]['generated_text']

        # Parse response
        response_upper = response.upper()

        # Check validity
        is_valid = "VALID" in response_upper and "INVALID" not in response_upper

        # Extract reason
        reason = ""
        if "Reason:" in response or "reason:" in response.lower():
            reason_match = re.search(r'[Rr]eason:\s*(.+?)(?:\n|Suggestion:|$)', response)
            if reason_match:
                reason = reason_match.group(1).strip()

        # Extract suggestion
        suggestion = ""
        if not is_valid and ("Suggestion:" in response or "suggestion:" in response.lower()):
            suggestion_match = re.search(r'[Ss]uggestion:\s*(.+?)(?:\n|$)', response)
            if suggestion_match:
                suggestion = suggestion_match.group(1).strip()
                if suggestion.lower() in ['none', 'n/a', '']:
                    suggestion = ""

        # Format error message
        error_message = reason if not is_valid else ""

        return is_valid, error_message, suggestion

    except Exception as e:
        logger.error(f"SLM validation failed: {e}")
        logger.warning("Falling back to strict rule validation")
        return fallback_validation(topic)


def fallback_validation(topic: str) -> Tuple[bool, str, str]:
    """Strict rule-based validation when SLM is unavailable."""
    topic_lower = topic.lower()
    words = topic.split()

    valid_acronyms = [
        'ai', 'ml', 'nlp', 'llm', 'slm', 'gpt',
        'saas', 'paas', 'iaas',
        'b2b', 'b2c', 'd2c',
        'seo', 'sem', 'cro',
        'hr', 'pr', 'ar', 'vr', 'xr',
        'ios', 'api', 'sdk', 'cli',
        'web3', 'defi', 'nft', 'dao',
        'vc', 'pe', 'ipo', 'roi',
        'ui', 'ux'
    ]

    is_acronym = topic_lower in valid_acronyms

    if len(words) == 1 and len(topic) <= 4:
        if not is_acronym:
            return False, "Short topics must be recognized acronyms (AI, ML, etc.)", "Try a more descriptive topic"

    vague_words = ['stuff', 'things', 'content', 'random', 'misc', 'various', 'general']
    for vague in vague_words:
        if vague in topic_lower.split():
            return False, f"Topic too vague: '{vague}'", "Be more specific about your interest"

    if topic_lower.startswith(('how ', 'what ', 'why ', 'when ', 'where ')):
        return False, "Topics should be nouns/phrases, not questions", "Rephrase as a topic (e.g., 'Python programming')"

    has_substantial_word = any(len(word) >= 3 for word in words)
    if not has_substantial_word and not is_acronym:
        return False, "Topic must contain at least one word with 3+ characters", ""

    return True, "", ""


def validate_topic(topic: str) -> Tuple[bool, str, str]:
    """
    Main validation entry point.

    Returns: (is_valid, error_message, suggestion)
    """
    valid, error, needs_slm = basic_validation(topic)

    if not needs_slm:
        return valid, error, ""

    return validate_with_slm(topic)


def suggest_topic_improvements(topic: str) -> str:
    """Provide suggestions for improving a topic."""
    topic_lower = topic.lower()
    words = topic_lower.split()

    # Vague terms (only suggest if standalone or in very short topics)
    vague_terms = {
        'stuff': 'What specific area are you interested in?',
        'things': 'What specific topic would you like to follow?',
        'content': 'What type of content specifically?',
    }

    for term, suggestion in vague_terms.items():
        if term in words:
            return suggestion

    # Broad terms (only suggest if standalone, not in compound topics)
    if len(words) == 1:
        broad_terms = {
            'business': 'Try narrowing to a specific industry or aspect (e.g., "B2B SaaS sales")',
            'technology': 'Try narrowing to a specific tech area (e.g., "AI agents", "Web development")',
            'startup': 'Consider being more specific (e.g., "startup fundraising", "YC companies")'
        }

        for term, suggestion in broad_terms.items():
            if term in words:
                return suggestion

    # Question format
    if topic_lower.startswith(('how ', 'what ', 'why ', 'when ', 'where ')):
        return 'Rephrase as a topic rather than a question (e.g., "Python programming" instead of "how to learn Python")'

    # All good
    return ""


def test_validation():
    """Test the validation with sample topics."""
    test_cases = [
        ("ML", True),
        ("AI agents", True),
        ("startup fundraising", True),
        ("Web3", True),
        ("DeFi", True),
        ("Y Combinator", True),
        ("f", False),
        ("test", False),
        ("asdf jkl", False),
        ("stuff about things", False),
        ("how do I learn programming", False),
        ("x" * 51, False),
    ]

    logger.info("Testing topic validation")

    for topic, expected_valid in test_cases:
        valid, error, suggestion = validate_topic(topic)
        status = "PASS" if valid == expected_valid else "FAIL"
        logger.info(f"{status}: '{topic}' - valid={valid}, error='{error}', suggestion='{suggestion}'")


if __name__ == "__main__":
    init_slm()
    test_validation()
