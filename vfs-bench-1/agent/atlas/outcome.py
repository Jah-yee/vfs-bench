import json

from atlas.constants import COMPLETED, LIMITS, MODEL_ERROR


def status_of(outputs: list) -> tuple[str, str]:
    """How the harness says a run ended, and what its error said.

    Args:
        outputs (list): the harness's answer, `{type, data}` per item.

    Returns:
        tuple[str, str]: the status, and the error's own words, if any.
    """
    status, detail = COMPLETED, ""
    for output in outputs:
        if output["type"] != "error":
            continue
        error = output["data"]
        reason = error.get("reason")
        if reason in LIMITS:
            status = LIMITS[reason]
            continue
        refused = (error.get("serverResponse") or {}).get("error") or {}
        status = refused.get("type") or MODEL_ERROR
        detail = refused.get("message") or error.get("message", "")
    return status, detail


def drawn(status: str, detail: str, items: list, usage, calls: list) -> dict:
    """One run's outcome, in the form the dump is written from.

    The response is the last assistant message with text, as `run_eval.py`
    reads it; a run that ended with none says why instead.

    Args:
        status (str): `COMPLETED`, or what ended the run.
        detail (str): what the error said, if one did.
        items (list): the transcript.
        usage: what the run's requests cost.
        calls (list): the relay's calls, in order.

    Returns:
        dict: `status`, `final_output`, `usage`, `items`, `tool_calls`.
    """
    final = next(
        (message["content"]
         for message in reversed(items) if message.get("role") == "assistant"
         and isinstance(message.get("content"), str) and message["content"]),
        "")
    if status != COMPLETED and not final:
        final = f"<{status}: {detail}>" if detail else f"<{status}>"
    return {
        "status": status,
        "final_output": final,
        "usage": usage,
        "items": items,
        "tool_calls": timed(items, calls),
    }


def timed(items: list, calls: list) -> list[dict]:
    """Each tool call's duration, by call id, as the relay saw it.

    The harness makes the calls one at a time in the order the model asked
    for them, and skips one whose arguments do not parse, so the relay's
    calls pair with the transcript's in order.

    A call whose result the transcript lacks -- the run was cut off after
    the app answered and before the harness asked the model again -- also
    carries the app's answer, as the app gave it, since there is nowhere
    else a reader could find it.

    Args:
        items (list): the transcript.
        calls (list): the relay's calls, in order.

    Returns:
        list[dict]: `id`, `name` and `seconds` per call that reached the
            app, and `answer` where the transcript has no result for it.
    """
    answered = {
        message.get("tool_call_id")
        for message in items if message.get("role") == "tool"
    }
    pending = list(calls)
    found = []
    for message in items:
        for call in message.get("tool_calls") or []:
            name = call["function"]["name"]
            try:
                json.loads(call["function"]["arguments"])
            except ValueError:
                continue
            if pending and pending[0]["name"] == name:
                seen = pending.pop(0)
                found.append({
                    "id": call["id"],
                    "name": name,
                    "seconds": seen["seconds"],
                    **({
                        "answer": seen["answer"]
                    } if call["id"] not in answered and "answer" in seen else
                       {}),
                })
    return found
