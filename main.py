#- Inicio e importaciones, configuración, utilidades básicas
import os
import json
import asyncio
from datetime import datetime, timedelta, time as dt_time
import pytz
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

# === CARGAR TOKEN DESDE .env ===
load_dotenv()

# === CONFIG ===
DB_FILE = "pepegotchi_db.json"
IMAGES_PATH = "images"
TZ = pytz.timezone("America/Tegucigalpa")
# Frecuencia del bucle de fondo (segundos)
BACKGROUND_SLEEP = 30
from telegram.ext import CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# === TIENDA PEPEGOTCHI ===

TIENDA = {
    "mosca": {"precio": 50, "xp": 30, "energia": 0},
    "mosquito": {"precio": 75, "xp": 50, "energia": 0},
    "araña": {"precio": 100, "xp": 100, "energia": 0},
    "paseo": {"precio": 100, "xp": 45, "energia": 0},
    "polillas": {"precio": 125, "xp": 50, "energia": 0},
    "pocion": {"precio": 300, "xp": 0, "energia": 100},
}

async def tienda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    datos = cargar_datos()

    if user_id not in datos["usuarios"]:
        await update.message.reply_text("Primero inicia tu Pepegotchi con /start")
        return

    usuario = datos["usuarios"][user_id]

    texto = (
        "🛒 *Tienda Pepegotchi*\n\n"
        f"Tienes 💰 {usuario['monedas']} monedas\n\n"
        "Elige un artículo abajo:"
    )

    # Botones
    teclado = [
        [InlineKeyboardButton("🪰 Mosca (50)", callback_data="buy_mosca")],
        [InlineKeyboardButton("🦟 Mosquito (75)", callback_data="buy_mosquito")],
        [InlineKeyboardButton("🕷 Araña (100)", callback_data="buy_araña")],
        [InlineKeyboardButton("🌿 Paseo (100)", callback_data="buy_paseo")],
        [InlineKeyboardButton("🦋 Polillas (125)", callback_data="buy_polillas")],
        [InlineKeyboardButton("🧪 Poción (300)", callback_data="buy_pocion")],
    ]
    reply_markup = InlineKeyboardMarkup(teclado)

    await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=reply_markup)


async def comprar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    datos = cargar_datos()

    if user_id not in datos["usuarios"]:
        await query.edit_message_text("Primero inicia tu Pepegotchi con /start")
        return

    accion = query.data.replace("buy_", "")  # buy_mosca → mosca

    if accion not in TIENDA:
        await query.edit_message_text("Ese artículo no existe.")
        return

    usuario = datos["usuarios"][user_id]
    item = TIENDA[accion]

    # Validar dinero
    if usuario["monedas"] < item["precio"]:
        await query.edit_message_text("No tienes suficientes monedas 💸")
        return

    # Aplicar compra
    usuario["monedas"] -= item["precio"]
    usuario["xp"] += item["xp"]
    usuario["energia"] = min(100, usuario["energia"] + item["energia"])

    guardar_datos(datos)

    await query.edit_message_text(
        f"🎉 Compraste *{accion}*!\n"
        f"+{item['xp']} XP ✨\n"
        f"+{item['energia']} ⚡ energía\n"
        f"Monedas restantes: {usuario['monedas']} 💰",
        parse_mode="Markdown"
    )
# === UTIL: LOAD / SAVE DB (seguros y optimizados) ===
def cargar_datos():
    if not os.path.exists(DB_FILE):
        return {"usuarios": {}}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        # si falla al leer, devolver estructura vacía para no bloquear el bot
        return {"usuarios": {}}

def guardar_datos(data):
    # write atomically: escribir en temporal y renombrar
    tmp = DB_FILE + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp, DB_FILE)
    except Exception:
        # fallback simple
        with open(DB_FILE, "w") as f:
            json.dump(data, f, indent=4)

# === AUX: asegurarse de que el usuario tiene todas las claves necesarias ===
def asegurar_usuario(datos, user_id, nombre=None):
    if user_id not in datos["usuarios"]:
        datos["usuarios"][user_id] = {
            "nombre": nombre or "Jugador",
            "xp": 0,
            "monedas": 50,
            "referidos": [],
            "codigo": user_id[-5:],
            "inventario": {},
            "ultimo_sueno": None,
            "is_sleeping": False,
            "sleep_until": None,
            "ultimo_checkin": None,
            "ultimo_rango": None,
            "energia": 100,
            "daily": {
                "date": None,
                "alimentar": 0,
                "jugar": 0
            }
        }
    user = datos["usuarios"][user_id]
    # asegurar claves en DB antigua
    user.setdefault("monedas", 50)
    user.setdefault("inventario", {})
    user.setdefault("ultimo_sueno", None)
    user.setdefault("is_sleeping", False)
    user.setdefault("sleep_until", None)
    user.setdefault("ultimo_checkin", None)
    user.setdefault("ultimo_rango", obtener_rango(user.get("xp", 0)))
    user.setdefault("energia", 100)
    user.setdefault("daily", {"date": None, "alimentar": 0, "jugar": 0})
    # si falta alguna subclave, setearla
    daily = user["daily"]
    daily.setdefault("date", None)
    daily.setdefault("alimentar", 0)
    daily.setdefault("jugar", 0)
    return user

# === RANGOS / IMAGENES ===
def obtener_rango(exp):
    if exp < 1000:
        return "🐸 Bebé"
    elif exp < 5000:
        return "🐢 Joven"
    elif exp < 10000:
        return "🐊 Adulto"
    elif exp < 20000:
        return "🐉 Legendario"
    elif exp < 40000:
        return "🔥 Legendario Supremo"
    elif exp < 60000:
        return "🌀 Maestro"
    else:
        return "👑 Divino"

def imagen_por_rango(exp):
    if exp < 1000:
        return f"{IMAGES_PATH}/bebe.png"
    elif exp < 5000:
        return f"{IMAGES_PATH}/joven.png"
    elif exp < 10000:
        return f"{IMAGES_PATH}/adulto.png"
    elif exp < 20000:
        return f"{IMAGES_PATH}/legendario.png"
    elif exp < 40000:
        return f"{IMAGES_PATH}/legendario_supremo.png"
    elif exp < 60000:
        return f"{IMAGES_PATH}/maestro.png"
    else:
        return f"{IMAGES_PATH}/divino.png"

# === AUX: manejo de día local (YYYY-MM-DD) ===
def fecha_local_hoy():
    return datetime.now(TZ).strftime("%Y-%m-%d")

# === AUX: reiniciar contadores diarios de un usuario ===
def reiniciar_contadores_diarios(user):
    user["daily"]["date"] = fecha_local_hoy()
    user["daily"]["alimentar"] = 0
    user["daily"]["jugar"] = 0

# === AUX: revisar si hay subida de rango ===
async def revisar_rango(update_or_bot, user_id, datos, via_update=True):
    user = datos["usuarios"][user_id]
    xp = user.get("xp", 0)
    nuevo_rango = obtener_rango(xp)
    if user.get("ultimo_rango") != nuevo_rango:
        # animación corta si es via_update (un Update); si es bot (background) usaremos send_message
        try:
            if via_update:
                await update_or_bot.message.reply_text("✨ Evolucionando...")
            else:
                await update_or_bot.send_message(chat_id=int(user_id), text="✨ Evolucionando...")
        except Exception:
            pass
        user["ultimo_rango"] = nuevo_rango
        bonus_monedas = 100
        user["monedas"] = user.get("monedas", 0) + bonus_monedas
        guardar_datos(datos)
        texto = (
            f"🌟 ¡Tu Pepegotchi ha subido al rango *{nuevo_rango}*! 🎉\n"
            f"🎁 Has ganado +{bonus_monedas} monedas"
        )
        try:
            if via_update:
                await update_or_bot.message.reply_text(texto, parse_mode="Markdown")
            else:
                await update_or_bot.send_message(chat_id=int(user_id), text=texto, parse_mode="Markdown")
        except Exception:
            pass
# - Comandos principales y funciones de interacción

# === COMANDO /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = cargar_datos()
    user_id = str(update.effective_user.id)
    nombre = update.effective_user.first_name
    user = asegurar_usuario(datos, user_id, nombre)
    guardar_datos(datos)

    imagen = imagen_por_rango(user["xp"])
    texto = (
        f"🐸 ¡Hola {nombre}! Bienvenido a *Pepegotchi Bot* 💚\n\n"
        f"✨ Cuida, alimenta y haz crecer a tu Pepegotchi.\n"
        f"💰 Monedas: {user['monedas']}\n"
        f"⭐ XP: {user['xp']}\n"
        f"🏅 Rango: {obtener_rango(user['xp'])}\n\n"
        f"Usa /ayuda para ver todos los comandos disponibles."
    )

    try:
        await update.message.reply_photo(InputFile(imagen), caption=texto, parse_mode="Markdown")
    except:
        await update.message.reply_text(texto, parse_mode="Markdown")

# === COMANDO /ayuda ===
async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "📜 *Lista de comandos disponibles:*\n\n"
        "🐸 /start - Inicia tu aventura con Pepegotchi\n"
        "🍽️ /alimentar - Alimenta a tu Pepegotchi\n"
        "🎮 /jugar - Juega con tu Pepegotchi\n"
        "💤 /dormir - Envía a dormir a tu Pepegotchi (6h)\n"
        "🛒 /tienda - Muestra la tienda con ítems\n"
        "💰 /comprar <ítem> - Compra un ítem de la tienda\n"
        "🎒 /usar <ítem> - Usa un ítem de tu inventario\n"
        "🎁 /checkin - Reclama tu recompensa diaria\n"
        "🎉 /evento - Muestra los eventos y sorpresas (¡próximamente!)\n"
        "📊 /estado - Ver estadísticas de tu Pepegotchi\n"
    )
    await update.message.reply_text(texto, parse_mode="Markdown")

# === COMANDO /evento ===
async def evento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 Próximamente tendremos *eventos y sorpresas* para ti 💚\n"
        "¡Mantente atento a las novedades!",
        parse_mode="Markdown"
    )

# === COMANDO /checkin ===
async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = cargar_datos()
    user_id = str(update.effective_user.id)
    user = asegurar_usuario(datos, user_id)
    hoy = fecha_local_hoy()

    if user["ultimo_checkin"] == hoy:
        await update.message.reply_text("🎁 Ya has hecho tu *check-in* de hoy. ¡Vuelve mañana!")
        return

    user["ultimo_checkin"] = hoy
    user["xp"] += 50
    guardar_datos(datos)
    await update.message.reply_text("✅ *Check-in diario completado!* +50 XP 🎉", parse_mode="Markdown")
    await revisar_rango(update, user_id, datos)

# === COMANDO /estado ===
async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = cargar_datos()
    user_id = str(update.effective_user.id)
    user = asegurar_usuario(datos, user_id)

    imagen = imagen_por_rango(user["xp"])
    texto = (
        f"📊 *Estado de tu Pepegotchi:*\n\n"
        f"💰 Monedas: {user['monedas']}\n"
        f"⭐ XP: {user['xp']}\n"
        f"🏅 Rango: {obtener_rango(user['xp'])}\n"
        f"⚡ Energía: {user['energia']}%\n"
        f"💤 Durmiendo: {'Sí 😴' if user['is_sleeping'] else 'No 🐸'}"
    )

    try:
        await update.message.reply_photo(InputFile(imagen), caption=texto, parse_mode="Markdown")
    except:
        await update.message.reply_text(texto, parse_mode="Markdown")

# === BLOQUEO GENERAL: si está dormido, no puede usar comandos ===
async def verificar_sueño(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    if user.get("is_sleeping", False):
        sleep_until = datetime.fromisoformat(user["sleep_until"])
        ahora = datetime.now(TZ)
        if ahora < sleep_until:
            restante = sleep_until - ahora
            horas = int(restante.total_seconds() // 3600)
            minutos = int((restante.total_seconds() % 3600) // 60)
            await update.message.reply_text(
                f"🤫 Shhh... tu Pepegotchi está dormido 💤\n"
                f"⏰ Despertará en {horas}h {minutos}min."
            )
            return True
        else:
            # Se despertó
            user["is_sleeping"] = False
            user["sleep_until"] = None
            guardar_datos(cargar_datos())
            await update.message.reply_text("☀️ Tu Pepegotchi ha despertado, ¡es hora de jugar y comer! 🐸")
            return False
    return False
# - Comandos de interacción (alimentar, jugar, dormir)

# === COMANDO /alimentar ===
async def alimentar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = cargar_datos()
    user_id = str(update.effective_user.id)
    user = asegurar_usuario(datos, user_id)

    if await verificar_sueño(update, context, user):
        return

    hoy = fecha_local_hoy()
    contador = user["acciones_hoy"].get("alimentar", 0)

    if contador == 0:
        # Primera alimentación gratuita
        user["xp"] += 30
        await update.message.reply_text("🍽️ Tu Pepegotchi ha comido una deliciosa mosca 🪰 +30 XP 💚")
    elif contador < 4:
        if user["monedas"] >= 30:
            user["monedas"] -= 30
            user["xp"] += 30
            await update.message.reply_text("🍽️ Tu Pepegotchi ha comido una mosca 🪰 +30 XP (costó 30 monedas)")
        else:
            await update.message.reply_text("💰 No tienes suficientes monedas para alimentar a tu Pepegotchi.")
            return
    else:
        await update.message.reply_text("🚫 Ya alimentaste a tu Pepegotchi el máximo de 4 veces hoy.")
        return

    user["acciones_hoy"]["alimentar"] = contador + 1
    guardar_datos(datos)
    await revisar_rango(update, user_id, datos)

# === COMANDO /jugar ===
async def jugar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = cargar_datos()
    user_id = str(update.effective_user.id)
    user = asegurar_usuario(datos, user_id)

    if await verificar_sueño(update, context, user):
        return

    contador = user["acciones_hoy"].get("jugar", 0)

    if contador == 0:
        user["xp"] += 25
        await update.message.reply_text("🎮 Tu Pepegotchi jugó por primera vez hoy 🐸 +25 XP 🎉")
    elif contador < 4:
        if user["monedas"] >= 25:
            user["monedas"] -= 25
            user["xp"] += 25
            await update.message.reply_text("🎮 Tu Pepegotchi jugó alegremente 🐸 +25 XP (costó 25 monedas)")
        else:
            await update.message.reply_text("💰 No tienes suficientes monedas para jugar.")
            return
    else:
        await update.message.reply_text("🚫 Ya jugaste el máximo de 4 veces hoy.")
        return

    user["acciones_hoy"]["jugar"] = contador + 1
    guardar_datos(datos)
    await revisar_rango(update, user_id, datos)

# === COMANDO /dormir ===
async def dormir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = cargar_datos()
    user_id = str(update.effective_user.id)
    user = asegurar_usuario(datos, user_id)

    ahora = datetime.now(TZ)

    if user.get("is_sleeping", False):
        sleep_until = datetime.fromisoformat(user["sleep_until"])
        if ahora < sleep_until:
            restante = sleep_until - ahora
            horas = int(restante.total_seconds() // 3600)
            minutos = int((restante.total_seconds() % 3600) // 60)
            await update.message.reply_text(
                f"😴 Tu Pepegotchi ya está durmiendo... 💤\nDespertará en {horas}h {minutos}min."
            )
            return

    sleep_until = ahora + timedelta(hours=6)
    user["is_sleeping"] = True
    user["sleep_until"] = sleep_until.isoformat()
    user["xp"] += 50
    guardar_datos(datos)

    await update.message.reply_text("💤 Tu Pepegotchi se ha dormido bajo la luna 🌙 +50 XP\nVolverá en 6 horas 🕓")

    # Tarea en segundo plano para avisar cuando despierte
    async def despertar_mensaje():
        await asyncio.sleep(6 * 3600)
        user["is_sleeping"] = False
        user["sleep_until"] = None
        guardar_datos(datos)
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="☀️ Tu Pepegotchi ha despertado, ¡es hora de comer y jugar! 🐸"
            )
        except:
            pass

    asyncio.create_task(despertar_mensaje())
# - Recompensas, tienda y eventos

# === COMANDO /checkin ===
async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = cargar_datos()
    user_id = str(update.effective_user.id)
    user = asegurar_usuario(datos, user_id)

    hoy = fecha_local_hoy()
    ultimo = user.get("ultimo_checkin")

    if ultimo == hoy:
        await update.message.reply_text("⏰ Ya hiciste tu check-in diario. ¡Vuelve mañana! 🌞")
        return

    user["ultimo_checkin"] = hoy
    user["xp"] += 50
    user["monedas"] += 200
    guardar_datos(datos)
    await revisar_rango(update, user_id, datos)
    await update.message.reply_text("🎁 ¡Recompensa diaria reclamada! +50 XP y +200 monedas 💰")

# === COMANDO /evento ===
async def evento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 *Próximamente tendremos eventos y sorpresas para ti* 🌟",
        parse_mode="Markdown"
    )



    await update.message.reply_text(f"✅ Compraste {TIENDA_ITEMS[key]['nombre']} por {precio} monedas.")

# === COMANDO /usar ===
async def usar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❗ Usa `/usar <nombre>`. Ejemplo: `/usar mosca`")
        return

    elegido = " ".join(args).lower().replace(" ", "")
    if elegido not in TIENDA_ITEMS:
        await update.message.reply_text("❌ Ese objeto no existe.")
        return

    datos = cargar_datos()
    user_id = str(update.effective_user.id)
    user = asegurar_usuario(datos, user_id)

    inv = user["inventario"]
    if inv.get(elegido, 0) <= 0:
        await update.message.reply_text("🧺 No tienes ese objeto en tu inventario.")
        return

    item = TIENDA_ITEMS[elegido]
    inv[elegido] -= 1
    if inv[elegido] == 0:
        del inv[elegido]

    if elegido == "pocion":
        user["energia"] = 100
        await update.message.reply_text("🧪 Tu Pepegotchi recuperó toda su energía 💪")
    else:
        user["xp"] += item["xp"]
        await update.message.reply_text(f"✨ Usaste {item['nombre']} y ganaste +{item['xp']} XP")

    guardar_datos(datos)
    await revisar_rango(update, user_id, datos)

# === COMANDO /inventario ===
async def inventario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = cargar_datos()
    user_id = str(update.effective_user.id)
    user = asegurar_usuario(datos, user_id)
    inv = user.get("inventario", {})

    if not inv:
        await update.message.reply_text("🧺 Tu inventario está vacío.")
        return

    texto = "🧺 *Inventario Pepegotchi:*\n\n"
    for key, cantidad in inv.items():
        item = TIENDA_ITEMS.get(key, {"nombre": key})
        texto += f"{item['nombre']} — {cantidad}\n"

    await update.message.reply_text(texto, parse_mode="Markdown")
# - Sistema de sueño, reinicio diario y tareas automáticas

# === COMANDO /dormir ===
async def dormir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = cargar_datos()
    user_id = str(update.effective_user.id)
    user = asegurar_usuario(datos, user_id)

    if user.get("durmiendo", False):
        await update.message.reply_text("😴 Tu Pepegotchi ya está dormido.")
        return

    user["durmiendo"] = True
    user["hora_dormir"] = datetime.now(pytz.timezone("America/Guatemala")).isoformat()
    guardar_datos(datos)

    await update.message.reply_text("💤 Tu Pepegotchi se ha ido a dormir. Volverá en 6 horas. 🌙")

    # Esperar 6 horas y despertar automáticamente
    async def despertar_automatico():
        await asyncio.sleep(6 * 3600)
        datos = cargar_datos()
        user = asegurar_usuario(datos, user_id)
        user["durmiendo"] = False
        guardar_datos(datos)
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🌞 ¡He despertado! Es hora de comer y jugar 🍽️🎮"
            )
        except Exception:
            pass

    asyncio.create_task(despertar_automatico())

# === Bloquear acciones mientras duerme ===
async def verificar_sueño(update: Update):
    datos = cargar_datos()
    user_id = str(update.effective_user.id)
    user = asegurar_usuario(datos, user_id)
    if user.get("durmiendo", False):
        await update.message.reply_text("🤫 Shhhh... tu Pepegotchi está dormido 💤 volverá en 6 horas.")
        return True
    return False

# Modificar alimentar y jugar para incluir la verificación de sueño
async def alimentar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await verificar_sueño(update):
        return
    datos = cargar_datos()
    user_id = str(update.effective_user.id)
    user = asegurar_usuario(datos, user_id)
    hoy = fecha_local_hoy()

    # Verificar límite diario
    if user.get("veces_alimento", {}).get(hoy, 0) >= 4:
        await update.message.reply_text("🍽️ Ya alimentaste 4 veces hoy. Espera hasta mañana.")
        return

    # Primera vez gratis
    veces = user.get("veces_alimento", {}).get(hoy, 0)
    costo = 0 if veces == 0 else 100

    if user["monedas"] < costo:
        await update.message.reply_text("💸 No tienes suficientes monedas para alimentar.")
        return

    user["monedas"] -= costo
    user["energia"] = min(100, user["energia"] + 20)
    user["xp"] += 10
    user.setdefault("veces_alimento", {})[hoy] = veces + 1
    guardar_datos(datos)
    await revisar_rango(update, user_id, datos)

    if costo == 0:
        await update.message.reply_text("🍎 Alimentaste a tu Pepegotchi gratis por hoy 💕 (+10 XP)")
    else:
        await update.message.reply_text(f"🍔 Alimentaste a tu Pepegotchi pagando {costo} monedas 💰 (+10 XP)")

async def jugar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await verificar_sueño(update):
        return
    datos = cargar_datos()
    user_id = str(update.effective_user.id)
    user = asegurar_usuario(datos, user_id)
    hoy = fecha_local_hoy()

    # Verificar límite diario
    if user.get("veces_juego", {}).get(hoy, 0) >= 4:
        await update.message.reply_text("🎮 Ya jugaste 4 veces hoy. Espera hasta mañana.")
        return

    veces = user.get("veces_juego", {}).get(hoy, 0)
    costo = 0 if veces == 0 else 150

    if user["monedas"] < costo:
        await update.message.reply_text("💸 No tienes suficientes monedas para jugar.")
        return

    user["monedas"] -= costo
    user["xp"] += 15
    user["felicidad"] = min(100, user["felicidad"] + 15)
    user.setdefault("veces_juego", {})[hoy] = veces + 1
    guardar_datos(datos)
    await revisar_rango(update, user_id, datos)

    if costo == 0:
        await update.message.reply_text("🎲 Jugaste gratis con tu Pepegotchi por hoy 🎉 (+15 XP)")
    else:
        await update.message.reply_text(f"🎯 Jugaste pagando {costo} monedas 💰 (+15 XP)")

# === Reinicio diario a las 00:00 ===
async def reinicio_diario():
    while True:
        ahora = datetime.now(pytz.timezone("America/Guatemala"))
        siguiente = (ahora + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        espera = (siguiente - ahora).total_seconds()
        await asyncio.sleep(espera)

        datos = cargar_datos()
        for user in datos["usuarios"].values():
            user["veces_alimento"] = {}
            user["veces_juego"] = {}
        guardar_datos(datos)
        print("🔄 Reinicio diario completado.")
# - Arranque del bot

# === COMANDO /estado ===
async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await verificar_sueño(update):
        return
    datos = cargar_datos()
    user_id = str(update.effective_user.id)
    user = asegurar_usuario(datos, user_id)

    msg = (
        f"📊 **Estado de tu Pepegotchi**\n\n"
        f"🪙 Monedas: {user['monedas']}\n"
        f"⭐ Experiencia: {user['xp']}\n"
        f"🏅 Nivel: {user['nivel']}\n"
        f"😊 Felicidad: {user['felicidad']}%\n"
        f"⚡ Energía: {user['energia']}%\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

## === Inicializar bot ===
from dotenv import load_dotenv
import os

load_dotenv()

async def main():

    app = ApplicationBuilder().token(os.getenv("TOKEN")).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("tienda", tienda))
    app.add_handler(CommandHandler("checkin", checkin))
    app.add_handler(CommandHandler("evento", evento))
    app.add_handler(CommandHandler("usar", usar))
    app.add_handler(CommandHandler("alimentar", alimentar))
    app.add_handler(CommandHandler("jugar", jugar))
    app.add_handler(CommandHandler("dormir", dormir))
    app.add_handler(CommandHandler("estado", estado))

    # === NUEVA TIENDA ===
    app.add_handler(CallbackQueryHandler(comprar_callback))

    # Reinicio diario del Pepegotchi
    asyncio.create_task(reinicio_diario())

    print("🤖 Bot iniciado correctamente. Esperando comandos…")
    await app.run_polling()
# --- ===Inicio: Ejecución segura del bot ---
import nest_asyncio
import asyncio

nest_asyncio.apply()

async def main_async():
    try:
        await main()
    except Exception as e:
        print(f"⚠️ Error en ejecución principal: {e}")

if __name__ == "__main__":
    import asyncio

    async def run_bot():
        # Ejecuta tu función principal sin cerrar el loop
        await main()

    try:
        # En la mayoría de entornos funciona bien
        asyncio.run(run_bot())
    except RuntimeError as e:
        # Si ya hay un loop corriendo (como en Termux)
        if "running event loop" in str(e):
            loop = asyncio.get_event_loop()
            loop.create_task(run_bot())
            loop.run_forever()
        else:
            raise
