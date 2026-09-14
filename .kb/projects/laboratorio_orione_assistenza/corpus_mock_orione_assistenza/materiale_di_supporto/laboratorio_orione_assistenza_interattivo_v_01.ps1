[CmdletBinding()]
param(
    [Parameter()]
    [string]$ResumeSession,

    [Parameter()]
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Find-RepositoryRoot {
    param([Parameter(Mandatory)][string]$Start)
    $cursor = [System.IO.DirectoryInfo]::new([System.IO.Path]::GetFullPath($Start))
    while ($null -ne $cursor) {
        $agents = Join-Path $cursor.FullName 'AGENTS.md'
        $project = Join-Path $cursor.FullName 'pyproject.toml'
        $config = Join-Path $cursor.FullName '.codex\config.toml'
        if ((Test-Path -LiteralPath $agents -PathType Leaf) -and
            (Test-Path -LiteralPath $project -PathType Leaf) -and
            (Test-Path -LiteralPath $config -PathType Leaf)) {
            return $cursor.FullName
        }
        $cursor = $cursor.Parent
    }
    throw 'Root non trovata: servono AGENTS.md, pyproject.toml e .codex/config.toml.'
}

function Resolve-ProjectPython {
    param([Parameter(Mandatory)][string]$RepositoryRoot)
    $configPath = Join-Path $RepositoryRoot '.codex\config.toml'
    $text = [System.IO.File]::ReadAllText($configPath, [System.Text.Encoding]::UTF8)
    $match = [regex]::Match($text, '(?m)^\s*PROJECT_PYTHON\s*=\s*"([^"]+)"\s*$')
    if (-not $match.Success) {
        throw "PROJECT_PYTHON assente in $configPath. Correggere la configurazione; non verra' usato Python globale."
    }
    $configured = $match.Groups[1].Value
    $candidate = if ([System.IO.Path]::IsPathRooted($configured)) {
        $configured
    }
    else {
        Join-Path $RepositoryRoot $configured
    }
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw "Interprete configurato non trovato: $candidate"
    }
    $resolved = (Resolve-Path -LiteralPath $candidate).Path
    $version = & $resolved --version 2>&1
    if ($LASTEXITCODE -ne 0 -or ($version -join ' ') -notmatch '^Python 3\.12(?:\.|\s|$)') {
        throw "Serve Python 3.12; risposta osservata: $($version -join ' ')"
    }
    return $resolved
}

$script:RepositoryRoot = Find-RepositoryRoot -Start $PSScriptRoot
$script:ProjectPython = Resolve-ProjectPython -RepositoryRoot $script:RepositoryRoot
$script:LabRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$script:CanonicalCorpus = Join-Path $script:LabRoot 'corpus\active'
$script:Adapter = Join-Path $PSScriptRoot 'promuovi_temporalita_orione_assistenza.py'
$script:Replay = Join-Path $PSScriptRoot 'fixture_controllate\ai_response_orione_assistenza_controllata.jsonl'

foreach ($required in @($script:CanonicalCorpus, $script:Adapter, $script:Replay)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Input del laboratorio assente: $required"
    }
}

if ($ValidateOnly) {
    [ordered]@{
        status = 'valid'
        repository_root = $script:RepositoryRoot
        project_python = $script:ProjectPython
        python_version = (& $script:ProjectPython --version 2>&1) -join ' '
        lab_root = $script:LabRoot
    } | ConvertTo-Json -Depth 4
    exit 0
}

function New-OrioneSession {
    $root = Join-Path ([System.IO.Path]::GetTempPath()) ('orione_assistenza_' + [guid]::NewGuid().ToString('N'))
    if (Test-Path -LiteralPath $root) {
        throw "Collisione inattesa sulla sessione: $root"
    }
    $null = New-Item -ItemType Directory -Path $root
    $workspace = Join-Path $root 'workspace'
    $sourceCopy = Join-Path $root 'input_active'
    $null = New-Item -ItemType Directory -Path $sourceCopy
    $journal = Join-Path $root 'diario_esecuzione.md'
    $commands = Join-Path $root 'commands.log'
    [System.IO.File]::WriteAllText(
        $journal,
        "# Diario esecuzione Orione Assistenza`n`nSessione creata: $([DateTimeOffset]::Now.ToString('o'))`n",
        $script:Utf8NoBom
    )
    [System.IO.File]::WriteAllText($commands, '', $script:Utf8NoBom)
    return [ordered]@{
        schema_version = 1
        session_root = $root
        workspace = $workspace
        source_copy = $sourceCopy
        phase = 'created'
        ids = [ordered]@{}
        decisions = @()
        ui_pid = $null
        created_at = [DateTimeOffset]::Now.ToString('o')
        updated_at = [DateTimeOffset]::Now.ToString('o')
    }
}

function Import-OrioneSession {
    param([Parameter(Mandatory)][string]$Path)
    $root = [System.IO.Path]::GetFullPath($Path)
    $statePath = Join-Path $root 'session_state.json'
    foreach ($required in @($statePath, (Join-Path $root 'diario_esecuzione.md'), (Join-Path $root 'commands.log'))) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "Sessione non riprendibile, artefatto assente: $required"
        }
    }
    $loaded = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
    if ([System.IO.Path]::GetFullPath([string]$loaded.session_root) -ne $root) {
        throw 'session_state.json appartiene a una directory diversa.'
    }
    return $loaded
}

$script:State = if ($ResumeSession) {
    Import-OrioneSession -Path $ResumeSession
}
else {
    New-OrioneSession
}
$script:StatePath = Join-Path ([string]$script:State.session_root) 'session_state.json'
$script:JournalPath = Join-Path ([string]$script:State.session_root) 'diario_esecuzione.md'
$script:CommandsPath = Join-Path ([string]$script:State.session_root) 'commands.log'

function Save-State {
    $script:State.updated_at = [DateTimeOffset]::Now.ToString('o')
    $json = $script:State | ConvertTo-Json -Depth 30
    [System.IO.File]::WriteAllText($script:StatePath, $json + "`n", $script:Utf8NoBom)
}

function Write-Journal {
    param([Parameter(Mandatory)][string]$Text)
    $line = "`n## $([DateTimeOffset]::Now.ToString('o'))`n`n$Text`n"
    [System.IO.File]::AppendAllText($script:JournalPath, $line, $script:Utf8NoBom)
}

function Add-Decision {
    param([Parameter(Mandatory)][string]$Decision)
    $script:State.decisions = @($script:State.decisions) + @([ordered]@{
        at = [DateTimeOffset]::Now.ToString('o')
        value = $Decision
    })
    Write-Journal -Text "Decisione utente: $Decision"
    Save-State
}

function Add-ObservedIds {
    param([Parameter(Mandatory)][string]$Text)
    foreach ($match in [regex]::Matches($Text, '(?<![A-Z])(RUN|REV|AISEL|AIPKG|CBATCH|CREC|DSL)_\d{6}')) {
        $prefix = $match.Groups[1].Value
        $value = $match.Value
        if (-not $script:State.ids.Contains($prefix)) {
            $script:State.ids[$prefix] = @()
        }
        if ($value -notin @($script:State.ids[$prefix])) {
            $script:State.ids[$prefix] = @($script:State.ids[$prefix]) + @($value)
        }
    }
    Save-State
}

function Format-CommandLine {
    param([Parameter(Mandatory)][string]$File, [Parameter(Mandatory)][string[]]$Arguments)
    $shown = foreach ($argument in $Arguments) {
        if ($argument -match '[\s"]') { '"' + $argument.Replace('"', '\"') + '"' } else { $argument }
    }
    return ('"' + $File + '" ' + ($shown -join ' '))
}

function Invoke-LoggedProcess {
    param(
        [Parameter(Mandatory)][string]$File,
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter()][switch]$LongRunning
    )
    $commandLine = Format-CommandLine -File $File -Arguments $Arguments
    Write-Host "`nCOMANDO: $commandLine" -ForegroundColor Cyan
    $started = [DateTimeOffset]::Now
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $File
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = $script:Utf8NoBom
    $psi.StandardErrorEncoding = $script:Utf8NoBom
    foreach ($argument in $Arguments) { $null = $psi.ArgumentList.Add($argument) }
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $psi
    $null = $process.Start()
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $nextNotice = 10
    while (-not $process.HasExited) {
        Start-Sleep -Milliseconds 250
        if ($LongRunning) {
            $elapsed = [int]([DateTimeOffset]::Now - $started).TotalSeconds
            if ($elapsed -ge $nextNotice) {
                Write-Host "Tempo trascorso: $elapsed s. Il worker Docling usa 300 s di default; massimo configurabile 600 s." -ForegroundColor DarkYellow
                $nextNotice += 10
            }
        }
    }
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    $finished = [DateTimeOffset]::Now
    if ($stdout) { Write-Host $stdout.TrimEnd() }
    if ($stderr) { Write-Host $stderr.TrimEnd() -ForegroundColor DarkYellow }
    $logRecord = [ordered]@{
        started_at = $started.ToString('o')
        finished_at = $finished.ToString('o')
        command = $commandLine
        stdout = $stdout
        stderr = $stderr
        exit_code = $process.ExitCode
    } | ConvertTo-Json -Compress -Depth 10
    [System.IO.File]::AppendAllText($script:CommandsPath, $logRecord + "`n", $script:Utf8NoBom)
    Add-ObservedIds -Text ($stdout + "`n" + $stderr)
    Write-Journal -Text "Comando: `$commandLine`  `nExit code: $($process.ExitCode)"
    return [pscustomobject]@{
        Command = $commandLine
        Stdout = $stdout
        Stderr = $stderr
        ExitCode = $process.ExitCode
        Elapsed = $finished - $started
    }
}

function Invoke-Dsl {
    param([Parameter(Mandatory)][string[]]$Arguments, [Parameter()][switch]$LongRunning)
    return Invoke-LoggedProcess -File $script:ProjectPython -Arguments (@('-m', 'dsl_mngr') + $Arguments) -LongRunning:$LongRunning
}

function Read-StepChoice {
    param(
        [Parameter(Mandatory)][string]$Title,
        [Parameter(Mandatory)][string]$Location,
        [Parameter(Mandatory)][string]$Purpose,
        [Parameter(Mandatory)][string]$Command,
        [Parameter(Mandatory)][string]$Expected,
        [Parameter()][bool]$CanSkip = $true
    )
    Write-Host "`n=== $Title ===" -ForegroundColor Green
    Write-Host "Dove: $Location"
    Write-Host "Perche': $Purpose"
    Write-Host "Comando: $Command" -ForegroundColor Cyan
    Write-Host "Atteso: $Expected"
    while ($true) {
        $options = if ($CanSkip) { '[E]segui [D]ettagli [S]alta [M]enu [Q]esci' } else { '[E]segui [D]ettagli [M]enu [Q]esci' }
        $choice = (Read-Host $options).Trim().ToUpperInvariant()
        switch ($choice) {
            'E' { Add-Decision "${Title}: esegui"; return 'execute' }
            'D' {
                Write-Host "`n$Purpose`nRisultato previsto: $Expected`nIn caso di errore vengono conservati stdout, stderr, exit code e ID; nessun ID viene presunto." -ForegroundColor Gray
            }
            'S' { if ($CanSkip) { Add-Decision "${Title}: salta"; return 'skip' } }
            'M' { Add-Decision "${Title}: menu"; return 'menu' }
            'Q' { Add-Decision "${Title}: esci salvando"; Save-State; return 'quit' }
        }
    }
}

function Confirm-Mutation {
    param([Parameter(Mandatory)][string]$Description)
    $answer = (Read-Host "$Description [S/N]").Trim().ToUpperInvariant()
    $approved = $answer -eq 'S'
    Add-Decision "$Description => $approved"
    return $approved
}

function Set-WorkspaceAllowlist {
    $projectConfig = Join-Path ([string]$script:State.workspace) 'configs\project.yaml'
    $text = [System.IO.File]::ReadAllText($projectConfig, [System.Text.Encoding]::UTF8)
    $policies = @(
        'explicit_ddl_table_only/1',
        'explicit_ddl_column_only/1',
        'explicit_resolved_ddl_fk_only/1',
        'explicit_xml_form_structure_only/1',
        'explicit_xml_operation_only/1',
        'explicit_db_code_unit_only/1',
        'observed_db_code_dependency_only/1',
        'named_explicit_log_policy_required/1',
        'explicit_excel_workbook_only/1',
        'explicit_excel_sheet_only/1',
        'explicit_excel_region_only/1',
        'explicit_excel_named_range_only/1',
        'explicit_excel_table_only/1'
    )
    $body = "  automatic_policies:`n" + (($policies | ForEach-Object { "    - $_" }) -join "`n") + "`n"
    $pattern = '(?ms)(review:\r?\n\s+default_actor_id:[^\r\n]*\r?\n)\s+automatic_policies:.*?(?=derive:)'
    if (-not [regex]::IsMatch($text, $pattern)) {
        throw 'Sezione review.automatic_policies non riconosciuta; non modificata.'
    }
    $updated = [regex]::Replace($text, $pattern, ('$1' + $body))
    [System.IO.File]::WriteAllText($projectConfig, $updated, $script:Utf8NoBom)
}

function Get-RelativeHashMap {
    param([Parameter(Mandatory)][string]$Root)
    $map = [ordered]@{}
    foreach ($file in Get-ChildItem -LiteralPath $Root -Recurse -File | Sort-Object FullName) {
        $relative = $file.FullName.Substring($Root.Length + 1).Replace('\', '/')
        $map[$relative] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    return $map
}

function Assert-IdenticalTrees {
    param([Parameter(Mandatory)][string]$Left, [Parameter(Mandatory)][string]$Right)
    $leftMap = Get-RelativeHashMap -Root $Left
    $rightMap = Get-RelativeHashMap -Root $Right
    $leftJson = $leftMap | ConvertTo-Json -Compress
    $rightJson = $rightMap | ConvertTo-Json -Compress
    if ($leftJson -ne $rightJson) {
        throw 'Checksum discordante. Non eseguire scan: ricopiare in una nuova sessione e conservare la diagnosi.'
    }
    Write-Host "Checksum uguali per $($leftMap.Count) fonti." -ForegroundColor Green
}

function Invoke-Prepare {
    $choice = Read-StepChoice -Title 'Preparazione workspace' -Location ([string]$script:State.session_root) -Purpose 'Crea workspace e DB con leaf pubblici, copia solo le fonti attive e configura una allowlist conservativa nel temporaneo.' -Command 'dsl_mngr init; dsl_mngr db init; copia e checksum; configurazione workspace' -Expected 'Exit 0, 11 migrazioni al primo DB init, 15 fonti byte-identiche.' -CanSkip $false
    if ($choice -in @('menu', 'quit')) { return $choice }
    if (-not (Confirm-Mutation -Description 'Creare il workspace temporaneo e copiarvi le fonti')) { return 'menu' }
    if (Test-Path -LiteralPath ([string]$script:State.workspace)) {
        Write-Host 'Workspace gia presente. Riprendere questa sessione oppure crearne una nuova; nessun file viene sovrascritto.' -ForegroundColor Yellow
        return 'menu'
    }
    $init = Invoke-Dsl -Arguments @('init', [string]$script:State.workspace)
    if ($init.ExitCode -ne 0) { return 'menu' }
    $db = Invoke-Dsl -Arguments @('db', 'init', [string]$script:State.workspace)
    if ($db.ExitCode -ne 0) { return 'menu' }
    Copy-Item -Path (Join-Path $script:CanonicalCorpus '*') -Destination ([string]$script:State.source_copy) -Recurse
    Copy-Item -Path (Join-Path ([string]$script:State.source_copy) '*') -Destination (Join-Path ([string]$script:State.workspace) 'corpus\active') -Recurse
    Assert-IdenticalTrees -Left ([string]$script:State.source_copy) -Right (Join-Path ([string]$script:State.workspace) 'corpus\active')
    Set-WorkspaceAllowlist
    $script:State.phase = 'prepared'
    Save-State
    return 'done'
}

function Invoke-Scans {
    $choice = Read-StepChoice -Title 'Doppio scan' -Location ([string]$script:State.workspace) -Purpose 'Registra le revisioni e prova che un secondo scan immutato non ne crea altre.' -Command 'dsl_mngr corpus scan WORKSPACE (due volte)' -Expected 'Prima Added 15; poi Unchanged 15; exit 0.'
    if ($choice -ne 'execute') { return $choice }
    if (-not (Confirm-Mutation -Description 'Registrare le fonti nel workspace')) { return 'menu' }
    foreach ($pass in 1..2) {
        $result = Invoke-Dsl -Arguments @('corpus', 'scan', [string]$script:State.workspace)
        if ($result.ExitCode -ne 0) {
            Write-Host 'Scan fallito. Controllare checksum/path; non presumere revision ID.' -ForegroundColor Yellow
            return 'menu'
        }
        if ($pass -eq 2 -and $result.Stdout -notmatch 'Unchanged:\s+15') {
            Write-Host 'Secondo scan non immutato: confrontare checksum e ripartire con workspace nuovo.' -ForegroundColor Yellow
            return 'menu'
        }
    }
    $script:State.phase = 'scanned'
    Save-State
    return 'done'
}

function Invoke-Consolidation {
    $choice = Read-StepChoice -Title 'Consolidamento deterministico' -Location ([string]$script:State.workspace) -Purpose 'Normalizza, chunka, estrae, applica l allowlist, fonde e riconcilia usando la pipeline pubblica.' -Command 'dsl_mngr batch consolidate WORKSPACE --reconcile' -Expected 'Exit 0; report per tutti i parser. Docling puo richiedere minuti.'
    if ($choice -ne 'execute') { return $choice }
    if (-not (Confirm-Mutation -Description 'Eseguire la pipeline mutante')) { return 'menu' }
    $result = Invoke-Dsl -Arguments @('batch', 'consolidate', [string]$script:State.workspace, '--reconcile') -LongRunning
    if ($result.ExitCode -ne 0) {
        Write-Host 'Pipeline non completata. Alternative: run status, report/checkpoint, attesa del lock o un solo --resume. Non aumentare automaticamente il timeout.' -ForegroundColor Yellow
        $resume = (Read-Host 'Inserire un RUN reale da riprendere, oppure Invio per tornare al menu').Trim()
        if ($resume) {
            $status = Invoke-Dsl -Arguments @('run', 'status', [string]$script:State.workspace, $resume)
            if ($status.ExitCode -eq 0 -and (Confirm-Mutation -Description 'Eseguire un solo resume consapevole')) {
                $null = Invoke-Dsl -Arguments @('batch', 'consolidate', [string]$script:State.workspace, '--reconcile', '--resume', $resume) -LongRunning
            }
        }
        return 'menu'
    }
    $script:State.phase = 'consolidated'
    Save-State
    return 'done'
}

function Invoke-AiPlans {
    $choice = Read-StepChoice -Title 'Piani di evidenza AI' -Location ([string]$script:State.workspace) -Purpose 'Confronta selezione tecnica e interpretativa e spiega evidenze incluse/escluse.' -Command 'dsl_mngr ai evidence plan/list/explain' -Expected 'Piani AISEL reali; nel corpus v 01: tecnico 11/89, dominio 89/89.'
    if ($choice -ne 'execute') { return $choice }
    foreach ($policy in @('technical_extraction', 'domain_interpretation')) {
        $plan = Invoke-Dsl -Arguments @('ai', 'evidence', 'plan', [string]$script:State.workspace, '--policy', $policy)
        if ($plan.ExitCode -ne 0) { return 'menu' }
        $planId = [regex]::Match($plan.Stdout, 'AISEL_\d{6}').Value
        if (-not $planId) { Write-Host 'ID AISEL non ricavato; salvato output, nessun fallback.'; return 'menu' }
        $included = Invoke-Dsl -Arguments @('ai', 'evidence', 'list', [string]$script:State.workspace, '--plan', $planId, '--outcome', 'included')
        $excluded = Invoke-Dsl -Arguments @('ai', 'evidence', 'list', [string]$script:State.workspace, '--plan', $planId, '--outcome', 'excluded')
        $evidence = [regex]::Match($included.Stdout, '(?:CHK|FRAG)_\d{6}').Value
        if ($evidence) { $null = Invoke-Dsl -Arguments @('ai', 'evidence', 'explain', [string]$script:State.workspace, $evidence, '--plan', $planId) }
        $excludedEvidence = [regex]::Match($excluded.Stdout, '(?:CHK|FRAG)_\d{6}').Value
        if ($excludedEvidence) { $null = Invoke-Dsl -Arguments @('ai', 'evidence', 'explain', [string]$script:State.workspace, $excludedEvidence, '--plan', $planId) }
    }
    $script:State.phase = 'ai_planned'
    Save-State
    return 'done'
}

function Test-ControlledReplay {
    param([Parameter(Mandatory)][string]$PackageDirectory)
    $contentPath = Join-Path $PackageDirectory 'content.md'
    $manifestPath = Join-Path $PackageDirectory 'package_manifest.json'
    if (-not (Test-Path -LiteralPath $contentPath) -or -not (Test-Path -LiteralPath $manifestPath)) { return $false }
    $content = Get-Content -LiteralPath $contentPath -Raw -Encoding UTF8
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($line in Get-Content -LiteralPath $script:Replay -Encoding UTF8) {
        if (-not $line.Trim()) { continue }
        $record = $line | ConvertFrom-Json
        $evidenceId = if ($record.chunk_id) { [string]$record.chunk_id } else { [string]$record.fragment_id }
        if (-not $evidenceId -or $content -notmatch [regex]::Escape($evidenceId) -or $content -notmatch [regex]::Escape([string]$record.evidence_text)) {
            Write-Host "Replay incompatibile con il package $($manifest.package_id): $evidenceId o testo non presente." -ForegroundColor Yellow
            return $false
        }
    }
    return $true
}

function Invoke-AiHandoff {
    $choice = Read-StepChoice -Title 'Package e handoff AI' -Location ([string]$script:State.workspace) -Purpose 'Crea il package dal piano interpretativo, fa leggere tutti i file e mette la sessione in pausa prima dell import.' -Command 'dsl_mngr ai package; lettura package; dsl_mngr ai inbox scan/import' -Expected 'AIPKG waiting_for_ai_candidates; risposta reale oppure replay verificato.'
    if ($choice -ne 'execute') { return $choice }
    $plans = @($script:State.ids['AISEL'])
    if ($plans.Count -eq 0) { Write-Host 'Nessun AISEL osservato: eseguire prima i piani.' -ForegroundColor Yellow; return 'menu' }
    $planId = [string]$plans[-1]
    if (-not (Confirm-Mutation -Description "Creare package dal piano $planId")) { return 'menu' }
    $package = Invoke-Dsl -Arguments @('ai', 'package', [string]$script:State.workspace, '--selection-plan', $planId)
    if ($package.ExitCode -eq 4 -and $package.Stderr -match 'stale') {
        Write-Host 'Piano stale: creare e spiegare un nuovo piano; non usare --allow-stale.' -ForegroundColor Yellow
        return 'menu'
    }
    if ($package.ExitCode -ne 0) { return 'menu' }
    $packageId = [regex]::Match($package.Stdout, 'AIPKG_\d{6}').Value
    if (-not $packageId) { Write-Host 'AIPKG non ricavato; nessun ID presunto.'; return 'menu' }
    $packageDir = Join-Path ([string]$script:State.workspace) "ai\outbox\$packageId"
    foreach ($file in Get-ChildItem -LiteralPath $packageDir -File | Sort-Object Name) {
        Write-Host "`n===== $($file.Name) =====" -ForegroundColor Cyan
        Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 | Write-Host
    }
    $script:State.phase = 'waiting_for_ai_candidates'
    Save-State
    Write-Host 'La sessione e stata salvata. La chiamata a un modello esterno non viene simulata di nascosto.' -ForegroundColor Green
    $mode = (Read-Host '[R]isposta AI reale [C] replay controllato [X] esci e riprendi dopo').Trim().ToUpperInvariant()
    if ($mode -eq 'X') { Add-Decision 'handoff: pausa persistente'; return 'quit' }
    $inputPath = $null
    if ($mode -eq 'R') {
        $provided = (Read-Host 'Percorso del JSONL fornito dall utente').Trim()
        if (-not (Test-Path -LiteralPath $provided -PathType Leaf)) {
            Write-Host 'Risposta assente: stato salvato; fornire un file valido alla ripresa.' -ForegroundColor Yellow
            return 'menu'
        }
        $inputPath = (Resolve-Path -LiteralPath $provided).Path
    }
    elseif ($mode -eq 'C') {
        Write-Host 'REPLAY CONTROLLATO: package/inbox/import/review sono reali; la chiamata al modello non lo e.' -ForegroundColor Yellow
        if (-not (Test-ControlledReplay -PackageDirectory $packageDir)) {
            Write-Host 'Generare un nuovo handoff: non riscrivere gli ID della fixture.' -ForegroundColor Yellow
            return 'menu'
        }
        $inputPath = $script:Replay
    }
    else { return 'menu' }
    if (-not (Confirm-Mutation -Description 'Copiare la risposta in inbox ed eseguire scan/import')) { return 'menu' }
    $inbox = Join-Path ([string]$script:State.workspace) 'ai\inbox'
    $destination = Join-Path $inbox ("${packageId}_candidates.jsonl")
    if (Test-Path -LiteralPath $destination -PathType Leaf) {
        $same = (Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash -eq
            (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
        if (-not $same) {
            Write-Host 'La destinazione inbox esiste con bytes diversi: nessuna sovrascrittura. Usare un nome nuovo e ripetere consapevolmente.' -ForegroundColor Yellow
            return 'menu'
        }
        Write-Host 'La stessa risposta e gia presente byte-identica; non viene sovrascritta.'
    }
    else {
        Copy-Item -LiteralPath $inputPath -Destination $destination
    }
    $scan = Invoke-Dsl -Arguments @('ai', 'inbox', 'scan', [string]$script:State.workspace)
    if ($scan.ExitCode -ne 0) { return 'menu' }
    $import = Invoke-Dsl -Arguments @('ai', 'import', [string]$script:State.workspace, '--package', $packageId)
    if ($import.ExitCode -ne 0) {
        Write-Host 'Import invalido: leggere report/schema, correggere fuori dal workspace e rifare inbox scan. Nessun candidato e stato presunto.' -ForegroundColor Yellow
        return 'menu'
    }
    $script:State.phase = 'ai_imported_pending'
    Save-State
    return 'done'
}

function Invoke-HumanReview {
    $choice = Read-StepChoice -Title 'Review umana' -Location ([string]$script:State.workspace) -Purpose 'Mostra candidati e applica una decisione esplicita con idempotency key; import non equivale a verita.' -Command 'dsl_mngr candidates review list/show/confirm/reject/correct; facts merge-batch/reconcile' -Expected 'Almeno conferma, rifiuto, correzione; parent superseded e replacement confirmed.'
    if ($choice -ne 'execute') { return $choice }
    $list = Invoke-Dsl -Arguments @('candidates', 'review', 'list', [string]$script:State.workspace)
    if ($list.ExitCode -ne 0) { return 'menu' }
    $parsed = $null
    try { $parsed = $list.Stdout | ConvertFrom-Json } catch {}
    if ($null -ne $parsed -and [int]$parsed.count -eq 0) {
        Write-Host 'Nessun pending: verificare package/import o scegliere un altro outcome; non inventare ID.' -ForegroundColor Yellow
        return 'menu'
    }
    $candidateId = (Read-Host 'CREC reale da ispezionare; Invio per tornare').Trim()
    if (-not $candidateId) { return 'menu' }
    $show = Invoke-Dsl -Arguments @('candidates', 'review', 'show', [string]$script:State.workspace, $candidateId)
    if ($show.ExitCode -ne 0) { return 'menu' }
    $action = (Read-Host '[C]onferma [R]ifiuta [O]correggi [P]ending').Trim().ToUpperInvariant()
    if ($action -eq 'P') { Add-Decision "$candidateId lasciato pending"; return 'done' }
    if (-not (Confirm-Mutation -Description "Applicare la review $action a $candidateId")) { return 'menu' }
    $reason = (Read-Host 'Motivazione sostanziale').Trim()
    if (-not $reason) { Write-Host 'Motivazione obbligatoria.'; return 'menu' }
    $key = 'orione-' + $candidateId.ToLowerInvariant() + '-' + [guid]::NewGuid().ToString('N')
    switch ($action) {
        'C' { $result = Invoke-Dsl -Arguments @('candidates','review','confirm',[string]$script:State.workspace,$candidateId,'--reason',$reason,'--actor-id','human_orione','--idempotency-key',$key) }
        'R' { $result = Invoke-Dsl -Arguments @('candidates','review','reject',[string]$script:State.workspace,$candidateId,'--reason',$reason,'--actor-id','human_orione','--idempotency-key',$key) }
        'O' {
            $payloadPath = (Read-Host 'Percorso JSON completo del payload corretto').Trim()
            if (-not (Test-Path -LiteralPath $payloadPath -PathType Leaf)) { Write-Host 'Payload assente.'; return 'menu' }
            $payload = Get-Content -LiteralPath $payloadPath -Raw -Encoding UTF8
            $refs = (Read-Host 'Evidence ID reali separati da virgola').Split(',',[System.StringSplitOptions]::RemoveEmptyEntries).Trim()
            $args = @('candidates','review','correct',[string]$script:State.workspace,$candidateId,'--reason',$reason,'--payload',$payload,'--actor-id','human_orione','--idempotency-key',$key)
            foreach ($ref in $refs) { $args += @('--evidence-ref',$ref) }
            $result = Invoke-Dsl -Arguments $args
        }
        default { return 'menu' }
    }
    if ($result.ExitCode -ne 0) { Write-Host 'Decisione non applicata: usare show, head corrente e una richiesta consapevole.' -ForegroundColor Yellow }
    else {
        $batchInput = (Read-Host 'CBATCH reali confermati da fondere, separati da virgola; Invio per rimandare').Trim()
        if ($batchInput -and (Confirm-Mutation -Description 'Fondere i batch indicati e riconciliare')) {
            $mergeArgs = @('facts','merge-batch',[string]$script:State.workspace)
            foreach ($batch in $batchInput.Split(',',[System.StringSplitOptions]::RemoveEmptyEntries).Trim()) {
                if ($batch -notmatch '^CBATCH_\d{6}$') { Write-Host "Batch invalido: $batch"; return 'menu' }
                $mergeArgs += @('--batch',$batch)
            }
            $merge = Invoke-Dsl -Arguments $mergeArgs
            if ($merge.ExitCode -eq 0) { $null = Invoke-Dsl -Arguments @('facts','reconcile',[string]$script:State.workspace) }
        }
    }
    $script:State.phase = 'review_in_progress'
    Save-State
    return 'done'
}

function Show-RegistryTargets {
    $render = Invoke-Dsl -Arguments @('dsl','render',[string]$script:State.workspace,'--schema-version','2','--output-dir','exports\tutorial_targets')
    if ($render.ExitCode -ne 0) { return $null }
    $pathMatch = [regex]::Match($render.Stdout, '(?m)^JSON:\s+(.+)$')
    if (-not $pathMatch.Success) { return $null }
    $jsonPath = Join-Path ([string]$script:State.workspace) $pathMatch.Groups[1].Value.Trim()
    $dsl = Get-Content -LiteralPath $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host "`nFatti reali disponibili:" -ForegroundColor Cyan
    $dsl.facts | Select-Object fact_id,entity_name,property_name,property_value | Format-Table -AutoSize
    Write-Host "Relazioni reali disponibili:" -ForegroundColor Cyan
    $dsl.relations | Select-Object relation_id,source_entity,relation_type,target_entity | Format-Table -AutoSize
    return $dsl
}

function Invoke-TemporalPromotion {
    $choice = Read-StepChoice -Title 'Promozione temporale governata' -Location ([string]$script:State.workspace) -Purpose 'Mostra target reali, chiama l adapter candidate-first e rimanda ogni intervallo alla review comune.' -Command 'promuovi_temporalita_orione_assistenza.py ...; dsl_mngr candidates review show/confirm/reject' -Expected 'JSON con candidate_record_ids o conflict_id; nessun intervallo approvato automaticamente.'
    if ($choice -ne 'execute') { return $choice }
    $dsl = Show-RegistryTargets
    if ($null -eq $dsl) { Write-Host 'Impossibile mostrare target dal DSL; nessun ID verra presunto.'; return 'menu' }
    Write-Host 'Prima confermare/rifiutare le temporalita delle fonti con i normali comandi review. Confermare date di dominio esplicite; rifiutare first_seen/mtime/ctime/metadata incoerenti; lasciare pending i conflitti.' -ForegroundColor Yellow
    $runId = (Read-Host 'RUN reale da associare alla promozione').Trim()
    $revisionId = (Read-Host 'REV sorgente gia confermata').Trim()
    $targetType = (Read-Host 'Tipo target: fact oppure relation').Trim().ToLowerInvariant()
    $targetId = (Read-Host 'ID target reale mostrato sopra').Trim()
    $policy = (Read-Host 'Policy: explicit_copy, intersection, aggregation oppure conflict').Trim().ToLowerInvariant()
    $sourceInput = (Read-Host 'Sorgenti TYPE:ID separate da virgola; la prima demo usa source_revision:REV').Trim()
    $sources = $sourceInput.Split(',',[System.StringSplitOptions]::RemoveEmptyEntries).Trim()
    if ($runId -notmatch '^RUN_\d{6}$' -or $revisionId -notmatch '^REV_\d{6}$' -or
        $targetType -notin @('fact','relation') -or $targetId -notmatch '^(FACT|REL)_\d{6}$' -or
        $policy -notin @('explicit_copy','intersection','aggregation','conflict') -or $sources.Count -eq 0) {
        Write-Host 'Argomenti non validi. Usare soltanto ID osservati e policy versionate.' -ForegroundColor Yellow
        return 'menu'
    }
    $args = @($script:Adapter,'--workspace',[string]$script:State.workspace,'--run-id',$runId,'--source-revision-id',$revisionId,'--target-subject-type',$targetType,'--target-subject-id',$targetId,'--policy',$policy)
    foreach ($source in $sources) { $args += @('--source-subject',$source) }
    if (-not (Confirm-Mutation -Description "Creare candidati temporali $policy su $targetId")) { return 'menu' }
    $result = Invoke-LoggedProcess -File $script:ProjectPython -Arguments $args
    if ($result.ExitCode -ne 0) {
        Write-Host 'Nessun accesso SQL alternativo: leggere exit semantico, sorgenti e conflict_id; salvare lo stato.' -ForegroundColor Yellow
        return 'menu'
    }
    try { $response = $result.Stdout | ConvertFrom-Json } catch { Write-Host 'JSON adapter invalido; nessun ID presunto.'; return 'menu' }
    if ($response.conflict_id) { Write-Host "Conflitto prodotto: $($response.conflict_id)" -ForegroundColor Yellow }
    $confirmedBatches = @()
    foreach ($candidate in @($response.candidate_record_ids)) {
        $showCandidate = Invoke-Dsl -Arguments @('candidates','review','show',[string]$script:State.workspace,[string]$candidate)
        $candidateBatch = $null
        try { $candidateBatch = [string](($showCandidate.Stdout | ConvertFrom-Json).candidate.batch_id) } catch {}
        $decision = (Read-Host "${candidate}: [C]onferma [R]ifiuta [P]ending").Trim().ToUpperInvariant()
        if ($decision -in @('C','R') -and (Confirm-Mutation -Description "Applicare decisione $decision a $candidate")) {
            $verb = if ($decision -eq 'C') { 'confirm' } else { 'reject' }
            $reviewResult = Invoke-Dsl -Arguments @('candidates','review',$verb,[string]$script:State.workspace,[string]$candidate,'--reason',"Decisione temporale $policy verificata",'--actor-id','human_orione','--idempotency-key',("orione-temporal-$candidate-$verb-v1"))
            if ($decision -eq 'C' -and $reviewResult.ExitCode -eq 0 -and $candidateBatch -match '^CBATCH_\d{6}$') {
                $confirmedBatches += $candidateBatch
            }
        }
    }
    if ($confirmedBatches.Count -gt 0 -and (Confirm-Mutation -Description 'Materializzare i candidati temporali appena confermati e riconciliare')) {
        $mergeArgs = @('facts','merge-batch',[string]$script:State.workspace)
        foreach ($batch in $confirmedBatches) { $mergeArgs += @('--batch',$batch) }
        $merge = Invoke-Dsl -Arguments $mergeArgs
        if ($merge.ExitCode -eq 0) { $null = Invoke-Dsl -Arguments @('facts','reconcile',[string]$script:State.workspace) }
        else { Write-Host 'Merge temporale fallito: ispezionare batch/report, evitare SQL e conservare lo stato.' -ForegroundColor Yellow }
    }
    Write-Host 'Ripetere questa fase per due fatti e una relazione. Per spell reali assegnare allo stesso fatto e alla stessa relazione lo storico chiuso e il corrente aperto; poi fondere i CBATCH reali.' -ForegroundColor Green
    $script:State.phase = 'temporal_review_in_progress'
    Save-State
    return 'done'
}

function Test-SpellBounds {
    param([Parameter(Mandatory)]$NodeSpells, [Parameter(Mandatory)]$EdgeSpells)
    foreach ($edge in $EdgeSpells) {
        $edgeStart = if ($edge.start) { [datetime]$edge.start } else { [datetime]::MinValue }
        $edgeEnd = if ($edge.end) { [datetime]$edge.end } else { [datetime]::MaxValue }
        $contained = $false
        foreach ($node in $NodeSpells) {
            $nodeStart = if ($node.start) { [datetime]$node.start } else { [datetime]::MinValue }
            $nodeEnd = if ($node.end) { [datetime]$node.end } else { [datetime]::MaxValue }
            if ($edgeStart -ge $nodeStart -and $edgeEnd -le $nodeEnd) { $contained = $true; break }
        }
        if (-not $contained) { return $false }
    }
    return $true
}

function Invoke-RenderAndGraph {
    $choice = Read-StepChoice -Title 'DSL, diff e grafi' -Location ([string]$script:State.workspace) -Purpose 'Renderizza schema 1 e 2, prova stabilita byte, diff cross-schema, orphan e GEXF dinamico con spell.' -Command 'dsl_mngr dsl render/diff; dsl_mngr graph export' -Expected 'Intervals v2 non vuote; strict orphan 2 atteso; spell nodo/arco e bounds validi.'
    if ($choice -ne 'execute') { return $choice }
    $v1 = Invoke-Dsl -Arguments @('dsl','render',[string]$script:State.workspace,'--schema-version','1','--output-dir','exports\orione_v1')
    $v2a = Invoke-Dsl -Arguments @('dsl','render',[string]$script:State.workspace,'--schema-version','2','--output-dir','exports\orione_v2_a')
    $v2b = Invoke-Dsl -Arguments @('dsl','render',[string]$script:State.workspace,'--schema-version','2','--output-dir','exports\orione_v2_b')
    if (@($v1.ExitCode,$v2a.ExitCode,$v2b.ExitCode) | Where-Object { $_ -ne 0 }) { return 'menu' }
    $dslV1 = [regex]::Match($v1.Stdout,'DSL_\d{6}').Value
    $dslV2a = [regex]::Match($v2a.Stdout,'DSL_\d{6}').Value
    $dslV2b = [regex]::Match($v2b.Stdout,'DSL_\d{6}').Value
    if (-not $dslV1 -or -not $dslV2a -or -not $dslV2b) { Write-Host 'Snapshot ID non ricavati.'; return 'menu' }
    $null = Invoke-Dsl -Arguments @('dsl','diff',[string]$script:State.workspace,'--from',$dslV1,'--to',$dslV2a,'--cross-schema')
    foreach ($extension in @('json','yaml','md')) {
        $a = Join-Path ([string]$script:State.workspace) "exports\orione_v2_a\$dslV2a.$extension"
        $b = Join-Path ([string]$script:State.workspace) "exports\orione_v2_b\$dslV2b.$extension"
        $stable = (Get-FileHash -LiteralPath $a -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $b -Algorithm SHA256).Hash
        Write-Host "Render $extension byte-stabile: $stable"
        if (-not $stable) { return 'menu' }
    }
    $dslJson = Get-Content -LiteralPath (Join-Path ([string]$script:State.workspace) "exports\orione_v2_a\$dslV2a.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    $intervalCount = @($dslJson.facts.intervals).Count + @($dslJson.relations.intervals).Count
    Write-Host "Intervalli DSL v2: $intervalCount"
    if ($intervalCount -eq 0) { Write-Host 'Zero intervalli: tornare alla promozione/review; non renderizzare marcatori fittizi.' -ForegroundColor Yellow; return 'menu' }
    $null = Invoke-Dsl -Arguments @('graph','export',[string]$script:State.workspace,'--snapshot-id',$dslV1,'--output-dir','exports\graph_static')
    $strict = Invoke-Dsl -Arguments @('graph','export',[string]$script:State.workspace,'--snapshot-id',$dslV1,'--output-dir','exports\graph_strict','--strict-orphans')
    if ($strict.ExitCode -eq 2) { Write-Host 'Exit 2 strict-orphans riconosciuto come fallimento intenzionale.' -ForegroundColor Green } else { Write-Host "Strict orphan inatteso: $($strict.ExitCode)" -ForegroundColor Yellow }
    $dynamic = Invoke-Dsl -Arguments @('graph','export',[string]$script:State.workspace,'--snapshot-id',$dslV2a,'--output-dir','exports\graph_dynamic','--dynamic','--timeformat','date','--temporal-output-mode','strict')
    if ($dynamic.ExitCode -ne 0) { return 'menu' }
    $gexfRelative = [regex]::Match($dynamic.Stdout,'(?m)^GEXF:\s+(.+)$').Groups[1].Value.Trim()
    if (-not $gexfRelative) { Write-Host 'Path GEXF non ricavato.'; return 'menu' }
    [xml]$xml = Get-Content -LiteralPath (Join-Path ([string]$script:State.workspace) $gexfRelative) -Raw -Encoding UTF8
    $ns = [System.Xml.XmlNamespaceManager]::new($xml.NameTable)
    $ns.AddNamespace('g',$xml.DocumentElement.NamespaceURI)
    $nodeSpells = @($xml.SelectNodes('//g:node/g:spells/g:spell',$ns))
    $edgeSpells = @($xml.SelectNodes('//g:edge/g:spells/g:spell',$ns))
    Write-Host "Spell nodo: $($nodeSpells.Count); spell arco: $($edgeSpells.Count)" -ForegroundColor Cyan
    $nodeSpells | Select-Object start,end | Format-Table -AutoSize
    $edgeSpells | Select-Object start,end | Format-Table -AutoSize
    if ($nodeSpells.Count -eq 0 -or $edgeSpells.Count -eq 0) { Write-Host 'Zero spell non soddisfa il laboratorio.' -ForegroundColor Yellow; return 'menu' }
    Write-Host "Contenimento degli spell arco nei bounds nodo mostrati: $(Test-SpellBounds -NodeSpells $nodeSpells -EdgeSpells $edgeSpells)"
    $script:State.phase = 'rendered_and_validated'
    Save-State
    return 'done'
}

function Invoke-LogsAndUi {
    $choice = Read-StepChoice -Title 'Log e UI locale' -Location ([string]$script:State.workspace) -Purpose 'Esporta log con la CLI e verifica in loopback solo le rotte pubbliche, arrestando solo il processo creato.' -Command 'dsl_mngr log table/csv; Start-Process ... dsl_mngr ui serve' -Expected 'HTML/CSV; GET 200 sulle 8 rotte, POST / 405; PID chiuso in finally.'
    if ($choice -ne 'execute') { return $choice }
    $exports = Join-Path ([string]$script:State.workspace) 'exports\tutorial_logs'
    $null = New-Item -ItemType Directory -Path $exports -Force
    $html = Invoke-Dsl -Arguments @('log','table',[string]$script:State.workspace,'--format','html','--output',(Join-Path $exports 'events.html'))
    $csv = Invoke-Dsl -Arguments @('log','csv',[string]$script:State.workspace,'--output',(Join-Path $exports 'events.csv'))
    if ($html.ExitCode -ne 0 -or $csv.ExitCode -ne 0) { return 'menu' }
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,0)
    $listener.Start()
    $port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    $listener.Stop()
    $stdout = Join-Path $exports 'ui_stdout.log'
    $stderr = Join-Path $exports 'ui_stderr.log'
    $arguments = @('-m','dsl_mngr','ui','serve',('"' + [string]$script:State.workspace + '"'),'--host','127.0.0.1','--port',[string]$port)
    $process = $null
    try {
        if (-not (Confirm-Mutation -Description "Avviare UI in loopback sulla porta libera $port")) { return 'menu' }
        $process = Start-Process -FilePath $script:ProjectPython -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        $script:State.ui_pid = $process.Id
        Save-State
        $base = "http://127.0.0.1:$port"
        $ready = $false
        foreach ($attempt in 1..40) {
            try {
                $response = Invoke-WebRequest -Uri "$base/" -Method Get -UseBasicParsing -TimeoutSec 2
                if ($response.StatusCode -eq 200) { $ready = $true; break }
            }
            catch {}
            Start-Sleep -Milliseconds 250
        }
        if (-not $ready) { throw 'Timeout UI: controllare stderr; il processo verra chiuso senza toccarne altri.' }
        $runs = @($script:State.ids['RUN'])
        $routeRun = if ($runs.Count) { [string]$runs[-1] } else { throw 'Nessun RUN reale per /runs/<ID>.' }
        foreach ($route in @('/','/runs',"/runs/$routeRun",'/logs','/rejected-candidates','/conflicts','/snapshots','/diff')) {
            $response = Invoke-WebRequest -Uri ($base + $route) -Method Get -UseBasicParsing -TimeoutSec 5
            Write-Host "GET $route => $($response.StatusCode)"
            if ($response.StatusCode -ne 200) { throw "Status inatteso per $route" }
        }
        try {
            $post = Invoke-WebRequest -Uri "$base/" -Method Post -UseBasicParsing -TimeoutSec 5
            $postCode = $post.StatusCode
        }
        catch { $postCode = [int]$_.Exception.Response.StatusCode.value__ }
        Write-Host "POST / => $postCode"
        if ($postCode -notin @(405,501)) { throw 'POST non e stato rifiutato come atteso.' }
    }
    catch {
        Write-Host $_.Exception.Message -ForegroundColor Yellow
        Write-Host "Diagnostica UI: $stdout e $stderr. Se la porta e occupata scegliere una nuova sessione UI; non terminare processi estranei."
    }
    finally {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit()
        }
        $script:State.ui_pid = $null
        Save-State
    }
    $script:State.phase = 'completed'
    Save-State
    return 'done'
}

Save-State
Write-Host "`nLaboratorio Orione Assistenza" -ForegroundColor Green
Write-Host "Interprete: $script:ProjectPython"
Write-Host "Sessione: $($script:State.session_root)"
Write-Host "Fase salvata: $($script:State.phase)"
Write-Host 'La shell orchestra soltanto aspetti secondari; il flusso applicativo usa sempre DSL Manager.'

$exitRequested = $false
while (-not $exitRequested) {
    Write-Host @'

Menu
  1  prepara workspace, database, fonti e allowlist
  2  esegui due scan
  3  consolida e riconcilia
  4  crea/confronta piani AI
  5  crea package e gestisci handoff
  6  review umana di un candidato
  7  promozione temporale candidate-first
  8  render, diff e grafi
  9  log e UI locale
  S  mostra stato e ID osservati
  Q  esci salvando
'@
    $selection = (Read-Host 'Scelta').Trim().ToUpperInvariant()
    $outcome = switch ($selection) {
        '1' { Invoke-Prepare }
        '2' { Invoke-Scans }
        '3' { Invoke-Consolidation }
        '4' { Invoke-AiPlans }
        '5' { Invoke-AiHandoff }
        '6' { Invoke-HumanReview }
        '7' { Invoke-TemporalPromotion }
        '8' { Invoke-RenderAndGraph }
        '9' { Invoke-LogsAndUi }
        'S' {
            Save-State
            $script:State | ConvertTo-Json -Depth 30 | Write-Host
            'menu'
        }
        'Q' { 'quit' }
        default { 'menu' }
    }
    if ($outcome -eq 'quit') { $exitRequested = $true }
}

Add-Decision 'sessione chiusa o messa in pausa dal menu'
Save-State
Write-Host "Stato salvato in $script:StatePath" -ForegroundColor Green
Write-Host "Ripresa: & '$PSCommandPath' -ResumeSession '$($script:State.session_root)'"
