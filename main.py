import threading

import paho.mqtt.client as mqtt
import logging
import psycopg2
from datetime import datetime
from boot_telegram import BotTelegram
import json
import time

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

        self.bot = BotTelegram(publish_function=self.publish_message)
        threading.Thread(target=self.bot.start, daemon=True).start()

        threading.Thread(target=self.monitor_keep_alive, daemon=True).start()

    def monitor_keep_alive(self):
        while True:
            todos_desconectados = True  # Suponemos que todos están desconectados

            for name, data in self.bot.led_states.items():
                logging.info(f"{name}: {data['keep_alive']}")
                timestamp = data.get('timestamp')

                if timestamp:
                    elapsed = time.time() - timestamp
                    if elapsed > 3 and data['keep_alive']:  # 3 segundos de inactividad
                        logging.warning(
                            f"❌ {name.capitalize()} desconectado. Último keep-alive hace {int(elapsed)} segundos.")
                        self.bot.update_keep_alive(name, status=False)

                # Si al menos uno está activo, entonces no están todos desconectados
                if data['keep_alive']:
                    todos_desconectados = False

            if todos_desconectados:
                logging.warning("⚠️ Todos los dispositivos están desconectados.")
                self.bot.alerta_todos_desconectados()

            time.sleep(10)  # Revisa cada 10 segundos

    def on_connect(self, client, userdata, flags, reason_code, properties):
        logging.info(f"Conectado con código de resultado: {reason_code}")
        for topic in self.topics:
            client.subscribe(topic)
            logging.info(f"Suscrito a: {topic}")

    def on_message(self, client, userdata, msg):
        message = msg.payload.decode()
        message_json = json.loads(message)
        topic = msg.topic


        if message_json.get('action') == 'response_led' and topic == "NaA":
            led_status = message_json.get('dato_led', None)
            if led_status is not None:
                self.bot.update_led_status(name="nairo", status=led_status)
                logging.info(f"Estado del LED Nairo actualizado: {led_status} {type(led_status)}")

        if message_json.get('action') == 'response_led' and topic == "AaN":
            led_status = message_json.get('dato_led', None)
            if led_status is not None:
                self.bot.update_led_status(name="alejandro", status=led_status)
                logging.info(f"Estado del LED Nairo actualizado: {led_status} {type(led_status)}")

        elif message_json.get('action') == 'response_temperatura' and topic == "NaA":
            temperature = message_json.get('dato_temperatura', None)
            if temperature is not None:
                self.bot.update_sensor_status(variable="temperatura", value=temperature)
                logging.info(f"Temperatura Nairo actualizada: {temperature} °C")

        elif message_json.get('action') == 'response_humedad' and topic == "NaA":
            humidity = message_json.get('dato_humedad', None)
            if humidity is not None:
                self.bot.update_sensor_status(variable="humedad", value=humidity)
                logging.info(f"Humedad Nairo actualizada: {humidity} %")

        elif message_json.get('action') == 'keep-alive' and topic == "NaA":
            self.bot.update_keep_alive(name="nairo", status=message_json.get('keep', None))

        elif message_json.get('action') == 'keep-alive' and topic == "AaN":
            self.bot.update_keep_alive(name="alejandro", status=message_json.get('keep', None))

        elif message_json.get('action') == 'response':
            print('GUARDODO ....')
            self.db_manager.save_message(message)

        logging.info(f"Mensaje recibido en {topic}: {message}")



        # self.db_manager.save_message(message)

    def publish_message(self, topic, message):
        """Publica un mensaje en el tópico especificado si hay conexión."""
        if self.client.is_connected():
            try:
                result = self.client.publish(topic, json.dumps(message))
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
            self.client.connect(self.broker, self.port, 5)
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
