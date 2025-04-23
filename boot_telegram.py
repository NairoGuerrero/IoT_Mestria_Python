import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import os
import time
import logging

load_dotenv()  # Cargar variables de entorno (.env)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", force=True)


class BotTelegram:
    def __init__(self, publish_function, db_manager):
        self.publish_function = publish_function
        self.db = db_manager
        self.token = os.getenv("TELEGRAM_API_TOKEN")
        self.bot = telebot.TeleBot(self.token)

        # Estados de los LEDs
        self.led_states = {
            'nairo': {'text': 'Desconocido', 'value': None, 'keep_alive': None, 'timestamp': None},
            'alejandro': {'text': 'Desconocido', 'value': None, 'keep_alive': False, 'timestamp': None},
        }

        # Estados de sensores
        self.sensor_states = {'temperatura': None, 'humedad': None}

        # Claves de callback para menús originales
        self.MENU_CALLBACKS = {
            'LED_MENU': 'submenu_leds',
            'LED_NAIRO': 'led_nairo',
            'LED_ALEJANDRO': 'led_alejandro',
            'TEMPERATURA': 'temperatura',
            'HUMEDAD': 'humedad',
            'VOLVER': 'volver_menu',
        }

        self.pending_led_status_request_chat_id = None
        self.register_handlers()

    # Teclados para activación y gestión de usuarios
    def _kb_solicitar_activacion(self):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Solicitar activación", callback_data="REQUEST_ACTIVATION"))
        return kb

    def _kb_superusuario_para(self, user_id):
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("✅ Activar", callback_data=f"SET_ACTIVE_{user_id}_1"),
            InlineKeyboardButton("❌ Desactivar", callback_data=f"SET_ACTIVE_{user_id}_0")
        )
        return kb

    # Registro de handlers
    def register_handlers(self):
        self.bot.message_handler(commands=['start', 'help'])(self.handle_start)
        self.bot.message_handler(func=lambda msg: True)(self.handle_text_message)
        self.bot.callback_query_handler(func=lambda call: True)(self.handle_callback)

    # Handlers de mensajes
    def handle_start(self, message):
        chat_id = message.chat.id
        user = self.db.get_user(chat_id)

        if not user:
            name = message.from_user.username or message.from_user.first_name
            self.db.add_user(chat_id, name)
            self.bot.send_message(
                chat_id,
                "Bienvenido. Tu cuenta está _pendiente de activación_.",
                parse_mode='Markdown',
                reply_markup=self._kb_solicitar_activacion()
            )
            return

        _, is_super, is_active = user

        if not is_active:
            self.bot.send_message(
                chat_id,
                "🚫 Acceso denegado. Tu cuenta está desactivada.",
                reply_markup=self._kb_solicitar_activacion()
            )
            return

        kb = self.get_main_menu()
        if is_super:
            kb.row(InlineKeyboardButton("👥 Usuarios", callback_data="VIEW_USERS"))
        self.bot.send_message(chat_id, "Bienvenido al sistema IoT 👋", reply_markup=kb)

    def handle_text_message(self, message):
        user = self.db.get_user(message.chat.id)
        if not user or not user[2]:  # Verificar si está inactivo
            self.bot.send_message(
                message.chat.id,
                "🔒 Necesitas una cuenta activa para usar el bot.",
                reply_markup=self._kb_solicitar_activacion()
            )
            return
        self.handle_start(message)

    def handle_callback(self, call):
        self.bot.answer_callback_query(call.id)
        data = call.data
        user_info = self.db.get_user(call.from_user.id)

        # Usuario no registrado
        if not user_info:
            self.bot.send_message(call.from_user.id, "⚠️ Por favor, inicia el bot con /start")
            return

        _, is_super, is_active = user_info

        # Permitir solicitud de activación incluso si está inactivo
        if data == "REQUEST_ACTIVATION":
            for su in self.db.get_superusers():
                self.bot.send_message(
                    su,
                    f"📢 El usuario @{call.from_user.username} (ID {call.from_user.id}) solicita activación.",
                    reply_markup=self._kb_superusuario_para(call.from_user.id)
                )
            self.bot.send_message(call.message.chat.id, "✅ Solicitud enviada a los administradores.")
            return

        # Bloquear otras acciones si no está activo
        if not is_active:
            self.bot.send_message(
                call.from_user.id,
                "🔒 Tu cuenta está inactiva. Solicita activación:",
                reply_markup=self._kb_solicitar_activacion()
            )
            return

        # Listar usuarios + botón menú principal
        if data == "VIEW_USERS":
            kb = InlineKeyboardMarkup(row_width=1)
            for uid, name, active in self.db.get_all_users():
                label = '✅' if active else '❌'
                kb.add(InlineKeyboardButton(f"{name} ({uid}) — [{label}]",
                                            callback_data=f"SET_ACTIVE_{uid}_{int(not active)}"))
            kb.add(InlineKeyboardButton("🏠 Menú principal", callback_data=self.MENU_CALLBACKS['VOLVER']))
            self.bot.send_message(call.from_user.id, "Lista de usuarios (clic para alternar):", reply_markup=kb)
            return

        # Callbacks originales del menú IoT
        if data == self.MENU_CALLBACKS['LED_MENU']:
            self.pending_led_status_request_chat_id = call.message.chat.id
            self.request_led_statuses()
            self.bot.send_message(call.message.chat.id, "🔄 Pidiendo estado de los LEDs...")

        elif data == self.MENU_CALLBACKS['VOLVER']:
            chat_id = call.message.chat.id
            _, is_super, _ = self.db.get_user(chat_id)
            kb = self.get_main_menu()
            if is_super:
                kb.row(InlineKeyboardButton("👥 Usuarios", callback_data="VIEW_USERS"))
            self.bot.send_message(chat_id, "Selecciona una opción:", reply_markup=kb)

        elif data in (self.MENU_CALLBACKS['LED_NAIRO'], self.MENU_CALLBACKS['LED_ALEJANDRO']):
            name = 'nairo' if data == self.MENU_CALLBACKS['LED_NAIRO'] else 'alejandro'
            self.action_leds(call.message.chat.id, name)

        elif data == self.MENU_CALLBACKS['TEMPERATURA']:
            self.pending_led_status_request_chat_id = call.message.chat.id
            self.bot.send_message(call.message.chat.id, "🌡️ Consultando temperatura...")
            self.request_sensor_status('temperatura')

        elif data == self.MENU_CALLBACKS['HUMEDAD']:
            self.pending_led_status_request_chat_id = call.message.chat.id
            self.bot.send_message(call.message.chat.id, "💧 Consultando humedad...")
            self.request_sensor_status('humedad')

        # Activar/Desactivar usuario (solo superusuarios)
        if data.startswith("SET_ACTIVE_"):
            if not is_super:
                self.bot.send_message(call.from_user.id, "🚫 No tienes permisos para esta acción")
                return

            try:
                payload = data[len("SET_ACTIVE_"):]
                uid_str, flag_str = payload.split("_", 1)
                uid, flag = int(uid_str), bool(int(flag_str))
            except ValueError:
                logging.warning(f"Callback SET_ACTIVE mal formado: {data}")
                return

            self.db.update_active(uid, flag)
            estado = "activo" if flag else "inactivo"
            self.bot.send_message(call.from_user.id, f"Usuario {uid} ahora está *{estado}*.", parse_mode='Markdown')

            try:
                self.bot.send_message(uid, f"Tu cuenta ha sido *{estado}* por el administrador.", parse_mode='Markdown')
            except Exception as e:
                logging.error(f"Error notificando al usuario {uid}: {e}")

    # ... (El resto de los métodos permanecen igual: get_main_menu, get_leds_menu, request_led_statuses, etc.)
    # Mantener sin cambios los métodos restantes de la clase BotTelegram

    def get_main_menu(self):
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("💡 LEDs", callback_data=self.MENU_CALLBACKS['LED_MENU']),
            InlineKeyboardButton("🌡️ Temperatura", callback_data=self.MENU_CALLBACKS['TEMPERATURA']),
            InlineKeyboardButton("💧 Humedad", callback_data=self.MENU_CALLBACKS['HUMEDAD'])
        )
        return kb

    def get_leds_menu(self):
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton(f"💡 LED Nairo ({self.led_states['nairo']['text']})",
                                 callback_data=self.MENU_CALLBACKS['LED_NAIRO']),
            InlineKeyboardButton(f"💡 LED Alejandro ({self.led_states['alejandro']['text']})",
                                 callback_data=self.MENU_CALLBACKS['LED_ALEJANDRO'])
        )
        kb.add(InlineKeyboardButton("🏠 Menú principal", callback_data=self.MENU_CALLBACKS['VOLVER']))
        return kb

    def request_led_statuses(self):
        for topic in ("AaN", "NaA"):
            self.publish_function(topic=topic, message={'id': 3, 'action': 'request', 'request_data': 'estado_led'})

    def request_sensor_status(self, variable: str):
        if self.led_states['nairo']['keep_alive']:
            self.publish_function(topic="AaN",
                                  message={'id': 3, 'action': 'request', 'request_data': f'estado_{variable}'})
        else:
            self.bot.send_message(
                self.pending_led_status_request_chat_id,
                f"Dispositivo desconectado - Última interacción: {self.timestamp_a_fecha(self.led_states['nairo']['timestamp'])}"
            )

    def update_keep_alive(self, name, status):
        if name in self.led_states:
            self.led_states[name]['keep_alive'] = status
            if status:
                self.led_states[name]['timestamp'] = time.time()

    def update_led_status(self, name, status):
        if name in self.led_states:
            self.led_states[name]['text'] = "Encendido" if status else "Apagado"
            self.led_states[name]['value'] = status
            if self.pending_led_status_request_chat_id:
                self.bot.send_message(
                    self.pending_led_status_request_chat_id,
                    "✅ Estado actualizado. Selecciona un LED:",
                    reply_markup=self.get_leds_menu()
                )
                self.pending_led_status_request_chat_id = None

    def update_sensor_status(self, variable, value):
        if variable in self.sensor_states:
            self.sensor_states[variable] = value
            if self.pending_led_status_request_chat_id:
                emoji = "🌡️" if variable == 'temperatura' else "💧"
                unidad = "°C" if variable == 'temperatura' else "%"
                self.bot.send_message(
                    self.pending_led_status_request_chat_id,
                    f"{emoji} {variable.capitalize()}: {value} {unidad}\n\nSelecciona otra opción:",
                    reply_markup=self.get_main_menu()
                )
                self.pending_led_status_request_chat_id = None

    def show_main_menu(self, chat_id, text):
        self.bot.send_message(chat_id, text, reply_markup=self.get_main_menu())

    def send_action_response(self, chat_id, text):
        self.bot.send_message(chat_id, text)
        self.show_main_menu(chat_id, "Selecciona otra opción:")

    def action_leds(self, chat_id, led_name):
        if self.led_states[led_name]['keep_alive']:
            self.publish_function(
                topic="AaN",
                message={'id': 3, 'action': 'response', 'dato_led': 0 if self.led_states[led_name]['value'] else 1}
            )
            estado = "Apagado" if self.led_states[led_name]['value'] else "Encendido"
            self.send_action_response(chat_id, f"🔆 LED {led_name.capitalize()} {estado}")
        else:
            self.send_action_response(
                chat_id,
                f"Dispositivo desconectado - Última interacción: {self.timestamp_a_fecha(self.led_states[led_name]['timestamp'])}"
            )

    def alerta_todos_desconectados(self):
        mensaje = "⚠️ *Todos los dispositivos están desconectados.*\n\n"
        for nombre, datos in self.led_states.items():
            ultima = self.timestamp_a_fecha(datos['timestamp']) if datos['timestamp'] else "Sin registro"
            mensaje += f"🔌 *{nombre.capitalize()}*: última señal {ultima}\n"
        chat = self.pending_led_status_request_chat_id or None
        if chat:
            self.send_action_response(chat, mensaje)
        else:
            logging.warning("No hay chat para alerta de desconexión.")

    def timestamp_a_fecha(self, timestamp):
        if not timestamp:
            return "Sin registro"
        tm = time.localtime(timestamp)
        return f"{tm.tm_year}/{tm.tm_mon:02d}/{tm.tm_mday:02d} {tm.tm_hour:02d}:{tm.tm_min:02d}:{tm.tm_sec:02d}"

    def start(self):
        self.bot.infinity_polling()