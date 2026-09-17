#requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Resume,

    [Parameter()]
    [string]$Workspace,

    [Parameter()]
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:TutorVersion = '13'
$script:Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $script:Utf8NoBom
[Console]::OutputEncoding = $script:Utf8NoBom
$OutputEncoding = $script:Utf8NoBom
$script:WorkspaceWasExplicit = -not [string]::IsNullOrWhiteSpace($Workspace)

# ===========================================================================
# 0. Utility di base
# ===========================================================================

function Write-Title {
    param([Parameter(Mandatory)][string]$Text)

    Write-Host ''
    Write-Host ('=' * 78) -ForegroundColor DarkGray
    Write-Host $Text -ForegroundColor Green
    Write-Host ('=' * 78) -ForegroundColor DarkGray
}

function Write-Why {
    param(
        [Parameter(Mandatory)][string]$What,
        [Parameter(Mandatory)][string]$Why,
        [Parameter(Mandatory)][string]$Expected
    )

    Write-Host ''
    Write-Host 'COSA STAI FACENDO' -ForegroundColor Cyan
    Write-Host $What
    Write-Host ''
    Write-Host "PERCHE'" -ForegroundColor Cyan
    Write-Host $Why
    Write-Host ''
    Write-Host 'COSA DEVI ASPETTARTI' -ForegroundColor Cyan
    Write-Host $Expected
}

function Find-RepositoryRoot {
    param([Parameter(Mandatory)][string]$Start)

    $cursor = [System.IO.DirectoryInfo]::new([System.IO.Path]::GetFullPath($Start))
    while ($null -ne $cursor) {
        $agents = Join-Path $cursor.FullName 'AGENTS.md'
        $project = Join-Path $cursor.FullName 'pyproject.toml'
        $config = Join-Path $cursor.FullName '.codex\config.toml'

        if (
            (Test-Path -LiteralPath $agents -PathType Leaf) -and
            (Test-Path -LiteralPath $project -PathType Leaf) -and
            (Test-Path -LiteralPath $config -PathType Leaf)
        ) {
            return $cursor.FullName
        }

        $cursor = $cursor.Parent
    }

    throw @"
Non riesco a trovare la root di dsl_manager-v1.

Lo script deve stare dentro il repository e deve poter risalire fino a una
cartella che contenga:
  - AGENTS.md
  - pyproject.toml
  - .codex\config.toml
"@
}

function Resolve-ProjectPython {
    param([Parameter(Mandatory)][string]$RepositoryRoot)

    $configPath = Join-Path $RepositoryRoot '.codex\config.toml'
    $text = [System.IO.File]::ReadAllText($configPath, [System.Text.Encoding]::UTF8)
    $match = [regex]::Match(
        $text,
        '(?m)^\s*PROJECT_PYTHON\s*=\s*"([^"]+)"\s*$'
    )

    if (-not $match.Success) {
        throw "PROJECT_PYTHON non e' dichiarato in $configPath"
    }

    $configured = $match.Groups[1].Value
    if ([System.IO.Path]::IsPathRooted($configured)) {
        $candidate = $configured
    }
    else {
        $candidate = Join-Path $RepositoryRoot $configured
    }

    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw "L'interprete configurato non esiste: $candidate"
    }

    $resolved = (Resolve-Path -LiteralPath $candidate).Path
    $versionText = (& $resolved --version 2>&1) -join ' '
    if ($LASTEXITCODE -ne 0) {
        throw "L'interprete configurato non parte: $resolved"
    }

    if ($versionText -notmatch '^Python 3\.12(?:\.|\s|$)') {
        throw @"
Vega richiede l'ambiente Python 3.12 del progetto.
Interprete: $resolved
Risposta:   $versionText
"@
    }

    return $resolved
}

function ConvertTo-NativeProcessArgument {
    param([Parameter(Mandatory)][AllowEmptyString()][string]$Argument)

    if ($Argument.Length -gt 0 -and $Argument -notmatch '[\s"]') {
        return $Argument
    }

    $escaped = [regex]::Replace($Argument, '(\\*)"', '$1$1\"')
    $escaped = [regex]::Replace($escaped, '(\\+)$', '$1$1')
    return '"' + $escaped + '"'
}

function Format-CommandLine {
    param(
        [Parameter(Mandatory)][string]$File,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    $shown = foreach ($argument in $Arguments) {
        ConvertTo-NativeProcessArgument -Argument $argument
    }

    return ('"' + $File + '" ' + ($shown -join ' '))
}

function Get-HashMap {
    param([Parameter(Mandatory)][string]$Root)

    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw "Directory da hashare non trovata: $Root"
    }

    $map = [ordered]@{}
    foreach ($file in Get-ChildItem -LiteralPath $Root -Recurse -File | Sort-Object FullName) {
        $relative = $file.FullName.Substring($Root.Length + 1).Replace('\', '/')
        $map[$relative] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }

    return $map
}

function Assert-TreesIdentical {
    param(
        [Parameter(Mandatory)][string]$Left,
        [Parameter(Mandatory)][string]$Right
    )

    $leftMap = Get-HashMap -Root $Left
    $rightMap = Get-HashMap -Root $Right

    if (($leftMap | ConvertTo-Json -Compress) -ne ($rightMap | ConvertTo-Json -Compress)) {
        throw @"
Le due copie del corpus non sono byte-identiche.

SINISTRA: $Left
DESTRA:   $Right
"@
    }

    Write-Host "Integrita': $($leftMap.Count) file byte-identici." -ForegroundColor Green
}

# ===========================================================================
# 1. Repository e fixture Vega
# ===========================================================================

$script:RepositoryRoot = Find-RepositoryRoot -Start $PSScriptRoot
$script:ProjectPython = Resolve-ProjectPython -RepositoryRoot $script:RepositoryRoot
$script:LabRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$script:CanonicalCorpus = Join-Path $script:LabRoot 'corpus\active'
$script:ChecksumFile = Join-Path $PSScriptRoot 'checksums.json'
$script:ScenarioManifest = Join-Path $PSScriptRoot 'scenario_manifest.json'

$script:ExpectedFiles = @(
    'database/schema_vega.sql',
    'plsql/logica_vega.sql',
    'forms/frm_richiesta.xml',
    'logs/vega_2026.log',
    'documenti/manuale_operativo_vega_2026.docx',
    'documenti/matrice_priorita_vega_2026.xlsx'
)

function Test-CanonicalCorpus {
    foreach ($required in @(
        $script:CanonicalCorpus,
        $script:ChecksumFile,
        $script:ScenarioManifest
    )) {
        if (-not (Test-Path -LiteralPath $required)) {
            throw "File/directory essenziale del laboratorio assente: $required"
        }
    }

    $manifest = Get-Content -LiteralPath $script:ChecksumFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([int]$manifest.active_source_count -ne 6) {
        throw 'checksums.json non dichiara 6 fonti.'
    }

    foreach ($relative in $script:ExpectedFiles) {
        $path = Join-Path $script:CanonicalCorpus ($relative.Replace('/', '\'))
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Fonte canonica mancante: $relative"
        }
    }

    $actual = Get-HashMap -Root $script:CanonicalCorpus
    foreach ($property in $manifest.files.PSObject.Properties) {
        $relative = [string]$property.Name
        $expectedHash = ([string]$property.Value).ToLowerInvariant()

        if (-not $actual.Contains($relative)) {
            throw "Fonte dichiarata nei checksum ma assente: $relative"
        }
        if ([string]$actual[$relative] -ne $expectedHash) {
            throw "Checksum diverso per $relative"
        }
    }

    if ($actual.Count -ne 6) {
        throw "Il corpus contiene $($actual.Count) file, ma Vega v13 ne prevede esattamente 6."
    }

    return $true
}

if ($ValidateOnly) {
    $valid = Test-CanonicalCorpus
    [ordered]@{
        status = if ($valid) { 'valid' } else { 'invalid' }
        tutor_version = $script:TutorVersion
        repository_root = $script:RepositoryRoot
        project_python = $script:ProjectPython
        python_version = ((& $script:ProjectPython --version 2>&1) -join ' ')
        lab_root = $script:LabRoot
        active_source_count = 6
        docling_source_count = 2
        ai_selection_policies = @('technical_extraction', 'domain_interpretation')
    } | ConvertTo-Json -Depth 8
    exit 0
}

# ===========================================================================
# 2. Stato persistente
# ===========================================================================

function Get-SessionBase {
    $root = $env:LOCALAPPDATA
    if (-not $root) {
        $root = [System.IO.Path]::GetTempPath()
    }
    return Join-Path $root 'DSLManagerLabs\VegaRicambi'
}

function New-VegaSession {
    $sessionBase = Get-SessionBase
    if (-not (Test-Path -LiteralPath $sessionBase)) {
        $null = New-Item -ItemType Directory -Path $sessionBase -Force
    }

    $stamp = [DateTimeOffset]::Now.ToString('yyyyMMdd_HHmmss')
    $sessionRoot = Join-Path $sessionBase ("vega_v13_${stamp}_" + [guid]::NewGuid().ToString('N').Substring(0, 8))
    $null = New-Item -ItemType Directory -Path $sessionRoot
    $null = New-Item -ItemType Directory -Path (Join-Path $sessionRoot 'logs')
    $null = New-Item -ItemType Directory -Path (Join-Path $sessionRoot 'source_copy')

    if ($script:WorkspaceWasExplicit) {
        $defaultWorkspace = [Environment]::ExpandEnvironmentVariables($Workspace.Trim().Trim('"'))
    }
    else {
        $defaultWorkspace = Join-Path $sessionRoot 'workspace'
    }

    if (-not [System.IO.Path]::IsPathRooted($defaultWorkspace)) {
        throw '-Workspace deve essere un percorso assoluto.'
    }

    return [pscustomobject][ordered]@{
        schema_version = 4
        tutor_version = 13
        scenario = 'Laboratorio Vega Ricambi'
        session_root = [System.IO.Path]::GetFullPath($sessionRoot)
        state_path = [System.IO.Path]::GetFullPath((Join-Path $sessionRoot 'session_state.json'))
        workspace = [System.IO.Path]::GetFullPath($defaultWorkspace)
        workspace_was_explicit = $script:WorkspaceWasExplicit
        source_copy = [System.IO.Path]::GetFullPath((Join-Path $sessionRoot 'source_copy'))
        completed_actions = @()
        completed_steps = @()
        observed_ids = @()
        technical_plan_id = $null
        domain_plan_id = $null
        technical_package_id = $null
        domain_package_id = $null
        selected_package_ids = @()
        ai_imports = @()
        dsl_snapshot_id = $null
        last_run_id = $null
        command_counter = 0
        created_at = [DateTimeOffset]::Now.ToString('o')
        updated_at = [DateTimeOffset]::Now.ToString('o')
    }
}

function Ensure-StateProperty {
    param(
        [Parameter(Mandatory)]$State,
        [Parameter(Mandatory)][string]$Name,
        [Parameter()]$DefaultValue
    )

    if ($null -eq $State.PSObject.Properties[$Name]) {
        $State | Add-Member -MemberType NoteProperty -Name $Name -Value $DefaultValue
    }
}

function Import-VegaSession {
    param([Parameter(Mandatory)][string]$Path)

    $expanded = [Environment]::ExpandEnvironmentVariables($Path.Trim().Trim('"'))
    $resolved = [System.IO.Path]::GetFullPath($expanded)

    if (Test-Path -LiteralPath $resolved -PathType Container) {
        $resolved = Join-Path $resolved 'session_state.json'
    }
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "session_state.json non trovato: $resolved"
    }

    $state = Get-Content -LiteralPath $resolved -Raw -Encoding UTF8 | ConvertFrom-Json
    $stateVersion = [int]$state.schema_version

    if ($stateVersion -eq 3) {
        $advanced = @(
            @($state.completed_steps) |
            Where-Object { [int]$_ -ge 6 }
        )

        if ($advanced.Count -gt 0) {
            throw @"
Questa sessione appartiene alla v12 ed e' gia arrivata alla vecchia fase 6 o oltre.
La v13 cambia intenzionalmente l'ordine AI:

  import -> review -> merge -> reconcile -> DSL

Non posso rimappare automaticamente quei checkpoint senza rischiare di saltare
il merge AI. Crea una nuova sessione v13 oppure termina quella sessione con v12.
"@
        }

        Ensure-StateProperty -State $state -Name 'technical_package_id' -DefaultValue $null
        Ensure-StateProperty -State $state -Name 'domain_package_id' -DefaultValue $null
        Ensure-StateProperty -State $state -Name 'selected_package_ids' -DefaultValue @()
        Ensure-StateProperty -State $state -Name 'ai_imports' -DefaultValue @()
        Ensure-StateProperty -State $state -Name 'workspace_was_explicit' -DefaultValue $false

        if ($state.PSObject.Properties['package_id'] -and $state.package_id) {
            $state.domain_package_id = [string]$state.package_id
        }

        $state.schema_version = 4
        $state.tutor_version = 13
    }
    elseif ($stateVersion -ne 4) {
        throw "Versione di stato non supportata: $($state.schema_version)"
    }

    foreach ($name in @(
        'technical_plan_id',
        'domain_plan_id',
        'technical_package_id',
        'domain_package_id',
        'selected_package_ids',
        'ai_imports',
        'dsl_snapshot_id',
        'last_run_id',
        'command_counter',
        'workspace_was_explicit'
    )) {
        if ($name -in @('selected_package_ids', 'ai_imports')) {
            $default = @()
        }
        elseif ($name -eq 'command_counter') {
            $default = 0
        }
        elseif ($name -eq 'workspace_was_explicit') {
            $default = $false
        }
        else {
            $default = $null
        }

        Ensure-StateProperty -State $state -Name $name -DefaultValue $default
    }

    $actualSessionRoot = Split-Path -Parent $resolved
    $state.session_root = [System.IO.Path]::GetFullPath($actualSessionRoot)
    $state.state_path = [System.IO.Path]::GetFullPath($resolved)
    $state.source_copy = [System.IO.Path]::GetFullPath((Join-Path $actualSessionRoot 'source_copy'))

    if (-not (Test-Path -LiteralPath (Join-Path $actualSessionRoot 'logs'))) {
        $null = New-Item -ItemType Directory -Path (Join-Path $actualSessionRoot 'logs')
    }

    return $state
}

if ($Resume) {
    $script:State = Import-VegaSession -Path $Resume
}
else {
    $script:State = New-VegaSession
}

$script:StatePath = [string]$script:State.state_path
$script:LogsDir = Join-Path ([string]$script:State.session_root) 'logs'
$script:JournalPath = Join-Path ([string]$script:State.session_root) 'journal.md'
$script:CommandsPath = Join-Path $script:LogsDir 'commands.jsonl'

function Save-State {
    $script:State.updated_at = [DateTimeOffset]::Now.ToString('o')
    $json = $script:State | ConvertTo-Json -Depth 40
    $tmp = $script:StatePath + '.tmp.' + [guid]::NewGuid().ToString('N')

    [System.IO.File]::WriteAllText($tmp, $json + "`n", $script:Utf8NoBom)

    if (Test-Path -LiteralPath $script:StatePath -PathType Leaf) {
        try {
            [System.IO.File]::Replace($tmp, $script:StatePath, $null)
        }
        catch {
            Move-Item -LiteralPath $tmp -Destination $script:StatePath -Force
        }
    }
    else {
        Move-Item -LiteralPath $tmp -Destination $script:StatePath
    }
}

function Write-Journal {
    param([Parameter(Mandatory)][string]$Text)

    if (-not (Test-Path -LiteralPath $script:JournalPath)) {
        [System.IO.File]::WriteAllText(
            $script:JournalPath,
            "# Diario Laboratorio Vega Ricambi v13`n",
            $script:Utf8NoBom
        )
    }

    $entry = "`n## $([DateTimeOffset]::Now.ToString('o'))`n`n$Text`n"
    [System.IO.File]::AppendAllText($script:JournalPath, $entry, $script:Utf8NoBom)
}

function Test-ActionDone {
    param([Parameter(Mandatory)][string]$Action)
    return $Action -in @($script:State.completed_actions)
}

function Complete-Action {
    param([Parameter(Mandatory)][string]$Action)

    if (-not (Test-ActionDone -Action $Action)) {
        $script:State.completed_actions = @($script:State.completed_actions) + @($Action)
    }

    Write-Journal -Text "Checkpoint completato: $Action"
    Save-State
}

function Complete-Step {
    param([Parameter(Mandatory)][int]$Step)

    $key = [string]$Step
    if ($key -notin @($script:State.completed_steps)) {
        $script:State.completed_steps = @($script:State.completed_steps) + @($key)
    }

    Write-Journal -Text "Fase completata: $Step"
    Save-State
}

function Set-WorkspacePath {
    param([Parameter(Mandatory)][string]$NewPath)

    if (Test-ActionDone -Action 'setup.init') {
        throw "Il workspace e' gia stato inizializzato: crea una nuova sessione per cambiarlo."
    }

    $expanded = [Environment]::ExpandEnvironmentVariables($NewPath.Trim().Trim('"'))
    if (-not [System.IO.Path]::IsPathRooted($expanded)) {
        throw 'Inserisci un percorso assoluto.'
    }

    $script:State.workspace = [System.IO.Path]::GetFullPath($expanded)
    $script:State.workspace_was_explicit = $true
    Save-State
}

if ($Resume -and $Workspace) {
    $requested = [System.IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Workspace.Trim().Trim('"'))
    )

    if ($requested -ne [string]$script:State.workspace) {
        Set-WorkspacePath -NewPath $requested
    }
}

Save-State

# ===========================================================================
# 3. Logging dei processi
# ===========================================================================

function Get-SafeSlug {
    param([Parameter(Mandatory)][string]$Text)

    $slug = [regex]::Replace($Text.ToLowerInvariant(), '[^a-z0-9]+', '_').Trim('_')
    if (-not $slug) {
        $slug = 'command'
    }
    if ($slug.Length -gt 48) {
        $slug = $slug.Substring(0, 48)
    }

    return $slug
}

function Add-ObservedIds {
    param([Parameter(Mandatory)][AllowEmptyString()][string]$Text)

    foreach ($match in [regex]::Matches(
        $Text,
        '(?<![A-Z])(RUN|REV|AISEL|AIPKG|CBATCH|CREC|DSL)_\d{6}'
    )) {
        $value = $match.Value

        if ($value -notin @($script:State.observed_ids)) {
            $script:State.observed_ids = @($script:State.observed_ids) + @($value)
        }

        if ($match.Groups[1].Value -eq 'RUN') {
            $script:State.last_run_id = $value
        }
        if ($match.Groups[1].Value -eq 'DSL') {
            $script:State.dsl_snapshot_id = $value
        }
    }

    Save-State
}

function Show-UsefulTail {
    param(
        [Parameter(Mandatory)][AllowEmptyString()][string]$Text,
        [int]$MaxLines = 8
    )

    $lines = @(
        $Text -split "`r?`n" |
        Where-Object { $_.Trim() } |
        Select-Object -Last $MaxLines
    )

    foreach ($line in $lines) {
        $shown = $line.Trim()
        if ($shown.Length -gt 180) {
            $shown = $shown.Substring(0, 177) + '...'
        }
        Write-Host "  $shown"
    }
}

function Show-CompactStdout {
    param(
        [Parameter(Mandatory)][AllowEmptyString()][string]$Text,
        [Parameter(Mandatory)][string]$StdoutPath
    )

    $trimmed = $Text.Trim()
    if (-not $trimmed) {
        Write-Host 'Output: nessun stdout.' -ForegroundColor DarkGray
        return
    }

    $scanMatches = [regex]::Matches(
        $trimmed,
        '(?m)^(Added|Modified|Deleted|Unchanged):\s*(\d+)\s*$'
    )
    if ($scanMatches.Count -gt 0) {
        foreach ($m in $scanMatches) {
            Write-Host ("{0}: {1}" -f $m.Groups[1].Value, $m.Groups[2].Value)
        }
        return
    }

    try {
        $obj = $trimmed | ConvertFrom-Json

        foreach ($name in @(
            'run_id',
            'status',
            'exit_code',
            'batch_command',
            'selection_plan_id',
            'package_id',
            'snapshot_id',
            'dsl_snapshot_id',
            'config_hash',
            'count'
        )) {
            $prop = $obj.PSObject.Properties[$name]
            if ($null -ne $prop -and $null -ne $prop.Value -and [string]$prop.Value) {
                Write-Host ("{0}: {1}" -f $name, [string]$prop.Value)
            }
        }

        if ($obj.PSObject.Properties['summary'] -and $null -ne $obj.summary) {
            Write-Host ('summary: ' + ($obj.summary | ConvertTo-Json -Compress -Depth 8))
        }
        if ($obj.PSObject.Properties['candidates']) {
            Write-Host ('candidates: ' + @($obj.candidates).Count)
        }
        return
    }
    catch {
        # Non e' JSON: mostro soltanto la coda utile.
    }

    Show-UsefulTail -Text $trimmed -MaxLines 6
    Write-Host "Output completo: $StdoutPath" -ForegroundColor DarkGray
}

function Invoke-LoggedProcess {
    param(
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][string]$File,
        [Parameter(Mandatory)][string[]]$Arguments,
        [switch]$LongRunning
    )

    $script:State.command_counter = [int]$script:State.command_counter + 1
    Save-State

    $number = '{0:D3}' -f [int]$script:State.command_counter
    $slug = Get-SafeSlug -Text $Label
    $stdoutPath = Join-Path $script:LogsDir "${number}_${slug}.stdout.log"
    $stderrPath = Join-Path $script:LogsDir "${number}_${slug}.stderr.log"
    $commandLine = Format-CommandLine -File $File -Arguments $Arguments

    Write-Host ''
    Write-Host "[$number] $Label" -ForegroundColor Cyan
    Write-Host "Comando: $commandLine" -ForegroundColor DarkGray

    $started = [DateTimeOffset]::Now

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $File
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = $script:Utf8NoBom
    $psi.StandardErrorEncoding = $script:Utf8NoBom

    if ($null -ne $psi.PSObject.Properties['ArgumentList']) {
        foreach ($argument in $Arguments) {
            $null = $psi.ArgumentList.Add($argument)
        }
    }
    else {
        $psi.Arguments = (
            $Arguments |
            ForEach-Object { ConvertTo-NativeProcessArgument -Argument $_ }
        ) -join ' '
    }

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    $null = $process.Start()

    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $nextHeartbeat = 15

    while (-not $process.HasExited) {
        Start-Sleep -Milliseconds 250

        if ($LongRunning) {
            $elapsed = [int]([DateTimeOffset]::Now - $started).TotalSeconds
            if ($elapsed -ge $nextHeartbeat) {
                Write-Host "Ancora in esecuzione... ${elapsed}s. L'output completo va nei log." -ForegroundColor DarkYellow
                $nextHeartbeat += 15
            }
        }
    }

    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    $finished = [DateTimeOffset]::Now
    $duration = $finished - $started

    [System.IO.File]::WriteAllText($stdoutPath, $stdout, $script:Utf8NoBom)
    [System.IO.File]::WriteAllText($stderrPath, $stderr, $script:Utf8NoBom)

    $record = [ordered]@{
        index = [int]$script:State.command_counter
        label = $Label
        started_at = $started.ToString('o')
        finished_at = $finished.ToString('o')
        duration_seconds = [math]::Round($duration.TotalSeconds, 3)
        command = $commandLine
        exit_code = [int]$process.ExitCode
        stdout_log = $stdoutPath
        stderr_log = $stderrPath
    } | ConvertTo-Json -Compress -Depth 8

    [System.IO.File]::AppendAllText(
        $script:CommandsPath,
        $record + "`n",
        $script:Utf8NoBom
    )

    Add-ObservedIds -Text ($stdout + "`n" + $stderr)

    Write-Journal -Text @"
Comando: $commandLine

- exit: $($process.ExitCode)
- durata: $([math]::Round($duration.TotalSeconds, 2)) s
- stdout: $stdoutPath
- stderr: $stderrPath
"@

    Write-Host "Exit code: $($process.ExitCode)"
    Write-Host ("Durata: {0:N1} s" -f $duration.TotalSeconds)

    if ($process.ExitCode -eq 0) {
        Show-CompactStdout -Text $stdout -StdoutPath $stdoutPath
    }
    else {
        Write-Host "Il comando NON e' terminato con successo." -ForegroundColor Yellow
        if ($stderr.Trim()) {
            Show-UsefulTail -Text $stderr -MaxLines 10
        }
        elseif ($stdout.Trim()) {
            Show-UsefulTail -Text $stdout -MaxLines 10
        }
    }

    Write-Host "stdout: $stdoutPath" -ForegroundColor DarkGray
    if ($stderr.Trim() -or $process.ExitCode -ne 0) {
        Write-Host "stderr: $stderrPath" -ForegroundColor DarkGray
    }

    return [pscustomobject]@{
        Label = $Label
        Command = $commandLine
        Stdout = $stdout
        Stderr = $stderr
        ExitCode = [int]$process.ExitCode
        Duration = $duration
        StdoutPath = $stdoutPath
        StderrPath = $stderrPath
    }
}

function Invoke-Dsl {
    param(
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][string[]]$Arguments,
        [switch]$LongRunning
    )

    return Invoke-LoggedProcess `
        -Label $Label `
        -File $script:ProjectPython `
        -Arguments (@('-m', 'dsl_mngr') + $Arguments) `
        -LongRunning:$LongRunning
}

function Require-Success {
    param(
        [Parameter(Mandatory)]$Result,
        [Parameter(Mandatory)][string]$Message
    )

    if ($Result.ExitCode -ne 0) {
        throw "$Message`nLeggi i log indicati sopra prima di ritentare."
    }
}

function Extract-FirstId {
    param(
        [Parameter(Mandatory)][AllowEmptyString()][string]$Text,
        [Parameter(Mandatory)][string]$Prefix
    )

    $m = [regex]::Match($Text, "(?<![A-Z])${Prefix}_\d{6}")
    if ($m.Success) {
        return $m.Value
    }
    return $null
}

function Extract-LastId {
    param(
        [Parameter(Mandatory)][AllowEmptyString()][string]$Text,
        [Parameter(Mandatory)][string]$Prefix
    )

    $matches = [regex]::Matches($Text, "(?<![A-Z])${Prefix}_\d{6}")
    if ($matches.Count -gt 0) {
        return $matches[$matches.Count - 1].Value
    }
    return $null
}

function Extract-LabeledInteger {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$Label
    )

    $m = [regex]::Match(
        $Text,
        '(?m)^' + [regex]::Escape($Label) + ':\s*(\d+)\s*$'
    )
    if ($m.Success) {
        return [int]$m.Groups[1].Value
    }
    return $null
}

function Assert-ScanCount {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][int]$Expected
    )

    $m = [regex]::Match($Text, "(?m)^${Name}:\s*(\d+)\s*$")
    if (-not $m.Success) {
        throw "Lo scan non contiene '${Name}: ...'."
    }

    $actual = [int]$m.Groups[1].Value
    if ($actual -ne $Expected) {
        throw "Scan inatteso: $Name=$actual, atteso $Expected."
    }
}

# ===========================================================================
# 4. Catalogo package/import AI
# ===========================================================================

function Get-AiPackageCatalog {
    $items = @()

    if ($script:State.technical_package_id) {
        $items += [pscustomobject]@{
            Policy = 'technical_extraction'
            PlanId = [string]$script:State.technical_plan_id
            PackageId = [string]$script:State.technical_package_id
        }
    }

    if ($script:State.domain_package_id) {
        $items += [pscustomobject]@{
            Policy = 'domain_interpretation'
            PlanId = [string]$script:State.domain_plan_id
            PackageId = [string]$script:State.domain_package_id
        }
    }

    return @($items)
}

function Get-AiImportRecord {
    param([Parameter(Mandatory)][string]$PackageId)

    return @(
        @($script:State.ai_imports) |
        Where-Object { [string]$_.package_id -eq $PackageId }
    ) | Select-Object -First 1
}

function Set-AiImportRecord {
    param([Parameter(Mandatory)]$Record)

    $remaining = @(
        @($script:State.ai_imports) |
        Where-Object { [string]$_.package_id -ne [string]$Record.package_id }
    )

    $script:State.ai_imports = @($remaining) + @($Record)
    Save-State
}

function Get-SelectedAiPackages {
    $selected = @($script:State.selected_package_ids)
    return @(
        Get-AiPackageCatalog |
        Where-Object { $_.PackageId -in $selected }
    )
}

# ===========================================================================
# 5. Handoff AI e validazione locale del JSONL
# ===========================================================================

function Get-JsonPropertyValue {
    param(
        [Parameter(Mandatory)]$Object,
        [Parameter(Mandatory)][string]$Name
    )

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }
    return $property.Value
}

function Test-MissingJsonValue {
    param([Parameter()]$Value)

    if ($null -eq $Value) {
        return $true
    }
    if ($Value -is [string] -and -not $Value.Trim()) {
        return $true
    }
    return $false
}

function Test-UnresolvedSemanticPlaceholder {
    param([Parameter()]$Value)

    if ($null -eq $Value) {
        return $false
    }

    if ($Value -is [string]) {
        $text = [string]$Value
    }
    else {
        $text = $Value | ConvertTo-Json -Compress -Depth 20
    }

    return [regex]::IsMatch(
        $text,
        '(?i)(\$\{[^{}]+\}|\{\{[^{}]+\}\}|\bREPLACE_[A-Z0-9_]+\b|^\s*(PLACEHOLDER|TBD|TODO)\s*$|<<[^<>]+>>)'
    )
}

function Test-EvidenceTextInPackageSection {
    param(
        [Parameter(Mandatory)][string]$Content,
        [Parameter(Mandatory)][string]$EvidenceId,
        [Parameter(Mandatory)][string]$EvidenceText
    )

    if (-not $EvidenceId -or -not $EvidenceText) {
        return $false
    }

    $header = "## Evidence $EvidenceId"
    $start = $Content.IndexOf($header, [System.StringComparison]::Ordinal)
    if ($start -lt 0) {
        return $false
    }

    $next = $Content.IndexOf(
        '## Evidence ',
        $start + $header.Length,
        [System.StringComparison]::Ordinal
    )

    if ($next -lt 0) {
        $section = $Content.Substring($start)
    }
    else {
        $section = $Content.Substring($start, $next - $start)
    }

    return ($section.IndexOf($EvidenceText, [System.StringComparison]::Ordinal) -ge 0)
}

function Write-AiHumanHandoffKit {
    param(
        [Parameter(Mandatory)][string]$WorkspacePath,
        [Parameter(Mandatory)][string]$PackageId,
        [Parameter(Mandatory)][string]$Policy
    )

    $packageDir = Join-Path $WorkspacePath ("ai\outbox\" + $PackageId)
    if (-not (Test-Path -LiteralPath $packageDir -PathType Container)) {
        throw "Directory package non trovata: $packageDir"
    }

    foreach ($name in @(
        'instructions.md',
        'content.md',
        'source_manifest.json',
        'candidate_schema.json',
        'output_template.jsonl',
        'package_manifest.json'
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $packageDir $name) -PathType Leaf)) {
            throw "Package $PackageId incompleto: manca $name"
        }
    }

    $kitDir = Join-Path ([string]$script:State.session_root) ("ai_handoff\" + $PackageId)
    $null = New-Item -ItemType Directory -Path $kitDir -Force

    $promptPath = Join-Path $kitDir 'PROMPT_PER_QUALSIASI_AI.txt'
    $templatePath = Join-Path $kitDir 'OUTPUT_TEMPLATE_ORIGINALE.jsonl'
    Copy-Item `
        -LiteralPath (Join-Path $packageDir 'output_template.jsonl') `
        -Destination $templatePath `
        -Force

    $expectedName = "${PackageId}_candidates.jsonl"
    $expectedInbox = Join-Path $WorkspacePath ("ai\inbox\" + $expectedName)
    $officialTemplate = [System.IO.File]::ReadAllText(
        (Join-Path $packageDir 'output_template.jsonl'),
        [System.Text.Encoding]::UTF8
    ).Trim()

    $prompt = @"
DSL MANAGER - STRICT AI HANDOFF CONTRACT
Package: $PackageId
Selection policy: $Policy
Desired output filename: $expectedName

ROLE
You are an external semantic extraction engine. The attached DSL Manager package is
READ-ONLY evidence. Do not modify or reinterpret its identifiers.

FILES TO READ
1. instructions.md
2. content.md
3. candidate_schema.json
4. source_manifest.json
5. output_template.jsonl
6. selection_plan.json if present
7. package_manifest.json only for package metadata

TASK
Produce only candidate records genuinely supported by evidence in content.md.
Follow candidate_schema.json and instructions.md.

ABSOLUTE JSONL RULES
- EXACTLY one complete JSON object per physical line.
- Never return a JSON array.
- Never use Markdown code fences.
- Never add prose, headings, comments or filename lines.
- Each non-empty line starts with { and ends with }.
- candidate_id values must be unique inside this response.
- Never leave REPLACE_*, PLACEHOLDER, TBD, TODO or template markers.
- output_template.jsonl is a SHAPE EXAMPLE only.

ABSOLUTE EVIDENCE RULES
- Copy source_revision_id, chunk_id and fragment_id EXACTLY from this package.
- evidence_text must be copied VERBATIM as one contiguous substring from the
  referenced Evidence section in content.md.
- Do not normalize whitespace, punctuation, Markdown tables or identifiers.
- If exact evidence cannot be cited, OMIT the candidate.

SEMANTIC RULES
- Use only record_type, assertion_type and confidence values allowed by
  candidate_schema.json.
- Fill every record-specific required field.
- Prefer fewer defensible candidates over speculative candidates.

MANDATORY SELF-CHECK
Before answering, parse each output line independently as JSON, verify required
fields and IDs, and verify every evidence_text against content.md.

OUTPUT
If your interface can create files, create exactly:
$expectedName

Otherwise answer with raw JSONL only.

OFFICIAL PACKAGE TEMPLATE - STRUCTURE ONLY
----- BEGIN TEMPLATE -----
$officialTemplate
----- END TEMPLATE -----
"@

    [System.IO.File]::WriteAllText($promptPath, $prompt, $script:Utf8NoBom)

    return [pscustomobject]@{
        Policy = $Policy
        PackageId = $PackageId
        PackageDir = $packageDir
        KitDir = $kitDir
        PromptPath = $promptPath
        TemplatePath = $templatePath
        ExpectedInbox = $expectedInbox
        ExpectedName = $expectedName
    }
}

function Test-AiCandidateJsonl {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$PackageDir
    )

    $errors = @()
    $warnings = @()
    $objects = @()
    $candidateIds = @{}

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return [pscustomobject]@{
            Valid = $false
            RecordCount = 0
            Errors = @("File non trovato: $Path")
            Warnings = @()
            Objects = @()
        }
    }

    $schema = Get-Content `
        -LiteralPath (Join-Path $PackageDir 'candidate_schema.json') `
        -Raw `
        -Encoding UTF8 | ConvertFrom-Json

    $manifest = Get-Content `
        -LiteralPath (Join-Path $PackageDir 'source_manifest.json') `
        -Raw `
        -Encoding UTF8 | ConvertFrom-Json

    $content = [System.IO.File]::ReadAllText(
        (Join-Path $PackageDir 'content.md'),
        [System.Text.Encoding]::UTF8
    )

    $knownRevisions = @{}
    foreach ($item in @($manifest.source_revisions)) {
        $knownRevisions[[string]$item.source_revision_id] = $true
    }

    $knownChunks = @{}
    $chunkRevision = @{}
    foreach ($item in @($manifest.chunks)) {
        $chunkId = [string]$item.chunk_id
        $knownChunks[$chunkId] = $true
        $chunkRevision[$chunkId] = [string]$item.source_revision_id
    }

    $knownFragments = @{}
    $fragmentRevision = @{}
    foreach ($item in @($manifest.fragments)) {
        $fragmentId = [string]$item.fragment_id
        $knownFragments[$fragmentId] = $true
        $fragmentRevision[$fragmentId] = [string]$item.source_revision_id
    }

    $allowedAssertionTypes = @(
        $schema.properties.assertion_type.enum |
        ForEach-Object { [string]$_ }
    )
    $allowedConfidence = @(
        $schema.properties.confidence.enum |
        ForEach-Object { [string]$_ }
    )

    $lines = [System.IO.File]::ReadAllLines($Path, [System.Text.Encoding]::UTF8)
    $nonEmptyCount = 0

    for ($index = 0; $index -lt $lines.Length; $index++) {
        $lineNumber = $index + 1
        $line = [string]$lines[$index]

        if (-not $line.Trim()) {
            $warnings += "Riga $lineNumber vuota: ignorata."
            continue
        }

        $nonEmptyCount++
        $trimmed = $line.Trim()

        if ($trimmed.StartsWith('```')) {
            $errors += "Riga ${lineNumber}: code fence Markdown non ammesso."
            continue
        }
        if (-not $trimmed.StartsWith('{') -or -not $trimmed.EndsWith('}')) {
            $errors += "Riga ${lineNumber}: ogni record JSONL deve essere un oggetto su una sola riga."
            continue
        }

        try {
            $obj = $trimmed | ConvertFrom-Json -ErrorAction Stop
        }
        catch {
            $errors += "Riga ${lineNumber}: JSON non valido: $($_.Exception.Message)"
            continue
        }

        if ($obj -isnot [System.Management.Automation.PSCustomObject]) {
            $errors += "Riga ${lineNumber}: il valore JSON deve essere un oggetto."
            continue
        }

        $objects += $obj

        $candidateId = [string](Get-JsonPropertyValue -Object $obj -Name 'candidate_id')
        if (-not $candidateId) {
            $errors += "Riga ${lineNumber}: candidate_id mancante."
        }
        elseif ($candidateIds.ContainsKey($candidateId)) {
            $errors += "Riga ${lineNumber}: candidate_id duplicato: $candidateId"
        }
        else {
            $candidateIds[$candidateId] = $true
        }

        if ($candidateId -and (Test-UnresolvedSemanticPlaceholder -Value $candidateId)) {
            $errors += "Riga ${lineNumber}: candidate_id contiene un placeholder."
        }

        foreach ($requiredName in @($schema.common_required_fields)) {
            $value = Get-JsonPropertyValue -Object $obj -Name ([string]$requiredName)
            if (Test-MissingJsonValue -Value $value) {
                $errors += "Riga ${lineNumber}: campo obbligatorio mancante/vuoto: $requiredName"
            }
        }

        $recordType = [string](Get-JsonPropertyValue -Object $obj -Name 'record_type')
        if ($recordType -and $recordType -notin @($schema.allowed_record_types)) {
            $errors += "Riga ${lineNumber}: record_type non ammesso: $recordType"
        }

        $assertionType = [string](Get-JsonPropertyValue -Object $obj -Name 'assertion_type')
        if (
            $assertionType -and
            $allowedAssertionTypes.Count -gt 0 -and
            $assertionType -notin $allowedAssertionTypes
        ) {
            $errors += "Riga ${lineNumber}: assertion_type non ammesso: $assertionType"
        }

        $confidence = [string](Get-JsonPropertyValue -Object $obj -Name 'confidence')
        if (
            $confidence -and
            $allowedConfidence.Count -gt 0 -and
            $confidence -notin $allowedConfidence
        ) {
            $errors += "Riga ${lineNumber}: confidence non ammessa: $confidence"
        }

        $specific = @()
        if ($recordType) {
            $specificProperty = $schema.record_specific_required_fields.PSObject.Properties[$recordType]
            if ($null -ne $specificProperty) {
                $specific = @($specificProperty.Value)
            }
        }

        foreach ($requiredName in $specific) {
            $value = Get-JsonPropertyValue -Object $obj -Name ([string]$requiredName)
            if (Test-MissingJsonValue -Value $value) {
                $errors += "Riga ${lineNumber}: campo specifico mancante/vuoto: $requiredName"
            }
            elseif (Test-UnresolvedSemanticPlaceholder -Value $value) {
                $errors += "Riga ${lineNumber}: placeholder non risolto in $requiredName"
            }
        }

        $revisionId = [string](Get-JsonPropertyValue -Object $obj -Name 'source_revision_id')
        $chunkId = [string](Get-JsonPropertyValue -Object $obj -Name 'chunk_id')
        $fragmentId = [string](Get-JsonPropertyValue -Object $obj -Name 'fragment_id')

        if ($revisionId -and -not $knownRevisions.ContainsKey($revisionId)) {
            $errors += "Riga ${lineNumber}: source_revision_id non presente nel package: $revisionId"
        }
        if (-not $chunkId -and -not $fragmentId) {
            $errors += "Riga ${lineNumber}: serve almeno chunk_id oppure fragment_id."
        }
        if ($chunkId -and -not $knownChunks.ContainsKey($chunkId)) {
            $errors += "Riga ${lineNumber}: chunk_id non presente nel package: $chunkId"
        }
        if ($fragmentId -and -not $knownFragments.ContainsKey($fragmentId)) {
            $errors += "Riga ${lineNumber}: fragment_id non presente nel package: $fragmentId"
        }
        if (
            $revisionId -and
            $chunkId -and
            $knownChunks.ContainsKey($chunkId) -and
            [string]$chunkRevision[$chunkId] -ne $revisionId
        ) {
            $errors += "Riga ${lineNumber}: $chunkId non appartiene a $revisionId"
        }
        if (
            $revisionId -and
            $fragmentId -and
            $knownFragments.ContainsKey($fragmentId) -and
            [string]$fragmentRevision[$fragmentId] -ne $revisionId
        ) {
            $errors += "Riga ${lineNumber}: $fragmentId non appartiene a $revisionId"
        }

        $evidenceText = [string](Get-JsonPropertyValue -Object $obj -Name 'evidence_text')
        if (-not $evidenceText) {
            $errors += "Riga ${lineNumber}: evidence_text mancante/vuoto."
        }
        else {
            $found = $false

            if ($chunkId -and $knownChunks.ContainsKey($chunkId)) {
                $found = Test-EvidenceTextInPackageSection `
                    -Content $content `
                    -EvidenceId $chunkId `
                    -EvidenceText $evidenceText
            }

            if (-not $found -and $fragmentId -and $knownFragments.ContainsKey($fragmentId)) {
                $found = Test-EvidenceTextInPackageSection `
                    -Content $content `
                    -EvidenceId $fragmentId `
                    -EvidenceText $evidenceText
            }

            if (-not $found) {
                $errors += "Riga ${lineNumber}: evidence_text non e' una sottostringa letterale dell'evidenza referenziata."
            }
        }
    }

    if ($nonEmptyCount -eq 0) {
        $errors += 'Il file non contiene record JSONL.'
    }

    return [pscustomobject]@{
        Valid = ($errors.Count -eq 0)
        RecordCount = $objects.Count
        Errors = @($errors)
        Warnings = @($warnings)
        Objects = @($objects)
    }
}

function Write-CanonicalJsonl {
    param(
        [Parameter(Mandatory)]$Objects,
        [Parameter(Mandatory)][string]$Destination
    )

    $parent = Split-Path -Parent $Destination
    if (-not (Test-Path -LiteralPath $parent)) {
        $null = New-Item -ItemType Directory -Path $parent -Force
    }

    $lines = foreach ($obj in @($Objects)) {
        $obj | ConvertTo-Json -Compress -Depth 50
    }

    [System.IO.File]::WriteAllText(
        $Destination,
        (($lines -join "`n") + "`n"),
        $script:Utf8NoBom
    )
}

# ===========================================================================
# 6. Fasi 1-4: baseline deterministica
# ===========================================================================

function Invoke-Step1Preflight {
    Write-Title 'FASE 1/11 - Preflight'
    Write-Why `
        -What 'Controllo repository, Python 3.12, sei fonti canoniche e checksum.' `
        -Why "Se ambiente o fixture sono sbagliati, ogni errore successivo sarebbe ambiguo." `
        -Expected 'Nessuna mutazione; tutti i controlli verdi.'

    $null = Test-CanonicalCorpus

    Write-Host "Repository: $script:RepositoryRoot"
    Write-Host "Python:     $script:ProjectPython"
    Write-Host "Workspace:  $($script:State.workspace)"
    Write-Host 'Fonti:      6 (2 Docling)' -ForegroundColor Green

    Complete-Action -Action 'preflight.valid'
    Complete-Step -Step 1
}

function Invoke-Step2Setup {
    Write-Title 'FASE 2/11 - Workspace e governance'
    Write-Why `
        -What 'Inizializzo workspace/database, copio le fonti e applico conservative/1.' `
        -Why 'Il corpus canonico resta immutabile e la review automatica e versionata.' `
        -Expected 'Workspace pulito, fonti byte-identiche, config valida.'

    $workspacePath = [string]$script:State.workspace
    $sourceCopy = [string]$script:State.source_copy

    if (-not (Test-ActionDone -Action 'setup.init')) {
        if (Test-Path -LiteralPath $workspacePath) {
            if ([bool]$script:State.workspace_was_explicit) {
                throw @"
Il workspace esplicito esiste gia':
$workspacePath

Per sicurezza la v13 NON cancella directory esplicite. Scegli un percorso nuovo
con l'opzione W oppure crea/riprendi la sessione corretta.
"@
            }

            Write-Host 'Workspace interno di sessione gia presente: lo ricreo pulito.' -ForegroundColor Yellow
            Remove-Item -LiteralPath $workspacePath -Recurse -Force
        }

        $r = Invoke-Dsl -Label 'init workspace' -Arguments @('init', $workspacePath)
        Require-Success $r 'dsl_mngr init fallito.'
        Complete-Action -Action 'setup.init'
    }

    if (-not (Test-ActionDone -Action 'setup.db_init')) {
        $r = Invoke-Dsl -Label 'db init' -Arguments @('db', 'init', $workspacePath)
        Require-Success $r 'dsl_mngr db init fallito.'
        Complete-Action -Action 'setup.db_init'
    }

    if (-not (Test-ActionDone -Action 'setup.copy_sources')) {
        if (Test-Path -LiteralPath $sourceCopy) {
            Get-ChildItem -LiteralPath $sourceCopy -Force | Remove-Item -Recurse -Force
        }
        else {
            $null = New-Item -ItemType Directory -Path $sourceCopy
        }

        Copy-Item `
            -Path (Join-Path $script:CanonicalCorpus '*') `
            -Destination $sourceCopy `
            -Recurse

        Copy-Item `
            -Path (Join-Path $sourceCopy '*') `
            -Destination (Join-Path $workspacePath 'corpus\active') `
            -Recurse

        Assert-TreesIdentical `
            -Left $sourceCopy `
            -Right (Join-Path $workspacePath 'corpus\active')

        Complete-Action -Action 'setup.copy_sources'
    }
    else {
        Assert-TreesIdentical `
            -Left $sourceCopy `
            -Right (Join-Path $workspacePath 'corpus\active')
    }

    if (-not (Test-ActionDone -Action 'setup.review_profile')) {
        $show = Invoke-Dsl `
            -Label 'review show' `
            -Arguments @('config', 'review', 'show', $workspacePath)
        Require-Success $show 'Impossibile leggere la config review.'

        $configHash = $null
        try {
            $obj = $show.Stdout | ConvertFrom-Json
            if ($obj.config_hash -match '^[0-9a-fA-F]{64}$') {
                $configHash = [string]$obj.config_hash
            }
        }
        catch {
            $configHash = $null
        }

        $applyArgs = @(
            'config',
            'review',
            'apply-profile',
            $workspacePath,
            '--profile',
            'conservative/1'
        )
        if ($configHash) {
            $applyArgs += @('--expect-config-hash', $configHash)
        }

        $apply = Invoke-Dsl -Label 'apply conservative profile' -Arguments $applyArgs
        Require-Success $apply 'Applicazione conservative/1 fallita.'

        $validate = Invoke-Dsl `
            -Label 'config validate' `
            -Arguments @(
                'config',
                'validate',
                $workspacePath,
                '--profile',
                'conservative/1'
            )
        Require-Success $validate 'Configurazione non valida.'

        Complete-Action -Action 'setup.review_profile'
    }

    Complete-Step -Step 2
}

function Invoke-Step3Scans {
    Write-Title 'FASE 3/11 - Doppio scan'
    Write-Why `
        -What 'Registro le sei fonti e ripeto subito lo scan.' `
        -Why 'Il secondo passaggio verifica che byte invariati non producano revisioni spurie.' `
        -Expected 'Primo scan Added=6. Secondo scan Unchanged=6.'

    $workspacePath = [string]$script:State.workspace

    if (-not (Test-ActionDone -Action 'scan.first')) {
        $r = Invoke-Dsl -Label 'corpus scan 1' -Arguments @('corpus', 'scan', $workspacePath)
        Require-Success $r 'Primo scan fallito.'
        Assert-ScanCount -Text $r.Stdout -Name 'Added' -Expected 6
        Assert-ScanCount -Text $r.Stdout -Name 'Modified' -Expected 0
        Assert-ScanCount -Text $r.Stdout -Name 'Deleted' -Expected 0
        Complete-Action -Action 'scan.first'
    }

    if (-not (Test-ActionDone -Action 'scan.second')) {
        $r = Invoke-Dsl -Label 'corpus scan 2' -Arguments @('corpus', 'scan', $workspacePath)
        Require-Success $r 'Secondo scan fallito.'
        Assert-ScanCount -Text $r.Stdout -Name 'Unchanged' -Expected 6
        Assert-ScanCount -Text $r.Stdout -Name 'Added' -Expected 0
        Assert-ScanCount -Text $r.Stdout -Name 'Modified' -Expected 0
        Assert-ScanCount -Text $r.Stdout -Name 'Deleted' -Expected 0
        Complete-Action -Action 'scan.second'
    }

    Complete-Step -Step 3
}

function Invoke-Step4Consolidate {
    Write-Title 'FASE 4/11 - Consolidamento deterministico'
    Write-Why `
        -What 'Eseguo batch consolidate: parse, derive, review automatica, merge e reconcile.' `
        -Why 'Prima materializziamo quello che i parser strutturali sanno stabilire senza AI.' `
        -Expected 'Quattro parser strutturali, due documenti Docling e merge deterministico concluso.'

    if (-not (Test-ActionDone -Action 'consolidate.run')) {
        $r = Invoke-Dsl `
            -Label 'batch consolidate' `
            -Arguments @(
                'batch',
                'consolidate',
                [string]$script:State.workspace,
                '--reconcile'
            ) `
            -LongRunning

        Require-Success $r 'Consolidamento fallito.'
        Complete-Action -Action 'consolidate.run'
    }

    Complete-Step -Step 4
}

# ===========================================================================
# 7. Fasi AI: due piani, due package, scelta multipla
# ===========================================================================

function Invoke-Step5AiHandoff {
    Write-Title 'FASE 5/11 - Due piani AI, due package e scelta export'
    Write-Why `
        -What 'Creo i due AISEL di Vega e un AIPKG per ciascuno. Poi scegli tecnico, dominio o entrambi.' `
        -Why 'La v12 creava due piani ma impacchettava solo il piano di dominio. La v13 rende simmetrici i due percorsi.' `
        -Expected 'AISEL tecnico + AISEL dominio; AIPKG tecnico + AIPKG dominio; scelta persistente dei package da elaborare.'

    $workspacePath = [string]$script:State.workspace

    if (-not $script:State.technical_plan_id) {
        $r = Invoke-Dsl `
            -Label 'AI evidence technical plan' `
            -Arguments @(
                'ai',
                'evidence',
                'plan',
                $workspacePath,
                '--policy',
                'technical_extraction'
            )
        Require-Success $r 'Piano technical_extraction fallito.'

        $id = Extract-LastId -Text $r.Stdout -Prefix 'AISEL'
        if (-not $id) {
            throw 'AISEL tecnico non ricavabile.'
        }
        $script:State.technical_plan_id = $id
        Save-State
    }

    if (-not $script:State.domain_plan_id) {
        $r = Invoke-Dsl `
            -Label 'AI evidence domain plan' `
            -Arguments @(
                'ai',
                'evidence',
                'plan',
                $workspacePath,
                '--policy',
                'domain_interpretation'
            )
        Require-Success $r 'Piano domain_interpretation fallito.'

        $id = Extract-LastId -Text $r.Stdout -Prefix 'AISEL'
        if (-not $id) {
            throw 'AISEL dominio non ricavabile.'
        }
        $script:State.domain_plan_id = $id
        Save-State
    }

    if (-not $script:State.technical_package_id) {
        $r = Invoke-Dsl `
            -Label 'AI package technical' `
            -Arguments @(
                'ai',
                'package',
                $workspacePath,
                '--selection-plan',
                [string]$script:State.technical_plan_id
            )
        Require-Success $r 'Package tecnico fallito.'

        $id = Extract-LastId -Text $r.Stdout -Prefix 'AIPKG'
        if (-not $id) {
            throw 'AIPKG tecnico non ricavabile.'
        }
        $script:State.technical_package_id = $id
        Save-State
    }

    if (-not $script:State.domain_package_id) {
        $r = Invoke-Dsl `
            -Label 'AI package domain' `
            -Arguments @(
                'ai',
                'package',
                $workspacePath,
                '--selection-plan',
                [string]$script:State.domain_plan_id
            )
        Require-Success $r 'Package dominio fallito.'

        $id = Extract-LastId -Text $r.Stdout -Prefix 'AIPKG'
        if (-not $id) {
            throw 'AIPKG dominio non ricavabile.'
        }
        $script:State.domain_package_id = $id
        Save-State
    }

    Write-Host ''
    Write-Host 'PACKAGE DISPONIBILI' -ForegroundColor Cyan
    Write-Host "T - technical_extraction  -> $($script:State.technical_package_id)"
    Write-Host "D - domain_interpretation -> $($script:State.domain_package_id)"

    if (@($script:State.selected_package_ids).Count -eq 0) {
        Write-Host ''
        Write-Host 'Quali package vuoi portare al round-trip con AI esterne?' -ForegroundColor Yellow
        Write-Host '[Invio/A] TUTTI e due (default del test completo)'
        Write-Host '[T]       Solo technical_extraction'
        Write-Host '[D]       Solo domain_interpretation'
        Write-Host '[Q]       Torna al menu senza fissare la scelta'

        $choice = (Read-Host 'Scelta').Trim().ToUpperInvariant()
        if ($choice -eq 'Q') {
            return
        }

        if (-not $choice -or $choice -eq 'A') {
            $script:State.selected_package_ids = @(
                [string]$script:State.technical_package_id,
                [string]$script:State.domain_package_id
            )
        }
        elseif ($choice -eq 'T') {
            $script:State.selected_package_ids = @(
                [string]$script:State.technical_package_id
            )
        }
        elseif ($choice -eq 'D') {
            $script:State.selected_package_ids = @(
                [string]$script:State.domain_package_id
            )
        }
        else {
            Write-Host 'Scelta non valida; fase lasciata incompleta.' -ForegroundColor Yellow
            return
        }

        Save-State
    }

    Write-Host ''
    Write-Host 'HANDOFF SELEZIONATO' -ForegroundColor Green

    foreach ($pkg in Get-SelectedAiPackages) {
        $kit = Write-AiHumanHandoffKit `
            -WorkspacePath $workspacePath `
            -PackageId $pkg.PackageId `
            -Policy $pkg.Policy

        Write-Host ''
        Write-Host "$($pkg.Policy) / $($pkg.PackageId)" -ForegroundColor Cyan
        Write-Host "  package:      $($kit.PackageDir)"
        Write-Host "  prompt:       $($kit.PromptPath)"
        Write-Host "  output atteso: $($kit.ExpectedInbox)"
    }

    Complete-Action -Action 'ai.packages.selected'
    Complete-Step -Step 5
}

function Import-OneAiPackage {
    param([Parameter(Mandatory)]$Package)

    $workspacePath = [string]$script:State.workspace
    $packageId = [string]$Package.PackageId
    $existing = Get-AiImportRecord -PackageId $packageId

    if ($existing -and $existing.import_batch_id) {
        Write-Host "Gia importato: $packageId -> $($existing.import_batch_id)" -ForegroundColor Green
        return $true
    }

    $kit = Write-AiHumanHandoffKit `
        -WorkspacePath $workspacePath `
        -PackageId $packageId `
        -Policy $Package.Policy

    Write-Title "IMPORT $packageId ($($Package.Policy))"
    Write-Host "Package da dare alla AI: $($kit.PackageDir)"
    Write-Host "Prompt:                  $($kit.PromptPath)"
    Write-Host "Risposta standard:       $($kit.ExpectedInbox)"
    Write-Host ''
    Write-Host 'La AI deve produrre un JSONL separato per QUESTO package.' -ForegroundColor Yellow

    $candidateSource = $kit.ExpectedInbox

    if (-not (Test-Path -LiteralPath $candidateSource -PathType Leaf)) {
        $choice = (Read-Host 'Invio=ricontrolla standard; P=stampa prompt; Q=interrompi; oppure percorso assoluto del JSONL').Trim()

        if ($choice.ToUpperInvariant() -eq 'Q') {
            return $false
        }
        if ($choice.ToUpperInvariant() -eq 'P') {
            Get-Content -LiteralPath $kit.PromptPath -Encoding UTF8
            return $false
        }

        if ($choice) {
            $expanded = [Environment]::ExpandEnvironmentVariables($choice.Trim().Trim('"'))
            if (-not [System.IO.Path]::IsPathRooted($expanded)) {
                throw 'Il percorso JSONL deve essere assoluto.'
            }
            $candidateSource = [System.IO.Path]::GetFullPath($expanded)
        }
    }

    if (-not (Test-Path -LiteralPath $candidateSource -PathType Leaf)) {
        Write-Host "Risposta non presente per $packageId. La fase resta incompleta." -ForegroundColor Yellow
        return $false
    }

    Write-Host ''
    Write-Host 'Preflight locale della risposta AI...' -ForegroundColor Cyan

    $preflight = Test-AiCandidateJsonl `
        -Path $candidateSource `
        -PackageDir $kit.PackageDir

    foreach ($warning in @($preflight.Warnings)) {
        Write-Host "WARN: $warning" -ForegroundColor DarkYellow
    }

    if (-not $preflight.Valid) {
        $report = Join-Path $kit.KitDir 'PREFLIGHT_ERRORI.txt'
        [System.IO.File]::WriteAllLines(
            $report,
            [string[]]$preflight.Errors,
            $script:Utf8NoBom
        )

        Write-Host "RISPOSTA NON IMPORTATA: $packageId" -ForegroundColor Red
        foreach ($errorText in @($preflight.Errors | Select-Object -First 15)) {
            Write-Host "  - $errorText"
        }
        if (@($preflight.Errors).Count -gt 15) {
            Write-Host '  ... altri errori nel report.'
        }
        Write-Host "Report: $report"
        return $false
    }

    # Copia/canonicalizza sempre nella inbox standard del package. In questo modo
    # anche un file scelto da un percorso esterno viene importato con la convenzione
    # attesa da `ai import`.
    Write-CanonicalJsonl `
        -Objects $preflight.Objects `
        -Destination $kit.ExpectedInbox

    Write-Host "Preflight OK: $($preflight.RecordCount) record." -ForegroundColor Green

    $confirm = (Read-Host "Invio=importa $packageId; V=prime 5 righe; Q=non importare").Trim().ToUpperInvariant()
    if ($confirm -eq 'Q') {
        return $false
    }

    if ($confirm -eq 'V') {
        Get-Content -LiteralPath $kit.ExpectedInbox -Encoding UTF8 | Select-Object -First 5
        $confirmAfterView = (Read-Host 'Invio=importa; Q=annulla').Trim().ToUpperInvariant()
        if ($confirmAfterView -eq 'Q') {
            return $false
        }
    }

    $scan = Invoke-Dsl `
        -Label "AI inbox scan before $packageId" `
        -Arguments @('ai', 'inbox', 'scan', $workspacePath)
    Require-Success $scan 'AI inbox scan fallito.'

    $import = Invoke-Dsl `
        -Label "AI import $packageId" `
        -Arguments @(
            'ai',
            'import',
            $workspacePath,
            '--package',
            $packageId
        )
    Require-Success $import "Import $packageId fallito."

    $runId = Extract-LastId -Text $import.Stdout -Prefix 'RUN'
    $batchId = Extract-LastId -Text $import.Stdout -Prefix 'CBATCH'
    $total = Extract-LabeledInteger -Text $import.Stdout -Label 'Total'
    $accepted = Extract-LabeledInteger -Text $import.Stdout -Label 'Accepted'
    $rejected = Extract-LabeledInteger -Text $import.Stdout -Label 'Rejected'

    if (
        -not $runId -or
        -not $batchId -or
        $null -eq $total -or
        $null -eq $accepted -or
        $null -eq $rejected
    ) {
        throw "Import $packageId concluso ma RUN/CBATCH/conteggi non ricavabili."
    }

    if ($accepted -le 0) {
        throw @"
Import ${packageId}: nessun candidato accettato.
Total=$total Accepted=$accepted Rejected=$rejected

Il round-trip di questo package non e' dimostrato. Correggi la risposta invece
di reimportare alla cieca lo stesso file.
"@
    }

    Set-AiImportRecord -Record ([pscustomobject][ordered]@{
        package_id = $packageId
        policy = [string]$Package.Policy
        candidate_path = $kit.ExpectedInbox
        response_sha256 = (Get-FileHash -LiteralPath $kit.ExpectedInbox -Algorithm SHA256).Hash.ToLowerInvariant()
        import_run_id = $runId
        import_batch_id = $batchId
        total = $total
        accepted = $accepted
        rejected = $rejected
        imported_at = [DateTimeOffset]::Now.ToString('o')
    })

    Write-Host "Importato: $packageId -> $batchId ($accepted accepted, $rejected rejected)" -ForegroundColor Green
    return $true
}

function Invoke-Step6AiRoundTrip {
    Write-Title 'FASE 6/11 - Round-trip e import di tutti i package selezionati'
    Write-Why `
        -What 'Per ogni AIPKG scelto verifico il JSONL esterno e lancio ai import separatamente.' `
        -Why 'Ogni package mantiene il proprio contratto, provenance e CBATCH. Nessun package viene ignorato implicitamente.' `
        -Expected 'Un CBATCH distinto per ogni AIPKG selezionato. La fase si chiude solo quando tutti sono importati.'

    $packages = @(Get-SelectedAiPackages)
    if ($packages.Count -eq 0) {
        throw 'Nessun package selezionato. Completa prima la fase 5.'
    }

    foreach ($pkg in $packages) {
        $ok = Import-OneAiPackage -Package $pkg
        if (-not $ok) {
            Write-Host 'Round-trip lasciato incompleto. Gli import gia eseguiti non verranno ripetuti.' -ForegroundColor Yellow
            return
        }
    }

    Complete-Action -Action 'ai.roundtrip.all_selected_imported'
    Complete-Step -Step 6
}

# ===========================================================================
# 8. Review -> MERGE -> reconcile
# ===========================================================================

function Get-ReviewList {
    param(
        [Parameter(Mandatory)][string]$BatchId,
        [Parameter(Mandatory)]
        [ValidateSet('pending', 'confirmed', 'rejected', 'superseded')]
        [string]$Outcome
    )

    $r = Invoke-Dsl `
        -Label "review list $Outcome $BatchId" `
        -Arguments @(
            'candidates',
            'review',
            'list',
            [string]$script:State.workspace,
            '--outcome',
            $Outcome,
            '--batch',
            $BatchId
        )
    Require-Success $r "Impossibile elencare $Outcome per $BatchId."

    try {
        return ($r.Stdout | ConvertFrom-Json)
    }
    catch {
        throw "Output review list non JSON per $BatchId/$Outcome."
    }
}

function Get-ReviewActorAndReason {
    param([Parameter(Mandatory)][string]$Operation)

    $defaultActor = [string]$env:USERNAME
    if ($defaultActor) {
        $actorPrompt = "Actor ID [$defaultActor]"
    }
    else {
        $actorPrompt = 'Actor ID'
    }

    $actor = (Read-Host $actorPrompt).Trim()
    if (-not $actor) {
        $actor = $defaultActor
    }
    while (-not $actor) {
        $actor = (Read-Host 'Actor ID obbligatorio').Trim()
    }

    $reason = ''
    while (-not $reason) {
        $reason = (Read-Host "Motivazione per $Operation").Trim()
    }

    return [pscustomobject]@{
        Actor = $actor
        Reason = $reason
    }
}

function Invoke-Step7ReviewAllAi {
    Write-Title 'FASE 7/11 - Review di tutti i batch AI importati'
    Write-Why `
        -What 'Passo in rassegna ogni CBATCH AI e ogni candidato pending.' `
        -Why 'Importare non significa approvare. La decisione umana deve precedere il merge.' `
        -Expected 'Per ogni candidato scegli pending, conferma o rifiuto. Lasciare pending e una scelta valida.'

    $imports = @($script:State.ai_imports)
    if ($imports.Count -eq 0) {
        throw 'Nessun import AI nello stato. Completa prima la fase 6.'
    }

    foreach ($imp in $imports) {
        $batchId = [string]$imp.import_batch_id
        Write-Title "REVIEW $($imp.package_id) / $batchId"

        $list = Get-ReviewList -BatchId $batchId -Outcome 'pending'
        $pending = @($list.candidates)

        if ($pending.Count -eq 0) {
            Write-Host 'Nessun candidato pending in questo batch.' -ForegroundColor Green
            continue
        }

        $leaveRest = $false

        foreach ($candidate in $pending) {
            if ($leaveRest) {
                break
            }

            $candidateId = [string]$candidate.candidate_record_id
            $show = Invoke-Dsl `
                -Label "review show $candidateId" `
                -Arguments @(
                    'candidates',
                    'review',
                    'show',
                    [string]$script:State.workspace,
                    $candidateId
                )
            Require-Success $show "Impossibile mostrare $candidateId."

            Write-Host ''
            Write-Host "DECISIONE PER $candidateId" -ForegroundColor Yellow
            Write-Host '[Invio/P] lascia pending'
            Write-Host '[C]         conferma'
            Write-Host '[R]         rifiuta'
            Write-Host '[B]         lascia pending tutti i restanti candidati del batch'

            $choice = (Read-Host 'Scelta').Trim().ToUpperInvariant()

            if (-not $choice -or $choice -eq 'P') {
                continue
            }
            if ($choice -eq 'B') {
                $leaveRest = $true
                continue
            }
            if ($choice -notin @('C', 'R')) {
                Write-Host 'Scelta non valida: candidato lasciato pending.' -ForegroundColor Yellow
                continue
            }

            if ($choice -eq 'C') {
                $operationLabel = 'conferma'
            }
            else {
                $operationLabel = 'rifiuto'
            }

            $who = Get-ReviewActorAndReason -Operation $operationLabel

            if ($choice -eq 'C') {
                $r = Invoke-Dsl `
                    -Label "confirm $candidateId" `
                    -Arguments @(
                        'candidates',
                        'review',
                        'confirm',
                        [string]$script:State.workspace,
                        $candidateId,
                        '--actor-id',
                        $who.Actor,
                        '--reason',
                        $who.Reason
                    )
                Require-Success $r "Conferma $candidateId fallita."
            }
            else {
                $r = Invoke-Dsl `
                    -Label "reject $candidateId" `
                    -Arguments @(
                        'candidates',
                        'review',
                        'reject',
                        [string]$script:State.workspace,
                        $candidateId,
                        '--actor-id',
                        $who.Actor,
                        '--reason',
                        $who.Reason
                    )
                Require-Success $r "Rifiuto $candidateId fallito."
            }
        }

        $confirmed = Get-ReviewList -BatchId $batchId -Outcome 'confirmed'
        $pendingAfter = Get-ReviewList -BatchId $batchId -Outcome 'pending'
        $rejected = Get-ReviewList -BatchId $batchId -Outcome 'rejected'

        Write-Host (
            "Batch {0}: confirmed={1}, pending={2}, rejected={3}" -f
            $batchId,
            @($confirmed.candidates).Count,
            @($pendingAfter.candidates).Count,
            @($rejected.candidates).Count
        ) -ForegroundColor Cyan
    }

    Complete-Action -Action 'review.all_ai_batches_inspected'
    Complete-Step -Step 7
}

function Invoke-Step8MergeAndReconcile {
    Write-Title 'FASE 8/11 - Merge dei candidati AI confermati, poi reconcile'
    Write-Why `
        -What 'Per ogni CBATCH AI con almeno un candidato confirmed eseguo facts merge; soltanto dopo eseguo facts reconcile.' `
        -Why 'Review e reconcile da soli non materializzano normali candidate_fact/candidate_relation AI.' `
        -Expected 'Confirmed -> fact/relation effettivi. Pending/rejected restano fuori. Poi reconcile riallinea eventuali supporti sostituiti.'

    $imports = @($script:State.ai_imports)
    if ($imports.Count -eq 0) {
        throw 'Nessun batch AI da fondere.'
    }

    foreach ($imp in $imports) {
        $batchId = [string]$imp.import_batch_id
        $confirmed = Get-ReviewList -BatchId $batchId -Outcome 'confirmed'
        $count = @($confirmed.candidates).Count

        if ($count -eq 0) {
            Write-Host "SKIP merge ${batchId}: nessun candidato confirmed. Pending/rejected non sono errori." -ForegroundColor Yellow
            continue
        }

        Write-Host "Merge ${batchId}: $count candidato/i confirmed." -ForegroundColor Cyan

        $merge = Invoke-Dsl `
            -Label "facts merge $batchId" `
            -Arguments @(
                'facts',
                'merge',
                [string]$script:State.workspace,
                '--batch',
                $batchId
            )
        Require-Success $merge "facts merge fallito per $batchId."
    }

    $reconcile = Invoke-Dsl `
        -Label 'facts reconcile after AI merges' `
        -Arguments @(
            'facts',
            'reconcile',
            [string]$script:State.workspace
        )
    Require-Success $reconcile 'facts reconcile fallito.'

    Complete-Action -Action 'ai.merge_then_reconcile.completed'
    Complete-Step -Step 8
}

# ===========================================================================
# 9. Export, UI e chiusura
# ===========================================================================

function Invoke-Step9Exports {
    Write-Title 'FASE 9/11 - Snapshot DSL e grafo'
    Write-Why `
        -What 'Renderizzo il DSL DOPO il merge AI e poi esporto il grafo.' `
        -Why 'Lo snapshot finale deve vedere patrimonio deterministico ed eventuali candidati AI confermati/materializzati.' `
        -Expected 'Un DSL_* schema 2 e graph export exit 0.'

    $workspacePath = [string]$script:State.workspace

    $render = Invoke-Dsl `
        -Label 'DSL render v2' `
        -Arguments @(
            'dsl',
            'render',
            $workspacePath,
            '--schema-version',
            '2'
        )
    Require-Success $render 'DSL render fallito.'

    $dslId = Extract-LastId -Text $render.Stdout -Prefix 'DSL'
    if (-not $dslId) {
        throw 'Render riuscito ma DSL_* non ricavabile.'
    }

    $script:State.dsl_snapshot_id = $dslId
    Save-State

    $graph = Invoke-Dsl `
        -Label 'graph export' `
        -Arguments @(
            'graph',
            'export',
            $workspacePath,
            '--snapshot-id',
            $dslId,
            '--dynamic'
        )
    Require-Success $graph 'Graph export fallito.'

    Complete-Action -Action 'export.dsl_graph'
    Complete-Step -Step 9
}

function Get-FreeLoopbackPort {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    $listener.Start()
    try {
        return ([Net.IPEndPoint]$listener.LocalEndpoint).Port
    }
    finally {
        $listener.Stop()
    }
}

function Invoke-UiSmokeTest {
    $workspacePath = [string]$script:State.workspace
    $port = Get-FreeLoopbackPort
    $stdout = Join-Path $script:LogsDir 'ui_server.stdout.log'
    $stderr = Join-Path $script:LogsDir 'ui_server.stderr.log'

    $argList = @(
        '-m',
        'dsl_mngr',
        'ui',
        'serve',
        ('"' + $workspacePath + '"'),
        '--host',
        '127.0.0.1',
        '--port',
        [string]$port
    )

    $process = $null
    try {
        $process = Start-Process `
            -FilePath $script:ProjectPython `
            -ArgumentList $argList `
            -WindowStyle Hidden `
            -PassThru `
            -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr

        $base = "http://127.0.0.1:$port"
        $ready = $false

        foreach ($attempt in 1..40) {
            if ($process.HasExited) {
                break
            }

            try {
                $response = Invoke-WebRequest `
                    -Uri "$base/" `
                    -UseBasicParsing `
                    -TimeoutSec 2

                if ($response.StatusCode -eq 200) {
                    $ready = $true
                    break
                }
            }
            catch {
                # Server non pronto: ritento.
            }

            Start-Sleep -Milliseconds 250
        }

        if (-not $ready) {
            throw "UI non pronta su $base"
        }

        foreach ($route in @('/', '/runs', '/logs', '/snapshots')) {
            $response = Invoke-WebRequest `
                -Uri ($base + $route) `
                -UseBasicParsing `
                -TimeoutSec 5

            if ($response.StatusCode -ne 200) {
                throw "UI $route -> $($response.StatusCode)"
            }

            Write-Host "UI GET $route -> 200" -ForegroundColor Green
        }
    }
    finally {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit()
        }
    }
}

function Invoke-Step10LogsUi {
    Write-Title 'FASE 10/11 - Log e UI locale'
    Write-Why `
        -What 'Esporto i log e provo le route principali della UI su loopback.' `
        -Why "Controllo osservabilita' senza esporre servizi in rete." `
        -Expected 'HTML/CSV e HTTP 200 sulle route principali.'

    $workspacePath = [string]$script:State.workspace
    $dir = Join-Path $workspacePath 'exports\logs'
    $null = New-Item -ItemType Directory -Path $dir -Force

    $html = Invoke-Dsl `
        -Label 'log table html' `
        -Arguments @(
            'log',
            'table',
            $workspacePath,
            '--format',
            'html',
            '--output',
            (Join-Path $dir 'events_vega.html')
        )
    Require-Success $html 'Export HTML log fallito.'

    $csv = Invoke-Dsl `
        -Label 'log csv' `
        -Arguments @(
            'log',
            'csv',
            $workspacePath,
            '--output',
            (Join-Path $dir 'events_vega.csv')
        )
    Require-Success $csv 'Export CSV log fallito.'

    Invoke-UiSmokeTest

    Complete-Action -Action 'ui.logs_smoke'
    Complete-Step -Step 10
}

function Invoke-Step11Final {
    Write-Title 'FASE 11/11 - Controllo finale'
    Write-Why `
        -What 'Rifaccio scan/checksum e riepilogo package, import, batch e DSL.' `
        -Why 'Il tutorial e concluso solo se la fixture e rimasta immutata e la catena AI e auditabile.' `
        -Expected 'Unchanged=6 e riepilogo completo.'

    $workspacePath = [string]$script:State.workspace

    $scan = Invoke-Dsl `
        -Label 'final corpus scan' `
        -Arguments @('corpus', 'scan', $workspacePath)
    Require-Success $scan 'Scan finale fallito.'

    Assert-ScanCount -Text $scan.Stdout -Name 'Unchanged' -Expected 6
    Assert-ScanCount -Text $scan.Stdout -Name 'Added' -Expected 0
    Assert-ScanCount -Text $scan.Stdout -Name 'Modified' -Expected 0
    Assert-ScanCount -Text $scan.Stdout -Name 'Deleted' -Expected 0

    Assert-TreesIdentical `
        -Left ([string]$script:State.source_copy) `
        -Right (Join-Path $workspacePath 'corpus\active')

    Complete-Action -Action 'final.verified'
    Complete-Step -Step 11

    Write-Host ''
    Write-Host 'LABORATORIO VEGA v13 COMPLETATO' -ForegroundColor Green
    Write-Host "Sessione:  $($script:State.session_root)"
    Write-Host "Workspace: $workspacePath"
    Write-Host "DSL:       $($script:State.dsl_snapshot_id)"
    Write-Host ''
    Write-Host 'PACKAGE E IMPORT AI' -ForegroundColor Cyan

    foreach ($pkg in Get-AiPackageCatalog) {
        $imp = Get-AiImportRecord -PackageId $pkg.PackageId
        if ($imp) {
            Write-Host "  $($pkg.Policy): $($pkg.PackageId) -> $($imp.import_batch_id) accepted=$($imp.accepted) rejected=$($imp.rejected)"
        }
        else {
            Write-Host "  $($pkg.Policy): $($pkg.PackageId) -> non importato"
        }
    }
}

# ===========================================================================
# 10. Menu
# ===========================================================================

$script:Steps = @(
    [pscustomobject]@{ Number = 1; Name = 'Preflight' },
    [pscustomobject]@{ Number = 2; Name = 'Setup workspace' },
    [pscustomobject]@{ Number = 3; Name = 'Doppio scan' },
    [pscustomobject]@{ Number = 4; Name = 'Consolidamento deterministico' },
    [pscustomobject]@{ Number = 5; Name = 'Due AISEL + due AIPKG + scelta export' },
    [pscustomobject]@{ Number = 6; Name = 'Import di tutti i package selezionati' },
    [pscustomobject]@{ Number = 7; Name = 'Review di tutti i batch AI' },
    [pscustomobject]@{ Number = 8; Name = 'Merge AI -> reconcile' },
    [pscustomobject]@{ Number = 9; Name = 'DSL + grafo' },
    [pscustomobject]@{ Number = 10; Name = 'Log + UI' },
    [pscustomobject]@{ Number = 11; Name = 'Controllo finale' }
)

function Get-RecommendedStep {
    foreach ($step in $script:Steps) {
        if ([string]$step.Number -notin @($script:State.completed_steps)) {
            return [int]$step.Number
        }
    }
    return 11
}

function Get-ResumeCommand {
    return (
        '& "' +
        $PSCommandPath +
        '" -Resume "' +
        $script:StatePath +
        '"'
    )
}

function Show-State {
    Write-Title 'STATO SESSIONE'
    Write-Host "Tutor:       v$script:TutorVersion"
    Write-Host "Sessione:    $($script:State.session_root)"
    Write-Host "Workspace:   $($script:State.workspace)"
    Write-Host "Completate:  $(@($script:State.completed_steps) -join ', ')"
    Write-Host "AISEL tech:  $($script:State.technical_plan_id)"
    Write-Host "AISEL domain:$($script:State.domain_plan_id)"
    Write-Host "AIPKG tech:  $($script:State.technical_package_id)"
    Write-Host "AIPKG domain:$($script:State.domain_package_id)"
    Write-Host "Selezionati: $(@($script:State.selected_package_ids) -join ', ')"
    Write-Host "Import AI:   $(@($script:State.ai_imports).Count)"

    foreach ($imp in @($script:State.ai_imports)) {
        Write-Host "  $($imp.package_id) -> $($imp.import_batch_id)"
    }

    Write-Host "DSL:         $($script:State.dsl_snapshot_id)"
    Write-Host "Stato:       $script:StatePath"
    Write-Host "Log:         $script:LogsDir"
}

function Show-RecentLogs {
    Write-Title 'ULTIMI LOG'

    $files = @(
        Get-ChildItem -LiteralPath $script:LogsDir -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 12
    )

    if (-not $files) {
        Write-Host 'Nessun log.'
        return
    }

    foreach ($file in $files) {
        Write-Host ("{0:yyyy-MM-dd HH:mm:ss}  {1}" -f $file.LastWriteTime, $file.FullName)
    }
}

function Show-Menu {
    Write-Host ''
    Write-Host 'Laboratorio Vega Ricambi - tutor interattivo v13' -ForegroundColor Green
    Write-Host "Workspace: $($script:State.workspace)"
    Write-Host "Ripresa:   $(Get-ResumeCommand)" -ForegroundColor DarkGray

    $recommended = Get-RecommendedStep

    Write-Host ''
    Write-Host 'FASI' -ForegroundColor Cyan
    foreach ($step in $script:Steps) {
        $done = [string]$step.Number -in @($script:State.completed_steps)
        if ($done) {
            $marker = '[OK]'
        }
        elseif ($step.Number -eq $recommended) {
            $marker = '[->]'
        }
        else {
            $marker = '[  ]'
        }

        Write-Host ("{0} {1,2}. {2}" -f $marker, $step.Number, $step.Name)
    }

    Write-Host ''
    Write-Host "Invio = fase consigliata ($recommended)"
    Write-Host '1..11 = fase precisa'
    if (-not (Test-ActionDone -Action 'setup.init')) {
        Write-Host 'W = cambia workspace'
    }
    Write-Host 'S = stato'
    Write-Host 'L = log recenti'
    Write-Host 'Q = salva ed esci'
}

function Invoke-StepByNumber {
    param([Parameter(Mandatory)][int]$Number)

    for ($prior = 1; $prior -lt $Number; $prior++) {
        if ([string]$prior -notin @($script:State.completed_steps)) {
            throw "Prima completa la fase $prior."
        }
    }

    switch ($Number) {
        1  { Invoke-Step1Preflight }
        2  { Invoke-Step2Setup }
        3  { Invoke-Step3Scans }
        4  { Invoke-Step4Consolidate }
        5  { Invoke-Step5AiHandoff }
        6  { Invoke-Step6AiRoundTrip }
        7  { Invoke-Step7ReviewAllAi }
        8  { Invoke-Step8MergeAndReconcile }
        9  { Invoke-Step9Exports }
        10 { Invoke-Step10LogsUi }
        11 { Invoke-Step11Final }
        default { throw "Fase inesistente: $Number" }
    }
}

while ($true) {
    try {
        Show-Menu
        $recommended = Get-RecommendedStep
        $choice = (Read-Host 'Scelta').Trim().ToUpperInvariant()

        if (-not $choice) {
            Invoke-StepByNumber -Number $recommended
            continue
        }

        if ($choice -match '^(11|10|[1-9])$') {
            Invoke-StepByNumber -Number ([int]$choice)
            continue
        }

        switch ($choice) {
            'W' {
                if (Test-ActionDone -Action 'setup.init') {
                    Write-Host 'Workspace gia inizializzato.' -ForegroundColor Yellow
                    continue
                }

                $newPath = (Read-Host 'Nuovo percorso assoluto; Invio=annulla').Trim()
                if ($newPath) {
                    Set-WorkspacePath -NewPath $newPath
                }
            }

            'S' {
                Show-State
            }

            'L' {
                Show-RecentLogs
            }

            'Q' {
                Save-State
                Write-Host 'Stato salvato.' -ForegroundColor Green
                Write-Host (Get-ResumeCommand)
                exit 0
            }

            default {
                Write-Host 'Scelta non riconosciuta.' -ForegroundColor Yellow
            }
        }
    }
    catch {
        Save-State
        Write-Host ''
        Write-Host 'ERRORE NELLA FASE' -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Yellow
        Write-Host "Sessione salvata. Ripresa: $(Get-ResumeCommand)"
        Write-Host "Journal: $script:JournalPath"
        Write-Host "Log:     $script:LogsDir"
    }
}
