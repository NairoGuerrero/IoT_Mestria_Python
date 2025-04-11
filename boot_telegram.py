import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import os
import time

load_dotenv()  # Cargar variables del archivo .env

class BotTelegram:
    def __init__(self, publish_function):
        self.publish_function = publish_function
        self.token = os.getenv("TELEGRAM_API_TOKEN")
        self.bot = telebot.TeleBot(self.token)

        # Estados de los LEDs
        self.led_states = {
            'nairo': {
                'text': 'Desconocido',
                'value': None,
                'keep_alive': None,
                'timestamp': None,
            },
            'alejandro': {
                'text': 'Desconocido',
                'value': None,
                'keep_alive': False,
                'timestamp': None,
            },
        }

        self.sensor_states = {
            'temperatura': None,
            'humedad': None
        }


        self.MENU_CALLBACKS = {
            'LED_MENU': 'submenu_leds',
            'LED_NAIRO': 'led_nairo',
            'LED_ALEJANDRO': 'led_alejandro',
            'TEMPERATURA': 'temperatura',
            'HUMEDAD': 'humedad',
            'VOLVER': 'volver_menu',
        }

        self.register_handlers()

        self.pending_led_status_request_chat_id = None

    def request_led_statuses(self):
        self.publish_function(
            topic="AaN",
            message={
                'id': 3,
                "action": "request",
                "request_data": "estado_led",
            }
        )
        self.publish_function(
            topic="NaA",
            message={
                'id': 3,
                "action": "request",
                "request_data": "estado_led",
            }
        )

    def request_sensor_status(self, variable:str):
        if self.led_states['nairo']['keep_alive']:
            request_data = f'estado_{variable}'

            self.publish_function(
                topic="AaN",
                message={
                    'id': 3,
                    "action": "request",
                    "request_data": request_data,
                }
            )
        else:
            self.bot.send_message(
                self.pending_led_status_request_chat_id,
                f"Dispositivo desconectado - Ultima interaccion : {self.timestamp_a_fecha(self.led_states['nairo']['timestamp'])}"
            )

    def update_keep_alive(self, name, status):
        if name in self.led_states:
            self.led_states[name]['keep_alive'] = status
            self.led_states[name]['timestamp'] = time.time() if status else self.led_states[name]['timestamp']


    def update_led_status(self, name, status):
        if name in self.led_states:
            self.led_states[name]['text'] = "Encendido" if status else "Apagado"
            self.led_states[name]['value'] = status

            # Si hay una solicitud pendiente, mostrar el menú
            if self.pending_led_status_request_chat_id:
                self.bot.send_message(
                    self.pending_led_status_request_chat_id,
                    "✅ Estado actualizado. Selecciona un LED para controlar:",
                    reply_markup=self.get_leds_menu()
                )
                self.pending_led_status_request_chat_id = None  # Limpiar el estado

    def update_sensor_status(self, variable, value):
        if variable in self.sensor_states:
            self.sensor_states[variable] = value

            # Si hay una solicitud pendiente, mostrar el menú
            if self.pending_led_status_request_chat_id:
                self.bot.send_message(
                    self.pending_led_status_request_chat_id,
                    f"{"🌡️" if variable == 'temperatura' else "💧"} {variable.capitalize()}: {value} {'°C' if variable == 'temperatura' else '%'} \n\nSelecciona otra opción del menú:",
                    reply_markup=self.get_main_menu()
                )
                self.pending_led_status_request_chat_id = None

    # =============================
    # ========== MENÚS ===========
    # =============================

    def get_main_menu(self):
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("💡 LEDs", callback_data=self.MENU_CALLBACKS['LED_MENU']),
            InlineKeyboardButton("🌡️ Temperatura", callback_data=self.MENU_CALLBACKS['TEMPERATURA']),
            InlineKeyboardButton("💧 Humedad", callback_data=self.MENU_CALLBACKS['HUMEDAD'])
        )
        return keyboard

    def get_leds_menu(self):
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton(f"💡 LED Nairo ({self.led_states['nairo']['text']})", callback_data=self.MENU_CALLBACKS['LED_NAIRO']),
            InlineKeyboardButton(f"💡 LED Alejandro ({self.led_states['alejandro']['text']})", callback_data=self.MENU_CALLBACKS['LED_ALEJANDRO']),
        )
        keyboard.add(
            InlineKeyboardButton("🏠 Menú principal", callback_data=self.MENU_CALLBACKS['VOLVER'])
        )
        return keyboard

    # =============================
    # ========= HANDLERS =========
    # =============================

    def register_handlers(self):
        self.bot.message_handler(commands=['start', 'help'])(self.handle_start)
        self.bot.message_handler(func=lambda msg: True)(self.handle_text_message)
        self.bot.callback_query_handler(func=lambda call: True)(self.handle_callback)

    def handle_start(self, message):
        self.show_main_menu(message.chat.id, "Bienvenido al sistema IoT 👋\nSelecciona una opción del menú:")

    def handle_text_message(self, message):
        self.show_main_menu(message.chat.id, "Selecciona una opción del menú:")

    def handle_callback(self, call):
        self.bot.answer_callback_query(call.id)
        data = call.data

        if data == self.MENU_CALLBACKS['LED_MENU']:
            self.pending_led_status_request_chat_id = call.message.chat.id  # Guardar el chat_id
            self.request_led_statuses()  # Pedir estado actualizado
            self.bot.send_message(
                call.message.chat.id,
                "🔄 Pidiendo estado de los LEDs..."
            )


        elif data == self.MENU_CALLBACKS['VOLVER']:
            self.bot.send_message(
                call.message.chat.id,
                "Selecciona una opción del menú:",
                reply_markup=self.get_main_menu()
            )

        elif data == self.MENU_CALLBACKS['LED_NAIRO']:
            self.action_leds(call.message.chat.id, 'nairo')

        elif data == self.MENU_CALLBACKS['LED_ALEJANDRO']:
            self.action_leds(call.message.chat.id, 'alejandro')

        elif data == self.MENU_CALLBACKS['TEMPERATURA']:
            self.pending_led_status_request_chat_id = call.message.chat.id
            self.bot.send_message(
                call.message.chat.id,
                "🌡️ Consultando temperatura..."
            )
            self.request_sensor_status('temperatura')
        elif data == self.MENU_CALLBACKS['HUMEDAD']:
            self.pending_led_status_request_chat_id = call.message.chat.id
            self.bot.send_message(
                call.message.chat.id,
                "💧 Consultando humedad..."
            )
            self.request_sensor_status('humedad')

    # =============================
    # ========= UTILIDADES =======
    # =============================

    def show_main_menu(self, chat_id, text):
        self.bot.send_message(chat_id, text, reply_markup=self.get_main_menu())

    def send_action_response(self, chat_id, text):
        self.bot.send_message(chat_id, text)
        self.show_main_menu(chat_id, "Selecciona otra opción del menú:")

    def action_leds(self, chat_id, led_name):

        if self.led_states[led_name]['keep_alive'] :

            self.publish_function(
                topic="AaN",
                message={
                    'id': 3,
                    "action": "response",
                    "dato_led": 0 if self.led_states[led_name]['value'] else 1,
                }
            )
            self.send_action_response(
                chat_id,
                f"🔆 LED {led_name.capitalize()} {'Apagado' if self.led_states[led_name]['value'] else 'Encendido'}"
            )
        else:
            self.send_action_response(
                chat_id,
                f" Dispositivo desconectado - Ultima interaccion : {self.timestamp_a_fecha(self.led_states[led_name]['timestamp'])}"
            )

    def alerta_todos_desconectados(self):
        mensaje = "⚠️ *Todos los dispositivos están desconectados.*\n\n"
        for nombre, datos in self.led_states.items():
            ultima_interaccion = self.timestamp_a_fecha(datos['timestamp']) if datos['timestamp'] else "Sin registro"
            mensaje += f"🔌 *{nombre.capitalize()}*: última señal hace {ultima_interaccion}\n"

        # Aquí deberías poner el ID de tu grupo o usuario autorizado
        chat_id_destino = self.pending_led_status_request_chat_id
        if chat_id_destino:
            self.send_action_response(
                chat_id_destino,
                mensaje
            )
        else:
            print("⚠️ No se encontró TELEGRAM_CHAT_ID para enviar la alerta.")

    def timestamp_a_fecha(self,timestamp):
        if timestamp is None:
            return "Sin registro"
        else:
            tm = time.localtime(timestamp)
            return "{:04d}/{:02d}/{:02d} {:02d}:{:02d}:{:02d}".format(
                tm[0], tm[1], tm[2], tm[3], tm[4], tm[5]
            )

    def start(self):
        self.bot.infinity_polling()
