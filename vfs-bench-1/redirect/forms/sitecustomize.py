"""Route the unchanged Forms/Drive seeders and graders to their fixture."""
import os

BASE = os.environ.get('GWS_MOCK_URL', '').rstrip('/')
if BASE:
    import googleapiclient.discovery as discovery
    from google.api_core.client_options import ClientOptions

    original_build = discovery.build

    def build(serviceName, version=None, *args, **kwargs):
        path = {'drive': '/drive/v3/', 'forms': '/'}.get(serviceName)
        if path is not None and not kwargs.get('client_options'):
            kwargs['client_options'] = ClientOptions(api_endpoint=BASE + path)
        kwargs.setdefault('cache_discovery', False)
        return original_build(serviceName, version, *args, **kwargs)

    discovery.build = build
