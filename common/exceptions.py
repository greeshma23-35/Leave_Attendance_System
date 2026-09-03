import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger('apps')


class ApplicationError(Exception):
    """Base exception for predictable, business-rule violations.

    Raise this (or a subclass) anywhere in the service/view layer to return
    a clean, structured error response instead of a raw traceback.
    """

    def __init__(self, message, code='application_error', status_code=status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def custom_exception_handler(exc, context):
    """Wrap every API error in a single, predictable JSON envelope.

    Response shape:
    {
        "success": false,
        "error": {
            "code": "validation_error",
            "message": "...",
            "details": {...}
        }
    }
    """
    if isinstance(exc, ApplicationError):
        response = Response(
            {
                'success': False,
                'error': {
                    'code': exc.code,
                    'message': exc.message,
                    'details': None,
                },
            },
            status=exc.status_code,
        )
        return response

    if isinstance(exc, Http404):
        exc = drf_exceptions.NotFound()
    if isinstance(exc, PermissionDenied):
        exc = drf_exceptions.PermissionDenied()

    response = exception_handler(exc, context)

    if response is not None:
        error_code = getattr(exc, 'default_code', 'error')
        message = response.data
        details = None

        if isinstance(response.data, dict):
            # DRF field validation errors come back as {"field": ["msg"]}
            message = 'Validation failed.' if response.status_code == 400 else str(exc)
            details = response.data
        elif isinstance(response.data, list):
            message = ' '.join(str(item) for item in response.data)

        logger.warning(
            'API error [%s]: %s | path=%s',
            response.status_code,
            message,
            context['request'].path if 'request' in context else 'unknown',
        )

        response.data = {
            'success': False,
            'error': {
                'code': error_code,
                'message': message,
                'details': details,
            },
        }
    else:
        # Unhandled exception - log full details, hide internals from client
        logger.exception('Unhandled exception in %s', context.get('view'))

    return response
