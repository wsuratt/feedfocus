# Architecture Documentation

Complete technical documentation for the FeedFocus platform.

## Core Architecture

### [Application Architecture](application-architecture.md)
Overall system design, technology stack, and design patterns.

**Topics:**
- Technology stack (FastAPI, React, SQLite, ChromaDB, Claude)
- Application structure and file organization
- Pipeline architecture
- Performance and scalability
- Cost architecture

### [Database](database.md)
Database design and patterns for SQLite and ChromaDB.

**Topics:**
- SQLite schema and migrations
- ChromaDB vector storage
- Data models and relationships
- Query patterns
- Performance optimization

### [Authentication](authentication.md)
Supabase authentication implementation.

**Topics:**
- Auth flows (email/password, OAuth)
- Session management
- Protected routes
- Deep linking for mobile
- Token handling

### [API Endpoints](api-endpoints.md)
Backend API design and conventions.

**Topics:**
- FastAPI endpoints and patterns
- Request/response formats
- Authentication middleware
- Error handling
- CORS configuration

### [Unified Feed](unified-feed.md)
Feed generation and personalization system.

**Topics:**
- Feed architecture (For You / Following)
- ML-based scoring and ranking
- Engagement tracking
- Infinite scroll implementation
- Cross-platform consistency

## Feature Documentation

### [Extraction Pipeline](../features/extraction-pipeline-plan.md)
Search, extract, and refresh pipeline for content extraction.

**Status:** In Development

**See also:**
- [Implementation Plan](../features/extraction-pipeline-implementation.md)

## Development

### Running the Application
```bash
# Backend
cd feedfocus && uvicorn backend.main:app --reload

# Frontend
cd feedfocus/frontend && npm run dev

# Mobile
cd feedfocus-mobile && npx expo start
```

### Testing
```bash
# Run all tests
python -m pytest tests/

# Run specific test
python -m pytest tests/unit/test_topic_validation.py
```

### Code Quality
```bash
# Python linting
ruff check backend/

# Type checking
mypy backend/

# JavaScript linting
cd frontend && npm run lint
```

## Deployment

See [Deployment Guide](../deployment/deployment.md) for production setup.

---

**Last Updated:** December 2024
