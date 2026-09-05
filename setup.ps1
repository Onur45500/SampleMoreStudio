# Windows PowerShell setup for SampleMoreStudio
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> Creating Python venv"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

Write-Host "==> Generating task suites"
python scripts/cli.py generate-tasks

Write-Host "==> Installing frontend deps"
Set-Location frontend
npm install
Set-Location ..

Write-Host ""
Write-Host "Setup complete."
Write-Host "  Terminal 1: .\.venv\Scripts\Activate.ps1; uvicorn backend.main:app --reload --port 8000"
Write-Host "  Terminal 2: cd frontend; npm run dev"
Write-Host "  Phase 0:    .\.venv\Scripts\Activate.ps1; python scripts/cli.py phase0"
Write-Host "Ensure Ollama is running with: ollama pull qwen2.5:7b"
