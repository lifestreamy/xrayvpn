<#
.SYNOPSIS
Provision and configure an Xray VLESS + REALITY VPN server via Linux/WSL + Ansible.

.DESCRIPTION
This script is a Windows/PowerShell wrapper around provision-vpn.sh.
It forwards connection parameters, cleanup options, and verbosity settings
into WSL, runs the Ansible-based provisioning, and ensures generated client
configs are copied to a Windows-accessible directory.

This script supports two parameter modes:
  - CLI mode (default): Pass connection parameters via flags
  - Inventory mode: Use pre-filled inventory.yml file (specify -UseInventory)

This project does not require Windows: on a native Linux environment you can
run provision-vpn.sh directly. On Windows, this PowerShell script provides
the same functionality by running the bash script through WSL.

For detailed usage, parameters, and examples, run:
  Get-Help .\Provision-VPN.ps1 -Full

.NOTES
If you want to be interactively prompted for an SSH password with
hidden input, specify neither -Pass nor -PKey.

+--------------------------------------------------------------+
| Release: v2026-09-04                                         |
| Author:  Tim Korelov                                         |
| Contact: https://korelov.dev                                 |
| License: AGPL-3.0 + commercial-use restriction                |
+--------------------------------------------------------------+

.PARAMETER UseInventory
Use values from inventory.yml in the project root instead of CLI parameters.
When specified, connection/auth parameters are ignored. If inventory.yml does
not exist, create it first:
  Copy-Item inventory.yml.example inventory.yml
and fill in ansible_host, ansible_user, ansible_port and ONE auth method
(ansible_ssh_private_key_file or ansible_ssh_pass).
Mutual exclusion between key and password is validated by the underlying
bash script.

.PARAMETER Inventory
Path to an explicit inventory file to use instead of CLI parameters
(same mode as -UseInventory, but any location on disk).
Mutually exclusive with -UseInventory when the default file makes sense.

.PARAMETER HostName
VPS IP or hostname to connect to (required in CLI mode).

.PARAMETER User
SSH user name. Defaults to 'root'.

.PARAMETER Port
SSH port. Defaults to 22.

.PARAMETER PKey
Path to the SSH private key for key-based authentication.
Must be an OpenSSH-format key readable from WSL (e.g. C:\Users\You\.ssh\id_rsa,
which is converted to /mnt/c/Users/You/.ssh/id_rsa). PuTTY .ppk files are
not supported. Mutually exclusive with -Pass.

.PARAMETER Pass
SSH password for password-based authentication (plain text).
If omitted and -PKey is not provided, you will be prompted in
interactive mode with hidden input. The password is never logged,
even in -LogLevel Verbose or -DryRun output.

.PARAMETER ClientsDir
Directory on Windows where generated client configs will be stored.
If omitted, a 'downloaded-clients' directory is created next to this script.

.PARAMETER CleanupMode
Controls cleanup behavior in the underlying bash script.
Allowed values:
  Default  - remove only the temporary workspace (maps to --cleanup)
  Full     - remove workspace AND any packages installed by the bash script
  None     - keep the temporary workspace for debugging

Defaults to Default.

.PARAMETER DryRun
Developer mode. The wrapper still invokes WSL and runs provision-vpn.sh,
but with --dry-run so that no packages are installed, no Ansible run
modifies the VPS, and no temporary files are removed. Useful for previewing
the final command line and verifying parameters.

.PARAMETER Rotate
Regenerate the REALITY identity (forwards --rotate to the bash script;
the old state is backed up on the server before rotation).
Mutually exclusive with -NoRotate.

.PARAMETER NoRotate
Explicitly keep the existing REALITY identity (forwards --no-rotate;
this is the default behavior).

.PARAMETER Runtime
xray_runtime override (forwards --runtime): native | docker.
Default: value from config/settings.yml on the server bundle.

.PARAMETER Warp
Force-enable the Cloudflare WARP outbound (forwards --warp).
Mutually exclusive with -NoWarp.

.PARAMETER NoWarp
Force-disable the Cloudflare WARP outbound (forwards --no-warp).
Mutually exclusive with -Warp.

.PARAMETER XrayPort
VLESS inbound TCP port (forwards --xray-port; default 443).

.PARAMETER NumClients
Number of client configs to generate (forwards --num-clients).

.PARAMETER CamouflageDomain
REALITY SNI camouflage domain (forwards --camouflage-domain).

.PARAMETER LogLevel
Controls output verbosity.
Forwards to the bash script and Ansible.

Allowed values:
  None     - suppress all output except fatal errors.
  Default  - show banner and essential progress messages.
  Verbose  - enable maximum tracing; forwards to bash as --verbose.

Defaults to Default.

.EXAMPLE
.\Provision-VPN.ps1 -HostName 1.2.3.4 -PKey C:\Keys\id_rsa

.EXAMPLE
.\Provision-VPN.ps1 -HostName vps.example.com -User root -Pass 'secret' `
    -ClientsDir C:\Users\Tim\Desktop\vpn-clients

.EXAMPLE
.\Provision-VPN.ps1 -HostName 1.2.3.4 -User root
# prompts for SSH password interactively with hidden input

.EXAMPLE
.\Provision-VPN.ps1 -UseInventory -CleanupMode Full
# Uses pre-filled inventory.yml, removes packages after run

.EXAMPLE
.\Provision-VPN.ps1 -Inventory C:\Keys\my-vps-inventory.yml
# Uses an explicit inventory file (any location), same mode as -UseInventory

.EXAMPLE
.\Provision-VPN.ps1 -HostName 1.2.3.4 -User root -DryRun -LogLevel Verbose
# dry run with full verbose output, no system changes
#>

[CmdletBinding()]
param(
    [Parameter()]
    [switch]$UseInventory,

    [Parameter()]
    [Alias('I')]
    [string]$Inventory,

    [Parameter()]
    [Alias('H')]
    [string]$HostName,

    [Parameter()]
    [Alias('u')]
    [string]$User = 'root',

    [Parameter()]
    [Alias('p')]
    [int]$Port = 22,

    [Parameter()]
    [string]$ClientsDir,

    [Parameter()]
    [ValidateSet('Default', 'Full', 'None')]
    [string]$CleanupMode = 'Default',

    [Parameter()]
    [string]$PKey,

    [Parameter()]
    [string]$Pass,

    [Parameter()]
    [switch]$DryRun,

    [Parameter()]
    [switch]$Rotate,

    [Parameter()]
    [switch]$NoRotate,

    [Parameter()]
    [ValidateSet('native', 'docker')]
    [string]$Runtime,

    [Parameter()]
    [switch]$Warp,

    [Parameter()]
    [switch]$NoWarp,

    [Parameter()]
    [ValidateRange(1, 65535)]
    [int]$XrayPort,

    [Parameter()]
    [ValidateRange(1, 999)]
    [int]$NumClients,

    [Parameter()]
    [string]$CamouflageDomain,

    [Parameter()]
    [ValidateSet('None', 'Default', 'Verbose')]
    [string]$LogLevel = 'Default'
)

$boxWidth = 60
$title = "Xray VPN Provisioning Wrapper (Clash Verge / FlClash / Amnezia)"
$version = 'v2026-09-04'
$license = 'AGPL-3.0 + commercial-use restriction'
$author = 'Tim Korelov'
$contact = 'https://korelov.dev'

function Write-LogDefault([string]$Message) {
    if ($LogLevel -in @('Default', 'Verbose')) {
        Write-Host $Message
    }
}

function Write-LogVerbose([string]$Message) {
    if ($LogLevel -eq 'Verbose') {
        Write-Host $Message -ForegroundColor DarkGray
    }
}

function Convert-ToWslPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $Path }
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $drive = $resolved.Substring(0,1).ToLower()
    $rest = $resolved.Substring(2) -replace '\\','/'
    return "/mnt/$drive$rest"
}

Write-LogDefault "+------------------------------------------------------------+"
Write-LogDefault ("| {0,-58} |" -f $title.PadLeft(($boxWidth + $title.Length) / 2).PadRight($boxWidth))
Write-LogDefault ("| {0,-58} |" -f "")
Write-LogDefault ("| Release: {0,-49} |" -f $version)
Write-LogDefault ("| Author:  {0,-49} |" -f $author)
Write-LogDefault ("| Contact: {0,-49} |" -f $contact)
Write-LogDefault ("| License: {0,-49} |" -f $license)
Write-LogDefault "+------------------------------------------------------------+"
Write-LogDefault ""
Write-LogDefault "Tip: Run 'Get-Help .\$(Split-Path -Leaf $MyInvocation.MyCommand.Path) -Full' for full documentation."
Write-LogDefault ""

if ($DryRun) {
    Write-LogDefault "[DryRun] Active: bash script will be executed with --dry-run inside WSL. No changes on the VPS."
    Write-LogVerbose "[DryRun] Local Windows paths are converted to WSL /mnt/<drive>/... paths in-process."
}

if ($UseInventory -and $Inventory) {
    throw "Parameters -UseInventory and -Inventory are mutually exclusive; use only one."
}

if ($Rotate -and $NoRotate) {
    throw "Parameters -Rotate and -NoRotate are mutually exclusive; use only one."
}
if ($Warp -and $NoWarp) {
    throw "Parameters -Warp and -NoWarp are mutually exclusive; use only one."
}
$inventoryMode = [bool]($UseInventory -or $Inventory)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)
$bashScriptPath = Join-Path $scriptDir '..\bash\provision-vpn.sh'

if ($UseInventory) {
    $personalInventory = Join-Path $repoRoot 'inventory.yml'
    if (-not (Test-Path -LiteralPath $personalInventory)) {
        throw "Inventory file not found: $personalInventory`n" +
              "Create it from the template and fill in your values:`n" +
              "  Copy-Item '$(Join-Path $repoRoot 'inventory.yml.example')' '$personalInventory'`n" +
              "(ansible_host, ansible_user, ansible_port and ONE auth method)`n" +
              "Or point to your own file with -Inventory <path>."
    }
}
if ($Inventory -and -not (Test-Path -LiteralPath $Inventory)) {
    throw "Inventory file not found: $Inventory`n" +
          "Create one from the template: Copy-Item '$(Join-Path $repoRoot 'inventory.yml.example')' '<your-inventory.yml>'`n" +
          "or pass an existing path to -Inventory."
}

if ($inventoryMode) {
    Write-LogDefault "Mode: Using inventory file for parameters$(if ($Inventory) { ": $Inventory" } else { " (inventory.yml)" })"
    Write-LogVerbose "Inventory mode active; CLI connection/auth parameters will be ignored."
    if ($HostName -or $User -ne 'root' -or $Port -ne 22 -or $PKey -or $Pass) {
        Write-Host "Warning: inventory mode; ignoring CLI connection/auth parameters (-HostName, -User, -Port, -PKey, -Pass)." -ForegroundColor Yellow
    }
} else {
    Write-LogDefault "Mode: Using CLI parameters"
    Write-LogVerbose "Inputs: Host=$HostName User=$User Port=$Port CleanupMode=$CleanupMode LogLevel=$LogLevel"
    if (-not $HostName) {
        throw "Parameter -HostName is required in CLI mode. Use -UseInventory to use inventory.yml instead."
    }
}

if (-not $inventoryMode) {
    if ($PKey -and $Pass) {
        throw "Parameters -PKey and -Pass are mutually exclusive; use only one."
    }

    Write-LogVerbose "Auth: PKeyProvided=$([bool]$PKey) PassProvided=$([bool]$Pass)"

    if (-not $DryRun) {
        if (-not $PKey -and -not $Pass) {
            $secure = Read-Host "Enter SSH password" -AsSecureString
            $Pass = [System.Net.NetworkCredential]::new('', $secure).Password
            Write-LogVerbose "Password obtained via interactive prompt."
        }
    } else {
        if (-not $PKey -and -not $Pass) {
            Write-LogDefault "[DryRun] No -PKey or -Pass provided. In a real run, script would prompt for hidden SSH password."
        }
    }
}

switch ($CleanupMode) {
    'Default' { $cleanupFlag = '--cleanup' }
    'Full' { $cleanupFlag = '--full-cleanup' }
    'None' { $cleanupFlag = '--no-cleanup' }
    default { throw "Unknown CleanupMode '$CleanupMode'." }
}

Write-LogVerbose "CleanupMode '$CleanupMode' mapped to bash flag '$cleanupFlag'."

Write-LogVerbose "Script directory (Windows): $scriptDir"
Write-LogVerbose "Bash script path (Windows): $bashScriptPath"

$wslScriptPath = Convert-ToWslPath $bashScriptPath
Write-LogVerbose "Bash script path (WSL): $wslScriptPath"

$wslArgs = @($cleanupFlag)

switch ($LogLevel) {
    'None' { }
    'Default' { }
    'Verbose' {
        $wslArgs += '--verbose'
        Write-LogVerbose "Passing verbosity flag to bash: --verbose"
    }
}

if ($Rotate) {
    $wslArgs += '--rotate'
    Write-LogVerbose "Passing rotation flag to bash: --rotate"
} elseif ($NoRotate) {
    $wslArgs += '--no-rotate'
    Write-LogVerbose "Passing rotation flag to bash: --no-rotate"
}

if ($Runtime) {
    $wslArgs += @('--runtime', $Runtime)
    Write-LogVerbose "Passing runtime flag to bash: --runtime $Runtime"
}
if ($Warp) {
    $wslArgs += '--warp'
    Write-LogVerbose "Passing warp flag to bash: --warp"
} elseif ($NoWarp) {
    $wslArgs += '--no-warp'
    Write-LogVerbose "Passing warp flag to bash: --no-warp"
}
if ($PSBoundParameters.ContainsKey('XrayPort')) {
    $wslArgs += @('--xray-port', $XrayPort)
    Write-LogVerbose "Passing port override to bash: --xray-port $XrayPort"
}
if ($PSBoundParameters.ContainsKey('NumClients')) {
    $wslArgs += @('--num-clients', $NumClients)
    Write-LogVerbose "Passing client count to bash: --num-clients $NumClients"
}
if ($CamouflageDomain) {
    $wslArgs += @('--camouflage-domain', $CamouflageDomain)
    Write-LogVerbose "Passing camouflage domain to bash: --camouflage-domain $CamouflageDomain"
}

if ($Inventory) {
    $wslInventoryPath = Convert-ToWslPath $Inventory
    $wslArgs += @('--inventory', $wslInventoryPath)
    Write-LogVerbose "Inventory (Windows): $Inventory"
    Write-LogVerbose "Inventory (WSL): $wslInventoryPath"
} elseif ($UseInventory) {
    $wslArgs += '--use-inventory'
} else {
    $wslArgs += @(
        '--host', $HostName
        '--user', $User
        '--port', $Port
    )
}

if ($ClientsDir) {
    $wslClientsDir = Convert-ToWslPath $ClientsDir
    $wslArgs += @('--clients-dir', $wslClientsDir)
    Write-LogVerbose "ClientsDir (Windows): $ClientsDir"
    Write-LogVerbose "ClientsDir (WSL): $wslClientsDir"
} else {
    $defaultClientsDir = Join-Path $repoRoot 'downloaded-clients'
    if (-not (Test-Path $defaultClientsDir)) {
        New-Item -ItemType Directory -Path $defaultClientsDir | Out-Null
        Write-LogVerbose "Created default clients directory: $defaultClientsDir"
    }

    $wslDefaultClientsDir = Convert-ToWslPath $defaultClientsDir
    $wslArgs += @('--clients-dir', $wslDefaultClientsDir)
    Write-LogVerbose "Using default ClientsDir (Windows): $defaultClientsDir"
    Write-LogVerbose "Using default ClientsDir (WSL): $wslDefaultClientsDir"
}

if (-not $inventoryMode) {
    if ($PKey) {
        $wslPKey = Convert-ToWslPath $PKey
        $wslArgs += @('--pkey', $wslPKey)
        Write-LogVerbose "PKey path (Windows): $PKey"
        Write-LogVerbose "PKey path (WSL): $wslPKey"
    }
    elseif ($Pass) {
        $wslArgs += @('--pass', $Pass)
        Write-LogVerbose "Using password authentication (password not logged)."
    }
}

Write-LogVerbose ("Final WSL args: " + ($wslArgs -join ' '))

if ($DryRun) {
    $wslArgs += '--dry-run'
}

if ($DryRun) {
    Write-LogDefault ""
    Write-LogDefault "[DryRun] Executing bash script in dry-run mode (safe, no changes made):"
    Write-LogDefault "  wsl chmod +x $wslScriptPath"
    Write-LogDefault "  wsl bash $wslScriptPath $($wslArgs -join ' ')"
    Write-LogVerbose ""
    Write-LogVerbose ("WSL args as array: " + ($wslArgs | ForEach-Object { "'$_'" }) -join ", ")
    Write-LogDefault ""
}

Write-LogVerbose "Ensuring bash script is executable..."
wsl chmod +x $wslScriptPath

Write-LogDefault "Running Ansible provisioning via WSL..."
wsl bash $wslScriptPath $wslArgs

$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    Write-Host "Error: Provisioning FAILED (Exit code: $exitCode)." -ForegroundColor Red
    exit $exitCode
}

Write-LogDefault "Provisioning script execution completed."