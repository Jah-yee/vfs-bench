import argparse
import asyncio
import os
import sys
import time
from contextlib import AsyncExitStack

from agents import (Agent, ModelSettings, OpenAIChatCompletionsModel,
                    RunConfig, Runner, set_tracing_disabled)
from agents.exceptions import AgentsException
from arms import build_arm, resolve_task
from claude import CLAUDE, claude_model
from context import Progress
from dotenv import load_dotenv
from dump import STAMP, dump_path, run_id, write_dump
from gemini import GEMINI, native_model
from grading import grade, seed
from openai import AsyncOpenAI
from openai.types.shared import Reasoning
from services import REPO_ROOT, holding, load_stack_env, workspaces_dir

sys.path.insert(0, str(REPO_ROOT / "server" / "fakes"))
sys.path.insert(0, str(REPO_ROOT / "task"))

import atlas  # noqa: E402
import dataset  # noqa: E402
import stack  # noqa: E402

DEEPSEEK_V41_FLASH = "deepseek/deepseek-v4.1-flash"


def upstream_tool_name(name: str, registered) -> str | None:
    """The one registered name a model's tool name means, or None.

    Copied from upstream's `_resolve_registered_tool_name`
    (utils/openai_agents_monkey_patch/custom_run_impl.py): an exact name,
    else the single registered name equal to it once `-` reads as `_`.
    """
    names = list(registered)
    if name in names:
        return name
    normalized = name.replace("-", "_")
    matches = [each for each in names if each.replace("-", "_") == normalized]
    return matches[0] if len(matches) == 1 else None


class UpstreamToolNames:
    """Upstream's tool-call name resolution, on a model's replies.

    Upstream's patched RunImpl renames each call to its registered name
    before looking the tool up; this does it to the response the runner is
    about to read. It goes before the model class it renames for.
    """

    async def get_response(self, *args, **kwargs):
        from openai.types.responses import ResponseFunctionToolCall

        response = await super().get_response(*args, **kwargs)
        names = [
            *(getattr(tool, "name", None) for tool in kwargs["tools"]),
            *(handoff.tool_name for handoff in kwargs["handoffs"]),
        ]
        output = []
        for item in response.output:
            if isinstance(item, ResponseFunctionToolCall):
                name = upstream_tool_name(item.name, filter(None, names))
                if name is not None and name != item.name:
                    item = item.model_copy(update={"name": name})
            output.append(item)
        response.output = output
        return response


class ContextTooLong(AgentsException):
    """Upstream's `ContextTooLongError`: the model refused its input as too
    long. An SDK exception, so the run's items and usage come with it."""


# What upstream reads as a request refused for its length: one of these
# phrases in the error, whatever its status, or in the message of the error
# body, or one of these codes there. Copied from
# `OpenAIChatCompletionsModelWithRetry.get_response`
# (utils/api_model/model_provider.py), the wrapper upstream builds for every
# provider but its stateful Responses one, which alone asks for a 400.
TOO_LONG = ('token count exceeds', 'exceeds the maximum', 'string too long',
            'too long', 'context_length_exceeded', 'maximum context length',
            'token limit exceeded', 'content too long', 'message too long',
            'prompt is too long', 'maximum number of tokens',
            'maximum prompt length is', 'request exceeded model token limit',
            'exceed max message tokens', "exceeds the model's context window",
            'is longer than')
TOO_LONG_CODES = ('string_above_max_length', 'context_length_exceeded',
                  'messages_too_long')


def too_long(error: Exception) -> bool:
    """Whether upstream reads a failed request as its context running out."""
    if any(phrase in str(error).lower() for phrase in TOO_LONG):
        return True
    try:
        body = error.response.json().get('error', {})
        message = body.get('message', '').lower()
        return (any(phrase in message for phrase in TOO_LONG)
                or body.get('code', '') in TOO_LONG_CODES)
    except Exception:
        return False


class UpstreamContextErrors:
    """Upstream's reading of a refused request, on a model's requests.

    Upstream's model wrapper raises a request refused for its length as
    ContextTooLongError, which its runner answers by clearing the context
    (`run_agents`). Any other error is left as it was.
    """

    async def get_response(self, *args, **kwargs):
        try:
            return await super().get_response(*args, **kwargs)
        except Exception as error:
            if too_long(error):
                raise ContextTooLong(str(error)) from error
            raise


class UpstreamModel(UpstreamContextErrors, UpstreamToolNames):
    """What upstream's model wrapper does around whichever model a run asks."""


class ChatCompletions(UpstreamModel, OpenAIChatCompletionsModel):
    """Chat Completions, as upstream asks every model."""


async def run_agents(agent, task: str, max_turns: int, progress):
    """Upstream's inner loop, `TaskAgent.run_interaction_loop`
    (utils/roles/task_agent.py), in its single-turn mode.

    A request the model refuses as too long clears the context, and the run
    starts again from the task and a summary of its recent turns. Every
    sequence draws on the one budget of turns, counted as upstream counts
    them, and a reset that would leave none ends the run.

    Args:
        agent (Agent): the agent.
        task (str): the task, the first user input.
        max_turns (int): the budget of turns.
        progress (Progress): the run's hooks and upstream context.

    Returns:
        RunResult: the last sequence's result.
    """
    query, used = task, 0
    while True:
        try:
            return await Runner.run(agent,
                                    query,
                                    max_turns=max_turns - used,
                                    context=progress.context,
                                    hooks=progress,
                                    run_config=run_config(
                                        progress.model_input, agent.name))
        except ContextTooLong as error:
            if progress.helpers is None:
                raise
            meta = progress.context['_context_meta']
            used += meta['turns_in_current_sequence'] or 1
            if used >= max_turns:
                raise
            query = progress.reset(task, error.run_data)


def run_config(model_input, agent_name: str) -> RunConfig:
    """The agents loop's run config, with upstream's answer to an unknown tool.

    Upstream's patched RunImpl gives the model `Tool X not found in agent Y`
    as that call's result and runs on; the SDK's default raises
    ModelBehaviorError and ends the run.
    """
    return RunConfig(call_model_input_filter=model_input,
                     tool_not_found_behavior="return_error_to_model",
                     tool_error_formatter=lambda args:
                     (f"Tool {args.tool_name} not found in agent {agent_name}"
                      if args.kind == "tool_not_found" else None))


def reasoning_request(model: str, effort: str) -> dict:
    """Translate the runner's effort label into provider request fields."""
    if effort == "default":
        return {}
    if model == DEEPSEEK_V41_FLASH:
        if effort == "none":
            return {"extra_body": {"thinking": {"type": "disabled"}}}
        # The router accepts DeepSeek's boundary names: `minimal` maps to
        # low thinking, medium through xhigh map to high, and max stays max.
        native_effort = ("minimal" if effort == "low" else
                         "max" if effort == "max" else "high")
        return {
            "reasoning_effort": native_effort,
            "extra_body": {
                "thinking": {
                    "type": "enabled"
                }
            },
        }
    if model.startswith(GEMINI) and effort in ("xhigh", "max"):
        # Gemini's thinking levels stop at `high`, and LiteLLM refuses a
        # name above it: an effort asked for as the model's most is its most.
        return {"reasoning_effort": "high"}
    return {"reasoning_effort": effort}


def atlas_effort(model: str, effort: str) -> dict:
    """The effort in Atlas's `extra_llm_params`, as `run_eval.py` sends it.

    As asked for, but for a Gemini model's: LiteLLM's adapter raises on a
    name above `high` (`Invalid reasoning effort: max`), so it is capped as
    the agents loop caps it, and an effort asked for as the model's most is
    its most.

    Args:
        model (str): the gateway's model id.
        effort (str): the runner's effort label.

    Returns:
        dict: `reasoning_effort`, or nothing for `default`.
    """
    if model.startswith(GEMINI):
        return reasoning_request(model, effort)
    return {} if effort == "default" else {"reasoning_effort": effort}


def parse_args() -> argparse.Namespace:
    """The command line.

    Returns:
        argparse.Namespace: the parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description='Run one task against one tool surface, and '
        'write down what it cost.')
    parser.add_argument(
        "task",
        nargs="?",
        help="the task to run, as <dataset>/<task>; its directory "
        "is task/<dataset>/<task>. Its fixtures are rebuilt first, "
        "and the evaluator runs after. A bare <task> is accepted "
        "while it is unambiguous.")
    parser.add_argument(
        "--task-dir",
        default=None,
        help="the task directory, if it is not task/<dataset>/<task>")
    parser.add_argument("--model", default="openai/gpt-5.6-luna")
    parser.add_argument("--base-url",
                        default=os.environ.get("TOOLATHLON_OPENAI_BASE_URL",
                                               "https://llm.onerouter.pro/v1"))
    parser.add_argument("--api-key-env", default="INFRON_API_KEY")
    parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help="turn cap; defaults to the one the dataset's own\n"
        "harness uses")
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="wall clock for the agent loop, seconds; defaults to "
        "the dataset runner budget. Both "
        "arms get the same one; the MCP arm is additionally "
        "bounded per call by each server's own upstream "
        "timeout")
    parser.add_argument(
        "--reasoning-effort",
        default="medium",
        choices=["default", "none", "low", "medium", "high", "xhigh", "max"],
        help="Reasoning effort (gpt-5.x has no temperature). "
        "'none' disables thinking; 'default' omits the "
        "parameter (provider default, ~medium)")
    parser.add_argument("--max-tokens",
                        type=int,
                        default=None,
                        help="completion cap; defaults to the dataset's "
                        "configured budget")
    parser.add_argument("--tools",
                        default="vfs",
                        choices=["vfs", "mcp", "gym"],
                        help="'vfs' = mirage arm (one `shell` tool over "
                        "the mounts); 'mcp' = the dataset's own MCP "
                        "surface; 'gym' = Toolathlon's, but with GYM's "
                        "PostgreSQL-backed sheets fork")
    parser.add_argument("--dump",
                        default=None,
                        help="Path for the JSON run dump (default: "
                        "dumps/<timestamp>_<tools>_<model>_<effort>_"
                        "<dataset>_<task>.json, at the repository root)")
    return parser.parse_args()


async def _main() -> int:
    args = parse_args()

    load_dotenv(REPO_ROOT / ".env.development")
    load_stack_env()
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        print(f"error: {args.api_key_env} not set", file=sys.stderr)
        return 2

    task_dir = resolve_task(args)
    # After `resolve_task`, which is what selects the dataset.
    if args.timeout is None:
        args.timeout = getattr(dataset, "TIMEOUT", 1800)
    if args.max_turns is None:
        args.max_turns = getattr(dataset, "MAX_TURNS", 60)
    # Whose harness drives the run is the dataset's upstream's to say, like
    # every other setting: Toolathlon's is the openai-agents runner, and
    # MCP-Atlas's is its own TypeScript service. Both arms get the same one.
    args.loop = getattr(dataset, "LOOP", "agents")
    if args.max_tokens is None:
        args.max_tokens = getattr(dataset, "MAX_TOKENS", 4096)
    args.parallel_tool_calls = getattr(dataset, "PARALLEL_TOOL_CALLS", False)
    with holding(draw_locks(task_dir)):
        return await _draw(args, task_dir, api_key)


def draw_locks(task_dir) -> list[str]:
    """Everything one draw of this task shares with others on the host.

    The task itself, since two draws of one task would seed the same
    tenant, mailbox and upstream files; the stack services it reaches; and
    whatever else its dataset says it holds -- fixed host ports, upstream's
    conflict groups.

    Args:
        task_dir (Path): the task directory.

    Returns:
        list[str]: lock names for `services.holding`.
    """
    extra = getattr(dataset, "holds", None)
    return [
        f"task-{dataset.NAME}-{task_dir.name}", *stack.locks(task_dir.name),
        *(extra(task_dir.name) if extra else [])
    ]


async def _draw(args, task_dir, api_key) -> int:
    """Run one draw once everything it shares is held.

    Args:
        args (argparse.Namespace): the command line, with the dataset's
            defaults filled in.
        task_dir (Path): the task directory.
        api_key (str): the model provider's key.

    Returns:
        int: 0 when the run completed and its grader passed.
    """
    task = (task_dir / "shared" / "task.md").read_text()
    shell_log: list = []
    # Read before the run rather than after it, because it names both the
    # dump and the workspace: a stamp minted at the end would date a
    # two-hour run by the hour it stopped, and put the two arms of one draw
    # hours apart in a listing that is sorted by exactly this field.
    #
    # Claimed rather than assumed free. The stamp has one-second resolution,
    # so two draws of one configuration started in the same second would
    # share a workspace, and each seed would empty the other's. Creating
    # the directory is the claim, because only one process can create it;
    # the loser takes the next second.
    while True:
        started = time.strftime(STAMP)
        run = run_id(args, task_dir, started)
        try:
            (workspaces_dir() / run).mkdir(parents=True)
            break
        except FileExistsError:
            time.sleep(1)
    dump_file = dump_path(args, task_dir, started)

    # Where this run writes, decided here and published so that everything
    # downstream inherits it rather than working it out: the seeder fills
    # it, the arm writes in it, the MCP servers get it as their cwd, and
    # the grader reads it. Named after the run, so the files an arm left
    # behind are still there tomorrow beside the transcript that explains
    # them -- they used to be one directory per task, which meant the
    # second arm of a draw wiped the first arm's evidence on its way in.
    os.environ["AGENT_WORKSPACE"] = str(workspaces_dir() / run)

    # Before anything is built, and before the model is reached: both arms
    # run against the same live services one after the other, so a fixture
    # left as the previous arm finished with it is the previous arm's answer
    # sitting in front of this one. Unconditional, because a run that could
    # skip it is a run whose grade means nothing -- upstream's own runner
    # has no such switch either, and the one here existed only to save a
    # developer a minute.
    # Idempotent, and a no-op on a stack that is already healthy: running a
    # draw is the whole procedure, rather than failing with an instruction
    # the caller has to carry out by hand.
    #
    # Unconditional for a dataset whose fixtures are live services, which is
    # the reason the paragraph above gives. A dataset whose fixture is a
    # committed tree has nothing in the stack to reset, and starting Docker
    # for it would make a task that needs no service fail on a machine that
    # has none -- so the dataset says which it is.
    # A dataset may make the answer depend on the task rather than on
    # itself, and GYM's does: 151 of its 503 tasks want Snowflake and 258
    # want mail, while the one ported here wants four servers that never
    # leave the run's own workspace.
    decide = getattr(dataset, "needs_stack", None)
    if decide(task_dir.name) if decide else getattr(dataset, "NEEDS_STACK",
                                                    True):
        stack.up(stack.used(task_dir.name))

    seeded = await asyncio.to_thread(seed, task_dir)
    if seeded != 0:
        return seeded
    # The seed may have started the emulator and changed which project the
    # arm's tools should talk to, so this process's copy is stale. Nothing
    # here reads the launch time: `grade` takes it from the seed's own
    # record, which is the only thing that knows it.
    load_stack_env(override=True)
    record_source = getattr(dataset, "run_provenance", None)

    set_tracing_disabled(True)
    client = AsyncOpenAI(base_url=args.base_url, api_key=api_key)
    reasoning = reasoning_request(args.model, args.reasoning_effort)
    extra_args = {
        key: value
        for key, value in reasoning.items() if key != "extra_body"
    }
    effort = None
    # Only the agents loop is asked through this model; the other brings
    # its own.
    if args.model.startswith(GEMINI) and args.loop == "agents":
        model, extra_args["client"] = native_model(args.model, args.base_url,
                                                   api_key, client.timeout,
                                                   UpstreamModel)
    elif args.model.startswith(CLAUDE) and args.loop == "agents":
        model, extra_args["client"] = claude_model(args.model, args.base_url,
                                                   api_key, client.timeout,
                                                   UpstreamModel)
        # The SDK hands a Claude model its signed thinking back, as
        # upstream's converter does, only for an effort in the settings' own
        # field. A request gets what the OpenAI client gives one on every
        # other route: ten minutes, and two more attempts after a failure.
        if "reasoning_effort" in extra_args:
            effort = Reasoning(effort=extra_args.pop("reasoning_effort"))
        extra_args.update(timeout=client.timeout.read,
                          num_retries=client.max_retries)
    else:
        model = ChatCompletions(model=args.model, openai_client=client)
    model_settings = ModelSettings(
        max_tokens=args.max_tokens,
        # The dataset's, not this file's: upstream's harness decides
        # whether the model may batch tool calls, and the two benchmarks
        # here differ. None omits the field entirely, which is what
        # upstream sends a Gemini model (`_get_model_specific_config`).
        parallel_tool_calls=(None if args.model.startswith(GEMINI) else
                             args.parallel_tool_calls),
        reasoning=effort,
        extra_body=reasoning.get("extra_body"),
        extra_args=extra_args,
    )

    print(f"model={args.model} base_url={args.base_url} "
          f"task={task_dir.name} tools={args.tools}")

    # Toolathlon's local tools read their state out of the run context.
    run_context: dict = {}

    async with AsyncExitStack() as exits:
        if "client" in extra_args:
            exits.push_async_callback(extra_args["client"].client.aclose)
        arm = await build_arm(args, task_dir, exits, shell_log, run_context)
        close_commands = getattr(dataset, "close_commands", None)
        if close_commands:
            exits.callback(close_commands, task_dir.name)
        provenance = record_source(task_dir.name) if record_source else {}

        # Atlas's harness is upstream's own, so its request is too:
        # `run_eval.py`'s, with the effort in `extra_llm_params`. It does not
        # replay DeepSeek reasoning content.
        effort = atlas_effort(args.model, args.reasoning_effort)
        drawn = None
        if args.loop == "atlas":
            url, enabled = await atlas.serve(arm, task_dir.name, exits)
            print(f"loop=atlas tools={len(enabled)}")
            drawn = await atlas.run(
                client,
                args.model,
                ([{
                    "role": "system",
                    "content": arm["instructions"]
                }] if arm["instructions"] else []) + [{
                    "role": "user",
                    "content": task
                }],
                enabled,
                url,
                task_id=dataset.declaration(task_dir.name)["task"],
                extra=effort,
                max_turns=args.max_turns,
                timeout=args.timeout,
                logs=dataset.logs())

        if drawn is not None:
            status = drawn["status"]
            final_output = drawn["final_output"]
            usage = drawn["usage"]
            items = drawn["items"]
            print("\n--- final output ---")
            print(final_output)
            print(f"\n--- usage: requests={usage.requests} "
                  f"in={usage.input_tokens} out={usage.output_tokens} ---")
            print(f"--- shell commands executed: {len(shell_log)} ---")
            write_dump(dump_file,
                       args,
                       task_dir,
                       status,
                       final_output,
                       usage,
                       shell_log,
                       items,
                       provenance=provenance,
                       started=started,
                       tool_calls=drawn["tool_calls"])
            print(f"dump written to {dump_file}")
            graded = await asyncio.to_thread(grade, task_dir, dump_file)
            return 0 if status == "completed" and graded == 0 else 1

        agent = Agent(
            name=arm["name"],
            model=model,
            instructions=arm["instructions"],
            tools=arm["tools"],
            model_settings=model_settings,
            **({
                "mcp_servers": arm["servers"]
            } if arm.get("servers") else {}),
        )

        progress = Progress(
            run_context,
            root=dataset.root() if dataset.NAME == "toolathlon" else None,
            history_dir=dump_file.parent / "history" / run,
            session_id=run,
            task=task)
        try:
            # Both arms use the same upstream profile's wall-clock budget.
            result = await asyncio.wait_for(run_agents(agent, task,
                                                       args.max_turns,
                                                       progress),
                                            timeout=args.timeout)
            status, final_output = "completed", result.final_output
            items, usage = progress.whole(result.new_items,
                                          result.context_wrapper.usage)
        except AgentsException as exc:
            # A run that blows the turn cap is exactly the run worth reading,
            # so salvage the transcript rather than losing it to a traceback.
            if exc.run_data is None:
                raise
            status = type(exc).__name__
            final_output = f"<{status}: {exc}>"
            items, usage = progress.whole(exc.run_data.new_items,
                                          exc.run_data.context_wrapper.usage)
        except TimeoutError:
            status = "WallClockExceeded"
            final_output = f"<{status}: {args.timeout}s>"
            items, usage = progress.items, progress.usage
            # Close native MCP processes before the grader observes state.
            # Service fixtures remain alive through grading.
            for server in reversed(arm.get("servers") or []):
                await server.cleanup()
        finally:
            progress.finish_turn()

        print("\n--- final output ---")
        print(final_output)
        print(f"\n--- usage: requests={usage.requests} "
              f"in={usage.input_tokens} out={usage.output_tokens} ---")
        print(f"--- shell commands executed: {len(shell_log)} ---")

        write_dump(dump_file,
                   args,
                   task_dir,
                   status,
                   final_output,
                   usage,
                   shell_log,
                   items,
                   provenance=provenance,
                   started=started)
        print(f"dump written to {dump_file}")

        # Upstream grades inside its task container, as root; this grader
        # reads the workspace from the host.
        from server.execution import hand_back
        hand_back()
        graded = await asyncio.to_thread(grade, task_dir, dump_file)
        return 0 if status == "completed" and graded == 0 else 1


async def main() -> int:
    """Run one complete draw while what it shares with others is held."""
    return await _main()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
