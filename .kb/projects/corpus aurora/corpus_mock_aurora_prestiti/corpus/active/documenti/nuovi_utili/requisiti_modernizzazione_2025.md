# Requisiti di modernizzazione di Aurora Prestiti

Versione approvata il 18 novembre 2025.

## Perimetro

Aurora Prestiti gestisce richieste di prestito personale presentate da clienti maggiorenni. Una richiesta registrata nel sistema è chiamata PraticaPrestito.

Ogni PraticaPrestito appartiene a un solo Cliente. Un Cliente può presentare più pratiche nel tempo.

Ogni pratica approvata genera un piano composto da una o più Rate. Un Pagamento può saldare una sola Rata; una Rata può ricevere più tentativi di pagamento, ma un solo pagamento con esito CONTABILIZZATO.

## Stati correnti

Gli stati ammessi per una PraticaPrestito sono: INSERITA, IN_ISTRUTTORIA, APPROVATA, RIFIUTATA, EROGATA, ESTINTA.

Il passaggio da IN_ISTRUTTORIA ad APPROVATA richiede un importo non superiore a 60000 euro e una durata compresa fra 6 e 84 mesi.

Quando la pratica passa ad APPROVATA, il sistema registra la data di approvazione.

Una pratica RIFIUTATA non può tornare in istruttoria senza l'apertura di una nuova pratica.

## Regole sul cliente

Il cliente è identificato dal codice fiscale. La data di nascita è obbligatoria.

Non è consentito approvare una pratica se il cliente ha meno di 18 anni alla data della richiesta.

## Obiettivi del nuovo sistema

Il nuovo sistema deve conservare la tracciabilità fra regola di business, dato tecnico, schermata e comportamento osservato.

Le informazioni storiche in conflitto non devono essere cancellate: devono essere segnalate per la revisione umana.

