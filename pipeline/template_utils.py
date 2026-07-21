"""قراءة قالب إكسل القسم وتعبئته بالقيم المستخرجة.

يدعم نمطين داخل نفس الورقة:
1) حقول «تسمية ← قيمة»: العمود A تسمية الحقل، والعمود B قيمته.
2) كتلة جدول: صف ترويسات (عدة أعمدة متجاورة نصية) تليه صفوف بيانات
   (مثل «جدول الشيكات»: رقم الشيك | التاريخ | البيان | ...).

parse_template() يستخرج البنية مرة واحدة عند إنشاء القسم وتُخزَّن JSON.
fill_template() ينسخ القالب ويكتب القيم في أماكنها ويحفظ ملف الناتج.
"""
import json
import shutil

import openpyxl


def parse_template(path):
    """يعيد بنية القالب:
    {"sheet": name,
     "kv": [{"row": r, "label": txt}, ...],
     "table": {"header_row": r, "columns": [..]} أو null}
    """
    wb = openpyxl.load_workbook(path)
    ws = wb.active

    kv = []
    table = None
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        cells = [(c.column, str(c.value).strip())
                 for c in row if c.value not in (None, "")]
        if not cells:
            continue
        r = row[0].row
        # كتلة جدول: 3+ خلايا نصية متجاورة في صف واحد = صف ترويسات
        if table is None and len(cells) >= 3:
            table = {"header_row": r, "columns": [t for _, t in cells]}
            continue
        # داخل منطقة الجدول (بعد الترويسات): صفوف بيانات نموذجية — نتجاهلها
        if table and r > table["header_row"]:
            continue
        # حقل تسمية في العمود A (القيمة النموذجية في B تُتجاهل)
        first_col, first_txt = cells[0]
        if first_col == 1:
            kv.append({"row": r, "label": first_txt})

    return {"sheet": ws.title, "kv": kv, "table": table}


def labels_of(fields):
    """قوائم جاهزة للموديل: تسميات الحقول + أعمدة الجدول."""
    kv_labels = [f["label"] for f in fields.get("kv", [])]
    tbl = fields.get("table")
    return kv_labels, (tbl["columns"] if tbl else [])


def fill_template(template_path, fields, values, out_path):
    """ينسخ القالب ويعبّئه.
    values = {"حقول": {label: value}, "جدول": [[v1, v2, ...], ...]}
    يكتب قيمة كل حقل في العمود B من صفّه، وصفوف الجدول تحت صف الترويسات
    (يمسح صفوف البيانات النموذجية القديمة أولاً)."""
    shutil.copy(template_path, out_path)
    wb = openpyxl.load_workbook(out_path)
    ws = wb[fields["sheet"]] if fields["sheet"] in wb.sheetnames else wb.active

    filled = values.get("حقول", {}) or {}
    for f in fields.get("kv", []):
        val = filled.get(f["label"])
        if val not in (None, ""):
            if isinstance(val, (list, dict)):
                val = json.dumps(val, ensure_ascii=False)
            ws.cell(row=f["row"], column=2, value=val)

    tbl = fields.get("table")
    rows = values.get("جدول", []) or []
    if tbl and rows:
        hr = tbl["header_row"]
        ncols = len(tbl["columns"])
        # مسح بيانات نموذجية قديمة تحت الترويسات
        for r in range(hr + 1, ws.max_row + 1):
            for c in range(1, ncols + 1):
                ws.cell(row=r, column=c, value=None)
        for i, rowvals in enumerate(rows, start=1):
            for c, v in enumerate(rowvals[:ncols], start=1):
                ws.cell(row=hr + i, column=c, value=v)

    wb.save(out_path)
    return out_path
