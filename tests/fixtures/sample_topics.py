"""Sample topics for testing."""

VALID_TOPICS = [
    "AI agents",
    "ML",
    "machine learning",
    "startup fundraising",
    "Web3",
    "DeFi",
    "Y Combinator",
    "value investing",
    "Gen Z marketing",
]

INVALID_TOPICS = [
    "x",  # Too short
    "test",  # Banned word
    "asdf jkl",  # Gibberish
    "x" * 51,  # Too long
    "123456",  # All numbers
    "stuff about things",  # Vague
]

EDGE_CASE_TOPICS = [
    "AI",  # Valid acronym
    "ML models",  # Acronym with context
    "B2B SaaS",  # Multiple acronyms
    "Y-Combinator",  # Hyphenated
    "Web3 & DeFi",  # With ampersand
]
