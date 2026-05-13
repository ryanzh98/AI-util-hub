# Voice Detection — one-shot installer + launcher.
# Idempotent: re-running it skips already-done steps and just launches.

$ErrorActionPreference = 'Continue'
$ProjectRoot = $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot

$EnvName     = 'voice-detection'
$PyVer       = '3.12'
$TorchIndex  = 'https://download.pytorch.org/whl/cu128'
$ModelUrl    = 'https://huggingface.co/sxndypz/rvc-v2-models/resolve/main/roca_act2.zip'
$env:PYTHONNOUSERSITE = '1'

function Write-Step([string]$msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "    $msg" -ForegroundColor Yellow }
function Die([string]$msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red; Read-Host "Press Enter to exit"; exit 1 }

Write-Host "=== Voice Detection — install + run ===" -ForegroundColor White
Write-Host "(Re-run this any time; already-done steps are skipped.)"

# ------------------------------------------------------------------
# 1. Find or auto-install Miniconda
# ------------------------------------------------------------------
Write-Step "[1/6] Locating conda"
$CondaRoot = $null

# Build a candidate list of common install locations for Anaconda/Miniconda
# across drives and folder layouts. Anaconda preferred (per user request).
$drives = @('C:', 'D:', 'E:', 'F:')
$subdirs = @(
    'anaconda3', 'Anaconda3',
    'miniconda3', 'Miniconda3',
    'ProgramData\anaconda3', 'ProgramData\Anaconda3',
    'ProgramData\miniconda3', 'ProgramData\Miniconda3',
    'Program Files\anaconda3', 'Program Files\Anaconda3',
    'Program Files\miniconda3', 'Program Files\Miniconda3',
    'Users\$env:USERNAME\anaconda3', 'Users\$env:USERNAME\Anaconda3',
    'Users\$env:USERNAME\miniconda3', 'Users\$env:USERNAME\Miniconda3'
)
$candidates = @()
# 1. User-profile locations.
$candidates += "$env:USERPROFILE\anaconda3"
$candidates += "$env:USERPROFILE\Anaconda3"
$candidates += "$env:USERPROFILE\miniconda3"
$candidates += "$env:USERPROFILE\Miniconda3"
$candidates += "$env:LOCALAPPDATA\anaconda3"
$candidates += "$env:LOCALAPPDATA\miniconda3"
# 2. Drive-root + Program Files variants (anaconda first per preference).
foreach ($d in $drives) {
    foreach ($s in $subdirs) {
        $candidates += "$d\$s"
    }
}
# 3. Registry-discovered installs (works for non-standard paths).
foreach ($hive in @('HKLM:', 'HKCU:')) {
    $regPath = "$hive\SOFTWARE\Python\ContinuumAnalytics"
    if (Test-Path $regPath) {
        Get-ChildItem $regPath -ErrorAction SilentlyContinue | ForEach-Object {
            $ip = (Get-ItemProperty "$($_.PSPath)\InstallPath" -ErrorAction SilentlyContinue).'(default)'
            if ($ip) { $candidates += $ip.TrimEnd('\') }
        }
    }
}
# 4. conda on PATH, if any.
$onPath = Get-Command conda.exe -ErrorAction SilentlyContinue
if ($onPath) {
    # conda.exe is usually in <root>\Scripts\ or <root>\condabin\
    $parent = Split-Path $onPath.Source -Parent
    if ($parent -match '\\(Scripts|condabin)$') {
        $candidates += (Split-Path $parent -Parent)
    } else {
        $candidates += $parent
    }
}

# De-duplicate (case-insensitive) and pick the first that has conda.exe.
$seen = @{}
foreach ($c in $candidates) {
    if ([string]::IsNullOrWhiteSpace($c)) { continue }
    $key = $c.ToLower()
    if ($seen.ContainsKey($key)) { continue }
    $seen[$key] = $true
    if (Test-Path "$c\Scripts\conda.exe") { $CondaRoot = $c; break }
}

if (-not $CondaRoot) {
    Write-Warn "No Anaconda/Miniconda found. Downloading Miniconda installer..."
    $installer = Join-Path $env:TEMP 'Miniconda3-installer.exe'
    try {
        Invoke-WebRequest -Uri 'https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe' -OutFile $installer -UseBasicParsing
    } catch {
        Die "Failed to download Miniconda installer: $_"
    }
    Write-Warn "Installing Miniconda silently to $env:USERPROFILE\miniconda3 (~5 min)..."
    $args = @('/InstallationType=JustMe', '/RegisterPython=0', '/AddToPath=0', '/S', "/D=$env:USERPROFILE\miniconda3")
    $p = Start-Process -FilePath $installer -ArgumentList $args -Wait -PassThru
    if ($p.ExitCode -ne 0) { Die "Miniconda installer exited with code $($p.ExitCode)" }
    Remove-Item $installer -Force -ErrorAction SilentlyContinue
    $CondaRoot = "$env:USERPROFILE\miniconda3"
}
Write-Ok "Conda at: $CondaRoot"

$Conda  = "$CondaRoot\Scripts\conda.exe"
$EnvDir = "$CondaRoot\envs\$EnvName"
$EnvPy  = "$EnvDir\python.exe"
$EnvPyW = "$EnvDir\pythonw.exe"

# ------------------------------------------------------------------
# 2. Create env if missing
# ------------------------------------------------------------------
Write-Step "[2/6] Ensuring conda env '$EnvName' (Python $PyVer)"
if (Test-Path $EnvPy) {
    Write-Ok "Env already exists."
} else {
    & $Conda create -n $EnvName "python=$PyVer" -y
    if ($LASTEXITCODE -ne 0) { Die "conda env create failed" }
    & $EnvPy -s -m pip install --no-user --upgrade pip --quiet
    Write-Ok "Env created."
}

# ------------------------------------------------------------------
# 3. PyTorch + CUDA 12.8 (skip if already installed in env)
# ------------------------------------------------------------------
Write-Step "[3/6] PyTorch (CUDA 12.8)"
$torchInstalled = Test-Path "$EnvDir\Lib\site-packages\torch\__init__.py"
if (-not $torchInstalled) {
    Write-Warn "Installing PyTorch — large download (~2 GB)..."
    & $EnvPy -s -m pip install --no-user torch torchaudio --index-url $TorchIndex
    if ($LASTEXITCODE -ne 0) { Die "PyTorch install failed (pip exit $LASTEXITCODE)" }
    Write-Ok "Installed."
} else {
    Write-Ok "Already installed."
}

# ------------------------------------------------------------------
# 4. Project requirements (skip if a marker package is present)
# ------------------------------------------------------------------
Write-Step "[4/6] Project requirements (PyQt6, faster-whisper, tts-with-rvc, etc.)"
# Check every package listed in requirements.txt by import-name. If ANY are
# missing (e.g. someone is upgrading from an older install_and_run that didn't
# include imageio-ffmpeg yet), rerun the full pip install.
$markers = @(
    'PyQt6', 'sounddevice', 'soundfile', 'pynput', 'openai', 'dotenv',
    'win32com', 'winshell', 'PIL', 'faster_whisper', 'ctranslate2',
    'yt_dlp', 'pycaw', 'fastapi', 'uvicorn', 'tts_with_rvc',
    'imageio_ffmpeg'
)
$missing = @()
foreach ($m in $markers) {
    $pkgDir = Join-Path $EnvDir ("Lib\site-packages\" + $m)
    $pkgPy  = Join-Path $EnvDir ("Lib\site-packages\" + $m + ".py")
    if (-not (Test-Path $pkgDir) -and -not (Test-Path $pkgPy)) {
        $missing += $m
    }
}
if ($missing.Count -gt 0) {
    Write-Warn "Missing packages: $($missing -join ', ')"
    & $EnvPy -s -m pip install --no-user -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        # Retry with --no-cache-dir in case pip's wheel cache is bad.
        Write-Warn "First install failed — retrying with --no-cache-dir..."
        & $EnvPy -s -m pip install --no-user --no-cache-dir -r requirements.txt
        if ($LASTEXITCODE -ne 0) { Die "requirements install failed (pip exit $LASTEXITCODE)" }
    }
    Write-Ok "Installed."
} else {
    Write-Ok "All packages present."
}

# Stdlib-DLL health check. Some stdlib modules (lzma, sqlite3, ssl) link
# against conda-provided DLLs in <env>\Library\bin\. When running python
# directly (no `conda activate`), that dir isn't on the DLL search path,
# so the imports fail even when the DLLs exist. We test the imports WITH
# add_dll_directory set so we get a true signal. If they still fail, we
# install the conda package that provides the missing DLL.
Write-Step "[4a/6] Verifying stdlib DLLs (lzma, sqlite, ssl)"
$libBin = "$EnvDir\Library\bin"

function Test-StdlibImport([string]$mod) {
    # Mimics what main.py does at startup so we test under realistic conditions.
    $code = "import os; os.add_dll_directory(r'$libBin'); import $mod"
    & $EnvPy -s -c $code 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

$stdlibBroken = @()
foreach ($m in @('lzma', 'sqlite3', 'ssl')) {
    if (-not (Test-StdlibImport $m)) { $stdlibBroken += $m }
}
if ($stdlibBroken.Count -gt 0) {
    Write-Warn "Missing stdlib DLLs for: $($stdlibBroken -join ', ')"
    Write-Warn "Installing conda packages from conda-forge..."
    $condaPkgs = @()
    if ('lzma' -in $stdlibBroken)    { $condaPkgs += 'xz' }
    if ('sqlite3' -in $stdlibBroken) { $condaPkgs += 'sqlite' }
    if ('ssl' -in $stdlibBroken)     { $condaPkgs += 'openssl', 'ca-certificates' }
    # Use conda-forge to dodge Anaconda's defaults-channel ToS prompt (added 2024).
    # --override-channels prevents falling back to defaults if -c conda-forge
    # alone isn't enough; -y auto-accepts.
    & $Conda install -n $EnvName -c conda-forge --override-channels @condaPkgs -y
    if ($LASTEXITCODE -ne 0) {
        # Fallback: try without override-channels in case conda-forge is unreachable.
        Write-Warn "conda-forge install failed; trying default channels..."
        & $Conda install -n $EnvName @condaPkgs -y
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "If you saw a Terms of Service error, run this once to accept:" -ForegroundColor Yellow
            Write-Host "  $Conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main" -ForegroundColor Gray
            Write-Host "  $Conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r" -ForegroundColor Gray
            Write-Host "  $Conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2" -ForegroundColor Gray
            Die "conda install of stdlib deps failed"
        }
    }
    foreach ($m in $stdlibBroken) {
        if (-not (Test-StdlibImport $m)) { Die "$m still broken after reinstall — re-create the env" }
    }
    Write-Ok "Stdlib restored."
} else {
    Write-Ok "All stdlib DLLs OK."
}

# Hard verification — tts-with-rvc has the heaviest dep chain (fairseq, faiss,
# torchcrepe) and pip can silently skip it if a sub-dep fails. Verify every
# critical package actually imports; reinstall any that don't.
Write-Step "[4b/6] Verifying critical imports"
$critical = @{
    'PyQt6.QtCore'    = 'PyQt6'
    'faster_whisper'  = 'faster-whisper'
    'tts_with_rvc'    = 'tts-with-rvc'
    'fastapi'         = 'fastapi'
    'pynput'          = 'pynput'
    'pycaw'           = 'pycaw'
    'imageio_ffmpeg'  = 'imageio-ffmpeg'
}

function Test-ImportClean([string]$module) {
    # Returns @{ok=$bool; err=$string}. Captures stderr so we can show the user.
    # Adds <env>\Library\bin to DLL search path first (matches main.py runtime).
    $errFile = [IO.Path]::GetTempFileName()
    try {
        $code = "import os; os.add_dll_directory(r'$libBin'); import $module"
        & $EnvPy -s -c $code 2>$errFile | Out-Null
        $exit = $LASTEXITCODE
        $err  = (Get-Content $errFile -Raw -ErrorAction SilentlyContinue) -as [string]
        if ($null -eq $err) { $err = '' }
        return @{ ok = ($exit -eq 0); err = $err.Trim() }
    } finally {
        Remove-Item $errFile -Force -ErrorAction SilentlyContinue
    }
}

$brokenMap = @{}
foreach ($mod in $critical.Keys) {
    $r = Test-ImportClean $mod
    if (-not $r.ok) { $brokenMap[$critical[$mod]] = @{ module = $mod; err = $r.err } }
}

if ($brokenMap.Count -gt 0) {
    Write-Warn "These packages did not import cleanly:"
    foreach ($pkg in $brokenMap.Keys) {
        Write-Host "      $pkg :" -ForegroundColor Yellow
        $errLines = $brokenMap[$pkg].err -split "`r?`n" | Select-Object -Last 6
        foreach ($line in $errLines) {
            if ($line.Trim()) { Write-Host "        $line" -ForegroundColor DarkYellow }
        }
    }

    # Reinstall WITH dependencies (the --no-deps was a mistake; we WANT the
    # transitive deps because they're often what's broken). --no-cache-dir
    # bypasses the pip wheel cache, which can have corrupted permissions
    # (PermissionError on AppData\Local\pip\cache\wheels\...).
    Write-Warn "Reinstalling with --force-reinstall (this also re-pulls transitive deps)..."
    $broken = @($brokenMap.Keys)
    & $EnvPy -s -m pip install --no-user --no-cache-dir --upgrade --force-reinstall $broken
    if ($LASTEXITCODE -ne 0) {
        # Cache-permission failures sometimes only show up on specific wheels;
        # clear pip's cache entirely and try once more.
        Write-Warn "Reinstall failed — clearing pip cache and retrying..."
        $pipCache = Join-Path $env:LOCALAPPDATA 'pip\cache'
        if (Test-Path $pipCache) {
            Remove-Item $pipCache -Recurse -Force -ErrorAction SilentlyContinue
        }
        & $EnvPy -s -m pip install --no-user --no-cache-dir --upgrade --force-reinstall $broken
        if ($LASTEXITCODE -ne 0) { Die "Critical package reinstall failed (even after clearing pip cache)" }
    }

    # Re-verify and surface the FULL error if it still fails.
    foreach ($pkg in $broken) {
        $mod = $brokenMap[$pkg].module
        $r = Test-ImportClean $mod
        if (-not $r.ok) {
            Write-Host ""
            Write-Host "[ERROR] '$mod' still won't import. Full error:" -ForegroundColor Red
            Write-Host $r.err -ForegroundColor Red
            Write-Host ""
            Write-Host "Common fixes:" -ForegroundColor Yellow
            Write-Host "  1. Run manually to see full traceback:" -ForegroundColor Yellow
            Write-Host "     $EnvPy -s -c `"import $mod`"" -ForegroundColor Gray
            Write-Host "  2. Re-create the env from scratch:" -ForegroundColor Yellow
            Write-Host "     $Conda env remove -n $EnvName -y" -ForegroundColor Gray
            Write-Host "     Then re-run install_and_run.bat" -ForegroundColor Gray
            Die "$mod broken; see error above"
        }
    }
    Write-Ok "Reinstalled + verified."
} else {
    Write-Ok "All critical imports OK."
}

# Torch CUDA build check. The pip force-reinstall above can drag torch down
# from cu128 (installed in step 3) to the CPU-only PyPI default build —
# requirements.txt doesn't pin a CUDA variant and pip resolves to whatever
# satisfies the version constraint. The CPU-only build can't deserialize
# CUDA tensors saved in voice.pth: "Torch not compiled with CUDA enabled".
Write-Step "[4c/6] Confirming torch is the cu128 build"
$torchCuda = & $EnvPy -s -c "import torch; print(getattr(torch.version, 'cuda', '') or 'cpu')" 2>$null
$torchCuda = ($torchCuda -as [string]).Trim()
if ($torchCuda -eq 'cpu' -or [string]::IsNullOrEmpty($torchCuda)) {
    Write-Warn "torch was downgraded to CPU-only ('$torchCuda'). Reinstalling cu128..."
    & $EnvPy -s -m pip install --no-user --no-cache-dir --upgrade --force-reinstall torch torchaudio --index-url $TorchIndex
    if ($LASTEXITCODE -ne 0) { Die "torch cu128 reinstall failed" }
    $torchCuda = (& $EnvPy -s -c "import torch; print(getattr(torch.version, 'cuda', '') or 'cpu')" 2>$null) -as [string]
    if ($torchCuda.Trim() -eq 'cpu') { Die "torch is still CPU-only after reinstall" }
    Write-Ok "cu128 restored (torch.version.cuda = $($torchCuda.Trim()))."
} else {
    Write-Ok "torch.version.cuda = $torchCuda."
}

# Recovery: if a prior run of this script installed ffmpeg via conda-forge, it
# bumped openssl/icu and broke PyQt6's QtCore loading. Delete just the .exe
# (not `conda remove`, which prunes shared deps like xz and breaks Python's
# stdlib lzma module). The full ffmpeg conda package is left in metadata but
# inert; imageio-ffmpeg provides the binary we actually use.
$condaFfmpeg = Join-Path $EnvDir 'Library\bin\ffmpeg.exe'
if (Test-Path $condaFfmpeg) {
    Write-Warn "Removing conda-installed ffmpeg.exe (will use imageio-ffmpeg instead)..."
    Remove-Item $condaFfmpeg -Force -ErrorAction SilentlyContinue
    # Also nuke ffprobe / ffplay if they came with it.
    foreach ($exe in @('ffprobe.exe', 'ffplay.exe')) {
        $p = Join-Path $EnvDir "Library\bin\$exe"
        if (Test-Path $p) { Remove-Item $p -Force -ErrorAction SilentlyContinue }
    }
    Write-Ok "ffmpeg.exe removed (other env packages untouched)."
}

# Pre-warm imageio-ffmpeg's binary cache so first respeaker fire is instant.
Write-Step "[5c/6] ffmpeg (via imageio-ffmpeg, isolated)"
$ffmpegPath = & $EnvPy -s -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())" 2>&1
if ($LASTEXITCODE -eq 0 -and $ffmpegPath -and (Test-Path $ffmpegPath.Trim())) {
    Write-Ok "ffmpeg ready at: $($ffmpegPath.Trim())"
} else {
    Write-Warn "Could not pre-warm ffmpeg. First respeaker call will download it."
}

# ------------------------------------------------------------------
# 5a. .env
# ------------------------------------------------------------------
Write-Step "[5/6] .env + RVC voice model"
if (-not (Test-Path .env) -and (Test-Path .env.example)) {
    Copy-Item .env.example .env
    Write-Ok ".env seeded from .env.example. Open it and set OPENAI_API_KEY + OPENROUTER_API_KEY."
} else {
    Write-Ok ".env already present."
}

# ------------------------------------------------------------------
# 5b. RVC model — only download if voice.pth is missing
# ------------------------------------------------------------------
$modelDir = Join-Path $ProjectRoot 'models\respeaker'
$voicePth = Join-Path $modelDir 'voice.pth'
if (-not (Test-Path $voicePth)) {
    Write-Warn "Downloading default RVC voice model (~250 MB)..."
    New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
    $zip = Join-Path $modelDir 'voice.zip'
    try {
        Invoke-WebRequest -Uri $ModelUrl -OutFile $zip -UseBasicParsing
        Expand-Archive -Path $zip -DestinationPath $modelDir -Force
        Remove-Item $zip -Force -ErrorAction SilentlyContinue
        # Normalize any extracted .pth / .index to voice.pth / voice.index
        $pths = @(Get-ChildItem $modelDir -Filter '*.pth' -File)
        foreach ($f in $pths) {
            if ($f.Name -ne 'voice.pth') { Rename-Item $f.FullName 'voice.pth' -Force }
        }
        $idxs = @(Get-ChildItem $modelDir -Filter '*.index' -File)
        foreach ($f in $idxs) {
            if ($f.Name -ne 'voice.index') { Rename-Item $f.FullName 'voice.index' -Force }
        }
        Write-Ok "Model saved as models\respeaker\voice.pth (+ voice.index)."
    } catch {
        Write-Warn "Model download failed: $_"
        Write-Warn "Voice cloning (Ctrl+Alt+5) won't work until you drop voice.pth + voice.index"
        Write-Warn "into models\respeaker\."
    }
} else {
    Write-Ok "voice.pth already present."
}

# ------------------------------------------------------------------
# 6. Launch (or do nothing if already running our pythonw)
# ------------------------------------------------------------------
Write-Step "[6/6] Launching"
$ours = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.ExecutablePath -like "$EnvDir*" }
if ($ours) {
    Write-Ok "App already running (pid $($ours.ProcessId)). Doing nothing."
} else {
    Start-Process -FilePath $EnvPyW -ArgumentList '-s', "`"$ProjectRoot\main.py`"" -WorkingDirectory $ProjectRoot
    Write-Ok "Started. Look for the tray icon (bottom-right of taskbar)."
    Write-Host ""
    Write-Host "Hotkeys:" -ForegroundColor White
    Write-Host "  Ctrl+Alt+0   Launcher popup"
    Write-Host "  Ctrl+Alt+1   Voice -> Clipboard (online OpenAI Whisper)"
    Write-Host "  Ctrl+Alt+2   Voice -> Clipboard (offline faster-whisper)"
    Write-Host "  Ctrl+Alt+3   Fix grammar (clipboard text)"
    Write-Host "  Ctrl+Alt+4   YouTube transcribe (paste URL)"
    Write-Host "  Ctrl+Alt+5   Voice -> cloned voice playback"
}

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Start-Sleep -Seconds 3
