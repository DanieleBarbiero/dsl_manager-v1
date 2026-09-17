# Suggerimenti emersi costruendo Vega

Questi punti non sono requisiti del laboratorio: sono possibili miglioramenti
di DSL Manager o della sua UX.

## 1. `batch consolidate --plan`

Prima di iniziare il lavoro pesante sarebbe molto utile ottenere una tabella
tipo:

```text
revision       file                         action(s)             docling
REV_000001     schema.sql                   parse_ddl             no
REV_000002     manuale.docx                 normalize, chunk      yes
```

In questo modo l'utente saprebbe **prima** quanti file passeranno da Docling.

## 2. `--quiet` / `--summary-json`

Molti comandi producono output ottimo per automazione ma troppo lungo per un
tutor umano.

Una modalità nativa compatta eviterebbe che lo script PowerShell debba
riassumere stdout.

## 3. `doctor WORKSPACE`

Un comando unico potrebbe verificare:

- interprete/versione;
- config;
- migrazioni;
- permessi;
- lock;
- worker disponibili;
- Docling importabile;
- spazio;
- integrità directory.

## 4. `--resume-latest`

Quando esiste un solo run fallito e retryable, il programma potrebbe proporre
esplicitamente il comando di ripresa, mantenendo comunque la conferma umana.

## 5. Envelope errori stabile

Un JSON di errore standard con:

```text
code
message
retryable
run_id
report_path
next_safe_action
```

renderebbe i tutor molto più robusti.

## 6. Smoke test UI nativo

Un comando come:

```text
dsl-manager ui smoke-test WORKSPACE
```

potrebbe avviare loopback, controllare le route e spegnere il server senza
replicare logica di processo in PowerShell.

## 7. Fixture framework

Uno standard di progetto per:

```text
fixture.yaml
sources/
expected/
controlled_failures/
```

renderebbe Aurora, Orione, Vega e futuri laboratori uniformi.

## 8. Checkpoint applicativo, non soltanto del tutor

Il tutor salva "dove era arrivato", ma il prodotto stesso potrebbe esporre una
vista `workflow status` che dica quali capability risultano già soddisfatte nel
workspace.
