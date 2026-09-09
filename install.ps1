<#
.SYNOPSIS
    math-modeling skill installer (Windows PowerShell).

.DESCRIPTION
    Installs the Python dependencies used by the validation toolchain, then
    runs the "doctor" health check. Run this script from the repository root
    after cloning.

.PARAMETER SkillsDir
    Optional. The agent skills directory to create a symlink in. If omitted,
    auto-detects $env:USERPROFILE\.claude\skills or $env:USERPROFILE\.config\opencode\skills.

.PARAMETER NoDoctor
    Skip the doctor health check.

.PARAMETER NoPip
    Skip pip install.

.EXAMPLE
    .\install.ps1
    .\install.ps1 -SkillsDir $env:USERPROFILE\.claude\skills
    .\install.ps1 -NoDoctor
#>

[CmdletBinding()]
param(
    [string]$SkillsDir = "",
    [switch]$NoDoctor,
    [switch]$NoPip
)

$ErrorActionPreference = "Stop"
$SkillName = "math-modeling"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# ANSI helpers (works in PowerShell 5.1+ when run in a modern terminal).
$Host.ui.RawUI.WindowTitle = "math-modeling skill installer"

function Write-Info  { param([string]$Msg) Write-Host "[INFO] $Msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$Msg) Write-Host "[ OK ] $Msg" -ForegroundColor Green }
function Write-Warn2 { param([string]$Msg) Write-Host "[WARN] $Msg" -ForegroundColor Yellow }
function Write-Err2  { param([string]$Msg) Write-Host "[ERR ] $Msg" -ForegroundColor Red }

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
Write-Host "================================" -ForegroundColor Cyan
Write-Host "  math-modeling skill installer"  -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# Preflight: detect git
# ---------------------------------------------------------------------------
$gitCmd = Get-Command git.exe -ErrorAction SilentlyContinue
if (-not $gitCmd) {
    Write-Err2 "git not found. Install Git for Windows from https://git-scm.com/download/win"
    exit 1
}
Write-Info "Found $(git --version 2>&1)"

# ---------------------------------------------------------------------------
# Preflight: detect Python (try python, python3, py launcher)
# ---------------------------------------------------------------------------
$pyExe = $null
foreach ($candidate in @("python", "python3", "py")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) {
        $pyExe = $candidate
        break
    }
}
if (-not $pyExe) {
    Write-Err2 "Python not found. Install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
}

# Verify the Python version is 3.10+
$pyVersionString = & $pyExe --version 2>&1
try {
    $pyVersion = & $pyExe -c "import sys, sysconfig, platform; print(platform.python_version())" 2>$null
    if (-not $pyVersion) { $pyVersion = $pyVersionString.ToString().Trim() }
    $majorMinor = & $pyExe -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null
    if (-not $majorMinor) {
        $majorMinor = ($pyVersion -replace '^(\d+\.\d+).*$', '$1')
    }
    $parts = $majorMinor -split '\.'
    $major = [int]$parts[0]
    $minor = [int]$parts[1]
    if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
        Write-Info "Found $pyVersionString"
    } else {
        Write-Err2 "Python 3.10+ required. Current: $pyVersionString"
        exit 1
    }
} catch {
    Write-Err2 "Could not determine Python version. Current output: $pyVersionString"
    exit 1
}

# ---------------------------------------------------------------------------
# Locate skill source directory
# ---------------------------------------------------------------------------
if (-not (Test-Path "$ScriptDir\SKILL.md")) {
    Write-Err2 "SKILL.md not found next to this script (expected at: $ScriptDir\SKILL.md)."
    exit 1
}
if (-not (Test-Path "$ScriptDir\requirements.txt")) {
    Write-Err2 "requirements.txt not found next to this script (expected at: $ScriptDir\requirements.txt)."
    exit 1
}
Write-Info "Skill source directory: $ScriptDir"

# ---------------------------------------------------------------------------
# Install Python dependencies
# ---------------------------------------------------------------------------
if ($NoPip) {
    Write-Warn2 "Skipping pip install (-NoPip)."
} else {
    Write-Info "Installing Python dependencies from requirements.txt ..."
    Push-Location $ScriptDir
    try {
        & $pyExe -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Err2 "pip install failed. See output above for details."
            Pop-Location
            exit 1
        }
        Write-Ok "Python dependencies installed."
    }
    catch {
        Write-Err2 "pip install failed with exception: $_"
        Pop-Location
        exit 1
    }
    finally {
        Pop-Location
    }
}

# ---------------------------------------------------------------------------
# Optional: deploy symlink into agent skills directory
# ---------------------------------------------------------------------------
$targetSkillsDir = $null
if ($SkillsDir -and $SkillsDir -ne "") {
    $targetSkillsDir = $SkillsDir
} elseif ($env:SKILLS_DIR -and $env:SKILLS_DIR -ne "") {
    $targetSkillsDir = $env:SKILLS_DIR
} else {
    # Auto-detect common agent skills directories on Windows.
    $candidates = @(
        (Join-Path $env:USERPROFILE ".claude\skills"),
        (Join-Path $env:USERPROFILE ".config\opencode\skills")
    )
    foreach ($c in $candidates) {
        if (Test-Path (Split-Path -Parent $c)) {
            $targetSkillsDir = $c
            break
        }
    }
}

if ($targetSkillsDir -and $targetSkillsDir -ne "") {
    $target = Join-Path $targetSkillsDir $SkillName
    $scriptDirFull = (Get-Item $ScriptDir).FullName

    if ((Test-Path $target) -and ((Get-Item $target).Target -or (Get-Item $target).FullName -eq $scriptDirFull)) {
        Write-Ok "Skill is already accessible from skills directory: $target"
    }
    elseif (Test-Path $target) {
        Write-Warn2 "Existing entry found at $target. Skipping symlink creation."
        Write-Warn2 "Remove it first if you want to (re)create the symlink."
    }
    else {
        Write-Info "Creating symlink: $target -> $scriptDirFull"
        try {
            New-Item -ItemType Directory -Path $targetSkillsDir -Force | Out-Null
            # Try symlink; if not elevated, fall back to junction
            try {
                New-Item -ItemType SymbolicLink -Path $target -Target $scriptDirFull -ErrorAction Stop | Out-Null
            }
            catch {
                # Fallback to Junction (works without admin rights on Windows).
                # Use the native PowerShell provider instead of shelling out to `cmd /c mklink`,
                # so a failure surfaces as a real terminating error rather than being
                # inferred indirectly from Test-Path.
                Write-Warn2 "Symlink needs admin rights; using junction instead."
                New-Item -ItemType Junction -Path $target -Target $scriptDirFull -ErrorAction Stop | Out-Null
            }
            Write-Ok "Link created. Your agent can now discover the skill at $target."
        }
        catch {
            Write-Warn2 "Link creation failed: $_"
            Write-Warn2 "You can manually copy this directory to your agent's skills directory."
        }
    }
} else {
    Write-Info "No agent skills directory detected."
    Write-Info "If your agent uses one, re-run:"
    Write-Info "    .\install.ps1 -SkillsDir <path-to-your-skills-dir>"
}

# ---------------------------------------------------------------------------
# Doctor health check
# ---------------------------------------------------------------------------
if ($NoDoctor) {
    Write-Warn2 "Skipping doctor health check (-NoDoctor)."
}
elseif (Test-Path "$ScriptDir\tools\doctor.py") {
    Write-Info "Running doctor health check..."
    Push-Location $ScriptDir
    try {
        & $pyExe tools\doctor.py --workspace .
        if ($LASTEXITCODE -ne 0) {
            Write-Warn2 "Doctor reported warnings/issues. See output above for details."
            Write-Warn2 "The skill may still work; doctor output is informational."
        } else {
            Write-Ok "Doctor check passed."
        }
    }
    catch {
        Write-Warn2 "Doctor check raised an exception: $_"
    }
    finally {
        Pop-Location
    }
} else {
    Write-Warn2 "Doctor script not found at $ScriptDir\tools\doctor.py; skipping."
}

# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------
Write-Ok "Installation complete!"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Restart your AI agent (Claude Code, OpenCode, or other) so it re-scans"
Write-Host "     the skills directory."
Write-Host "  2. Trigger the skill by asking your agent to help with a math modeling"
Write-Host "     problem (e.g. '帮我做一道数学建模题'), or by providing a problem"
Write-Host "     file (PDF / DOCX / Markdown / TXT) together with data attachments"
Write-Host "     (Excel / CSV)."
Write-Host ""
Write-Host "Skill location: $ScriptDir"