"""معالجة الوثائق:
تنظيف ← استخراج (Gemini) ← تصحيح تلقائي (Arabic KB + Number Validator) ←
تدقيق بصري (Claude) ← تعبئة قالب القسم.
"""
import base64
import json
import mimetypes
import os

import cv2
import numpy as np

import config as C
from arabic_kb.arabic_patterns import (
    build_ocr_hints_prompt,
    build_audit_hints_prompt,
    normalize_arabic_text,
)
from arabic_kb.number_validator import validate_and_fix_numbers

# =============================================================================
# الـ Prompts
# =============================================================================

EXTRACT_PROMPT = (
    "اقرأ هذه الصفحة واكتب نصها الكامل بالعربية بصيغة Markdown محافظاً على البنية "
    "(العناوين، الجداول، الأسطر). قد تكون مطبوعة أو بخط اليد أو مختلطة.\n\n"
    + build_ocr_hints_prompt() +
    "\nتجاوز التواقيع والأختام والبصمات ولا تصفها بنص. أخرج النص فقط."
)

AUDIT_VISION_PROMPT = (
    "أمامك صورة صفحة من وثيقة عربية رسمية، ونص أساس استخرجه نظام موثوق منها.\n"
    "اعتبر نص الأساس هو القراءة المعتمدة، ومهمتك تحسينه فقط عبر مقارنته بالصورة:\n"
    "- انسخ نص الأساس كما هو بنيةً وترتيباً وصياغةً.\n"
    "- غيّر كلمة أو رقماً فقط إذا أظهرت الصورة بوضوح تام قراءة مختلفة.\n"
    "- إن لم تكن متأكداً تماماً، أبقِ قراءة الأساس كما هي.\n"
    "- لا تضف داخل النص أي شرح أو وصف.\n"
    "- «ملاحظات»: فقط الشكوك الجوهرية على البيانات الحساسة "
    "(أرقام، تواريخ، أسماء، نسب) — بحد أقصى 5 ملاحظات.\n"
    "- «نسبة»: تقديرك 0-100.\n\n"
    + build_audit_hints_prompt() +
    "\n\nأخرج JSON فقط:\n"
    '{"نص_مصحح": "...", "نسبة": 0, "ملاحظات": ["..."]}\n\n'
    "نص الأساس:\n"
)

# =============================================================================
# تنظيف الصورة
# =============================================================================

def _deskew(g):
    inv = cv2.bitwise_not(g)
    thr = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thr > 0))
    if coords.shape[0] < 50:
        return g
    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < 0.3:
        return g
    h, w = g.shape
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(g, M, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


def clean_image(path):
    img = cv2.imread(path)
    if img is None:
        return path
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.fastNlMeansDenoising(g, h=10)
    g = _deskew(g)
    g = cv2.normalize(g, None, 0, 255, cv2.NORM_MINMAX)
    out = os.path.splitext(path)[0] + "_clean.png"
    cv2.imwrite(out, g)
    return out

# =============================================================================
# الاستخراج
# =============================================================================

def _gemini_model():
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    return genai.GenerativeModel(C.EXTRACT_MODEL)


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _openrouter_chat(content, max_tokens=4000):
    import requests
    resp = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                 "Content-Type": "application/json"},
        json={"model": C.EXTRACT_MODEL, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": content}]},
        timeout=300)
    resp.raise_for_status()
    data = resp.json()
    if "choices" not in data:
        raise RuntimeError(f"OpenRouter: {data.get('error', data)}")
    return data["choices"][0]["message"]["content"]


def _openrouter_extract(image_path):
    with open(image_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode()
    mime = mimetypes.guess_type(image_path)[0] or "image/png"
    return _openrouter_chat([
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        {"type": "text",      "text": EXTRACT_PROMPT},
    ])


def extract(image_path):
    if C.MOCK:
        name = os.path.basename(image_path)
        return (f"# نص خام تجريبي — {name}\n"
                "كشف حساب. الرقم: 14/1. التاريخ: 14/1/2010.\n"
                "قيمة 27,630 سهم من العقار رقم 1476 منطقة زاكية العقارية.\n"
                "المبلغ 1,320,000 ل.س. رقم الشيك 300030106.")
    if C.EXTRACT_PROVIDER == "openrouter":
        return _openrouter_extract(image_path)
    model = _gemini_model()
    with open(image_path, "rb") as f:
        data = f.read()
    mime = mimetypes.guess_type(image_path)[0] or "image/png"
    return model.generate_content([{"mime_type": mime, "data": data},
                                   EXTRACT_PROMPT]).text

# =============================================================================
# التدقيق البصري — Claude
# =============================================================================

def _parse_json_reply(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].replace("json", "", 1).strip()
    return json.loads(text)


def audit_page(image_path, raw_text, hints="", validator_warnings=None):
    """
    يقارن النص مع الصورة.
    validator_warnings: تحذيرات الـ number_validator تُضاف للـ prompt
    لتوجيه Claude لمراجعة أرقام محددة.
    """
    if C.MOCK:
        corrected = raw_text.replace("14/1.", "14/ر.")
        return {"corrected": corrected, "score": 88.0,
                "notes": ["رقم الكشف: «ر» التبست بـ ١"]}
    if C.STRUCTURE_ENGINE != "claude":
        return {"corrected": raw_text, "score": None, "notes": []}

    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    with open(image_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode()
    mime = mimetypes.guess_type(image_path)[0] or "image/png"

    # إضافة تحذيرات الـ validator كتعليمات إضافية لـ Claude
    extra = ""
    if validator_warnings:
        extra = (
            "\n⚠️ تحذيرات مدقق الأرقام التلقائي — راجع هذه المواضع في الصورة:\n"
            + "\n".join(f"  • {w}" for w in validator_warnings)
            + "\n\n"
        )

    full_prompt = (
        AUDIT_VISION_PROMPT
        + extra
        + ((hints + "\n\n") if hints else "")
        + raw_text
    )

    msg = client.messages.create(
        model=C.STRUCTURE_MODEL, max_tokens=4000,
        messages=[{"role": "user", "content": [
            {"type": "image",
             "source": {"type": "base64", "media_type": mime, "data": b64}},
            {"type": "text", "text": full_prompt},
        ]}])
    try:
        r = _parse_json_reply(msg.content[0].text)
        return {
            "corrected": r.get("نص_مصحح") or raw_text,
            "score":     float(r["نسبة"]) if r.get("نسبة") is not None else None,
            "notes":     r.get("ملاحظات", []),
        }
    except Exception:
        return {"corrected": raw_text, "score": None,
                "notes": ["تعذّر التدقيق البصري"]}

# =============================================================================
# تعبئة قالب القسم
# =============================================================================

def _section_prompt(kv_labels, table_columns, full_text, hints=""):
    tbl = (f"وأعمدة الجدول: {json.dumps(table_columns, ensure_ascii=False)}\n"
           if table_columns else "")
    return (
        "لديك نص مدقّق من وثيقة عربية. المطلوب تعبئة قالب.\n"
        f"حقول القالب:\n{json.dumps(kv_labels, ensure_ascii=False)}\n{tbl}"
        "انتبه بشدة للأرقام والحروف المتشابهة (ر/١، ٥/٠، ٢/٣).\n"
        "أخرج JSON فقط:\n"
        '{"حقول": {"اسم الحقل": "القيمة"}, '
        '"جدول": [["..."]], '
        '"ثقة": {"اسم الحقل": 0.0}, "مراجعة": ["حقول مشكوك فيها"]}\n\n'
        + ((hints + "\n\n") if hints else "")
        + f"النص:\n{full_text}"
    )


def structure_for_section(kv_labels, table_columns, full_text, hints=""):
    if C.MOCK:
        vals = {}
        samples = {"رقم العقد": "9029", "تاريخ العقد": "21/12/2009",
                   "رقم العقار": "1476", "المنطقة العقارية": "زاكية",
                   "المساحة": "4000", "السعر الكلي": "1320000",
                   "رقم كشف الحساب": "14/ر"}
        for lbl in kv_labels:
            if lbl in samples:
                vals[lbl] = samples[lbl]
        row = []
        if table_columns:
            demo = {"رقم الشيك": "300030106", "التاريخ": "31/1/2010",
                    "البنك": "المصرف العقاري", "الفرع": "فرع التعاوني",
                    "المستفيد": "خالد طعمه", "المبلغ": "1320000",
                    "نوع الدفعة": "شيك"}
            row = [demo.get(c, "") for c in table_columns]
        return {"حقول": vals, "جدول": [row] if row else [],
                "ثقة": {k: 0.9 for k in vals}, "مراجعة": ["تاريخ العقد"]}

    prompt = _section_prompt(kv_labels, table_columns, full_text, hints)

    if C.STRUCTURE_ENGINE == "claude":
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        msg = client.messages.create(
            model=C.STRUCTURE_MODEL, max_tokens=3000,
            messages=[{"role": "user", "content": prompt}])
        return _parse_json_reply(msg.content[0].text)

    if C.STRUCTURE_ENGINE == "openrouter":
        return _parse_json_reply(_openrouter_chat(prompt, max_tokens=3000))

    model = _gemini_model()
    return _parse_json_reply(model.generate_content(prompt).text)

# =============================================================================
# معالجة صفحة كاملة — Pipeline الكامل
# =============================================================================

def process_page(image_path, hints=""):
    """
    Pipeline:
    ١. تنظيف الصورة (اختياري)
    ٢. استخراج النص — Gemini
    ٣. تطبيع الأحرف — normalize_arabic_text
    ٤. تدقيق الأرقام — number_validator (بدون API، تلقائي)
    ٥. تدقيق بصري — Claude (يرى الصورة + تحذيرات الـ validator)
    """
    src = clean_image(image_path) if C.MODEL_IMAGE == "cleaned" else image_path

    # ١. الاستخراج
    raw = extract(src)

    # ٢. تطبيع الأحرف (كاف فارسية، هاء أردية...)
    raw = normalize_arabic_text(raw)

    # ٣. تدقيق الأرقام تلقائياً — بدون API
    val_result       = validate_and_fix_numbers(raw)
    raw_validated    = val_result["text"]
    val_warnings     = val_result["warnings"]
    val_fixes        = val_result["fixes"]

    # ٤. التدقيق البصري — Claude يرى الصورة + تحذيرات الـ validator
    audit = audit_page(
        src,
        raw_validated,
        hints=hints,
        validator_warnings=val_warnings,
    )

    # دمج ملاحظات الـ validator مع ملاحظات Claude
    all_notes = []
    if val_fixes:
        all_notes.append(f"تصحيحات تلقائية: {', '.join(val_fixes)}")
    if val_warnings:
        all_notes.extend(val_warnings)
    all_notes.extend(audit["notes"])

    return {
        "raw_text":       raw,
        "corrected_text": audit["corrected"],
        "score":          audit["score"],
        "notes":          all_notes,
        "result":         {"data": {"ملخص": audit["corrected"]}},
        "avg_conf":       None,
        "needs_review":   bool(all_notes),
    }