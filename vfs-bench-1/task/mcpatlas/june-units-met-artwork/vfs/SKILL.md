---
name: workspace-commands
description: Use when running commands in this workspace - which commands exist, what they can do, and what the interpreter supports.
---

# Available commands

Python (`python` or `python3`), Perl, JavaScript/Node.js, and TypeScript
runtimes are unavailable. Use the shell commands and task CLIs documented
below; do not probe for or attempt to install other runtimes.

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq

with pipes, `>` redirection and `$(...)` substitution.

Do not probe the machine with `which`, `type`, `--version`, `env`, `ps`,
`echo $PATH`, `ls /usr/bin` or `cat /usr/bin/<command>`: they tell you
nothing about the task.

A filename with a space in it needs quoting, as it would in any shell.

You can also use `gh` for GitHub and `git`.

## airtable

Use `airtable <command> '<JSON arguments>'`. Run `airtable <command> --help`
to get more information.

```sh
airtable list-bases '{}'
airtable list-tables '{"base_id":"BASE_ID"}'
airtable search-records '{"base_id":"BASE_ID","table_name":"TABLE","field_name":"FIELD","value":"VALUE"}'
```

| Command | Arguments | Description |
|---|---|---|
| `airtable list-bases` | `{}` | List all accessible Airtable bases |
| `airtable list-tables` | `{base_id: str}` | List all tables in a base |
| `airtable search-records` | `{base_id: str, table_name: str, field_name: str, value: str}` | Search for records in a table |

## met-museum

Use `met-museum <command> '<JSON arguments>'`. Run
`met-museum <command> --help` to get more information.

```sh
met-museum list-departments '{}'
met-museum search-museum-objects '{"q":"QUERY","hasImages":true}'
met-museum get-museum-object '{"objectId":OBJECT_ID}'
```

| Command | Arguments | Description |
|---|---|---|
| `met-museum list-departments` | `{}` | List all departments in the Metropolitan Museum of Art (Met Museum) |
| `met-museum search-museum-objects` | `{q: str, hasImages?: bool = false, title?: bool = false, departmentId?: number}` | Search for objects in the Metropolitan Museum of Art (Met Museum). Will return Total objects found, followed by a list of Object Ids.The parameter title should be set to true if you want to search for objects by title.The parameter hasImages is false by default, but can be set to true to return objects without images.If the parameter hasImages is true, the parameter title should be false. |
| `met-museum get-museum-object` | `{objectId: number, returnImage?: bool = true}` | Get a museum object by its ID, from the Metropolitan Museum of Art Collection |
