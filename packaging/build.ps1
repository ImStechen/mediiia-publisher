param(
    [switch]$SkipInstallers
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$PyInstaller = Join-Path $Root ".venv\Scripts\pyinstaller.exe"
$Version = (Get-Content (Join-Path $Root "VERSION") -Raw).Trim()
$Release = Join-Path $Root "release"
$Portable = Join-Path $Release "portable"

Get-Process "MediiiaPublisher" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500

if (-not (Test-Path $Python)) {
    throw "Python virtual environment not found: $Python"
}
if (-not (Test-Path $PyInstaller)) {
    & $Python -m pip install pyinstaller
}

& $Python (Join-Path $PSScriptRoot "make_icon.py")
if ($LASTEXITCODE -ne 0) { throw "Icon generation failed" }

Remove-Item (Join-Path $Root "build") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $Root "dist") -Recurse -Force -ErrorAction SilentlyContinue
if (Test-Path $Release) {
    Remove-Item $Release -Recurse -Force
}
New-Item $Portable -ItemType Directory -Force | Out-Null

Push-Location $Root
try {
    & $PyInstaller --noconfirm --clean (Join-Path $PSScriptRoot "MediiiaPublisher.spec")
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
} finally {
    Pop-Location
}

Copy-Item (Join-Path $Root "dist\MediiiaPublisher\*") $Portable -Recurse
Copy-Item (Join-Path $Root "config.example.json") $Portable
Copy-Item (Join-Path $Root "README.md") $Portable
Copy-Item (Join-Path $Root "VERSION") $Portable

$PortableReadme = @"
MEDIIIA PUBLISHER $Version

Run MediiiaPublisher.exe. Installation is not required.
The folder can be moved to another Windows computer.

Requirements:
- Windows 10/11 x64
- Google Chrome or Microsoft Edge
- Internet access

User data is stored separately:
%USERPROFILE%\.mediiia-publisher
"@
Set-Content (Join-Path $Portable "START.txt") $PortableReadme -Encoding utf8

$Zip = Join-Path $Release "MediiiaPublisher-portable.zip"
Compress-Archive -Path (Join-Path $Portable "*") -DestinationPath $Zip -CompressionLevel Optimal

$BuildIni = "[build]`r`nversion=$Version`r`n"
Set-Content (Join-Path $PSScriptRoot "build.ini") $BuildIni -Encoding ascii

if (-not $SkipInstallers) {
    $IsccCandidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
    )
    $Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $Iscc) {
        throw "Inno Setup 6 (ISCC.exe) not found"
    }
    & $Iscc (Join-Path $PSScriptRoot "offline-installer.iss")
    if ($LASTEXITCODE -ne 0) { throw "Offline installer build failed" }
    & $Iscc (Join-Path $PSScriptRoot "online-installer.iss")
    if ($LASTEXITCODE -ne 0) { throw "Online installer build failed" }
}

Get-ChildItem $Release -File | ForEach-Object {
    $Hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    [PSCustomObject]@{
        File = $_.Name
        SizeMB = [math]::Round($_.Length / 1MB, 2)
        SHA256 = $Hash
    }
} | Format-Table -AutoSize
