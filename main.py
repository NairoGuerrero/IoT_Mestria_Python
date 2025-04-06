import threading

import paho.mqtt.client as mqtt
import logging
import psycopg2
from datetime import datetime
from boot_telegram import BotTelegram

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


class MqttSubscriber:
    def __init__(self, broker: str, port: int, topics, db_manager: DatabaseManager):
        self.broker = broker
        self.port = port
        self.topics = topics if isinstance(topics, list) else [topics]
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.db_manager = db_manager

        self.bot = BotTelegram(publish_funtion=self.publish_message)
        threading.Thread(target=self.bot.start, daemon=True).start()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        logging.info(f"Conectado con código de resultado: {reason_code}")
        for topic in self.topics:
            client.subscribe(topic)
            logging.info(f"Suscrito a: {topic}")

    def on_message(self, client, userdata, msg):
        message = msg.payload.decode()
        logging.info(f"Mensaje recibido en {msg.topic}: {message}")
        self.db_manager.save_message(message)

    def publish_message(self, topic: str, message: str):
        """Publica un mensaje en el tópico especificado si hay conexión."""
        if self.client.is_connected():
            try:
                result = self.client.publish(topic, message)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    logging.info(f"Mensaje publicado en {topic}: {message}")
                else:
                    logging.warning(f"No se pudo publicar el mensaje en {topic}. Código de error: {result.rc}")
            except Exception as e:
                logging.error(f"Error al publicar mensaje en {topic}: {e}")
        else:
            logging.warning("Cliente MQTT no está conectado. No se puede publicar el mensaje.")

    def start(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()  # Mantiene el cliente en un hilo separado
            while True:
                pass  # Mantiene la ejecución activa sin bloquear
        except Exception as e:
            logging.error(f"Error en la conexión MQTT: {e}")


if __name__ == "__main__":
    db_config = {
        "dbname": "logs",
        "user": "administrador",
        "password": "C4Ab1nGe+*",
        "host": "localhost",
        "port": "5432"
    }

    db_manager = DatabaseManager(db_config)
    mqtt_subscriber = MqttSubscriber(broker="test.mosquitto.org", port=1883, topics=["NaA", "AaN"],
                                     db_manager=db_manager)
    mqtt_subscriber.start()
