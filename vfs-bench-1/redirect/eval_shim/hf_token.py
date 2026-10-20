import os

# A Hugging Face evaluator reads its token out of Toolathlon's own
# `configs/token_key_session.py`, where it is the literal "XX" that upstream
# ships in place of a filled-in secret. On this fake the bearer IS the tenant,
# so grading with "XX" reads an empty Hub: the agent's repository comes back
# 404 and the run fails for a reason that is not the agent's.
#
# The library is patched rather than the config, which is what every other
# shim here does and is not merely a preference: `sitecustomize` runs before
# the evaluator's own package is importable, so `import configs` raises
# ModuleNotFoundError and the shim silently does nothing, and
# `huggingface-upload` is then graded against `XX/MyAwesomeModel-TestRepo`.
#
# `HF_ENDPOINT` needs no shim at all: huggingface_hub reads it itself.
_TOKEN = os.environ.get("HF_TOKEN", "")

if _TOKEN:
    from huggingface_hub import hf_api

    _original_headers = hf_api.HfApi._build_hf_headers
    _original_whoami = hf_api.HfApi.whoami

    def _headers(self, token=None, **kwargs):
        """Sign every request with the run's tenant, whatever was passed."""
        return _original_headers(self, token=_TOKEN, **kwargs)

    def _whoami(self, token=None):
        """`whoami` resolves its own token before the headers are built.

        It reads `token or self.token or get_token() or True` and hands the
        result on, so a caller passing "XX" never reaches the override above.
        The evaluator prepends this answer to the repo id it downloads, so
        getting it wrong sends it looking under the wrong namespace.
        """
        return _original_whoami(self, token=_TOKEN)

    hf_api.HfApi._build_hf_headers = _headers
    hf_api.HfApi.whoami = _whoami
