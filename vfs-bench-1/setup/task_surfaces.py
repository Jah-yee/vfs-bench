"""Apply the shared shell contract without replacing existing service CLIs."""
import json
import re
import textwrap
from copy import deepcopy
from pathlib import Path

import yaml

from server.mcp.mcp_servers import timeout_for, upstream_config
from task import mcpatlas
from task.toolathlon import (TOOL_COMMANDS, needed_local_tools,
                             needed_mcp_servers)

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / 'task/toolathlon/ab-testing/vfs/workspace.yaml'
# Every command each tool CLI lists, with the description and input schema
# its `<cli> <tool> --help` returns; written by
# task/toolathlon/script/capture_cli_tools.py.
CLI_TOOLS = REPO / 'setup/toolathlon/cli_tools.json'
# The same for each MCP-Atlas task, keyed by task: an Atlas CLI lists only
# the tools the task's row enables; written by
# task/mcpatlas/script/capture_cli_tools.py.
ATLAS_CLI_TOOLS = REPO / 'setup/mcpatlas/cli_tools.json'
# Atlas's tool CLIs: its servers' tools as commands.
ATLAS_TOOL_COMMANDS = set(mcpatlas.TOOL_COMMANDS)
# An Atlas CLI that drops its tools' upstream prefix, as cli/mcpatlas/tool.mjs
# builds it: Notion's generated `API-post-search` is `notion post-search`.
ATLAS_PREFIXES = {'notion': 'API-'}
# Commands with their own syntax, documented in `upgrade`'s `native`.
NATIVE = ('gh', 'hf', 'git', 'kubectl', 'helm', 'mysql')

# One worked call for each tool an MCP-Atlas task's CLI lists; a task's
# section shows those of the tools its CLIs list. Slack's
# `conversations_add_message` has none: upstream's template sets no
# SLACK_MCP_ADD_MESSAGE_TOOL, so the server refuses every post on both arms,
# and a worked call would show one that cannot succeed.
ATLAS_EXAMPLES = {
    'airtable': [
        ('list-bases', {}),
        ('list-tables', {
            'base_id': 'BASE_ID'
        }),
        ('list-records', {
            'base_id': 'BASE_ID',
            'table_name': 'TABLE',
            'max_records': 10
        }),
        ('search-records', {
            'base_id': 'BASE_ID',
            'table_name': 'TABLE',
            'field_name': 'FIELD',
            'value': 'VALUE'
        }),
        ('get-record', {
            'base_id': 'BASE_ID',
            'table_name': 'TABLE',
            'record_id': 'RECORD_ID'
        }),
    ],
    'arxiv': [('search-papers', {
        'query': 'QUERY',
        'max_results': 5
    })],
    'calculator': [('calculate', {
        'expression': '2 * (3 + 4)'
    })],
    'clinicaltrialsgov-mcp-server': [
        ('clinicaltrials-list-studies', {
            'query': {
                'cond': 'CONDITION'
            },
            'pageSize': 10
        }),
        ('clinicaltrials-get-study', {
            'nctIds': 'NCT00000000',
            'summaryOnly': True
        }),
        ('clinicaltrials-analyze-trends', {
            'analysisType': 'countByPhase',
            'query': {
                'cond': 'CONDITION'
            }
        }),
    ],
    'context7': [
        ('resolve-library-id', {
            'libraryName': 'LIBRARY'
        }),
        ('get-library-docs', {
            'context7CompatibleLibraryID': '/ORG/PROJECT',
            'topic': 'TOPIC'
        }),
    ],
    'ddg-search': [
        ('search', {
            'query': 'QUERY',
            'max_results': 5
        }),
        ('fetch-content', {
            'url': 'https://example.com'
        }),
    ],
    'e2b-server': [('run-code', {
        'code': 'print(1 + 1)'
    })],
    'exa': [('web-search-exa', {
        'query': 'QUERY',
        'numResults': 5
    })],
    'fetch': [('fetch', {
        'url': 'https://example.com'
    })],
    'google-maps': [
        ('maps-search-places', {
            'query': 'QUERY'
        }),
        ('maps-geocode', {
            'address': 'ADDRESS'
        }),
        ('maps-reverse-geocode', {
            'latitude': '#LATITUDE',
            'longitude': '#LONGITUDE'
        }),
        ('maps-place-details', {
            'place_id': 'PLACE_ID'
        }),
        ('maps-directions', {
            'origin': 'ORIGIN',
            'destination': 'DESTINATION',
            'mode': 'driving'
        }),
        ('maps-distance-matrix', {
            'origins': ['ORIGIN'],
            'destinations': ['DESTINATION'],
            'mode': 'driving'
        }),
        ('maps-elevation', {
            'locations': [{
                'latitude': '#LATITUDE',
                'longitude': '#LONGITUDE'
            }]
        }),
    ],
    'google-workspace': [('list-events', {
        'timeMin': 'YYYY-MM-DDT00:00:00Z',
        'timeMax': 'YYYY-MM-DDT00:00:00Z',
        'maxResults': 50
    })],
    'memory': [
        ('read-graph', {}),
        ('search-nodes', {
            'query': 'QUERY'
        }),
        ('open-nodes', {
            'names': ['NAME']
        }),
    ],
    'mcp-server-code-runner': [('run-code', {
        'code': 'print(1 + 1)',
        'languageId': 'python'
    })],
    'met-museum': [
        ('list-departments', {}),
        ('search-museum-objects', {
            'q': 'QUERY',
            'hasImages': True
        }),
        ('get-museum-object', {
            'objectId': '#OBJECT_ID'
        }),
    ],
    'mongodb': [
        ('list-databases', {}),
        ('list-collections', {
            'database': 'DATABASE'
        }),
        ('collection-schema', {
            'database': 'DATABASE',
            'collection': 'COLLECTION'
        }),
        ('collection-indexes', {
            'database': 'DATABASE',
            'collection': 'COLLECTION'
        }),
        ('find', {
            'database': 'DATABASE',
            'collection': 'COLLECTION',
            'filter': {
                'FIELD': 'VALUE'
            },
            'limit': 10
        }),
        ('count', {
            'database': 'DATABASE',
            'collection': 'COLLECTION',
            'query': {
                'FIELD': 'VALUE'
            }
        }),
        ('aggregate', {
            'database': 'DATABASE',
            'collection': 'COLLECTION',
            'pipeline': [{
                '$group': {
                    '_id': '$FIELD',
                    'total': {
                        '$sum': 1
                    }
                }
            }]
        }),
        ('collection-storage-size', {
            'database': 'DATABASE',
            'collection': 'COLLECTION'
        }),
        ('db-stats', {
            'database': 'DATABASE'
        }),
        ('explain', {
            'database':
            'DATABASE',
            'collection':
            'COLLECTION',
            'method': [{
                'name': 'find',
                'arguments': {
                    'filter': {
                        'FIELD': 'VALUE'
                    }
                }
            }]
        }),
    ],
    'national-parks': [
        ('findParks', {
            'stateCode': 'CA',
            'q': 'QUERY'
        }),
        ('getParkDetails', {
            'parkCode': 'PARK_CODE'
        }),
        ('getCampgrounds', {
            'parkCode': 'PARK_CODE',
            'limit': 10
        }),
        ('getVisitorCenters', {
            'parkCode': 'PARK_CODE'
        }),
    ],
    'notion': [
        ('post-search', {
            'query': 'QUERY'
        }),
        ('post-database-query', {
            'database_id': 'ID',
            'filter': {
                'property': 'Name',
                'rich_text': {
                    'contains': 'TEXT'
                }
            },
            'page_size': 10
        }),
        ('retrieve-a-database', {
            'database_id': 'ID'
        }),
        ('retrieve-a-page', {
            'page_id': 'ID'
        }),
        ('retrieve-a-page-property', {
            'page_id': 'ID',
            'property_id': 'PROPERTY_ID'
        }),
        ('retrieve-a-block', {
            'block_id': 'ID'
        }),
        ('get-block-children', {
            'block_id': 'ID'
        }),
        ('retrieve-a-comment', {
            'block_id': 'ID'
        }),
        ('get-users', {}),
        ('get-user', {
            'user_id': 'ID'
        }),
        ('get-self', {}),
    ],
    'open-library': [
        ('get-book-by-title', {
            'title': 'TITLE'
        }),
        ('get-authors-by-name', {
            'name': 'NAME'
        }),
        ('get-author-info', {
            'author_key': 'AUTHOR_KEY'
        }),
        ('get-book-by-id', {
            'idType': 'isbn',
            'idValue': 'ISBN'
        }),
        ('get-book-cover', {
            'key': 'ISBN',
            'value': 'ISBN',
            'size': 'M'
        }),
        ('get-author-photo', {
            'olid': 'AUTHOR_OLID'
        }),
    ],
    'osm-mcp-server': [
        ('geocode-address', {
            'address': 'ADDRESS'
        }),
        ('reverse-geocode', {
            'latitude': '#LATITUDE',
            'longitude': '#LONGITUDE'
        }),
        ('get-route-directions', {
            'from_latitude': '#FROM_LATITUDE',
            'from_longitude': '#FROM_LONGITUDE',
            'to_latitude': '#TO_LATITUDE',
            'to_longitude': '#TO_LONGITUDE',
            'mode': 'car'
        }),
        ('analyze-neighborhood', {
            'latitude': '#LATITUDE',
            'longitude': '#LONGITUDE',
            'radius': 1000
        }),
        ('find-schools-nearby', {
            'latitude': '#LATITUDE',
            'longitude': '#LONGITUDE',
            'radius': 2000
        }),
        ('find-parking-facilities', {
            'latitude': '#LATITUDE',
            'longitude': '#LONGITUDE',
            'radius': 1000
        }),
        ('find-nearby-places', {
            'latitude': '#LATITUDE',
            'longitude': '#LONGITUDE',
            'radius': 1000,
            'limit': 20
        }),
        ('find-ev-charging-stations', {
            'latitude': '#LATITUDE',
            'longitude': '#LONGITUDE',
            'radius': 5000
        }),
    ],
    'oxylabs': [
        ('universal-scraper', {
            'url': 'https://example.com',
            'output_format': 'md'
        }),
        ('google-search-scraper', {
            'query': 'QUERY'
        }),
        ('amazon-search-scraper', {
            'query': 'QUERY'
        }),
    ],
    'pubmed': [
        ('search-pubmed-advanced', {
            'term': 'QUERY',
            'num_results': 5
        }),
        ('get-pubmed-article-metadata', {
            'pmid': 'PMID'
        }),
        ('search-pubmed-key-words', {
            'key_words': 'QUERY',
            'num_results': 5
        }),
        ('download-pubmed-pdf', {
            'pmid': 'PMID'
        }),
    ],
    'slack': [
        ('channels-list', {
            'channel_types': 'public_channel,private_channel'
        }),
        ('conversations-history', {
            'channel_id': 'CHANNEL_ID',
            'limit': '1d'
        }),
        ('conversations-replies', {
            'channel_id': 'CHANNEL_ID',
            'thread_ts': '1234567890.123456'
        }),
        ('conversations-search-messages', {
            'search_query': 'QUERY',
            'filter_in_channel': 'CHANNEL_ID'
        }),
    ],
    'weather': [
        ('find-weather-stations', {
            'location': '40.7128,-74.0060'
        }),
        ('get-current-weather', {
            'location': '40.7128,-74.0060'
        }),
        ('get-weather-forecast', {
            'location': '40.7128,-74.0060',
            'days': 3
        }),
        ('get-hourly-forecast', {
            'location': '40.7128,-74.0060',
            'hours': 12
        }),
        ('get-weather-alerts', {
            'location': 'CA'
        }),
        ('get-local-time', {
            'location': '40.7128,-74.0060'
        }),
    ],
    'weather-data': [
        ('weather-search', {
            'q': 'CITY'
        }),
        ('weather-history', {
            'q': 'CITY',
            'dt': '2025-06-01'
        }),
        ('weather-astronomy', {
            'q': 'CITY',
            'dt': '2025-06-01'
        }),
        ('weather-alerts', {
            'q': 'CITY'
        }),
        ('weather-current', {
            'q': 'CITY'
        }),
        ('weather-forecast', {
            'q': 'CITY',
            'days': 3
        }),
        ('weather-airquality', {
            'q': 'CITY'
        }),
    ],
    'whois': [
        ('whois-domain', {
            'domain': 'example.com'
        }),
        ('whois-ip', {
            'ip': '192.0.2.1'
        }),
        ('whois-tld', {
            'tld': 'com'
        }),
    ],
    'wikipedia': [
        ('search-wikipedia', {
            'query': 'QUERY'
        }),
        ('get-article', {
            'title': 'TITLE'
        }),
        ('get-summary', {
            'title': 'TITLE'
        }),
        ('summarize-article-for-query', {
            'title': 'TITLE',
            'query': 'QUERY'
        }),
        ('summarize-article-section', {
            'title': 'TITLE',
            'section_title': 'SECTION'
        }),
        ('extract-key-facts', {
            'title': 'TITLE',
            'count': 5
        }),
        ('get-links', {
            'title': 'TITLE'
        }),
        ('get-sections', {
            'title': 'TITLE'
        }),
        ('get-related-topics', {
            'title': 'TITLE',
            'limit': 10
        }),
    ],
}


def example(cli, command, arguments):
    """One worked call, as the model would type it."""
    if arguments is None:
        return f'{cli} {command} - < /workspace/arguments.json'
    text = json.dumps(arguments, ensure_ascii=False, separators=(',', ':'))
    return f"{cli} {command} '" + re.sub(r'"#([A-Z_]+)"', r'\1', text) + "'"


def summary(description):
    """The first paragraph of a tool's description, on one table row."""
    first = re.split(r'\n\s*\n', description.strip())[0]
    return ' '.join(first.split()).replace('|', '\\|')


def fill(text):
    """Wrap prose without breaking inside a `code` span."""
    kept = re.sub(r'`[^`]*`', lambda m: m.group(0).replace(' ', '\0'), text)
    return textwrap.fill(kept,
                         76,
                         break_on_hyphens=False,
                         break_long_words=False).replace('\0', ' ')


# Each JSON Schema type as the Arguments column spells it.
TYPES = {
    'string': 'str',
    'integer': 'int',
    'number': 'number',
    'boolean': 'bool',
    'array': 'list',
    'object': 'dict',
    'null': 'null',
}


def resolved(schema, defs):
    """The schema itself, not a `$ref` to one of its `$defs`."""
    while '$ref' in schema:
        schema = defs[schema['$ref'].rsplit('/', 1)[-1]]
    return schema


def spelled(schema, defs, nested=False):
    """An argument's type: `str`, `list[int]`, an enum's values, or a
    top-level object's own fields."""
    schema = resolved(schema, defs)
    if 'enum' in schema:
        return ' | '.join(
            json.dumps(value, ensure_ascii=False) for value in schema['enum'])
    alternatives = schema.get('anyOf') or schema.get('oneOf')
    if alternatives:
        return ' | '.join(
            dict.fromkeys(
                spelled(item, defs, nested) for item in alternatives))
    kind = schema.get('type')
    if isinstance(kind, list):
        return ' | '.join(TYPES.get(item, item) for item in kind)
    if kind == 'array' and schema.get('items'):
        return f"list[{spelled(schema['items'], defs, nested)}]"
    if kind == 'object' and schema.get('properties') and not nested:
        return fields(schema, defs, True)
    return TYPES.get(kind, 'any')


def fields(schema, defs, nested=False):
    """`{name: type, optional?: type = default}` for a schema's properties."""
    required = set(schema.get('required') or [])
    parts = []
    for name, value in (schema.get('properties') or {}).items():
        kind = spelled(value, defs, nested)
        source = value if 'default' in value else resolved(value, defs)
        if 'default' in source and source['default'] is None:
            # A null default says the argument may be null.
            kind = kind.removesuffix(' | null')
        part = f"{name}{'' if name in required else '?'}: {kind}"
        if 'default' in source:
            part += ' = ' + json.dumps(source['default'], ensure_ascii=False)
        parts.append(part)
    return '{' + ', '.join(parts) + '}'


def cell(text):
    """Text as a table cell's code span."""
    return '`' + text.replace('|', '\\|') + '`'


def prose(description):
    """A description on one table line: whitespace folded in its prose, and
    each line break inside a fenced code block kept as `<br>`, so an example
    with a `#` comment still reads line by line."""
    return ' '.join(
        part.strip('\n').replace('\n', '<br>') if part.
        startswith('```') else ' '.join(part.split())
        for part in re.split(r'(```.*?```)', description, flags=re.S)
        if part.strip())


def written(schema, defs, seen=()):
    """`spelled`, with every nested object's own fields, as the MCP arm's
    tool schema gives them, a map's too when its values have fields; a
    `$ref` back into itself stays `dict`."""
    ref = schema.get('$ref', '').rsplit('/', 1)[-1]
    if ref and ref in seen:
        return 'dict'
    seen += (ref, ) if ref else ()
    schema = resolved(schema, defs)
    if 'enum' in schema:
        return ' | '.join(
            json.dumps(value, ensure_ascii=False) for value in schema['enum'])
    alternatives = schema.get('anyOf') or schema.get('oneOf')
    if alternatives:
        return ' | '.join(
            dict.fromkeys(written(item, defs, seen) for item in alternatives))
    kind = schema.get('type')
    if isinstance(kind, list):
        return ' | '.join(TYPES.get(item, item) for item in kind)
    if kind == 'array' and schema.get('items'):
        return f"list[{written(schema['items'], defs, seen)}]"
    if kind == 'object' and schema.get('properties'):
        return signature(schema, defs, seen)
    values = schema.get('additionalProperties')
    if kind == 'object' and isinstance(values, dict):
        value = resolved(values, defs)
        parts = [value, *(value.get('anyOf') or value.get('oneOf') or [])]
        if any(resolved(part, defs).get('properties') for part in parts):
            return f'dict[str, {written(values, defs, seen)}]'
    return TYPES.get(kind, 'any')


def signature(schema, defs, seen=()):
    """`fields`, with nested objects spelled out at every depth."""
    required = set(schema.get('required') or [])
    parts = []
    for name, value in (schema.get('properties') or {}).items():
        kind = written(value, defs, seen)
        source = value if 'default' in value else resolved(value, defs)
        if 'default' in source and source['default'] is None:
            kind = kind.removesuffix(' | null')
        part = f"{name}{'' if name in required else '?'}: {kind}"
        if 'default' in source:
            part += ' = ' + json.dumps(source['default'], ensure_ascii=False)
        parts.append(part)
    return '{' + ', '.join(parts) + '}'


def notes(schema, defs, said, prefix='', seen=()):
    """Each argument's own description, nested ones by their dotted path,
    where the tool's description does not already say it."""
    found = []
    for name, value in (schema.get('properties') or {}).items():
        ref = value.get('$ref', '').rsplit('/', 1)[-1]
        if ref and ref in seen:
            continue
        inner = resolved(value, defs)
        text = ' '.join((value.get('description') or inner.get('description')
                         or '').split())
        if text and text not in said:
            found.append(f'`{prefix}{name}`: {text}')
        for part in [
                inner,
                inner.get('items') or {},
                *(inner.get('anyOf') or inner.get('oneOf') or [])
        ]:
            if isinstance(part, dict):
                found += notes(resolved(part, defs), defs, said,
                               f'{prefix}{name}.', seen + ((ref, ) if ref else
                                                           ()))
    return list(dict.fromkeys(found))


def tool_section(cli):
    """A tool CLI's SKILL.md section: how to call it, then every command it
    lists with each argument's type and description and its whole upstream
    description, so the model has each tool's name, arguments and purpose up
    front as the MCP arm's tool list gives them.
    """
    usage = (f"Use `{cli} <command> '<JSON arguments>'`. Run "
             f'`{cli} <command> --help` to get more information.')
    rows = []
    for tool in json.loads(CLI_TOOLS.read_text())[cli]:
        schema = tool['inputSchema'] or {}
        defs = schema.get('$defs', {})
        said = prose(tool['description'] or '')
        described = ' — '.join(
            part for part in (said, '; '.join(notes(schema, defs, said)))
            if part).replace('|', '\\|')
        rows.append(f"| {cell(cli + ' ' + tool['command'])} | "
                    f"{cell(signature(schema, defs))} | {described} |")
    return '\n\n'.join([
        fill(usage), '| Command | Arguments | Description |\n|---|---|---|\n' +
        '\n'.join(rows)
    ])


def atlas_tool_section(task, cli):
    """An MCP-Atlas task's tool CLI section, laid out as Toolathlon's: how
    to call it, a worked call for each command that has one, then every
    command with the type of each argument and the first paragraph of its
    upstream description.

    The table is what the task's CLI lists, which is the tools Atlas's row
    enables and no others.
    """
    tools = json.loads(ATLAS_CLI_TOOLS.read_text())[task][cli]
    calls = dict(ATLAS_EXAMPLES[cli])
    usage = (f"Use `{cli} <command> '<JSON arguments>'`. Run "
             f'`{cli} <command> --help` to get more information.')
    rows = []
    for tool in tools:
        schema = tool['inputSchema'] or {}
        rows.append(f"| {cell(cli + ' ' + tool['command'])} | "
                    f"{cell(fields(schema, schema.get('$defs', {})))} | "
                    f"{summary(tool['description'])} |")
    worked = [
        example(cli, tool['command'], calls[tool['command']]) for tool in tools
        if tool['command'] in calls
    ]
    return '\n\n'.join([
        fill(usage), '```sh\n' + '\n'.join(worked) + '\n```',
        '| Command | Arguments | Description |\n|---|---|---|\n' +
        '\n'.join(rows)
    ])


def atlas_skill(task):
    """Re-render an MCP-Atlas task's tool CLI sections in its SKILL.md.

    The head and `python3` are written by hand and kept; the tool
    sections follow the task's own, in its yaml's order, ahead of
    `python3`.
    """
    directory = REPO / 'task/mcpatlas' / task / 'vfs'
    clis = [
        name
        for name in (yaml.safe_load((directory / 'workspace.yaml').read_text())
                     or {}).get('clis') or {} if name in ATLAS_TOOL_COMMANDS
    ]
    head, *parts = (directory / 'SKILL.md').read_text().split('\n## ')
    kept = [
        part for part in parts
        if not set(part.split('\n', 1)[0].split(', ')) <= ATLAS_TOOL_COMMANDS
    ]
    python = [part for part in kept if part.startswith('python3\n')]
    rendered = [f'{cli}\n\n{atlas_tool_section(task, cli)}\n' for cli in clis]
    (directory / 'SKILL.md').write_text(
        '\n## '.join([head] + [part for part in kept if part not in python] +
                     rendered + python))


class WorkspaceDumper(yaml.SafeDumper):

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def upstream_python(task):
    if 'python_execute' in needed_local_tools(task):
        return True
    if 'terminal' not in needed_mcp_servers(task):
        return False
    config = yaml.safe_load(upstream_config('terminal'))
    allowed = config['params']['env']['ALLOWED_COMMANDS'].split(',')
    return bool({'python', 'python3'} & {cmd.strip() for cmd in allowed})


def upstream_network(task):
    """Whether this arm's `curl` reaches the public network.

    It does where upstream's terminal or python_execute does
    (agent/arms.py `public_network`). Kubernetes tasks keep neither, but
    for the one with a browser, whose sandbox keeps the network.
    """
    servers = needed_mcp_servers(task)
    shell = 'terminal' in servers or 'python_execute' in needed_local_tools(
        task)
    if 'k8s' in servers:
        return shell and 'playwright_with_chunk' in servers
    return shell


def upstream_git(task):
    """Whether this arm's `git` stands in for one upstream's model has.

    Upstream's git server is one. Its terminal is the other: `git` is in
    its ALLOWED_COMMANDS, and its task image has git 2.34.1. The
    Kubernetes task with a browser already runs git natively in its
    sandbox (server/shared_workspace.py `BROWSER_CAPTURES`).
    """
    servers = needed_mcp_servers(task)
    return 'git' in servers or (
        'terminal' in servers
        and not ('k8s' in servers and 'playwright_with_chunk' in servers))


def upgrade(task):
    """Reuse each registered CLI; fill missing original-tool transports."""
    from server.seed.travel_video import DOCUMENT_TOOLS, GOOGLE_TOOLS, TOOLS

    directory = REPO / 'task/toolathlon' / task / 'vfs'
    workspace = yaml.safe_load((directory / 'workspace.yaml').read_text())
    servers = needed_mcp_servers(task)
    python = upstream_python(task)
    # Upstream's terminal runs commands under LC_CTYPE=C.UTF-8 (its Python
    # coerces the C locale, PEP 538), where GNU grep, sed and expr match
    # whole characters; Mirage's do so only under a UTF-8 locale.
    workspace.setdefault('env', {}).update(HOME='/workspace',
                                           LC_CTYPE='C.UTF-8')
    workspace.setdefault('profiles', {}).setdefault('default',
                                                    {})['cwd'] = '/workspace'
    workspace['runtimes'] = (deepcopy(
        yaml.safe_load(TEMPLATE.read_text())['runtimes'])
                             if python else ['workspace'])
    mounts = workspace['mounts']
    if '/work' in mounts:
        mounts['/workspace'] = mounts.pop('/work')
    mounts.pop('/opt/wheels', None)
    clis = workspace.setdefault('clis', {})
    if 'web_search' in needed_local_tools(task):
        clis.setdefault(
            'web-search', {
                'cli': '../../../../cli/toolathlon/research.mjs:SEARCH',
                'config': {
                    'apiBase': '${SEARCH_CLI_URL}'
                }
            })
    definitions = {**TOOLS, **GOOGLE_TOOLS, **DOCUMENT_TOOLS}
    for kind, name, export in TOOL_COMMANDS:
        if kind in servers and name not in clis:
            clis[name] = {
                'cli': '../../../../' + export,
                'config': {
                    'apiBase': '${' + definitions[kind][2] + '}',
                    'timeoutMs': 1000 * timeout_for(kind)
                }
            }
    if upstream_git(task):
        clis.setdefault('git', {'cli': 'git'})
    transports = {
        export.rsplit(':', 1)[-1]: kind
        for kind, _, export in TOOL_COMMANDS
    }
    transports.update(BROWSER='playwright_with_chunk',
                      CANVAS='canvas',
                      WOOCOMMERCE='woocommerce',
                      ARXIV='arxiv_local',
                      ARXIV_LATEX='arxiv-latex',
                      SCHOLARLY='scholarly',
                      MAPS='google_map',
                      YOUTUBE='youtube',
                      TRANSCRIPT='youtube-transcript',
                      RAIL='rail_12306',
                      FORMS='google_forms')
    for spec in clis.values():
        kind = transports.get(str(spec.get('cli', '')).rsplit(':', 1)[-1])
        if kind in servers:
            spec.setdefault('config',
                            {})['timeoutMs'] = 1000 * timeout_for(kind)
    # Repository files remain hf/VFS operations. Search, Dataset Viewer and
    # other MCP-only operations reuse the existing Hub transport.
    if 'huggingface' in servers:
        live = task == 'vlm-history-completer'
        clis.setdefault(
            'huggingface', {
                'cli': '../../../../cli/toolathlon/hub.mjs:HUB',
                'config': {
                    'endpoint': 'https://huggingface.co/mcp'
                    if live else 'http://127.0.0.1:5200/mcp',
                    'token': '${HF_TOKEN}' if live else task,
                }
            })
    (directory / 'workspace.yaml').write_text(
        yaml.dump(workspace, Dumper=WorkspaceDumper, sort_keys=False))
    skill = [
        '---\nname: workspace-commands\ndescription: The shell '
        'commands and task tools available in this '
        'workspace.\n---',
        '# Available commands',
    ]
    if not python:
        skill.append(
            'Python (`python` or `python3`), Perl, '
            'JavaScript/Node.js, and TypeScript\n'
            'runtimes are unavailable. Use the shell commands and '
            'task CLIs documented\n'
            'below; do not probe for or attempt to install other runtimes.')
    skill.append(
        'Standard Unix commands, among them:\n\n'
        '    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  '
        'tr  sed  awk\n'
        '    diff  tee  xargs  jq  unzip' +
        ('  curl' if upstream_network(task) else '') + '\n\n'
        "with pipes, `>` redirection, `$(...)` substitution and `$'...'`.")
    skill.append(
        'The task CLIs below are registered with this shell rather than '
        'installed\nas files; do not inspect them with `which`, `file` or '
        '`/usr/bin`.')
    native = {
        'gh':
        'Use `gh --help` for the registered GitHub commands. '
        'Repository, issue, pull-request, release and API '
        'operations use the same GitHub service as upstream MCP. '
        'Use `gh <command> --help` for arguments and output '
        'options.',
        'hf':
        'Use `hf --help` for Hugging Face repository, download '
        'and upload commands. Repository paths and revisions '
        'identify the same files as upstream. Use `huggingface` for the '
        'upstream MCP search and Dataset Viewer operations.',
        'git':
        'Use `git --help` for Git operations on workspace repositories.',
        'kubectl':
        'Use `kubectl --help` for Kubernetes reads and mutations '
        'against the task cluster. Use the original resource '
        'names, namespaces and selectors. Piped bytes reach '
        'stdin; file arguments under `/workspace` refer to task '
        'files.',
        'helm':
        'Use `helm --help` for Helm operations against the task cluster.',
        'mysql':
        'Use `mysql --help` for SQL connection options. Pass SQL '
        'with `-e` or piped stdin. Keep the requested port-forward '
        'running.',
    }
    for name in clis:
        skill.append('## ' + name)
        skill.append(native[name] if name in native else tool_section(name))
    if python:
        skill.extend([
            '## python3',
            'Execute Python code directly under the agent workspace '
            'and return stdout\n'
            'and stderr. Code can be pasted into a `.py` file and '
            'run with `python3`.\n\n'
            'Python cannot launch subprocesses or make direct '
            'network requests. Run the\n'
            'documented service commands directly in the shell. Use '
            'Python for local\n'
            'file processing and generating JSON arguments.'
        ])
    (directory / 'SKILL.md').write_text('\n\n'.join(skill) + '\n')
    lines = [
        '---', 'name: workspace-filesystem',
        'description: The virtual filesystem layout of this workspace.', '---',
        '', '# Virtual Filesystem', '',
        'You work in a terminal over a virtual filesystem. Read '
        'files with shell',
        'commands; service operations are listed in SKILL.md.', '',
        '| Path | Description |', '|---|---|',
        '| `/workspace` | Agent workspace; current directory and '
        'home (`~`). |', '| `/tmp` | Temporary files. |',
        '| `/dev` | Device files: `null` and `zero` (mounted automatically). |'
    ]
    for path, spec in mounts.items():
        if path in ('/workspace', '/tmp'):
            continue
        kind = spec['vfs'].split(':')[-1]

        # A read-only mount says so, and names the task's CLI that changes
        # what it holds; `wandb` and `huggingface` only read theirs.
        def change(noun, cli):
            return (f'; change {noun} with the `{cli}` CLI.'
                    if cli in clis else '.')

        description = {
            'email':
            'Mail folders and messages, read-only' + change('them', 'emails'),
            'notion':
            'Notion pages and databases, read-only' + change('them', 'notion'),
            'wandb':
            'W&B experiment metadata and captured histories, read-only.',
            'CanvasVFS':
            'Canvas courses, assignments, quizzes and files, read-only' +
            change('them', 'canvas'),
            'KubernetesVFS':
            'Kubernetes resources, read-only' + change('them', 'kubectl'),
            'WooCommerceVFS':
            'WooCommerce service objects, read-only' +
            change('them', 'woocommerce'),
            'gdrive':
            'Drive files and Sheets, read-only' +
            change('spreadsheets', 'google-sheet'),
        }.get(kind, kind + ' files.')
        cfg = spec.get('config', {})
        if kind == 'github':
            description = (f"GitHub repository `{cfg.get('owner')}/"
                           f"{cfg.get('repo')}`, ref `{cfg.get('ref')}`, "
                           'read-only' + change('it', 'gh'))
        elif kind.startswith('hf_'):
            description = (f"Hugging Face repository `{cfg.get('repo_id')}`, "
                           'read-only' + change('it', 'hf'))
        lines.append(f'| `{path}` | {description} |')
    (directory / 'VFS.md').write_text('\n'.join(lines) + '\n')
