# Changelog

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
