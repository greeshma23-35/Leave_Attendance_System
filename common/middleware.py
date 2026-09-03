import logging
import time

logger = logging.getLogger('apps')


class RequestLoggingMiddleware:
    """Logs method, path, status code and response time for every request.

    Useful for debugging and for spotting slow endpoints in production.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.monotonic()
        response = self.get_response(request)
        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            '%s %s -> %s (%.2fms)',
            request.method,
            request.get_full_path(),
            response.status_code,
            duration_ms,
        )
        return response
