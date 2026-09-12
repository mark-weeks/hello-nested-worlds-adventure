# Voice and prompt-cache guidance

Read when changing voice quality, model selection, prompt bibles, or caching.

For flat voices, inspect which world-state the dynamic prompt omits before changing the
model. This is a diagnostic starting point, not a conclusion that model capability can
never be the bottleneck. Compare representative voices when evaluating a model change.

Confirm the configured model via `NESTED_WORLDS_MODEL` and `consciousness/__init__.py`.
When changing models or cache structure, verify the selected model's current cache
minimum against official documentation. The bibles deliberately exceed their required
prefix length: preserve `consciousness.cached_prefix_meets_minimum()` and the startup
`warn_if_cache_ineffective()` guard. Do not trim a bible below its effective threshold.
The historical 1024-versus-4096 cache failure explains this guard; it is not a universal
threshold for every future model.

Complete a voice/caching change with relevant prompt behavior tests and observed evidence
for the claimed improvement. Report any unavailable live-model verification; avoid claiming
a cache hit from the presence of `cache_control` alone.
