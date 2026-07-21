"""الإعدادات — كلها عبر متغيّرات البيئة (.env)."""
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOADS = os.path.join(BASE, "uploads")
STORAGE = os.path.join(BASE, "storage")
TEMPLATES_DIR = os.path.join(STORAGE, "section_templates")  # قوالب الأقسام
OUTPUTS_DIR = os.path.join(STORAGE, "outputs")              # ملفات الإكسل الناتجة

SECRET_KEY = os.environ.get("SECRET_KEY", "dev")

# حساب الدخول الافتراضي (غيّره في .env أول تشغيل!)
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# بناء رابط قاعدة البيانات من متغيّرات منفصلة (XAMPP / MySQL)
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "3307")
DB_NAME = os.environ.get("DB_NAME", "mirsad")

_pw = f":{quote_plus(DB_PASSWORD)}" if DB_PASSWORD else ""
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"mysql+pymysql://{DB_USER}{_pw}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
)

# الوضع التجريبي: 1 = بلا مفاتيح API (لاختبار كل شيء قبل الشراء)
MOCK = os.environ.get("MOCK", "1") == "1"

# محرك الاستخراج (العين): gemini أو openrouter (نماذج مجانية مثل Gemma)
EXTRACT_PROVIDER = os.environ.get("EXTRACT_PROVIDER", "gemini").lower()
EXTRACT_MODEL = os.environ.get("EXTRACT_MODEL", "gemini-flash-latest")

# محرك الهيكلة (العقل): gemini أو claude أو openrouter
# التبديل لاحقاً = تغيير هذا السطر في .env فقط
STRUCTURE_ENGINE = os.environ.get("STRUCTURE_ENGINE", "gemini").lower()
STRUCTURE_MODEL = os.environ.get("STRUCTURE_MODEL", "claude-opus-4-8")

# تحقّق مزدوج: استخراجان مستقلان يقارنهما المدقّق (دقة أعلى، كلفة أعلى)
DUAL_EXTRACT = os.environ.get("DUAL_EXTRACT", "0") == "1"

CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.7"))

# الصورة المرسلة للنماذج: original (أفضل للخط اليدوي) أو cleaned
MODEL_IMAGE = os.environ.get("MODEL_IMAGE", "original").lower()

MAX_UPLOAD_MB = 60
