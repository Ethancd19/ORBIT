# attach_pico.ps1
# Automatically finds and attaches the Pico (RP2 Boot or normal mode) to WSL2

$PICO_BOOTSEL = "2e8a:0003"
$PICO_NORMAL = "2e8a:000a"


function Attach-PicoByVidPid($vidpid) {
    $output = usbipd list 2>&1
    $matches = $output | Select-String $vidpid
    if ($matches) {
        $line  = $matches[0].Line.Trim()
        $busid = ($line -split "\s+")[0].Trim()
        $state = ($line -split "\s+")[-1].Trim()

        Write-Host "[usbipd] Found Pico (${vidpid}) at busid $busid (state: $state)"

        if ($state -eq "Not shared") {
            Write-Host "[usbipd] Sharing $busid..."
            usbipd bind --busid $busid 2>&1 | Out-Null
        }

        Write-Host "[usbipd] Attaching $busid to WSL2..."
        $result = usbipd attach --wsl --busid $busid 2>&1

        if ($LASTEXITCODE -eq 0) {
            Write-Host "[usbipd] Successfully attached $busid."
            return $true
        } elseif ($result -match "already attached") {
            Write-Host "[usbipd] $busid is already attached to WSL2, continuing..."
            return $true
        } else {
            Write-Host "[usbipd] Attach failed: $result"
            return $false
        }
    }
    return $false
}

Write-Host "[usbipd] Scanning for Pico..."

if (-not (Attach-PicoByVidPid $PICO_BOOTSEL)) {
    if (-not (Attach-PicoByVidPid $PICO_NORMAL)) {
        Write-Host "[usbipd] No Pico found. Is it plugged in?"
        exit 1
    }
}