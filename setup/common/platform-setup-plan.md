# Platform Setup Plan

## Comune

- definire entrypoint applicativo
- elencare dipendenze Python e dipendenze native
- separare i dati persistenti dagli asset reinstallabili
- prevedere aggiornamenti senza perdere `config/` e `data/`

## Windows

- launcher elevato opzionale
- pacchetto con runtime Python incluso
- collegamenti Start Menu / Desktop
- regole di aggiornamento per database e catalogo

## Linux

- launcher desktop `.desktop`
- packaging AppImage o pacchetto distro-specifico
- mapping dipendenze di sistema per audio e GUI

## Android

- valutare solo sottosistemi esportabili
- separare UI desktop da logica riusabile
- isolare i componenti Windows-only prima del porting

