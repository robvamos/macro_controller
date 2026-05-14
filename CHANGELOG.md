# Changelog

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
