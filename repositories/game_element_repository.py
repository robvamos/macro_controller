"""Repository per gli elementi grafici di gioco."""

from repositories.database import connect_db


def _game_element_row_to_dict(row, include_image=False):
    element = {
        "id": row[0],
        "nome": row[1],
        "descrizione": row[2],
    }
    if include_image:
        element["immagine"] = row[3]
        element["formato_immagine"] = row[4]
        element["data_creazione"] = row[5]
        element["data_ultima_modifica"] = row[6]
    else:
        element["formato_immagine"] = row[3]
        element["data_creazione"] = row[4]
        element["data_ultima_modifica"] = row[5]
    return element


def create_game_element(nome, descrizione, immagine_blob, formato_immagine):
    """Crea un nuovo elemento grafico del gioco."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM GameElements WHERE nome = ?", (nome,))
        if cursor.fetchone():
            raise ValueError(f"Un elemento con il nome '{nome}' esiste già.")

        cursor.execute(
            """
            INSERT INTO GameElements (nome, descrizione, immagine, formato_immagine)
            VALUES (?, ?, ?, ?)
            """,
            (nome, descrizione, immagine_blob, formato_immagine),
        )

        element_id = cursor.lastrowid
        conn.commit()
        return element_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_all_game_elements(include_image=False):
    """Ottiene tutti gli elementi grafici del gioco."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        if include_image:
            cursor.execute(
                """
                SELECT id, nome, descrizione, immagine, formato_immagine, data_creazione, data_ultima_modifica
                FROM GameElements
                ORDER BY data_ultima_modifica DESC, data_creazione DESC
                """
            )
            return [_game_element_row_to_dict(row, include_image=True) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT id, nome, descrizione, formato_immagine, data_creazione, data_ultima_modifica
            FROM GameElements
            ORDER BY data_ultima_modifica DESC, data_creazione DESC
            """
        )
        return [_game_element_row_to_dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_game_element_by_id(element_id):
    """Ottiene un elemento grafico specifico per ID."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, nome, descrizione, immagine, formato_immagine, data_creazione, data_ultima_modifica
            FROM GameElements
            WHERE id = ?
            """,
            (element_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None
        return _game_element_row_to_dict(row, include_image=True)
    finally:
        conn.close()


def get_game_element_by_name(nome):
    """Ottiene un elemento grafico specifico per nome."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, nome, descrizione, immagine, formato_immagine, data_creazione, data_ultima_modifica
            FROM GameElements
            WHERE nome = ?
            """,
            (nome,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return _game_element_row_to_dict(row, include_image=True)
    finally:
        conn.close()


def update_game_element(element_id, nome=None, descrizione=None, immagine_blob=None, formato_immagine=None):
    """Aggiorna un elemento grafico esistente."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM GameElements WHERE id = ?", (element_id,))
        if not cursor.fetchone():
            raise ValueError(f"Elemento con ID {element_id} non trovato.")

        if nome is not None:
            cursor.execute("SELECT id FROM GameElements WHERE nome = ? AND id != ?", (nome, element_id))
            if cursor.fetchone():
                raise ValueError(f"Un elemento con il nome '{nome}' esiste già.")

        update_fields = []
        update_values = []

        if nome is not None:
            update_fields.append("nome = ?")
            update_values.append(nome)
        if descrizione is not None:
            update_fields.append("descrizione = ?")
            update_values.append(descrizione)
        if immagine_blob is not None:
            update_fields.append("immagine = ?")
            update_values.append(immagine_blob)
        if formato_immagine is not None:
            update_fields.append("formato_immagine = ?")
            update_values.append(formato_immagine)

        if update_fields:
            update_fields.append("data_ultima_modifica = CURRENT_TIMESTAMP")
            update_values.append(element_id)
            query = f"UPDATE GameElements SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, update_values)

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def delete_game_element(element_id):
    """Elimina un elemento grafico."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM GameElements WHERE id = ?", (element_id,))
        if cursor.rowcount == 0:
            raise ValueError(f"Elemento con ID {element_id} non trovato.")
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


__all__ = [
    "create_game_element",
    "delete_game_element",
    "get_all_game_elements",
    "get_game_element_by_id",
    "get_game_element_by_name",
    "update_game_element",
]
