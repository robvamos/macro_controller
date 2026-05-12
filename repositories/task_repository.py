"""Repository per scheduled task e sequenze di macro."""

import datetime

from repositories.database import connect_db


def _task_row_to_dict(row):
    return {
        "id": row[0],
        "nome": row[1],
        "descrizione": row[2],
        "macro_id": row[3],
        "schedulazione_tipo": row[4],
        "ora_target": row[5],
        "intervallo_ore": row[6],
        "intervallo_minuti": row[7],
        "attivo": bool(row[8]),
        "data_creazione": row[9],
        "data_ultima_esecuzione": row[10],
        "prossima_esecuzione": row[11],
        "stato": row[12] or "stopped",
        "terminazione_tipo": row[13] or "nessuna",
        "terminazione_valore": row[14],
        "data_inizio_schedulazione": row[15],
        "conteggio_esecuzioni": row[16] or 0,
        "macro_nome": row[17],
        "macro_eseguibile": row[18],
    }


def _task_sequence_row_to_dict(row):
    return {
        "id": row[0],
        "macro_id": row[1],
        "ordine": row[2],
        "attesa_secondi": row[3],
        "macro_nome": row[4],
        "macro_eseguibile": row[5],
    }


def _calculate_next_execution(schedulazione_tipo, ora_target, intervallo_ore, intervallo_minuti, now=None):
    now = now or datetime.datetime.now()
    if schedulazione_tipo == "ora_fissa":
        target_hour, target_minute = map(int, ora_target.split(":"))
        prossima_esecuzione = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if prossima_esecuzione <= now:
            prossima_esecuzione += datetime.timedelta(days=1)
        return prossima_esecuzione

    interval_seconds = (intervallo_ore * 3600 if intervallo_ore else 0) + (intervallo_minuti * 60 if intervallo_minuti else 0)
    return now + datetime.timedelta(seconds=interval_seconds)


def get_all_scheduled_tasks():
    """Ottieni tutti gli scheduled tasks con i loro metadati."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT st.id, st.nome, st.descrizione, st.macro_id, st.schedulazione_tipo,
                   st.ora_target, st.intervallo_ore, st.intervallo_minuti, st.attivo,
                   st.data_creazione, st.data_ultima_esecuzione, st.prossima_esecuzione,
                   st.stato, st.terminazione_tipo, st.terminazione_valore,
                   st.data_inizio_schedulazione, st.conteggio_esecuzioni,
                   m.nome as macro_nome, m.eseguibile
            FROM ScheduledTasks st
            LEFT JOIN Macro m ON st.macro_id = m.id
            ORDER BY st.data_creazione DESC
            """
        )
        return [_task_row_to_dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_active_tasks_ordered_by_next_execution():
    """Ottieni tutti i task attivi ordinati per prossima esecuzione (più prossimi prima)."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT st.id, st.nome, st.descrizione, st.macro_id, st.schedulazione_tipo,
                   st.ora_target, st.intervallo_ore, st.intervallo_minuti, st.attivo,
                   st.data_creazione, st.data_ultima_esecuzione, st.prossima_esecuzione,
                   st.stato, st.terminazione_tipo, st.terminazione_valore,
                   st.data_inizio_schedulazione, st.conteggio_esecuzioni,
                   m.nome as macro_nome, m.eseguibile
            FROM ScheduledTasks st
            LEFT JOIN Macro m ON st.macro_id = m.id
            WHERE st.attivo = 1 AND (st.stato IS NULL OR st.stato != 'completed')
                  AND st.prossima_esecuzione IS NOT NULL
            ORDER BY st.prossima_esecuzione ASC
            """
        )
        return [_task_row_to_dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def create_scheduled_task(
    nome,
    descrizione,
    macro_id,
    schedulazione_tipo,
    ora_target=None,
    intervallo_ore=None,
    intervallo_minuti=None,
    terminazione_tipo=None,
    terminazione_valore=None,
):
    """Crea un nuovo scheduled task."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM Macro WHERE id = ?", (macro_id,))
        if not cursor.fetchone():
            raise ValueError(f"Macro con ID {macro_id} non trovata.")

        cursor.execute("SELECT id FROM ScheduledTasks WHERE nome = ?", (nome,))
        if cursor.fetchone():
            raise ValueError(f"Un scheduled task con il nome '{nome}' esiste già.")

        if schedulazione_tipo == "ora_fissa":
            if not ora_target:
                raise ValueError("Per schedulazione a ora fissa è necessario specificare ora_target.")
            try:
                datetime.datetime.strptime(ora_target, "%H:%M")
            except ValueError:
                raise ValueError("Formato ora_target non valido. Usa formato HH:MM.")
        elif schedulazione_tipo == "intervallo":
            if intervallo_ore is None and intervallo_minuti is None:
                raise ValueError("Per schedulazione ad intervallo devi specificare almeno intervallo_ore o intervallo_minuti.")
        else:
            raise ValueError("schedulazione_tipo deve essere 'ora_fissa' o 'intervallo'.")

        prossima_esecuzione = _calculate_next_execution(
            schedulazione_tipo, ora_target, intervallo_ore, intervallo_minuti
        )

        if terminazione_tipo and terminazione_tipo != "nessuna":
            if terminazione_valore is None or terminazione_valore <= 0:
                raise ValueError(f"Per terminazione tipo '{terminazione_tipo}' è necessario specificare un valore positivo.")

        cursor.execute(
            """
            INSERT INTO ScheduledTasks (nome, descrizione, macro_id, schedulazione_tipo,
                                      ora_target, intervallo_ore, intervallo_minuti,
                                      prossima_esecuzione, terminazione_tipo, terminazione_valore)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                nome,
                descrizione,
                macro_id,
                schedulazione_tipo,
                ora_target,
                intervallo_ore,
                intervallo_minuti,
                prossima_esecuzione.strftime("%Y-%m-%d %H:%M:%S"),
                terminazione_tipo or "nessuna",
                terminazione_valore,
            ),
        )

        task_id = cursor.lastrowid
        conn.commit()
        return task_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def update_scheduled_task(
    task_id,
    nome=None,
    descrizione=None,
    macro_id=None,
    schedulazione_tipo=None,
    ora_target=None,
    intervallo_ore=None,
    intervallo_minuti=None,
    attivo=None,
    terminazione_tipo=None,
    terminazione_valore=None,
):
    """Aggiorna un scheduled task esistente."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM ScheduledTasks WHERE id = ?", (task_id,))
        if not cursor.fetchone():
            raise ValueError(f"Scheduled task con ID {task_id} non trovato.")

        if macro_id is not None:
            cursor.execute("SELECT id FROM Macro WHERE id = ?", (macro_id,))
            if not cursor.fetchone():
                raise ValueError(f"Macro con ID {macro_id} non trovata.")

        if nome is not None:
            cursor.execute("SELECT id FROM ScheduledTasks WHERE nome = ? AND id != ?", (nome, task_id))
            if cursor.fetchone():
                raise ValueError(f"Un scheduled task con il nome '{nome}' esiste già.")

        if schedulazione_tipo:
            if schedulazione_tipo == "ora_fissa" and not ora_target:
                raise ValueError("Per schedulazione a ora fissa è necessario specificare ora_target.")
            if schedulazione_tipo == "intervallo" and intervallo_ore is None and intervallo_minuti is None:
                raise ValueError("Per schedulazione ad intervallo devi specificare almeno intervallo_ore o intervallo_minuti.")

        if ora_target is not None:
            try:
                datetime.datetime.strptime(ora_target, "%H:%M")
            except ValueError:
                raise ValueError("Formato ora_target non valido. Usa formato HH:MM.")

        update_fields = []
        update_values = []

        if nome is not None:
            update_fields.append("nome = ?")
            update_values.append(nome)
        if descrizione is not None:
            update_fields.append("descrizione = ?")
            update_values.append(descrizione)
        if macro_id is not None:
            update_fields.append("macro_id = ?")
            update_values.append(macro_id)
        if schedulazione_tipo is not None:
            update_fields.append("schedulazione_tipo = ?")
            update_values.append(schedulazione_tipo)
        if ora_target is not None:
            update_fields.append("ora_target = ?")
            update_values.append(ora_target)
        if intervallo_ore is not None:
            update_fields.append("intervallo_ore = ?")
            update_values.append(intervallo_ore)
        if intervallo_minuti is not None:
            update_fields.append("intervallo_minuti = ?")
            update_values.append(intervallo_minuti)
        if attivo is not None:
            update_fields.append("attivo = ?")
            update_values.append(attivo)
        if terminazione_tipo is not None:
            update_fields.append("terminazione_tipo = ?")
            update_values.append(terminazione_tipo)
        if terminazione_valore is not None:
            update_fields.append("terminazione_valore = ?")
            update_values.append(terminazione_valore)

        if update_fields:
            now = datetime.datetime.now()
            if schedulazione_tipo:
                prossima_esecuzione = _calculate_next_execution(
                    schedulazione_tipo, ora_target, intervallo_ore, intervallo_minuti, now=now
                )
                update_fields.append("prossima_esecuzione = ?")
                update_values.append(prossima_esecuzione.strftime("%Y-%m-%d %H:%M:%S"))

            update_values.append(task_id)
            query = f"UPDATE ScheduledTasks SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, update_values)

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def delete_scheduled_task(task_id):
    """Elimina un scheduled task."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM ScheduledTasks WHERE id = ?", (task_id,))
        if cursor.rowcount == 0:
            raise ValueError(f"Scheduled task con ID {task_id} non trovato.")
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def duplicate_scheduled_task(task_id):
    """Duplica un scheduled task esistente."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT nome, descrizione, macro_id, schedulazione_tipo, ora_target,
                   intervallo_ore, intervallo_minuti
            FROM ScheduledTasks WHERE id = ?;
            """,
            (task_id,),
        )

        task_data = cursor.fetchone()
        if not task_data:
            raise ValueError(f"Scheduled task con ID {task_id} non trovato.")

        nome_originale, descrizione, macro_id, schedulazione_tipo, ora_target, intervallo_ore, intervallo_minuti = task_data

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nuovo_nome = f"{nome_originale}_{timestamp}"

        cursor.execute("SELECT id FROM ScheduledTasks WHERE nome = ?", (nuovo_nome,))
        if cursor.fetchone():
            counter = 1
            while True:
                nuovo_nome = f"{nome_originale}_{timestamp}_{counter}"
                cursor.execute("SELECT id FROM ScheduledTasks WHERE nome = ?", (nuovo_nome,))
                if not cursor.fetchone():
                    break
                counter += 1

        task_id_nuovo = create_scheduled_task(
            nome=nuovo_nome,
            descrizione=descrizione,
            macro_id=macro_id,
            schedulazione_tipo=schedulazione_tipo,
            ora_target=ora_target,
            intervallo_ore=intervallo_ore,
            intervallo_minuti=intervallo_minuti,
        )

        return task_id_nuovo, nuovo_nome
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_scheduled_task_by_id(task_id):
    """Ottieni un scheduled task specificato per ID."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT st.id, st.nome, st.descrizione, st.macro_id, st.schedulazione_tipo,
                   st.ora_target, st.intervallo_ore, st.intervallo_minuti, st.attivo,
                   st.data_creazione, st.data_ultima_esecuzione, st.prossima_esecuzione,
                   st.stato, st.terminazione_tipo, st.terminazione_valore,
                   st.data_inizio_schedulazione, st.conteggio_esecuzioni,
                   m.nome as macro_nome, m.eseguibile
            FROM ScheduledTasks st
            LEFT JOIN Macro m ON st.macro_id = m.id
            WHERE st.id = ?
            """,
            (task_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None
        return _task_row_to_dict(row)
    finally:
        conn.close()


def update_last_execution(task_id, execution_time=None):
    """Aggiorna la data di ultima esecuzione di un task."""
    execution_time = execution_time or datetime.datetime.now()

    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT schedulazione_tipo, ora_target, intervallo_ore, intervallo_minuti
            FROM ScheduledTasks WHERE id = ?
            """,
            (task_id,),
        )

        row = cursor.fetchone()
        if not row:
            return False

        schedulazione_tipo, ora_target, intervallo_ore, intervallo_minuti = row
        prossima_esecuzione = _calculate_next_execution(
            schedulazione_tipo, ora_target, intervallo_ore, intervallo_minuti, now=execution_time
        )

        cursor.execute(
            """
            UPDATE ScheduledTasks
            SET data_ultima_esecuzione = ?, prossima_esecuzione = ?
            WHERE id = ?
            """,
            (
                execution_time.strftime("%Y-%m-%d %H:%M:%S"),
                prossima_esecuzione.strftime("%Y-%m-%d %H:%M:%S"),
                task_id,
            ),
        )

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_tasks_due_for_execution():
    """Ottieni tutti i task da eseguire ora o prima, escludendo quelli completati."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            SELECT st.id, st.macro_id, st.nome, st.schedulazione_tipo,
                   st.intervallo_ore, st.intervallo_minuti, st.ora_target,
                   st.stato, st.terminazione_tipo, st.terminazione_valore,
                   st.data_inizio_schedulazione, st.conteggio_esecuzioni,
                   m.nome as macro_nome, m.eseguibile
            FROM ScheduledTasks st
            LEFT JOIN Macro m ON st.macro_id = m.id
            WHERE st.attivo = 1 AND st.prossima_esecuzione <= ?
                  AND (st.stato IS NULL OR st.stato != 'completed')
            """,
            (now,),
        )

        tasks = []
        for row in cursor.fetchall():
            tasks.append(
                {
                    "id": row[0],
                    "macro_id": row[1],
                    "nome": row[2],
                    "schedulazione_tipo": row[3],
                    "intervallo_ore": row[4],
                    "intervallo_minuti": row[5],
                    "ora_target": row[6],
                    "stato": row[7] or "stopped",
                    "terminazione_tipo": row[8] or "nessuna",
                    "terminazione_valore": row[9],
                    "data_inizio_schedulazione": row[10],
                    "conteggio_esecuzioni": row[11] or 0,
                    "macro_nome": row[12],
                    "macro_eseguibile": row[13],
                }
            )
        return tasks
    finally:
        conn.close()


def start_task_scheduling(task_id):
    """Avvia la schedulazione di un task, impostando lo stato a 'running' e la data di inizio."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        now = datetime.datetime.now()
        cursor.execute(
            """
            UPDATE ScheduledTasks
            SET stato = 'running', data_inizio_schedulazione = ?, conteggio_esecuzioni = 0
            WHERE id = ?
            """,
            (now.strftime("%Y-%m-%d %H:%M:%S"), task_id),
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def stop_task_scheduling(task_id):
    """Ferma la schedulazione di un task, impostando lo stato a 'stopped'."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE ScheduledTasks
            SET stato = 'stopped'
            WHERE id = ?
            """,
            (task_id,),
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def increment_task_execution_count(task_id):
    """Incrementa il conteggio delle esecuzioni di un task."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE ScheduledTasks
            SET conteggio_esecuzioni = conteggio_esecuzioni + 1
            WHERE id = ?
            """,
            (task_id,),
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def check_and_complete_task_if_needed(task_id):
    """Controlla se un task deve essere completato in base alle condizioni di terminazione."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT terminazione_tipo, terminazione_valore, data_inizio_schedulazione, conteggio_esecuzioni
            FROM ScheduledTasks WHERE id = ?
            """,
            (task_id,),
        )

        row = cursor.fetchone()
        if not row:
            return False

        terminazione_tipo, terminazione_valore, data_inizio, conteggio = row
        if terminazione_tipo == "nessuna" or terminazione_valore is None:
            return False

        should_complete = False
        if terminazione_tipo == "esecuzioni":
            if conteggio and conteggio >= terminazione_valore:
                should_complete = True
        elif terminazione_tipo == "durata_ore" and data_inizio:
            start_time = datetime.datetime.strptime(data_inizio, "%Y-%m-%d %H:%M:%S")
            elapsed_hours = (datetime.datetime.now() - start_time).total_seconds() / 3600
            if elapsed_hours >= terminazione_valore:
                should_complete = True
        elif terminazione_tipo == "durata_minuti" and data_inizio:
            start_time = datetime.datetime.strptime(data_inizio, "%Y-%m-%d %H:%M:%S")
            elapsed_minutes = (datetime.datetime.now() - start_time).total_seconds() / 60
            if elapsed_minutes >= terminazione_valore:
                should_complete = True

        if should_complete:
            cursor.execute(
                """
                UPDATE ScheduledTasks
                SET stato = 'completed', attivo = 0
                WHERE id = ?
                """,
                (task_id,),
            )
            conn.commit()
            return True

        return False
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def reactivate_completed_task(task_id):
    """Riattiva un task completato, resettando lo stato e i contatori."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE ScheduledTasks
            SET stato = 'stopped', attivo = 1, conteggio_esecuzioni = 0, data_inizio_schedulazione = NULL
            WHERE id = ?
            """,
            (task_id,),
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_task_macro_sequence(task_id):
    """Ottieni la sequenza di macro per un task, ordinata per ordine."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT tms.id, tms.macro_id, tms.ordine, tms.attesa_secondi,
                   m.nome as macro_nome, m.eseguibile
            FROM TaskMacroSequence tms
            LEFT JOIN Macro m ON tms.macro_id = m.id
            WHERE tms.task_id = ?
            ORDER BY tms.ordine
            """,
            (task_id,),
        )
        return [_task_sequence_row_to_dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def add_macro_to_task_sequence(task_id, macro_id, attesa_secondi=0):
    """Aggiungi una macro alla sequenza di un task. L'ordine viene determinato automaticamente."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM Macro WHERE id = ?", (macro_id,))
        if not cursor.fetchone():
            raise ValueError(f"Macro con ID {macro_id} non trovata.")

        cursor.execute("SELECT id FROM ScheduledTasks WHERE id = ?", (task_id,))
        if not cursor.fetchone():
            raise ValueError(f"Task con ID {task_id} non trovato.")

        cursor.execute("SELECT MAX(ordine) FROM TaskMacroSequence WHERE task_id = ?", (task_id,))
        max_ordine = cursor.fetchone()[0]
        next_ordine = (max_ordine + 1) if max_ordine is not None else 0

        cursor.execute(
            """
            INSERT INTO TaskMacroSequence (task_id, macro_id, ordine, attesa_secondi)
            VALUES (?, ?, ?, ?)
            """,
            (task_id, macro_id, next_ordine, attesa_secondi),
        )

        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def add_macro_to_task_sequence_with_order(task_id, macro_id, ordine, attesa_secondi=0):
    """Aggiungi una macro alla sequenza di un task con un ordine specifico."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM Macro WHERE id = ?", (macro_id,))
        if not cursor.fetchone():
            raise ValueError(f"Macro con ID {macro_id} non trovata.")

        cursor.execute("SELECT id FROM ScheduledTasks WHERE id = ?", (task_id,))
        if not cursor.fetchone():
            raise ValueError(f"Task con ID {task_id} non trovato.")

        cursor.execute("SELECT id FROM TaskMacroSequence WHERE task_id = ? AND ordine = ?", (task_id, ordine))
        if cursor.fetchone():
            cursor.execute(
                """
                UPDATE TaskMacroSequence
                SET ordine = ordine + 1
                WHERE task_id = ? AND ordine >= ?
                """,
                (task_id, ordine),
            )

        cursor.execute(
            """
            INSERT INTO TaskMacroSequence (task_id, macro_id, ordine, attesa_secondi)
            VALUES (?, ?, ?, ?)
            """,
            (task_id, macro_id, ordine, attesa_secondi),
        )

        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def remove_macro_from_task_sequence(sequence_id):
    """Rimuovi una macro dalla sequenza di un task."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT task_id, ordine FROM TaskMacroSequence WHERE id = ?", (sequence_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Sequenza con ID {sequence_id} non trovata.")

        task_id, ordine_rimosso = row
        cursor.execute("DELETE FROM TaskMacroSequence WHERE id = ?", (sequence_id,))
        cursor.execute(
            """
            UPDATE TaskMacroSequence
            SET ordine = ordine - 1
            WHERE task_id = ? AND ordine > ?
            """,
            (task_id, ordine_rimosso),
        )

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def update_macro_sequence_wait_time(sequence_id, attesa_secondi):
    """Aggiorna il tempo di attesa per una macro nella sequenza."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE TaskMacroSequence
            SET attesa_secondi = ?
            WHERE id = ?
            """,
            (attesa_secondi, sequence_id),
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def clear_task_macro_sequence(task_id):
    """Rimuovi tutte le macro dalla sequenza di un task."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM TaskMacroSequence WHERE task_id = ?", (task_id,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


__all__ = [
    "add_macro_to_task_sequence",
    "add_macro_to_task_sequence_with_order",
    "check_and_complete_task_if_needed",
    "clear_task_macro_sequence",
    "create_scheduled_task",
    "delete_scheduled_task",
    "duplicate_scheduled_task",
    "get_active_tasks_ordered_by_next_execution",
    "get_all_scheduled_tasks",
    "get_scheduled_task_by_id",
    "get_task_macro_sequence",
    "get_tasks_due_for_execution",
    "increment_task_execution_count",
    "reactivate_completed_task",
    "remove_macro_from_task_sequence",
    "start_task_scheduling",
    "stop_task_scheduling",
    "update_last_execution",
    "update_macro_sequence_wait_time",
    "update_scheduled_task",
]
