"""
number_validator.py
====================
مدقق الأرقام — يعمل بعد Gemini وقبل Claude.
"""
import re

AR2EN = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
EN2AR = str.maketrans("0123456789",   "٠١٢٣٤٥٦٧٨٩")

def _to_int(s):
    return int(str(s).translate(AR2EN))

def _ar(n, use_arabic=True):
    return str(n).translate(EN2AR) if use_arabic else str(n)

def _uses_arabic(s):
    return any(c in "٠١٢٣٤٥٦٧٨٩" for c in s)

# =====================================================================
# ١. توحيد الأرقام اللاتينية → هندية-عربية
# =====================================================================
def unify_digits(text):
    result = []
    for ch in text:
        if "0" <= ch <= "9":
            result.append(ch.translate(EN2AR))
        else:
            result.append(ch)
    return "".join(result)

# =====================================================================
# ٢. التواريخ — نمط ذكي يفرق بين اليوم والشهر والسنة
# =====================================================================
# يوم/شهر/سنة — السنة دائماً 4 أرقام أو 2 رقم بعد اليوم والشهر
DATE_RE = re.compile(
    r'([٠-٩]{1,2}|\d{1,2})'       # يوم (1-2 رقم)
    r'\s*[/\-\.]\s*'
    r'([٠-٩]{1,2}|\d{1,2})'       # شهر (1-2 رقم)
    r'\s*[/\-\.]\s*'
    r'([٠-٩]{2,4}|\d{2,4})'       # سنة (2-4 أرقام)
)

def _fix_year(y_raw):
    yi = _to_int(y_raw)
    ar = _uses_arabic(y_raw)
    warnings  = []
    suggestion = None

    # سنتان فقط — أكملها
    if yi < 100:
        full = 2000 + yi if yi < 50 else 1900 + yi
        suggestion = _ar(full, ar)
        warnings.append(f"سنة مختصرة {yi} → {full}")
        return suggestion, warnings

    if 1980 <= yi <= 2030:
        return y_raw, []

    # معكوسة؟
    rev = int(str(yi)[::-1])
    if 1980 <= rev <= 2030:
        suggestion = _ar(rev, ar)
        warnings.append(f"سنة معكوسة {yi} → {rev}")
        return suggestion, warnings

    # خطأ ٢↔٣ الشامي
    for i, ch in enumerate(str(yi)):
        if ch == "2":
            cand = int(str(yi)[:i] + "3" + str(yi)[i+1:])
            if 1980 <= cand <= 2030:
                suggestion = _ar(cand, ar)
                warnings.append(f"خطأ ٢↔٣ الشامي: {yi} → {cand}")
                return suggestion, warnings

    warnings.append(f"سنة غير منطقية: {yi}")
    return y_raw, warnings


def validate_dates(text):
    warnings = []
    result   = text

    for m in DATE_RE.finditer(text):
        d_raw, mo_raw, y_raw = m.group(1), m.group(2), m.group(3)
        d_i  = _to_int(d_raw)
        mo_i = _to_int(mo_raw)

        fixed_y, w = _fix_year(y_raw)
        warnings.extend(w)

        if not (1 <= mo_i <= 12):
            warnings.append(f"شهر غير منطقي: {mo_i} في «{m.group()}»")
        if not (1 <= d_i  <= 31):
            warnings.append(f"يوم غير منطقي: {d_i} في «{m.group()}»")

        if fixed_y != y_raw:
            old = m.group()
            new = old[:old.rfind(y_raw)] + fixed_y + old[old.rfind(y_raw)+len(y_raw):]
            result = result.replace(old, new, 1)

    return result, warnings

# =====================================================================
# ٣. السجل التجاري
# =====================================================================
SIJIL_RE = re.compile(
    r'(?:س\s*ت|سجل\s*تجاري|ت\.?\s{0,2})[\s:]*([٠-٩\d]{3,6})'
)

def validate_sijil(text):
    warnings = []
    for m in SIJIL_RE.finditer(text):
        num = _to_int(m.group(1))
        if num < 100 or num > 999999:
            warnings.append(f"رقم سجل تجاري مشبوه: {m.group(1)}")
    return warnings

# =====================================================================
# ٤. النسب المئوية — مجموعها يجب أن يساوي 100
# =====================================================================
PCT_RE = re.compile(r'([٠-٩\d]+(?:[.,][٠-٩\d]+)?)\s*[%٪]')

def validate_percentages(text):
    warnings = []
    pcts = []
    for m in PCT_RE.finditer(text):
        try:
            pcts.append(float(m.group(1).translate(AR2EN)))
        except ValueError:
            pass
    if len(pcts) >= 2:
        total = sum(pcts)
        if not (99 <= total <= 101) and total != 0:
            warnings.append(f"مجموع النسب {total}٪ ≠ ١٠٠٪ — راجع: {pcts}")
    return warnings

# =====================================================================
# ٥. الدالة الرئيسية
# =====================================================================
def validate_and_fix_numbers(text):
    """
    يعيد:
    {
        "text":     النص بعد التصحيح,
        "warnings": تحذيرات للمدقق البشري,
        "fixes":    ما صُحِّح تلقائياً,
    }
    """
    fixes    = []
    warnings = []

    t = unify_digits(text)
    if t != text:
        fixes.append("توحيد أرقام لاتينية → هندية-عربية")

    t2, dw = validate_dates(t)
    if t2 != t:
        fixes.append("تصحيح تاريخ")
    warnings.extend(dw)
    t = t2

    warnings.extend(validate_sijil(t))
    warnings.extend(validate_percentages(t))

    return {"text": t, "warnings": warnings, "fixes": fixes}


# =====================================================================
# اختبار بالبيانات الحقيقية من الصورة
# =====================================================================
if __name__ == "__main__":
    tests = [
        # من الصورة الفعلية
        "س ت حلب ٦٢٧٢ ت ٢١٧٦  من ٢٢/٨/٢٨ إلى ١٤/٨/١٨",
        "تاريخ: ٢٢/٨/١٨ إلى ١٤/٨/١٨",
        "المؤسسون: من سلوم ٥٠٪ وراغب ٥٠٪",
        "تاريخ التأسيس: 18/8/1202",
        "من ٢٣/١/٨ تا ٢٣/٨/١/٨",
        "النسب: ٧٠٪ و٤٢٪",         # مجموع خاطئ
    ]
    for s in tests:
        r = validate_and_fix_numbers(s)
        print(f"قبل:      {s}")
        print(f"بعد:      {r['text']}")
        if r["fixes"]:    print(f"✅ صُحِّح: {r['fixes']}")
        if r["warnings"]: print(f"⚠️  تحذير: {r['warnings']}")
        print()