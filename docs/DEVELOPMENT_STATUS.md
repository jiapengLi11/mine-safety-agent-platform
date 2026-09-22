# Development status

## Phase 1 baseline

Status: in progress

Completed:

- Product and architecture handbook.
- Environment verification against the local VMware runbooks.
- Spring Boot parent and backend module.
- Detection-frame domain contract.
- Detection-frame JSON Schema and example payload.
- Window hit-count rule with idempotency and cooldown.
- Alert state-transition aggregate.
- Flyway V1 schema for detection, alert, outbox, and audit records.
- One explicit Outbox implementation; Spring Modulith is used for module boundaries without enabling its second JPA event store.
- Twenty-two unit tests and Spring Modulith architecture verification.
- Project-local VM deployment guide and Docker Compose definition.
- Offline executable-JAR deployment path for periods when Docker Hub is unreachable.
- Isolated `mineguard` MySQL database/account and protected runtime environment created in the VM.
- User-level service deployed with linger enabled; aggregate health is `UP` on port `18080` from both VM and Windows host.
- Added a versioned Agent Golden format, deterministic domain metrics, Harness Evals 0.23.1 adapter, local-Qwen and OpenAI-compatible targets, release gates, negative tests, and JSON/Markdown/HTML reports.
- Ran a real RTX 3060/Qwen3-0.6B FP16 12-case seed benchmark. It failed the candidate gate on schema validity and unexpected tool calls; the failure is retained as evidence that model text quality does not grant execution authority.
- Ran a reproducible RTX 5090 BF16 matrix across Qwen3-1.7B, 4B, and 8B with three repeats each. Qwen3-8B was the only raw model to pass every candidate gate in all three runs; 1.7B exposed an unknown-citation hallucination and 4B exposed schema drift plus a missing approval tool.
- Implemented a Spring-managed deterministic Agent output gateway using the project-native Jackson 3 stack. It rejects malformed, oversized, duplicate-key, schema-drifted, rule-inconsistent, ungrounded, or unauthorized plans and fails closed to one human-review request.
- Added eleven focused gateway regression tests covering the concrete 5090 model failures and common authorization bypass attempts.

Next:

- Start and smoke-test Kafka only when integration work begins.
- Add JPA persistence and Kafka detection-event consumer.
- Replace the in-memory tracker with a Redis implementation.
- Add a replay producer and the first Testcontainers integration test.
- Connect the policy gateway to the future RAG/LLM orchestrator, persist raw outputs and violation codes, and keep tool authorization in a separate executor.

Environment facts:

- Main VM: `E:\vmware17.5.2\ubuntu.vmx`
- SSH alias: `ubuntu-vm`
- Guest address: `192.168.1.110`
- Shared MySQL and Redis: running in `~/industrial-lab`
- Native Kafka: installed in `~/dev-middleware`, currently on-demand
- Project port reserved for first deployment: `18080`
