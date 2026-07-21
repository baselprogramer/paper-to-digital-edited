"""تقسيم ملفات PDF إلى صور صفحات (PyMuPDF — بلا اعتماديات خارجية)."""
import os
import fitz  # PyMuPDF

IMG_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")


def split_to_images(src_path, out_dir, dpi=300):
    """يعيد قائمة مسارات صور الصفحات.
    PDF -> صورة لكل صفحة بدقة 300. صورة مفردة -> تُنسخ كصفحة واحدة."""
    os.makedirs(out_dir, exist_ok=True)
    ext = os.path.splitext(src_path)[1].lower()

    if ext in IMG_EXT:
        dst = os.path.join(out_dir, "page_001.png")
        import shutil
        shutil.copy(src_path, dst)
        return [dst]

    if ext != ".pdf":
        raise ValueError(f"نوع غير مدعوم: {ext}")

    paths = []
    doc = fitz.open(src_path)
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(matrix=mat)
        dst = os.path.join(out_dir, f"page_{i:03d}.png")
        pix.save(dst)
        paths.append(dst)
    doc.close()
    return paths
