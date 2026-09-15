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
