---
name: workspace-commands
description: The shell commands and task tools available in this workspace.
---

# Available commands

Python (`python` or `python3`), Perl, JavaScript/Node.js, and TypeScript
runtimes are unavailable. Use the shell commands and task CLIs documented
below; do not probe for or attempt to install other runtimes.

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq  unzip

with pipes, `>` redirection, `$(...)` substitution and `$'...'`.

The task CLIs below are registered with this shell rather than installed
as files; do not inspect them with `which`, `file` or `/usr/bin`.

## gh

Use `gh --help` for the registered GitHub commands. Repository, issue, pull-request, release and API operations use the same GitHub service as upstream MCP. Use `gh <command> --help` for arguments and output options.

## memory

Use `memory <command> '<JSON arguments>'`. Run `memory <command> --help` to
get more information.

| Command | Arguments | Description |
|---|---|---|
| `memory create-entities` | `{entities: list[{name: str, entityType: str, observations: list[str]}]}` | Create multiple new entities in the knowledge graph — `entities.name`: The name of the entity; `entities.entityType`: The type of the entity; `entities.observations`: An array of observation contents associated with the entity |
| `memory create-relations` | `{relations: list[{from: str, to: str, relationType: str}]}` | Create multiple new relations between entities in the knowledge graph. Relations should be in active voice — `relations.from`: The name of the entity where the relation starts; `relations.to`: The name of the entity where the relation ends; `relations.relationType`: The type of the relation |
| `memory add-observations` | `{observations: list[{entityName: str, contents: list[str]}]}` | Add new observations to existing entities in the knowledge graph — `observations.entityName`: The name of the entity to add the observations to; `observations.contents`: An array of observation contents to add |
| `memory delete-entities` | `{entityNames: list[str]}` | Delete multiple entities and their associated relations from the knowledge graph — `entityNames`: An array of entity names to delete |
| `memory delete-observations` | `{deletions: list[{entityName: str, observations: list[str]}]}` | Delete specific observations from entities in the knowledge graph — `deletions.entityName`: The name of the entity containing the observations; `deletions.observations`: An array of observations to delete |
| `memory delete-relations` | `{relations: list[{from: str, to: str, relationType: str}]}` | Delete multiple relations from the knowledge graph — `relations`: An array of relations to delete; `relations.from`: The name of the entity where the relation starts; `relations.to`: The name of the entity where the relation ends; `relations.relationType`: The type of the relation |
| `memory read-graph` | `{}` | Read the entire knowledge graph |
| `memory search-nodes` | `{query: str}` | Search for nodes in the knowledge graph based on a query — `query`: The search query to match against entity names, types, and observation content |
| `memory open-nodes` | `{names: list[str]}` | Open specific nodes in the knowledge graph by their names — `names`: An array of entity names to retrieve |
