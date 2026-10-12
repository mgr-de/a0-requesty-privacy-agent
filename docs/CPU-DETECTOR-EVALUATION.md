# CPU PII evaluation integration

The optional `nym` detector is owned by the companion `a0-local-privacy-guard`, on branch `feat/cpu-pii-evaluation`. This manager keeps the existing detector configuration when applying the instance privacy floor; it still forces regex, NER, mapping and the required language union. No model route, preset, minimum policy, embedding behavior or default backend changes.

Prepare an immutable Nym model bundle and optional dependencies in a separate environment as described in the local guard's `docs/CPU-DETECTOR-EVALUATION.md`. Select it explicitly through `pii_filter.backend: nym` and `nym_model_dir` in the local guard configuration. DE/EN are the evaluated languages. There is no automatic model download or fallback during a call. An unavailable backend fails the existing preflight.

The new regression test verifies that the instance floor retains Nym configuration without relaxing required protection. Preflight's missing-model guidance now refers to the selected detector backend rather than prescribing spaCy for every backend. Routing and detector selection remain independent.

Run the native test suite in an isolated Agent Zero source checkout with copies of all three companion plugins. Tests use synthetic metadata and simulated transports. The local guard supplies the aggregate detector/component/native-payload benchmarks and a strictly local Ollama smoke test. No Requesty credential or paid request is required.
