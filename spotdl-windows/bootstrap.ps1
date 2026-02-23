# spotDL Bootstrap Script
# Downloads Python 3.13 embeddable + pip + spotdl wheel + ffmpeg
# Everything installs to .runtime\ next to this script — no system changes.

param(
    [string]$BaseDir
)

# If no BaseDir passed, use script's own location
if (-not $BaseDir -or $BaseDir -eq "") {
    $BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}

# Normalize: remove trailing backslash, resolve to absolute
$BaseDir = (Resolve-Path -LiteralPath $BaseDir).Path.TrimEnd('\')

$ErrorActionPreference = "Stop"

$runtimeDir = Join-Path $BaseDir ".runtime"
$pythonDir  = Join-Path $runtimeDir "python"
$pythonExe  = Join-Path $pythonDir "python.exe"

$pythonVersion = "3.13.2"
$pythonUrl     = "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-embed-amd64.zip"
$getPipUrl     = "https://bootstrap.pypa.io/get-pip.py"

# ── Download helper ───────────────────────────────────────────────────
function Download-File {
    param([string]$Url, [string]$Dest)
    $ProgressPreference = 'SilentlyContinue'  # 10x faster downloads
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
    } catch {
        Write-Host "  DOWNLOAD FAILED: $Url"
        Write-Host "  Error: $_"
        Write-Host ""
        Write-Host "  Check your internet connection and try again."
        exit 1
    }
    $ProgressPreference = 'Continue'
}

# ── Safe runner (quotes paths with spaces) ────────────────────────────
function Run-Python {
    param([string[]]$Arguments)
    # Quote any arguments containing spaces so Start-Process doesn't split them
    $quotedArgs = @()
    foreach ($arg in $Arguments) {
        if ($arg -match '\s') {
            $quotedArgs += "`"$arg`""
        } else {
            $quotedArgs += $arg
        }
    }
    $outFile = Join-Path $runtimeDir "stdout.tmp"
    $errFile = Join-Path $runtimeDir "stderr.tmp"
    $proc = Start-Process -FilePath $pythonExe -ArgumentList $quotedArgs `
        -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $outFile `
        -RedirectStandardError  $errFile
    $stdout = ""
    $stderr = ""
    if (Test-Path $outFile) { $stdout = Get-Content $outFile -Raw; Remove-Item $outFile -Force -ErrorAction SilentlyContinue }
    if (Test-Path $errFile) { $stderr = Get-Content $errFile -Raw; Remove-Item $errFile -Force -ErrorAction SilentlyContinue }
    return @{ ExitCode = $proc.ExitCode; Stdout = $stdout; Stderr = $stderr }
}

# ── Main ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "======================================================"
Write-Host "  spotDL - First Time Setup"
Write-Host "======================================================"
Write-Host ""
Write-Host "  Install path: $BaseDir"
Write-Host ""

# Warn about long/special paths
if ($BaseDir.Length -gt 200) {
    Write-Host "  WARNING: Path is very long. Move the folder closer"
    Write-Host "  to the root (e.g. C:\spotDL) if setup fails."
    Write-Host ""
}

# Create runtime directory
if (-not (Test-Path -LiteralPath $runtimeDir)) {
    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
}

# ── Step 1: Python ────────────────────────────────────────────────────
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $pythonZip = Join-Path $runtimeDir "python-embed.zip"

    Write-Host "  [1/4] Downloading Python $pythonVersion (~25MB)..."
    Download-File -Url $pythonUrl -Dest $pythonZip

    Write-Host "  [1/4] Extracting Python..."
    if (-not (Test-Path -LiteralPath $pythonDir)) {
        New-Item -ItemType Directory -Path $pythonDir -Force | Out-Null
    }

    try {
        Expand-Archive -LiteralPath $pythonZip -DestinationPath $pythonDir -Force
    } catch {
        Write-Host ""
        Write-Host "  EXTRACT FAILED. This usually means the folder path"
        Write-Host "  has special characters or is too long."
        Write-Host ""
        Write-Host "  Current path: $pythonDir"
        Write-Host ""
        Write-Host "  FIX: Move the spotDL folder to somewhere simple like:"
        Write-Host "       C:\spotDL"
        Write-Host "       or"
        Write-Host "       C:\Users\YourName\Desktop\spotDL"
        Write-Host ""
        Write-Host "  Error: $_"
        # Clean up partial download
        Remove-Item -LiteralPath $pythonZip -Force -ErrorAction SilentlyContinue
        exit 1
    }
    Remove-Item -LiteralPath $pythonZip -Force -ErrorAction SilentlyContinue

    # Enable site-packages by uncommenting 'import site' in the ._pth file
    # Without this, pip and package imports won't work
    $pthFiles = Get-ChildItem -LiteralPath $pythonDir -Filter "python*._pth"
    foreach ($pth in $pthFiles) {
        $lines = Get-Content -LiteralPath $pth.FullName
        $newLines = @()
        $hasSite = $false
        foreach ($line in $lines) {
            if ($line -match '^\s*#\s*import\s+site') {
                $newLines += "import site"
                $hasSite = $true
            } elseif ($line -match '^\s*import\s+site') {
                $newLines += $line
                $hasSite = $true
            } else {
                $newLines += $line
            }
        }
        if (-not $hasSite) {
            $newLines += "import site"
        }
        Set-Content -LiteralPath $pth.FullName $newLines
    }

    Write-Host "  [1/4] Python $pythonVersion ready."
} else {
    Write-Host "  [1/4] Python already installed."
}

# ── Step 2: pip ───────────────────────────────────────────────────────
$hasPip = $false
try {
    $r = Run-Python @("-m", "pip", "--version")
    if ($r.ExitCode -eq 0) { $hasPip = $true }
} catch {}

if (-not $hasPip) {
    $getPipFile = Join-Path $runtimeDir "get-pip.py"

    Write-Host "  [2/4] Installing pip..."
    Download-File -Url $getPipUrl -Dest $getPipFile

    $r = Run-Python @($getPipFile, "--no-warn-script-location")
    Remove-Item -LiteralPath $getPipFile -Force -ErrorAction SilentlyContinue

    if ($r.ExitCode -ne 0) {
        Write-Host "  [2/4] WARNING: pip install may have had issues."
        Write-Host "         $($r.Stderr)"
    } else {
        Write-Host "  [2/4] pip installed."
    }
} else {
    Write-Host "  [2/4] pip already installed."
}

# ── Step 3: spotDL wheel ─────────────────────────────────────────────
$hasSpotdl = $false
try {
    $r = Run-Python @("-m", "spotdl", "--version")
    if ($r.ExitCode -eq 0) { $hasSpotdl = $true }
} catch {}

if (-not $hasSpotdl) {
    $wheel = Get-ChildItem -LiteralPath $BaseDir -Filter "*.whl" | Select-Object -First 1
    if (-not $wheel) {
        Write-Host "  [3/4] ERROR: No .whl file found in $BaseDir"
        Write-Host "         Re-download the spotDL package."
        exit 1
    }

    Write-Host "  [3/4] Installing spotDL + dependencies (~30 packages)..."
    Write-Host "         This may take a minute..."

    $wheelPath = $wheel.FullName
    $r = Run-Python @("-m", "pip", "install", "--no-warn-script-location", $wheelPath)

    if ($r.ExitCode -ne 0) {
        Write-Host "  [3/4] WARNING: Installation may have had issues."
        # Show last 3 lines of stderr for context
        $errLines = ($r.Stderr -split "`n") | Where-Object { $_.Trim() -ne "" } | Select-Object -Last 3
        foreach ($line in $errLines) { Write-Host "         $line" }
    }

    # Verify
    try {
        $r = Run-Python @("-m", "spotdl", "--version")
        if ($r.ExitCode -eq 0) {
            Write-Host "  [3/4] spotDL installed! (version: $($r.Stdout.Trim()))"
        } else {
            Write-Host "  [3/4] WARNING: spotDL may not have installed correctly."
        }
    } catch {
        Write-Host "  [3/4] WARNING: Could not verify spotDL installation."
    }
} else {
    Write-Host "  [3/4] spotDL already installed."
}

# ── Step 4: FFmpeg ────────────────────────────────────────────────────
$hasFFmpeg = $false

# Check system PATH
try {
    $r = & ffmpeg -version 2>&1
    if ($LASTEXITCODE -eq 0) { $hasFFmpeg = $true }
} catch {}

# Check common spotdl ffmpeg locations
if (-not $hasFFmpeg) {
    $ffmpegLocations = @(
        (Join-Path $pythonDir "ffmpeg.exe"),
        (Join-Path $runtimeDir "ffmpeg.exe"),
        (Join-Path $BaseDir "ffmpeg.exe"),
        (Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "spotdl\ffmpeg.exe"),
        (Join-Path $env:USERPROFILE ".spotdl\ffmpeg.exe")
    )
    foreach ($loc in $ffmpegLocations) {
        if (Test-Path -LiteralPath $loc) {
            $hasFFmpeg = $true
            break
        }
    }
}

if (-not $hasFFmpeg) {
    Write-Host "  [4/4] Downloading FFmpeg..."
    try {
        $r = Run-Python @("-m", "spotdl", "--download-ffmpeg")
        if ($r.ExitCode -eq 0) {
            Write-Host "  [4/4] FFmpeg ready."
        } else {
            Write-Host "  [4/4] FFmpeg will download on first use."
        }
    } catch {
        Write-Host "  [4/4] FFmpeg will download on first use."
    }
} else {
    Write-Host "  [4/4] FFmpeg already available."
}

# ── Write tuned config ────────────────────────────────────────────────
$launcherPy = Join-Path $BaseDir "spotdl_launcher.py"
if (Test-Path -LiteralPath $launcherPy) {
    $r = Run-Python @($launcherPy, "--write-config")
}

# ── Done ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Setup complete! Starting spotDL..."
Write-Host ""
