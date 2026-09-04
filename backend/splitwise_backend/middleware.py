import logging

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        print(f"\n--- [INCOMING REQUEST] {request.method} {request.get_full_path()} ---")
        
        # Print headers safely
        headers = {}
        for key, value in request.META.items():
            if key.startswith('HTTP_') or key in ['CONTENT_TYPE', 'CONTENT_LENGTH']:
                headers[key] = value
        print("HEADERS:", headers)

        # Print body safely (only for smaller payloads)
        if request.body:
            try:
                # Don't print massive file uploads or binary data
                body = request.body.decode('utf-8')
                if len(body) > 1000:
                    print("BODY:", body[:1000] + "... [TRUNCATED]")
                else:
                    print("BODY:", body)
            except UnicodeDecodeError:
                print("BODY: <Binary Data>")
        
        response = self.get_response(request)
        
        print(f"--- [RESPONSE] {response.status_code} ---\n")
        
        return response
