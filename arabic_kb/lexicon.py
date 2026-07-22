"""
lexicon.py
==========
قاموس المصطلحات المعتمدة: أسماء أشخاص + مناطق عقارية + كلمات مجال.

وظيفتان:
  ١. مطابقة ضبابية عربية-الوعي — تقترح تصحيحاً لكلمة قريبة من مدخل معتمد
  ٢. كشف الأخطاء الصامتة — كلمة في موضع اسم غير موجودة بالقاموس = علامة صفراء

كل هذا محلي بالكامل — صفر كلفة API.
"""

import re
import unicodedata

# =============================================================================
# ١. التطبيع — توحيد أشكال الحرف قبل أي مقارنة
# =============================================================================

_DIACRITICS = re.compile(r'[\u064B-\u065F\u0670\u06D6-\u06ED]')
_TATWEEL    = re.compile(r'\u0640+')

def normalize_for_match(text: str) -> str:
    """
    تطبيع للمقارنة فقط — لا يُستخدم للعرض.
    يوحّد: الهمزات، التاء المربوطة، الألف المقصورة، ويحذف التشكيل والتطويل.
    """
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = _DIACRITICS.sub("", t)
    t = _TATWEEL.sub("", t)
    # توحيد الألف بكل أشكالها
    t = re.sub(r'[أإآٱا]', 'ا', t)
    # التاء المربوطة ← هاء
    t = t.replace('ة', 'ه')
    # الألف المقصورة ← ياء
    t = t.replace('ى', 'ي')
    # الكاف والهاء والياء الفارسية
    t = t.replace('ک', 'ك').replace('ی', 'ي')
    t = t.replace('ھ', 'ه').replace('ہ', 'ه')
    # همزات منفصلة
    t = t.replace('ؤ', 'و').replace('ئ', 'ي').replace('ء', '')
    return t.strip()


# =============================================================================
# ٢. أزواج الخلط — الفروق التي يُرجَّح أنها خطأ OCR لا اختلاف حقيقي
# =============================================================================

# كل مجموعة = أحرف يخلط بينها OCR في الخط اليدوي الشامي
CONFUSABLE_GROUPS = [
    set("بتثنيپ"),     # عائلة الجسم الواحد + النقاط
    set("دذ"),
    set("رز"),
    set("عغ"),
    set("حخجچ"),
    set("سش"),
    set("صض"),
    set("طظ"),
    set("قفڤ"),        # قاطرجي ↔ فاطرجي
    set("كل"),
    set("هة"),
    set("ويى"),
]

# خريطة سريعة: حرف → معرّف مجموعته
_CONF_MAP = {}
for _i, _g in enumerate(CONFUSABLE_GROUPS):
    for _ch in _g:
        _CONF_MAP.setdefault(_ch, set()).add(_i)


def is_confusable(a: str, b: str) -> bool:
    """هل الحرفان من نفس مجموعة الخلط؟"""
    if a == b:
        return True
    ga, gb = _CONF_MAP.get(a), _CONF_MAP.get(b)
    return bool(ga and gb and (ga & gb))


# =============================================================================
# ٣. مسافة تحرير موزونة — الخلط المعروف أرخص من التغيير العشوائي
# =============================================================================

SUB_COST_CONFUSABLE = 0.5   # استبدال بين حرفين متشابهين بصرياً
SUB_COST_OTHER      = 1.0   # استبدال عشوائي
INDEL_COST          = 1.0   # حذف أو إضافة

def weighted_distance(a: str, b: str, max_cost: float = 3.0) -> float:
    """
    مسافة تحرير واعية بأزواج الخلط العربية.
    ترجع max_cost+1 مبكراً إذا تجاوزت الحد (توفير حسابي).
    """
    a, b = normalize_for_match(a), normalize_for_match(b)
    if a == b:
        return 0.0
    la, lb = len(a), len(b)
    if abs(la - lb) > max_cost:
        return max_cost + 1

    prev = [j * INDEL_COST for j in range(lb + 1)]
    for i in range(1, la + 1):
        cur = [i * INDEL_COST] + [0.0] * lb
        row_min = cur[0]
        for j in range(1, lb + 1):
            if a[i - 1] == b[j - 1]:
                sub = prev[j - 1]
            else:
                cost = (SUB_COST_CONFUSABLE
                        if is_confusable(a[i - 1], b[j - 1])
                        else SUB_COST_OTHER)
                sub = prev[j - 1] + cost
            cur[j] = min(sub, prev[j] + INDEL_COST, cur[j - 1] + INDEL_COST)
            row_min = min(row_min, cur[j])
        if row_min > max_cost:
            return max_cost + 1
        prev = cur
    return prev[lb]


def only_confusable_diffs(a: str, b: str) -> bool:
    """
    هل الفرق بين الكلمتين محصور في أزواج الخلط المعروفة فقط؟
    شرط الأمان: لا نقترح استبدالاً إلا إذا كان الفرق مفسَّراً بصرياً.
    (أسبر ← أسمر مرفوض لأن ب/م ليسا زوج خلط)
    """
    a, b = normalize_for_match(a), normalize_for_match(b)
    if len(a) != len(b):
        return False
    diffs = 0
    for ca, cb in zip(a, b):
        if ca == cb:
            continue
        if not is_confusable(ca, cb):
            return False
        diffs += 1
    return 0 < diffs <= 2


# =============================================================================
# ٤. البحث عن مرشحين في القاموس
# =============================================================================

def find_candidates(word: str, entries: list, max_distance: float = 1.5,
                    limit: int = 3) -> list:
    """
    entries: قائمة dict فيها على الأقل {"term": str, "occurrence_count": int}
    يعيد قائمة مرشحين مرتبة: [{"term", "distance", "safe", "count"}]
      safe=True يعني الفرق مفسَّر بأزواج الخلط → آمن للاقتراح كزر
      safe=False يعني قريب لكن الفرق غير مفسَّر → علامة فقط، لا زر
    """
    if not word or len(normalize_for_match(word)) < 3:
        return []

    nw = normalize_for_match(word)
    out = []
    for e in entries:
        term = e["term"]
        if normalize_for_match(term) == nw:
            return []          # الكلمة صحيحة أصلاً — لا اقتراح
        d = weighted_distance(word, term, max_cost=max_distance)
        if d <= max_distance:
            out.append({
                "term": term,
                "distance": round(d, 2),
                "safe": only_confusable_diffs(word, term),
                "count": e.get("occurrence_count", 0),
            })
    # الأقرب أولاً، ثم الأكثر تكراراً، والآمن قبل غير الآمن
    out.sort(key=lambda x: (not x["safe"], x["distance"], -x["count"]))
    return out[:limit]


def is_known(word: str, entries: list) -> bool:
    """هل الكلمة موجودة حرفياً (بعد التطبيع) في القاموس؟"""
    nw = normalize_for_match(word)
    return any(normalize_for_match(e["term"]) == nw for e in entries)


# =============================================================================
# ٥. كشف مواضع الأسماء والمناطق في النص
# =============================================================================

# مؤشرات تسبق اسم منطقة عقارية
REGION_TRIGGERS = [
    "المنطقة العقارية", "منطقة عقارية", "المنطقه العقاريه",
    "منطقة", "المنطقة", "ناحية", "الناحية", "قرية", "القرية",
    "مدينة", "المدينة", "بلدة", "البلدة", "حي", "الحي",
]

# مؤشرات تسبق اسم شخص
PERSON_TRIGGERS = [
    "السيد", "السيدة", "المالك", "المالكة", "البائع", "المشتري",
    "الوكيل", "الموكل", "المستفيد", "المؤسس", "المؤسسون",
    "الشريك", "الشركاء", "الوريث", "الورثة", "باسم", "بن", "بنت",
]

# كلمات وظيفية لا تُعامل كأسماء أبداً
STOPWORDS = {
    "من", "الى", "إلى", "على", "في", "عن", "مع", "بين", "بعد", "قبل",
    "هذا", "هذه", "ذلك", "التي", "الذي", "كل", "بعض", "غير", "حتى",
    "قد", "لقد", "ثم", "أو", "او", "لكن", "إن", "ان", "أن", "كان",
    "شركة", "الشركة", "محدودة", "المحدودة", "المسؤولية", "مساهمة",
    "عقار", "العقار", "سهم", "أسهم", "مبلغ", "المبلغ", "تاريخ", "التاريخ",
    "رقم", "الرقم", "سجل", "السجل", "تجاري", "التجاري", "ليرة", "سورية",
}

_WORD_RE = re.compile(r'[\u0621-\u064A\u0660-\u0669]+')


def extract_candidate_terms(text: str):
    """
    يمسح النص ويستخرج الكلمات التي تقع في مواضع أسماء أو مناطق.
    يعيد: [{"word", "kind", "index", "before", "after"}]
      kind = "region" أو "person"
    """
    if not text:
        return []

    tokens = [(m.group(), m.start(), m.end())
              for m in _WORD_RE.finditer(text)]
    results = []

    # سلسلة الاسم العربي تمتد: «السيد أحمد بن عبد الرحمن قاطرجي»
    # فبمجرد بدء اسم، نتابع الكلمات التالية حتى نصطدم بكلمة وظيفية
    chain_left = 0

    for i, (w, s, e) in enumerate(tokens):
        prev1 = tokens[i - 1][0] if i >= 1 else ""
        prev2 = tokens[i - 2][0] if i >= 2 else ""
        nxt1  = tokens[i + 1][0] if i + 1 < len(tokens) else ""

        is_func = (w in STOPWORDS or len(w) < 3
                   or any(c.isdigit() or '\u0660' <= c <= '\u0669' for c in w))

        # «بن/بنت» لا يكسر السلسلة بل يمدّها
        if w in ("بن", "بنت", "ابن", "عبد", "أبو", "ابو", "آل", "ال"):
            if chain_left > 0:
                chain_left = 3
            continue

        if is_func:
            chain_left = 0
            continue

        kind = None
        # منطقة: الكلمة تسبق «العقارية» أو تتبع مؤشر منطقة
        if nxt1 in ("العقارية", "العقاريه"):
            kind = "region"
        elif prev1 in REGION_TRIGGERS or f"{prev2} {prev1}" in REGION_TRIGGERS:
            kind = "region"
        elif prev1 in PERSON_TRIGGERS or prev2 in PERSON_TRIGGERS:
            kind = "person"
            chain_left = 3
        elif chain_left > 0:
            kind = "person"
            chain_left -= 1

        if kind:
            results.append({
                "word":  w,
                "kind":  kind,
                "index": s,
                "before": prev1,
                "after":  nxt1,
            })

    return results


# =============================================================================
# ٦. الفحص الكامل — يجمع الاقتراحات والعلامات الصفراء
# =============================================================================

def scan_text(text: str, region_entries: list, person_entries: list) -> dict:
    """
    الفحص المحلي الكامل — صفر كلفة API.

    يعيد:
    {
      "suggestions": [ {word, kind, suggested, distance, before, after, index} ],
      "unknown":     [ {word, kind, before, after, index} ],
    }
      suggestions = اقتراح آمن (فرق مفسَّر بأزواج الخلط) → يُعرض كزر
      unknown     = كلمة غير معروفة بلا مرشّح آمن → علامة صفراء بلا زر
    """
    suggestions, unknown = [], []

    for c in extract_candidate_terms(text):
        entries = region_entries if c["kind"] == "region" else person_entries
        if not entries:
            continue

        if is_known(c["word"], entries):
            continue

        cands = find_candidates(c["word"], entries)
        safe  = [x for x in cands if x["safe"]]

        if safe:
            best = safe[0]
            suggestions.append({
                "word":      c["word"],
                "kind":      c["kind"],
                "suggested": best["term"],
                "distance":  best["distance"],
                "source":    "lexicon",
                "before":    c["before"],
                "after":     c["after"],
                "index":     c["index"],
            })
        else:
            unknown.append({
                "word":   c["word"],
                "kind":   c["kind"],
                "near":   [x["term"] for x in cands[:2]],
                "before": c["before"],
                "after":  c["after"],
                "index":  c["index"],
            })

    return {"suggestions": suggestions, "unknown": unknown}


# =============================================================================
# اختبار سريع
# =============================================================================
if __name__ == "__main__":
    regions = [{"term": "زاكية", "occurrence_count": 12},
               {"term": "قدسيا", "occurrence_count": 8},
               {"term": "جديدة عرطوز", "occurrence_count": 5}]
    persons = [{"term": "قاطرجي", "occurrence_count": 20},
               {"term": "نذير",   "occurrence_count": 9},
               {"term": "أسبر",   "occurrence_count": 3}]

    print("— مسافة موزونة —")
    for a, b in [("ماطرجي", "قاطرجي"), ("تاطرجي", "قاطرجي"),
                 ("ندير", "نذير"), ("أسمر", "أسبر"), ("زاكيه", "زاكية")]:
        print(f"  {a:8} ↔ {b:8} = {weighted_distance(a,b):.2f} "
              f"| آمن: {only_confusable_diffs(a,b)}")

    print("\n— فحص نص —")
    sample = ("العقار رقم 1476 منطقة زاكيه العقارية. "
              "السيد هشام ندير ماطرجي والسيد صلاح نذير قاطرجي. "
              "المستفيد راغب أسمر بن مروان.")
    r = scan_text(sample, regions, persons)
    for s in r["suggestions"]:
        print(f"  ✅ زر: «{s['word']}» ← «{s['suggested']}» "
              f"({s['kind']}, d={s['distance']})")
    for u in r["unknown"]:
        print(f"  ⚠️  غير معروفة: «{u['word']}» ({u['kind']}) "
              f"قريب من: {u['near']}")