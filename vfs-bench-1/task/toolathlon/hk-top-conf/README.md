# hk-top-conf

Original Toolathlon task at `9be8d8fe07a497b18ee61e3f2ae694e9797f39eb`.
The prompt, initial workspace and grader are unchanged. Both arms use the
original Serper handler and locked fetch/browser servers. The search, fetch and browser
CLIs preserve the original tool names and JSON arguments. Browser hosting
is local. Exact search/fetch requests share captured responses; new requests
and browser navigation use the live web.

Original tool schema/response parity and service startup were checked with
temporary integration probes. Source hashes are covered by DVC; no test
files were added.
