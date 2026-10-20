# What the mirage arm refuses to run: a command that walks a whole mount and
# prints what it finds there, or reads every table of a base at once, a `cat`
# of a whole Airtable table, MongoDB collection or Notion database's rows, and
# a Notion search or database query that asks for everything. VFS.md already
# asks for the directory or file instead, and output comes back whole, so one
# such answer is re-sent with every request after it. A walk that prints
# little is let through: `find` or `tree` at most three levels deep, and a
# `grep` or `rg` that prints file names or nothing (`-l`, `-q`). Mirage hands
# this the command's words and the paths it will touch, resolved: a bare
# `find` or `grep -r` names the working directory. The model reads why from
# `shell_output` in __init__.py, since a refusal prints only
# `<command>: Permission denied`.
#
# A port of the JavaScript this was first written in, decision for decision,
# to monty's Python: where Python and JavaScript part (`Number()`, `trim()`,
# `JSON.parse`, a `RegExp` built from a glob), the JavaScript is what is
# spelled out below.
import json
import os
import re

# `/` holds every mount. /tmp is scratch, and each repository under
# /data/repos is a mount of its own that a search is meant to walk.
MOUNTS = ('/', '/data', '/airtable', '/calendar', '/mongodb', '/notion',
          '/slack')
# A directory that holds as much as its mount does: /data/repos holds
# every repository, and an Airtable base or a MongoDB database, alone in
# its mount, holds all of it.
WHOLE = (r'/data/repos', r'/airtable/bases(/[^/]+)?',
         r'/mongodb/[^/]+(/collections)?')
ROWS = ('records.jsonl', 'documents.jsonl', 'view.jsonl')
# What JavaScript's `trim()` strips and `\s` matches: its white space and
# line terminators.
SPACE = ('\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006'
         '\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff')
# JavaScript's `Number()` of a string, as far as `<= 3` can tell: decimal,
# or hex, octal or binary with no sign, or Infinity, the whitespace trimmed.
DECIMAL = r'[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?'
RADIX = {'0x': 16, '0X': 16, '0o': 8, '0O': 8, '0b': 2, '0B': 2}
DIGITS = {16: '[0-9a-fA-F]+', 8: '[0-7]+', 2: '[01]+'}
# What a word still holds when `pre_execute` sees it before the shell has
# expanded it: a quote, a `$`, a backquote, a backslash, a `~` or a brace.
# `{}`, `find -exec`'s, is no brace.
TYPED = '\'"\\$`~{'


def walked(path):
    return path in MOUNTS or any(re.fullmatch(whole, path) for whole in WHOLE)


def at_most_three(text):
    text = text.strip(SPACE)
    if text == '':
        return True
    if re.fullmatch(DECIMAL, text):
        return float(text) <= 3
    radix = RADIX.get(text[:2])
    if radix is not None and re.fullmatch(DIGITS[radix], text[2:]):
        return int(text[2:], radix) <= 3
    return text == '-Infinity'


def units(text):
    # A string as JavaScript holds it, in UTF-16 code units.
    out = []
    for char in text:
        point = ord(char)
        if point > 0xffff:
            point -= 0x10000
            out += [0xd800 + (point >> 10), 0xdc00 + (point & 0x3ff)]
        else:
            out.append(point)
    return out


def tokens(pattern):
    # The glob as `matches` turns it into a RegExp: each escaped character
    # is itself, `*` is `.*`, `?` is `.`, and a `[` opens a class that the
    # next `]` closes, `[]` matching nothing. In the class `*` is `.*` and
    # `?` is `.`, both literal there, and `-` between two members is a
    # range. A class left open, or a range out of order, is a RegExp that
    # does not compile, and so a refusal: `None`.
    glob = units(pattern)
    out = []
    i = 0
    while i < len(glob):
        unit = glob[i]
        i += 1
        if unit == ord('*'):
            out.append(('any', None))
        elif unit == ord('?'):
            out.append(('one', None))
        elif unit != ord('['):
            out.append(('is', [(unit, unit)]))
        else:
            if ord(']') not in glob[i:]:
                return None
            end = glob.index(ord(']'), i)
            atoms = []
            for member in glob[i:end]:
                if member == ord('*'):
                    atoms += [ord('.'), ord('*')]
                elif member == ord('?'):
                    atoms.append(ord('.'))
                else:
                    atoms.append(member)
            # `-` is never escaped, so every `-` here can make a range.
            ranges = []
            j = 0
            while j < len(atoms):
                if j + 2 < len(atoms) and atoms[j + 1] == ord('-'):
                    if atoms[j] > atoms[j + 2]:
                        return None
                    ranges.append((atoms[j], atoms[j + 2]))
                    j += 3
                else:
                    ranges.append((atoms[j], atoms[j]))
                    j += 1
            out.append(('is', ranges))
            i = end + 1
    return out


def matches(pattern, name):
    # `new RegExp(^<glob>$)` with `.+^${}()|\` escaped, `*` as `.*` and `?`
    # as `.`, tested against a name of rows.
    compiled = tokens(pattern)
    if compiled is None:
        raise ValueError('not a RegExp: ' + pattern)
    subject = units(name)
    at = [0]
    for kind, ranges in compiled:
        reached = []
        if kind == 'any':
            if at:
                reached = list(range(min(at), len(subject) + 1))
        else:
            for index in at:
                if index < len(subject) and (kind == 'one' or any(
                        low <= subject[index] <= high
                        for low, high in ranges)):
                    reached.append(index + 1)
        at = reached
    return len(subject) in at


def every_table(path):
    # Every table at once: a glob standing for every table of an Airtable
    # base or every collection of a MongoDB database, over names that can
    # be their rows, is the same read as a walk of the base and is refused
    # on the same terms. Mirage hands the glob over unexpanded, so its last
    # name is matched as a pattern: `*/*.json*` reaches `records.jsonl`,
    # `*/table.json` does not.
    if not path.startswith('/airtable/') and not path.startswith('/mongodb/'):
        return False
    glob = -1
    for index, char in enumerate(path):
        if char in '*?[':
            glob = index
            break
    if glob < 0:
        return False
    parent = path[:path.rfind('/', 0, glob)]
    table, *rest = path[len(parent) + 1:].split('/')
    if table != '*' or not walked(parent):
        return False
    last = rest[-1] if rest else '*'
    return any(matches(last, name) for name in ROWS)


def table(path):
    # A table whole: an Airtable table's or view's records, a MongoDB
    # collection's or view's documents, or a Notion data source's
    # `rows.jsonl`, which the MCP arm's query returns a hundred rows at a
    # time.
    return ((path.startswith('/airtable/') and path.endswith('.jsonl'))
            or (path.startswith('/mongodb/')
                and path.endswith('/documents.jsonl'))
            or (path.startswith('/notion/') and path.endswith('/rows.jsonl')))


def parsed(text):
    # `JSON.parse`, which refuses the NaN and Infinity Python reads, the only
    # capitals Python takes outside a string, and reads the lone surrogate
    # monty cannot hold: each surrogate escape is read as U+FFFD, a string
    # as given as the one JavaScript reads.
    out = []
    inside = False
    i = 0
    while i < len(text):
        char = text[i]
        if inside and char == '\\':
            if re.fullmatch(r'\\u[dD][89a-fA-F][0-9a-fA-F]{2}', text[i:i + 6]):
                out.append('\\' + 'ufffd')
                i += 6
            else:
                out.append(text[i:i + 2])
                i += 2
            continue
        if char == '"':
            inside = not inside
        elif not inside and char in 'NI':
            raise ValueError('not JSON')
        out.append(char)
        i += 1
    return json.loads(''.join(out))


def given(args, key):
    value = args.get(key)
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip(SPACE) != ''
    return not isinstance(value, (dict, list)) or len(value) > 0


def refused(ctx):
    command = ctx['command']
    argv = ctx.get('argv') or []
    paths = ctx['paths']

    def shallow(flag):
        if flag not in argv:
            return False
        at = argv.index(flag)
        return at + 1 < len(argv) and at_most_three(argv[at + 1])

    # A `find` that runs a command on what it finds prints what that prints.
    runs = any(word in ('-exec', '-execdir', '-ok', '-okdir') for word in argv)
    names = any(
        word in ('--files-with-matches', '--quiet',
                 '--silent') or re.fullmatch(r'-[A-Za-z]*[lq][A-Za-z]*', word)
        for word in argv)
    listed = command in ('grep', 'rg') and names
    little = ((command == 'find' and shallow('-maxdepth') and not runs)
              or (command == 'tree' and shallow('-L')) or listed)
    if ctx.get('walks') and not little and any(walked(p) for p in paths):
        return True
    # Listing or counting every table prints little and is let through, as
    # is a `grep` or `rg` that prints names; `head` and `tail` are not,
    # since `tail -n +1` prints every row.
    counts = command in ('ls', 'wc', 'du', 'stat', 'file')
    if not counts and not listed and any(every_table(p) for p in paths):
        return True
    if command == 'cat' and any(table(p) for p in paths):
        return True
    # `notion` is the MCP arm's own Notion tool, and this is the one place
    # the mirage arm's differs: a search with neither a query nor a filter
    # answers with every page in the workspace, and a database query with
    # neither a filter nor `filter_properties` with every property of up to
    # a hundred rows. Its one JSON object is `{}` when left out, as
    # `tool.mjs` reads it; one that does not parse is the tool's to refuse.
    if command == 'notion':
        try:
            args = parsed(argv[1] if len(argv) > 1 else '{}')
        except ValueError:
            return False
        # An array has a `filter` of its own, its prototype's, so it asks
        # for no everything.
        if not isinstance(args, dict):
            return False
        verb = argv[0] if argv else None
        if (verb == 'post-search' and not given(args, 'query')
                and not given(args, 'filter')):
            return True
        if (verb == 'post-database-query' and not given(args, 'filter')
                and not given(args, 'filter_properties')):
            return True
    return False


def held(ctx):
    # The line as `pre_execute` sees it, before anything in it runs. Mirage
    # refuses a whole line only here, and names the refusal by the line's
    # first word, so a line is refused whole, as Mirage refused one before,
    # only when that word is the command refused; a command refused after
    # it is `pre_command`'s, refused where it stands. Its words are judged
    # here only as typed: one the shell expands later (`TYPED`) is judged
    # when it runs, by `pre_command`. A line of one command is left to
    # `pre_command`, which judged it alone before too.
    if len(ctx['commands']) < 2:
        return False
    first = ctx['commands'][0]
    line = ctx['line'].strip(SPACE)
    word = line
    for index, char in enumerate(line):
        if char in SPACE:
            word = line[:index]
            break
    typed = not any(text != '{}' and char in TYPED
                    for text in first.get('argv') or [] for char in text)
    return word == first['command'] and typed and refused({**ctx, **first})


ctx = json.loads(os.environ['MIRAGE_POLICY_CTX'])
if held(ctx) if 'commands' in ctx else refused(ctx):
    print(json.dumps({'kind': 'deny'}))
