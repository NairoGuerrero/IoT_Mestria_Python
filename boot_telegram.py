import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import os

load_dotenv()  # Cargar variables del archivo .env

class BotTelegram:
    def __init__(self, publish_funtion):
        self.publish_function = publish_funtion
        self.token = os.getenv("TELEGRAM_API_TOKEN")
        self.bot = telebot.TeleBot(self.token)
        self.register_handlers()

    def create_inline_menu(self):
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("💡 LED Nairo", callback_data="led_nairo"),
            InlineKeyboardButton("💡 LED Alejandro", callback_data="led_alejandro"),
            InlineKeyboardButton("🌡️ Temperatura", callback_data="temperatura"),
            InlineKeyboardButton("💧 Humedad", callback_data="humedad")
        )
        return keyboard

    def register_handlers(self):
        self.bot.message_handler(commands=['start', 'help'])(self.handle_start_help)
        self.bot.message_handler(func=lambda message: True)(self.handle_text_message)
        self.bot.callback_query_handler(func=lambda call: True)(self.handle_button)

    def handle_start_help(self, message):
        self.bot.send_message(
            message.chat.id,
            "Bienvenido al sistema IoT 👋\nSelecciona una opción del menú:",
            reply_markup=self.create_inline_menu()
        )

    def handle_text_message(self, message):
        self.bot.send_message(
            message.chat.id,
            "Selecciona una opción del menú:",
            reply_markup=self.create_inline_menu()
        )

    def handle_button(self, call):
        self.bot.answer_callback_query(call.id)

        response = ""
        action = ""

        if call.data == "led_nairo":
            response = "🔆 LED Nairo activado/desactivado"
            action = "led_nairo"

        elif call.data == "led_alejandro":
            response = "🔆 LED Alejandro activado/desactivado"
            action = "led_alejandro"

        elif call.data == "temperatura":
            response = "🌡️ Consultando temperatura..."
            action = "temperatura"

        elif call.data == "humedad":
            response = "💧 Consultando humedad..."
            action = "humedad"

        # Enviar respuesta
        if response:
            self.bot.send_message(call.message.chat.id, response)

        # Volver a enviar el menú
        self.bot.send_message(
            call.message.chat.id,
            "Selecciona otra opción del menú:",
            reply_markup=self.create_inline_menu()
        )

    def start(self):
        self.bot.infinity_polling()
