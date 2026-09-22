param(
    [ValidateSet('nuitka', 'pyinstaller')] [string]$Engine = 'nuitka',
    [ValidateSet('onefile', 'standalone')] [string]$Mode = 'onefile',
    [string]$Version = ''
)
Set-Location -LiteralPath $PSScriptRoot
$uvArgs = @('run', '--group', 'build', 'python', 'build_binary.py', '--engine', $Engine, '--mode', $Mode)
if ($Version) { $uvArgs += @('--version', $Version) }
uv @uvArgs
exit $LASTEXITCODE
