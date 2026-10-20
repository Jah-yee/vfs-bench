"""Analyze saved agent dumps without executing their commands."""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ERRORS = {
    'awk_unsupported': r'awk: unsupported construct:',
    'curl_option_as_host': r'Failed to connect to -(?:sv|max-time)\b',
    'missing_file': r'No such file or directory',
    'python_traceback': r'Traceback \(most recent call last\):',
    'command_not_found': r'(?:command not found|: not found\b)',
}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def text(value):
    return value if isinstance(value, str) else json.dumps(value,
                                                           sort_keys=True)


def repeated(values):
    """Exact repeats are observations, not proof of unnecessary work."""
    seen = {}
    matches = []
    for index, value in values:
        if value in seen:
            matches.append({'index': index, 'first_index': seen[value]})
        else:
            seen[value] = index
    return matches


def analyze(path):
    raw = path.read_bytes()
    record = json.loads(raw)
    if not isinstance(record, dict) or not isinstance(record.get('items'),
                                                      list):
        raise ValueError(f'{path}: expected an agent dump with items')
    items = record['items']
    calls = []
    responses = Counter()
    unidentified = 0
    for index, item in enumerate(items):
        if item.get('type') != 'function_call':
            continue
        arguments = item.get('arguments', '')
        try:
            canonical = json.dumps(json.loads(arguments), sort_keys=True)
        except (ValueError, TypeError):
            canonical = text(arguments)
        response = item.get('provider_data', {}).get('response_id')
        if response:
            responses[response] += 1
        else:
            unidentified += 1
        calls.append((index, (item.get('name'), canonical)))
    batches = list(responses.values())
    outputs = []
    for index, item in enumerate(items):
        if item.get('type') == 'function_call_output':
            value = text(item.get('output', ''))
            outputs.append({
                'item_index': index,
                'bytes': len(value.encode()),
                'sha256': digest(value),
            })
    shell = record.get('shell_log')
    shell_metrics = None
    if isinstance(shell, list) and shell:
        evidence = []
        sizes = []
        raw_sizes = []
        commands = []
        for index, entry in enumerate(shell):
            command = entry.get('command', '')
            output = entry.get('model_output', entry.get('output', ''))
            output = text(output)
            commands.append((index, command))
            sizes.append(len(output.encode()))
            raw_sizes.append(len(text(entry.get('output', '')).encode()))
            markers = [
                name for name, pattern in ERRORS.items()
                if re.search(pattern, output)
            ]
            # A literal wildcard embedded in a printed path is only a lead:
            # commands may intentionally print patterns or fixture text.
            if re.search(r'/\*/[^\s]+|\*/\d{4}-\d{2}-\d{2}', output):
                markers.append('literal_glob_in_output_candidate')
            if markers:
                evidence.append({
                    'shell_index': index,
                    'markers': markers,
                    'command_excerpt': command[:400],
                })
        shell_metrics = {
            'calls':
            len(shell),
            'exact_command_repeats':
            repeated(commands),
            'recorded_output_bytes':
            sum(raw_sizes),
            'model_visible_output_bytes':
            sum(sizes),
            'largest_outputs': [{
                'shell_index': i,
                'bytes': sizes[i],
                'command_excerpt': commands[i][1][:400]
            } for i in sorted(
                range(len(sizes)), key=lambda i: sizes[i], reverse=True)[:5]],
            'diagnostic_candidates':
            evidence,
        }
    usage = record.get('usage', {})
    input_tokens = usage.get('input_tokens')
    output_tokens = usage.get('output_tokens')
    total = (input_tokens + output_tokens if isinstance(input_tokens, int)
             and isinstance(output_tokens, int) else None)
    provenance = record.get('provenance', {})
    return {
        'trace': str(path),
        'trace_sha256': hashlib.sha256(raw).hexdigest(),
        'task': Path(record.get('task_dir', '')).name,
        'model': record.get('model'),
        'arm': record.get('tools'),
        'settings': {
            k: record.get(k)
            for k in ('reasoning_effort', 'max_tokens', 'max_turns',
                      'parallel_tool_calls', 'loop')
        },
        'source_git': provenance.get('git'),
        'source_sha256': provenance.get('sha256'),
        'status': record.get('status'),
        # Preserve exit status: nonzero can be grader failure or exception.
        'evaluation': record.get('evaluation'),
        'usage': {
            k: v
            for k, v in usage.items() if k != 'per_request'
        },
        'total_tokens': total,
        'tool_calls': len(calls),
        'tool_names': dict(Counter(value[0] for _, value in calls)),
        'batching': {
            'identified_call_responses':
            len(batches),
            'calls_without_response_id':
            unidentified,
            'multi_call_responses':
            sum(n > 1 for n in batches),
            'largest_batch':
            max(batches, default=0),
            'calls_in_multi_call_responses':
            sum(n for n in batches if n > 1),
            'fraction_of_identified_calls_batched':
            (sum(n for n in batches if n > 1) /
             sum(batches) if batches else None),
            'actual_concurrency':
            None,
        },
        'exact_tool_call_repeats': repeated(calls),
        'tool_output': {
            'items':
            len(outputs),
            'serialized_bytes':
            sum(row['bytes'] for row in outputs),
            'largest_outputs':
            sorted(outputs, key=lambda x: x['bytes'], reverse=True)[:5],
            'exact_nonempty_repeats':
            repeated([(row['item_index'], row['sha256']) for row in outputs
                      if row['bytes'] > 0]),
        },
        'shell': shell_metrics,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('traces',
                        type=Path,
                        nargs='+',
                        help='Explicit saved agent dump JSON paths')
    args = parser.parse_args()
    report = {
        'analyzer_sha256':
        hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limitations': [
            'Offline analysis only; no commands are executed.',
            'Batching means calls sharing a recorded model response ID, '
            'not actual concurrent execution or known independence.',
            'Missing response IDs are reported, not inferred.',
            'Exact repeats are not necessarily redundant; state may change.',
            'Byte counts are UTF-8, not model tokens or backend bytes read.',
            'Tool outputs and shell outputs overlap; do not add them.',
            'Diagnostic text is a candidate for review, not a failure count.',
            'No semantic shell parsing, resource access tracing, timing, '
            'completion-point inference, or causal efficiency score.',
            'Requested effort labels do not establish equal native thinking.',
            'Check historical settings and revisions before comparing.',
        ],
        'runs': [analyze(path) for path in args.traces],
    }
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
