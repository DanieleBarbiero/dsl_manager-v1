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

$script:Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $script:Utf8NoBom
[Console]::OutputEncoding = $script:Utf8NoBom
$OutputEncoding = $script:Utf8NoBom

# ---------------------------------------------------------------------------
# 0. Piccole utility generiche
# ---------------------------------------------------------------------------

function Write-Title {
    param([Parameter(Mandatory)][string]$Text)
    Write-Host ""
    Write-Host ("=" * 78) -ForegroundColor DarkGray
    Write-Host $Text -ForegroundColor Green
    Write-Host ("=" * 78) -ForegroundColor DarkGray
}

function Write-Why {
    param(
        [Parameter(Mandatory)][string]$What,
        [Parameter(Mandatory)][string]$Why,
        [Parameter(Mandatory)][string]$Expected
    )
    Write-Host ""
    Write-Host "COSA STAI FACENDO" -ForegroundColor Cyan
    Write-Host $What
    Write-Host ""
    Write-Host "PERCHE'" -ForegroundColor Cyan
    Write-Host $Why
    Write-Host ""
    Write-Host "COSA DEVI ASPETTARTI" -ForegroundColor Cyan
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

Ho cercato, risalendo dalle directory dello script, una cartella che contenga:
  - AGENTS.md
  - pyproject.toml
  - .codex\config.toml

Metti la cartella Laboratorio Vega sotto il repository (per esempio sotto
.kb\projects\) e rilancia lo script.
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
        throw @"
PROJECT_PYTHON non e' dichiarato in:
$configPath

Non usero' il Python globale come ripiego: rischierebbe di usare dipendenze
diverse da quelle previste dal progetto.
"@
    }

    $configured = $match.Groups[1].Value
    $candidate = if ([System.IO.Path]::IsPathRooted($configured)) {
        $configured
    } else {
        Join-Path $RepositoryRoot $configured
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

Correggi PROJECT_PYTHON / ambiente virtuale; non modificare Vega per usare un
Python casuale.
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

    $leftJson = $leftMap | ConvertTo-Json -Compress
    $rightJson = $rightMap | ConvertTo-Json -Compress

    if ($leftJson -ne $rightJson) {
        throw @"
I file non sono byte-identici.

SINISTRA: $Left
DESTRA:   $Right

Non eseguire lo scan. Il test perderebbe la sua baseline.
"@
    }

    Write-Host "Integrita': $($leftMap.Count) file byte-identici." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# 1. Contesto del repository e del laboratorio
# ---------------------------------------------------------------------------

$script:RepositoryRoot = Find-RepositoryRoot -Start $PSScriptRoot
$script:ProjectPython = Resolve-ProjectPython -RepositoryRoot $script:RepositoryRoot
$script:LabRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$script:CanonicalCorpus = Join-Path $script:LabRoot 'corpus\active'
$script:ChecksumFile = Join-Path $PSScriptRoot 'checksums.json'
$script:ScenarioManifest = Join-Path $PSScriptRoot 'scenario_manifest.json'

foreach ($required in @(
    $script:CanonicalCorpus,
    $script:ChecksumFile,
    $script:ScenarioManifest
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "File/directory essenziale del laboratorio assente: $required"
    }
}

$script:ExpectedFiles = @(
    'database/schema_vega.sql',
    'plsql/logica_vega.sql',
    'forms/frm_richiesta.xml',
    'logs/vega_2026.log',
    'documenti/manuale_operativo_vega_2026.docx',
    'documenti/matrice_priorita_vega_2026.xlsx'
)

function Test-CanonicalCorpus {
    $manifest = Get-Content -LiteralPath $script:ChecksumFile -Raw -Encoding UTF8 | ConvertFrom-Json

    if ([int]$manifest.active_source_count -ne 6) {
        throw "checksums.json non dichiara 6 fonti."
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
        throw "Il corpus contiene $($actual.Count) file, ma Vega v12 ne prevede esattamente 6."
    }

    return $true
}

if ($ValidateOnly) {
    $valid = Test-CanonicalCorpus
    [ordered]@{
        status = if ($valid) { 'valid' } else { 'invalid' }
        repository_root = $script:RepositoryRoot
        project_python = $script:ProjectPython
        python_version = ((& $script:ProjectPython --version 2>&1) -join ' ')
        lab_root = $script:LabRoot
        active_source_count = 6
        docling_source_count = 2
    } | ConvertTo-Json -Depth 5
    exit 0
}

# ---------------------------------------------------------------------------
# 2. Stato persistente
# ---------------------------------------------------------------------------

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
    $sessionRoot = Join-Path $sessionBase ("vega_${stamp}_" + [guid]::NewGuid().ToString('N').Substring(0, 8))
    $null = New-Item -ItemType Directory -Path $sessionRoot
    $null = New-Item -ItemType Directory -Path (Join-Path $sessionRoot 'logs')
    $null = New-Item -ItemType Directory -Path (Join-Path $sessionRoot 'source_copy')

    $defaultWorkspace = if ($Workspace) {
        [Environment]::ExpandEnvironmentVariables($Workspace.Trim().Trim('"'))
    } else {
        Join-Path $sessionRoot 'workspace'
    }

    if (-not [System.IO.Path]::IsPathRooted($defaultWorkspace)) {
        throw "-Workspace deve essere un percorso assoluto."
    }

    $state = [pscustomobject][ordered]@{
        schema_version = 3
        scenario = 'Laboratorio Vega Ricambi'
        session_root = [System.IO.Path]::GetFullPath($sessionRoot)
        state_path = [System.IO.Path]::GetFullPath((Join-Path $sessionRoot 'session_state.json'))
        workspace = [System.IO.Path]::GetFullPath($defaultWorkspace)
        source_copy = [System.IO.Path]::GetFullPath((Join-Path $sessionRoot 'source_copy'))
        completed_actions = @()
        completed_steps = @()
        observed_ids = @()
        technical_plan_id = $null
        domain_plan_id = $null
        package_id = $null
        ai_prompt_path = $null
        ai_template_path = $null
        ai_candidate_path = $null
        ai_response_sha256 = $null
        ai_import_run_id = $null
        ai_import_batch_id = $null
        ai_import_total = $null
        ai_import_accepted = $null
        ai_import_rejected = $null
        dsl_snapshot_id = $null
        last_run_id = $null
        command_counter = 0
        created_at = [DateTimeOffset]::Now.ToString('o')
        updated_at = [DateTimeOffset]::Now.ToString('o')
    }

    return $state
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
    if ($stateVersion -eq 2) {
        # Migrazione sicura v04 -> v07 soltanto se la vecchia sessione non ha
        # superato la fase 5. Dalla vecchia fase 6 in poi i numeri cambiano.
        $advancedOldSteps = @(
            @($state.completed_steps) |
            Where-Object { [int]$_ -ge 6 }
        )
        if ($advancedOldSteps.Count -gt 0) {
            throw @"
Questa sessione appartiene al tutor precedente ed e' gia arrivata almeno alla
vecchia fase 6. La v07 inserisce una nuova fase 6 (round-trip AI), quindi non
posso rimappare automaticamente i checkpoint senza rischiare di saltare lavoro.

Crea una nuova sessione Vega oppure riprendi una sessione v04 ferma alla fase 5.
"@
        }

        foreach ($propertyName in @(
            'ai_prompt_path',
            'ai_template_path',
            'ai_candidate_path',
            'ai_response_sha256',
            'ai_import_run_id',
            'ai_import_batch_id',
            'ai_import_total',
            'ai_import_accepted',
            'ai_import_rejected'
        )) {
            if ($null -eq $state.PSObject.Properties[$propertyName]) {
                $state | Add-Member -MemberType NoteProperty -Name $propertyName -Value $null
            }
        }
        $state.schema_version = 3
    } elseif ($stateVersion -ne 3) {
        throw "Versione di stato non supportata: $($state.schema_version)"
    }

    # Se la directory di sessione e' stata spostata, lo stato segue il file.
    # Il workspace invece NON viene cambiato in silenzio.
    $actualSessionRoot = (Split-Path -Parent $resolved)
    $state.session_root = [System.IO.Path]::GetFullPath($actualSessionRoot)
    $state.state_path = [System.IO.Path]::GetFullPath($resolved)
    $state.source_copy = [System.IO.Path]::GetFullPath((Join-Path $actualSessionRoot 'source_copy'))

    if (-not (Test-Path -LiteralPath (Join-Path $actualSessionRoot 'logs'))) {
        $null = New-Item -ItemType Directory -Path (Join-Path $actualSessionRoot 'logs')
    }

    return $state
}

$script:State = if ($Resume) {
    Import-VegaSession -Path $Resume
} else {
    New-VegaSession
}

$script:StatePath = [string]$script:State.state_path
$script:LogsDir = Join-Path ([string]$script:State.session_root) 'logs'
$script:JournalPath = Join-Path ([string]$script:State.session_root) 'journal.md'
$script:CommandsPath = Join-Path $script:LogsDir 'commands.jsonl'

function Save-State {
    $script:State.updated_at = [DateTimeOffset]::Now.ToString('o')
    $json = $script:State | ConvertTo-Json -Depth 30
    $tmp = $script:StatePath + '.tmp.' + [guid]::NewGuid().ToString('N')

    [System.IO.File]::WriteAllText($tmp, $json + "`n", $script:Utf8NoBom)

    if (Test-Path -LiteralPath $script:StatePath -PathType Leaf) {
        try {
            [System.IO.File]::Replace($tmp, $script:StatePath, $null)
        }
        catch {
            Move-Item -LiteralPath $tmp -Destination $script:StatePath -Force
        }
    } else {
        Move-Item -LiteralPath $tmp -Destination $script:StatePath
    }
}

function Write-Journal {
    param([Parameter(Mandatory)][string]$Text)

    if (-not (Test-Path -LiteralPath $script:JournalPath)) {
        [System.IO.File]::WriteAllText(
            $script:JournalPath,
            "# Diario Laboratorio Vega Ricambi`n",
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

    Write-Journal -Text ("Checkpoint completato: {0}" -f $Action)
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
        throw @"
Il workspace e' gia stato inizializzato.

Non posso cambiare soltanto il percorso e fingere che database, revisioni e ID
siano gli stessi. Per usare un altro workspace crea una nuova sessione.
"@
    }

    $expanded = [Environment]::ExpandEnvironmentVariables($NewPath.Trim().Trim('"'))
    if (-not [System.IO.Path]::IsPathRooted($expanded)) {
        throw "Inserisci un percorso assoluto, per esempio D:\laboratori\vega_workspace."
    }

    $script:State.workspace = [System.IO.Path]::GetFullPath($expanded)
    Write-Journal -Text "Workspace cambiato in: $($script:State.workspace)"
    Save-State

    Write-Host "Workspace salvato nello stato: $($script:State.workspace)" -ForegroundColor Green
}

# Eventuale override -Workspace durante un resume.
if ($Resume -and $Workspace) {
    $requested = [System.IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Workspace.Trim().Trim('"'))
    )
    if ($requested -ne [string]$script:State.workspace) {
        Set-WorkspacePath -NewPath $requested
    }
}

# Crea subito lo stato di una sessione nuova.
Save-State

# ---------------------------------------------------------------------------
# 3. Logging di processo: completo su file, corto in console
# ---------------------------------------------------------------------------

function Get-SafeSlug {
    param([Parameter(Mandatory)][string]$Text)
    # Evita una forma sintattica che alcuni parser di Windows PowerShell interpretano male.
    $slug = [regex]::Replace($Text.ToLowerInvariant(), '[^a-z0-9]+', '_')
    $slug = $slug.Trim('_')
    if (-not $slug) { $slug = 'command' }
    if ($slug.Length -gt 40) { $slug = $slug.Substring(0, 40) }
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

        switch ($match.Groups[1].Value) {
            'RUN'   { $script:State.last_run_id = $value }
            'AIPKG' { $script:State.package_id = $value }
            'DSL'   { $script:State.dsl_snapshot_id = $value }
        }
    }

    Save-State
}

function Show-UsefulTail {
    param(
        [Parameter(Mandatory)][AllowEmptyString()][string]$Text,
        [Parameter()][int]$MaxLines = 8
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
        Write-Host "Output: nessun stdout." -ForegroundColor DarkGray
        return
    }

    # Scan: la sintesi piu utile sono i quattro conteggi.
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

    # Prova JSON: mostra solo campi di alto livello e summary.
    try {
        $obj = $trimmed | ConvertFrom-Json

        foreach ($name in @(
            'run_id', 'status', 'exit_code', 'batch_command',
            'report_path', 'batch_report_path',
            'selection_plan_id', 'package_id', 'snapshot_id',
            'dsl_snapshot_id', 'config_hash'
        )) {
            $prop = $obj.PSObject.Properties[$name]
            if ($null -ne $prop -and $null -ne $prop.Value -and [string]$prop.Value) {
                Write-Host ("{0}: {1}" -f $name, [string]$prop.Value)
            }
        }

        $summaryProp = $obj.PSObject.Properties['summary']
        if ($null -ne $summaryProp -and $null -ne $summaryProp.Value) {
            Write-Host ("summary: " + ($summaryProp.Value | ConvertTo-Json -Compress -Depth 8))
        }

        $candidateProp = $obj.PSObject.Properties['candidates']
        if ($null -ne $candidateProp -and $null -ne $candidateProp.Value) {
            Write-Host ("candidates: " + @($candidateProp.Value).Count)
        }

        return
    }
    catch {
        # Non e' JSON: continua con una piccola anteprima.
    }

    Write-Host "Anteprima stdout (massimo 6 righe):"
    Show-UsefulTail -Text $trimmed -MaxLines 6
    Write-Host "Output completo: $StdoutPath" -ForegroundColor DarkGray
}

function Invoke-LoggedProcess {
    param(
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][string]$File,
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter()][switch]$LongRunning
    )

    $script:State.command_counter = [int]$script:State.command_counter + 1
    Save-State

    $number = '{0:D3}' -f [int]$script:State.command_counter
    $slug = Get-SafeSlug -Text $Label
    $stdoutPath = Join-Path $script:LogsDir "${number}_${slug}.stdout.log"
    $stderrPath = Join-Path $script:LogsDir "${number}_${slug}.stderr.log"

    $commandLine = Format-CommandLine -File $File -Arguments $Arguments

    Write-Host ""
    Write-Host "[$number] $Label" -ForegroundColor Cyan
    Write-Host "Comando: $commandLine" -ForegroundColor DarkGray

    $started = [DateTimeOffset]::Now

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
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
    } else {
        $psi.Arguments = (
            $Arguments |
            ForEach-Object { ConvertTo-NativeProcessArgument -Argument $_ }
        ) -join ' '
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $psi
    $null = $process.Start()

    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()

    $nextHeartbeat = 15

    while (-not $process.HasExited) {
        Start-Sleep -Milliseconds 250

        if ($LongRunning) {
            $elapsedSeconds = [int]([DateTimeOffset]::Now - $started).TotalSeconds
            if ($elapsedSeconds -ge $nextHeartbeat) {
                Write-Host "Ancora in esecuzione... ${elapsedSeconds}s. L'output completo va nei log." -ForegroundColor DarkYellow
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
        Write-Host "stdout completo: $stdoutPath" -ForegroundColor DarkGray
        if ($stderr.Trim()) {
            Write-Host "stderr completo: $stderrPath" -ForegroundColor DarkGray
        }
    } else {
        Write-Host "Il comando NON e' terminato con successo." -ForegroundColor Yellow

        if ($stderr.Trim()) {
            Write-Host "Ultime righe stderr:" -ForegroundColor DarkYellow
            Show-UsefulTail -Text $stderr -MaxLines 10
        } elseif ($stdout.Trim()) {
            Write-Host "Ultime righe stdout:" -ForegroundColor DarkYellow
            Show-UsefulTail -Text $stdout -MaxLines 10
        }

        Write-Host "stdout completo: $stdoutPath" -ForegroundColor DarkGray
        Write-Host "stderr completo: $stderrPath" -ForegroundColor DarkGray
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
        [Parameter()][switch]$LongRunning
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
        [Parameter(Mandatory)][ValidateSet('RUN','REV','AISEL','AIPKG','CBATCH','CREC','DSL')][string]$Prefix
    )
    $m = [regex]::Match($Text, "(?<![A-Z])${Prefix}_\d{6}")
    if ($m.Success) { return $m.Value }
    return $null
}

function Extract-LastId {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][ValidateSet('RUN','REV','AISEL','AIPKG','CBATCH','CREC','DSL')][string]$Prefix
    )
    $matches = [regex]::Matches($Text, "(?<![A-Z])${Prefix}_\d{6}")
    if ($matches.Count -gt 0) { return $matches[$matches.Count - 1].Value }
    return $null
}

# ---------------------------------------------------------------------------
# 4. Le dieci fasi
# ---------------------------------------------------------------------------

function Invoke-Step1Preflight {
    Write-Title "FASE 1/11 - Preflight"
    Write-Why `
        -What "Controllo repository, Python 3.12, sei fonti canoniche e checksum." `
        -Why "Se l'ambiente o la fixture sono sbagliati, qualunque errore successivo sarebbe ambiguo." `
        -Expected "Nessuna mutazione del workspace. Tutti i controlli verdi."

    $null = Test-CanonicalCorpus

    Write-Host "Repository: $script:RepositoryRoot"
    Write-Host "Python:     $script:ProjectPython"
    Write-Host "Workspace:  $($script:State.workspace)"
    Write-Host "Fonti:      6 (solo 2 Docling)" -ForegroundColor Green

    Complete-Action -Action 'preflight.valid'
    Complete-Step -Step 1
}

function Invoke-Step2Setup {
    Write-Title "FASE 2/11 - Crea il workspace e prepara la governance"
    Write-Why `
        -What "Inizializzo workspace/database, copio le fonti, verifico gli hash e applico conservative/1." `
        -Why "Il corpus originale resta immutabile; le policy di review sono esplicite e versionate." `
        -Expected "Workspace pronto, sei file identici, config valida."

    $workspacePath = [string]$script:State.workspace
    $sourceCopy = [string]$script:State.source_copy

    if (-not (Test-ActionDone 'setup.init')) {
        if (Test-Path -LiteralPath $workspacePath) {
            Write-Host "Workspace gia' esistente: nuova sessione Vega, lo elimino e riparto pulito." -ForegroundColor Yellow
            Remove-Item -LiteralPath $workspacePath -Recurse -Force -ErrorAction Stop
        }

        $r = Invoke-Dsl -Label 'init workspace' -Arguments @('init', $workspacePath)
        Require-Success $r 'dsl_mngr init fallito.'
        Complete-Action 'setup.init'
    } else {
        Write-Host "Checkpoint: init gia completato; non lo ripeto." -ForegroundColor DarkGray
    }

    if (-not (Test-ActionDone 'setup.db_init')) {
        $r = Invoke-Dsl -Label 'db init' -Arguments @('db', 'init', $workspacePath)
        Require-Success $r 'dsl_mngr db init fallito.'
        Complete-Action 'setup.db_init'
    } else {
        Write-Host "Checkpoint: db init gia completato; non lo ripeto." -ForegroundColor DarkGray
    }

    if (-not (Test-ActionDone 'setup.copy_sources')) {
        if (Test-Path -LiteralPath $sourceCopy) {
            Get-ChildItem -LiteralPath $sourceCopy -Force | Remove-Item -Recurse -Force
        } else {
            $null = New-Item -ItemType Directory -Path $sourceCopy
        }

        Copy-Item -Path (Join-Path $script:CanonicalCorpus '*') -Destination $sourceCopy -Recurse

        $workspaceCorpus = Join-Path $workspacePath 'corpus\active'
        Copy-Item -Path (Join-Path $sourceCopy '*') -Destination $workspaceCorpus -Recurse

        Assert-TreesIdentical -Left $sourceCopy -Right $workspaceCorpus
        Complete-Action 'setup.copy_sources'
    } else {
        Write-Host "Checkpoint: fonti gia copiate; verifico comunque gli hash." -ForegroundColor DarkGray
        Assert-TreesIdentical -Left $sourceCopy -Right (Join-Path $workspacePath 'corpus\active')
    }

    if (-not (Test-ActionDone 'setup.review_profile')) {
        $show = Invoke-Dsl -Label 'review show' -Arguments @('config', 'review', 'show', $workspacePath)
        Require-Success $show 'Impossibile leggere la configurazione review.'

        $profiles = Invoke-Dsl -Label 'review profiles' -Arguments @('config', 'review', 'profiles', $workspacePath)
        Require-Success $profiles 'Impossibile elencare i profili review.'

        $configHash = $null
        try {
            $obj = $show.Stdout | ConvertFrom-Json
            if ($obj.config_hash -match '^[0-9a-fA-F]{64}$') {
                $configHash = [string]$obj.config_hash
            }
        } catch {}

        $applyArgs = @(
            'config', 'review', 'apply-profile', $workspacePath,
            '--profile', 'conservative/1'
        )
        if ($configHash) {
            $applyArgs += @('--expect-config-hash', $configHash)
        }

        $apply = Invoke-Dsl -Label 'apply conservative profile' -Arguments $applyArgs
        Require-Success $apply 'Applicazione del profilo conservative/1 fallita.'

        $validate = Invoke-Dsl -Label 'config validate' -Arguments @(
            'config', 'validate', $workspacePath, '--profile', 'conservative/1'
        )
        Require-Success $validate 'La configurazione non supera la validazione.'

        Complete-Action 'setup.review_profile'
    } else {
        Write-Host "Checkpoint: profilo review gia applicato." -ForegroundColor DarkGray
    }

    Complete-Step -Step 2
}

function Assert-ScanCount {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][int]$Expected
    )
    $m = [regex]::Match($Text, "(?m)^${Name}:\s*(\d+)\s*$")
    if (-not $m.Success) {
        throw "Lo scan non contiene la riga '${Name}: ...'. Leggi il log completo."
    }
    $actual = [int]$m.Groups[1].Value
    if ($actual -ne $Expected) {
        throw "Scan inatteso: $Name=$actual, atteso $Expected."
    }
}

function Invoke-Step3Scans {
    Write-Title "FASE 3/11 - Doppio scan"
    Write-Why `
        -What "Registro le sei fonti e ripeto subito lo scan." `
        -Why "Il secondo passaggio verifica che byte invariati non producano revisioni spurie." `
        -Expected "Primo scan Added=6. Secondo scan Unchanged=6."

    $workspacePath = [string]$script:State.workspace

    if (-not (Test-ActionDone 'scan.first')) {
        $r1 = Invoke-Dsl -Label 'corpus scan 1' -Arguments @('corpus', 'scan', $workspacePath)
        Require-Success $r1 'Primo scan fallito.'
        Assert-ScanCount -Text $r1.Stdout -Name 'Added' -Expected 6
        Assert-ScanCount -Text $r1.Stdout -Name 'Modified' -Expected 0
        Assert-ScanCount -Text $r1.Stdout -Name 'Deleted' -Expected 0
        Complete-Action 'scan.first'
    } else {
        Write-Host "Checkpoint: primo scan gia completato." -ForegroundColor DarkGray
    }

    if (-not (Test-ActionDone 'scan.second')) {
        $r2 = Invoke-Dsl -Label 'corpus scan 2' -Arguments @('corpus', 'scan', $workspacePath)
        Require-Success $r2 'Secondo scan fallito.'
        Assert-ScanCount -Text $r2.Stdout -Name 'Unchanged' -Expected 6
        Assert-ScanCount -Text $r2.Stdout -Name 'Added' -Expected 0
        Assert-ScanCount -Text $r2.Stdout -Name 'Modified' -Expected 0
        Assert-ScanCount -Text $r2.Stdout -Name 'Deleted' -Expected 0
        Complete-Action 'scan.second'
    } else {
        Write-Host "Checkpoint: secondo scan gia completato." -ForegroundColor DarkGray
    }

    Complete-Step -Step 3
}

function Invoke-Step4Consolidate {
    Write-Title "FASE 4/11 - Consolidamento"
    Write-Why `
        -What "Eseguo la pipeline pubblica batch consolidate con reconcile." `
        -Why "E' lo smoke test principale: quattro parser strutturali + due documenti Docling." `
        -Expected "Batch completato senza item failed. Solo DOCX e XLSX pagano la normalizzazione Docling."

    if (Test-ActionDone 'consolidate.run') {
        Write-Host "Checkpoint: consolidamento gia completato; non lo ripeto automaticamente." -ForegroundColor DarkGray
        Complete-Step -Step 4
        return
    }

    $workspacePath = [string]$script:State.workspace
    $r = Invoke-Dsl `
        -Label 'batch consolidate' `
        -Arguments @('batch', 'consolidate', $workspacePath, '--reconcile') `
        -LongRunning

    if ($r.ExitCode -ne 0) {
        $runId = Extract-LastId -Text ($r.Stdout + "`n" + $r.Stderr) -Prefix 'RUN'
        if ($runId) {
            Write-Host ""
            Write-Host "Run rilevata: $runId" -ForegroundColor Yellow
            Write-Host "Prima diagnosi consigliata:" -ForegroundColor Yellow
            Write-Host "  `"$script:ProjectPython`" -m dsl_mngr run status `"$workspacePath`" $runId"
            Write-Host ""
            Write-Host "Se il report dichiara il run retryable, usa al massimo un resume consapevole:"
            Write-Host "  `"$script:ProjectPython`" -m dsl_mngr batch consolidate `"$workspacePath`" --reconcile --resume $runId"
        }
        throw "Consolidamento non completato. Lo stato NON marca questa fase come conclusa."
    }

    Complete-Action 'consolidate.run'
    Complete-Step -Step 4
}

function Invoke-Step5AiHandoff {
    Write-Title "FASE 5/11 - Preparazione dell'handoff AI"
    Write-Why `
        -What "Creo due piani di evidenza e un package reale per una AI esterna." `
        -Why "Vega separa la selezione deterministica delle evidenze dalla successiva interpretazione AI." `
        -Expected "Due AISEL reali e un AIPKG reale in ai/outbox."

    $workspacePath = [string]$script:State.workspace

    if (-not (Test-ActionDone 'ai.technical_plan')) {
        $tech = Invoke-Dsl -Label 'AI evidence technical plan' -Arguments @(
            'ai', 'evidence', 'plan', $workspacePath,
            '--policy', 'technical_extraction'
        )
        Require-Success $tech 'Creazione piano technical_extraction fallita.'

        $id = Extract-LastId -Text $tech.Stdout -Prefix 'AISEL'
        if (-not $id) { throw "Piano tecnico creato ma AISEL non ricavabile dall'output." }
        $script:State.technical_plan_id = $id
        Save-State
        Complete-Action 'ai.technical_plan'
    } else {
        Write-Host "Piano tecnico salvato: $($script:State.technical_plan_id)" -ForegroundColor DarkGray
    }

    if (-not (Test-ActionDone 'ai.domain_plan')) {
        $domain = Invoke-Dsl -Label 'AI evidence domain plan' -Arguments @(
            'ai', 'evidence', 'plan', $workspacePath,
            '--policy', 'domain_interpretation'
        )
        Require-Success $domain 'Creazione piano domain_interpretation fallita.'

        $id = Extract-LastId -Text $domain.Stdout -Prefix 'AISEL'
        if (-not $id) { throw "Piano dominio creato ma AISEL non ricavabile dall'output." }
        $script:State.domain_plan_id = $id
        Save-State
        Complete-Action 'ai.domain_plan'
    } else {
        Write-Host "Piano dominio salvato: $($script:State.domain_plan_id)" -ForegroundColor DarkGray
    }

    if (-not (Test-ActionDone 'ai.package')) {
        $plan = [string]$script:State.domain_plan_id
        if (-not $plan) { throw "Manca domain_plan_id nello stato." }

        $pkg = Invoke-Dsl -Label 'AI package' -Arguments @(
            'ai', 'package', $workspacePath,
            '--selection-plan', $plan
        )
        Require-Success $pkg 'Creazione package AI fallita.'

        $pkgId = Extract-LastId -Text $pkg.Stdout -Prefix 'AIPKG'
        if (-not $pkgId) { throw "Package creato ma AIPKG non ricavabile dall'output." }
        $script:State.package_id = $pkgId
        Save-State
        Complete-Action 'ai.package'
    } else {
        Write-Host "Package salvato: $($script:State.package_id)" -ForegroundColor DarkGray
    }

    $packageDir = Join-Path $workspacePath ("ai\outbox\" + [string]$script:State.package_id)
    Write-Host ""
    Write-Host "Package pronto per l'handoff umano:" -ForegroundColor Green
    Write-Host "  $packageDir"
    Write-Host ""
    Write-Host "La prossima fase insegna il giro completo: package -> AI esterna -> JSONL -> inbox -> import." -ForegroundColor Yellow

    Complete-Step -Step 5
}

function Get-JsonPropertyValue {
    param(
        [Parameter(Mandatory)]$Object,
        [Parameter(Mandatory)][string]$Name
    )

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Test-MissingJsonValue {
    param([Parameter()]$Value)

    if ($null -eq $Value) { return $true }
    if ($Value -is [string] -and -not $Value.Trim()) { return $true }
    return $false
}

function Test-UnresolvedSemanticPlaceholder {
    param([Parameter()]$Value)

    if ($null -eq $Value) { return $false }
    $text = if ($Value -is [string]) {
        [string]$Value
    } else {
        ($Value | ConvertTo-Json -Compress -Depth 20)
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

    if (-not $EvidenceId -or -not $EvidenceText) { return $false }

    $header = "## Evidence $EvidenceId"
    $start = $Content.IndexOf($header, [System.StringComparison]::Ordinal)
    if ($start -lt 0) { return $false }

    $next = $Content.IndexOf(
        '## Evidence ',
        $start + $header.Length,
        [System.StringComparison]::Ordinal
    )

    $section = if ($next -lt 0) {
        $Content.Substring($start)
    } else {
        $Content.Substring($start, $next - $start)
    }

    return ($section.IndexOf($EvidenceText, [System.StringComparison]::Ordinal) -ge 0)
}

function Write-AiHumanHandoffKit {
    param(
        [Parameter(Mandatory)][string]$WorkspacePath,
        [Parameter(Mandatory)][string]$PackageId
    )

    $packageDir = Join-Path $WorkspacePath ("ai\outbox\" + $PackageId)
    if (-not (Test-Path -LiteralPath $packageDir -PathType Container)) {
        throw "Directory del package AI non trovata: $packageDir"
    }

    foreach ($name in @(
        'instructions.md',
        'content.md',
        'source_manifest.json',
        'candidate_schema.json',
        'output_template.jsonl',
        'package_manifest.json'
    )) {
        $required = Join-Path $packageDir $name
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "Package AI incompleto: manca $required"
        }
    }

    $kitDir = Join-Path ([string]$script:State.session_root) ("ai_handoff\" + $PackageId)
    if (-not (Test-Path -LiteralPath $kitDir)) {
        $null = New-Item -ItemType Directory -Path $kitDir -Force
    }

    $promptPath = Join-Path $kitDir 'PROMPT_PER_QUALSIASI_AI.txt'
    $templatePath = Join-Path $kitDir 'OUTPUT_TEMPLATE_ORIGINALE.jsonl'
    Copy-Item -LiteralPath (Join-Path $packageDir 'output_template.jsonl') -Destination $templatePath -Force

    $expectedName = "${PackageId}_candidates.jsonl"
    $expectedInbox = Join-Path $WorkspacePath ("ai\inbox\" + $expectedName)
    $officialTemplate = [System.IO.File]::ReadAllText(
        (Join-Path $packageDir 'output_template.jsonl'),
        [System.Text.Encoding]::UTF8
    ).Trim()

    $prompt = @"
DSL MANAGER - STRICT AI HANDOFF CONTRACT
Package: $PackageId
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
Produce only candidate records that are genuinely supported by evidence in content.md.
Follow candidate_schema.json and instructions.md. The output will be machine-imported
without a human cleaning pass, so lexical correctness is mandatory.

ABSOLUTE JSONL RULES - THESE ARE PART OF THE DATA CONTRACT
- Output must be JSONL / NDJSON: EXACTLY ONE complete JSON object per PHYSICAL line.
- Never put two JSON objects on the same line.
- Never return a JSON array and never wrap records in an outer object.
- Do not use Markdown code fences of any kind.
- Do not add introductions, explanations, headings, comments, bullet points, or a filename line.
- The first character of every non-empty output line must be { and the last must be }.
- Every line must be independently parseable by a standard JSON parser.
- Escape JSON strings correctly: embedded double quotes become \" and backslashes become \\.
- A string must never contain a literal physical newline. Encode it as \n only if the exact
  evidence itself requires a newline.
- Use plain UTF-8 text. Do not emit a UTF-8 BOM if you create a file.
- candidate_id values must be unique within this response.
- Never leave REPLACE_*, PLACEHOLDER, TBD, TODO, brace-style or angle-bracket template markers.
- The supplied output_template.jsonl is a SHAPE EXAMPLE ONLY. Never return it unchanged.

ABSOLUTE EVIDENCE RULES
- Copy source_revision_id, chunk_id and fragment_id EXACTLY from the package.
- Never invent, normalize, shorten or reconstruct an identifier.
- evidence_text MUST be copied VERBATIM as one contiguous substring from the referenced
  evidence block in content.md.
- Preserve evidence_text character-for-character: spaces, punctuation, case, quotes and
  Markdown/table formatting must remain exactly as present in the referenced evidence.
- NEVER convert spreadsheet/tabular evidence into a different Markdown table representation.
- In particular, never add Markdown table pipes (`|`) unless those exact pipe characters are
  already present in the referenced evidence text.
- NEVER add leading/trailing pipes, bullets, labels or punctuation that are absent from evidence.
- If you cannot provide an exact literal evidence_text for a proposed candidate, OMIT that
  candidate instead of guessing.
- Prefer fewer valid candidates over many speculative candidates.

SEMANTIC RULES
- Use only record_type values allowed by candidate_schema.json.
- Use assertion_type explicit for directly stated declarations, observed for runtime/log events,
  inferred only for a necessary inference, and ambiguous for genuine ambiguity.
- confidence must use only values allowed by candidate_schema.json.
- Fill every record-specific required field declared by candidate_schema.json.

MANDATORY SELF-CHECK BEFORE ANSWERING
Perform this check internally before you return anything:
1. Split your intended answer into physical lines.
2. Parse EACH non-empty line independently as JSON.
3. Confirm each parsed value is a JSON object, not an array/string.
4. Confirm there is exactly one object on each line and no text before/after it.
5. Confirm every required field in candidate_schema.json is present.
6. Confirm every source_revision_id/chunk_id/fragment_id exists in source_manifest.json.
7. For every record, search the referenced Evidence section in content.md and confirm
   evidence_text occurs there as an exact contiguous substring.
8. Confirm no template placeholder remains.
9. If any check fails, fix or remove that record BEFORE returning the response.

OUTPUT
If your interface can create files, create exactly:
$expectedName

If your interface cannot create a file, respond with ONLY the raw JSONL body. No Markdown fences,
no prose and no blank explanatory lines.

OFFICIAL PACKAGE TEMPLATE - FOR STRUCTURE ONLY, DO NOT COPY PLACEHOLDERS
If your system supports constrained/structured output, use candidate_schema.json as the schema
and use the template below only as a field-layout example.
----- BEGIN TEMPLATE -----
$officialTemplate
----- END TEMPLATE -----

Again: the final answer must contain candidate JSONL only. The BEGIN/END TEMPLATE markers above
must NOT appear in the final output.
"@

    [System.IO.File]::WriteAllText($promptPath, $prompt, $script:Utf8NoBom)

    $script:State.ai_prompt_path = $promptPath
    $script:State.ai_template_path = $templatePath
    $script:State.ai_candidate_path = $expectedInbox
    Save-State

    return [pscustomobject]@{
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

    $schemaPath = Join-Path $PackageDir 'candidate_schema.json'
    $manifestPath = Join-Path $PackageDir 'source_manifest.json'
    $contentPath = Join-Path $PackageDir 'content.md'

    $schema = Get-Content -LiteralPath $schemaPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $content = [System.IO.File]::ReadAllText($contentPath, [System.Text.Encoding]::UTF8)

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

    $allowedAssertionTypes = @($schema.properties.assertion_type.enum | ForEach-Object { [string]$_ })
    $allowedConfidence = @($schema.properties.confidence.enum | ForEach-Object { [string]$_ })

    $lines = [System.IO.File]::ReadAllLines($Path, [System.Text.Encoding]::UTF8)
    $nonEmptyCount = 0

    for ($index = 0; $index -lt $lines.Length; $index++) {
        $lineNumber = $index + 1
        $line = [string]$lines[$index]
        if (-not $line.Trim()) {
            $warnings += "Riga $lineNumber vuota: verra ignorata."
            continue
        }

        $nonEmptyCount++
        $trimmed = $line.Trim()
        if ($trimmed.StartsWith('```')) {
            $errors += "Riga ${lineNumber}: code fence Markdown non ammesso."
            continue
        }
        if (-not $trimmed.StartsWith('{') -or -not $trimmed.EndsWith('}')) {
            $errors += "Riga ${lineNumber}: ogni record JSONL deve iniziare con { e terminare con }."
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
        } elseif ($candidateIds.ContainsKey($candidateId)) {
            $errors += "Riga ${lineNumber}: candidate_id duplicato: $candidateId"
        } else {
            $candidateIds[$candidateId] = $true
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
        if ($assertionType -and $allowedAssertionTypes.Count -gt 0 -and $assertionType -notin $allowedAssertionTypes) {
            $errors += "Riga ${lineNumber}: assertion_type non ammesso: $assertionType"
        }

        $confidence = [string](Get-JsonPropertyValue -Object $obj -Name 'confidence')
        if ($confidence -and $allowedConfidence.Count -gt 0 -and $confidence -notin $allowedConfidence) {
            $errors += "Riga ${lineNumber}: confidence non ammessa: $confidence"
        }

        $specific = $null
        if ($recordType) {
            $specificProperty = $schema.record_specific_required_fields.PSObject.Properties[$recordType]
            if ($null -ne $specificProperty) {
                $specific = @($specificProperty.Value)
            }
        }

        foreach ($requiredName in @($specific)) {
            $value = Get-JsonPropertyValue -Object $obj -Name ([string]$requiredName)
            if (Test-MissingJsonValue -Value $value) {
                $errors += "Riga ${lineNumber}: campo specifico mancante/vuoto: $requiredName"
            } elseif (Test-UnresolvedSemanticPlaceholder -Value $value) {
                $errors += "Riga ${lineNumber}: placeholder non risolto nel campo $requiredName."
            }
        }

        if ($candidateId -and (Test-UnresolvedSemanticPlaceholder -Value $candidateId)) {
            $errors += "Riga ${lineNumber}: candidate_id contiene un placeholder."
        }

        $revisionId = [string](Get-JsonPropertyValue -Object $obj -Name 'source_revision_id')
        if ($revisionId -and -not $knownRevisions.ContainsKey($revisionId)) {
            $errors += "Riga ${lineNumber}: source_revision_id non presente nel package: $revisionId"
        }

        $chunkId = [string](Get-JsonPropertyValue -Object $obj -Name 'chunk_id')
        $fragmentId = [string](Get-JsonPropertyValue -Object $obj -Name 'fragment_id')
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
            $revisionId -and $chunkId -and $knownChunks.ContainsKey($chunkId) -and
            [string]$chunkRevision[$chunkId] -ne $revisionId
        ) {
            $errors += "Riga ${lineNumber}: $chunkId appartiene a $($chunkRevision[$chunkId]), non a $revisionId."
        }
        if (
            $revisionId -and $fragmentId -and $knownFragments.ContainsKey($fragmentId) -and
            [string]$fragmentRevision[$fragmentId] -ne $revisionId
        ) {
            $errors += "Riga ${lineNumber}: $fragmentId appartiene a $($fragmentRevision[$fragmentId]), non a $revisionId."
        }

        $evidenceText = [string](Get-JsonPropertyValue -Object $obj -Name 'evidence_text')
        if (-not $evidenceText) {
            $errors += "Riga ${lineNumber}: evidence_text mancante/vuoto."
        } else {
            $evidenceFound = $false
            if ($chunkId -and $knownChunks.ContainsKey($chunkId)) {
                $evidenceFound = Test-EvidenceTextInPackageSection `
                    -Content $content `
                    -EvidenceId $chunkId `
                    -EvidenceText $evidenceText
            }
            if (-not $evidenceFound -and $fragmentId -and $knownFragments.ContainsKey($fragmentId)) {
                $evidenceFound = Test-EvidenceTextInPackageSection `
                    -Content $content `
                    -EvidenceId $fragmentId `
                    -EvidenceText $evidenceText
            }
            if (-not $evidenceFound) {
                $label = if ($candidateId) { $candidateId } else { "riga $lineNumber" }
                $errors += "Riga ${lineNumber} ($label): evidence_text non e' una sottostringa letterale dell'evidenza referenziata."
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
    $text = (($lines -join "`n") + "`n")
    $tmp = $Destination + '.tmp.' + [guid]::NewGuid().ToString('N')
    [System.IO.File]::WriteAllText($tmp, $text, $script:Utf8NoBom)
    Move-Item -LiteralPath $tmp -Destination $Destination -Force
}

function Write-AiRepairPrompt {
    param(
        [Parameter(Mandatory)][string]$BasePromptPath,
        [Parameter(Mandatory)][string]$Destination,
        [Parameter(Mandatory)][string[]]$Errors
    )

    $base = [System.IO.File]::ReadAllText($BasePromptPath, [System.Text.Encoding]::UTF8)
    $errorText = ($Errors | ForEach-Object { '- ' + $_ }) -join "`n"
    $repair = @"
The previous AI response FAILED the local DSL Manager preflight.
Do not explain the errors. Regenerate the complete JSONL output according to the original
contract below and return ONLY corrected JSONL.

LOCAL PREFLIGHT ERRORS
$errorText

ORIGINAL STRICT CONTRACT
$base
"@
    [System.IO.File]::WriteAllText($Destination, $repair, $script:Utf8NoBom)
}

function Extract-LabeledInteger {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$Label
    )

    $pattern = '(?m)^' + [regex]::Escape($Label) + ':\s*(\d+)\s*$'
    $match = [regex]::Match($Text, $pattern)
    if ($match.Success) { return [int]$match.Groups[1].Value }
    return $null
}

function Invoke-Step6AiRoundTrip {
    Write-Title "FASE 6/11 - Round-trip AI: intervento umano, inbox e import"
    Write-Why `
        -What "Ti consegno package, prompt e template; tu fai elaborare il package a una AI esterna; poi Vega valida localmente il JSONL e lo importa." `
        -Why "Questa e' la frontiera reale del sistema: DSL Manager governa evidenze e validazione, mentre il passaggio alla AI resta esplicito e controllato dall'umano." `
        -Expected "Un file AIPKG_*_candidates.jsonl sintatticamente valido, almeno un candidato accettato e un CBATCH reale."

    $workspacePath = [string]$script:State.workspace
    $packageId = [string]$script:State.package_id
    if (-not $packageId) { throw "Manca package_id nello stato. Completa prima la fase 5." }

    if (Test-ActionDone 'ai.roundtrip.import') {
        Write-Host "Round-trip AI gia importato." -ForegroundColor Green
        Write-Host "Batch:    $($script:State.ai_import_batch_id)"
        Write-Host "Accepted: $($script:State.ai_import_accepted)"
        Write-Host "Rejected: $($script:State.ai_import_rejected)"
        Complete-Step -Step 6
        return
    }

    $kit = Write-AiHumanHandoffKit -WorkspacePath $workspacePath -PackageId $packageId

    Write-Host ""
    Write-Host "PASSAGGIO UMANO OBBLIGATORIO" -ForegroundColor Yellow
    Write-Host "1. Apri una chat nuova con QUALSIASI AI capace di leggere file."
    Write-Host "2. Fornisci tutti i file della cartella package:" 
    Write-Host "   $($kit.PackageDir)" -ForegroundColor Cyan
    Write-Host "3. Fornisci anche questo prompt:" 
    Write-Host "   $($kit.PromptPath)" -ForegroundColor Cyan
    Write-Host "4. Se l'AI ha dubbi sulla forma, fornisci anche il template originale:" 
    Write-Host "   $($kit.TemplatePath)" -ForegroundColor Cyan
    Write-Host "5. Salva la risposta come:" 
    Write-Host "   $($kit.ExpectedInbox)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Il tutor NON corregge semanticamente la risposta della AI." -ForegroundColor DarkYellow
    Write-Host "Prima dell'import controlla pero' JSONL, ID, placeholder ed evidence_text letterale."

    $candidateSource = $kit.ExpectedInbox
    if (-not (Test-Path -LiteralPath $candidateSource -PathType Leaf)) {
        Write-Host ""
        $choice = (Read-Host "Invio = controlla il percorso standard; P = stampa il prompt; Q = torna al menu; oppure incolla il percorso assoluto del .jsonl").Trim()

        if ($choice.ToUpperInvariant() -eq 'Q') {
            Write-Host "Fase 6 lasciata incompleta. Potrai riprenderla senza rigenerare il package." -ForegroundColor Yellow
            return
        }

        if ($choice.ToUpperInvariant() -eq 'P') {
            Write-Title "PROMPT DA DARE ALLA AI"
            Get-Content -LiteralPath $kit.PromptPath -Encoding UTF8
            Write-Host ""
            Write-Host "Salva poi la risposta in: $($kit.ExpectedInbox)" -ForegroundColor Yellow
            return
        }

        if ($choice) {
            $expanded = [Environment]::ExpandEnvironmentVariables($choice.Trim().Trim('"'))
            if (-not [System.IO.Path]::IsPathRooted($expanded)) {
                throw "Il percorso della risposta AI deve essere assoluto."
            }
            $candidateSource = [System.IO.Path]::GetFullPath($expanded)
        }
    }

    if (-not (Test-Path -LiteralPath $candidateSource -PathType Leaf)) {
        Write-Host ""
        Write-Host "La risposta AI non e' ancora presente." -ForegroundColor Yellow
        Write-Host "Atteso: $($kit.ExpectedInbox)"
        Write-Host "La fase resta incompleta: puoi chiudere e riprenderla piu tardi."
        return
    }

    Write-Host ""
    Write-Host "Preflight locale della risposta AI..." -ForegroundColor Cyan
    $preflight = Test-AiCandidateJsonl -Path $candidateSource -PackageDir $kit.PackageDir

    foreach ($warning in @($preflight.Warnings)) {
        Write-Host "WARN: $warning" -ForegroundColor DarkYellow
    }

    if (-not $preflight.Valid) {
        $reportPath = Join-Path $kit.KitDir 'PREFLIGHT_ERRORI.txt'
        $repairPath = Join-Path $kit.KitDir 'PROMPT_CORREZIONE_AI.txt'
        [System.IO.File]::WriteAllLines($reportPath, [string[]]$preflight.Errors, $script:Utf8NoBom)
        Write-AiRepairPrompt `
            -BasePromptPath $kit.PromptPath `
            -Destination $repairPath `
            -Errors ([string[]]$preflight.Errors)

        Write-Host "RISPOSTA AI NON IMPORTATA." -ForegroundColor Red
        Write-Host "Il preflight ha trovato $(@($preflight.Errors).Count) problema/i." -ForegroundColor Yellow
        foreach ($errorText in @($preflight.Errors | Select-Object -First 12)) {
            Write-Host "  - $errorText"
        }
        if (@($preflight.Errors).Count -gt 12) {
            Write-Host "  ... altri errori nel report."
        }
        Write-Host ""
        Write-Host "Report completo: $reportPath"
        Write-Host "Prompt di correzione pronto: $repairPath"
        Write-Host "Ridai alla AI package + PROMPT_CORREZIONE_AI.txt, sostituisci il JSONL e rilancia la fase 6." -ForegroundColor Yellow
        return
    }

    # Canonicalizza soltanto il trasporto: un oggetto compatto per riga, UTF-8 senza BOM.
    # Non cambia il significato dei candidati.
    Write-CanonicalJsonl -Objects $preflight.Objects -Destination $kit.ExpectedInbox
    $script:State.ai_candidate_path = $kit.ExpectedInbox
    $script:State.ai_response_sha256 = (
        Get-FileHash -LiteralPath $kit.ExpectedInbox -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    Save-State

    Write-Host "Preflight OK: $($preflight.RecordCount) record JSONL." -ForegroundColor Green
    Write-Host "Risposta canonica: $($kit.ExpectedInbox)"
    Write-Host ""
    Write-Host "CONTROLLO UMANO PRIMA DELL'IMPORT" -ForegroundColor Yellow
    Write-Host "Il file e' formalmente coerente con il package, ma l'import scrivera' candidati nel database."
    Write-Host "Invio = importa adesso; V = mostra le prime 5 righe; Q = torna al menu senza importare."
    $humanChoice = (Read-Host "Scelta").Trim().ToUpperInvariant()
    if ($humanChoice -eq 'Q') {
        Write-Host "Import rimandato. Il JSONL validato resta in: $($kit.ExpectedInbox)" -ForegroundColor Yellow
        return
    }
    if ($humanChoice -eq 'V') {
        Write-Host ""
        Get-Content -LiteralPath $kit.ExpectedInbox -Encoding UTF8 | Select-Object -First 5
        Write-Host ""
        $confirm = (Read-Host "Invio = importa; Q = torna al menu").Trim().ToUpperInvariant()
        if ($confirm -eq 'Q') {
            Write-Host "Import rimandato. Il JSONL validato resta in: $($kit.ExpectedInbox)" -ForegroundColor Yellow
            return
        }
    }

    $scan = Invoke-Dsl -Label 'AI inbox scan' -Arguments @(
        'ai', 'inbox', 'scan', $workspacePath
    )
    Require-Success $scan 'AI inbox scan fallito.'

    $import = Invoke-Dsl -Label 'AI candidate import' -Arguments @(
        'ai', 'import', $workspacePath,
        '--package', $packageId
    )
    Require-Success $import 'Import della risposta AI fallito.'

    $runId = Extract-LastId -Text $import.Stdout -Prefix 'RUN'
    $batchId = Extract-LastId -Text $import.Stdout -Prefix 'CBATCH'
    $total = Extract-LabeledInteger -Text $import.Stdout -Label 'Total'
    $accepted = Extract-LabeledInteger -Text $import.Stdout -Label 'Accepted'
    $rejected = Extract-LabeledInteger -Text $import.Stdout -Label 'Rejected'

    if (-not $runId -or -not $batchId -or $null -eq $total -or $null -eq $accepted -or $null -eq $rejected) {
        throw "Import concluso ma non riesco a ricavare RUN/CBATCH/Total/Accepted/Rejected dall'output. Leggi il log completo."
    }

    $script:State.ai_import_run_id = $runId
    $script:State.ai_import_batch_id = $batchId
    $script:State.ai_import_total = $total
    $script:State.ai_import_accepted = $accepted
    $script:State.ai_import_rejected = $rejected
    Save-State

    if ($accepted -le 0) {
        throw @"
L'import ha creato $batchId ma non ha accettato alcun candidato.
Total=$total Accepted=$accepted Rejected=$rejected

Il round-trip non e' dimostrato. Consulta i rifiuti prima di proseguire.
NON reimportare alla cieca lo stesso file se in futuro ci sono candidati gia accettati.
"@
    }

    Complete-Action 'ai.roundtrip.import'
    Complete-Step -Step 6

    Write-Host ""
    Write-Host "ROUND-TRIP AI COMPLETATO" -ForegroundColor Green
    Write-Host "Package:  $packageId"
    Write-Host "Run:      $runId"
    Write-Host "Batch:    $batchId"
    Write-Host "Total:    $total"
    Write-Host "Accepted: $accepted"
    Write-Host "Rejected: $rejected"

    if ($rejected -gt 0) {
        Write-Host ""
        Write-Host "Nota didattica: alcuni candidati semanticamente rifiutati NON annullano il round-trip." -ForegroundColor Yellow
        Write-Host "Il file era formalmente valido e il validatore ha applicato il proprio contratto record per record."
        Write-Host "Non reimportare il file completo: i candidati accettati sono gia nel database."
    }
}

function Invoke-Step7ReviewInspect {
    Write-Title "FASE 7/11 - Ispezione e decisione umana della review"
    Write-Why `
        -What "Elenco i candidati pending del batch AI appena importato e, se presenti, mostro automaticamente il primo. Poi sei tu a scegliere se lasciarlo pending, confermarlo o rifiutarlo." `
        -Why "Dopo il round-trip AI, la decisione semantica resta umana. Il tutor propone pending come default ma non impedisce una decisione esplicita." `
        -Expected "Lista leggibile del batch AI e scelta umana esplicita. Invio lascia pending; conferma/rifiuto richiedono actor ID e motivazione."

    $workspacePath = [string]$script:State.workspace

    $listArgs = @(
        'candidates', 'review', 'list', $workspacePath
    )

    if ($script:State.ai_import_batch_id) {
        $aiBatchId = [string]$script:State.ai_import_batch_id
        Write-Host "Filtro la review sul batch AI appena importato: $aiBatchId" -ForegroundColor DarkGray
        $listArgs += @('--batch', $aiBatchId)
    } else {
        Write-Host "Batch AI non presente nello stato: filtro almeno sulla sorgente AI." -ForegroundColor Yellow
        $listArgs += @('--source', 'ai')
    }

    $list = Invoke-Dsl -Label 'pending AI candidates' -Arguments $listArgs
    Require-Success $list 'Impossibile elencare la review dei candidati AI.'

    $candidateId = Extract-FirstId -Text $list.Stdout -Prefix 'CREC'

    if ($candidateId) {
        Write-Host "Scelgo il primo candidato AI per l'ispezione: $candidateId" -ForegroundColor Green

        $show = Invoke-Dsl -Label 'show first pending AI candidate' -Arguments @(
            'candidates', 'review', 'show', $workspacePath, $candidateId
        )
        Require-Success $show 'Impossibile mostrare il candidato AI selezionato.'

        Write-Host ""
        Write-Host "DECISIONE UMANA" -ForegroundColor Yellow
        Write-Host "[Invio/P] Lascia PENDING (default, nessuna mutazione)"
        Write-Host "[C]         CONFERMA il candidato"
        Write-Host "[R]         RIFIUTA il candidato"

        while ($true) {
            $reviewChoice = (Read-Host "Scelta").Trim().ToUpperInvariant()

            if (-not $reviewChoice -or $reviewChoice -eq 'P') {
                Write-Host "Candidato lasciato pending: $candidateId" -ForegroundColor Yellow
                break
            }

            if ($reviewChoice -eq 'C' -or $reviewChoice -eq 'R') {
                $defaultActorId = [string]$env:USERNAME
                if ($defaultActorId) {
                    $actorId = (Read-Host "Actor ID stabile [$defaultActorId]").Trim()
                    if (-not $actorId) {
                        $actorId = $defaultActorId
                    }
                } else {
                    $actorId = ''
                    while (-not $actorId) {
                        $actorId = (Read-Host "Actor ID stabile (obbligatorio)").Trim()
                        if (-not $actorId) {
                            Write-Host "Inserisci un actor ID non vuoto." -ForegroundColor Yellow
                        }
                    }
                }

                $reason = ''
                while (-not $reason) {
                    $reason = (Read-Host "Reason/motivazione (obbligatoria per questa esercitazione)").Trim()
                    if (-not $reason) {
                        Write-Host "Inserisci una motivazione non vuota." -ForegroundColor Yellow
                    }
                }

                if ($reviewChoice -eq 'C') {
                    $decision = Invoke-Dsl -Label 'confirm reviewed AI candidate' -Arguments @(
                        'candidates', 'review', 'confirm',
                        $workspacePath, $candidateId,
                        '--actor-id', $actorId,
                        '--reason', $reason
                    )
                    Require-Success $decision 'Conferma del candidato AI fallita.'
                    Write-Host "Candidato AI confermato: $candidateId" -ForegroundColor Green
                } else {
                    $decision = Invoke-Dsl -Label 'reject reviewed AI candidate' -Arguments @(
                        'candidates', 'review', 'reject',
                        $workspacePath, $candidateId,
                        '--actor-id', $actorId,
                        '--reason', $reason
                    )
                    Require-Success $decision 'Rifiuto del candidato AI fallito.'
                    Write-Host "Candidato AI rifiutato: $candidateId" -ForegroundColor Green
                }

                $showAfter = Invoke-Dsl -Label 'show AI candidate after decision' -Arguments @(
                    'candidates', 'review', 'show', $workspacePath, $candidateId
                )
                Require-Success $showAfter 'La decisione e stata registrata, ma non riesco a rileggere il candidato AI.'
                break
            }

            Write-Host "Scelta non valida. Usa Invio/P, C oppure R." -ForegroundColor Yellow
        }
    } else {
        Write-Host "Nessun candidato AI pending trovato nel batch selezionato. Non e' necessariamente un errore." -ForegroundColor Green
    }

    Complete-Action 'review.inspected'
    Complete-Step -Step 7
}

function Invoke-Step8Reconcile {
    Write-Title "FASE 8/11 - Reconcile"
    Write-Why `
        -What "Riallineo lo stato effettivo con le decisioni attuali usando il comando pubblico." `
        -Why "Evita query SQLite o scritture manuali e verifica il percorso applicativo supportato." `
        -Expected "Exit 0."

    if (-not (Test-ActionDone 'reconcile.run')) {
        $r = Invoke-Dsl -Label 'facts reconcile' -Arguments @(
            'facts', 'reconcile', [string]$script:State.workspace
        )
        Require-Success $r 'facts reconcile fallito.'
        Complete-Action 'reconcile.run'
    } else {
        Write-Host "Checkpoint: reconcile gia completato." -ForegroundColor DarkGray
    }

    Complete-Step -Step 8
}

function Invoke-Step9Exports {
    Write-Title "FASE 9/11 - Snapshot DSL e grafo"
    Write-Why `
        -What "Renderizzo DSL schema 2 e uso il DSL_* reale per esportare il grafo." `
        -Why "Verifico che lo stato consolidato sia serializzabile e consumabile dalle viste derivate." `
        -Expected "Un ID DSL_* e graph export exit 0."

    $workspacePath = [string]$script:State.workspace

    if (-not (Test-ActionDone 'export.dsl')) {
        $render = Invoke-Dsl -Label 'DSL render v2' -Arguments @(
            'dsl', 'render', $workspacePath,
            '--schema-version', '2'
        )
        Require-Success $render 'DSL render fallito.'

        $dslId = Extract-LastId -Text $render.Stdout -Prefix 'DSL'
        if (-not $dslId) {
            throw "Render riuscito ma DSL_* non ricavabile dall'output. Leggi il log completo."
        }

        $script:State.dsl_snapshot_id = $dslId
        Save-State
        Complete-Action 'export.dsl'
    } else {
        Write-Host "Snapshot salvato: $($script:State.dsl_snapshot_id)" -ForegroundColor DarkGray
    }

    if (-not (Test-ActionDone 'export.graph')) {
        $dslId = [string]$script:State.dsl_snapshot_id
        if (-not $dslId) { throw "Manca dsl_snapshot_id nello stato." }

        $graph = Invoke-Dsl -Label 'graph export' -Arguments @(
            'graph', 'export', $workspacePath,
            '--snapshot-id', $dslId,
            '--dynamic'
        )
        Require-Success $graph 'Graph export fallito.'
        Complete-Action 'export.graph'
    } else {
        Write-Host "Checkpoint: grafo gia esportato." -ForegroundColor DarkGray
    }

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

    Write-Host "Avvio UI soltanto su 127.0.0.1:$port"
    Write-Host "stdout UI: $stdout" -ForegroundColor DarkGray
    Write-Host "stderr UI: $stderr" -ForegroundColor DarkGray

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
            if ($process.HasExited) { break }

            try {
                $response = Invoke-WebRequest `
                    -Uri "$base/" `
                    -UseBasicParsing `
                    -TimeoutSec 2
                if ($response.StatusCode -eq 200) {
                    $ready = $true
                    break
                }
            } catch {}

            Start-Sleep -Milliseconds 250
        }

        if (-not $ready) {
            throw "La UI non e' diventata pronta su $base."
        }

        foreach ($route in @('/', '/runs', '/logs', '/snapshots')) {
            $response = Invoke-WebRequest `
                -Uri ($base + $route) `
                -UseBasicParsing `
                -TimeoutSec 5

            if ($response.StatusCode -ne 200) {
                throw "Route UI non valida: $route -> $($response.StatusCode)"
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
    Write-Title "FASE 10/11 - Log e UI locale"
    Write-Why `
        -What "Esporto i log e faccio uno smoke test HTTP della UI su loopback." `
        -Why "Verifico osservabilita e superficie locale senza aprire servizi sulla rete." `
        -Expected "HTML/CSV generati; route principali HTTP 200."

    $workspacePath = [string]$script:State.workspace
    $logsExportDir = Join-Path $workspacePath 'exports\logs'
    if (-not (Test-Path -LiteralPath $logsExportDir)) {
        $null = New-Item -ItemType Directory -Path $logsExportDir -Force
    }

    if (-not (Test-ActionDone 'ui.logs')) {
        $html = Invoke-Dsl -Label 'log table html' -Arguments @(
            'log', 'table', $workspacePath,
            '--format', 'html',
            '--output', (Join-Path $logsExportDir 'events_vega.html')
        )
        Require-Success $html 'Export HTML dei log fallito.'

        $csv = Invoke-Dsl -Label 'log csv' -Arguments @(
            'log', 'csv', $workspacePath,
            '--output', (Join-Path $logsExportDir 'events_vega.csv')
        )
        Require-Success $csv 'Export CSV dei log fallito.'

        Complete-Action 'ui.logs'
    } else {
        Write-Host "Checkpoint: export log gia completato." -ForegroundColor DarkGray
    }

    if (-not (Test-ActionDone 'ui.smoke')) {
        Invoke-UiSmokeTest
        Complete-Action 'ui.smoke'
    } else {
        Write-Host "Checkpoint: smoke test UI gia completato." -ForegroundColor DarkGray
    }

    Complete-Step -Step 10
}

function Invoke-Step11Final {
    Write-Title "FASE 11/11 - Controllo finale"
    Write-Why `
        -What "Rifaccio scan e checksum, poi stampo dove si trova tutto." `
        -Why "Il test e concluso soltanto se le fonti sono ancora immutate e la sessione e riprendibile/auditabile." `
        -Expected "Unchanged=6, hash identici, riepilogo finale."

    $workspacePath = [string]$script:State.workspace

    $scan = Invoke-Dsl -Label 'final corpus scan' -Arguments @(
        'corpus', 'scan', $workspacePath
    )
    Require-Success $scan 'Scan finale fallito.'
    Assert-ScanCount -Text $scan.Stdout -Name 'Unchanged' -Expected 6
    Assert-ScanCount -Text $scan.Stdout -Name 'Added' -Expected 0
    Assert-ScanCount -Text $scan.Stdout -Name 'Modified' -Expected 0
    Assert-ScanCount -Text $scan.Stdout -Name 'Deleted' -Expected 0

    Assert-TreesIdentical `
        -Left ([string]$script:State.source_copy) `
        -Right (Join-Path $workspacePath 'corpus\active')

    Complete-Action 'final.verified'
    Complete-Step -Step 11

    Write-Host ""
    Write-Host "LABORATORIO VEGA COMPLETATO" -ForegroundColor Green
    Write-Host "Sessione:  $($script:State.session_root)"
    Write-Host "Stato:     $script:StatePath"
    Write-Host "Workspace: $workspacePath"
    Write-Host "Log:       $script:LogsDir"
    Write-Host "Export:    $(Join-Path $workspacePath 'exports')"
}

# ---------------------------------------------------------------------------
# 5. Menu / navigazione
# ---------------------------------------------------------------------------

$script:Steps = @(
    [pscustomobject]@{ Number = 1; Name = 'Preflight' },
    [pscustomobject]@{ Number = 2; Name = 'Setup workspace' },
    [pscustomobject]@{ Number = 3; Name = 'Doppio scan' },
    [pscustomobject]@{ Number = 4; Name = 'Consolidamento' },
    [pscustomobject]@{ Number = 5; Name = 'Prepara handoff AI' },
    [pscustomobject]@{ Number = 6; Name = 'Round-trip AI + import' },
    [pscustomobject]@{ Number = 7; Name = 'Ispezione review' },
    [pscustomobject]@{ Number = 8; Name = 'Reconcile' },
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

function Show-SessionHeader {
    Write-Host ""
    Write-Host "Laboratorio Vega Ricambi - tutor interattivo v12" -ForegroundColor Green
    Write-Host "Repository: $script:RepositoryRoot"
    Write-Host "Workspace:  $($script:State.workspace)"
    Write-Host "Stato:      $script:StatePath"
    Write-Host ""
    Write-Host "COMANDO DI RIPRESA (copialo se vuoi chiudere):" -ForegroundColor Yellow
    Write-Host (Get-ResumeCommand)
}

function Show-Menu {
    Show-SessionHeader
    $recommended = Get-RecommendedStep

    Write-Host ""
    Write-Host "FASI" -ForegroundColor Cyan
    foreach ($step in $script:Steps) {
        $done = [string]$step.Number -in @($script:State.completed_steps)
        $marker = if ($done) { '[OK]' } elseif ($step.Number -eq $recommended) { '[->]' } else { '[  ]' }
        Write-Host ("{0} {1,2}. {2}" -f $marker, $step.Number, $step.Name)
    }

    Write-Host ""
    Write-Host "Invio = esegui la fase consigliata ($recommended)"
    Write-Host "1..11 = vai a una fase precisa"
    if (-not (Test-ActionDone 'setup.init')) {
        Write-Host "W = cambia workspace (salvataggio immediato)"
    }
    Write-Host "S = mostra stato e percorsi"
    Write-Host "L = mostra gli ultimi log"
    Write-Host "Q = salva ed esci"
}

function Show-State {
    Write-Title "STATO SESSIONE"
    Write-Host "Sessione:  $($script:State.session_root)"
    Write-Host "Workspace: $($script:State.workspace)"
    Write-Host "Completate: $(@($script:State.completed_steps) -join ', ')"
    Write-Host "Checkpoint: $(@($script:State.completed_actions).Count)"
    Write-Host "Ultimo RUN: $($script:State.last_run_id)"
    Write-Host "AISEL tecnico: $($script:State.technical_plan_id)"
    Write-Host "AISEL dominio: $($script:State.domain_plan_id)"
    Write-Host "AIPKG: $($script:State.package_id)"
    Write-Host "Prompt AI: $($script:State.ai_prompt_path)"
    Write-Host "Risposta AI: $($script:State.ai_candidate_path)"
    Write-Host "Batch AI import: $($script:State.ai_import_batch_id)"
    Write-Host "AI accepted/rejected: $($script:State.ai_import_accepted) / $($script:State.ai_import_rejected)"
    Write-Host "DSL: $($script:State.dsl_snapshot_id)"
    Write-Host "Stato file: $script:StatePath"
    Write-Host "Log: $script:LogsDir"
}

function Show-RecentLogs {
    Write-Title "ULTIMI LOG"
    $files = @(
        Get-ChildItem -LiteralPath $script:LogsDir -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 12
    )

    if (-not $files) {
        Write-Host "Nessun log ancora creato."
        return
    }

    foreach ($file in $files) {
        Write-Host ("{0:yyyy-MM-dd HH:mm:ss}  {1}" -f $file.LastWriteTime, $file.FullName)
    }
}

function Invoke-StepByNumber {
    param([Parameter(Mandatory)][int]$Number)

    # Impedisce di saltare le dipendenze essenziali senza spiegazione.
    if ($Number -gt 1 -and '1' -notin @($script:State.completed_steps)) {
        throw "Prima completa la fase 1 (preflight)."
    }
    if ($Number -gt 2 -and '2' -notin @($script:State.completed_steps)) {
        throw "Prima completa la fase 2 (setup workspace)."
    }
    if ($Number -gt 3 -and '3' -notin @($script:State.completed_steps)) {
        throw "Prima completa la fase 3 (doppio scan)."
    }
    if ($Number -gt 4 -and '4' -notin @($script:State.completed_steps)) {
        throw "Prima completa la fase 4 (consolidamento)."
    }
    if ($Number -gt 5 -and '5' -notin @($script:State.completed_steps)) {
        throw "Prima completa la fase 5 (preparazione handoff AI)."
    }
    if ($Number -gt 6 -and '6' -notin @($script:State.completed_steps)) {
        throw "Prima completa la fase 6 (round-trip AI e import)."
    }

    switch ($Number) {
        1  { Invoke-Step1Preflight }
        2  { Invoke-Step2Setup }
        3  { Invoke-Step3Scans }
        4  { Invoke-Step4Consolidate }
        5  { Invoke-Step5AiHandoff }
        6  { Invoke-Step6AiRoundTrip }
        7  { Invoke-Step7ReviewInspect }
        8  { Invoke-Step8Reconcile }
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
        $choice = (Read-Host "Scelta").Trim().ToUpperInvariant()

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
                if (Test-ActionDone 'setup.init') {
                    Write-Host "Il workspace e' gia inizializzato: non puo essere cambiato nella stessa sessione." -ForegroundColor Yellow
                    continue
                }

                Write-Host "Workspace corrente: $($script:State.workspace)"
                $newPath = (Read-Host "Nuovo percorso assoluto; Invio = annulla").Trim()
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
                Write-Host ""
                Write-Host "Stato salvato." -ForegroundColor Green
                Write-Host "Per riprendere:"
                Write-Host (Get-ResumeCommand)
                exit 0
            }

            default {
                Write-Host "Scelta non riconosciuta. Usa Invio, 1..11, W, S, L o Q." -ForegroundColor Yellow
            }
        }
    }
    catch {
        Save-State
        Write-Host ""
        Write-Host "ERRORE NELLA FASE" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Yellow
        Write-Host ""
        Write-Host "La sessione e' stata salvata. Nessuna fase fallita viene marcata completata." -ForegroundColor Yellow
        Write-Host "Per riprendere:"
        Write-Host (Get-ResumeCommand)
        Write-Host ""
        Write-Host "Consulta anche:"
        Write-Host "  $script:JournalPath"
        Write-Host "  $script:LogsDir"
    }
}
