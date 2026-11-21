# Local AI runs on an external server, and Description search stays outside FilterSpec

Questions and Description search use a local language model and a local embedding model. The app reaches them
only over HTTP, through the OpenAI-compatible API of a server the user runs (Ollama, llama.cpp's `llama-server`,
LM Studio), configured in the `[ai]` section of `config.toml`. We do not load a model inside the Python process
(for example with `llama-cpp-python`), because that means compiling against the user's GPU stack (the target
machine has a Radeon RX 6600, which ROCm does not officially support) and an out-of-memory error would take the
app down with it. The model also becomes a configuration value rather than a dependency. The tool may start that server itself (with `[ai].command`, or
as a Docker container from `[ai.docker]`) and stops it again, but it is still a separate process spoken to over
HTTP.

Description search is a separate layer on top of the filter, not a `FilterSpec` criterion. A Question turns into
a plain `FilterSpec` plus an optional search text. `domain/filters.py` therefore stays deterministic and free of
any dependency on the embedding index or the server, and every existing use of `--filter` keeps behaving
exactly as before. The price is that Description search needs its own command-line option (`--search`) and
cannot be written into a filter JSON.
