"""Helper UI per il pannello degli elementi grafici."""

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
