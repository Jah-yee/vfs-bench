import json
from functools import lru_cache
from pathlib import Path

from mirage.accessor.base import NOOPAccessor
from mirage.commands.cli.types import CLI, CLIHandler
from mirage.commands.config import Context
from mirage.commands.errors import UsageError
from mirage.commands.spec import Argument, CommandSpec, FlagView
from mirage.io.stream import yield_bytes
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec
from pydantic import BaseModel

Result = tuple[ByteSource | None, IOResult]


class CookConfig(BaseModel):
    corpus: str


def out(payload: object) -> Result:
    """Render a verb result as the JSON document the MCP tool returns.

    Upstream is `JSON.stringify(x, null, 2)` in every tool, which indents
    two spaces and leaves non-ASCII alone. A recipe corpus is entirely
    non-ASCII, so `ensure_ascii` is the difference between the two arms
    reading the same document and one of them reading \\u-escapes.

    Args:
        payload (object): the JSON-serializable result.
    """
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return yield_bytes(body.encode()), IOResult()


@lru_cache(maxsize=None)
def load(path: str) -> tuple[dict, ...]:
    """Read the corpus once per process.

    Args:
        path (str): absolute path to the pinned all_recipes.json.

    Returns:
        tuple[dict, ...]: every recipe, in file order.
    """
    corpus = Path(path)
    if not corpus.is_file():
        raise UsageError(f"no recipe corpus at {corpus}; run "
                         f"`uv run python server/mcp/setup_howtocook.py`")
    return tuple(json.loads(corpus.read_text()))


def recipes(accessor: NOOPAccessor) -> tuple[dict, ...]:
    """The corpus this install reads.

    Args:
        accessor (NOOPAccessor): the install's accessor, carrying the CLI
            config.
    """
    return load(accessor.config.corpus)


def categories_of(corpus: tuple[dict, ...]) -> list[str]:
    """Every category name, in first-appearance order.

    Upstream builds this with a `Set` and returns `Array.from` it, so the
    order is the order the corpus introduces them rather than sorted.

    Args:
        corpus (tuple[dict, ...]): every recipe.
    """
    seen = {}
    for recipe in corpus:
        if recipe.get("category"):
            seen[recipe["category"]] = None
    return list(seen)


def simplify(recipe: dict) -> dict:
    """Cut a recipe down to what `simplifyRecipe` returns.

    Args:
        recipe (dict): one corpus entry.
    """
    return {
        "id":
        recipe["id"],
        "name":
        recipe["name"],
        "description":
        recipe["description"],
        "ingredients": [{
            "name": i["name"],
            "text_quantity": i["text_quantity"],
        } for i in recipe["ingredients"]],
    }


async def all_recipes(accessor: NOOPAccessor, paths: list[PathSpec],
                      texts: list[str], ctx: Context) -> Result:
    """Return every dish as a name and a description.

    Args:
        accessor (NOOPAccessor): the install's accessor.
        paths (list[PathSpec]): the path operands, none.
        texts (list[str]): the text operands, none.
        ctx (Context): the invocation.
    """
    return out([{
        "name": r["name"],
        "description": r["description"]
    } for r in recipes(accessor)])


async def categories(accessor: NOOPAccessor, paths: list[PathSpec],
                     texts: list[str], ctx: Context) -> Result:
    """Return the category names `recipes_by_category` accepts.

    Args:
        accessor (NOOPAccessor): the install's accessor.
        paths (list[PathSpec]): the path operands, none.
        texts (list[str]): the text operands, none.
        ctx (Context): the invocation.
    """
    return out(categories_of(recipes(accessor)))


async def recipes_by_category(accessor: NOOPAccessor, paths: list[PathSpec],
                              texts: list[str], ctx: Context) -> Result:
    """Return one category's dishes, with ingredients but without steps.

    Args:
        accessor (NOOPAccessor): the install's accessor.
        paths (list[PathSpec]): the path operands, none.
        texts (list[str]): the text operands, none.
        ctx (Context): the invocation.
    """
    corpus = recipes(accessor)
    want = FlagView(ctx.flags, ctx.spec).as_str("category")
    known = categories_of(corpus)
    # Upstream types this parameter as a `z.enum`, so the MCP client is
    # refused client-side rather than answered with an empty list. The CLI
    # has no schema to refuse from, so the check is here.
    if want not in known:
        raise UsageError("--category must be one of: " + ", ".join(known))
    return out([simplify(r) for r in corpus if r["category"] == want])


async def recipe(accessor: NOOPAccessor, paths: list[PathSpec],
                 texts: list[str], ctx: Context) -> Result:
    """Return one dish in full, or the near misses when nothing is exact.

    Upstream's cascade, kept in order: exact id, exact name, then a unique
    substring hit on the name. Only when all three miss does it fall back to
    listing up to five candidates matching on name *or* description, and
    that fallback is a different document -- an object, not a recipe -- so
    an agent has to read which one it got.

    Args:
        accessor (NOOPAccessor): the install's accessor.
        paths (list[PathSpec]): the path operands, none.
        texts (list[str]): the text operands, none.
        ctx (Context): the invocation.
    """
    corpus = recipes(accessor)
    query = FlagView(ctx.flags, ctx.spec).as_str("query")
    if not query:
        raise UsageError("--query is required")
    found = next((r for r in corpus if r["id"] == query), None)
    if found is None:
        found = next((r for r in corpus if r["name"] == query), None)
    if found is None:
        hits = [r for r in corpus if query.lower() in r["name"].lower()]
        if len(hits) == 1:
            found = hits[0]
    if found is not None:
        return out(found)

    possible = [
        r for r in corpus if query.lower() in r["name"].lower()
        or query.lower() in r["description"].lower()
    ][:5]
    if not possible:
        return out({
            "error": "未找到匹配的菜谱",
            "query": query,
            "suggestion": "请检查菜谱名称是否正确，或尝试使用关键词搜索",
        })
    return out({
        "message":
        "未找到精确匹配，以下是可能的匹配项：",
        "query":
        query,
        "possibleMatches": [{
            "id": r["id"],
            "name": r["name"],
            "description": r["description"],
            "category": r["category"],
        } for r in possible],
    })


COOK = CLI(
    spec=CommandSpec(
        name="cook",
        description="Look up Chinese home-cooking recipes",
        subcommands=(
            CommandSpec(
                name="all_recipes",
                description="Every dish, as a name and a description",
            ),
            CommandSpec(
                name="categories",
                description="Category names recipes_by_category accepts",
            ),
            CommandSpec(
                name="recipes_by_category",
                description="One category's dishes, with ingredients",
                arguments=(Argument("--category", required=True), ),
            ),
            CommandSpec(
                name="recipe",
                description="One dish in full, by name or id",
                arguments=(Argument("--query", required=True), ),
            ),
        ),
    ),
    handlers={
        "all_recipes": CLIHandler(fn=all_recipes),
        "categories": CLIHandler(fn=categories),
        "recipes_by_category": CLIHandler(fn=recipes_by_category),
        "recipe": CLIHandler(fn=recipe),
    },
    config_model=CookConfig,
)
