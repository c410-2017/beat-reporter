import os
import logging
import asyncio
import nest_asyncio
nest_asyncio.apply()
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)
TOKEN = os.getenv("TOKEN")
ID_DO_GRUPO = int(os.getenv("ID_DO_GRUPO"))

# Tópicos disponíveis (nome: thread_id)
TOPICOS = {
    "Fla retrô": 1041,
    "Brasileirão": 3922,
    "Libertadores": 3781,
    "Fala Nação": 1,
    "Copa do Brasil": 4273,
    "Mundial de Clubes": 4450,
    "Enquetes": 1124
}

mensagens_em_espera = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
def somente_usuario_autorizado(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if str(user_id)!= os.getenv("USER_ID"):
            await update.message.reply_text("Acesso negado.")
            return
        return await func(update, context)
    return wrapper

@somente_usuario_autorizado
async def handle_photo(update, context):
    msg = update.message
    user_id = msg.from_user.id
    file_id = msg.photo[-1].file_id
    timestamp = msg.date

    mensagens_em_espera.setdefault(user_id, []).append({
        "tipo": "foto",
        "file_id": file_id,
        "legenda": None,
        "timestamp": timestamp
    })

@somente_usuario_autorizado
async def handle_video(update, context):
    msg = update.message
    user_id = msg.from_user.id
    file_id = msg.video.file_id
    timestamp = msg.date

    mensagens_em_espera.setdefault(user_id, []).append({
        "tipo": "video",
        "file_id": file_id,
        "legenda": None,
        "timestamp": timestamp
    })

@somente_usuario_autorizado
async def handle_text(update, context):
    msg = update.message
    user_id = msg.from_user.id
    texto = msg.text.replace("tweet", "")
    timestamp = msg.date

    if user_id in mensagens_em_espera and mensagens_em_espera[user_id]:
        ultima = mensagens_em_espera[user_id][-1]
        if ultima["legenda"] is None and (timestamp - ultima["timestamp"]).seconds < 20:
            ultima["legenda"] = texto
            return

    mensagens_em_espera.setdefault(user_id, []).append({
        "tipo": "texto",
        "texto": texto,
        "timestamp": timestamp
    })
@somente_usuario_autorizado
async def comando_postar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msgs = mensagens_em_espera.get(user_id, [])
    if not msgs:
        await update.message.reply_text("Nenhuma mensagem armazenada pra postar.")
        return

    keyboard = [
        [InlineKeyboardButton(nome, callback_data=str(tid))]
        for nome, tid in TOPICOS.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Você tem {len(msgs)} mensagens prontas. Escolha o tópico para postar:",
        reply_markup=reply_markup
    )

@somente_usuario_autorizado
async def tratar_escolha_topico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    thread_id = int(query.data)
    user_id = query.from_user.id

    mensagens = mensagens_em_espera.get(user_id, [])
    if not mensagens:
        await query.edit_message_text("Nenhuma mensagem pra enviar.")
        return

    for msg in mensagens:
        if msg["tipo"] == "foto":
            await context.bot.send_photo(
                chat_id=ID_DO_GRUPO,
                photo=msg["file_id"],
                caption=msg.get("legenda"),
                message_thread_id=thread_id
            )
        elif msg["tipo"] == "video":
            await context.bot.send_video(
                chat_id=ID_DO_GRUPO,
                video=msg["file_id"],
                caption=msg.get("legenda"),
                message_thread_id=thread_id
            )
        elif msg["tipo"] == "texto":
            await context.bot.send_message(
                chat_id=ID_DO_GRUPO,
                text=msg["texto"],
                message_thread_id=thread_id
            )

    mensagens_em_espera[user_id] = []
    await query.edit_message_text("Mensagens enviadas com sucesso! ✅")
import traceback

async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling an update:", exc_info=context.error)
    tb = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
    print(f"Erro capturado:\n{tb}")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.VIDEO, handle_video))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(CommandHandler("postar", comando_postar))
app.add_handler(CallbackQueryHandler(tratar_escolha_topico))
app.add_error_handler(error_handler)

async def main():
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.initialize()
    await app.start()
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.get_event_loop().run_until_complete(main())
