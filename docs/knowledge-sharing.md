# Condivisione della conoscenza tra workstation

Ogni workstation usa un clone Git autonomo. Il repository GitHub è il punto comune: dopo aver pubblicato e inviato una modifica a `main`, gli altri clone la ricevono con `git pull origin main`. Il programma non sincronizza in rete i profili locali.

## Cosa viene condiviso

- Codice, test, schemi portabili, cataloghi e dati di ricerca revisionati.
- `data/doomsday/knowledge/`: grafo semantico, catalogo di elementi visivi e immagini canoniche, sessioni di apprendimento compattate, osservazioni OCR revisionate e suggerimenti ricavati da sessioni distinte.
- `data/doomsday/intelligence/source_registry.overlay.json`: overlay senza percorsi assoluti.

Il comando `python tools/export_shared_knowledge.py` unisce in modo additivo gli elementi e le sessioni presenti nel database locale al catalogo condiviso. Mantiene gli ID già pubblicati, assegna ID liberi quando due workstation hanno ID SQLite in conflitto, conserva varianti d'immagine e ricalcola i suggerimenti dagli eventi condivisi. Importa inoltre le osservazioni OCR locali, togliendo nomi workstation e percorsi ai frame. Il setup locale importa una sola volta per processo le immagini condivise mancanti, mantenendo intatti elementi con lo stesso nome creati localmente.

## Cosa resta locale

Configurazioni, database SQLite, registro dei runtime, macro utente, log, frame completi, catture di rete, CA e ambienti virtuali restano in `workstation/local/<profilo>/runtime/` o in altre cartelle ignorate elencate in `.gitignore`. Le osservazioni di rete condivisibili contengono solo metadati redatti; payload, header, valori di query e credenziali non fanno parte del flusso.

## Flusso di pubblicazione

1. Aggiorna il clone: `git pull origin main`.
2. Usa l'app o gli strumenti di apprendimento sulla workstation.
3. Quando vuoi pubblicare ciò che è stato appreso, esegui `python tools/export_shared_knowledge.py`.
4. Rivedi `git diff`, soprattutto `data/doomsday/knowledge/`. Verifica che non siano comparsi nomi utente, host, percorsi locali, coordinate schermo grezze o dati non revisionati. I suggerimenti rimangono candidati e non autorizzano l'automazione.
5. Se il diff è corretto, registra e invia il commit su `main`.
6. Sulle altre workstation esegui `git pull origin main`; all'avvio gli elementi visuali canonici vengono aggiunti al database del profilo locale.

L'esportazione non esegue commit o push e non richiede credenziali GitHub al programma. Per osservazioni di battaglia, registry e dossier di ricerca, applica la stessa revisione e registra nel repository solo il contenuto portabile che vuoi condividere. In caso di conflitto Git, conserva entrambe le osservazioni indipendenti e rivedi gli ID del catalogo prima di risolverlo.