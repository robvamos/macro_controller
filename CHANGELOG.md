# Changelog

## 0.11.0 - 2026-07-23

- Semplificata la barra Comandi a un solo pulsante `Stop`; lo stop di emergenza
  resta accessibile tramite le scorciatoie globali.
- Added the read-only `Mappa Task/Chiamate` desktop tab.
- Added navigation from learning domains to observed tasks, linked UI functions,
  channels and individual metadata-only call shapes.
- Added search plus domain and maturity filters, with explicit evidence and
  replay-safety notices.
- Added a reusable task/call read-model service backed by persisted annotated
  network observations.

## 0.10.1 - 2026-07-23

- Aggiunta la skill condivisa `doomsday-task-call-mapper` per raggruppare
  transizioni UI, chiusure popup e fingerprint applicativi metadata-only in
  candidati di operazioni e task ricorrenti.
- Formalizzate classi e livelli di maturità che mantengono separate evidenza,
  attribuzione semantica, revisione umana ed eventuale autorità esecutiva.

## 0.9.0 - 2026-07-23

- Resa predefinita l'osservazione rete metadata-only nelle sessioni Learning,
  con attach o avvio bounded sul PID del gioco e fallback visuale esplicito.
- Collegati click, crop, frame completi e nodi UI agli indici degli eventi
  TCP/UDP osservati prima e dopo la stabilizzazione grafica.
- Aggiunti marker incrociati, fingerprint per click, latenza candidata e
  `network_correlation_summary.json` senza contenuti, header o credenziali.
- Introdotto il registro dei domini Learning per rapporti battaglia, risorse,
  armamenti, raccolta, officina, ricerca e missioni.
- Rimosso dal launcher Learning il percorso Python specifico della postazione:
  ora usa `CODEX_PYTHON_EXE`, `.venv` o discovery del runtime.

## 0.8.2 - 2026-07-23

- Estesa l'osservazione metadata-only con eventi per ogni messaggio TCP/UDP:
  timestamp, direzione, indice e byte count, senza persistere payload.
- Resa possibile la correlazione temporale supervisionata tra transizioni del
  grafo UI dei report e scambi sui canali persistenti del gioco.

## 0.7.1 - 2026-07-15

- Reso esplicito il collegamento pubblico `Doomsday.lnk` come unico ingresso
  supportato al client Windows e registrato il target launcher risolto.
- Aggiunto `-LaunchViaShortcut` all'osservatore: apre il launcher, attende il
  PID di gioco e solo dopo applica la cattura metadata-only al processo.
- Aggiunto setup riproducibile con dipendenze opzionali bloccate e ambiente
  isolato sotto `.tools/mitmproxy`, senza CA o modifiche al proxy di Windows.
- Vietato nel profilo di osservazione l'avvio diretto del binario versionato,
  che senza contesto launcher restituisce `ErrCode: 0x4`.

## 0.7.0 - 2026-07-15

- Installato mitmproxy 12.2.3 in un ambiente isolato e ignorato dal repository.
- Aggiunta osservazione per PID con TLS passthrough: destinazioni, SNI/ALPN,
  trasporti, contatori e dimensioni senza header, cookie, token o payload.
- Aggiunti normalizzazione degli endpoint, aggregatore di schemi, comandi
  start/stop/summarize e profilo di sicurezza versionato.
- Verificata la cattura locale per PID con risposta HTTPS 200 e contenuto
  rimasto cifrato; nessuna CA e nessun proxy Windows sono stati configurati.
- Mantenuti Wireshark/Npcap come classificatore passivo dei canali TCP/UDP che
  non risultano HTTP e formalizzato il confine di correlazione semantica UI.

## 0.6.1 - 2026-07-14

- Resi i nodi UI strutturali privi di riconoscitori esplicitamente non osservabili:
  non possono piu' apparire attivi o diventare fatti di stato.
- Estese le campagne semantiche con run supervisionati, stato prima/dopo,
  evidenze, copertura e suggerimenti di attribuzione esclusivamente consultivi.
- Aggiunta CI Windows per compilazione e suite automatica completa.

## 0.6.0 - 2026-07-14

- Aggiunte campagne semantiche per attribuire macro e sequenze a obiettivi,
  operazioni, domini asset (eroi, veicoli, bestie, armi e armamenti), versione
  e stato di validazione, con snapshot immutabile della sequenza.
- Aggiunta la modalita' learning `hero-inspection` con journal JSONL crash-safe,
  frame completi, hash, qualita' e recupero read-only delle sessioni interrotte.
- Formalizzato il workflow Eroe con automazione negata fino a frame before/after
  validi e conferma umana.
- Rimossa dal learning generale l'inferenza “fascia 4 = chiusura popup”, che
  aveva fuso quattro click distinti in un elemento globale.
- Recuperata la dimostrazione ANTARTIKA da 22 click senza modificare il database
  macro in conflitto; i gap visivi legacy restano espliciti.
- Aggiunti Tesseract CLI `ita+eng`, preprocessing PIL e profilo cattura
  versionato con la sola anchor `Eroe` calibrata.
- Aggiunto il roster live transazionale con artifact immutabili, preview,
  decisioni, conferma, commit atomico, revisioni, audit e outbox.
- Aggiunto l'adapter BlueStacks fail-closed che usa esclusivamente una sessione
  ADB gia' verificata e non avvia emulatori o daemon.
- Canonicalizzate le chiavi OCR italiane di talenti nel modello roster live.

## 0.5.4 - 2026-07-14

- Aggiunta la tab `Piano Gioco` per consultare interpretazione e piano
  semantico senza avviare macro o collegare executor.
- Reso conservativo il planner: gli effetti delle azioni restano potenziali
  finche non esistono esecuzione confermata e nuova osservazione.
- Reso visibile e abilitato il comando Stop normale durante le operazioni;
  rimossi gli accessi Pillow deprecati dalle verifiche visive.
- Documentato il piano di evoluzione e ignorati i sidecar SQLite volatili.

## 0.5.3 - 2026-07-14

- Aggiornato il pianificatore delle cinque marce con Maxwell + Daryl come
  prima coppia, Felix + Chasey come seconda e una sequenza di transizione
  verificabile per bestie, armi speciali e riserve.
- Separato Metok Tso dal percorso automatico Maxwell: resta un investimento
  da confrontare con la quinta marcia a sviluppo completato.

## 0.5.2 - 2026-07-14

- Inventariati in un registro versionato la VM VirtualBox Android-x86 storica,
  BlueStacks 5 e il client Windows Doomsday corrente.
- Aggiunto un probe read-only che non avvia gioco, emulatori o daemon ADB.
- Aggiunta cattura Win32 della finestra DirectX visibile e un contratto
  supervisionato per sessioni e osservazioni roster.
- Collegati i parser OCR a contributi atomici con provenienza, scartando i
  valori di default non realmente osservati.
- Estesi i pattern delle statistiche per separatori OCR come `ATK: 1234`.

## 0.5.0 - 2026-07-14

- Introdotto il package `doomsday.intelligence` con dominio versionato, 15 modalità, 18 ruleset e 27 azioni semantiche.
- Aggiunti interpretazione degli obiettivi, vincoli di spesa/perdita, planner conservativo, state estimator e binding opzionale UI/macro.
- Aggiunti provider isolati per fase, risoluzione delle evidenze con conflitti e adapter al SourceRegistry condiviso di Knowledge.
- Aggiunti policy gate, port Executor, valutazione degli esiti e persistenza separata per contributi, episodi e performance.
- Pubblicati registry di dominio, overlay delle fonti, interfaccia runtime e architettura di migrazione strangler.
- L'esecuzione macro resta disabilitata per default finché database legacy e riconoscimento dei nodi UI P0 non sono risolti.

## 0.3.0 - 2026-05-26

- Importati modularmente componenti Doomsday legacy nel nuovo package `doomsday/`:
  OCR roster, parser talenti/statistiche, loader catalogo e primitive di visione esterna.
- Portati nel progetto dataset utili da `F:\Zombi` in `data/doomsday/` per market profiles, profile pack e roster base.
- Aggiunti test automatici dedicati ai moduli Doomsday.

## 0.2.1 - 2026-05-26

- Onboarded the project into the shared AI workspace with local `AGENTS.md` and `project-manifest.json`.
- Registered `macro_controller` in the shared knowledge hub as an active sibling project.
- Published shared interface notes for Doomsday roster bootstrap and external vision primitives.

## 0.2.0 - 2026-05-14
- Migliorata la velocita' di playback riducendo controlli focus ridondanti e alleggerendo gli aggiornamenti UI durante i mouse move molto densi.
- Aggiunto il pulsante `Ottimizza` nell'editor macro per creare una nuova macro ottimizzata e caricarla subito nell'editor.
- Introdotto `services/macro_optimization_service.py` con logica dedicata per compressione dei mouse move e rimozione di move ridondanti prima dei click.
- Aggiunte statistiche sintetiche nell'editor macro per eventi, durata e distribuzione input.
- Migliorata la visibilita' del runtime scheduler nel pannello countdown dei task schedulati.
- Estesa la suite di test automatici per ottimizzazione macro e pannello scheduled tasks.

## 0.1.0 - 2026-05-12

- Refactor architetturale principale con separazione in `repositories`, `services`, `ui` e `core`.
- Messa in sicurezza di scheduler, stop playback e accesso SQLite.
- Introdotti test automatici per servizi, repository e configurazione.
- Aggiunto README iniziale e pubblicazione del repository privato.
