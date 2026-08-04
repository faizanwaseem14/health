"""
The ONE response shape every endpoint uses - so the frontend only ever
needs to handle two possible shapes, forever:

    Success:  {"status": "success", "data": <whatever the route returns>}
    Error:    {"status": "error",   "detail": <a message, or list of messages>}

The error side is already handled everywhere automatically by the
global error handlers in app/core/errors.py (Task 15). This file is the
success side - call `success_response(...)` at the end of a route
instead of just returning a bare dict, so both halves of every response
share the same "status" contract.
"""

from typing import Any

from fastapi.responses import JSONResponse


def success_response(data: Any = None, status_code: int = 200) -> JSONResponse:
    """
    Wraps a route's actual payload in the standard success envelope.

    `data` should already be JSON-serializable (a dict, a list, or
    None) - the same kind of thing you'd normally just `return` from a
    route directly.
    """
    return JSONResponse(
        status_code=status_code, content={"status": "success", "data": data}
    )
