"""
Modulo per la gestione degli elementi grafici del gioco.
Gestisce l'upload di immagini da file o clipboard Windows.
"""

import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from PIL import Image, ImageTk
import io
import base64
import logging

logger = logging.getLogger(__name__)

def get_image_from_clipboard():
    """Ottiene un'immagine dagli appunti di Windows."""
    try:
        import win32clipboard
        from PIL import ImageGrab
        
        # Prova a ottenere l'immagine dalla clipboard
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
                # Formato DIB (Device Independent Bitmap)
                data = win32clipboard.GetClipboardData(win32clipboard.CF_DIB)
                win32clipboard.CloseClipboard()
                
                # Converti DIB in immagine PIL
                from io import BytesIO
                import struct
                
                # DIB header è di 40 byte + color table
                dib_header = data[:40]
                width, height = struct.unpack('<ii', dib_header[4:12])
                
                # Crea un'immagine PIL dal DIB
                # Nota: questa è una semplificazione, potrebbe non funzionare per tutti i formati
                try:
                    image = ImageGrab.grabclipboard()
                    if image:
                        return image, 'PNG'
                except:
                    pass
        except Exception as e:
            logger.warning(f"Errore nel tentativo di ottenere immagine dalla clipboard: {e}")
            try:
                win32clipboard.CloseClipboard()
            except:
                pass
        
        # Metodo alternativo usando ImageGrab
        try:
            image = ImageGrab.grabclipboard()
            if image:
                return image, 'PNG'
        except Exception as e:
            logger.warning(f"Errore ImageGrab: {e}")
        
        return None, None
    except ImportError:
        logger.error("win32clipboard non disponibile. Installa pywin32: pip install pywin32")
        return None, None
    except Exception as e:
        logger.error(f"Errore nel recupero immagine da clipboard: {e}")
        return None, None

def image_to_blob(image, formato='PNG'):
    """Converte un'immagine PIL in BLOB per il database."""
    try:
        buffer = io.BytesIO()
        image.save(buffer, format=formato)
        buffer.seek(0)
        return buffer.read()
    except Exception as e:
        logger.error(f"Errore nella conversione immagine in BLOB: {e}")
        raise

def blob_to_image(blob_data, formato='PNG'):
    """Converte un BLOB del database in immagine PIL."""
    try:
        buffer = io.BytesIO(blob_data)
        image = Image.open(buffer)
        return image
    except Exception as e:
        logger.error(f"Errore nella conversione BLOB in immagine: {e}")
        raise

def load_image_from_file():
    """Carica un'immagine da file."""
    try:
        file_path = filedialog.askopenfilename(
            title="Seleziona immagine",
            filetypes=[
                ("Immagini", "*.png *.jpg *.jpeg *.bmp *.gif"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("BMP", "*.bmp"),
                ("GIF", "*.gif"),
                ("Tutti i file", "*.*")
            ]
        )
        
        if file_path:
            image = Image.open(file_path)
            # Determina il formato dal file
            formato = image.format or 'PNG'
            return image, formato
        return None, None
    except Exception as e:
        logger.error(f"Errore nel caricamento immagine da file: {e}")
        messagebox.showerror("Errore", f"Errore nel caricamento dell'immagine: {e}")
        return None, None

def paste_image_from_clipboard():
    """Ottiene un'immagine dalla clipboard Windows."""
    image, formato = get_image_from_clipboard()
    if image:
        return image, formato or 'PNG'
    else:
        messagebox.showwarning("Clipboard vuota", "Nessuna immagine trovata negli appunti di Windows.")
        return None, None
