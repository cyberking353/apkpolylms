class NoCacheHTMLMiddleware:
    """
    Prevent browsers from heuristically caching rendered HTML.

    Without explicit Cache-Control headers Chrome may serve stale pages
    (e.g. an old homepage after a deployment), especially on mobile.
    Static files keep their own caching; only dynamic HTML is affected.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        content_type = response.get('Content-Type', '')
        if content_type.startswith('text/html'):
            response['Cache-Control'] = 'no-cache'
        return response
