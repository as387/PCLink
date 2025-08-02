import json
import os
import platform
import psutil
import subprocess
import win32gui
import win32con
import webbrowser
import sys
from telegram.error import Conflict
import io
import qrcode
import ctypes
from PIL import Image, ImageGrab
from typing import Union

import pystray
from PIL import Image
import threading
import asyncio

try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    import comtypes
except ImportError:
    print("Внимание: библиотеки для управления звуком не установлены. Установите: pip install pycaw comtypes")

try:
    import win32gui, win32con
except ImportError:
    print("Внимание: библиотеки для управления Focus Assist не установлены. Установите: pip install pywin32")


# Попробуйте импортировать библиотеки, чтобы проверить их наличие
try:
    import pyperclip
except ImportError:
    print("Внимание: библиотека 'pyperclip' не найдена. Функционал буфера обмена будет недоступен. Установите: pip install pyperclip")
    pyperclip = None

try:
    import pyautogui
except ImportError:
    print("Внимание: библиотека 'pyautogui' не найдена. Скриншоты на Windows могут не работать. Установите: pip install pyautogui")
    pyautogui = None

try:
    import cv2
except ImportError:
    print("Внимание: библиотека 'opencv-python' не найдена. Функция снимка с камеры будет недоступна. Установите: pip install opencv-python")
    cv2 = None

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
    from telegram.ext import (
        ApplicationBuilder,
        CommandHandler,
        CallbackQueryHandler,
        ContextTypes,
        MessageHandler,
        filters
    )
    from telegram.error import BadRequest
except ImportError:
    print("Критическая ошибка: библиотека 'python-telegram-bot' не найдена. Пожалуйста, установите ее: pip install python-telegram-bot")
    sys.exit(1) 

# --- КОНФИГУРАЦИЯ И ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ---
config = {}
user_states = {}  # Хранит состояния пользователей, например, ожидание ввода
user_current_path = {} # Хранит текущий путь в файловом менеджере для каждого пользователя

def load_config():
    """Загружает конфигурацию из файла config.json."""
    global config
    try:
        # Определяем базовую директорию для доступа к bundled-файлам
        # В случае PyInstaller, sys._MEIPASS указывает на временную директорию
        # При обычном запуске sys._MEIPASS не существует, поэтому используем текущую директорию
        base_path = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))
        config_path = os.path.join(base_path, 'config.json') # <-- Вот как нужно указывать путь!

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print("✅ Конфигурация успешно загружена.")
    except FileNotFoundError:
        print(f"❌ Ошибка: Файл 'config.json' не найден по пути: {config_path}. Убедитесь, что он находится рядом с исполняемым файлом.")
        print("Программа будет завершена.")
        sys.exit(1)
    except json.JSONDecodeError:
        print("❌ Ошибка: Некорректный формат JSON в config.json.")
        print("Программа будет завершена.")
        sys.exit(1)
    except Exception as e:
        print(f"⚠️ Критическая ошибка при загрузке конфигурации: {type(e).__name__}: {e}")
        sys.exit(1)

def save_config():
    """Сохраняет текущую конфигурацию в файл config.json."""
    try:
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        print("Конфигурация успешно сохранена.")
    except Exception as e:
        print(f"Ошибка при сохранении конфигурации: {e}")

load_config()

TOKEN = config.get("TOKEN")
OWNER_IDS = config.get("OWNER_IDS", [])

if not TOKEN or not OWNER_IDS:
    print("Ошибка: TOKEN или OWNER_IDS не указаны в config.json.")
    sys.exit(1)

TUTORIAL_TEXT = """
🤖 **Привет! Я твой персональный помощник для управления ПК.**

--- **Главное меню** ---
- **Управление ПК**: Выключение, перезагрузка, выключение монитора и просмотр статуса системы.
- **Системные утилиты**: Доступ к скриншотам, диспетчеру задач, буферу обмена и другим утилитам.
- **Веб-действия**: Быстрое открытие сайтов из вашего списка, добавление и удаление сайтов.
- **Файлы и скрипты**: Мощный файловый менеджер, загрузка файлов по пути и выполнение команд.
- **Генерация QR-кода**: Создание QR-кода из текста или ссылки.
- **Туториал**: Показывает это сообщение.

--- **Управление ПК** ---
- `Выключить ПК`: Полностью выключает компьютер.
- `Перезагрузить ПК`: Перезагружает компьютер.
- `Выключить монитор`: Отключает дисплей.
- `Статус ПК`: Показывает загрузку CPU, RAM и диска.

--- **Системные утилиты** ---
- `Скриншот`: Делает снимок экрана и отправляет его в чат.
- `Диспетчер задач`: Показывает список процессов, отсортированных по памяти, с возможностью их завершения.
- `Буфер обмена`: Позволяет получить текст с ПК или отправить текст на ПК.
- `Мониторинг батареи`: Показывает статус батареи ноутбука.
- `Тест скорости`: Запускает тест скорости интернета (требует `speedtest-cli`).

--- **Файлы и скрипты** ---
- `Файловый менеджер`: Позволяет перемещаться по папкам на ПК, просматривать их содержимое и загружать файлы в чат.
- `Загрузить файл по пути`: Запрашивает полный путь к файлу для загрузки.
- `Запустить команду`: Выполняет консольную команду на ПК.

--- **Важно** ---
- Для безопасности бот реагирует только на команды от пользователей, чьи ID указаны в `OWNER_IDS` в файле `config.json`.
- Некоторые функции требуют установки дополнительных библиотек (`pip install ...`). Бот сообщит, если чего-то не хватает.
"""

# --- ГЕНЕРАЦИЯ КЛАВИАТУР МЕНЮ ---

def get_main_menu_keyboard():
    return [
        [InlineKeyboardButton("🖥️ Управление ПК", callback_data="pc_control_menu"), InlineKeyboardButton("🛠️ Системные утилиты", callback_data="system_utilities_menu")],
        [InlineKeyboardButton("🌐 Веб-действия", callback_data="web_actions_menu"), InlineKeyboardButton("⚙️ Дополнительные функции", callback_data="advanced_features_menu")],
        [InlineKeyboardButton("🔗 Генерация QR-кода", callback_data="qr_code_generator_prompt"), InlineKeyboardButton("📖 Туториал", callback_data="send_tutorial")]
    ]

def get_pc_control_keyboard():
    return [
        [InlineKeyboardButton("🔴 Выключить ПК", callback_data="shutdown"), InlineKeyboardButton("🔄 Перезагрузить ПК", callback_data="restart")],
        [InlineKeyboardButton("⚫ Выключить монитор", callback_data="monitor_off"), InlineKeyboardButton("📊 Статус ПК", callback_data="status")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]
    ]

def get_system_utilities_keyboard():
    return [
        [InlineKeyboardButton("📸 Скриншот", callback_data="screenshot"), InlineKeyboardButton("📈 Диспетчер задач", callback_data="process_list")],
        [InlineKeyboardButton("📋 Буфер обмена", callback_data="clipboard_menu"), InlineKeyboardButton("🔋 Мониторинг батареи", callback_data="battery_status")],
        [InlineKeyboardButton("📷 Снимок с камеры", callback_data="take_photo"), InlineKeyboardButton("🚀 Тест скорости интернета", callback_data="speed_test")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]
    ]

def get_web_actions_keyboard():
    keyboard = []
    for i, site in enumerate(config.get("WEBSITES", [])):
        keyboard.append([
            InlineKeyboardButton(site["name"], callback_data=f"open_website_{i}"),
            InlineKeyboardButton("🗑️", callback_data=f"delete_website_{i}")
        ])
    keyboard.append([InlineKeyboardButton("➕ Добавить сайт", callback_data="add_website_prompt")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")])
    return keyboard

def get_file_script_keyboard():
    return [
        [InlineKeyboardButton("📂 Файловый менеджер", callback_data="file_manager_open")],
        [InlineKeyboardButton("📥 Загрузить файл по пути", callback_data="upload_file_prompt")],
        [InlineKeyboardButton("🚀 Запустить команду", callback_data="run_command_prompt")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]
    ]

def get_clipboard_keyboard():
    return [
        [InlineKeyboardButton("📥 Получить текст с ПК", callback_data="clipboard_get")],
        [InlineKeyboardButton("📤 Отправить текст на ПК", callback_data="clipboard_set_prompt")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="system_utilities_menu")]
    ]

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def get_chat_user_id(update_or_query: Union[Update, CallbackQuery]):
    """Универсально получает chat_id и user_id из Update или CallbackQuery."""
    if isinstance(update_or_query, Update):
        return update_or_query.effective_chat.id, update_or_query.effective_user.id
    # Если это CallbackQuery
    return update_or_query.message.chat_id, update_or_query.from_user.id

def get_advanced_features_keyboard():
    keyboard = [
        [InlineKeyboardButton("⏰ Таймер выключения", callback_data="shutdown_timer_prompt")],
        [InlineKeyboardButton("🔇 Вкл/Выкл звук", callback_data="toggle_sound"),
         InlineKeyboardButton("🧘 Вкл/Выкл фокусировку", callback_data="toggle_focus_assist")],
    ]
    
    # Проверяем, есть ли активный таймер у любого пользователя
    for user_id, data in user_states.items():
        if "shutdown_timer" in data:
            keyboard.insert(1, [InlineKeyboardButton(
                f"❌ Отменить таймер ({data['timer_minutes']} мин)", 
                callback_data="cancel_shutdown_timer"
            )])
            break
            
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")])
    return keyboard

async def send_advanced_features_menu(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    await _send_or_edit_menu(query.message.chat_id, query.from_user.id, "Дополнительные функции ПК:", get_advanced_features_keyboard(), context)

async def _send_or_edit_menu(chat_id: int, user_id: int, text: str, keyboard: list, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет или редактирует сообщение с меню, избегая ошибок."""
    reply_markup = InlineKeyboardMarkup(keyboard)
    last_menu_message_id = user_states.get(user_id, {}).get("last_menu_message_id")

    if last_menu_message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=last_menu_message_id, text=text, reply_markup=reply_markup
            )
            return
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                print(f"Ошибка при редактировании сообщения {last_menu_message_id}: {e}. Отправляю новое.")
    
    new_message = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
    if user_id not in user_states:
        user_states[user_id] = {}
    user_states[user_id]["last_menu_message_id"] = new_message.message_id

# --- ОБРАБОТЧИКИ МЕНЮ ---

async def send_main_menu(update_or_query: Union[Update, CallbackQuery], context: ContextTypes.DEFAULT_TYPE):
    chat_id, user_id = get_chat_user_id(update_or_query)
    await _send_or_edit_menu(chat_id, user_id, "Главное меню:", get_main_menu_keyboard(), context)

async def send_pc_control_menu(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    await _send_or_edit_menu(query.message.chat_id, query.from_user.id, "Управление ПК:", get_pc_control_keyboard(), context)

async def send_system_utilities_menu(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    await _send_or_edit_menu(query.message.chat_id, query.from_user.id, "Системные утилиты:", get_system_utilities_keyboard(), context)

async def send_web_actions_menu(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    await _send_or_edit_menu(query.message.chat_id, query.from_user.id, "Веб-действия:", get_web_actions_keyboard(), context)

async def send_file_script_menu(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    await _send_or_edit_menu(query.message.chat_id, query.from_user.id, "Файлы и скрипты:", get_file_script_keyboard(), context)

async def send_clipboard_menu(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    await _send_or_edit_menu(query.message.chat_id, query.from_user.id, "Управление буфером обмена:", get_clipboard_keyboard(), context)

# --- ОСНОВНЫЕ ОБРАБОТЧИКИ КОМАНД И СООБЩЕНИЙ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in OWNER_IDS:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    await send_main_menu(update, context)

async def set_shutdown_timer_prompt(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    """Запрашивает время для таймера выключения"""
    prompt_msg = await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Введите время в минутах, через которое выключить ПК:"
    )
    user_states[query.from_user.id] = {
        "state": "awaiting_shutdown_timer",
        "prompt_message_id": prompt_msg.message_id,
        "last_menu_message_id": query.message.message_id
    }

async def set_focus_assist_mode(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, mode: int):
    """Устанавливает конкретный режим Focus Assist (0-выкл, 1-приоритет, 2-только будильники)"""
    try:
        if platform.system() == "Windows":
            hwnd = win32gui.FindWindow("Windows.UI.Core.CoreWindow", "Помощник по сосредоточению")
            if hwnd:
                # 0x1001 - команда установки конкретного режима
                win32gui.PostMessage(hwnd, win32con.WM_COMMAND, 0x1001, mode)
                await query.answer(f"Режим фокусировки установлен: {mode}", show_alert=True)
            else:
                await query.answer("Не удалось найти окно Помощника по сосредоточению", show_alert=True)
        else:
            await query.answer("Эта функция доступна только на Windows", show_alert=True)
    except Exception as e:
        print(f"Ошибка при установке Focus Assist: {e}")
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Основной обработчик всех кнопок."""
    query = update.callback_query
    await query.answer()

    # Проверка прав доступа
    if query.from_user.id not in OWNER_IDS:
        await context.bot.send_message(chat_id=query.message.chat_id, text="⛔ Доступ запрещён.")
        return

    action = query.data
    
    # Словарь простых действий, которые не требуют дополнительной обработки
    simple_actions = {
        "main_menu": send_main_menu,
        "pc_control_menu": send_pc_control_menu,
        "system_utilities_menu": send_system_utilities_menu,
        "web_actions_menu": send_web_actions_menu,
        "advanced_features_menu": send_advanced_features_menu,
        "file_script_menu": send_file_script_menu,
        "clipboard_menu": send_clipboard_menu,
        "shutdown": shutdown_pc,
        "restart": restart_pc,
        "monitor_off": turn_off_monitor,
        "status": get_pc_status,
        "screenshot": take_screenshot,
        "battery_status": get_battery_status,
        "speed_test": run_speed_test,
        "process_list": list_processes,
        "file_manager_open": file_manager_handler,
        "clipboard_get": get_clipboard,
        "take_photo": take_photo,
        "send_tutorial": send_tutorial_file,
        "toggle_sound": toggle_sound,
        "toggle_focus_assist": toggle_focus_assist,
        "cancel_shutdown_timer": cancel_shutdown_timer,
    }

    # Обработка простых действий
    if action in simple_actions:
        await simple_actions[action](query, context)
        return
        
    # Обработка действий с префиксами
    if action.startswith("open_website_"): 
        await open_website(query, context)
    elif action.startswith("delete_website_"): 
        await delete_website(query, context)
    elif action.startswith("proc_kill_"): 
        await kill_process(query, context)
    elif action.startswith("fm_nav_"): 
        await file_manager_handler(query, context)
    elif action.startswith("fm_upload_"): 
        await file_manager_upload_handler(query, context)
    
    # Обработка действий, требующих ввода данных
    elif action.endswith("_prompt"):
        prompts = {
            "qr_code_generator_prompt": ("awaiting_qr_text", "Отправьте текст или ссылку для QR-кода:"),
            "add_website_prompt": ("awaiting_website_name", "Введите название сайта (например, 'Мой YouTube'):"),
            "upload_file_prompt": ("awaiting_file_path", "Отправьте полный путь к файлу."),
            "run_command_prompt": ("awaiting_command", "Отправьте команду для выполнения."),
            "clipboard_set_prompt": ("awaiting_clipboard_text", "Отправьте текст для буфера обмена."),
            "shutdown_timer_prompt": ("awaiting_shutdown_timer", "Введите время в минутах для таймера выключения:"),
        }
        
        if action in prompts:
            state, text = prompts[action]
            prompt_msg = await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=text
            )
            user_states[query.from_user.id] = {
                "state": state,
                "prompt_message_id": prompt_msg.message_id,
                "last_menu_message_id": query.message.message_id
            }
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Неизвестная команда. Пожалуйста, попробуйте снова."
        )
        await send_main_menu(query, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения, когда бот ожидает ввода."""
    user_id = update.effective_user.id
    if user_id not in OWNER_IDS:
        return

    # Пытаемся удалить сообщение пользователя для чистоты чата
    try:
        await context.bot.delete_message(
            chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
    except Exception:
        pass

    state_data = user_states.get(user_id, {})
    current_state = state_data.get("state")

    # Если нет активного состояния, проверяем команду /qr
    if not current_state:
        if update.message.text.startswith("/qr "):
            text_to_encode = update.message.text[4:].strip()
            if text_to_encode:
                await generate_qr_code(update, context, text_to_encode)
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Неизвестная команда. Используйте /start."
            )
        await send_main_menu(update, context)
        return

    # Удаляем prompt-сообщение бота, если оно есть
    if "prompt_message_id" in state_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=state_data["prompt_message_id"]
            )
        except Exception:
            pass

    text = update.message.text.strip()
    user_states.pop(user_id, None)  # Очищаем состояние пользователя

    # Обработка различных состояний
    if current_state == "awaiting_file_path":
        await upload_file(update, context, os.path.normpath(text.strip('"')))
    
    elif current_state == "awaiting_command":
        await run_custom_command(update, context, text)
    
    elif current_state == "awaiting_qr_text":
        await generate_qr_code(update, context, text)
    
    elif current_state == "awaiting_clipboard_text":
        await set_clipboard(update, context, text)
    
    elif current_state == "awaiting_website_name":
        # Сохраняем название сайта и запрашиваем URL
        state_data["site_name"] = text
        state_data["state"] = "awaiting_website_url"
        prompt_msg_url = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Хорошо, '{text}'. Теперь введите полный URL сайта:"
        )
        state_data["prompt_message_id"] = prompt_msg_url.message_id
        user_states[user_id] = state_data
        return
    
    elif current_state == "awaiting_website_url":
        if state_data.get("site_name") and text:
            await add_website(update, context, state_data["site_name"], text)
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Ошибка: Не удалось получить название или URL."
            )


    elif current_state == "awaiting_shutdown_timer":
        try:
            minutes = int(text)
            if minutes <= 0:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Введите положительное число минут."
                )
                return
            
            # Устанавливаем таймер
            if platform.system() == "Windows":
                os.system(f"shutdown /s /t {minutes * 60}")
            else:
                os.system(f"shutdown -h +{minutes}")
            
            # Сохраняем информацию о таймере
            user_id = update.effective_user.id
            user_states[user_id] = {
                "shutdown_timer": True,
                "timer_minutes": minutes
            }
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"⏰ Таймер установлен! ПК выключится через {minutes} минут.\n"
                     "Для отмены используйте кнопку в меню дополнительных функций."
            )
        except ValueError:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Пожалуйста, введите число."
            )
    
    elif current_state == "awaiting_shutdown_timer":
        try:
            minutes = int(text)
            if minutes <= 0:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Введите положительное число минут."
                )
            else:
                seconds = minutes * 60
                if platform.system() == "Windows":
                    cmd = f"shutdown /s /t {seconds}"
                else:
                    cmd = f"shutdown -h +{minutes}"

                os.system(cmd)
                user_states[user_id] = {
                    "shutdown_timer": True,
                    "timer_minutes": minutes
                }
                
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"⏳ Таймер установлен! ПК выключится через {minutes} минут.\n"
                         "Для отмены используйте кнопку 'Отменить таймер'."
                )
        except ValueError:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Пожалуйста, введите число."
            )
    
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Неизвестное состояние. Возвращаюсь в главное меню."
        )

    # Возвращаем пользователя в главное меню после обработки
    await send_main_menu(update, context)

async def set_shutdown_timer(update: Update, context: ContextTypes.DEFAULT_TYPE, minutes: int):
    """Устанавливает таймер выключения ПК"""
    try:
        minutes = int(minutes)
        if minutes <= 0:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Введите положительное число минут.")
            return

        seconds = minutes * 60
        if platform.system() == "Windows":
            cmd = f"shutdown /s /t {seconds}"
        else:
            cmd = f"shutdown -h +{minutes}"

        os.system(cmd)
        user_id = update.effective_user.id
        user_states[user_id] = {"shutdown_timer": True, "timer_minutes": minutes}
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⏳ Таймер установлен! ПК выключится через {minutes} минут.\n"
                 "Для отмены используйте кнопку 'Отменить таймер'."
        )
    except ValueError:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Пожалуйста, введите число.")

async def cancel_shutdown_timer(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет запланированное выключение"""
    try:
        if platform.system() == "Windows":
            os.system("shutdown /a")  # Отмена выключения на Windows
        else:
            os.system("shutdown -c")  # Отмена выключения на Linux/Mac
        
        # Удаляем информацию о таймере
        user_id = query.from_user.id
        if user_id in user_states and "shutdown_timer" in user_states[user_id]:
            del user_states[user_id]["shutdown_timer"]
        
        await query.answer("Таймер выключения отменён!", show_alert=True)
        await send_advanced_features_menu(query, context)
    except Exception as e:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"❌ Ошибка при отмене таймера: {e}"
        )

async def toggle_sound(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    """Переключает системный звук (mute/unmute)"""
    try:
        if platform.system() == "Windows":
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            
            is_muted = volume.GetMute()
            volume.SetMute(not is_muted, None)
            
            status = "выключен 🔇" if not is_muted else "включен 🔊"
            await query.answer(f"Звук {status}", show_alert=True)
        else:
            await query.answer("Эта функция доступна только на Windows", show_alert=True)
    except Exception as e:
        print(f"Ошибка при переключении звука: {e}")
        await query.answer("❌ Ошибка при переключении звука", show_alert=True)

async def toggle_focus_assist(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    try:
        if platform.system() != "Windows":
            await query.answer("Эта функция доступна только на Windows", show_alert=True)
            return

        # Альтернативный метод через PowerShell
        try:
            ps_command = """
            $prefs = Get-WindowsFocusAssist
            if ($prefs.State -eq "PriorityOnly") {
                Set-WindowsFocusAssist -State Off
                "Режим фокусировки выключен"
            } else {
                Set-WindowsFocusAssist -State PriorityOnly
                "Режим фокусировки включен (приоритетные уведомления)"
            }
            """
            result = subprocess.run(["powershell", "-Command", ps_command], capture_output=True, text=True, shell=True)
            output = result.stdout.strip() or "Состояние изменено"
            await query.answer(output, show_alert=True)
        except Exception as ps_error:
            print(f"PowerShell метод не сработал: {ps_error}")
            await query.answer("❌ Ошибка PowerShell. Попробуйте вручную.", show_alert=True)
    except Exception as e:
        print(f"Общая ошибка: {e}")
        await query.answer("❌ Не удалось переключить фокусировку", show_alert=True)

async def take_photo(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    if cv2 is None:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="❌ OpenCV не установлен. Установите: `pip install opencv-python`"
        )
        return

    await context.bot.send_message(chat_id=query.message.chat_id, text="📷 Ищу физическую камеру...")

    # Пробуем камеры 0 и 1 (стандартные индексы для встроенной/внешней камеры)
    for camera_index in [0, 1]:
        cap = None
        try:
            # Явно указываем CAP_DSHOW для Windows и избегаем iVCam
            cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            
            if not cap.isOpened():
                continue  # Пропускаем, если камера не открылась

            # Даём камере 5 попыток на инициализацию
            for _ in range(5):
                cap.read()

            # Делаем снимок
            ret, frame = cap.read()
            
            # Проверяем, что это не iVCam (пустой/чёрный кадр или надпись)
            if not ret or frame is None or frame.mean() < 10:
                continue  # Пропускаем "битые" кадры

            # Конвертируем в RGB и отправляем
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(image)
            
            byte_arr = io.BytesIO()
            pil_image.save(byte_arr, format='JPEG')
            byte_arr.seek(0)
            
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=byte_arr,
                caption=f"Снимок с камеры #{camera_index}"
            )
            return  # Успех — выходим из цикла

        except Exception as e:
            print(f"Ошибка с камерой #{camera_index}: {e}")
            continue

        finally:
            if cap is not None:
                cap.release()  # Важно освободить камеру!

    # Если дошли сюда — ни одна камера не сработала
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="❌ Не удалось сделать снимок. Проверьте:\n"
             "1. Физическая камера подключена\n"
             "2. Нет других программ, использующих камеру\n"
             "3. iVCam отключён в Диспетчере устройств"
    )

# --- РЕАЛИЗАЦИЯ ФУНКЦИЙ ---

async def shutdown_pc(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=query.message.chat_id, text="🔴 Выключаю ПК...")
    cmd = "shutdown /s /t 1" if platform.system() == "Windows" else "poweroff"
    os.system(cmd)

async def restart_pc(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=query.message.chat_id, text="🔄 Перезагружаю ПК...")
    cmd = "shutdown /r /t 1" if platform.system() == "Windows" else "reboot"
    os.system(cmd)

async def turn_off_monitor(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    try:
        if platform.system() == "Windows": ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
        elif platform.system() == "Linux": os.system("xset dpms force off")
        await context.bot.send_message(chat_id=query.message.chat_id, text="⚫ Монитор выключен.")
    except Exception as e: await context.bot.send_message(chat_id=query.message.chat_id, text=f"❌ Ошибка: {e}")

async def get_pc_status(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    status_text = (f"💻 **Статус ПК**\n\n"
                   f"🔸 **CPU**: {psutil.cpu_percent(interval=1)}%\n"
                   f"🔸 **RAM**: {psutil.virtual_memory().percent}% \n"
                   f"🔸 **Диск**: {psutil.disk_usage('/').percent}%")
    await context.bot.send_message(chat_id=query.message.chat_id, text=status_text, parse_mode='Markdown')

async def take_screenshot(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=query.message.chat_id, text="📸 Делаю скриншот...")
    try:
        screenshot = pyautogui.screenshot() if platform.system() == "Windows" and pyautogui else ImageGrab.grab()
        byte_arr = io.BytesIO()
        screenshot.save(byte_arr, format='PNG')
        byte_arr.seek(0)
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=byte_arr, caption="Скриншот рабочего стола")
    except Exception as e: await context.bot.send_message(chat_id=query.message.chat_id, text=f"❌ Ошибка: {e}.")

async def get_battery_status(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    try:
        battery = psutil.sensors_battery()
        if not battery:
            await context.bot.send_message(chat_id=query.message.chat_id, text="Информация о батарее недоступна.")
            return
        plugged = "🔌 Заряжается" if battery.power_plugged else "🔋 От батареи"
        time_left = "неограниченно"
        if battery.secsleft and battery.secsleft < psutil.POWER_TIME_UNLIMITED:
            mins, _ = divmod(battery.secsleft, 60)
            hours, mins = divmod(mins, 60)
            time_left = f"{hours}ч {mins}мин"
        text = f"**Статус батареи**\n- Заряд: {battery.percent}%\n- Статус: {plugged}\n- Осталось: {time_left}"
        await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='Markdown')
    except Exception as e: await context.bot.send_message(chat_id=query.message.chat_id, text=f"❌ Ошибка: {e}")

async def run_speed_test(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=query.message.chat_id, text="🚀 Запускаю тест скорости...")
    try:
        result = subprocess.run(["speedtest-cli", "--simple"], capture_output=True, text=True, check=True)
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"**Результаты:**\n```\n{result.stdout}\n```", parse_mode='MarkdownV2')
    except FileNotFoundError: await context.bot.send_message(chat_id=query.message.chat_id, text="❌ Ошибка: `speedtest-cli` не найден.")
    except Exception as e: await context.bot.send_message(chat_id=query.message.chat_id, text=f"❌ Ошибка: {e}")

async def list_processes(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    await query.answer("Собираю список процессов...")
    processes = sorted([p.info for p in psutil.process_iter(['pid', 'name', 'memory_percent']) if p.info['memory_percent']], key=lambda p: p['memory_percent'], reverse=True)[:15]
    keyboard = [[InlineKeyboardButton(f"❌ {p['name']} ({p['pid']})", callback_data=f"proc_kill_{p['pid']}")] for p in processes]
    keyboard.extend([[InlineKeyboardButton("🔄 Обновить", callback_data="process_list")], [InlineKeyboardButton("⬅️ Назад", callback_data="system_utilities_menu")]])
    try:
        await query.edit_message_text(text="📈 **Топ 15 процессов по памяти:**", reply_markup=InlineKeyboardMarkup(keyboard))
    except BadRequest as e:
        if "Message is not modified" not in str(e): print(f"Error updating process list: {e}")

async def kill_process(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    pid = int(query.data.replace("proc_kill_", ""))
    try:
        p = psutil.Process(pid)
        p.kill()
        await query.answer(f"Процесс {pid} ({p.name()}) завершен.", show_alert=True)
    except psutil.NoSuchProcess: await query.answer("Процесс уже не существует.", show_alert=True)
    except psutil.AccessDenied: await query.answer("Отказано в доступе.", show_alert=True)
    await list_processes(query, context)

async def get_clipboard(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    if not pyperclip: return
    try: await context.bot.send_message(chat_id=query.message.chat_id, text=f"`{pyperclip.paste()}`", parse_mode='MarkdownV2')
    except Exception as e: await context.bot.send_message(chat_id=query.message.chat_id, text=f"❌ Ошибка: {e}")

async def set_clipboard(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    if not pyperclip: return
    try:
        pyperclip.copy(text)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Текст скопирован в буфер обмена ПК.")
    except Exception as e: await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Ошибка: {e}")

async def open_website(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    site = config["WEBSITES"][int(query.data.replace("open_website_", ""))]
    webbrowser.open_new_tab(site["url"])
    await context.bot.send_message(chat_id=query.message.chat_id, text=f"🌐 Сайт '{site['name']}' открыт.")

async def add_website(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str, url: str):
    config.setdefault("WEBSITES", []).append({"name": name, "url": url})
    save_config()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"✅ Сайт '{name}' добавлен!")

async def delete_website(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    deleted_site = config["WEBSITES"].pop(int(query.data.replace("delete_website_", "")))
    save_config()
    await query.answer(f"Сайт '{deleted_site['name']}' удален.", show_alert=True)
    await send_web_actions_menu(query, context)

async def upload_file(update: Union[Update, CallbackQuery], context: ContextTypes.DEFAULT_TYPE, file_path: str):
    chat_id = get_chat_user_id(update)[0]
    if not os.path.isfile(file_path):
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Ошибка: Файл не найден или это не файл.")
        return
    try:
        await context.bot.send_message(chat_id=chat_id, text=f"📥 Загружаю: `{os.path.basename(file_path)}`...")
        with open(file_path, 'rb') as f: await context.bot.send_document(chat_id=chat_id, document=f)
    except Exception as e: await context.bot.send_message(chat_id=chat_id, text=f"❌ Ошибка при загрузке: {e}")

async def run_custom_command(update: Update, context: ContextTypes.DEFAULT_TYPE, command: str):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🚀 Выполняю: `{command}`")
    try:
        result = subprocess.run(command.split(), capture_output=True, text=True, check=False, encoding='cp866', errors='ignore')
        response = f"✅ **Результат**:\n```\n{result.stdout or '(пусто)'}\n```"
        if result.stderr: response += f"\n⚠️ **Ошибки**:\n```\n{result.stderr}\n```"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response[:4090], parse_mode='MarkdownV2')
    except Exception as e: await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Ошибка: {e}")

async def file_manager_handler(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    user_id = query.from_user.id
    current_path = user_current_path.get(user_id, os.path.expanduser("~"))
    action = query.data

    if action == "fm_nav_..": path = os.path.dirname(current_path)
    elif action.startswith("fm_nav_"): path = os.path.join(current_path, action.replace("fm_nav_", ""))
    else: path = current_path

    if not os.path.isdir(path):
        await query.answer("Ошибка: это не папка.", show_alert=True)
        return

    user_current_path[user_id] = path
    keyboard = []
    try:
        if os.path.dirname(path) != path: keyboard.append([InlineKeyboardButton("⬆️ .. (Наверх)", callback_data="fm_nav_..")])
        items = os.listdir(path)
        dirs = sorted([d for d in items if os.path.isdir(os.path.join(path, d))])
        files = sorted([f for f in items if os.path.isfile(os.path.join(path, f))])
        for d in dirs: keyboard.append([InlineKeyboardButton(f"📁 {d}", callback_data=f"fm_nav_{d}")])
        for f in files: keyboard.append([InlineKeyboardButton(f"📄 {f}", callback_data=f"fm_upload_{f}")])
    except Exception as e: keyboard.append([InlineKeyboardButton(f"Ошибка доступа: {e}", callback_data="no_action")])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад в меню", callback_data="file_script_menu")])
    display_path = path if len(path) < 60 else f"...{path[-57:]}"
    try:
        await query.edit_message_text(text=f"**Файловый менеджер**\n`{display_path}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='MarkdownV2')
    except BadRequest as e:
        if "Message is not modified" not in str(e): print(f"Error updating file manager: {e}")

async def file_manager_upload_handler(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    current_path = user_current_path.get(query.from_user.id, os.path.expanduser("~"))
    file_name = query.data.replace("fm_upload_", "")
    await query.answer(f"Загружаю {file_name}...")
    await upload_file(query, context, os.path.join(current_path, file_name))

async def generate_qr_code(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    byte_arr = io.BytesIO()
    qrcode.make(text).save(byte_arr, format="PNG")
    byte_arr.seek(0)
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=byte_arr, caption=f"`{text}`", parse_mode='MarkdownV2')

async def send_tutorial_file(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=query.message.chat_id, text=TUTORIAL_TEXT, parse_mode='Markdown')

# Глобальные переменные для управления ботом из трея
bot_running = False
bot_thread = None
application_instance = None # Храним экземпляр ApplicationBuilder
bot_loop = None

async def run_bot_async():
    global bot_running, application_instance
    bot_running = True
    try:
        application_instance = ApplicationBuilder().token(TOKEN).build()
        application_instance.add_handler(CommandHandler("start", start))
        application_instance.add_handler(CommandHandler("qr", handle_message))
        application_instance.add_handler(CallbackQueryHandler(button_handler))
        application_instance.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        print("🤖 Бот запущен (из трея)...")
        await application_instance.initialize()
        await application_instance.updater.start_polling()
        await application_instance.start()

        while bot_running: # Бесконечный цикл, пока бот должен работать
            await asyncio.sleep(1)

    except Conflict:
        print("⚠️ Ошибка: Убедитесь, что не запущены другие экземпляры бота!")
    except asyncio.CancelledError:
        print("🛑 Бот остановлен (через трей).")
    except Exception as e:
        print(f"⚠️ Критическая ошибка бота: {type(e).__name__}: {e}")
    finally:
        if application_instance:
            print("⏳ Останавливаю бота (из трея)...")
            try:
                await application_instance.updater.stop()
                await application_instance.stop()
                await application_instance.shutdown()
            except Exception as e:
                print(f"⚠️ Ошибка при остановке бота (из трея): {e}")
        bot_running = False
        print("✅ Бот успешно остановлен (из трея)")

def run_bot_in_thread_target():
    """Целевая функция для запуска asyncio в отдельном потоке."""
    global bot_loop # <<< ДОБАВЬТЕ global bot_loop
    bot_loop = asyncio.new_event_loop() # <<< bot_loop теперь глобальный
    asyncio.set_event_loop(bot_loop)
    bot_loop.run_until_complete(run_bot_async())

def stop_bot_in_thread(icon):
    global bot_thread, bot_running, bot_loop # <<< ДОБАВЬТЕ global bot_loop
    if bot_running and bot_thread and bot_thread.is_alive():
        print("Останавливаю бота...")
        # Важно: используем bot_loop, а не asyncio.get_event_loop()
        if bot_loop and bot_loop.is_running():
            asyncio.run_coroutine_threadsafe(stop_bot_async(), bot_loop)

        bot_thread.join(timeout=5) # Ждем завершения потока до 5 секунд
        if bot_thread.is_alive():
            print("Бот не завершился в срок. Возможно, потребуется принудительная остановка.")
        icon.notify("Бот Telegram остановлен.", "PCLink")
    else:
        print("Бот не запущен или уже остановлен.")

def start_bot_in_thread(icon):
    global bot_thread, bot_running
    if not bot_running:
        print("Запускаю бота в новом потоке...")
        # Создаем новый цикл событий для нового потока
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        bot_thread = threading.Thread(target=lambda: new_loop.run_until_complete(run_bot_async()))
        bot_thread.start()
        icon.notify("Бот Telegram запущен!", "PCLink")
        print("Бот запущен.")
    else:
        print("Бот уже запущен.")

async def stop_bot_async():
    global bot_running, application_instance
    if bot_running and application_instance:
        bot_running = False # Устанавливаем флаг для остановки цикла
        # Попытка остановить updater извне, если он активен
        if application_instance.updater and application_instance.updater.running:
             await application_instance.updater.stop()
        if application_instance.running:
            await application_instance.stop()
        print("Сигнал остановки бота отправлен.")
    else:
        print("Бот не запущен.")

def exit_app(icon):
    stop_bot_in_thread(icon)
    icon.stop()
    print("Приложение закрыто.")

if __name__ == "__main__":
    # Загружаем конфигурацию перед созданием иконки
    load_config()

    # Проверяем наличие файла иконки
    icon_path = "PCLink.ico" # <--- Эту строку нужно изменить
    if not os.path.exists(icon_path):
        print(f"Ошибка: Файл иконки '{icon_path}' не найден. Убедитесь, что он находится рядом с исполняемым файлом.")
        # Можно использовать иконку по умолчанию или выйти
        sys.exit(1)

    image = Image.open(icon_path) # <--- Эту строку нужно изменить

    menu = (pystray.MenuItem("Запустить бота", start_bot_in_thread),
            pystray.MenuItem("Остановить бота", stop_bot_in_thread),
            pystray.MenuItem("Выход", exit_app))

    icon = pystray.Icon("PCLinkBot", image, "PCLink Bot", menu)

    print("Приложение PCLink Bot запущено в системном трее.")
    # Запускаем иконку трея в отдельном потоке
    icon.run()

    menu = (pystray.MenuItem("Запустить бота", start_bot_in_thread),
            pystray.MenuItem("Остановить бота", stop_bot_in_thread),
            pystray.MenuItem("Выход", exit_app))

    icon = pystray.Icon("PCLinkBot", image, "PCLink Bot", menu)

    print("Приложение PCLink Bot запущено. Иконка должна появиться в трее.")
    try:
        icon.run() # Этот вызов блокирующий, он запускает цикл иконки трея
    except KeyboardInterrupt:
        print("\n👋 Программа завершена через закрытие трея.")
    except Exception as e:
        print(f"⚠️ Критическая ошибка при работе иконки трея: {e}")