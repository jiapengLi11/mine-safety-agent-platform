# VMware development deployment

This project reuses the existing Ubuntu development VM and its shared middleware. The source of truth for machine recovery remains `C:\Users\22842\Desktop\priorFact`; this file records only the MineGuard-specific procedure.

## Verified environment

- VM configuration: `E:\vmware17.5.2\ubuntu.vmx`
- VM control script: `E:\vmware17.5.2\vm_control.ps1`
- SSH alias: `ubuntu-vm`
- Guest address: `192.168.1.110`
- Shared MySQL and Redis: `~/industrial-lab`
- Native Kafka: `~/dev-middleware/native-kafka.sh`
- MineGuard HTTP port: `18080`

Do not expose MySQL, Redis, or Kafka to the campus network. Only expose the application HTTP port when a teammate needs access.

## 1. Start and verify the VM

```powershell
powershell -ExecutionPolicy Bypass -File 'E:\vmware17.5.2\vm_control.ps1' -Action Start
ssh ubuntu-vm "hostname && free -h && df -h / && docker ps"
```

## 2. Start Kafka only when event integration is required

```powershell
ssh ubuntu-vm "cd ~/dev-middleware && ./native-kafka.sh start && ./native-kafka.sh smoke-test"
```

Kafka is intentionally on-demand because its configured heap is 512 MB to 1 GB.

## 3. Configure project secrets

Create `deploy/mineguard.local.env` from `deploy/mineguard.local.env.example` on the deployment machine. Never commit or paste the real password into logs or documentation.

The project must use its own MySQL database, MySQL account, Redis key prefix, Kafka topics, and consumer group. It must not reuse another project's logical namespace.

## 4. Build and run

Copy or clone the repository to the VM, then run from the repository root:

```bash
docker compose -f deploy/compose.vm.yml --env-file deploy/mineguard.local.env up -d --build
docker compose -f deploy/compose.vm.yml ps
curl -fsS http://127.0.0.1:18080/actuator/health
```

The backend uses host networking inside this development VM so it can reach the shared middleware on `127.0.0.1` without exposing additional ports.

### Offline fallback when Docker Hub is unavailable

The VM already contains a Java 21 runtime used by native Kafka. Build the executable JAR on Windows and install it as a user-level systemd service:

```powershell
Set-Location -LiteralPath 'E:\project11\mine-safety-agent-platform'
mvn clean verify
powershell -ExecutionPolicy Bypass -File .\deploy\install-offline-to-vm.ps1
```

The installer creates the isolated `mineguard` database and account, imports the existing Redis credential without printing it, writes a mode-600 environment file, uploads the JAR, enables user lingering, and starts `mineguard-backend.service`. It does not modify another project's schema or stop shared middleware.

Useful service commands:

```powershell
ssh ubuntu-vm "systemctl --user status mineguard-backend"
ssh ubuntu-vm "journalctl --user -u mineguard-backend -n 100 --no-pager"
ssh ubuntu-vm "systemctl --user restart mineguard-backend"
ssh ubuntu-vm "systemctl --user stop mineguard-backend"
```

## 5. Stop the project

```bash
docker compose -f deploy/compose.vm.yml down
```

For the offline deployment, stop only the MineGuard user service:

```powershell
ssh ubuntu-vm "systemctl --user stop mineguard-backend"
```

Stopping MineGuard must not stop the shared MySQL or Redis containers. Stop Kafka separately only when no other project is using it:

```powershell
ssh ubuntu-vm "cd ~/dev-middleware && ./native-kafka.sh stop"
```

## 6. Campus network access

For a temporary team demonstration, allow inbound TCP `18080` in Windows/VM networking as required and access `http://192.168.1.110:18080`. Do not open database or messaging ports. Campus addresses can change, so verify the current guest address before every demonstration.

## Verified deployment snapshot

On 2026-09-12, Docker Compose syntax validation passed, but Docker Hub name resolution timed out inside the VM. The offline JAR path was exercised end to end instead of merely documented. The application completed Flyway migration against MySQL 8.4.3, connected to authenticated Redis, remained active after the SSH session closed, and returned HTTP 200 with `status=UP` from both the VM and the Windows host.
