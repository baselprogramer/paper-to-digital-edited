"""
lexicon_models.py
=================
جدول القاموس المعتمد + بذرة أولية + دوال القراءة والكتابة.

القاموس عام لكل المشروع (اسم حقيقي هو حقيقي في كل قسم).
"""

import datetime
from sqlalchemy import (Column, Integer, String, Boolean, DateTime,
                        Enum, UniqueConstraint, func)

from models import Base, SessionLocal, _engine
from arabic_kb.lexicon import normalize_for_match, scan_text


# =============================================================================
# الجدول
# =============================================================================

class LexiconEntry(Base):
    """مصطلح معتمد: اسم شخص، منطقة عقارية، أو مصطلح مجال."""
    __tablename__ = "lexicon_entries"
    __table_args__ = (
        UniqueConstraint("term_norm", "term_type", name="uq_lex_term_type"),
    )

    id        = Column(Integer, primary_key=True)
    term      = Column(String(120), nullable=False)      # الشكل المعروض
    term_norm = Column(String(120), nullable=False, index=True)  # المطبَّع للمطابقة
    term_type = Column(
        Enum("person", "region", "domain", name="lex_type_enum"),
        default="person", index=True
    )
    source = Column(
        Enum("seed", "verified", "imported", name="lex_source_enum"),
        default="verified"
    )
    occurrence_count = Column(Integer, default=1)
    is_active        = Column(Boolean, default=True)
    created_at       = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.datetime.utcnow,
                              onupdate=datetime.datetime.utcnow)


# =============================================================================
# بذرة أولية — وسّعها من وثائقك ومن قوائم GitHub
# =============================================================================

SEED_REGIONS = [
    # محافظات
    "دمشق", "ريف دمشق", "حلب", "حمص", "حماة", "اللاذقية", "طرطوس",
    "إدلب", "درعا", "السويداء", "القنيطرة", "دير الزور", "الرقة",
    "الحسكة",
    # ريف دمشق — مناطق عقارية شائعة
    "زاكية", "قدسيا", "الهامة", "دمر", "جديدة عرطوز", "عرطوز",
    "صحنايا", "أشرفية صحنايا", "جرمانا", "سيدي مقداد", "المليحة",
    "دوما", "حرستا", "عربين", "زملكا", "كفربطنا", "سقبا",
    "التل", "منين", "صيدنايا", "معضمية الشام", "داريا",
    "الكسوة", "الديماس", "قطنا", "خان الشيح", "الزبداني",
    "بلودان", "مضايا", "سرغايا", "يبرود", "النبك", "دير عطية",
    "قارة", "جيرود", "الرحيبة", "عدرا", "الضمير",
    # دمشق — أحياء
    "المزة", "كفرسوسة", "المالكي", "أبو رمانة", "الشعلان",
    "الميدان", "القدم", "برزة", "ركن الدين", "المهاجرين",
    "باب توما", "القصاع", "الصالحية", "دمر البلد", "التضامن",
    "جوبر", "القابون", "حرستا القنطرة",
    # حلب
    "الفرقان", "السريان", "الشهباء", "حلب الجديدة", "الأشرفية",
    "صلاح الدين", "السكري", "الشعار", "باب النيرب", "الميدان حلب",
    "عزيزية", "الجميلية", "سيف الدولة",
]

SEED_PERSON_NAMES = [
    # أسماء ذكور شائعة
    "محمد", "أحمد", "علي", "عمر", "خالد", "حسن", "حسين", "عبد الله",
    "عبد الرحمن", "عبد الكريم", "عبد المجيد", "عبد الحميد", "عبد القادر",
    "إبراهيم", "إسماعيل", "يوسف", "يعقوب", "داود", "سليمان", "موسى",
    "عيسى", "زكريا", "يحيى", "مصطفى", "مرتضى", "هاشم", "طلال",
    "باسل", "بشار", "ماهر", "سامر", "ياسر", "وسيم", "نبيل", "كمال",
    "جمال", "فيصل", "نادر", "زياد", "كريم", "سعيد", "وليد", "رامي",
    "طارق", "هيثم", "غسان", "ربيع", "عدنان", "صلاح", "هادي", "كامل",
    "إحسان", "أسبر", "نذير", "هشام", "معن", "راغب", "مروان", "سلوم",
    "شادي", "فادي", "رافع", "أنس", "أيمن", "أمجد", "بسام", "تامر",
    "ثائر", "جهاد", "حازم", "حاتم", "رائد", "رياض", "سامي", "شريف",
    "صابر", "ضياء", "عادل", "عامر", "عصام", "علاء", "عماد", "فراس",
    "فؤاد", "قاسم", "لؤي", "مأمون", "مازن", "محسن", "مروة", "منذر",
    "مهند", "ناصر", "نزار", "نور الدين", "وائل", "يامن", "أيهم",
    # أسماء إناث شائعة
    "فاطمة", "مريم", "زينب", "عائشة", "خديجة", "نور", "هند", "سارة",
    "لينا", "رنا", "ميساء", "دانا", "نهاد", "تكريم", "غنان", "إيمان",
    "هدى", "سعاد", "أمل", "رجاء", "وفاء", "منى", "ليلى", "سلمى",
    "رغد", "لمى", "ريم", "دارين", "علا", "هبة", "نسرين", "ياسمين",
    "غادة", "سميرة", "نادية", "بشرى", "صفاء", "شذى", "رباب", "لبنى",
    # أسماء عائلات شامية
    "قاطرجي", "الشهابي", "عاصي", "طعمة", "الحلبي", "الدمشقي",
    "الحمصي", "الحموي", "الزعبي", "العمر", "البرازي", "الأتاسي",
    "الكيلاني", "الجابري", "القدسي", "الشامي", "الخطيب", "الرفاعي",
    "السباعي", "العظمة", "المارديني", "النابلسي", "الحكيم",
    "قطان", "شربجي", "خربوطلي", "عرنوس", "دعبول", "جزماتي",
    "صباغ", "حلاق", "نجار", "حداد", "خياط", "عطار", "دباغ",
    "بيطار", "طباع", "قباني", "شيخ", "مفتي", "عبيد", "درويش",
]


# =============================================================================
# التهيئة
# =============================================================================

def init_lexicon():
    """ينشئ الجدول ويزرع البيانات الأولية — آمن للتكرار."""
    Base.metadata.create_all(_engine)
    db = SessionLocal()
    try:
        if db.query(LexiconEntry).count() > 0:
            db.close()
            return

        rows = []
        seen = set()
        for term in SEED_REGIONS:
            n = normalize_for_match(term)
            if (n, "region") in seen:
                continue
            seen.add((n, "region"))
            rows.append(LexiconEntry(term=term, term_norm=n,
                                     term_type="region", source="seed",
                                     occurrence_count=1))
        for term in SEED_PERSON_NAMES:
            n = normalize_for_match(term)
            if (n, "person") in seen:
                continue
            seen.add((n, "person"))
            rows.append(LexiconEntry(term=term, term_norm=n,
                                     term_type="person", source="seed",
                                     occurrence_count=1))

        db.add_all(rows)
        db.commit()
        print(f"✓ Lexicon: زُرع {len(rows)} مصطلح "
              f"({len(SEED_REGIONS)} منطقة + {len(SEED_PERSON_NAMES)} اسم)")
    except Exception as e:
        db.rollback()
        print(f"✗ Lexicon خطأ: {e}")
        raise
    finally:
        db.close()


# =============================================================================
# القراءة
# =============================================================================

_CACHE = {"regions": None, "persons": None, "stamp": None}


def get_entries(term_type: str) -> list:
    """يجلب مصطلحات نوع معيّن كقائمة dict جاهزة للمطابقة."""
    db = SessionLocal()
    try:
        rows = (db.query(LexiconEntry)
                .filter_by(term_type=term_type, is_active=True)
                .all())
        return [{"term": r.term, "occurrence_count": r.occurrence_count}
                for r in rows]
    finally:
        db.close()


def scan_page_text(text: str) -> dict:
    """الفحص المحلي الكامل لنص صفحة — صفر كلفة API."""
    return scan_text(text,
                     region_entries=get_entries("region"),
                     person_entries=get_entries("person"))


# =============================================================================
# الكتابة — كل تصحيح معتمد يدخل القاموس
# =============================================================================

def add_term(term: str, term_type: str = "person",
             source: str = "verified") -> bool:
    """
    يضيف مصطلحاً أو يزيد عدّاده إن كان موجوداً.
    يُستدعى عند: ضغط زر اقتراح، أو تعديل يدوي، أو اعتماد صفحة.
    """
    term = (term or "").strip()
    if not term or len(term) < 3 or len(term) > 120:
        return False
    n = normalize_for_match(term)
    if not n:
        return False

    db = SessionLocal()
    try:
        row = (db.query(LexiconEntry)
               .filter_by(term_norm=n, term_type=term_type).first())
        if row:
            row.occurrence_count += 1
            if not row.is_active:
                row.is_active = True
        else:
            db.add(LexiconEntry(term=term, term_norm=n, term_type=term_type,
                                source=source, occurrence_count=1))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"add_term خطأ: {e}")
        return False
    finally:
        db.close()


def add_terms_from_text(text: str, limit: int = 40) -> int:
    """
    يستخرج الأسماء والمناطق من نص معتمد بشرياً ويضيفها للقاموس.
    يُستدعى عند اعتماد الصفحة (approve) — هنا يتراكم الذهب الحقيقي.
    """
    from arabic_kb.lexicon import extract_candidate_terms
    added = 0
    for c in extract_candidate_terms(text)[:limit]:
        if add_term(c["word"], c["kind"], source="verified"):
            added += 1
    return added


def deactivate_term(term: str, term_type: str = "person") -> bool:
    """يعطّل مصطلحاً خاطئاً دخل القاموس بالغلط."""
    n = normalize_for_match(term)
    db = SessionLocal()
    try:
        row = (db.query(LexiconEntry)
               .filter_by(term_norm=n, term_type=term_type).first())
        if row:
            row.is_active = False
            db.commit()
            return True
        return False
    finally:
        db.close()


def lexicon_stats() -> dict:
    """إحصاءات للعرض في الواجهة."""
    db = SessionLocal()
    try:
        q = (db.query(LexiconEntry.term_type, LexiconEntry.source,
                      func.count(LexiconEntry.id))
             .filter(LexiconEntry.is_active == True)
             .group_by(LexiconEntry.term_type, LexiconEntry.source).all())
        out = {}
        for ttype, src, cnt in q:
            out.setdefault(ttype, {})[src] = cnt
        return out
    finally:
        db.close()