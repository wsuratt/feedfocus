"""API response utilities."""

from fastapi.responses import JSONResponse
from typing import Any, Dict


def success_response(data: Any, status_code: int = 200) -> JSONResponse:
    """
    Create a successful JSON response.

    Args:
        data: Response data (dict, list, or any JSON-serializable object)
        status_code: HTTP status code

    Returns:
        JSONResponse with the data
    """
    return JSONResponse(content=data, status_code=status_code)


def error_response(message: str, status_code: int = 400, details: Dict = None) -> JSONResponse:
    """
    Create an error JSON response.

    Args:
        message: Error message
        status_code: HTTP status code
        details: Optional additional error details

    Returns:
        JSONResponse with error information
    """
    content: Dict[str, Any] = {"error": message}
    if details:
        content["details"] = details

    return JSONResponse(content=content, status_code=status_code)


def paginated_response(
    items: list,
    total: int,
    limit: int,
    offset: int,
    has_more: bool = None
) -> Dict:
    """
    Create a paginated response structure.

    Args:
        items: List of items for current page
        total: Total number of items
        limit: Items per page
        offset: Current offset
        has_more: Whether more items are available (calculated if not provided)

    Returns:
        Dictionary with pagination metadata
    """
    if has_more is None:
        has_more = offset + len(items) < total

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "count": len(items)
    }
