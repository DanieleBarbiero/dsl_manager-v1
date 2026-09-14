# Laboratorio Orione Assistenza

Orione Assistenza e' un corpus interamente fittizio per collaudare DSL Manager
su una piccola applicazione legacy Oracle Forms/PL/SQL. La storia riguarda
asset, interventi, tecnici, assegnazioni, checklist di chiusura e SLA. Non
contiene persone reali, credenziali, endpoint utilizzabili o macro eseguibili.

## Da dove iniziare

1. Leggere questo file, le
   [limitazioni intenzionali](materiale_di_supporto/limitazioni_intenzionali.md),
   la [matrice delle fixture](materiale_di_supporto/matrice_fixture_attesi.md) e
   la [checklist](materiale_di_supporto/checklist_risultati_attesi.md).
2. Scegliere una delle guide equivalenti:
   [CMD](materiale_di_supporto/guida_dsl_manager_cmd_v_01.md) oppure
   [PowerShell](materiale_di_supporto/guida_dsl_manager_powershell_v_01.md).
3. Usare sempre un workspace temporaneo nuovo, fuori dal repository.
4. Copiare nel workspace soltanto `corpus/active`, mantenendo gli stessi byte.
5. Trattare `fixture_controllate` come materiale di prova, mai come fonte.

Gli esiti del collaudo canonico sono nel
[diario tecnico](materiale_di_supporto/diario_tecnico_validazione.md).

Il file PowerShell interattivo e' un tutor, non un autopilota. Ogni azione del
flusso principale viene eseguita dalla CLI `python -m dsl_mngr`. PowerShell o
CMD servono soltanto per preparare la directory temporanea, confrontare hash,
leggere JSON e verificare HTTP. La propagazione temporale usa l'adapter Python
richiesto dal laboratorio perche' la CLI corrente non offre ancora il relativo
leaf; l'adapter chiama il servizio governato, non accede al database.

## Modello mentale

Una fonte registrata non e' una verita'. Il flusso e': fonte immutabile,
revisione, normalizzazione o frammenti strutturati, candidati, decisione umana,
merge, stato effettivo, snapshot DSL e viste derivate. L'import AI crea
candidati pending; non approva nulla. Una correzione rende superseded il
genitore e crea una sostituzione confermata. Mapping e question possono essere
revisionati ma non diventano fatti o relazioni nel registro effettivo.

La temporalita' segue lo stesso governo. Confermare l'intervallo di una
`source_revision` non lo eredita su un fatto o una relazione. L'utente sceglie
esplicitamente una policy di propagazione; il servizio crea nuovi candidati
`temporal_interval`, poi la review comune decide se materializzarli.

## Storia verificabile

- DDL, XML Forms, PL/SQL e log forniscono struttura tecnica e osservazioni.
- Requisiti e verbale attestano indipendentemente che una checklist obbligatoria
  completa e' necessaria alla chiusura e che le regole correnti decorrono dal
  2026-03-01.
- La frase “tutti entro quattro ore” e' volutamente troppo forte e va corretta
  nel target P1.
- La procedura 2023 ammette auto-assegnazione, ma e' storica e va rifiutata per
  il processo corrente.
- PDF 2025 e matrice 2026 espongono valori SLA diversi senza cancellare la
  validita' storica.
- Sistema ticket esterno, sospensione SLA e riassegnazione rimangono incerti.
- Parcheggio e arredi sono rumore recente e storico.

## Sicurezza delle fixture binarie

`build_orione_assistenza_fixtures.py` rigenera DOCX, XLSX, XLSM, PPTX, PDF e le
fixture workbook senza rete. Ogni membro ZIP OOXML usa l'epoch 1980-01-01.
`calcolo_sla_macro_2026.xlsm` contiene `xl/vbaProject.bin`, ma il payload e' un
marcatore inerte, hashato e mai eseguito. Il link esterno del workbook usa il
dominio riservato `.invalid`, viene inventariato e non deve essere dereferenziato.

`workbook_malformed_controllato.xlsx` serve al rifiuto preflight.
`workbook_partial_controllato.xlsx` e' un workbook valido associato a una
risposta `partial_success` di worker controllato: la CLI pubblica non consente
di iniettare quel worker. Entrambi restano fuori da `corpus/active`.

## Risultato finale minimo

Il laboratorio e' riuscito quando il secondo scan e' invariato, i parser non
falliscono, il percorso AI mostra conferma/rifiuto/correzione, due supporti
convergono sullo stesso fatto, la temporalita' e' propagata a due fatti e una
relazione, il DSL v2 contiene intervalli, il GEXF dinamico contiene spell di
nodo e arco, il caso orphan fallisce in strict mode, log e UI sono leggibili e
nessun hash delle fonti e' cambiato.
