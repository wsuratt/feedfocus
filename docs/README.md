# Documentation

Comprehensive documentation for the Insight Feed platform.

## Core Documentation

### [Architecture](architecture.md)
Complete system architecture, technology stack, and design patterns.

**Topics covered:**
- Technology stack (FastAPI, React, ChromaDB, Claude, Groq)
- Application structure and file organization
- Pipeline architecture (discovery → extraction → filtering → storage)
- Quality filtering system (fast path + SLM evaluation)
- Vector database design
- Query generation strategy
- Performance and scalability
- Cost architecture
- Security patterns

**Read this if you want to understand:**
- How the system works end-to-end
- Why design decisions were made
- Where to find specific functionality

---

### [API Reference](api.md)
Complete HTTP API documentation with examples.

**Endpoints documented:**
- `GET /api/interests` - Get user interests
- `POST /api/interests` - Add interest
- `DELETE /api/interests/{id}` - Remove interest
- `GET /api/feed` - Get personalized insights
- `POST /api/feed/engage` - Record engagement
- `GET /api/stats` - Database statistics

**Read this if you want to:**
- Integrate with the API
- Understand request/response formats
- Test endpoints manually
- Build a client application

---

## Testing Documentation

### [Testing Guide](../tests/README.md)
How to run tests and debug the insight pipeline.

**Test scripts covered:**
- `test_quality.py` - End-to-end pipeline test
- `test_manual_extraction.py` - Single URL extraction test
- `test_extraction.py` - Extraction logic test
- `test_automation.py` - Automation components test

### [Training Data](../training_data/README.md)
Training data collection for fine-tuning a cheaper SLM to replace Claude.

**Collected data:**
- Extraction inputs/outputs (source content → insights)
- User engagement (likes, saves, dismissals)
- Query generation performance

**Cost savings:** 30x cheaper ($0.12/topic → $0.004/topic)

---

## Quick Navigation

**Getting Started:**
1. [Project README](../README.md) - Installation and quick start
2. [Architecture](architecture.md) - Understand the system
3. [API Reference](api.md) - Use the API

**Development:**
1. [Testing Guide](../tests/README.md) - Run tests
2. [Architecture](architecture.md#development-architecture) - Code organization
3. [API Reference](api.md#api-client-examples) - Client examples

**Debugging:**
1. [Testing Guide](../tests/README.md#common-issues) - Common issues
2. [Architecture](architecture.md#monitoring-and-observability) - Debug output
3. [API Reference](api.md#error-responses) - Error handling

---

## Contributing

When adding new features:

1. **Update Architecture** if system design changes
2. **Update API Docs** if endpoints change
3. **Add Tests** for new functionality
4. **Update README** if setup changes

---

## Documentation Standards

### Code Comments
- Docstrings for all public functions
- Type hints for function parameters
- Explain "why" not "what" in comments

### Architecture Docs
- Include code examples
- Show data flow diagrams (ASCII or Markdown)
- Link to relevant source files
- Keep up to date with major changes

### API Docs
- Provide curl examples
- Show full request/response JSON
- Document all error cases
- Include client library examples

---

**Last Updated**: November 2024
