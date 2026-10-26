"""Печать PNG/PDF на принтер Windows по имени, без диалога выбора принтера.
Картинка вписывается в печатную область принтера (размер бумаги задаётся в драйвере принтера)
и при необходимости поворачивается, чтобы ориентация совпадала с этикеткой."""
import io

import pypdfium2 as pdfium
import win32con
import win32print
import win32ui
from PIL import Image, ImageDraw, ImageFont, ImageWin

MAX_PDF_DPI = 300


def list_printers():
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    return sorted({p[2] for p in win32print.EnumPrinters(flags)})


def _pages(data, kind, dpi):
    if kind == "pdf":
        pdf = pdfium.PdfDocument(data)
        scale = min(dpi, MAX_PDF_DPI) / 72
        return [pdf[i].render(scale=scale).to_pil() for i in range(len(pdf))]
    return [Image.open(io.BytesIO(data))]


def print_file(printer, data, kind, title):
    """kind - png | pdf. Ошибки печати пробрасываются наружу текстом исключения."""
    dc = win32ui.CreateDC()
    dc.CreatePrinterDC(printer)
    try:
        width = dc.GetDeviceCaps(win32con.HORZRES)
        height = dc.GetDeviceCaps(win32con.VERTRES)
        dpi = dc.GetDeviceCaps(win32con.LOGPIXELSX)
        pages = _pages(data, kind, dpi)
        dc.StartDoc(title[:100])
        for img in pages:
            if (img.width > img.height) != (width > height):
                img = img.rotate(90, expand=True)
            if img.mode != "RGB":
                bg = Image.new("RGB", img.size, "white")
                bg.paste(img, mask=img.getchannel("A") if "A" in img.getbands() else None)
                img = bg
            scale = min(width / img.width, height / img.height)
            w, h = int(img.width * scale), int(img.height * scale)
            x, y = (width - w) // 2, (height - h) // 2
            dc.StartPage()
            ImageWin.Dib(img).draw(dc.GetHandleOutput(), (x, y, x + w, y + h))
            dc.EndPage()
        dc.EndDoc()
    finally:
        dc.DeleteDC()


def test_page(label):
    """Пробная этикетка для окна настроек."""
    img = Image.new("RGB", (580, 400), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((4, 4, 575, 395), outline="black", width=4)
    try:
        font = ImageFont.truetype("arial.ttf", 44)  # шрифт Windows с кириллицей
    except OSError:
        font = ImageFont.load_default()
    d.text((30, 120), f"Print Agent\n{label}\nпробная печать", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
