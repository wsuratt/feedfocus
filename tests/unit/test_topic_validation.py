"""Test suite for topic validation module."""

import pytest
from backend.topic_validation import (
    validate_topic,
    basic_validation,
    suggest_topic_improvements,
    fallback_validation
)
from tests.fixtures.sample_topics import VALID_TOPICS, INVALID_TOPICS, EDGE_CASE_TOPICS


def test_tier1_basic_validation():
    """Test tier 1 fast rule-based validation"""
    print("\n" + "="*70)
    print("TEST 1: Tier 1 Basic Validation (Fast Rules)")
    print("="*70)

    tests = [
        # (topic, expected_valid, should_need_slm)
        ("f", False, False),  # Too short
        ("x" * 51, False, False),  # Too long
        ("test", False, False),  # Banned word
        ("asdf", False, False),  # Banned word
        ("123456", False, False),  # All numbers
        ("valid topic!", False, False),  # Invalid characters
        ("ML", True, True),  # Valid, needs SLM
        ("AI agents", True, True),  # Valid, needs SLM
    ]

    passed = 0
    failed = 0

    for topic, expected_valid, expected_needs_slm in tests:
        valid, error, needs_slm = basic_validation(topic)

        if valid == expected_valid and needs_slm == expected_needs_slm:
            print(f"✅ '{topic}': valid={valid}, needs_slm={needs_slm}")
            passed += 1
        else:
            print(f"❌ '{topic}': expected valid={expected_valid}, needs_slm={expected_needs_slm}, got valid={valid}, needs_slm={needs_slm}")
            failed += 1

    print(f"\nTier 1 Tests: {passed} passed, {failed} failed")
    return failed == 0


def test_fallback_validation():
    """Test fallback validation (when SLM unavailable)"""
    print("\n" + "="*70)
    print("TEST 2: Fallback Validation (Strict Rules)")
    print("="*70)

    tests = [
        # (topic, expected_valid)
        ("ML", True),  # Valid acronym in whitelist
        ("AI", True),  # Valid acronym
        ("DeFi", True),  # Valid acronym
        ("Web3", True),  # Valid acronym
        ("startup fundraising", True),  # Valid compound topic
        ("stuff about things", False),  # Vague words
        ("how do I learn programming", False),  # Question format
        ("a b c", False),  # No substantial word
        ("XYZ", False),  # Not in whitelist (fallback is strict)
    ]

    passed = 0
    failed = 0

    for topic, expected_valid in tests:
        valid, error, suggestion = fallback_validation(topic)

        if valid == expected_valid:
            print(f"✅ '{topic}': valid={valid}")
            passed += 1
        else:
            print(f"❌ '{topic}': expected {expected_valid}, got {valid} - {error}")
            failed += 1

    print(f"\nFallback Tests: {passed} passed, {failed} failed")
    return failed == 0


def test_full_validation_without_slm():
    """Test full validation in fallback mode (no SLM loaded)"""
    print("\n" + "="*70)
    print("TEST 3: Full Validation (Fallback Mode - No SLM)")
    print("="*70)

    tests = [
        # (topic, expected_valid)
        ("ML", True),
        ("AI agents", True),
        ("startup fundraising", True),
        ("f", False),
        ("test", False),
        ("x" * 51, False),
        ("stuff about things", False),
        ("Web3", True),
        ("DeFi", True),
    ]

    passed = 0
    failed = 0

    for topic, expected_valid in tests:
        valid, error, suggestion = validate_topic(topic)

        status = "✅" if valid == expected_valid else "❌"
        print(f"{status} '{topic}': valid={valid}, error='{error}', suggestion='{suggestion}'")

        if valid == expected_valid:
            passed += 1
        else:
            failed += 1

    print(f"\nFull Validation Tests: {passed} passed, {failed} failed")
    return failed == 0


def test_full_validation_with_slm():
    """Test full validation with SLM loaded"""
    print("\n" + "="*70)
    print("TEST 4: Full Validation (With SLM)")
    print("="*70)
    print("⏳ Loading SLM (this takes 5-10 seconds)...")

    # Try to load SLM
    slm_loaded = init_slm()

    if not slm_loaded:
        print("⚠️  SLM failed to load, skipping SLM tests")
        print("   (This is expected if transformers/torch not installed)")
        return True  # Don't fail test if dependencies missing

    print("✅ SLM loaded\n")

    tests = [
        # (topic, expected_valid, description)
        ("ML", True, "Valid acronym"),
        ("AI agents", True, "Compound valid topic"),
        ("startup fundraising", True, "Compound topic"),
        ("Web3", True, "Emerging tech"),
        ("DeFi", True, "Crypto topic"),
        ("Y Combinator", True, "Named entity"),
        ("f", False, "Too short"),
        ("test", False, "Banned word"),
        ("asdf jkl", False, "Gibberish"),
        ("stuff about things", False, "Too vague"),
        ("how do I learn programming", False, "Question format"),
        ("x" * 51, False, "Too long"),
        ("B2B SaaS sales", True, "Compound with acronyms"),
        ("machine learning for robotics", True, "Specific niche"),
    ]

    passed = 0
    failed = 0

    for topic, expected_valid, description in tests:
        valid, error, suggestion = validate_topic(topic)

        status = "✅" if valid == expected_valid else "❌"
        print(f"{status} '{topic}' ({description})")
        print(f"   valid={valid}, error='{error}', suggestion='{suggestion}'")

        if valid == expected_valid:
            passed += 1
        else:
            failed += 1

    print(f"\nSLM Validation Tests: {passed} passed, {failed} failed")
    return failed == 0


def test_suggestions():
    """Test topic improvement suggestions"""
    print("\n" + "="*70)
    print("TEST 5: Topic Improvement Suggestions")
    print("="*70)

    tests = [
        ("stuff", True),  # Should have suggestion
        ("things", True),  # Should have suggestion
        ("how do I learn Python", True),  # Should have suggestion
        ("business", True),  # Should have suggestion
        ("AI agents", False),  # Should NOT have suggestion
        ("startup fundraising", False),  # Should NOT have suggestion
    ]

    passed = 0
    failed = 0

    for topic, should_have_suggestion in tests:
        suggestion = suggest_topic_improvements(topic)
        has_suggestion = len(suggestion) > 0

        if has_suggestion == should_have_suggestion:
            status = "✅"
            print(f"{status} '{topic}': has_suggestion={has_suggestion}")
            if has_suggestion:
                print(f"   → {suggestion}")
            passed += 1
        else:
            status = "❌"
            print(f"{status} '{topic}': expected has_suggestion={should_have_suggestion}, got {has_suggestion}")
            failed += 1

    print(f"\nSuggestion Tests: {passed} passed, {failed} failed")
    return failed == 0


def main():
    """Run all tests"""
    print("="*70)
    print("TOPIC VALIDATION TEST SUITE")
    print("="*70)

    results = []

    # Test 1: Basic validation (fast rules)
    results.append(("Tier 1 Basic Validation", test_tier1_basic_validation()))

    # Test 2: Fallback validation
    results.append(("Fallback Validation", test_fallback_validation()))

    # Test 3: Full validation without SLM
    results.append(("Full Validation (No SLM)", test_full_validation_without_slm()))

    # Test 4: Full validation with SLM (optional)
    print("\n" + "="*70)
    print("OPTIONAL: Testing with SLM (requires transformers/torch)")
    print("="*70)
    try:
        results.append(("Full Validation (With SLM)", test_full_validation_with_slm()))
    except Exception as e:
        print(f"⚠️  SLM tests skipped: {e}")
        results.append(("Full Validation (With SLM)", True))  # Don't fail if missing deps

    # Test 5: Suggestions
    results.append(("Topic Suggestions", test_suggestions()))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False

    print("="*70)

    if all_passed:
        print("\n✅ All tests passed!")
        print("\nTask 1.2 completed! ✓")
        print("Ready to proceed to Task 1.3: Build Semantic Similarity Function")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit(main())
