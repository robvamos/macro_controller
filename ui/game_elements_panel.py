"""Helper UI per il pannello degli elementi grafici."""

from runtime_env import sanitize_runtime_env

sanitize_runtime_env()

import tkinter as tk

from PIL import Image, ImageTk


def build_game_element_row(element):
    """Restituisce la tupla valori per l'inserimento nella TreeView."""
    return (
        element["id"],
        element["nome"],
        element["formato_immagine"],
        element["data_ultima_modifica"] or element["data_creazione"],
    )


def build_game_element_details_text(element):
    """Restituisce il testo descrittivo da mostrare nell'anteprima."""
    descrizione = element["descrizione"] or ""
    semantic_hint = ""
    if "[semantic_hint]" in descrizione:
        parts = descrizione.split("[semantic_hint]", 1)
        descrizione = parts[0].strip()
        semantic_hint = parts[1].strip()

    details_text = f"Nome: {element['nome']}\n"
    if descrizione:
        details_text += f"Descrizione: {descrizione}\n"
    if semantic_hint:
        details_text += f"Ruolo semantico: {semantic_hint}\n"
    details_text += f"Formato: {element['formato_immagine']}\n"
    details_text += f"ID: {element['id']}"
    return details_text


def render_preview_image(image, image_label, max_size=(350, 350), clear_text=True):
    """Ridimensiona e applica l'immagine di anteprima al label."""
    preview = image.copy()
    preview.thumbnail(max_size, Image.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(preview)
    image_label.configure(image=photo, text="" if clear_text else image_label.cget("text"))
    image_label.image = photo
    return photo


def render_fullsize_image_on_canvas(image, canvas, *, background="#000000"):
    """Mostra l'immagine 1:1 su canvas con area scrollabile, senza ridimensionarla."""
    if image is None:
        canvas.delete("all")
        canvas.configure(scrollregion=(0, 0, 1, 1), background=background)
        canvas.image = None
        return None

    photo = ImageTk.PhotoImage(image.copy())
    canvas.delete("all")
    canvas.configure(background=background)
    canvas.create_image(0, 0, image=photo, anchor="nw", tags=("preview_image",))
    canvas.configure(scrollregion=(0, 0, image.width, image.height))
    canvas.image = photo
    return photo


def compute_crop_display_size(image_size, max_size):
    """Calcola la dimensione di visualizzazione per il crop mantenendo il rapporto."""
    width, height = image_size
    max_width, max_height = max_size
    if width <= 0 or height <= 0:
        return 1, 1

    scale = min(max_width / float(width), max_height / float(height), 1.0)
    return max(1, int(round(width * scale))), max(1, int(round(height * scale)))


def map_display_selection_to_original(selection_box, *, original_size, display_size):
    """Converte una selezione fatta sulla preview nelle coordinate dell'immagine originale."""
    left, top, right, bottom = selection_box
    display_width, display_height = display_size
    original_width, original_height = original_size
    if display_width <= 0 or display_height <= 0 or original_width <= 0 or original_height <= 0:
        raise ValueError("Dimensioni immagine non valide per il mapping del crop.")

    left, right = sorted((left, right))
    top, bottom = sorted((top, bottom))
    left = max(0, min(display_width, int(round(left))))
    right = max(0, min(display_width, int(round(right))))
    top = max(0, min(display_height, int(round(top))))
    bottom = max(0, min(display_height, int(round(bottom))))

    if right <= left or bottom <= top:
        raise ValueError("Selezione crop non valida.")

    scale_x = original_width / float(display_width)
    scale_y = original_height / float(display_height)
    mapped = (
        max(0, min(original_width, int(round(left * scale_x)))),
        max(0, min(original_height, int(round(top * scale_y)))),
        max(1, min(original_width, int(round(right * scale_x)))),
        max(1, min(original_height, int(round(bottom * scale_y)))),
    )

    if mapped[2] <= mapped[0]:
        mapped = (mapped[0], mapped[1], min(original_width, mapped[0] + 1), mapped[3])
    if mapped[3] <= mapped[1]:
        mapped = (mapped[0], mapped[1], mapped[2], min(original_height, mapped[1] + 1))
    return mapped
