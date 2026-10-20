import importlib.util
import sys
from pathlib import Path

# The name upstream's client imports. The Postgres behind it is
# `server/clients/snowflake.py`; this package is only the spelling.
# Importing either `snowflake.connector` or `snowflake.snowpark` runs this
# first, so registering the repository's package here covers both.
#
# Registered from its own files rather than found on sys.path: inside the
# runtime boundary the repository root is readable but not listable, and a
# path finder lists a directory before it looks inside.
REPO = Path(__file__).resolve().parents[3]
for name, folder in (('server', REPO / 'server'), ('server.clients',
                                                   REPO / 'server/clients')):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            name,
            folder / '__init__.py',
            submodule_search_locations=[str(folder)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
