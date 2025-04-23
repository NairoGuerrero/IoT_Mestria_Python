import psycopg2
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", force=True)


class DatabaseManager:
    def __init__(self, db_config):
        self.db_config = db_config
        self.connection = self.connect_to_db()

    def connect_to_db(self):
        try:
            conn = psycopg2.connect(
                dbname=self.db_config["dbname"],
                user=self.db_config["user"],
                password=self.db_config["password"],
                host=self.db_config["host"],
                port=self.db_config["port"]
            )
            logging.info("Conexión a la base de datos establecida correctamente.")
            return conn
        except Exception as e:
            logging.error(f"Error al conectar a la base de datos: {e}")
            return None

    def get_user(self, chat_id):
        cur = self.connection.cursor()

        cur.execute('SELECT name_user, "is_superUser", is_active FROM public.users WHERE id = %s', (chat_id,))


        row = cur.fetchone()
        cur.close()

        return row  # (name_user, bool, bool) o None

    def add_user(self, chat_id, name):
        cur = self.connection.cursor()

        cur.execute(
            'INSERT INTO public.users (id, name_user, "is_superUser", is_active) VALUES (%s, %s, FALSE, FALSE)',
            (chat_id, name)
        )
        self.connection.commit()
        cur.close()


    def update_active(self, chat_id, activo: bool):
        cur = self.connection.cursor()

        cur.execute(
            'UPDATE public.users SET is_active = %s WHERE id = %s',(activo, chat_id)
        )
        self.connection.commit()
        cur.close()


    def get_all_users(self):
        cur = self.connection.cursor()


        cur.execute('SELECT id, name_user, is_active FROM public.users ORDER BY id')
        rows = cur.fetchall()
        cur.close()

        return rows  # lista de (id, name_user, is_active)


    def get_superusers(self):
        cur = self.connection.cursor()

        cur.execute('SELECT id FROM public.users WHERE "is_superUser" = TRUE')
        su = [r[0] for r in cur.fetchall()]
        cur.close()
        return su


    def save_message(self, message):
        if self.connection:
            try:
                cursor = self.connection.cursor()
                query = 'INSERT INTO "logsESP" (fecha, mensaje) VALUES (%s, %s)'
                cursor.execute(query, (datetime.now(), message))
                self.connection.commit()
                cursor.close()
                logging.info("Mensaje guardado en la base de datos.")
            except Exception as e:
                logging.error(f"Error al guardar mensaje en la base de datos: {e}")
