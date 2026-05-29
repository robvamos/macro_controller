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
6. Salvare l'elemento solo se il ritaglio è nitido e abbastanza specifico.

## Uso futuro

Gli elementi così inseriti sono pensati per:

- ricerca grafica sull'intera schermata
- riconoscimento di pannelli e popup nei grafi UI
- recovery automation
- collegamento tra nodi del grafo e macro candidate
