"""Route libraries' HTTP reads through the shared public cache."""
import os
import urllib.parse
import urllib.request

BASE = os.environ.get('PAPER_API_URL')
if BASE:
    import requests.sessions
    original_send = requests.sessions.Session.send

    def send(self, request, **kwargs):
        if urllib.parse.urlsplit(
                request.url).hostname in ('arxiv.org', 'export.arxiv.org',
                                          'scholar.google.com'):
            request.url = BASE + '/fetch?url=' + urllib.parse.quote(
                request.url, safe='')
        return original_send(self, request, **kwargs)

    requests.sessions.Session.send = send
    original_open = urllib.request.urlopen

    def urlopen(url, *args, **kwargs):
        target = url.full_url if isinstance(url,
                                            urllib.request.Request) else url
        if urllib.parse.urlsplit(target).hostname in ('arxiv.org',
                                                      'export.arxiv.org',
                                                      'scholar.google.com'):
            url = BASE + '/fetch?url=' + urllib.parse.quote(target, safe='')
        return original_open(url, *args, **kwargs)

    urllib.request.urlopen = urlopen

    # Scholarly's navigator uses HTTPX; arxiv and the LaTeX package use
    # requests/urllib. Redirect at the transport so response cookie handling
    # still sees the original request URL.
    import httpx
    original_httpx = httpx.HTTPTransport.handle_request

    def handle_request(self, request):
        if request.url.host in ('arxiv.org', 'export.arxiv.org',
                                'scholar.google.com'):
            request = httpx.Request(
                request.method,
                BASE + '/fetch?url=' +
                urllib.parse.quote(str(request.url), safe=''),
                headers=request.headers,
                content=request.content,
                extensions=request.extensions)
        return original_httpx(self, request)

    httpx.HTTPTransport.handle_request = handle_request
