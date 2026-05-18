# =========================================================================================
# 🌀 JETWEB MESH - AUTOMATED GITHUB UPLOADER SCRIPT
# =========================================================================================
# This PowerShell script automates the publishing of your Sovereign Swarm Mesh and 
# JetWeb Time Machine codebase directly under your GitHub account: thealanphipps-del
#
# Run this script directly on your Windows host:
# Powershell -ExecutionPolicy Bypass -File .\publish_to_github.ps1
# =========================================================================================

$RepoPath = "\\wsl.localhost\Ubuntu\home\aellok\sovereign_mesh"
$TargetOrg = "thealanphipps-del"
$TargetRepo = "sovereign-mesh"
$RemoteUrlHttps = "https://github.com/$TargetOrg/$TargetRepo.git"
$RemoteUrlSsh = "git@github.com:$TargetOrg/$TargetRepo.git"

# Check if git is available in Windows. If not, route git operations through WSL engine!
$GitInstalled = $false
try {
    $null = Get-Command git -ErrorAction Stop
    $GitInstalled = $true
} catch {}

if (-not $GitInstalled) {
    Write-Host "[WSL DETECTED] 'git' is not found in Windows PATH." -ForegroundColor Yellow
    Write-Host "Executing all Git operations securely inside WSL Ubuntu container context..." -ForegroundColor Cyan
    Write-Host ""
    
    function git {
        wsl --cd /home/aellok/sovereign_mesh git $args
    }
}

Clear-Host
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "         🌀 JETWEB SWARM MESH - AUTOMATED GITHUB PUBLISHER           " -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verify path location
if (-not (Test-Path $RepoPath)) {
    Write-Host "[ERROR] Could not resolve WSL Repository path at: $RepoPath" -ForegroundColor Red
    Write-Host "Please ensure your Ubuntu WSL distribution is running." -ForegroundColor Yellow
    Exit
}

# 2. Enter repository context
Set-Location $RepoPath
Write-Host "[SYSTEM] Context switched to repository: $RepoPath" -ForegroundColor Green

# 3. Check for existing git setup
if (-not (Test-Path ".git")) {
    Write-Host "[SYSTEM] Initializing Git repository..." -ForegroundColor Yellow
    git init -b main
}

# 4. Check for GitHub CLI (gh.exe)
$GH_Installed = $false
try {
    $null = Get-Command gh -ErrorAction Stop
    $GH_Installed = $true
} catch {}

if ($GH_Installed) {
    Write-Host "[DETECTED] GitHub CLI (gh.exe) is installed on your Windows host!" -ForegroundColor Green
    Write-Host "We can automate the remote repository creation under '$TargetOrg'..." -ForegroundColor Cyan
    Write-Host ""
    $Choice = Read-Host "Would you like to automate creation and upload using GitHub CLI? (Y/N)"
    
    if ($Choice -eq 'Y' -or $Choice -eq 'y') {
        Write-Host "[SYSTEM] Running: gh repo create $TargetOrg/$TargetRepo --public --source=. --push" -ForegroundColor Cyan
        gh repo create "$TargetOrg/$TargetRepo" --public --source=. --push
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[SUCCESS] Repository created and pushed successfully under your account!" -ForegroundColor Green
            Write-Host "Visit: https://github.com/$TargetOrg/$TargetRepo" -ForegroundColor Green
            Exit
        } else {
            Write-Host "[WARNING] Automated CLI creation failed or returned an error." -ForegroundColor Yellow
            Write-Host "Falling back to standard manual push method..." -ForegroundColor Yellow
        }
    }
}

# 5. Standard Push Method
Write-Host "---------------------------------------------------------------------" -ForegroundColor Gray
Write-Host "                       STANDARD REMOTE PUSH                          " -ForegroundColor Gray
Write-Host "---------------------------------------------------------------------" -ForegroundColor Gray
Write-Host "Select your preferred git connection protocol:" -ForegroundColor White
Write-Host "  [1] HTTPS (Recommended if using Windows Git Credential Manager)"
Write-Host "  [2] SSH (Recommended if using registered SSH keys)"
Write-Host ""
$ProtoChoice = Read-Host "Select Protocol Option (1 or 2)"

if ($ProtoChoice -eq '2') {
    $TargetRemote = $RemoteUrlSsh
    Write-Host "[SYSTEM] Using SSH protocol: $TargetRemote" -ForegroundColor Cyan
} else {
    $TargetRemote = $RemoteUrlHttps
    Write-Host "[SYSTEM] Using HTTPS protocol: $TargetRemote" -ForegroundColor Cyan
}

# Add Remote Origin
$ExistingRemote = git remote get-url origin 2>$null
if ($ExistingRemote) {
    Write-Host "[SYSTEM] Updating existing remote origin to: $TargetRemote" -ForegroundColor Yellow
    git remote set-url origin $TargetRemote
} else {
    Write-Host "[SYSTEM] Registering remote origin to: $TargetRemote" -ForegroundColor Yellow
    git remote add origin $TargetRemote
}

Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Yellow
Write-Host "  ⚠️  ACTION REQUIRED:" -ForegroundColor Yellow
Write-Host "  Before pushing, please ensure you have created an empty repository" -ForegroundColor White
Write-Host "  named '$TargetRepo' under your GitHub account: $TargetOrg" -ForegroundColor White
Write-Host "  URL: https://github.com/new" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Yellow
Write-Host ""

$Confirm = Read-Host "Have you created the remote repository on GitHub? (Y/N)"
if ($Confirm -eq 'Y' -or $Confirm -eq 'y') {
    Write-Host "[SYSTEM] Staging and confirming commit..." -ForegroundColor Cyan
    git add .
    git commit -m "feat: Initial release of JetWeb Time Machine & Sovereign Swarm Mesh v2.0" 2>$null
    
    Write-Host "[SYSTEM] Pushing main branch to origin..." -ForegroundColor Cyan
    git push -u origin main
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] Sovereign Swarm Mesh is live on GitHub!" -ForegroundColor Green
        Write-Host "Visit: https://github.com/$TargetOrg/$TargetRepo" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Git push failed. Verify your network or credentials." -ForegroundColor Red
    }
} else {
    Write-Host "[ABORTED] Please run this script again once the repository is created." -ForegroundColor Yellow
}
