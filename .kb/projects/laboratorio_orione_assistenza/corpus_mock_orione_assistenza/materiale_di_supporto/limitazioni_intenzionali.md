# Limitazioni intenzionali

## Limiti del corpus

- Orione e' piccolo e didattico; non rappresenta tutte le varianti Oracle.
- La view nel DDL viene conservata e segnalata come statement non supportato;
  tabelle, colonne, PK, FK e indici sono invece nel sottoinsieme corrente.
- Procedure e trigger vengono riconosciuti. Le istruzioni PL/SQL interne piu'
  complesse non sono promosse se il parser non possiede un locator affidabile.
- Il PDF e' minimale ma valido; serve a normalizzazione, chunking e metadata.
- Rumore e ambiguita' sono intenzionali e non vanno “ripuliti” a posteriori.
- Il dominio `.invalid` del link workbook e' riservato e non risolvibile. Il
  laboratorio vieta comunque qualunque dereferenziazione.

## Limiti pubblici dell'applicazione osservata

- `temporal propagate` richiede propagazione esplicita: non eredita intervalli,
  non auto-conferma candidati e accetta target soltanto `fact` o `relation`.
- La configurazione review espone un solo profilo built-in,
  `conservative/1`. Profili custom e parser YAML general-purpose restano fuori
  scope; l'allowlist di un workspace nuovo resta vuota finche' non viene
  applicata intenzionalmente.
- Il batch stampa il report complessivo soltanto alla fine; un worker Docling
  lungo puo' sembrare silenzioso. Il default e' 300 s per worker e il massimo
  accettato e' 600 s; il tempo del batch puo' essere maggiore.
- La selezione stale osservata dipende dallo stato rilevante di fonti,
  revisioni ed evidenze, non dalle sole decisioni di review. Una modifica
  meramente descrittiva della policy non ha invalidato il piano.
- Il modello GEXF dinamico assegna spell ai nodi-fatto e agli archi; gli archi
  di relazione collegano nodi-entita' senza spell propri. Il validatore tratta
  un nodo senza intervalli come non limitante. Il laboratorio verifica inoltre
  che l'intervallo dell'arco sia contenuto negli intervalli di dominio scelti
  per i due fatti, senza fingere che siano gli endpoint XML dell'arco.
- `diagnostics normalization run` espone soltanto lo scenario built-in
  `controlled_partial_success/1`, senza worker arbitrari, con un tentativo e
  senza resume. Dimostra il contratto applicativo partial, non un esito di
  Docling sulla fonte.

## Simulazioni controllate

- `ai_response_orione_assistenza_controllata.jsonl` e' un replay: package,
  inbox, import, review e merge sono reali; non avviene una chiamata al modello.
- Il replay e' valido soltanto se package, ID delle evidenze e testo letterale
  coincidono. In caso contrario va creato un nuovo handoff.
- `workbook_partial_controllato.xlsx` resta una fixture storica valida; non
  viene presentato come fonte operativa e non prova da solo uno stato partial.
- `vbaProject.bin` e' un marcatore binario sintetico e inerte. La prova riguarda
  rilevazione e hash, non l'esecuzione di VBA.

## Confini non negoziabili

Niente rete, niente macro, niente SQL diretto al database del workspace, niente
ID inventati, niente modifiche alle fonti dopo la scansione. Se un passaggio
richiede una capacita' applicativa assente, si salva lo stato e ci si ferma.
