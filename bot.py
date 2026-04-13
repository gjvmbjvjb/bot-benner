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

# ========== إعدادات البوت ==========
TOKEN = "8730861249:AAFldFUdK-uKcp3hJtThrb6tvQdsCBmUuIY"
URL = os.environ.get("RENDER_EXTERNAL_URL", "https://maker-banner-freefire-bot.onrender.com")
PORT = int(os.getenv("PORT", 8000))

# ========== إعدادات التحويل ==========
TARGET_SIZE = (128, 128)      # الأبعاد الجديدة (عرض × ارتفاع)
BLOCK_SIZE = "8x8"            # حجم البلوك لضغط ASTC
QUALITY = "medium"            # جودة الضغط (fast, medium, best, thorough)
ASTC_ENCODER = "./astcenc-avx2"  # مسار المشفر (غير حسب نظامك)

# ========== إعدادات التسجيل ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== دوال معالجة الصور ==========
def process_image(input_path: str, output_png: str) -> bool:
    """
    معالجة الصورة: تغيير الأبعاد + قلب 180 درجة
    """
    try:
        # فتح الصورة
        img = Image.open(input_path)
        original_size = img.size
        logger.info(f"📸 الأبعاد الأصلية: {original_size}")
        
        # تغيير الأبعاد مع الحفاظ على الجودة
        img_resized = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
        logger.info(f"📏 تم تغيير الأبعاد إلى: {TARGET_SIZE}")
        
        # قلب الصورة 180 درجة
        img_flipped = img_resized.rotate(180)
        logger.info(f"🔄 تم قلب الصورة 180 درجة")
        
        # حفظ كـ PNG مؤقت
        img_flipped.save(output_png, "PNG")
        logger.info(f"💾 تم حفظ الصورة المعالجة: {output_png}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الصورة: {e}")
        return False

def convert_to_astc(png_path: str, astc_path: str) -> bool:
    """
    تحويل PNG إلى ASTC باستخدام astcenc
    """
    try:
        # التحقق من وجود المشفر
        if not os.path.exists(ASTC_ENCODER):
            logger.error(f"❌ المشفر غير موجود: {ASTC_ENCODER}")
            return False
        
        # أمر التحويل
        cmd = f"{ASTC_ENCODER} -cs {png_path} {astc_path} {BLOCK_SIZE} -{QUALITY}"
        logger.info(f"🔧 تنفيذ الأمر: {cmd}")
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(astc_path):
            file_size = os.path.getsize(astc_path)
            logger.info(f"✅ تم التحويل بنجاح! حجم الملف: {file_size} بايت")
            return True
        else:
            logger.error(f"❌ فشل التحويل: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ خطأ في التحويل: {e}")
        return False

# ========== أوامر البوت ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    await update.message.reply_text(
        "🎮 *بوت تحويل الصور إلى بنرات ASTC* 🎮\n\n"
        "✨ *الميزات:*\n"
        f"• تغيير الأبعاد إلى {TARGET_SIZE[0]}×{TARGET_SIZE[1]} بيكسل\n"
        "• قلب الصورة 180 درجة\n"
        "• تحويل إلى صيغة ASTC (جودة عالية)\n\n"
        "📤 *كيفية الاستخدام:*\n"
        "• أرسل أي صورة (PNG, JPG, JPEG)\n"
        "• سأقوم بمعالجتها وتحويلها تلقائياً\n\n"
        "🇲🇦 *مطور مغربي*",
        parse_mode="Markdown"
    )

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الصور المرسلة"""
    user = update.effective_user
    user_id = user.id
    
    # إرسال رسالة انتظار
    status_msg = await update.message.reply_text("🔄 *جاري معالجة الصورة...*\n\n📏 تغيير الأبعاد...", parse_mode="Markdown")
    
    try:
        # تحميل الصورة
        if update.message.photo:
            photo = await update.message.photo[-1].get_file()
        elif update.message.document:
            photo = await update.message.document.get_file()
        else:
            await status_msg.edit_text("❌ يرجى إرسال صورة صالحة")
            return
        
        input_path = f"temp_input_{user_id}.jpg"
        temp_png = f"temp_processed_{user_id}.png"
        output_path = f"output_{user_id}.astc"
        
        # تحميل الملف
        await photo.download_to_drive(input_path)
        await status_msg.edit_text("🔄 *جاري معالجة الصورة...*\n\n✅ تم التحميل\n📏 تغيير الأبعاد...", parse_mode="Markdown")
        
        # معالجة الصورة (تغيير الأبعاد + قلب)
        if not process_image(input_path, temp_png):
            await status_msg.edit_text("❌ فشل في معالجة الصورة! تأكد من أن الملف صورة سليمة.")
            return
        
        await status_msg.edit_text("🔄 *جاري معالجة الصورة...*\n\n✅ تم التحميل\n✅ تم تغيير الأبعاد\n🔧 جاري التحويل إلى ASTC...", parse_mode="Markdown")
        
        # تحويل إلى ASTC
        if not convert_to_astc(temp_png, output_path):
            await status_msg.edit_text("❌ فشل التحويل! تأكد من وجود المشفر (astcenc).")
            return
        
        # إرسال الملف النهائي
        await status_msg.edit_text("✅ *تم التحويل بنجاح!*\n📤 جاري الإرسال...", parse_mode="Markdown")
        
        with open(output_path, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=f"banner_{user_id}.astc",
                caption=f"✅ *تم التحويل بنجاح!*\n\n"
                       f"📏 الأبعاد الجديدة: {TARGET_SIZE[0]}×{TARGET_SIZE[1]}\n"
                       f"🔄 تم قلب الصورة 180 درجة\n"
                       f"🎮 صيغة ASTC جاهزة للاستخدام",
                parse_mode="Markdown"
            )
        
        # حذف رسالة الحالة
        await status_msg.delete()
        
        # تنظيف الملفات المؤقتة
        for f in [input_path, temp_png, output_path]:
            if os.path.exists(f):
                os.remove(f)
                logger.info(f"🗑️ تم حذف الملف: {f}")
                
    except Exception as e:
        logger.error(f"❌ خطأ عام: {e}")
        await update.message.reply_text("❌ حدث خطأ غير متوقع. حاول مرة أخرى لاحقاً.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الملفات (فقط الصور)"""
    doc = update.message.document
    if doc.mime_type and doc.mime_type.startswith('image/'):
        await handle_image(update, context)
    else:
        await update.message.reply_text("❌ يرجى إرسال صورة فقط (PNG, JPG, JPEG)")

# ========== إعداد السيرفر ==========
async def main():
    # إعداد تطبيق تيليجرام
    app = Application.builder().token(TOKEN).updater(None).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    
    # إعداد Webhook
    webhook_url = f"{URL}/telegram"
    await app.bot.set_webhook(url=webhook_url)
    logger.info(f"🌐 تم تعيين Webhook: {webhook_url}")
    
    # دوال الـ Webhook
    async def telegram_webhook(request: Request) -> Response:
        try:
            data = await request.json()
            await app.update_queue.put(Update.de_json(data, app.bot))
            return Response()
        except Exception as e:
            logger.error(f"❌ خطأ في webhook: {e}")
            return Response(status_code=500)
    
    async def health_check(request: Request) -> PlainTextResponse:
        return PlainTextResponse("✅ Bot is running!")
    
    # إعداد خادم Starlette
    starlette_app = Starlette(routes=[
        Route("/telegram", telegram_webhook, methods=["POST"]),
        Route("/health", health_check, methods=["GET"]),
        Route("/", health_check, methods=["GET"]),
    ])
    
    # تشغيل الخادم
    import uvicorn
    config = uvicorn.Config(starlette_app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    
    async with app:
        await app.start()
        logger.info(f"🚀 البوت يعمل على المنفذ {PORT}")
        await server.serve()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())