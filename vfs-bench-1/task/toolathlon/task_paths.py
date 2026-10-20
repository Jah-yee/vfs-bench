# What the mirage arm refuses to run: a command that reads or lists a path
# outside the task's mounts, and a walk of `/`. Upstream's terminal server
# runs with ALLOWED_DIR set to the agent workspace and refuses any path
# outside it, and its filesystem server serves only that directory; here the
# task's mounts stand in for that workspace, since each is this arm's copy of
# something the MCP arm reaches through a server. Only commands that read or
# list files are judged: `gh api /repos/...` names an endpoint and
# `python3 -c` a program, not a path. `/` and a directory that holds mounts
# (`/repo` over `/repo/main`) may be listed, and only `/` may not be walked,
# since only it holds anything besides the task's mounts. A path the shell
# has not expanded yet (`/repo/$b/tasks`) is judged by what comes before its
# first `$` or glob. The model reads why from `shell_output` in __init__.py,
# since a refusal prints only `<command>: Permission denied`.
import json
import os
import re

READERS = ('awk', 'base64', 'cat', 'cd', 'cmp', 'column', 'comm', 'cp', 'cut',
           'diff', 'du', 'egrep', 'fgrep', 'file', 'find', 'grep', 'head',
           'hexdump', 'iconv', 'jq', 'less', 'ls', 'md5sum', 'more', 'nl',
           'od', 'readlink', 'realpath', 'rg', 'sed', 'sha1sum', 'sha256sum',
           'sort', 'stat', 'strings', 'tac', 'tail', 'tar', 'tree', 'uniq',
           'wc', 'xxd', 'zip')
STREAMS = r'/dev/(null|stdin|stdout|stderr|fd/[0-9]+)'
# Mirage's own mounts, which `ctx['mounts']` lists beside the task's: the
# CLI wrappers, the session's shell history and the device files.
OWN = ('/usr/bin', '/.bash_history', '/dev')
# What JavaScript's `trim()` strips and `\s` matches: its white space and
# line terminators.
SPACE = ('\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006'
         '\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff')
# What a word still holds when `pre_execute` sees it before the shell has
# expanded it: a quote, a `$`, a backquote, a backslash, a `~` or a brace.
# `{}`, `find -exec`'s, is no brace.
TYPED = '\'"\\$`~{'


def refused(ctx):
    if ctx['command'] not in READERS:
        return False
    mounts = [
        mount for mount in (mount.rstrip('/') for mount in ctx['mounts'])
        if mount and mount not in OWN
    ]
    for path in ctx['paths']:
        if re.fullmatch(STREAMS, path):
            continue
        cut = -1
        for index, char in enumerate(path):
            if char in '$*?[':
                cut = index
                break
        at = path
        if cut >= 0:
            at = path[:cut]
            at = at[:at.rfind('/')] if '/' in at else at
            at = at or '/'
        if any(at == mount or at.startswith(mount + '/') for mount in mounts):
            continue
        holds = at == '/' or any(
            mount.startswith(at + '/') for mount in mounts)
        if holds and not (ctx.get('walks') and at == '/'):
            continue
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
