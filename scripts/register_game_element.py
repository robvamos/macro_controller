from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_env import sanitize_runtime_env

sanitize_runtime_env()

import argparse
import json

from services.game_element_ingestion_service import (
    build_prepared_asset_summary,
    ingest_game_element_from_path,
)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Censisce un elemento grafico del gioco a partire da un file immagine e una connotazione semantica."
    )
    parser.add_argument("--image", help="Percorso dell'immagine da censire.")
    parser.add_argument(
        "--clipboard",
        action="store_true",
        help="Legge l'immagine direttamente dalla clipboard di Windows.",
    )
    parser.add_argument("--name", required=True, help="Nome stabile dell'elemento nel catalogo.")
    parser.add_argument("--description", default="", help="Descrizione umana dell'elemento.")
    parser.add_argument(
        "--connotation",
        default="",
        help="Connotazione o ruolo semantico dell'elemento, utile per matching, grafi e recovery.",
    )
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=None,
        help="Soglia opzionale di deduplica, se vuoi forzare un comportamento più o meno severo.",
    )
    parser.add_argument(
        "--user-element",
        action="store_true",
        help="Registra l'elemento come modificabile/cancellabile dall'utente. Di default gli elementi inseriti da Codex sono di sistema.",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.image and not args.clipboard:
        parser.error("Serve --image oppure --clipboard.")
    if args.image and args.clipboard:
        parser.error("Usa solo uno tra --image e --clipboard.")

    if args.clipboard:
        try:
            from PIL import ImageGrab
        except ImportError as exc:
            raise RuntimeError("Pillow non disponibile per leggere l'immagine dalla clipboard.") from exc

        clipboard_image = ImageGrab.grabclipboard()
        if clipboard_image is None or not hasattr(clipboard_image, "copy"):
            raise RuntimeError("Nessuna immagine disponibile nella clipboard.")

        from services.game_element_ingestion_service import ingest_game_element_from_image

        kwargs = {
            "image": clipboard_image,
            "name": args.name,
            "description_text": args.description,
            "semantic_connotation": args.connotation,
            "source_format": "PNG",
            "is_system": not args.user_element,
        }
        if args.similarity_threshold is not None:
            kwargs["similarity_threshold"] = float(args.similarity_threshold)
        result = ingest_game_element_from_image(**kwargs)
    else:
        kwargs = {
            "image_path": Path(args.image),
            "name": args.name,
            "description_text": args.description,
            "semantic_connotation": args.connotation,
            "is_system": not args.user_element,
        }
        if args.similarity_threshold is not None:
            kwargs["similarity_threshold"] = float(args.similarity_threshold)
        result = ingest_game_element_from_path(**kwargs)
    payload = {
        "element_id": result.upsert_result.element_id,
        "element_name": result.upsert_result.element_name,
        "reused_existing": result.upsert_result.reused_existing,
        "updated_existing": result.upsert_result.updated_existing,
        "description": result.description,
        "asset_summary": build_prepared_asset_summary(result.asset),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
