# Setup Scaffold

Questa cartella contiene la base per i futuri pacchetti di installazione dell'app.

## Obiettivo

Tenere separati:

- i metadati comuni dell'app
- gli asset condivisibili tra più piattaforme
- gli script specifici per ogni piattaforma

## Struttura

- [common](common): metadati e convenzioni riusabili
- [windows](windows): primi file guida per il setup Windows
- [linux](linux): spazio riservato per packaging Linux
- [android](android): spazio riservato per una futura variante Android

## Principio

La logica comune deve stare in `common/`. Le cartelle piattaforma devono limitarsi a:

- launcher
- installer
- mapping dipendenze
- icone, scorciatoie e integrazioni OS

