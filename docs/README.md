# Documentation

Comprehensive documentation for the FeedFocus platform.

## Core Documentation

### [Architecture](architecture/)
Complete system architecture, technology stack, and design patterns.

**Key Documentation:**
- [Application Architecture](architecture/application-architecture.md) - System design and tech stack
- [Database](architecture/database.md) - SQLite and ChromaDB patterns
- [Authentication](architecture/authentication.md) - Supabase auth implementation
- [API Endpoints](architecture/api-endpoints.md) - Backend API design
- [Unified Feed](architecture/unified-feed.md) - Feed generation system

**See [Architecture README](architecture/README.md) for complete index.**

---

## Feature Documentation

### [Extraction Pipeline](features/extraction-pipeline-plan.md)
Search, extract, and refresh pipeline for content extraction.

**Status:** In Development

**Related:**
- [Implementation Plan](features/extraction-pipeline-implementation.md)

---

## Testing Documentation

### [Testing Guide](../tests/README.md)
How to run tests and debug the system.

**Test categories:**
- Unit tests for individual functions
- Integration tests for API endpoints
- End-to-end workflow tests

### [Training Data](../training_data/README.md)
Training data collection for SLM fine-tuning.

---

## Deployment

### [Deployment Guide](deployment/deployment.md)
Production deployment instructions and configuration.

---

## Quick Navigation

**Getting Started:**
1. [Project README](../README.md) - Installation and quick start
2. [Architecture Overview](architecture/) - Understand the system
3. [API Reference](architecture/api-endpoints.md) - Use the API

**Development:**
1. [Testing Guide](../tests/README.md) - Run tests
2. [Architecture Docs](architecture/) - Code organization
3. [.windsurfrules](../../.windsurfrules) - Coding guidelines

**Debugging:**
1. [Testing Guide](../tests/README.md) - Common issues
2. [Architecture Docs](architecture/) - System design

---

## Contributing

When adding new features:

1. **Read relevant architecture docs** before implementing
2. **Update architecture docs** if system design changes
3. **Add tests** for new functionality
4. **Update this README** if documentation structure changes

---

## Documentation Standards

### Code Documentation
- Minimal comments - code should be self-documenting
- Docstrings for public functions only
- Type hints for all function parameters
- Comments explain "why", not "what"

### Architecture Documentation
- Include code examples
- Show implementation patterns
- Link to relevant source files
- Keep up to date with changes

### API Documentation
- Provide examples with full request/response
- Document all error cases
- Show authentication patterns

---

**Last Updated:** December 2024
