# Privacy desensitization

Scan every document in the workspace, replace each piece of sensitive
information with `/hidden/` in place, and write the copies to
`desensitized_documents/` as `<original>_desensitized.<ext>`. Five types only:
phone/fax numbers, SSNs, email addresses, credit card numbers, and IP addresses
including attached ports.

```bash
uv run python agent/run_agent.py toolathlon/privacy-desensitization --tools vfs
uv run python agent/run_agent.py toolathlon/privacy-desensitization --tools mcp
```
