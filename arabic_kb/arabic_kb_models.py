"""
arabic_kb_models.py
====================
جداول قاعدة البيانات لـ Arabic Knowledge Base.
تُضاف تلقائياً عند أول تشغيل عبر init_arabic_kb().
لا تحتاج migrations — تعمل مع نفس engine الموجود في models.py.
"""

import datetime
from sqlalchemy import (Column, Integer, String, Text, Float,
                        Boolean, DateTime, ForeignKey, Enum)
from sqlalchemy.orm import relationship

from models import Base, SessionLocal, _engine
import arabic_kb.arabic_patterns as AP


# =============================================================================
# جدول ١: أنماط الأحرف العربية — ثابتة + تنمو
# =============================================================================

class ArabicCharPattern(Base):
    __tablename__ = "arabic_char_patterns"

    id             = Column(Integer, primary_key=True)
    char_original  = Column(String(10),  nullable=False, index=True)
    char_name      = Column(String(100))
    char_type      = Column(
        Enum("digit", "letter", "compound", name="char_type_enum"),
        default="letter"
    )
    form_id        = Column(String(100), nullable=False)
    position       = Column(
        Enum("isolated", "initial", "medial", "final", "any", name="position_enum"),
        default="any"
    )
    description_ar        = Column(Text, nullable=False)
    description_en        = Column(Text)
    ocr_risk              = Column(
        Enum("CRITICAL", "HIGH", "MEDIUM", "LOW", name="risk_enum"),
        default="MEDIUM"
    )
    confusable_with       = Column(String(500))
    disambiguation_clue   = Column(Text)
    example_words         = Column(Text)
    is_shami_variant      = Column(Boolean, default=False)
    occurrence_count      = Column(Integer, default=0)
    is_active             = Column(Boolean, default=True)
    created_at            = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at            = Column(DateTime, default=datetime.datetime.utcnow,
                                   onupdate=datetime.datetime.utcnow)

    def to_prompt_line(self) -> str:
        icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(
            self.ocr_risk, "•")
        line = f"{icon} [{self.char_name}] {self.form_id}: {self.description_ar}"
        if self.disambiguation_clue:
            line += f" → {self.disambiguation_clue}"
        if self.confusable_with:
            line += f" (يُخلط مع: {self.confusable_with})"
        return line


# =============================================================================
# جدول ٢: سجل التصحيحات التفصيلي
# =============================================================================

class OCRCorrectionLog(Base):
    __tablename__ = "ocr_correction_log"

    id               = Column(Integer, primary_key=True)
    section_id       = Column(Integer, ForeignKey("sections.id"), nullable=True, index=True)
    page_id          = Column(Integer, ForeignKey("pages.id"),    nullable=True)
    correction_type  = Column(
        Enum("digit", "letter", "word", "date", "name",
             "national_id", "amount", "property_number", "other",
             name="correction_type_enum"),
        default="other"
    )
    ocr_reading      = Column(Text, nullable=False)
    claude_reading   = Column(Text, nullable=True)
    human_correction = Column(Text, nullable=False)
    claude_agreed    = Column(Boolean, nullable=True)
    context_before   = Column(String(200))
    context_after    = Column(String(200))
    field_label      = Column(String(255))
    pattern_detected = Column(String(100), nullable=True)
    occurrence_count = Column(Integer, default=1)
    confidence       = Column(Float, default=1.0)
    created_at       = Column(DateTime, default=datetime.datetime.utcnow)

    section = relationship("Section")
    page    = relationship("Page")


# =============================================================================
# تهيئة الجداول وحقن البيانات الأولية
# =============================================================================

def init_arabic_kb():
    """
    يُنشئ الجداول ويحقن بيانات arabic_patterns.py.
    يُشغَّل تلقائياً عند بدء التطبيق — آمن للتكرار (يتحقق قبل الإضافة).
    """
    Base.metadata.create_all(_engine)
    db = SessionLocal()
    try:
        if db.query(ArabicCharPattern).count() > 0:
            db.close()
            return

        to_add = []

        # ---- الأرقام ----
        for char, data in AP.DIGITS.items():
            for form in data.get("visual_forms", []):
                risk = form.get("ocr_risk", "LOW")
                if risk not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                    risk = risk.upper()
                to_add.append(ArabicCharPattern(
                    char_original=char,
                    char_name=f"الرقم {data['correct_value']}",
                    char_type="digit",
                    form_id=form["id"],
                    position="any",
                    description_ar=form["description_ar"],
                    description_en=form.get("description_en", ""),
                    ocr_risk=risk,
                    confusable_with=",".join(str(c) for c in form.get("confusable_with", [])),
                    disambiguation_clue=form.get("disambiguation_clue", ""),
                    is_shami_variant="shami" in form["id"],
                    is_active=True,
                ))

        # ---- الأحرف ----
        for char_key, char_data in AP.LETTERS.items():
            char_name = char_data.get("name", char_key)
            if "positions" in char_data:
                for pos_name, pos_data in char_data["positions"].items():
                    if not isinstance(pos_data, dict):
                        continue
                    risk = pos_data.get("ocr_risk", "MEDIUM")
                    if risk not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                        risk = "MEDIUM"
                    to_add.append(ArabicCharPattern(
                        char_original=char_key,
                        char_name=char_name,
                        char_type="letter",
                        form_id=f"{char_key}_{pos_name}",
                        position=pos_name if pos_name in (
                            "isolated", "initial", "medial", "final") else "any",
                        description_ar=pos_data.get("description_ar", ""),
                        ocr_risk=risk,
                        confusable_with=",".join(
                            str(c) for c in pos_data.get("confusable_with", [])),
                        disambiguation_clue=pos_data.get("disambiguation_clue", ""),
                        example_words=",".join(pos_data.get("example_words", [])),
                        is_shami_variant="shami" in pos_name,
                        is_active=True,
                    ))
            else:
                desc = char_data.get("description_ar",
                       char_data.get("shared_body_description",
                       char_data.get("shared_body", "")))
                risk = char_data.get("ocr_risk", "MEDIUM")
                if not isinstance(risk, str) or risk not in ("CRITICAL","HIGH","MEDIUM","LOW"):
                    risk = "MEDIUM"
                to_add.append(ArabicCharPattern(
                    char_original=char_key,
                    char_name=char_name,
                    char_type="letter",
                    form_id=f"{char_key}_general",
                    position="any",
                    description_ar=desc,
                    ocr_risk=risk,
                    is_active=True,
                ))

        db.add_all(to_add)
        db.commit()
        print(f"✓ Arabic KB: أُضيف {len(to_add)} نمط لقاعدة المعرفة")
    except Exception as e:
        db.rollback()
        print(f"✗ Arabic KB خطأ: {e}")
        raise
    finally:
        db.close()


# =============================================================================
# دوال الاستخدام
# =============================================================================

def log_correction(
    section_id: int,
    page_id,
    ocr_reading: str,
    human_correction: str,
    correction_type: str = "other",
    context_before: str = "",
    context_after: str  = "",
    field_label: str    = "",
    claude_reading: str = None,
    claude_agreed: bool = None,
):
    """يسجل تصحيحاً بشرياً مع كامل السياق. يُستدعى من app.py."""
    if not ocr_reading or not human_correction or ocr_reading == human_correction:
        return
    db = SessionLocal()
    try:
        existing = db.query(OCRCorrectionLog).filter_by(
            section_id=section_id,
            ocr_reading=ocr_reading,
            human_correction=human_correction,
            correction_type=correction_type,
        ).first()
        if existing:
            existing.occurrence_count += 1
        else:
            db.add(OCRCorrectionLog(
                section_id=section_id,
                page_id=page_id,
                correction_type=correction_type,
                ocr_reading=ocr_reading,
                claude_reading=claude_reading,
                human_correction=human_correction,
                claude_agreed=claude_agreed,
                context_before=(context_before or "")[-200:],
                context_after=(context_after or "")[:200],
                field_label=field_label,
                confidence=1.0,
            ))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"log_correction خطأ: {e}")
    finally:
        db.close()


def build_smart_hints(section_id: int, max_items: int = 15) -> str:
    """
    يبني نص hints يجمع:
    ١. المعرفة الثابتة بالخط الشامي (arabic_patterns)
    ٢. التصحيحات البشرية السابقة للقسم مرتبةً بالأهمية
    """
    from models import Correction
    lines = [AP.build_ocr_hints_prompt()]

    db = SessionLocal()
    try:
        # تصحيحات corrections القديمة
        old_rows = (db.query(Correction)
                    .filter_by(section_id=section_id)
                    .order_by(Correction.count.desc())
                    .limit(max_items).all())

        # سجل التصحيحات التفصيلي الجديد
        new_rows = (db.query(OCRCorrectionLog)
                    .filter_by(section_id=section_id)
                    .order_by(OCRCorrectionLog.occurrence_count.desc())
                    .limit(max_items).all())

        if old_rows or new_rows:
            lines.append("\n【تصحيحات بشرية موثوقة لهذا القسم — طبّقها فوراً إذا ظهر النمط】")
            for r in old_rows:
                prefix = f"في حقل «{r.label}»: " if r.kind == "field" and r.label else ""
                lines.append(f"• {prefix}«{r.wrong}» → «{r.right}» [{r.count}x]")
            for c in new_rows:
                ctx = f" (…{c.context_before}…)" if c.context_before else ""
                field = f" في «{c.field_label}»" if c.field_label else ""
                lines.append(
                    f"• [{c.correction_type}]{field}: "
                    f"«{c.ocr_reading}» → «{c.human_correction}»"
                    f"{ctx} [{c.occurrence_count}x]"
                )
    finally:
        db.close()

    return "\n".join(lines)