# Corpus dimostrativo «Aurora Prestiti»

Questo corpus descrive una piccola applicazione legacy Oracle Forms/PL/SQL per
la gestione di prestiti personali. E' una fixture locale: non contiene dati
personali reali, non richiede rete e non autorizza l'esecuzione di macro.

## Obiettivo della modernizzazione

Il corpus serve a ricostruire entita', regole, relazioni e temporalita' con
evidenza verificabile. Conserva fonti correnti, fonti storiche in conflitto e
rumore intenzionale, cosi' da distinguere fatti confermati, candidati pending e
contraddizioni che richiedono revisione umana.

## Struttura

- `corpus/active/`: 18 fonti originali immutabili da registrare nel workspace;
- `corpus/active/documenti/nuovi_utili/matrice_stati_2025.xlsx`: workbook
  multi-sheet e multi-region con formula e cached value, celle eterogenee,
  merged range, named range, fogli visible/hidden/veryHidden ed external link;
- `corpus/active/documenti/nuovi_utili/calcolo_rate_macro_2025.xlsm`: workbook
  macro-enabled inerte, da rilevare senza eseguire VBA;
- `materiale_di_supporto/fixture_controllate/`: un package malformed, un
  workbook valido destinato al percorso controllato `partial` e una risposta
  AI JSONL controllata da usare soltanto nel relativo handoff di test;
- `materiale_di_supporto/checksums.json`: SHA-256 immutabili delle 18 fonti
  attive e delle tre fixture controllate;
- `materiale_di_supporto/inventario_fonti.csv`: ruolo e azione attesa per ogni
  file;
- `materiale_di_supporto/checklist_risultati_attesi.md`: contratto E2E;
- `materiale_di_supporto/matrice_fixture_attesi.md`: tracciabilita' fra fixture,
  requisito ed expected/test;
- `materiale_di_supporto/guida_dsl_manager_powershell_v_02.md` e
  `materiale_di_supporto/guida_dsl_manager_cmd_v_02.md`: le due guide operative
  correnti, complete e destinate anche a chi non conosce DSL Manager.

## Regole di uso

1. Verificare `checksums.json` prima dello scan.
2. Copiare soltanto `corpus/active/` nel workspace e conservarne i byte.
3. Usare le fixture controllate con comandi o test dedicati: il malformed deve
   fallire in preflight; il partial deve produrre artefatti con stato distinto;
   la risposta AI va copiata nell'inbox soltanto dopo avere verificato package,
   revisione e frammenti attesi.
4. Non dereferenziare external link, non eseguire macro e non chiamare servizi
   di rete o AI reali. La fixture JSONL simula in modo deterministico il solo
   output esterno, mentre package, import, review e merge sono eseguiti realmente.
5. Non promuovere date di documento o segnali discordanti a validita' del
   dominio senza una decisione di review.

Per il ciclo completo seguire una delle due guide presenti in
`materiale_di_supporto/`, in base alla shell utilizzata.
