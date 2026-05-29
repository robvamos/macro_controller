# Game Element Ingestion Workflow

## Obiettivo

Registrare elementi grafici del gioco in modo:

- lossless
- semanticamente descrivibile
- riusabile per matching, recovery e grafi UI

## Regole operative

1. Acquisire il ritaglio più stretto e pulito possibile.
2. Evitare ridimensionamenti manuali prima del salvataggio.
3. Salvare l'asset in PNG lossless.
4. Mantenere il rapporto originale dell'immagine.
5. Accompagnare sempre l'asset con:
   - nome descrittivo
   - descrizione di dove compare
   - ruolo semantico
   - eventuale uso operativo o di recovery
6. Se il controllo contiene testo localizzato, trattare la scritta come secondaria e usare il simbolo stabile come riferimento principale.
7. Se il pannello contiene badge, contatori o puntini rossi variabili, considerarli rumore visivo e non parte del riferimento stabile.

## Procedura consigliata

1. Incollare o caricare l'immagine nel pannello `Elementi`.
2. Verificare il riepilogo tecnico mostrato dal dialog:
   - formato origine
   - dimensioni origine
   - formato di salvataggio
   - conferma di assenza distorsioni
3. Inserire un nome stabile e descrittivo.
4. Inserire una descrizione contestuale.
5. Inserire un ruolo semantico, ad esempio:
   - `popup close button`
   - `shared top-left status panel`
   - `shelter training control`
6. Per bottoni multilingua, nominare l'elemento in base alla funzione o all'icona, non alla parola visibile.
7. Per pannelli con contatori variabili, preferire il ritaglio delle icone o della struttura comune, evitando di dare peso ai numeri rossi.
8. Salvare l'elemento solo se il ritaglio è nitido e abbastanza specifico.

## Esempio utile

- Se nel rifugio il bottone basso a sinistra mostra un globo con la scritta `Regione`, l'elemento va trattato come `region_view_switch_globe_icon`.
- La scritta puo' cambiare lingua, ma l'icona globo resta il riferimento visivo piu' stabile per il matching.
- Se il pannello `Campagna / Zaino / Alleanza / Bestia / Eroe` mostra badge rossi con numeri, quei badge non vanno considerati parte del confronto stabile.

## Uso futuro

Gli elementi così inseriti sono pensati per:

- ricerca grafica sull'intera schermata
- riconoscimento di pannelli e popup nei grafi UI
- recovery automation
- collegamento tra nodi del grafo e macro candidate
