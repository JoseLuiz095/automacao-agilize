$ErrorActionPreference = 'Stop'
$Repo = 'JoseLuiz095/automacao-agilize'
$SetupName = 'AutomacaoAgilize-Setup.exe'
$ShaName = 'AutomacaoAgilize-Setup.exe.sha256'
$Api = "https://api.github.com/repos/$Repo"
$TempDir = Join-Path $env:LOCALAPPDATA 'AutomacaoAgilize\updates\bridge'
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null

function Get-GitHubTokenFromGCM {
    try {
        if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) { return '' }
        $oldInteractive = $env:GCM_INTERACTIVE
        $oldPrompt = $env:GIT_TERMINAL_PROMPT
        $env:GCM_INTERACTIVE = 'never'
        $env:GIT_TERMINAL_PROMPT = '0'
        try {
            $lines = "protocol=https`nhost=github.com`n`n" | & git.exe credential fill 2>$null
        } finally {
            $env:GCM_INTERACTIVE = $oldInteractive
            $env:GIT_TERMINAL_PROMPT = $oldPrompt
        }
        foreach ($line in $lines) {
            if ($line -like 'password=*') { return $line.Substring(9).Trim() }
        }
    } catch {}
    return ''
}

$Token = $env:AUTOMACAO_AGILIZE_GITHUB_TOKEN
if (-not $Token) { $Token = $env:GITHUB_TOKEN }
if (-not $Token) { $Token = Get-GitHubTokenFromGCM }

$Headers = @{
    'User-Agent' = 'AutomacaoAgilize-Bridge/0.8.1'
    'Accept' = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
}
if ($Token) { $Headers['Authorization'] = "Bearer $Token" }

Write-Host 'Consultando a ultima Release...' -ForegroundColor Cyan
try {
    $Release = Invoke-RestMethod -Uri "$Api/releases/latest" -Headers $Headers -Method Get
} catch {
    throw "Nao foi possivel consultar a Release. Publique primeiro a v0.8.1 pelo GitHub Actions. Detalhe: $($_.Exception.Message)"
}

$SetupAsset = $Release.assets | Where-Object { $_.name -eq $SetupName } | Select-Object -First 1
$ShaAsset = $Release.assets | Where-Object { $_.name -eq $ShaName } | Select-Object -First 1
if (-not $SetupAsset -or -not $ShaAsset) {
    throw "A Release $($Release.tag_name) ainda nao possui Setup.exe + SHA-256. Aguarde o GitHub Actions concluir."
}

$DownloadHeaders = @{
    'User-Agent' = 'AutomacaoAgilize-Bridge/0.8.1'
    'Accept' = 'application/octet-stream'
    'X-GitHub-Api-Version' = '2022-11-28'
}
if ($Token) { $DownloadHeaders['Authorization'] = "Bearer $Token" }

$SetupPath = Join-Path $TempDir $SetupName
$ShaPath = Join-Path $TempDir $ShaName
Write-Host "Baixando $($Release.tag_name)..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $SetupAsset.url -Headers $DownloadHeaders -OutFile $SetupPath -UseBasicParsing
Invoke-WebRequest -Uri $ShaAsset.url -Headers $DownloadHeaders -OutFile $ShaPath -UseBasicParsing

$ExpectedText = Get-Content -Raw $ShaPath
$Match = [regex]::Match($ExpectedText, '(?i)\b[0-9a-f]{64}\b')
if (-not $Match.Success) { throw 'SHA-256 publicado e invalido.' }
$Expected = $Match.Value.ToLowerInvariant()
$Actual = (Get-FileHash $SetupPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Expected -ne $Actual) { throw 'SHA-256 do instalador nao confere.' }

Write-Host 'SHA-256 confirmado.' -ForegroundColor Green
Write-Host 'Fechando a versao antiga e instalando...' -ForegroundColor Cyan
Get-Process AutomacaoAgilize -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 700
$Proc = Start-Process -FilePath $SetupPath -ArgumentList '/SP-','/VERYSILENT','/NORESTART','/CLOSEAPPLICATIONS' -PassThru -Wait
if ($Proc.ExitCode -ne 0) { throw "O instalador terminou com codigo $($Proc.ExitCode)." }

$Exe = Join-Path $env:LOCALAPPDATA 'Programs\AutomacaoAgilize\AutomacaoAgilize.exe'
if (Test-Path $Exe) {
    Start-Process -FilePath $Exe
}
Write-Host "Atualizacao concluida para $($Release.tag_name)." -ForegroundColor Green
