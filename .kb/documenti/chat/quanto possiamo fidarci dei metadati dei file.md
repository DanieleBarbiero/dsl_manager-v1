# Quanto possiamo fidarci?

> **Conversation created:** 2026-03-03T22:00:00.000Z
>
> exported_at: 2026-09-01T09:13:14.549Z
>
> source_url: https://chatgpt.com/c/6a969551-2b88-83eb-b126-8b4d2af31078

## User

Web search

esistono metadati nei formati file principali (.pdf, .docx, .pptx, .html, .md, .txt, excel, ecc.) che permettano di avere un'idea della timeline di esistenza del file, senza affidarsi alle date di creazione / modifica che sono dipendente dagli spostamenti, dal sistema operativo e dalle operazioni di copia? puoi redarre una tabella, nel caso?

Show moreShow less

## Assistant

Sì. In diversi formati esistono **timestamp e altri indizi temporali incorporati nel contenuto del file**, quindi indipendenti da `ctime`/`mtime` del filesystem. Se copi un `.docx` da Windows a Linux, su NAS, ZIP, cloud ecc., questi metadati in genere restano invariati finché il documento non viene risalvato o riconvertito.

La distinzione fondamentale è però questa: **sono ottimi indizi storici, non prove crittografiche**. Quasi tutti possono essere modificati intenzionalmente, e alcuni programmi li azzerano, li ricreano o li aggiornano in modi non perfettamente coerenti.

### Quadro generale

| Formato | Metadati temporali interni | Altri indizi di timeline | Sopravvivono a copia/spostamento? | Utilità pratica |
| --- | --- | --- | --- | --- |
| **PDF** | `CreationDate`, `ModDate`; XMP `CreateDate`, `ModifyDate`, `MetadataDate` | `DocumentID`, `InstanceID`, PDF File ID, eventuali **incremental updates** con revisioni precedenti ancora fisicamente presenti | **Sì** | **Molto alta** |
| **DOCX** | `dcterms:created`, `dcterms:modified`, `lastPrinted` | `revision`, `creator`, `lastModifiedBy`, Total Edit Time, timestamp delle entry ZIP | **Sì** | **Alta** |
| **PPTX** | Come DOCX | Come DOCX | **Sì** | **Alta** |
| **XLSX** | Come DOCX | Come DOCX | **Sì** | **Alta** |
| **DOC / XLS / PPT legacy** | Creation time, Last Save time, Last Printed | Revision number, Total Edit Time, Last Author, application | **Sì** | **Alta** |
| **ODT / ODS / ODP** | `meta:creation-date`, `dc:date` | `print-date`, `editing-duration`, `editing-cycles`, initial creator, generator | **Sì** | **Alta** |
| **EPUB** | `dcterms:modified`; eventualmente `dc:date` come data di pubblicazione | identifier, generator e altri Dublin Core | **Sì** | **Medio-alta** |
| **HTML** | Nessuna data storica universale prevista dal formato HTML | Schema.org `dateCreated`, `dateModified`, `datePublished`, oppure metadata CMS/custom | **Sì, se presenti** | **Variabile** |
| **Markdown `.md`** | Nessuna nel Markdown/CommonMark standard | YAML/TOML/JSON front matter con `date`, `created`, `modified`, ecc., se usato dal software | **Sì** | **Bassa-media** |
| **TXT** | Nessuna | Solo convenzioni inserite nel testo | — | **Nulla** |
| **CSV** | Nessuna | Eventuali header/commenti proprietari | — | **Nulla** |

## PDF: probabilmente il formato più interessante

Un PDF può contenere sia il vecchio **Document Information Dictionary**:

```
/CreationDate (D:20210314124211+01'00)
/ModDate      (D:20240824101532+02'00)
```

sia metadata XMP, fra cui tipicamente:

```
xmp:CreateDate
xmp:ModifyDate
xmp:MetadataDate
xmp:CreatorTool
xmpMM:DocumentID
xmpMM:InstanceID
```

Lo standard PDF prevede esplicitamente `CreationDate` e `ModDate`; XMP aggiunge un secondo livello di informazioni.  [[Adobe Open Source+1\]](https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/PDF32000_2008.pdf?utm_source=chatgpt.com) [[Errata for PDF specifications\]](https://pdf-issues.pdfa.org/32000-2-2020/clause14.html?utm_source=chatgpt.com) [[Adobe Open Source+1\]](https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/pdfreference1.3.pdf?utm_source=chatgpt.com) [[Microsoft Learn+1\]](https://learn.microsoft.com/en-us/office/open-xml/general/how-to-create-a-package?utm_source=chatgpt.com) [[Microsoft Learn+1\]](https://learn.microsoft.com/is-is/dotnet/api/documentformat.openxml.packaging.ipackageproperties?view=openxml-3.0.0&utm_source=chatgpt.com) [[ExifTool\]](https://www.exiftool.org/TagNames/OOXML.html?utm_source=chatgpt.com) [[PKWARE Support+1\]](https://support.pkware.com/pkzip/appnote?utm_source=chatgpt.com) [[Microsoft Learn+1\]](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-oleps/f7933d28-2cc4-4b36-bc23-8861cbcd37c4?utm_source=chatgpt.com) [[OASIS Documentation+1\]](https://docs.oasis-open.org/office/OpenDocument/part3-schema/OpenDocument-v1.4-os-part3-schema.html?utm_source=chatgpt.com) [[html.spec.whatwg.org\]](https://html.spec.whatwg.org/multipage/semantics.html?utm_source=chatgpt.com) [[Schema.org+2Schema.org+2\]](https://schema.org/CreativeWork?utm_source=chatgpt.com) [[CommonMark Discussion+1\]](https://talk.commonmark.org/t/front-matter-best-practice/2235?utm_source=chatgpt.com) [[W3C\]](https://www.w3.org/TR/epub-33/?utm_source=chatgpt.com) [[ExifTool+1\]](https://exiftool.org/forum/index.php?topic=15578.0&utm_source=chatgpt.com)

Particolarmente interessante è `DocumentID`: l'ID originario dovrebbe rimanere stabile attraverso gli aggiornamenti del PDF, mentre l'altro identificatore del file cambia con gli aggiornamenti. Questo può aiutare a riconoscere **versioni successive dello stesso documento**. [[Errata for PDF specifications\]](https://pdf-issues.pdfa.org/32000-2-2020/clause14.html?utm_source=chatgpt.com)

Ancora più interessante: PDF supporta gli **incremental updates**. Un programma può salvare le modifiche aggiungendole in fondo al file anziché riscrivere tutto; in tal caso il PDF può conservare fisicamente le revisioni precedenti. La specifica dice esplicitamente che gli aggiornamenti vengono appesi lasciando intatto il contenuto precedente. [[Adobe Open Source+1\]](https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/pdfreference1.3.pdf?utm_source=chatgpt.com)

Quindi un PDF potrebbe raccontare qualcosa del tipo:

```
CreateDate        2018-04-12
prima struttura   2018...
incremental save  2020...
incremental save  2022...
ModifyDate        2022-11-03
```

Questo è decisamente più interessante del semplice `mtime` del file.

---

## DOCX / PPTX / XLSX

I tre formati Office moderni sono essenzialmente **pacchetti ZIP contenenti XML**. [[Microsoft Learn+1\]](https://learn.microsoft.com/en-us/office/open-xml/general/how-to-create-a-package?utm_source=chatgpt.com)

Dentro trovi normalmente:

```
docProps/core.xml
```

con proprietà come:

```
<dc:creator>...</dc:creator>
<cp:lastModifiedBy>...</cp:lastModifiedBy>
<cp:revision>...</cp:revision>

<dcterms:created>2020-04-15T10:20:00Z</dcterms:created>
<dcterms:modified>2024-07-02T17:32:00Z</dcterms:modified>

<cp:lastPrinted>...</cp:lastPrinted>
```

Microsoft definisce esplicitamente `Created`, `Modified`, `LastPrinted`, `LastModifiedBy` e `Revision`; quest'ultima è intesa come numero di revisioni/save, anche se è l'applicazione a essere responsabile del suo aggiornamento. [[Microsoft Learn+1\]](https://learn.microsoft.com/is-is/dotnet/api/documentformat.openxml.packaging.ipackageproperties?view=openxml-3.0.0&utm_source=chatgpt.com)

ExifTool, per esempio, estrae da OOXML anche:

- `CreateDate`
- `ModifyDate`
- `LastPrinted`
- `LastModifiedBy`
- `RevisionNumber`
- `TotalEditTime`
- `Application`
- `AppVersion`
- `Template`

[[ExifTool\]](https://www.exiftool.org/TagNames/OOXML.html?utm_source=chatgpt.com)

C'è poi un secondo livello interessante: essendo ZIP, **le singole entry interne possiedono timestamp ZIP**. Questi non sono la stessa cosa di `dcterms:created`. Quindi puoi ottenere, per esempio:

```
core.xml:
    created       2017-06-03
    modified      2022-01-10

ZIP container:
    core.xml      2022-01-10
    document.xml  2022-01-10
    styles.xml    2019-05-14
```

Le discrepanze possono diventare indizi utili. Naturalmente un semplice repackaging dello ZIP può riscrivere questi valori, quindi li considererei **evidenza secondaria**, non una data certa. OOXML usa formalmente ZIP come tecnologia di packaging. [[PKWARE Support+1\]](https://support.pkware.com/pkzip/appnote?utm_source=chatgpt.com)

---

## Vecchi `.doc`, `.xls`, `.ppt`

Paradossalmente sono anch'essi piuttosto interessanti.

I vecchi formati Office basati su OLE Compound File hanno un flusso:

```
\005SummaryInformation
```

con campi standardizzati come:

| Campo | Significato |
| --- | --- |
| `PIDSI_CREATE_DTM` | creazione del documento |
| `PIDSI_LASTSAVE_DTM` | ultimo salvataggio |
| `PIDSI_LASTPRINTED` | ultima stampa |
| `PIDSI_EDITTIME` | tempo totale di editing |
| `PIDSI_REVNUMBER` | numero revisione |
| `PIDSI_LASTAUTHOR` | ultimo autore/editor |
| `PIDSI_APPNAME` | applicazione creatrice |

Sono definiti esplicitamente nella specifica Microsoft OLE Property Set. [[Microsoft Learn+1\]](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-oleps/f7933d28-2cc4-4b36-bc23-8861cbcd37c4?utm_source=chatgpt.com)

Quindi anche un `.xls` del 2002 copiato dieci volte negli anni può ancora dichiarare internamente qualcosa come:

```
Created:       2002-09-14
Last saved:    2007-03-22
Last printed:  2005-11-03
Revision:      47
Edit time:     18h 42m
Last author:   Mario Rossi
```

mentre Windows magari dice banalmente:

```
Created: 2026-08-30
Modified: 2007-03-22
```

Il primo insieme è molto più interessante per ricostruire la storia del documento.

---

## OpenDocument: ODT / ODS / ODP

Anche qui la situazione è piuttosto buona.

La specifica ODF prevede nel metadata XML:

```
meta:creation-date
dc:date
meta:print-date
meta:initial-creator
dc:creator
meta:editing-cycles
meta:editing-duration
meta:generator
```

e specifica esplicitamente che `meta:creation-date` è la creazione del documento e `dc:date`, quando compare nei metadata del documento, è la sua ultima modifica. [[OASIS Documentation+1\]](https://docs.oasis-open.org/office/OpenDocument/part3-schema/OpenDocument-v1.4-os-part3-schema.html?utm_source=chatgpt.com)

Interessanti anche:

```
editing-cycles
editing-duration
```

perché non sono date, ma possono corroborare una storia del tipo «questo documento esiste da tempo ed è stato lavorato più volte». La specifica ODF prevede esplicitamente anche il tempo totale di editing. [[OASIS Documentation+1\]](https://docs.oasis-open.org/office/OpenDocument/part3-schema/OpenDocument-v1.4-os-part3-schema.html?utm_source=chatgpt.com)

---

## HTML

Qui cambia completamente la situazione.

HTML può contenere moltissimi metadata, ma lo standard HTML non definisce un equivalente universale di:

```
fileCreated
fileModified
```

fra i suoi nomi standard di `<meta>`. [[html.spec.whatwg.org\]](https://html.spec.whatwg.org/multipage/semantics.html?utm_source=chatgpt.com)

Una pagina può però includere structured data Schema.org:

```
{
  "@type": "Article",
  "dateCreated": "2019-01-10",
  "datePublished": "2019-02-01",
  "dateModified": "2024-03-12"
}
```

Schema.org definisce espressamente tutte e tre queste proprietà. [[Schema.org+2Schema.org+2\]](https://schema.org/CreativeWork?utm_source=chatgpt.com)

Oppure potresti trovare:

```
<meta name="date" ...>
<meta property="article:published_time" ...>
<meta name="last-modified" ...>
```

ma qui entriamo nelle convenzioni di CMS/framework/sito, non nel formato HTML stesso.

Quindi per un `.html` salvato localmente la risposta è essenzialmente **«forse»**.

---

## Markdown

Qui la risposta è ancora più netta: **Markdown non possiede metadata temporali standard**.

YAML front matter:

```
---
created: 2021-04-04
modified: 2024-06-17
author: Daniele
---
```

è molto comune, ma non è CommonMark. Gli stessi maintainers di CommonMark hanno chiarito che il front matter è una convenzione che le singole applicazioni possono implementare, non parte della specifica. [[CommonMark Discussion+1\]](https://talk.commonmark.org/t/front-matter-best-practice/2235?utm_source=chatgpt.com)

Quindi:

```
foo.md
```

senza front matter è sostanzialmente un file di testo: **nessuna timeline intrinseca**.

Lo stesso vale per TXT e normalmente CSV.

---

## EPUB

Caso interessante perché EPUB 3 è molto più prescrittivo.

Il Package Document deve contenere **esattamente un**:

```
<meta property="dcterms:modified">
    2026-01-01T12:34:56Z
</meta>
```

con l'ultima modifica; `dc:date`, se presente, indica invece la **data di pubblicazione**, non l'ultima modifica. [[W3C\]](https://www.w3.org/TR/epub-33/?utm_source=chatgpt.com)

È quindi un buon formato per inferire almeno:

```
publication date
        ↓
last package modification
```

anche dopo mille copie del file.

---

# Quanto possiamo fidarci?

Io userei questa gerarchia:

| Evidenza | Forza come indicatore storico |
| --- | --- |
| Firma digitale + trusted timestamp | ★★★★★ |
| Vecchie revisioni effettivamente presenti nel file | ★★★★☆ |
| Metadata interni provenienti da più fonti concordanti | ★★★★☆ |
| `created` / `modified` interno singolo | ★★★☆☆ |
| revision count / editing time / lastPrinted | ★★★☆☆ |
| timestamp ZIP interni | ★★☆☆☆–★★★☆☆ |
| front matter HTML/Markdown dichiarato dall'autore | ★★☆☆☆ |
| filesystem creation time | ★☆☆☆☆ |

La cosa importante è **correlare gli indizi**, anziché cercare «la data».

Un documento Office, per esempio, potrebbe presentare:

```
dcterms:created        2016-04-02
creator                Alice

dcterms:modified       2023-11-14
lastModifiedBy         Bob
revision               81
TotalEditTime          1347 min
lastPrinted            2021-08-10

ZIP timestamps         2023-11-14

filesystem created     2026-08-30
filesystem modified    2023-11-14
```

In questo caso **2016 come inizio della vita del documento diventa abbastanza plausibile**, anche se il file fisico presente sul disco è stato copiato lì solo nel 2026.

Al contrario:

```
created          2004
modified         2004
revision         1
ZIP timestamps   2026
Application      LibreOffice 26
filesystem       2026
```

farebbe sospettare che il documento sia stato **creato/reimpacchettato nel 2026 con metadata che dichiarano 2004**, o che sia stato sottoposto a una conversione.

### Un dettaglio importante sui PDF

Qui si può andare anche oltre la semplice plausibilità. Se trovi una sequenza di **incremental updates**, le revisioni precedenti sono realmente byte presenti nel file: la specifica PDF stabilisce che gli aggiornamenti incrementali vengono aggiunti senza riscrivere il contenuto precedente. [[Adobe Open Source+1\]](https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/pdfreference1.3.pdf?utm_source=chatgpt.com)

Quindi, per ricostruire una timeline documentale, personalmente considererei **PDF, OOXML e ODF nettamente superiori** a HTML/Markdown/TXT.

Per un'ispezione rapida trasversale, uno strumento particolarmente comodo è ExifTool:

```
exiftool -time:all -a -G1 -s documento.pdf
```

e più in generale:

```
exiftool -a -G1 -s documento.docx
```

L'opzione `-time:all` è utile proprio perché mostra separatamente i vari timestamp invece di confondere quelli embedded con quelli del filesystem. [[ExifTool+1\]](https://exiftool.org/forum/index.php?topic=15578.0&utm_source=chatgpt.com)

La conclusione quindi è: **sì, per PDF e documenti Office/OpenDocument è spesso possibile costruire una timeline interna sorprendentemente ricca e molto meno sensibile agli spostamenti del file rispetto alle date del filesystem; per HTML è intermittente, per Markdown/TXT/CSV praticamente nulla salvo convenzioni esplicite.**

## Links

- [Adobe Open Source+1]: https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/PDF32000_2008.pdf?utm_source=chatgpt.com
- [Errata for PDF specifications]: https://pdf-issues.pdfa.org/32000-2-2020/clause14.html?utm_source=chatgpt.com
- [Adobe Open Source+1]: https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/pdfreference1.3.pdf?utm_source=chatgpt.com
- [Microsoft Learn+1]: https://learn.microsoft.com/en-us/office/open-xml/general/how-to-create-a-package?utm_source=chatgpt.com
- [Microsoft Learn+1]: https://learn.microsoft.com/is-is/dotnet/api/documentformat.openxml.packaging.ipackageproperties?view=openxml-3.0.0&utm_source=chatgpt.com
- [ExifTool]: https://www.exiftool.org/TagNames/OOXML.html?utm_source=chatgpt.com
- [PKWARE Support+1]: https://support.pkware.com/pkzip/appnote?utm_source=chatgpt.com
- [Microsoft Learn+1]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-oleps/f7933d28-2cc4-4b36-bc23-8861cbcd37c4?utm_source=chatgpt.com
- [OASIS Documentation+1]: https://docs.oasis-open.org/office/OpenDocument/part3-schema/OpenDocument-v1.4-os-part3-schema.html?utm_source=chatgpt.com
- [html.spec.whatwg.org]: https://html.spec.whatwg.org/multipage/semantics.html?utm_source=chatgpt.com
- [Schema.org+2Schema.org+2]: https://schema.org/CreativeWork?utm_source=chatgpt.com
- [CommonMark Discussion+1]: https://talk.commonmark.org/t/front-matter-best-practice/2235?utm_source=chatgpt.com
- [W3C]: https://www.w3.org/TR/epub-33/?utm_source=chatgpt.com
- [ExifTool+1]: https://exiftool.org/forum/index.php?topic=15578.0&utm_source=chatgpt.com