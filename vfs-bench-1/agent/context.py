"""Adapt upstream's context lifecycle to the current Agents SDK hooks."""
import ast
import copy
import subprocess
from pathlib import Path

from agents import RunContextWrapper, RunHooks
from agents.items import (MessageOutputItem, ReasoningItem, ToolCallItem,
                          ToolCallOutputItem)
from agents.run_config import ModelInputData
from agents.usage import Usage

# What upstream tells the model when it clears a context the model refused
# as too long, from `TaskAgent.run_interaction_loop` (task_agent.py). Its
# Chinese text is for a `task_config.language` its TaskConfig never has.
RESET = ('[Context reset] The context length of the previous interaction '
         'exceeds the acceptable length of the model, and the context has '
         'been forcibly cleared. Below are the original task requirements '
         'and a summary of recent interactions. Please continue with the '
         'task, and use history search tools if you need complete details.')


def upstream_methods(root: Path, path: str, name: str, wanted: set,
                     imports: str):
    """Compile the named methods of one upstream class, and nothing else.

    Read from the pinned source, so no line of them is restated here.
    """
    source = subprocess.check_output(
        ['git', '-C', str(root), 'show', f'HEAD:{path}'], text=True)
    tree = ast.parse(source)
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == name)
    methods = [
        n for n in cls.body
        if isinstance(n, ast.FunctionDef) and n.name in wanted
    ]
    if {n.name for n in methods} != wanted:
        raise RuntimeError(f'Upstream {name} API changed')
    cls.bases, cls.keywords, cls.body = [], [], methods
    prelude = ast.parse(imports)
    prelude.body.append(cls)
    scope = {}
    exec(
        compile(ast.fix_missing_locations(prelude), f'Toolathlon/{path}',
                'exec'), scope)
    return scope[name]


def upstream_helpers(root: Path):
    """Load the unchanged helpers without importing upstream's retired SDK
    loop.

    The old module imports agents._run_impl, removed by the current SDK.
    Compile only its data/history helpers from the pinned source. No server,
    tool definition or truncation algorithm is reimplemented here.
    """
    return upstream_methods(
        root, 'utils/roles/context_managed_runner.py', 'ContextManagedRunner',
        {
            '_init_context_metadata', '_handle_truncation',
            '_truncate_sequential_lists', '_retain_sequential_turns',
            '_save_items_to_history', '_save_user_input_to_history',
            'get_recent_turns_summary', '_format_multiline_content'
        }, 'from __future__ import annotations\n'
        'from datetime import datetime\n'
        'from pathlib import Path\nimport json\n')


class Progress(RunHooks):
    """Keep completed usage/items even when a tool stalls or a run is
    cancelled."""

    def __init__(self,
                 context,
                 root=None,
                 history_dir=None,
                 session_id=None,
                 task=None):
        self.context = context
        self.items = []
        self.pending = []
        self.usage = Usage()
        self.sequence = []
        # How many of the SDK's input items the sequence already holds.
        self.taken = 0
        # What the sequences a context reset cleared left behind, which the
        # next sequence's own result does not carry.
        self.before = []
        self.before_usage = Usage()
        self.helpers = upstream_helpers(root) if root else None
        self.task_agent = upstream_methods(
            root, 'utils/roles/task_agent.py', 'TaskAgent',
            {'_reset_context_and_history'},
            'import datetime\n')() if root else None
        self.history_dir = history_dir
        self.session_id = session_id
        self.agent_name = 'agent'
        if self.helpers:
            self.helpers._init_context_metadata(context, session_id,
                                                history_dir)
            meta = context['_context_meta']
            # task_agent.py records the initial user input as the first turn.
            meta.update(current_turn=1,
                        total_turns_ever=1,
                        turns_in_current_sequence=1,
                        mini_turns_in_current_sequence=1,
                        boundary_in_current_sequence=[(0, 1)])
            self.helpers._save_user_input_to_history(session_id, task,
                                                     history_dir, 1)

    def finish_turn(self, inputs=None):
        """Save a completed batch before applying upstream's pending
        truncation."""
        if not self.helpers or not self.pending:
            return
        ctx = self.context
        meta = ctx['_context_meta']
        start = meta['mini_turns_in_current_sequence']
        # The SDK's input past what the sequence holds, not a count of the
        # hooks: it answers a call to an unknown tool without one, and a
        # count short by that answer cut the turn's first item instead.
        if inputs is not None:
            batch, self.taken = inputs[self.taken:], len(inputs)
        else:
            batch = [item.to_input_item() for item in self.pending]
        count = len(batch)
        self.sequence.extend(batch)
        meta['boundary_in_current_sequence'].append((start, start + count))
        meta['mini_turns_in_current_sequence'] += count
        self.helpers._save_items_to_history(self.session_id,
                                            meta['current_turn'], self.pending,
                                            self.agent_name, self.history_dir)
        self.pending = []
        if request := ctx.pop('_pending_truncate', None):
            self.helpers._handle_truncation(self.sequence, [], [], request,
                                            RunContextWrapper(context=ctx))

    def model_input(self, data):
        if not self.helpers:
            return data.model_data
        if not self.sequence:
            self.sequence = list(data.model_data.input)
            self.taken = len(self.sequence)
        self.finish_turn(data.model_data.input)
        meta = self.context['_context_meta']
        for key in ('current_turn', 'total_turns_ever',
                    'turns_in_current_sequence'):
            meta[key] += 1
        return ModelInputData(input=list(self.sequence),
                              instructions=data.model_data.instructions)

    def reset(self, task, run):
        """Clear a context the model refused as too long, as upstream does.

        The body of `TaskAgent.run_interaction_loop`'s ContextTooLongError
        handler (utils/roles/task_agent.py), less the turn budget its caller
        keeps: upstream's own `_reset_context_and_history` clears the
        context, and the next sequence starts from the task and a summary of
        the last ten turns of history.

        Args:
            task (str): the original task, upstream's first user input.
            run: the cleared sequence's `RunErrorDetails`.

        Returns:
            list: the next sequence's input.
        """
        self.before += run.new_items
        self.before_usage.add(run.context_wrapper.usage)
        self.task_agent.shared_context = self.context
        self.task_agent._debug_print = lambda *args: None
        self.task_agent._reset_context_and_history()
        self.context = self.task_agent.shared_context
        summary = self.helpers.get_recent_turns_summary(self.history_dir,
                                                        self.session_id,
                                                        num_turns=10)
        query = (f'{RESET}\n\n=== Original User Task ===\n{task}\n\n'
                 f'{summary}')
        meta = self.context['_context_meta']
        meta.update(turns_in_current_sequence=1,
                    mini_turns_in_current_sequence=1,
                    boundary_in_current_sequence=[(0, 1)])
        meta['total_turns_ever'] += 1
        self.helpers._save_user_input_to_history(self.session_id, query,
                                                 self.history_dir,
                                                 meta['current_turn'])
        message = {'role': 'user', 'content': query}
        self.before.append(message)
        self.items.append(message)
        self.sequence = []
        return [message]

    def whole(self, items, usage):
        """A sequence's items and usage, after the cleared sequences'."""
        total = copy.deepcopy(self.before_usage)
        total.add(usage)
        return [*self.before, *items], total

    async def on_llm_end(self, context, agent, response):
        # The whole run's usage, where upstream's context counts only the
        # current sequence's.
        self.usage = copy.deepcopy(self.before_usage)
        self.usage.add(context.usage)
        self.agent_name = agent.name
        self.context['_last_response_usage'] = {
            key: getattr(response.usage, key)
            for key in ('total_tokens', 'input_tokens', 'output_tokens',
                        'requests')
        }
        self.context['_cumulative_usage'] = {
            key: getattr(context.usage, key)
            for key in ('total_tokens', 'input_tokens', 'output_tokens',
                        'requests')
        }
        kinds = {
            'message': MessageOutputItem,
            'reasoning': ReasoningItem,
            'function_call': ToolCallItem
        }
        for raw in response.output:
            item = kinds[raw.type](agent=agent, raw_item=raw)
            self.items.append(item)
            self.pending.append(item)

    async def on_tool_end(self, context, agent, tool, result):
        call_id = getattr(context, 'tool_call_id', None)
        if call_id is None:
            return
        item = ToolCallOutputItem(
            agent=agent,
            output=result,
            raw_item={
                'type': 'function_call_output',
                'call_id': call_id,
                'output': result if isinstance(result, str) else str(result)
            })
        self.items.append(item)
        self.pending.append(item)
