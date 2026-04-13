import os
import subprocess
import asyncio
from PIL import Image
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8730861249:AAFldFUdK-uKcp3hJtThrb6tvQdsCBmUuIY"
URL = os.environ.get("RENDER_EXTERNAL_URL", "https://maker-banner-freefire-bot.onrender.com")
PORT = int(os.getenv("PORT", 8000))

TARGET_SIZE = (128, 128)
BLOCK_SIZE = "8x8"
QUALITY = "medium"
ASTC_ENCODER = "./astcenc-avx2"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 بوت تحويل صور الى بنرات\n\n"
        "قم بارسال اي صوره و سوف احولها\n"
        "مطور مغربي 🇲🇦"
    )

def process_image(input_path: str, output_png: str) -> bool:
    try:
        img = Image.open(input_path)
        img_resized = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
        img_flipped = img_resized.rotate(180)
        img_flipped.save(output_png, "PNG")
        return True
    except:
        return False

def convert_to_astc(png_path: str, astc_path: str) -> bool:
    try:
        cmd = f"{ASTC_ENCODER} -cs {png_path} {astc_path} {BLOCK_SIZE} -{QUALITY}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.returncode == 0 and os.path.exists(astc_path)
    except:
        return False

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    await update.message.reply_text("🔄 جار التحويل...")
    
    try:
        if update.message.photo:
            photo = await update.message.photo[-1].get_file()
        elif update.message.document:
            photo = await update.message.document.get_file()
        else:
            await update.message.reply_text("❌ يرجى ارسال صورة")
            return
        
        input_path = f"input_{user_id}.jpg"
        temp_png = f"temp_{user_id}.png"
        output_path = f"output_{user_id}.astc"
        
        await photo.download_to_drive(input_path)
        
        if not process_image(input_path, temp_png):
            await update.message.reply_text("❌ فشل التحويل")
            return
        
        if not convert_to_astc(temp_png, output_path):
            await update.message.reply_text("❌ فشل التحويل")
            return
        
        with open(output_path, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename="_rgb",
                caption="✅ تم تحويل بنجاح"
            )
        
        for f in [input_path, temp_png, output_path]:
            if os.path.exists(f):
                os.remove(f)
                
    except:
        await update.message.reply_text("❌ حدث خطأ")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type and doc.mime_type.startswith('image/'):
        await handle_image(update, context)
    else:
        await update.message.reply_text("❌ يرجى ارسال صورة فقط")

async def main():
    app = Application.builder().token(TOKEN).updater(None).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    
    webhook_url = f"{URL}/telegram"
    await app.bot.set_webhook(url=webhook_url)
    
    async def telegram_webhook(request: Request) -> Response:
        try:
            data = await request.json()
            await app.update_queue.put(Update.de_json(data, app.bot))
            return Response()
        except:
            return Response(status_code=500)
    
    async def health_check(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")
    
    starlette_app = Starlette(routes=[
        Route("/telegram", telegram_webhook, methods=["POST"]),
        Route("/healthcheck", health_check, methods=["GET"]),
        Route("/", health_check, methods=["GET"]),
    ])
    
    import uvicorn
    config = uvicorn.Config(starlette_app, host="0.0.0.0", port=PORT, log_level="error")
    server = uvicorn.Server(config)
    
    async with app:
        await app.start()
        await server.serve()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())