# AI Package Content AIPKG_000002

Use only the evidence blocks below.

## Evidence CHK_000001

- source_id: SRC_000003
- source_revision_id: REV_000003
- source_path: corpus/active/documenti/manuale_operativo_orione_2026.md
- source_type: unknown
- authority_level: unknown
- evidence_kind: chunk
- chunk_id: CHK_000001
- sequence: 1
- text_hash: c5b1eba79c4a4f721424da9e39d4f4213883818033d545d23bfb22559ff8d631
- truncated: false

```text
# Manuale operativo Orione Assistenza

effective\_from: 2026-01-15

## Scopo e lessico

Orione Assistenza gestisce interventi di manutenzione su asset industriali. Un Asset è identificato dalla matricola; un Intervento descrive una richiesta di lavoro; un Tecnico può essere assegnato a più interventi; una Voce di checklist documenta una verifica eseguita durante un intervento.

Nel linguaggio degli operatori, “ticket” e “intervento” indicano lo stesso concetto. Il codice applicativo e il database usano il termine INTERVENTO. La schermata principale mostra la matricola dell'asset, la priorità, lo stato e il tecnico assegnato.

## Apertura e assegnazione

Ogni intervento appartiene a un solo asset. Alla creazione lo stato è APERTO e la priorità è BASSA, MEDIA o ALTA. Un intervento ad alta priorità deve essere assegnato entro due ore a un tecnico con livello almeno 3. Il responsabile di turno può riassegnare il tecnico, ma deve conservare la motivazione nell'audit.

La funzione “Assegna” della form aggiorna il tecnico e porta lo stato ad ASSEGNATO. La procedura PRC\_ASSEGNA\_TECNICO implementa l'aggiornamento tecnico; la relazione fra il pulsante della form e la procedura non è espressa nel DDL.

## Checklist e chiusura

Prima della chiusura devono essere presenti almeno le voci SICUREZZA e COLLAUDO, entrambe con esito OK. La chiusura valida porta lo stato a CHIUSO e registra CHIUSO\_IL. Un intervento senza checklist completa deve rimanere IN\_LAVORAZIONE.

Il manuale richiede che sia l'operatore a premere “Chiudi”. Nel codice legacy esiste però un trigger chiamato TRG\_CHIUDI\_INTERVENTO: occorre verificare se effettui una chiusura automatica e se ciò contraddica la procedura operativa.

## Modernizzazione e domande aperte

Nel nuovo servizio il termine pubblico sarà WorkOrder, mentre la tabella legacy rimarrà INTERVENTO durante la migrazione. La corrispondenza WorkOrder ↔ INTERVENTO è una proposta di mapping, non un cambio di schema già approvato.

Non è chiaro se i tecnici di livello 2 con certificazione temporanea possano gestire priorità ALTA. La fonte corrente non definisce né il periodo né l'autorità che concede l'eccezione: la questione deve restare aperta.
```

## Evidence CHK_000002

- source_id: SRC_000004
- source_revision_id: REV_000004
- source_path: corpus/active/documenti/nota_sla_orione_2026.docx
- source_type: unknown
- authority_level: unknown
- evidence_kind: chunk
- chunk_id: CHK_000002
- sequence: 1
- text_hash: 162bc6928643332def6435648fdc5f048cf14a55a6d090bc152be211e594c156
- truncated: false

```text
# Nota SLA Orione

effective\_date: 2026-01-15

## Priorità alta

Gli interventi ad alta priorità devono essere presi in carico entro due ore da un tecnico con livello almeno 3. La presa in carico e la chiusura sono eventi distinti.

## Chiusura

La checklist SICUREZZA e la checklist COLLAUDO devono entrambe avere esito OK. Questa nota conferma il manuale 2026 ma non chiarisce le certificazioni temporanee.
```

## Evidence CHK_000003

- source_id: SRC_000005
- source_revision_id: REV_000005
- source_path: corpus/active/documenti/procedura_storica_chiusura_2023.html
- source_type: unknown
- authority_level: unknown
- evidence_kind: chunk
- chunk_id: CHK_000003
- sequence: 1
- text_hash: bcfab4c7a9f3362cc1d08f0d3c522ab52612614f812c924afbca691b911a077e
- truncated: false

```text
# Procedura storica di chiusura

Questa procedura è stata pubblicata il 10 gennaio 2023 .

## Regola precedente

L'operatore poteva chiudere un intervento anche con la sola voce SICUREZZA in stato OK. La verifica COLLAUDO era facoltativa per gli asset non critici.

## Nota di superamento

La procedura è storica. Il manuale operativo 2026 richiede sia SICUREZZA sia COLLAUDO e deve essere valutato come fonte corrente.
```

## Evidence FRAG_000014

- source_id: SRC_000007
- source_revision_id: REV_000007
- source_path: corpus/active/logs/esecuzione_interventi_2026.log
- source_type: log
- authority_level: runtime_observation
- evidence_kind: fragment
- fragment_id: FRAG_000014
- fragment_type: log_event
- path_or_selector: log/line:1
- sequence: 1
- text_hash: 129eea60f0f55e3cf4513981aa489b5ab0065f24c194cf89b84e8dc35482067d
- truncated: false

```text
2026-02-03 08:10:00 INFO scheduler Avvio coda work order batch_id=BATCH-77
```

## Evidence FRAG_000015

- source_id: SRC_000007
- source_revision_id: REV_000007
- source_path: corpus/active/logs/esecuzione_interventi_2026.log
- source_type: log
- authority_level: runtime_observation
- evidence_kind: fragment
- fragment_id: FRAG_000015
- fragment_type: log_event
- path_or_selector: log/line:2
- sequence: 2
- text_hash: b7aea39c0876c65acf1f678aad5c84835eed712f0a39c569a9d7a16998520045
- truncated: false

```text
2026-02-03 08:10:02 INFO assignment Intervento assegnato intervention_id=INT-104 technician_id=TEC-9 priority=ALTA
```

## Evidence FRAG_000016

- source_id: SRC_000007
- source_revision_id: REV_000007
- source_path: corpus/active/logs/esecuzione_interventi_2026.log
- source_type: log
- authority_level: runtime_observation
- evidence_kind: fragment
- fragment_id: FRAG_000016
- fragment_type: log_event
- path_or_selector: log/line:4
- sequence: 3
- text_hash: 12755b8cc6411996ff493244f33bea628ac3e1206ee2951483939ad79b7e3cab
- truncated: false

```text
2026-02-03 09:42:17 WARN closure Checklist incompleta intervention_id=INT-104 missing=COLLAUDO
```

## Evidence FRAG_000017

- source_id: SRC_000007
- source_revision_id: REV_000007
- source_path: corpus/active/logs/esecuzione_interventi_2026.log
- source_type: log
- authority_level: runtime_observation
- evidence_kind: fragment
- fragment_id: FRAG_000017
- fragment_type: log_event
- path_or_selector: log/line:5
- sequence: 4
- text_hash: b031d2d6f0786c1575a56c7f13ea46289fe2ae210e31cfaeae0d89984800ac80
- truncated: false

```text
2026-02-03 10:05:44 INFO closure Intervento chiuso intervention_id=INT-105 status=CHIUSO
```
