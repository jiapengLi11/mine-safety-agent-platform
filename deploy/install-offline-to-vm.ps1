param(
    [string]$VmAlias = "ubuntu-vm"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$jarPath = Join-Path $projectRoot "backend\target\mineguard-backend-0.1.0-SNAPSHOT.jar"
$servicePath = Join-Path $PSScriptRoot "systemd\mineguard-backend.service"
$bootstrapPath = Join-Path $PSScriptRoot "bootstrap-mineguard-db.sh"

if (-not (Test-Path -LiteralPath $jarPath)) {
    throw "Executable JAR not found. Run 'mvn clean verify' first."
}

ssh $VmAlias "mkdir -p ~/apps/mineguard ~/.config/systemd/user"
if ($LASTEXITCODE -ne 0) { throw "Unable to prepare VM directories." }

scp $jarPath "${VmAlias}:apps/mineguard/app.jar"
if ($LASTEXITCODE -ne 0) { throw "Unable to upload application JAR." }

scp $servicePath "${VmAlias}:.config/systemd/user/mineguard-backend.service"
if ($LASTEXITCODE -ne 0) { throw "Unable to upload systemd unit." }

scp $bootstrapPath "${VmAlias}:apps/mineguard/bootstrap-mineguard-db.sh"
if ($LASTEXITCODE -ne 0) { throw "Unable to upload database bootstrap script." }

ssh $VmAlias "chmod 700 ~/apps/mineguard/bootstrap-mineguard-db.sh && ~/apps/mineguard/bootstrap-mineguard-db.sh && loginctl enable-linger && systemctl --user daemon-reload && systemctl --user enable mineguard-backend && systemctl --user restart mineguard-backend"
if ($LASTEXITCODE -ne 0) { throw "MineGuard installation or startup failed." }

ssh $VmAlias "systemctl --user --no-pager --full status mineguard-backend | head -n 20"
