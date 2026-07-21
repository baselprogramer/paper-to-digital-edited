"""
arabic_patterns.py
==================
قاعدة معرفة الأحرف والأرقام العربية للخط اليدوي الشامي (السوري).
مبنية من مشاهدة مباشرة لعينات خط يدوي شامي حقيقي.

الهدف: حقن هذه المعرفة في prompts نماذج الذكاء الاصطناعي
       وبناء pre-processor يصحح الأخطاء الشائعة قبل إرسال النص للـ API.
"""

import re

# =============================================================================
# القسم الأول: الأرقام
# =============================================================================

DIGITS = {
    "٣": {
        "unicode": "\u0663",
        "correct_value": 3,
        "visual_forms": [
            {
                "id": "3_classic",
                "description_ar": "الشكل الكلاسيكي: خط عمودي مع ثلاثة أسنان أفقية إلى اليسار، يشبه حرف E مقلوب",
                "description_en": "Classic form: vertical stroke with three horizontal serifs to the left",
                "ocr_risk": "LOW",
                "confusable_with": [],
            },
            {
                "id": "3_shami_single_tooth",
                "description_ar": (
                    "الشكل الشامي العامي: خط عمودي مع سن واحدة فقط في المنتصف — "
                    "يُكتب هكذا كثيراً في سوريا ولبنان وفلسطين. "
                    "OCR يخطئه ويقرأه ٢. "
                    "علامة التمييز: الرقم ٢ له قاعدة أفقية في الأسفل، "
                    "أما الشامي ٣ فلا قاعدة له — الخط ينتهي حراً في الأسفل."
                ),
                "description_en": (
                    "Syrian colloquial form: vertical stroke with ONE serif in the middle. "
                    "OCR frequently misreads as 2. "
                    "Key difference: 2 has a flat base at bottom, Shami-3 has no base."
                ),
                "ocr_risk": "CRITICAL",
                "confusable_with": ["٢"],
                "disambiguation_clue": (
                    "الرقم ٢ له قاعدة أفقية واضحة في الأسفل. "
                    "الشامي ٣ ليس له قاعدة — الخط ينتهي حراً."
                ),
            },
        ],
        "context_priority": ["تواريخ", "أرقام_وطنية", "أرقام_عقارية", "مبالغ"],
        "date_note": (
            "في التواريخ: ١٩٩٣ أو ٢٠٠٣ أو ٢٠١٣ — "
            "إذا قرأ OCR ٢ في موضع السنة فتحقق إذا كانت ٣"
        ),
    },

    "٢": {
        "unicode": "\u0662",
        "correct_value": 2,
        "visual_forms": [
            {
                "id": "2_standard",
                "description_ar": "منحنى علوي ينزل ويُنتهي بقاعدة أفقية واضحة في الأسفل",
                "ocr_risk": "MEDIUM",
                "confusable_with": ["٣_shami"],
                "disambiguation_clue": "٢ لها قاعدة أفقية واضحة في الأسفل. الشامي ٣ ليس له قاعدة",
            },
        ],
    },

    "١": {
        "unicode": "\u0661",
        "correct_value": 1,
        "visual_forms": [
            {
                "id": "1_standard",
                "description_ar": "خط عمودي مستقيم، أحياناً مع قاعدة صغيرة",
                "ocr_risk": "MEDIUM",
                "confusable_with": ["ر", "ل"],
                "disambiguation_clue": "في سياق الأرقام: خط عمودي منفرد = ١. في أرقام الكشوف (١٤/ر): الحرف بعد الشرطة راء وليس ١",
            },
            {
                "id": "1_with_serif",
                "description_ar": "خط عمودي مع شرطة علوية مائلة — شائع في الخط الشامي",
                "ocr_risk": "LOW",
                "confusable_with": [],
            },
        ],
    },

    "٤": {
        "unicode": "\u0664",
        "correct_value": 4,
        "visual_forms": [
            {
                "id": "4_reverse_triangle",
                "description_ar": "مثلث عكسي مفتوح من الأعلى مع ذيل نازل",
                "ocr_risk": "MEDIUM",
                "confusable_with": ["٣", "٦"],
            },
        ],
    },

    "٥": {
        "unicode": "\u0665",
        "correct_value": 5,
        "visual_forms": [
            {
                "id": "5_circle_tail",
                "description_ar": "دائرة صغيرة مع ذيل صاعد — يشبه القلب المقلوب",
                "ocr_risk": "HIGH",
                "confusable_with": ["٠", "ه"],
                "disambiguation_clue": "٥ له ذيل صاعد خارج من الدائرة. ٠ مجرد بيضاوية مغلقة بلا ذيل",
            },
        ],
    },

    "٦": {
        "unicode": "\u0666",
        "correct_value": 6,
        "visual_forms": [
            {
                "id": "6_hook",
                "description_ar": "خطاف نازل مع دائرة في الأسفل",
                "ocr_risk": "LOW",
                "confusable_with": ["٧"],
            },
        ],
    },

    "٧": {
        "unicode": "\u0667",
        "correct_value": 7,
        "visual_forms": [
            {
                "id": "7_standard",
                "description_ar": "خط أفقي علوي مع خط نازل مائل — مطابق تقريباً للرقم 7 اللاتيني",
                "ocr_risk": "LOW",
                "confusable_with": ["١"],
            },
            {
                "id": "7_with_middle_bar",
                "description_ar": "نفس الشكل مع شرطة أفقية في المنتصف — شائع عند بعض الكتّاب الشاميين",
                "ocr_risk": "MEDIUM",
                "confusable_with": ["٤"],
            },
        ],
    },

    "٨": {
        "unicode": "\u0668",
        "correct_value": 8,
        "visual_forms": [
            {
                "id": "8_double_loop",
                "description_ar": "دائرتان متصلتان فوق بعض — شكل لانهائي ∞ عمودي",
                "ocr_risk": "LOW",
                "confusable_with": [],
            },
        ],
    },

    "٩": {
        "unicode": "\u0669",
        "correct_value": 9,
        "visual_forms": [
            {
                "id": "9_circle_tail",
                "description_ar": "دائرة مع ذيل نازل — يشبه رقم 9 اللاتيني",
                "ocr_risk": "LOW",
                "confusable_with": ["٤"],
            },
        ],
    },

    "٠": {
        "unicode": "\u0660",
        "correct_value": 0,
        "visual_forms": [
            {
                "id": "0_oval",
                "description_ar": "بيضاوية مغلقة صغيرة بلا ذيل",
                "ocr_risk": "MEDIUM",
                "confusable_with": ["٥", "ه"],
                "disambiguation_clue": "٠ بيضاوية مغلقة تماماً بلا ذيل. ٥ له ذيل صاعد",
            },
        ],
    },
}

# =============================================================================
# القسم الثاني: الأحرف الإشكالية
# =============================================================================

LETTERS = {
    "ه": {
        "unicode": "\u0647",
        "name": "الهاء",
        "positions": {
            "initial": {
                "description_ar": "شكل يشبه حرف E صغير مقلوب أو مربع مفتوح من اليمين مع ذيل",
                "example_words": ["هاني", "هدى", "هند", "هيثم"],
                "ocr_risk": "MEDIUM",
                "confusable_with": ["ح_initial"],
            },
            "medial_classic": {
                "description_ar": (
                    "دائرتان متداخلتان أو متلاصقتان — تبدو كعقدة أو رقم 8 أفقي مصغر. "
                    "شائع في الخط الرسمي."
                ),
                "example_words": ["نهاد", "فهد", "سهل", "جهاد"],
                "ocr_risk": "MEDIUM",
                "confusable_with": ["ح_medial"],
                "disambiguation_clue": "الهاء الكلاسيكية = دائرتان. الحاء = قوس واحد مفتوح من الأعلى",
            },
            "medial_shami": {
                "description_ar": (
                    "يُكتب كرقم ٧ أو كحرف y مقلوب — خط نازل مع سن واحدة. "
                    "شائع جداً في الخط العامي الشامي. "
                    "OCR يخطئه كثيراً ويقرأه ياء أو نون أو رقم ٧."
                ),
                "example_words": ["نهاد (شامي)", "فهد (شامي)"],
                "ocr_risk": "CRITICAL",
                "confusable_with": ["ي_medial", "ن_medial", "٧"],
                "disambiguation_clue": (
                    "في سياق الأسماء: إذا جاء شكل يشبه ٧ أو y وسط كلمة "
                    "بجانب أحرف عربية = هاء غالباً"
                ),
            },
            "final": {
                "description_ar": "دائرة مغلقة أو شبه مغلقة مع ذيل نازل أو بدونه",
                "example_words": ["وجه", "نبه", "شبه"],
                "ocr_risk": "LOW",
                "confusable_with": ["ة_final"],
            },
        },
    },

    "ة": {
        "unicode": "\u0629",
        "name": "التاء المربوطة",
        "positions": {
            "final": {
                "description_ar": (
                    "دائرة مغلقة مع نقطتين فوقها — "
                    "تُكتب أحياناً كهاء نهائية بدون نقطتين في الخط العامي السريع"
                ),
                "ocr_risk": "MEDIUM",
                "confusable_with": ["ه_final"],
                "disambiguation_clue": "وجود نقطتين = تاء مربوطة. غيابهما = هاء. السياق النحوي يحسم",
            },
        },
    },

    "ا": {
        "unicode": "\u0627",
        "name": "الألف",
        "positions": {
            "isolated_initial": {
                "description_ar": "خط عمودي مستقيم",
                "ocr_risk": "LOW",
                "confusable_with": ["١"],
            },
        },
        "variants": ["آ (مد)", "أ (همزة فوق)", "إ (همزة تحت)", "ى (مقصورة)"],
        "shami_note": "في الخط الشامي السريع: الهمزات تُحذف كثيراً (أحمد→احمد، إبراهيم→ابراهيم)",
    },

    "ب_ت_ث": {
        "name": "عائلة الباء-التاء-الثاء",
        "shared_body_description": "جسم واحد مشترك: قوس أفقي مسطح. التمييز بالنقاط فقط",
        "members": {
            "ب": {"dots": "نقطة واحدة تحت", "unicode": "\u0628"},
            "ت": {"dots": "نقطتان فوق",     "unicode": "\u062a"},
            "ث": {"dots": "ثلاث نقاط فوق",  "unicode": "\u062b"},
        },
        "ocr_risk": "HIGH",
        "critical_note": "في الخط اليدوي السريع: النقاط مستعجلة أو مدمجة — OCR يخلط بين الثلاثة باستمرار",
        "disambiguation_clue": "اعتمد على السياق والكلمة الكاملة إذا أخفق عد النقاط",
    },

    "ي": {
        "unicode": "\u064a",
        "name": "الياء",
        "positions": {
            "medial": {
                "description_ar": "شكل يشبه الباء المتوسطة — قوس صغير مع نقطتين تحت",
                "ocr_risk": "MEDIUM",
                "confusable_with": ["ب_medial", "ن_medial"],
            },
            "final_without_dots": {
                "description_ar": "ذيل منحنٍ طويل إلى اليسار بدون نقاط — هذه ألف مقصورة ى",
                "ocr_risk": "HIGH",
                "confusable_with": ["ي", "ى"],
                "disambiguation_clue": "في الأسماء الشامية: يحيى، مصطفى، عيسى، زكريا — الحرف الأخير ألف مقصورة",
                "shami_examples": ["يحيى", "مصطفى", "عيسى", "زكريا"],
            },
        },
    },

    "ع_غ": {
        "name": "العين والغين",
        "positions": {
            "medial": {
                "description_ar": (
                    "شكلهما متطابق تقريباً في وسط الكلمة — "
                    "خط أفقي مع تعرج صغير. "
                    "نقطة فوق = غين. بدون نقطة = عين. "
                    "في الخط السريع النقطة تُختزل أو تُوضع بعيداً."
                ),
                "example_words_ain":  ["سعيد", "بعد", "فعل"],
                "example_words_ghain": ["بغداد", "غني"],
                "ocr_risk": "HIGH",
                "disambiguation_clue": "نقطة فوق الشكل المتوسط = غين. بدون نقطة = عين",
            },
        },
    },

    "ك": {
        "unicode": "\u0643",
        "name": "الكاف",
        "positions": {
            "shami_simplified": {
                "description_ar": (
                    "في الخط الشامي السريع: تُكتب كشكل مبسط يشبه L مع خط علوي، "
                    "أو كحرف كاف فارسي ک"
                ),
                "unicode_variant": "\u06a9",
                "ocr_risk": "MEDIUM",
                "confusable_with": ["ل", "ک"],
                "disambiguation_clue": "الكاف الشامية المبسطة شائعة في: كريم، كمال، كاظم",
            },
        },
    },

    "ر_ز": {
        "name": "الراء والزاي",
        "shared_body": "خط نازل منحنٍ قصير — التمييز بالنقطة فوق الزاي فقط",
        "ocr_risk": "HIGH",
        "critical_cases": [
            "رقم كشف الحساب: ١٤/ر — حرف الراء يُقرأ خطأً كرقم ١",
            "في أرقام الملفات والكشوف: الراء بعد شرطة مائلة",
        ],
        "confusable_with_numbers": ["١"],
        "disambiguation_clue": "الراء والزاي أقصر وأكثر انحناءً من الرقم ١. في أرقام الكشوف: الحرف بعد / هو راء",
    },

    "ن": {
        "unicode": "\u0646",
        "name": "النون",
        "positions": {
            "medial": {
                "description_ar": "في وسط الكلمة: يتحول لشكل بسيط يشبه الباء المتوسطة تماماً",
                "ocr_risk": "HIGH",
                "confusable_with": ["ب_medial", "ي_medial", "ت_medial"],
                "disambiguation_clue": "نقطة واحدة فوق = نون. تحت = باء. فوق اثنتان = تاء",
            },
        },
    },
}

# =============================================================================
# القسم الثالث: أزواج الخلط الأكثر شيوعاً
# =============================================================================

CONFUSABLES = [
    {
        "wrong_reading": "٢",
        "correct_reading": "٣",
        "risk_level": "CRITICAL",
        "context": ["تواريخ", "أرقام وطنية", "أرقام عقارية", "مبالغ"],
        "explanation": "الرقم ٣ الشامي بسن واحدة يُقرأ ٢. أكثر خطأ يؤثر على صحة البيانات",
        "detection_hint": "في التاريخ: إذا قرأ OCR سنة كـ ١٩٩٢ — تحقق إذا كانت ١٩٩٣",
    },
    {
        "wrong_reading": "١",
        "correct_reading": "ر",
        "risk_level": "HIGH",
        "context": ["أرقام كشوف الحساب", "ترقيم الملفات"],
        "explanation": "حرف الراء بعد شرطة مائلة يُقرأ كرقم ١ (مثل ١٤/ر → ١٤/١)",
        "detection_hint": "إذا جاء ١ بعد / في رقم كشف = الأرجح أنها ر",
    },
    {
        "wrong_reading": "ي أو ن أو ٧",
        "correct_reading": "ه (هاء وسط شامية)",
        "risk_level": "CRITICAL",
        "context": ["أسماء", "وسط كلمة"],
        "explanation": "الهاء الشامية المتوسطة تشبه ٧ أو y — يُقرأ حرفاً آخر أو رقماً",
    },
    {
        "wrong_reading": "ب أو ت أو ث",
        "correct_reading": "أي من الثلاثة",
        "risk_level": "HIGH",
        "context": ["أي موضع"],
        "explanation": "جسم واحد والتمييز بالنقاط المستعجلة في الخط اليدوي",
    },
    {
        "wrong_reading": "٥",
        "correct_reading": "٠",
        "risk_level": "HIGH",
        "context": ["مبالغ مالية"],
        "explanation": "خطير جداً في المبالغ — ٥٠٠٠ مقابل ٠٠٠٠",
    },
    {
        "wrong_reading": "ع",
        "correct_reading": "غ",
        "risk_level": "MEDIUM",
        "context": ["وسط الكلمة"],
        "explanation": "النقطة فوق الغين تُحذف في الخط السريع",
    },
]

# =============================================================================
# القسم الرابع: قواعد السياق
# =============================================================================

CONTEXT_RULES = [
    {
        "field_type": "تاريخ",
        "rules": [
            "السنوات المتوقعة بين ١٩٨٠ و٢٠١٥",
            "إذا قرأت سنة خارج هذا النطاق — راجع الأرقام المشتبه بها (٢↔٣، ٦↔٠)",
            "الأشهر بين ١ و١٢ — إذا قرأت ١٣+ فالأرجح خطأ في رقم",
            "الأيام بين ١ و٣١",
        ],
    },
    {
        "field_type": "رقم_وطني_سوري",
        "rules": [
            "١١ رقماً بالضبط",
            "أول رقم: ١ (ذكر) أو ٢ (أنثى)",
            "إذا كان الإجمالي غير ١١ خانة — راجع ٢↔٣ و٥↔٠",
        ],
    },
    {
        "field_type": "رقم_عقاري",
        "rules": [
            "عادة ٣-٦ أرقام",
            "يسبقه أو يتبعه اسم المنطقة العقارية",
            "قد يحتوي شرطة مائلة: ١٤/ر",
        ],
    },
    {
        "field_type": "مبلغ_مالي",
        "rules": [
            "المبالغ بالليرة السورية: عادة ٤-٨ أرقام",
            "انتبه لـ ٥ مقابل ٠ في المبالغ الكبيرة",
            "المبالغ تُكتب أحياناً بالكلمات ثم بالأرقام بين قوسين",
        ],
    },
    {
        "field_type": "اسم_شخص",
        "shami_common_names": [
            "محمد", "أحمد", "علي", "خالد", "سامر", "باسل", "وسيم",
            "ياسر", "عمر", "إبراهيم", "كمال", "جمال", "نبيل", "فيصل",
            "كريم", "سعيد", "وليد", "رامي", "طارق", "هيثم", "غسان",
            "عدنان", "صلاح", "هادي", "زكريا", "كامل", "عيسى", "إحسان",
            "أسبر", "ربيع", "زياد", "نادر",
            "فاطمة", "مريم", "زينب", "نور", "هند", "سارة", "لينا",
            "رنا", "نهاد", "تكريم", "غنان", "إيمان", "ميساء", "دانا",
        ],
        "rules": [
            "الأسماء الشامية كثيراً ما تحذف الهمزات: أحمد→احمد",
            "الهاء في وسط الاسم (نهاد، فهد) عرضة للخطأ — دقق فيها",
            "قارن مع قائمة الأسماء الشائعة لتأكيد القراءة",
        ],
    },
]

# =============================================================================
# القسم الخامس: بناء نصوص الـ Prompt
# =============================================================================

def build_ocr_hints_prompt(field_types: list = None) -> str:
    """
    يبني نص تعليمات للحقن في prompt نموذج الاستخراج (Gemini).
    field_types: قائمة بأنواع الحقول المتوقعة مثل ["تاريخ", "اسم_شخص"]
    """
    lines = [
        "═══ تعليمات خاصة بالخط اليدوي الشامي (السوري) ═══",
        "",
        "【أرقام — تنبيهات حرجة】",
        "• الرقم ٣ الشامي: يُكتب بسن واحدة فقط وسط الرقم وبدون قاعدة سفلية.",
        "  شكله قريب جداً من الرقم ٢ لكن الفرق الحاسم:",
        "  ٢ له قاعدة أفقية في الأسفل — الشامي ٣ ليس له قاعدة على الإطلاق.",
        "  ⚠ إذا رأيت رقماً يشبه ٢ بدون قاعدة = الأرجح أنه ٣.",
        "• الرقم ٥: دائرة مع ذيل صاعد — لا تخلطه مع ٠ (بيضاوية مغلقة بلا ذيل).",
        "• في المبالغ المالية: ٥٠٠٠ ≠ ٠٠٠٠ — دقق في الصفر والخمسة.",
        "",
        "【أحرف — تنبيهات حرجة】",
        "• الهاء في وسط الكلمة لها شكلان في الخط الشامي:",
        "  ① الكلاسيكي: دائرتان متداخلتان كالعقدة — مثال: نهاد بالخط الرسمي.",
        "  ② الشامي العامي: يشبه رقم ٧ أو حرف y مقلوب.",
        "  كلا الشكلين = هاء. لا تقرأه ياء أو نون أو رقم ٧.",
        "• باء/تاء/ثاء: جسم واحد — الفرق بعدد النقاط فقط (١تحت=ب، ٢فوق=ت، ٣فوق=ث).",
        "  في الخط السريع: النقاط مستعجلة — اعتمد على السياق والكلمة الكاملة.",
        "• العين/الغين في وسط الكلمة: شكلهما متطابق تقريباً — نقطة فوق = غين.",
        "• حرف الراء ≠ رقم ١: في أرقام الكشوف (مثل ١٤/ر) الحرف بعد الشرطة هو الراء وليس ١.",
        "",
    ]

    if field_types:
        lines.append("【تعليمات خاصة بحقول هذه الوثيقة】")
        for ft in field_types:
            rules_obj = next((r for r in CONTEXT_RULES if r["field_type"] == ft), None)
            if rules_obj and "rules" in rules_obj:
                lines.append(f"• {ft}:")
                for rule in rules_obj["rules"]:
                    lines.append(f"  - {rule}")
        lines.append("")

    lines += [
        "【أسماء شامية شائعة في الوثائق العقارية السورية】",
        "ذكور: محمد، أحمد، خالد، ياسر، باسل، كمال، نبيل، غسان، هادي، زكريا، كامل، عيسى، إحسان، أسبر",
        "إناث: نهاد، تكريم، غنان، إيمان، لينا، مريم، فاطمة، نور، هند",
        "إذا قرأت كلمة تشبه اسماً من هذه القائمة — أعد التحقق قبل تعديله.",
        "",
        "═══════════════════════════════════════════════════════",
    ]

    return "\n".join(lines)


def build_audit_hints_prompt(field_types: list = None) -> str:
    """نص تعليمات مخصص لـ Claude في مرحلة التدقيق البصري."""
    base = build_ocr_hints_prompt(field_types)
    audit_extra = "\n".join([
        "",
        "【تعليمات التدقيق البصري الإضافية】",
        "• قارن كل رقم في النص مع الصورة — الأرقام أولوية قصوى.",
        "• إذا رأيت في الصورة رقماً بدون قاعدة سفلية وقرأه النظام ٢ → صححه إلى ٣.",
        "• في التواريخ: السنوات خارج نطاق ١٩٨٠-٢٠١٥ مشبوهة — راجعها.",
        "• في أرقام الهوية (١١ خانة): أول خانة ١ أو ٢ فقط.",
        "• في المبالغ: قارن الرقم بالكلمات (إن وُجدت) مع الرقم بالأرقام.",
    ])
    return base + audit_extra


# =============================================================================
# القسم السادس: Pre-processor
# =============================================================================

# تصحيحات تلقائية آمنة ١٠٠٪ بدون سياق
_AUTO_CORRECTIONS = [
    (r"ک", "ك"),   # كاف فارسية → عربية
    (r"ھ|ہ", "ه"), # هاء فارسية/أردية → عربية
    (r"ی", "ي"),   # ياء فارسية → عربية
]


def normalize_arabic_text(text: str, convert_latin_digits: bool = False) -> str:
    """تطبيق التصحيحات التلقائية الآمنة على النص المستخرج."""
    if not text:
        return text
    for pattern, replacement in _AUTO_CORRECTIONS:
        text = re.sub(pattern, replacement, text)
    if convert_latin_digits:
        text = text.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
    return text


def validate_date_string(date_str: str) -> dict:
    """يتحقق من منطق التاريخ ويقترح تصحيحات."""
    result = {"valid": True, "warnings": [], "suggestions": []}
    parts = re.findall(r"[\d٠-٩]+", date_str)
    if len(parts) == 3:
        ar2en = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
        d, m, y = (int(p.translate(ar2en)) for p in parts)
        if not 1 <= d <= 31:
            result["valid"] = False
            result["warnings"].append(f"يوم غير منطقي: {parts[0]}")
        if not 1 <= m <= 12:
            result["valid"] = False
            result["warnings"].append(f"شهر غير منطقي: {parts[1]}")
        if not 1900 <= y <= 2030:
            result["valid"] = False
            result["warnings"].append(f"سنة غير منطقية: {parts[2]}")
            suggested = str(y).replace("2", "3", 1)
            if suggested != str(y):
                result["suggestions"].append(
                    f"هل السنة {suggested} بدلاً من {y}؟ (خطأ ٢↔٣ الشامي)"
                )
    return result


def validate_national_id(id_str: str) -> dict:
    """تحقق بسيط من منطق رقم الهوية السوري."""
    result = {"valid": True, "warnings": []}
    digits = re.sub(r"[^\d٠-٩]", "", id_str)
    digits_en = digits.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    if len(digits_en) != 11:
        result["valid"] = False
        result["warnings"].append(f"رقم الهوية {len(digits_en)} خانة بدلاً من ١١")
    if digits_en and digits_en[0] not in ("1", "2"):
        result["valid"] = False
        result["warnings"].append(f"أول رقم في الهوية يجب أن يكون ١ أو ٢، وُجد: {digits_en[0]}")
    return result