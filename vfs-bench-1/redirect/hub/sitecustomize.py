# The model's own Python on the MCP arm, for a task that has the Hub. It
# reaches the Hub two ways, as upstream's does: through huggingface_hub, which
# HF_ENDPOINT already points at the fake, and through a bare `requests` call
# at a literal huggingface.co URL, which only `hf_host` moves; server/
# execution.py puts eval_shim/ beside this directory on PYTHONPATH. Without
# it that call reached the live Hub carrying the fake's tenant as its token
# and was refused, where upstream's real token is accepted
# (dataset-license-issue's MCP arm). An interpreter
# without `requests` makes no such call, so there is nothing to move.
try:
    import hf_host  # noqa: F401
except ImportError:
    pass
