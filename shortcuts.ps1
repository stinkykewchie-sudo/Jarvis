<#
  Creates Jarvis shortcuts on Windows: Desktop, Start menu (voice and typed), and optionally Startup.

    powershell -ExecutionPolicy Bypass -File shortcuts.ps1             # Desktop + Start menu
    powershell -ExecutionPolicy Bypass -File shortcuts.ps1 -Startup    # ...and start Jarvis when you log in
    powershell -ExecutionPolicy Bypass -File shortcuts.ps1 -NoStartup  # stop starting Jarvis when you log in
    powershell -ExecutionPolicy Bypass -File shortcuts.ps1 -Remove     # remove every Jarvis shortcut
#>
param([switch]$Startup, [switch]$NoStartup, [switch]$Remove)

$dir = $PSScriptRoot
$desktop = Join-Path ([Environment]::GetFolderPath('Desktop')) "Jarvis.lnk"
$menu = Join-Path ([Environment]::GetFolderPath('Programs')) "Jarvis"
$autostart = Join-Path ([Environment]::GetFolderPath('Startup')) "Jarvis.lnk"

if ($Remove) {
    Remove-Item -Force -ErrorAction SilentlyContinue $desktop, $autostart
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $menu
    Write-Host "Removed the Jarvis shortcuts."
    exit
}
if ($NoStartup) {
    Remove-Item -Force -ErrorAction SilentlyContinue $autostart
    Write-Host "Jarvis will no longer start when you log in."
    exit
}

if (-not (Test-Path "$dir\jarvis.ico") -and (Test-Path "$dir\.venv\Scripts\python.exe")) {
    & "$dir\.venv\Scripts\python.exe" "$dir\make_icon.py" | Out-Null
}

$shell = New-Object -ComObject WScript.Shell
function New-JarvisShortcut($path, $arguments, $description, $windowStyle = 1) {
    $s = $shell.CreateShortcut($path)
    $s.TargetPath = Join-Path $dir "Start Jarvis.bat"
    $s.Arguments = $arguments
    $s.WorkingDirectory = $dir
    $s.IconLocation = "$dir\jarvis.ico,0"
    $s.Description = $description
    $s.WindowStyle = $windowStyle  # 1 = normal window, 7 = minimised
    $s.Save()
    Write-Host "Created $path"
}

New-Item -ItemType Directory -Force $menu | Out-Null
New-JarvisShortcut $desktop "" "Jarvis voice assistant - say 'Jarvis' and a command"
New-JarvisShortcut (Join-Path $menu "Jarvis.lnk") "" "Jarvis voice assistant - say 'Jarvis' and a command"
New-JarvisShortcut (Join-Path $menu "Jarvis (type commands).lnk") "--type" "Jarvis with typed commands instead of voice"
if ($Startup) {
    New-JarvisShortcut $autostart "" "Starts Jarvis when you log in" 7
}
