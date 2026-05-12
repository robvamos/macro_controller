"""Helper UI per il pannello degli elementi grafici."""

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
    details_text = f"Nome: {element['nome']}\n"
    if element["descrizione"]:
        details_text += f"Descrizione: {element['descrizione']}\n"
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
