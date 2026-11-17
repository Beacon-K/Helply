"""Signed-in pages and API answers are private to the person who requested them."""
from django.utils.cache import add_never_cache_headers


class PrivateResponsesMiddleware:
    """Mark responses for signed-in users as not cacheable.

    Without it a browser may keep a copy of a signed-in page (including the assistant chat that was open)
    and show it again to the next person on a shared computer after logout, via the Back button. Views that
    already set their own Cache-Control keep it. Static files are served earlier by WhiteNoise and stay cacheable.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and not response.has_header("Cache-Control"):
            add_never_cache_headers(response)
        return response