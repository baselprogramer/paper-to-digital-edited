"""
suggestions.py
==============
محرّك الاقتراحات: يدمج مصدرين ويطبّقهما بأمان.

المصدران:
  ١. القاموس (محلي، صفر كلفة) — مطابقة ضبابية آمنة
  ٢. Claude (لغوي) — يلتقط ما لا يستطيع القاموس تفسيره

القاعدة الحاكمة: الأرقام لا تُقترح أبداً كزر — تبقى للمراجعة البصرية.
"""

import datetime
import json
import re

from sqlalchemy import (Column, Integer, String, Text, Float, Boolean,
                        DateTime, ForeignKey, Enum)

from models import Base, SessionLocal, _engine
from arabic_kb.lexicon import normalize_for_match
from arabic_kb.lexicon_models import add_term


# =============================================================================
# جدول الاقتراحات — يحفظ القرار البشري (قبول / رفض)
# =============================================================================

class Suggestion(Base):
    """اقتراح تصحيح نصي واحد على موضع محدد في صفحة."""
    __tablename__ = "suggestions"

    id      = Column(Integer, primary_key=True)
    page_id = Column(Integer, ForeignKey("pages.id"), index=True)

    wrong     = Column(String(160), nullable=False)   # ما هو مكتوب الآن
    suggested = Column(String(160), nullable=False)   # المقترح
    kind = Column(
        Enum("person", "region", "word", name="sugg_kind_enum"),
        default="word"
    )
    origin = Column(
        Enum("lexicon", "claude", name="sugg_origin_enum"),
        default="lexicon"
    )
    reason     = Column(Text)                 # حجة الاقتراح (من Claude)
    confidence = Column(Float, default=0.8)

    # التثبيت: الكلمة السابقة واللاحقة لتحديد الموضع بدقة
    ctx_before = Column(String(80), default="")
    ctx_after  = Column(String(80), default="")
    char_index = Column(Integer, default=-1)  # موضع تقريبي في النص

    decision = Column(
        Enum("pending", "accepted", "rejected", name="sugg_decision_enum"),
        default="pending", index=True
    )
    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


def init_suggestions():
    Base.metadata.create_all(_engine)


# =============================================================================
# فلترة الأمان — ما الذي يُسمح له أن يصير زراً
# =============================================================================

_HAS_DIGIT = re.compile(r'[0-9\u0660-\u0669]')

def is_button_safe(wrong: str, suggested: str) -> bool:
    """
    زر الاستبدال مسموح فقط للنص. الأرقام تبقى للمراجعة البصرية اليدوية.
    """
    if not wrong or not suggested or wrong == suggested:
        return False
    if _HAS_DIGIT.search(wrong) or _HAS_DIGIT.search(suggested):
        return False           # ← القاعدة الحاكمة: لا أزرار للأرقام
    if len(normalize_for_match(wrong)) < 3:
        return False           # كلمات قصيرة جداً: خطر أن تكون حرف جر
    if len(wrong) > 60 or len(suggested) > 60:
        return False
    return True


# =============================================================================
# بناء قائمة الاقتراحات لصفحة
# =============================================================================

def build_for_page(page_id: int, text: str, claude_suggestions=None) -> dict:
    """
    يبني ويحفظ اقتراحات صفحة، ويعيد ما يُعرض في الواجهة.

    claude_suggestions: قائمة من Claude بالشكل
        [{"خطأ":..., "صح":..., "سبب":..., "ثقة":..., "قبل":..., "بعد":...}]

    يعيد: {"buttons": [...], "flags": [...]}
        buttons = اقتراحات آمنة تُعرض كأزرار
        flags   = علامات صفراء بلا زر (كلمات غير معروفة / شكوك أرقام)
    """
    from arabic_kb.lexicon_models import scan_page_text

    db = SessionLocal()
    try:
        # امسح اقتراحات معلّقة قديمة لنفس الصفحة (إعادة معالجة)
        (db.query(Suggestion)
           .filter_by(page_id=page_id, decision="pending").delete())
        db.commit()

        seen = set()
        rows = []

        # ---- المصدر ١: القاموس المحلي ----
        local = scan_page_text(text)
        for s in local["suggestions"]:
            key = (s["word"], s["suggested"], s["before"], s["after"])
            if key in seen or not is_button_safe(s["word"], s["suggested"]):
                continue
            seen.add(key)
            rows.append(Suggestion(
                page_id=page_id,
                wrong=s["word"], suggested=s["suggested"],
                kind=s["kind"], origin="lexicon",
                reason=f"مطابقة قاموس (مسافة {s['distance']})",
                confidence=max(0.6, 1.0 - s["distance"] / 3.0),
                ctx_before=s["before"][:80], ctx_after=s["after"][:80],
                char_index=s["index"],
            ))

        # ---- المصدر ٢: Claude ----
        for s in (claude_suggestions or []):
            w = str(s.get("خطأ") or s.get("wrong") or "").strip()
            r = str(s.get("صح")  or s.get("right") or "").strip()
            if not is_button_safe(w, r):
                continue
            before = str(s.get("قبل") or s.get("before") or "")[:80]
            after  = str(s.get("بعد") or s.get("after")  or "")[:80]
            key = (w, r, before, after)
            if key in seen:
                continue
            seen.add(key)
            try:
                conf = float(s.get("ثقة") or s.get("confidence") or 0.75)
            except (TypeError, ValueError):
                conf = 0.75
            rows.append(Suggestion(
                page_id=page_id,
                wrong=w, suggested=r,
                kind=s.get("نوع") or "word",
                origin="claude",
                reason=str(s.get("سبب") or s.get("reason") or "")[:500],
                confidence=conf,
                ctx_before=before, ctx_after=after,
                char_index=-1,
            ))

        db.add_all(rows)
        db.commit()

        buttons = [{
            "id": r.id, "wrong": r.wrong, "suggested": r.suggested,
            "kind": r.kind, "origin": r.origin, "reason": r.reason,
            "confidence": round(r.confidence or 0, 2),
            "before": r.ctx_before, "after": r.ctx_after,
        } for r in rows]

        flags = [{
            "word": u["word"], "kind": u["kind"],
            "near": u["near"], "before": u["before"], "after": u["after"],
        } for u in local["unknown"]]

        return {"buttons": buttons, "flags": flags}
    finally:
        db.close()


# =============================================================================
# تطبيق اقتراح — استبدال مثبَّت بالسياق
# =============================================================================

def _replace_anchored(text: str, wrong: str, right: str,
                      before: str = "", after: str = "") -> tuple:
    """
    يستبدل «wrong» بـ«right» في الموضع المثبَّت بالسياق فقط.
    يعيد (النص_الجديد, عدد_الاستبدالات).

    الأولوية:
      ١. مطابقة محصورة بين before و after → موضع واحد بالضبط
      ٢. إن تعذّر، أول مطابقة للكلمة ككلمة كاملة
    """
    if not wrong or wrong not in text:
        return text, 0

    ww = re.escape(wrong)

    # ١) مثبَّت بالسياق من الجهتين
    if before and after:
        pat = re.compile(
            rf'({re.escape(before)}\s+){ww}(\s+{re.escape(after)})')
        new, n = pat.subn(rf'\g<1>{right}\g<2>', text, count=1)
        if n:
            return new, n

    # ٢) مثبَّت من جهة واحدة
    if before:
        pat = re.compile(rf'({re.escape(before)}\s+){ww}\b')
        new, n = pat.subn(rf'\g<1>{right}', text, count=1)
        if n:
            return new, n
    if after:
        pat = re.compile(rf'\b{ww}(\s+{re.escape(after)})')
        new, n = pat.subn(rf'{right}\g<1>', text, count=1)
        if n:
            return new, n

    # ٣) كلمة كاملة، أول موضع فقط (لا استبدال جماعي)
    pat = re.compile(rf'(?<![\u0621-\u064A]){ww}(?![\u0621-\u064A])')
    new, n = pat.subn(right, text, count=1)
    return new, n


def apply_suggestion(suggestion_id: int, text: str) -> dict:
    """
    يطبّق اقتراحاً على النص، يسجّل القبول، ويضيف المصطلح للقاموس.
    يعيد: {"ok", "text", "replaced", "message"}
    """
    db = SessionLocal()
    try:
        s = db.get(Suggestion, suggestion_id)
        if not s:
            return {"ok": False, "text": text, "replaced": 0,
                    "message": "الاقتراح غير موجود"}

        new_text, n = _replace_anchored(
            text, s.wrong, s.suggested, s.ctx_before, s.ctx_after)

        if n == 0:
            return {"ok": False, "text": text, "replaced": 0,
                    "message": "تعذّر تحديد موضع الكلمة — عدّلها يدوياً"}

        s.decision   = "accepted"
        s.decided_at = datetime.datetime.utcnow()
        db.commit()

        # المصطلح المعتمد يدخل القاموس — هنا يتراكم الذهب
        if s.kind in ("person", "region"):
            add_term(s.suggested, s.kind, source="verified")

        return {"ok": True, "text": new_text, "replaced": n,
                "message": f"استُبدلت «{s.wrong}» بـ«{s.suggested}»"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "text": text, "replaced": 0, "message": str(e)}
    finally:
        db.close()


def reject_suggestion(suggestion_id: int) -> dict:
    """
    يسجّل رفض اقتراح.
    الرفض معلومة ثمينة: الكلمة الأصلية صحيحة → تدخل القاموس.
    """
    db = SessionLocal()
    try:
        s = db.get(Suggestion, suggestion_id)
        if not s:
            return {"ok": False, "message": "الاقتراح غير موجود"}

        s.decision   = "rejected"
        s.decided_at = datetime.datetime.utcnow()
        db.commit()

        # المراجع رفض ⇒ الكلمة كما هي صحيحة ⇒ اعتمدها
        if s.kind in ("person", "region"):
            add_term(s.wrong, s.kind, source="verified")

        return {"ok": True,
                "message": f"رُفض الاقتراح، واعتُمدت «{s.wrong}» في القاموس"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "message": str(e)}
    finally:
        db.close()


def get_page_suggestions(page_id: int) -> list:
    """يجلب الاقتراحات المعلّقة لصفحة."""
    db = SessionLocal()
    try:
        rows = (db.query(Suggestion)
                .filter_by(page_id=page_id, decision="pending")
                .order_by(Suggestion.confidence.desc()).all())
        return [{
            "id": r.id, "wrong": r.wrong, "suggested": r.suggested,
            "kind": r.kind, "origin": r.origin, "reason": r.reason,
            "confidence": round(r.confidence or 0, 2),
            "before": r.ctx_before, "after": r.ctx_after,
        } for r in rows]
    finally:
        db.close()


def suggestion_accuracy() -> dict:
    """
    نسبة قبول الاقتراحات حسب المصدر — لقياس جودة كل مصدر مع الوقت.
    """
    from sqlalchemy import func
    db = SessionLocal()
    try:
        rows = (db.query(Suggestion.origin, Suggestion.decision,
                         func.count(Suggestion.id))
                .filter(Suggestion.decision != "pending")
                .group_by(Suggestion.origin, Suggestion.decision).all())
        out = {}
        for origin, decision, cnt in rows:
            out.setdefault(origin, {})[decision] = cnt
        for origin, d in out.items():
            a, r = d.get("accepted", 0), d.get("rejected", 0)
            d["accuracy"] = round(a / (a + r), 3) if (a + r) else None
        return out
    finally:
        db.close()