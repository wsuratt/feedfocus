# Testing Strategy

## Test Structure

```
tests/
├── conftest.py           # Pytest configuration and fixtures
├── unit/                 # Unit tests for individual functions
│   ├── test_topic_validation.py
│   ├── test_semantic_search.py
│   └── test_feed_scoring.py
├── integration/          # API endpoint tests
│   ├── test_api_endpoints.py
│   ├── test_auth_flow.py
│   └── test_feed_generation.py
└── fixtures/             # Test data and mocks
    ├── sample_topics.py
    └── sample_insights.py
```

## Running Tests

```bash
# All tests
python -m pytest tests/

# Unit tests only
python -m pytest tests/unit/

# Integration tests only
python -m pytest tests/integration/

# Specific test file
python -m pytest tests/unit/test_topic_validation.py

# Specific test function
python -m pytest tests/unit/test_topic_validation.py::test_basic_validation

# With coverage
python -m pytest --cov=backend tests/

# Verbose output
python -m pytest -v tests/
```

## Test Patterns

### Unit Tests

Test individual functions in isolation.

```python
def test_basic_validation():
    """Test rule-based validation."""
    from backend.topic_validation import basic_validation

    valid, error, needs_slm = basic_validation("AI agents")
    assert valid is True
    assert error == ""
    assert needs_slm is True

    valid, error, needs_slm = basic_validation("x")
    assert valid is False
    assert "too short" in error.lower()
```

### Integration Tests

Test API endpoints with test database.

```python
def test_follow_topic(client, test_user_token):
    """Test following a topic."""
    response = client.post(
        "/api/topics/follow",
        json={"topic": "AI agents"},
        headers={"Authorization": f"Bearer {test_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["topic"] == "AI agents"
```

### Using Fixtures

```python
@pytest.fixture
def test_db():
    """Create test database."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE insights (
            id TEXT PRIMARY KEY,
            topic TEXT,
            text TEXT
        )
    """)
    conn.commit()
    yield conn
    conn.close()

def test_get_topics(test_db):
    """Test topic retrieval."""
    cursor = test_db.cursor()
    cursor.execute("INSERT INTO insights VALUES (?, ?, ?)",
                   ("1", "AI", "Test insight"))
    test_db.commit()

    topics = get_all_topics(test_db)
    assert "AI" in topics
```

## Writing Tests

### Guidelines

1. **One assertion per test when possible**
   - Makes failures easier to diagnose
   - Test one behavior at a time

2. **Use descriptive test names**
   - `test_validate_topic_rejects_short_input`
   - `test_semantic_search_returns_similar_topics`

3. **Arrange-Act-Assert pattern**
   ```python
   def test_example():
       # Arrange: Set up test data
       topic = "AI agents"

       # Act: Execute function
       result = validate_topic(topic)

       # Assert: Verify result
       assert result[0] is True
   ```

4. **Test edge cases**
   - Empty inputs
   - Null values
   - Maximum lengths
   - Invalid characters

5. **Mock external dependencies**
   ```python
   def test_api_call(mocker):
       mock_response = mocker.Mock()
       mock_response.json.return_value = {"data": "test"}
       mocker.patch("requests.get", return_value=mock_response)

       result = fetch_data()
       assert result == {"data": "test"}
   ```

## Test Coverage

### Target Coverage
- Overall: 80% minimum
- Critical paths: 100%
- Utility functions: 100%
- Integration: Key flows only

### Generate Coverage Report
```bash
python -m pytest --cov=backend --cov-report=html tests/
open htmlcov/index.html
```

## Continuous Integration

### Pre-commit Checks
```bash
# Install pre-commit hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

### CI Pipeline
1. Linting (ruff, mypy)
2. Unit tests
3. Integration tests
4. Coverage check

## Common Test Utilities

### Database Setup
```python
def setup_test_db():
    """Create test database with schema."""
    conn = sqlite3.connect(":memory:")
    with open("db/schema.sql") as f:
        conn.executescript(f.read())
    return conn
```

### API Client
```python
@pytest.fixture
def client():
    """FastAPI test client."""
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)
```

### Auth Token
```python
@pytest.fixture
def test_user_token():
    """Generate test JWT token."""
    return generate_test_token(user_id="test-user")
```

## Debugging Tests

### Run with print statements
```bash
python -m pytest -s tests/
```

### Run with debugger
```python
def test_example():
    import pdb; pdb.set_trace()
    result = function_to_test()
    assert result == expected
```

### Show full diff on failure
```bash
python -m pytest -vv tests/
```

## Best Practices

1. **Keep tests fast**
   - Use in-memory databases
   - Mock external services
   - Avoid sleep() calls

2. **Independent tests**
   - Each test should run independently
   - Don't rely on test execution order
   - Clean up after each test

3. **Readable tests**
   - Clear test names
   - Minimal comments (test should be self-explanatory)
   - Use helper functions for setup

4. **Test behavior, not implementation**
   - Test what the function does, not how
   - Don't test private methods directly

5. **Maintain tests**
   - Update tests when code changes
   - Remove obsolete tests
   - Keep test data realistic

## Troubleshooting

### Import errors
```python
# Add project root to path in conftest.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
```

### Database locked
```python
# Use separate test database
@pytest.fixture
def test_db():
    db_path = "test_insights.db"
    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()
    os.remove(db_path)
```

### Async tests
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result is not None
```

---

**Last Updated:** December 2024
