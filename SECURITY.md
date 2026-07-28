# Security policy

## Reporting a vulnerability

Report privately through GitHub's **[Report a vulnerability](https://github.com/EmmaLeonhart/Sutra/security/advisories/new)**
advisory form rather than opening a public issue.

Please include the `.su` source or input that triggers it, the backend, and what an attacker
gains. Expect an initial response within about a week; this is a research project maintained
by one person, not a funded product with an on-call rotation.

## Supported versions

Only the latest release (**1.1.0**) is supported. Sutra is **on hold** after 1.1.0, so fixes
are made on a best-effort basis and there is no backporting to earlier tags.

## Threat model — read this before reporting

Two properties are intentional and are **not** vulnerabilities:

**1. Compiling and running a `.su` file executes code.** `sutrac --run` and `sutrac --emit`
generate a self-contained Python module and, in the `--run` case, execute it. A `.su` file is
therefore executable input, exactly like a Python script or a Makefile. Do not compile or run
`.su` files from sources you would not run a Python script from. Reports that a crafted `.su`
can cause code execution via `--run` describe the documented behaviour of a compiler.

**2. The runtime downloads and caches a model.** The default substrate loads
`nomic-embed-text` in-process via `sentence-transformers`, and embeddings are cached to disk
keyed by model, dimension, and backend. First use fetches model weights over the network.

Things that **are** in scope:

- Path traversal or arbitrary file write from the embedding cache key, the compiler's output
  path handling, or the site build scripts.
- Code execution during *validation* (`sutrac file.su` with no `--run`), which is meant to
  parse and check without executing the program.
- Deserialization of untrusted data in the cache leading to execution when a `.su` file is only
  validated, not run.
- Dependency vulnerabilities reachable through normal use — though please check the advisory is
  not already known upstream in `torch` or `sentence-transformers` first.

## Dependency reports

Automated scanner output alone is usually not actionable. If you report a transitive CVE,
include the path by which Sutra reaches the affected code.
