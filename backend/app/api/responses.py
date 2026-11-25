from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.schemas.auth import DataResponse, RequestMeta, T
from app.services.complaints import ComplaintConflict, ComplaintNotFound, ComplaintUnavailable, InvalidComplaintValue

_ERROR_CODES = {
    401: "AUTHENTICATION_FAILED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    503: "SERVICE_UNAVAILABLE",
}
_COMPLAINT_ERRORS = {
    ComplaintNotFound: 404,
    ComplaintConflict: 409,
    InvalidComplaintValue: 422,
    ComplaintUnavailable: 503,
}


def success(request: Request, data: T) -> DataResponse[T]:
    return DataResponse(data=data, meta=RequestMeta(request_id=request.state.request_id))


def install_api_responses(app: FastAPI) -> None:
    @app.middleware("http")
    async def identify_request(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            headers=error.headers,
            content={
                "error": {
                    "code": _ERROR_CODES.get(error.status_code, "HTTP_ERROR"),
                    "message": error.detail,
                    "details": [],
                    "request_id": request.state.request_id,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "The request contains invalid fields.",
                    "details": [
                        {"field": ".".join(map(str, field["loc"])), "type": field["type"]}
                        for field in error.errors()
                    ],
                    "request_id": request.state.request_id,
                }
            },
        )

    async def complaint_error(request: Request, error: Exception) -> JSONResponse:
        return await http_error(request, HTTPException(_COMPLAINT_ERRORS[type(error)], str(error)))

    for error_type in _COMPLAINT_ERRORS:
        app.add_exception_handler(error_type, complaint_error)
