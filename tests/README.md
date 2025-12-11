# Testing

## Structure

```
tests/
├── conftest.py              # Pytest configuration and fixtures
├── unit/                    # Unit tests
│   ├── test_topic_validation.py
│   └── test_semantic_search.py
├── integration/             # API endpoint tests
├── fixtures/                # Test data
│   ├── sample_topics.py
│   └── sample_insights.py
└── README.md
```

## Running Tests

```bash
# All tests
python -m pytest tests/

# Unit tests only
python -m pytest tests/unit/

# Specific test
python -m pytest tests/unit/test_topic_validation.py

# With coverage
python -m pytest --cov=backend tests/
```

See [docs/architecture/testing.md](../docs/architecture/testing.md) for comprehensive testing documentation.

## Original Testing Scripts Scripts

This directory contains all testing and debugging scripts for the insight extraction pipeline.

## Available Tests

### `test_quality.py`
**Purpose:** End-to-end quality test for a single topic
**Usage:** `python tests/test_quality.py`
**What it does:**
- Resets database
- Processes one topic through full pipeline
- Shows extraction, filtering, and deduplication stats
- Displays final insights in feed

**Use when:** Testing overall quality after making changes to extraction or filtering

---

### `test_manual_extraction.py`
**Purpose:** Test extraction on specific URLs
**Usage:** `python tests/test_manual_extraction.py <url> [topic]`
**What it does:**
- Extracts insights from a single URL
- Shows raw extracted insights
- Tests filtering with detailed pass/fail reasons
- Shows SLM evaluation scores

**Use when:** Debugging why specific sources are failing or passing filters

**Example:**
```bash
python tests/test_manual_extraction.py "https://berkshirehathaway.com/letters/2023ltr.pdf" "value investing"
```

---

### `test_extraction.py`
**Purpose:** Test extraction logic in isolation
**Usage:** `python tests/test_extraction.py`
**What it does:**
- Tests LLM extraction prompt
- Validates JSON parsing
- Tests hallucination removal

**Use when:** Debugging extraction prompt or JSON parsing issues

---

### `test_automation.py`
**Purpose:** Test automation pipeline components
**Usage:** `python tests/test_automation.py`
**What it does:**
- Tests query generation
- Tests source discovery
- Tests full topic processing

**Use when:** Debugging automation workflow issues

---

## Running Tests

Tests can be run from either the project root OR from the tests/ directory:

**From project root:**
```bash
python tests/test_quality.py
python tests/test_manual_extraction.py
python tests/test_automation.py
python tests/test_extraction.py
```

**From tests/ directory:**
```bash
cd tests
python test_quality.py
python test_manual_extraction.py
python test_automation.py
python test_extraction.py
```

All test files automatically add the project root to `sys.path`, so imports will work from either location.

---

## Test Workflow

1. **Make changes** to extraction, filtering, or discovery
2. **Test specific URL** with `test_manual_extraction.py` to verify the change works
3. **Run quality test** with `test_quality.py` to verify overall pipeline quality
4. **Check feed** in browser to see final user experience

---

## Common Issues

### Import Errors
If you see `ModuleNotFoundError: No module named 'automation'`:
- This should not happen - all test files now automatically add project root to path
- If it persists, check that the test file has the `sys.path.insert()` block at the top

### No Insights Extracted
If `test_manual_extraction.py` shows 0 insights:
- Check extraction prompt in `automation/extraction.py`
- Check if LLM is being too strict
- Verify API keys are set in `.env`

### All Insights Filtered
If insights are extracted but all filtered:
- Check SLM evaluation in `automation/semantic_db.py`
- Lower threshold from 7 to 5
- Check debug output for rejection reasons
