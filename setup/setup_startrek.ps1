# Star Trek - one-time setup on a new Windows PC (NVIDIA RTX GPU). Safe to run again: finished steps are skipped,
# downloads resume. Started by "SETUP NEW PC.bat" in the Star Trek folder. Log: setup\setup_log.txt
#
#   -AnyLocation   set it up right where it is, without A: (not recommended: the tools and manuals expect A:\Ai projects\Star Trek)
#   -SkipModels    everything except the ~150 GB of model downloads (run again later without it)
param([switch]$AnyLocation, [switch]$SkipModels)

$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'SilentlyContinue'
$Setup = $PSScriptRoot
$ST    = Split-Path -Parent $Setup
$CCdir = Join-Path $ST 'ClaudeComfy'
$Want  = 'A:\Ai projects\Star Trek'
$Log   = Join-Path $Setup 'setup_log.txt'
$env:PYTHONUTF8 = '1'; $env:PYTHONIOENCODING = 'utf-8'; $env:UV_LINK_MODE = 'copy'; $env:UV_HTTP_TIMEOUT = '600'
Start-Transcript -Path $Log -Append | Out-Null

function Say([string]$t, [string]$c = 'Gray') { Write-Host $t -ForegroundColor $c }
function Step([string]$t) { Say ''; Say ("=== " + $t + " ===") 'Cyan' }
function Stop-Setup([string]$t) { Say ''; Say ("SETUP STOPPED: " + $t) 'Red'; Say ("Log: " + $Log) 'Red'; Stop-Transcript | Out-Null; exit 1 }
function Have([string]$cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Refresh-Path {
    $m = [Environment]::GetEnvironmentVariable('Path', 'Machine'); $u = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = ($m + ';' + $u + ';' + (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links'))
}
function Winget([string]$id, [string]$what) {
    # winget when Windows has it; otherwise (Windows 10 LTSC has no winget) the official installer, downloaded directly
    Refresh-Path
    if (Have 'winget') {
        Say ("installing " + $what + " (winget " + $id + ") ...")
        & winget install -e --id $id --accept-package-agreements --accept-source-agreements --silent
        Refresh-Path; return
    }
    Say ("installing " + $what + " (no winget on this Windows - official installer) ...")
    $t = Join-Path $env:TEMP ('st_' + ($id -replace '[^A-Za-z0-9]', '_'))
    switch ($id) {
        'Git.Git' {
            $r = Invoke-RestMethod 'https://api.github.com/repos/git-for-windows/git/releases/latest'
            $u = ($r.assets | Where-Object { $_.name -match '^Git-[0-9.]+-64-bit\.exe$' } | Select-Object -First 1).browser_download_url
            Download $u "$t.exe"; Start-Process -Wait "$t.exe" '/VERYSILENT /NORESTART /NOCANCEL /SP- /SUPPRESSMSGBOXES'
        }
        'Python.Python.3.12' {
            Download 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' "$t.exe"
            Start-Process -Wait "$t.exe" '/quiet InstallAllUsers=0 InstallLauncherAllUsers=0 Include_launcher=1 PrependPath=1 Include_test=0'
            $env:Path = (Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher') + ';' + $env:Path
        }
        'Gyan.FFmpeg' { Install-FFmpegZip }
        'Ollama.Ollama' {
            Download 'https://ollama.com/download/OllamaSetup.exe' "$t.exe"; Start-Process -Wait "$t.exe" '/VERYSILENT /NORESTART /SUPPRESSMSGBOXES'
        }
        'Microsoft.VCRedist.2015+.x64' {
            Download 'https://aka.ms/vs/17/release/vc_redist.x64.exe' "$t.exe"; Start-Process -Wait "$t.exe" '/install /quiet /norestart'
        }
        'Google.Chrome' {
            Download 'https://dl.google.com/chrome/install/googlechromestandaloneenterprise64.msi' "$t.msi"
            Start-Process -Wait msiexec.exe ('/i "' + $t + '.msi" /qn /norestart')
        }
    }
    Refresh-Path
}
function Add-UserPath([string]$dir) {
    # put a folder on this user's PATH for good, and on this window's PATH now (works when the user PATH is empty)
    $up = [Environment]::GetEnvironmentVariable('Path', 'User'); if (-not $up) { $up = '' }
    if (($up -split ';') -notcontains $dir) { [Environment]::SetEnvironmentVariable('Path', (($up.TrimEnd(';') + ';' + $dir).TrimStart(';')), 'User') }
    if (($env:Path -split ';') -notcontains $dir) { $env:Path = $dir + ';' + $env:Path }
}
function Find-FFmpeg {
    # wherever ffmpeg ended up: the direct download, a winget install (Links or its package folder), a hand install
    $dirs = @('C:\ffmpeg\bin', (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links'), 'C:\Program Files\ffmpeg\bin')
    foreach ($root in (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'), 'C:\Program Files\WinGet\Packages') {
        if (Test-Path $root) {
            Get-ChildItem -Directory $root -Filter 'Gyan.FFmpeg*' -ErrorAction SilentlyContinue | ForEach-Object {
                $hit = Get-ChildItem -Recurse -File -Filter ffmpeg.exe $_.FullName -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($hit) { $dirs += $hit.DirectoryName }
            }
        }
    }
    foreach ($d in $dirs) { if ($d -and (Test-Path (Join-Path $d 'ffmpeg.exe'))) { return $d } }
    return $null
}
function Install-FFmpegZip {
    $z = Join-Path $env:TEMP 'st_ffmpeg.zip'; $x = Join-Path $env:TEMP 'st_ffmpeg'
    Download 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' $z
    if (Test-Path $x) { Remove-Item -Recurse -Force $x }
    Expand-Archive -Force $z $x
    $exe = Get-ChildItem -Recurse -File -Filter ffmpeg.exe $x | Select-Object -First 1
    if (-not $exe) { Stop-Setup 'the ffmpeg download had no ffmpeg.exe in it' }
    New-Item -ItemType Directory -Path 'C:\ffmpeg\bin' -Force | Out-Null
    Copy-Item -Force (Join-Path $exe.DirectoryName '*') 'C:\ffmpeg\bin\'
}
function Download([string]$url, [string]$out) {
    & curl.exe -L --fail --retry 5 -C - -o $out $url
    if ($LASTEXITCODE -ne 0) { Stop-Setup ("download failed: " + $url) }
}
function Junction([string]$old, [string]$new) {
    if (Test-Path -LiteralPath $old) {
        $it = Get-Item -LiteralPath $old -Force
        if ($it.LinkType -eq 'Junction') { Say ("   ok   " + $old + " -> " + $it.Target); return }
        Say ("   NOTE " + $old + " already exists as a real folder - left alone (it should point to " + $new + ")") 'Yellow'; return
    }
    $parent = Split-Path -Parent $old
    if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    $target = $new
    $home_ = Get-Item -LiteralPath $Want -Force -ErrorAction SilentlyContinue
    if ($home_ -and $home_.LinkType -eq 'Junction' -and $target -like ($Want + '*')) { $target = (@($home_.Target)[0]).TrimEnd('\') + $target.Substring($Want.Length) }
    $dd = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\DOS Devices' -ErrorAction SilentlyContinue).'A:'
    if (-not $dd) { $sl = (& subst.exe) | Where-Object { $_ -like 'A:\*' } | Select-Object -First 1; if ($sl) { $dd = ($sl -split '=> ')[1] } }
    if ($dd -and $target -like 'A:*' -and $target -notlike ($Want + '*')) { $target = ($dd -replace '^\\\?\?\\', '').TrimEnd('\') + $target.Substring(2) }
    cmd /c mklink /J "$old" "$target" | Out-Null
    Say ("   made " + $old + " -> " + $new)
}

Say ''
Say '   STAR TREK - new PC setup' 'Green'
Say ('   folder: ' + $ST)

# ---------------------------------------------------------------- 0. location
# Unzipped anywhere: with an A: drive, Star Trek is copied to A:\Ai projects\Star Trek (where every config, doc and song
# project expects it) and the setup carries on from there. Without an A: drive it runs right where it is.
Step 'Location'
if (-not (Test-Path 'A:\') -and -not $AnyLocation) {
    # No A: drive: make one. A:\ is the folder C:\A (nothing is renamed or moved; the C: drive stays as it is).
    # Now for this session with subst; for every restart through Windows' DOS Devices registry key (one admin prompt).
    $root = 'C:\A'
    $free = [int]((Get-PSDrive C).Free / 1GB)
    Say ('This PC has no A: drive - making A: from ' + $root + ' (C: has ' + $free + ' GB free; Star Trek needs about 250 GB)') 'Yellow'
    if ($free -lt 250) { Say '   NOTE: less than 250 GB free on C: - the model downloads may run out of space' 'Yellow' }
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    & subst.exe A: $root | Out-Null
    if (-not (Test-Path 'A:\')) { Stop-Setup 'could not make the A: drive (subst A: C:\A failed)' }
    $reg = "New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\DOS Devices' -Name 'A:' -Value '\??\C:\A' -PropertyType String -Force | Out-Null"
    Say '   Windows will ask for admin permission once, so A: stays after restarts - choose Yes.'
    try {
        Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList ('-NoProfile -EncodedCommand ' + [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($reg)))
    } catch { }
    $kept = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\DOS Devices' -ErrorAction SilentlyContinue).'A:'
    if ($kept) { Say '   A: drive made (C:\A) and kept after restarts' 'Green' }
    else {
        # no admin: map A: at every login instead (works for Star Trek, which runs as you)
        Set-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'Star Trek A drive' -Value 'subst.exe A: C:\A'
        Say '   A: drive made (C:\A); no admin permission, so it is mapped again at every login' 'Yellow'
    }
}
if ($ST -ne $Want -and (Test-Path 'A:\') -and -not $AnyLocation) {
    $it = Get-Item -LiteralPath $Want -Force -ErrorAction SilentlyContinue
    if ($it -and $it.LinkType -ne 'Junction') {
        # an older Star Trek already lives in A:\Ai projects\Star Trek: update it (this PC's own settings are kept)
        Say ('   updating the Star Trek in ' + $Want + ' ...')
        & robocopy $ST $Want /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XF songs.txt level.txt config.json launcher.json /XD .git | Out-Null
        if ($LASTEXITCODE -ge 8) { Stop-Setup ('could not copy to ' + $Want) }
    } else {
        # the files stay where they are: A:\Ai projects\Star Trek becomes a link to this folder, so every tool and manual
        # finds them at the A: path
        if ($it) { cmd /c rmdir "$Want" | Out-Null }
        New-Item -ItemType Directory -Path (Split-Path -Parent $Want) -Force | Out-Null
        cmd /c mklink /J "$Want" "$ST" | Out-Null
        if (-not (Test-Path (Join-Path $Want 'SETUP NEW PC.bat'))) { Stop-Setup ('could not link ' + $Want + ' to ' + $ST) }
        Say ('   ' + $Want + ' -> ' + $ST + '  (the files stay in this folder)') 'Green'
    }
    Say ('   continuing the setup through ' + $Want)
    Stop-Transcript | Out-Null
    $more = @(); if ($SkipModels) { $more += '-SkipModels' }
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Want 'setup\setup_startrek.ps1') @more
    exit $LASTEXITCODE
}
$onA = ($ST -eq $Want)
if (-not $onA) { Say ('   -AnyLocation: Star Trek is set up right here: ' + $ST + ' (the A: links are skipped; the tools and manuals still expect A:)') 'Yellow' }
$CC  = if ($onA) { 'A:\ClaudeComfy' } else { $CCdir }

# Files from a GitHub "Download ZIP" carry Windows' downloaded-from-the-internet mark, which makes SmartScreen block
# Comfort.exe and the hidden watchdog. Clear it on everything in the Star Trek folder (a git clone has no mark).
Get-ChildItem -LiteralPath $ST -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue

# ---------------------------------------------------------------- 1. programs
Step 'Programs (git, Python 3.12, ffmpeg, Ollama, VC++ runtime, a browser for Comfort)'
Refresh-Path
if (-not (Have 'git'))    { Winget 'Git.Git' 'Git' }
& git config --global core.longpaths true
$py312 = $false; if (Have 'py') { & py -3.12 -c "import sys" 2>$null; $py312 = ($LASTEXITCODE -eq 0) }
if (-not $py312)          { Winget 'Python.Python.3.12' 'Python 3.12' }
if (-not (Have 'ffmpeg')) {
    $ff = Find-FFmpeg
    if (-not $ff) { Winget 'Gyan.FFmpeg' 'ffmpeg'; $ff = Find-FFmpeg }
    if (-not $ff -and -not (Have 'ffmpeg')) { Say 'ffmpeg still missing - downloading it directly ...'; Install-FFmpegZip; $ff = Find-FFmpeg }
    if ($ff) { Add-UserPath $ff; Say ('   ffmpeg: ' + $ff) }
}
$ollama = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
if (-not (Have 'ollama') -and -not (Test-Path $ollama)) { Winget 'Ollama.Ollama' 'Ollama' }
if (-not (Test-Path (Join-Path $env:WINDIR 'System32\vcruntime140_1.dll'))) { Winget 'Microsoft.VCRedist.2015+.x64' 'Visual C++ runtime' }
# Comfort opens its window in Edge or Chrome (Windows 10 LTSC 2019 has neither)
$browsers = @('C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', 'C:\Program Files\Microsoft\Edge\Application\msedge.exe', 'C:\Program Files\Google\Chrome\Application\chrome.exe')
if (-not ($browsers | Where-Object { Test-Path $_ })) { Winget 'Google.Chrome' 'Google Chrome (for Comfort''s window)'; if (-not ($browsers | Where-Object { Test-Path $_ })) { Say '   Chrome did not install (it needs admin rights) - install Chrome or Edge by hand' 'Yellow' } }
foreach ($c in 'git', 'py', 'ffmpeg') { if (-not (Have $c)) { Stop-Setup ($c + " is still not on PATH - close this window, open a new one and run setup again") } }
try { & nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader } catch { Say 'nvidia-smi not found - an NVIDIA driver 580+ is needed (CUDA 13)' 'Yellow' }

# ---------------------------------------------------------------- 2. folders and the old-path links
Step 'Folders and links (the old paths Justice''s tools still use)'
foreach ($d in 'Preview', 'Comfort\inbox', 'Comfort\out\videos', 'Comfort\out\video_info', 'Comfort\inputs', 'Comfort\jobs\done', 'Comfort\jobs\failed', 'Overseer\logs', 'Overseer\sheets', 'FilmCraft\renders', 'FilmCraft\cuts') {
    New-Item -ItemType Directory -Path (Join-Path $ST $d) -Force | Out-Null
}
if ($onA) {
    Junction 'A:\ClaudeComfy'              $CCdir
    Junction 'A:\artcraft\FilmCraft'       (Join-Path $ST 'FilmCraft')
    Junction 'A:\Ai projects\Comfort'      (Join-Path $ST 'Comfort')
    Junction 'A:\Ai projects\ClaudeSubtitles' (Join-Path $ST 'ClaudeSubtitles')
    foreach ($d in 'A:\Music', 'A:\finished\sentimientos_style_tests\fonts') { New-Item -ItemType Directory -Path $d -Force | Out-Null }
    if (Test-Path 'A:\ClaudeComfy\ComfyUI\main.py') {
        $real = (Get-Item 'A:\ClaudeComfy' -Force).LinkType
        if ($real -ne 'Junction') { Say '   A:\ClaudeComfy is a separate real install - this setup builds the one inside Star Trek\ClaudeComfy' 'Yellow' }
    }
}

# ---------------------------------------------------------------- 3. ComfyUI + custom nodes (pinned)
Step 'ComfyUI v0.39.2 and the 26 custom node packs (pinned commits)'
$Comfy = Join-Path $CCdir 'ComfyUI'
$lines = Get-Content (Join-Path $Setup 'custom_nodes.txt') | Where-Object { $_ -and -not $_.StartsWith('#') }
foreach ($ln in $lines) {
    $p = $ln.Split('|') | ForEach-Object { $_.Trim() }
    $name, $url, $sha = $p[0], $p[1], $p[2]
    $dir = if ($name -eq 'ComfyUI') { $Comfy } else { Join-Path $Comfy ('custom_nodes\' + $name) }
    if (Test-Path (Join-Path $dir '.git')) {
        $cur = (& git -C $dir rev-parse HEAD).Trim()
        if ($cur.StartsWith($sha)) { Say ("   ok   " + $name); continue }
    } else {
        Say ("   clone " + $name)
        & git clone --filter=blob:none --quiet $url $dir
        if ($LASTEXITCODE -ne 0) { Stop-Setup ("git clone failed: " + $url) }
    }
    & git -C $dir -c advice.detachedHead=false checkout --quiet $sha
    if ($LASTEXITCODE -ne 0) { Stop-Setup ("could not check out " + $name + " at " + $sha) }
    Say ("   at " + $sha + "  " + $name)
}
$k2e = Join-Path $Comfy 'custom_nodes\comfyui-krea2edit'
if (-not (Test-Path $k2e)) { Copy-Item -Recurse (Join-Path $CCdir 'local_nodes\comfyui-krea2edit') $k2e; Say '   copied comfyui-krea2edit (v1.2.5)' }
# workflows (UI + Comfort's API copies), ComfyUI settings, extra model paths
$ud = Join-Path $Comfy 'user\default'
New-Item -ItemType Directory -Path $ud -Force | Out-Null
Get-ChildItem -Recurse -File (Join-Path $CCdir 'comfyui_user\default') | ForEach-Object {
    $rel = $_.FullName.Substring((Join-Path $CCdir 'comfyui_user\default').Length + 1)
    $dst = Join-Path $ud $rel
    if (-not (Test-Path -LiteralPath $dst)) { New-Item -ItemType Directory -Path (Split-Path -Parent $dst) -Force | Out-Null; Copy-Item -LiteralPath $_.FullName $dst }
}
$emp = Join-Path $Comfy 'extra_model_paths.yaml'
if (-not (Test-Path $emp)) { Copy-Item (Join-Path $CCdir 'comfyui_extra_model_paths.yaml') $emp }
Say '   workflows, settings and extra_model_paths.yaml in place'

# ---------------------------------------------------------------- 4. Python environment for ComfyUI + Comfort
Step 'ClaudeComfy Python environment (uv, Python 3.12, PyTorch 2.10 CUDA 13.0, node packages)'
$uv = Join-Path $CCdir 'tools\uv.exe'
if (-not (Test-Path $uv)) {
    New-Item -ItemType Directory -Path (Join-Path $CCdir 'tools') -Force | Out-Null
    $z = Join-Path $env:TEMP 'uv-win.zip'
    Download 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' $z
    Expand-Archive -Force $z (Join-Path $env:TEMP 'uv-win'); Copy-Item (Join-Path $env:TEMP 'uv-win\uv.exe') $uv
}
$venvPy = Join-Path $CC 'venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) { & $uv venv (Join-Path $CC 'venv') --python 3.12 --seed; if ($LASTEXITCODE -ne 0) { Stop-Setup 'uv venv failed' } }
$idx = 'https://download.pytorch.org/whl/cu130'
& $uv pip install --python $venvPy --index-url $idx 'torch==2.10.0+cu130' 'torchvision==0.25.0+cu130' 'torchaudio==2.11.0+cu130'
if ($LASTEXITCODE -ne 0) { Stop-Setup 'PyTorch install failed' }
& $uv pip install --python $venvPy -c (Join-Path $CC 'scripts\constraints.txt') --extra-index-url $idx --index-strategy unsafe-best-match -r (Join-Path $CC 'scripts\krea_requirements.txt')
if ($LASTEXITCODE -ne 0) { Stop-Setup 'Krea node packages failed' }
# ClaudeComfy's own setup (from Justice's PC): ComfyUI + Manager + node requirements, NVIDIA VFX (RTX upscaler used by
# the Stage 1080p60 finish), GPU check, MiniMax H3 support downloads, test start of ComfyUI with every custom node.
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $CC 'scripts\setup_claudecomfy.ps1')
if ($LASTEXITCODE -ne 0) { Stop-Setup 'ClaudeComfy setup failed - see ClaudeComfy\setup_log.txt' }

# ---------------------------------------------------------------- 5. models
if (-not $SkipModels) {
    Step 'Model files (about 150 GB: Krea 2, MiniMax H3, style LoRAs, 1080p60 finish, 3D)'
    $tokFile = Join-Path $Setup 'civitai_token.txt'
    if (-not $env:CIVITAI_TOKEN -and -not (Test-Path $tokFile)) {
        Say 'Two models come from Civitai (DaSiWa H3 Hybrid v3, RedCraft Krea2 3.0) and need your Civitai API key:' 'Yellow'
        Say 'civitai.com > your avatar > Account settings > API Keys > Add API key. Paste it here (Enter = skip for now).' 'Yellow'
        $t = Read-Host 'Civitai API key'
        if ($t) { Set-Content -Path $tokFile -Value $t.Trim() -Encoding ASCII }
    }
    & $venvPy -s (Join-Path $Setup 'download_models.py')
    if ($LASTEXITCODE -ne 0) { Say 'Some model downloads did not finish - run setup again to resume them (the list is above).' 'Yellow' }
}

# ---------------------------------------------------------------- 6. FilmCraft 0.10.0 (the exact build fc.py runs on)
Step 'FilmCraft 0.10.0'
$fcdir = Join-Path $ST 'FilmCraft'
if (-not (Test-Path (Join-Path $fcdir 'filmcraft-cli.exe'))) {
    $z = Join-Path $env:TEMP 'filmcraft-0.10.0.zip'
    Download 'https://github.com/storytold/filmcraft/releases/download/v0.10.0/filmcraft-0.10.0-windows-x64-portable.zip' $z
    $h = (Get-FileHash $z -Algorithm SHA256).Hash.ToLower()
    if ($h -ne '8f5b52e0f8fd5540b5e0a4c5ae283f11371df1d983fd109f248a3d6c1ed5a263') { Remove-Item $z; Stop-Setup 'FilmCraft download damaged (sha256) - run again' }
    Expand-Archive -Force $z (Join-Path $env:TEMP 'fc010')
    Copy-Item (Join-Path $env:TEMP 'fc010\filmcraft-0.10.0-windows-x64-portable\filmcraft.exe'), (Join-Path $env:TEMP 'fc010\filmcraft-0.10.0-windows-x64-portable\filmcraft-cli.exe') $fcdir
}
Say '   filmcraft.exe + filmcraft-cli.exe in FilmCraft\'

# ---------------------------------------------------------------- 7. Subtitle Studio, then SongMap (SongMap uses Subtitle Studio's models)
Step 'Subtitle Studio (Qwen3-ASR lyrics, about 7 GB of models)'
$ss = Join-Path $ST 'ClaudeSubtitles\SubtitleStudio'
if (-not (Test-Path (Join-Path $ss 'venv\Scripts\python.exe')) -or -not (Test-Path (Join-Path $ss 'models'))) {
    Push-Location $ss; cmd /c setup.bat; $c = $LASTEXITCODE; Pop-Location
    if ($c -ne 0) { Stop-Setup 'Subtitle Studio setup failed (see the lines above)' }
} else { Say '   ok' }
Step 'SongMap (beats, sections, lyrics on timestamps)'
$sm = Join-Path $ST 'SongMap'
if (-not (Test-Path (Join-Path $sm 'venv\Scripts\python.exe')) -or -not (Test-Path (Join-Path $sm 'models\SongFormer'))) {
    Push-Location $sm; cmd /c setup.bat; $c = $LASTEXITCODE; Pop-Location
    if ($c -ne 0) { Stop-Setup 'SongMap setup failed (see the lines above)' }
} else { Say '   ok' }

# ---------------------------------------------------------------- 8. the local AI (Ollama)
Step 'Local AI: Ollama + qwen3.6:27b (Comfort agent and Overseer, about 18 GB)'
Refresh-Path
$oll = if (Have 'ollama') { 'ollama' } else { $ollama }
& $oll list *> $null
if ($LASTEXITCODE -ne 0) { Start-Process -WindowStyle Hidden $oll 'serve'; Start-Sleep 6 }
& $oll pull qwen3.6:27b
if ($LASTEXITCODE -ne 0) { Say '   ollama pull failed - run "ollama pull qwen3.6:27b" later' 'Yellow' }

# ---------------------------------------------------------------- 9. Comfort config for this PC
Step 'Comfort settings for this PC'
$utf8 = New-Object System.Text.UTF8Encoding $false            # no BOM: Python's json.load refuses a BOM
$cfgp = Join-Path $ST 'Comfort\config.json'
$cfg = Get-Content $cfgp -Raw | ConvertFrom-Json
$wantDir = (Join-Path $CC 'ComfyUI')
if ($cfg.comfy_dir -ne $wantDir -or $cfg.comfy_python -ne $venvPy -or -not $onA) {
    $cfg.comfy_dir = $wantDir; $cfg.comfy_python = $venvPy
    if (-not $onA) { $cfg | Add-Member -Force filmcraft_dir $fcdir }
    [IO.File]::WriteAllText($cfgp, ($cfg | ConvertTo-Json -Depth 10), $utf8)
}
$lp = Join-Path $ST 'Comfort\launcher.json'
$l = Get-Content $lp -Raw | ConvertFrom-Json
$wantPyw = (Join-Path $CC 'venv\Scripts\pythonw.exe')
if ($l.python -ne $wantPyw) { $l.python = $wantPyw; [IO.File]::WriteAllText($lp, ($l | ConvertTo-Json), $utf8) }
Say ('   Comfort -> ' + $cfg.comfy_dir)

# ---------------------------------------------------------------- 10. fonts used by the Sentimientos subtitles
Step 'Fonts'
if ($onA) {
    $f = 'A:\finished\sentimientos_style_tests\fonts\Caprasimo-Regular.ttf'
    if (-not (Test-Path $f)) { Download 'https://github.com/google/fonts/raw/main/ofl/caprasimo/Caprasimo-Regular.ttf' $f }
    Say '   Caprasimo in A:\finished\sentimientos_style_tests\fonts'
}

# ---------------------------------------------------------------- 11. check
Step 'Check'
$ok = $true
foreach ($p in @("$Comfy\main.py", $venvPy, "$fcdir\filmcraft-cli.exe", "$ss\venv\Scripts\python.exe", "$sm\venv\Scripts\python.exe", "$ST\Comfort\Comfort.exe")) {
    if (Test-Path $p) { Say ("   ok      " + $p) } else { Say ("   MISSING " + $p) 'Red'; $ok = $false }
}
& $venvPy -s (Join-Path $Setup 'download_models.py') --list
Stop-Transcript | Out-Null
Say ''
if ($ok) {
    Say 'SETUP FINISHED.' 'Green'
    Say 'Next: double-click "Open Star Trek.bat" (starts Comfort -> ComfyUI + Ollama, opens the Star Trek interface).' 'Green'
    Say 'Before that, look at Overseer\songs.txt: songs set to auto start generating as soon as Comfort runs.' 'Green'
} else { Say 'Setup finished with missing parts (red above). Run it again.' 'Yellow' }
