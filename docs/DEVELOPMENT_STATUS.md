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
- Eleven unit tests and Spring Modulith architecture verification.
- Project-local VM deployment guide and Docker Compose definition.
- Offline executable-JAR deployment path for periods when Docker Hub is unreachable.
- Isolated `mineguard` MySQL database/account and protected runtime environment created in the VM.
- User-level service deployed with linger enabled; aggregate health is `UP` on port `18080` from both VM and Windows host.

Next:

- Start and smoke-test Kafka only when integration work begins.
- Add JPA persistence and Kafka detection-event consumer.
- Replace the in-memory tracker with a Redis implementation.
- Add a replay producer and the first Testcontainers integration test.

Environment facts:

- Main VM: `E:\vmware17.5.2\ubuntu.vmx`
- SSH alias: `ubuntu-vm`
- Guest address: `192.168.1.110`
- Shared MySQL and Redis: running in `~/industrial-lab`
- Native Kafka: installed in `~/dev-middleware`, currently on-demand
- Project port reserved for first deployment: `18080`
