import os

from capture import install

if os.environ.get('YAHOO_CLI_URL'):
    install(os.environ['PUBLIC_SERVICE_URL'] + '/yahoo')
