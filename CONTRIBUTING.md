# Contributing

MineGuard is developed incrementally. Each contribution should preserve a runnable path and keep implementation claims separate from roadmap statements.

## Before opening a change

1. Read `README.md`, `docs/DEVELOPMENT_STATUS.md`, and the relevant handbook section.
2. Keep module dependencies explicit; one module must not reach into another module's repository.
3. Add or update tests for domain behavior and failure paths.
4. Run `mvn clean verify` from the repository root.
5. Do not commit credentials, RTSP URLs, model weights, private images, datasets, generated build output, or local environment files.

## Commit style

Use a short imperative subject such as `feat: add detection event persistence` or `test: cover out-of-order frame handling`. Keep architecture and documentation changes in the same pull request when they explain the code being introduced.
