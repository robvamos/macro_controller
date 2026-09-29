# Istruzioni per gli agenti

Questo progetto fa parte del workspace condiviso. Non assumere che il clone sia in una directory o unità fissa. Leggi [configurazione workstation](workstation/README.md) e risolvi percorsi macchina tramite `workstation/settings.py` / `core.paths`.

## Coordinamento Knowledge

Usa le skill `attivasviluppo` per setup, GitHub e asset persistenti e `sviluppo-conoscenza` per lo sviluppo coordinato nel workspace. Il Knowledge hub si trova nel percorso `knowledgeRoot` del profilo locale (predefinito: `../Knowledge`); la copia GitHub è [robvamos/knowledge](https://github.com/robvamos/knowledge).

Prima di introdurre una capability:

1. consulta nel Knowledge hub i registry di progetti, skill, capability e interfacce;
2. verifica le interfacce pubblicate dai progetti fratelli e riusa le skill disponibili;
3. evita duplicazioni di logica già pubblicata;
4. aggiorna `project-manifest.json` per versioni, capability, interfacce o stato;
5. dopo modifiche significative sincronizza manifest e scheda progetto nel Knowledge hub.

## Aree riutilizzabili

- riproduzione/registrazione macro, monitoraggio del focus e pianificazione;
- bootstrap del roster da dataset versionati;
- parser OCR di statistiche e talenti degli eroi;
- cattura finestre Doomsday e primitives di template matching.

Interfacce locali: [bootstrap roster](interfaces/doomsday-roster-bootstrap.md) e [primitives visuali](interfaces/doomsday-vision-primitives.md). Per ricerche su rider, bestie, armamenti o guide consulta prima [l'indice delle fonti](docs/research/SOURCES.md).

## Dati condivisi e locali

Leggi [come si condivide la conoscenza](docs/knowledge-sharing.md) e [l'inventario del supporto](docs/project-support.md). Profili, database, runtime, frame e log sono locali e ignorati. Versiona soltanto conoscenza portabile dopo revisione; gli exporter devono aggiungere/riconciliare i dati senza cancellare contributi delle altre workstation.