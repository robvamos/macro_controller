# Piano Di Evoluzione

Aggiornato: 2026-07-14

## Stato Corrente

Completati in questa iterazione:

- preview GUI read-only del motore `GoalInterpretation` e `GamePlan`;
- planner conservativo: gli effetti restano potenziali fino a una receipt e a una nuova osservazione;
- pulsante Stop normale visibile e attivo durante registrazione o playback;
- compatibilita Pillow nella cattura e nella guardia visiva senza API deprecate.
- campagne semantiche indipendenti dal playback: una macro puo' essere candidata,
  revisionata o validata per uno scopo, con asset, versione e snapshot della sequenza;
  i run supervisionati raccolgono stato prima/dopo senza promuovere automaticamente la macro.

## Blocco Di Rilascio

1. `data/macro_recorder.db` e' stato riconciliato con backup dei tre stage Git, confronto schema e merge logico: la copia corrente e due sessioni ANTARTIKA mancanti sono preservate. Restano da recuperare o ricatturare gli elementi grafici 229-342 referenziati da una sessione storica, assenti dalla controparte del conflitto.
2. Separare dati seed dai database runtime: mantenere versionati solo dataset riproducibili; ignorare WAL/SHM e database di apprendimento; offrire export/import per i dati personali.
3. Introdurre migrazioni ordinate per il database macro, con tabella schema-version e transazioni, prima di qualsiasi nuova modifica allo schema legacy.

## Prossimo Ciclo

1. Collegare la versione del runtime Doomsday alla pianificazione. Un piano sensibile alla versione deve indicare mismatch o blocco, non usare silenziosamente il registry 1.56.0 con il client 1.58.0.
2. Esporre il workflow roster live in modalita supervisionata: cattura, proposta OCR con provenienza, revisione umana, commit e refresh della tab Roster Campo.
3. Rendere atomico il salvataggio delle Scheduled Tasks e della sequenza macro mediante un unico servizio transazionale.
4. Aggiungere alla tab Grafo UI i controlli per creare, ordinare e rimuovere link macro, con conferma e test di persistenza.
5. Introdurre retry differiti, limite tentativi e stato dead-letter per l'outbox delle evidenze.

## Stabilizzazione

1. Validare `ProviderContribution` richiedendo `source_ref` e timestamp osservabile per le fonti esterne.
2. Creare un ambiente Python riproducibile, con dipendenze bloccate, smoke test installazione e build wheel.
3. Aggiungere CI per test, compilazione Python, audit dipendenze e build del pacchetto Windows.
4. Completare il builder Windows con entry point, inclusione esplicita di config/dataset e test di avvio su installazione pulita.
5. Aggiungere test Tk headless per bootstrap delle tab, stati dei comandi e superfici di errore/riprova.
