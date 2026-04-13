import os
import subprocess
import asyncio
import logging
from PIL import Image
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8730861249:AAFldFUdK-uKcp3hJtThrb6tvQdsCBmUuIY"  # توكن البوت الخاص بك
URL = os.environ.get("RENDER_EXTERNAL_URL", "https://maker-banner-freefire-bot.onrender.com")
PORT = int(os.getenv("PORT", 8000))

TARGET_SIZE = (128, 128)
BLOCK_SIZE = "8x8"
QUALITY = "medium"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "بوت تحويل صور الى بنرات فري فاير 🎮\n\n"
        "قم بارسال اي صوره و سوف أحوالها الى بانر✔️\n"
        "مطور مغربي🇲🇦",
        parse_mode="Markdown"
    )

async def convert_image(input_path: str, output_path: str) -> bool:
    try:
        img = Image.open(input_path)
        img_resized = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
        temp_png = "temp_converted.png"
        img_resized.save(temp_png)
        
        cmd = f"./astcenc-avx2 -cs {temp_png} {output_path} {BLOCK_SIZE} -{QUALITY}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if os.path.exists(temp_png):
            os.remove(temp_png)
        
        return result.returncode == 0 and os.path.exists(output_path)
    except Exception as e:
        logger.error(f"خطأ: {e}")
        return False

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text("🔄 جاري تحويل الصورة...")
    
    try:
        photo = await update.message.photo[-1].get_file()
        input_path = f"input_{user.id}.jpg"
        await photo.download_to_drive(input_path)
        
        output_path = f"output_{user.id}.astc"
        success = await convert_image(input_path, output_path)
        
        if success:
            with open(output_path, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename="_rgb",
                    caption=f"✅ تم التحويل"
                )
        else:
            await update.message.reply_text("❌ فشل التحويل!")
        
        for f in [input_path, output_path]:
            if os.path.exists(f):
                os.remove(f)
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await update.message.reply_text("❌ حدث خطأ، حاول مرة أخرى.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type and doc.mime_type.startswith('image/'):
        await handle_photo(update, context)
    else:
        await update.message.reply_text("❌ يرجى إرسال صورة")

async def main():
    app = Application.builder().token(TOKEN).updater(None).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    
    webhook_url = f"{URL}/telegram"
    await app.bot.set_webhook(url=webhook_url)
    logger.info(f"تم تعيين Webhook: {webhook_url}")
    
    async def telegram_webhook(request: Request) -> Response:
        try:
            data = await request.json()
            await app.update_queue.put(Update.de_json(data, app.bot))
            return Response()
        except Exception as e:
            logger.error(f"خطأ: {e}")
            return Response(status_code=500)
    
    async def health_check(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")
    
    starlette_app = Starlette(routes=[
        Route("/telegram", telegram_webhook, methods=["POST"]),
        Route("/healthcheck", health_check, methods=["GET"]),
        Route("/", health_check, methods=["GET"]),
    ])
    
    import uvicorn
    config = uvicorn.Config(starlette_app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    
    async with app:
        await app.start()
        await server.serve()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())