"""
FinGestor - Geracao de cupom (comprovante) em PNG e PDF usando Pillow,
e compartilhamento nativo no Android via FileProvider (pyjnius).

Nao depende de Kivy. Pillow (PIL) gera a imagem; a mesma imagem e salva
tambem como PDF (img.save(..., 'PDF')), evitando dependencias extras.
"""
import os
from PIL import Image, ImageDraw, ImageFont

from db import fmt_money, STATUS_LABEL

W = 720  # largura do cupom em px
PAD = 36


def _font(size, bold=False):
    """Tenta fontes comuns; cai para a fonte padrao do PIL se nao achar."""
    candidates = [
        "/system/fonts/Roboto-Bold.ttf" if bold else "/system/fonts/Roboto-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        try:
            if os.path.exists(c):
                return ImageFont.truetype(c, size)
        except Exception:
            pass
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _text_h(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def render_receipt_image(sale, company):
    """Retorna um objeto PIL.Image com o cupom da venda."""
    f_title = _font(40, bold=True)
    f_h = _font(26, bold=True)
    f = _font(24)
    f_small = _font(20)
    f_total = _font(34, bold=True)

    # Estima altura
    n_inst = len(sale.get("installments", []))
    height = 520 + n_inst * 40 + 160
    img = Image.new("RGB", (W, height), "white")
    d = ImageDraw.Draw(img)

    dark = (33, 37, 41)
    gray = (110, 116, 122)
    primary = (33, 82, 165)
    y = PAD

    # Cabecalho: logo + empresa
    logo_path = (company or {}).get("logo_path")
    x_text = PAD
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((120, 120))
            img.paste(logo, (PAD, y), logo)
            x_text = PAD + 140
        except Exception:
            pass

    d.text((x_text, y), (company or {}).get("name") or "Minha Empresa",
           font=f_title, fill=primary)
    yy = y + 50
    for key in ("document", "phone", "email", "address"):
        val = (company or {}).get(key)
        if val:
            d.text((x_text, yy), str(val), font=f_small, fill=gray)
            yy += 26
    y = max(y + 140, yy + 10)

    d.line([(PAD, y), (W - PAD, y)], fill=(220, 224, 228), width=2)
    y += 24

    # Titulo comprovante
    d.text((PAD, y), "COMPROVANTE DE VENDA", font=f_h, fill=dark)
    d.text((W - PAD - 160, y), f"#{sale['id']:05d}", font=f_h, fill=gray)
    y += 44

    cliente = (sale.get("contact") or {}).get("name") if sale.get("contact") else "Sem cliente"
    d.text((PAD, y), f"Cliente: {cliente}", font=f, fill=dark); y += 34
    d.text((PAD, y), f"Data: {sale['sale_date']}", font=f, fill=dark); y += 34
    d.text((PAD, y), f"Pagamento: {STATUS_LABEL.get(sale['payment_type'], sale['payment_type'])}",
           font=f, fill=dark)
    y += 44

    d.line([(PAD, y), (W - PAD, y)], fill=(235, 238, 240), width=1)
    y += 20

    # Valores
    def row(label, value, bold=False, color=dark):
        nonlocal y
        d.text((PAD, y), label, font=(f_h if bold else f), fill=color)
        val_font = f_total if bold else f
        vw = d.textlength(value, font=val_font)
        d.text((W - PAD - vw, y), value, font=val_font, fill=color)
        y += 48 if bold else 34

    row("Subtotal", fmt_money(sale["gross_cents"]))
    if sale["discount_cents"] > 0:
        row("Desconto", "- " + fmt_money(sale["discount_cents"]), color=(180, 60, 60))
    y += 6
    d.line([(PAD, y), (W - PAD, y)], fill=(220, 224, 228), width=2); y += 16
    row("TOTAL", fmt_money(sale["net_cents"]), bold=True, color=primary)
    y += 10

    # Parcelas
    insts = sale.get("installments", [])
    if len(insts) > 1 or sale["payment_type"] == "INSTALLMENT":
        d.text((PAD, y), "Parcelas", font=f_h, fill=dark); y += 40
        for i in insts:
            st = STATUS_LABEL.get(_inst_status(i, sale), "")
            line = f"{i['number']}/{len(insts)}  venc. {i['due_date']}"
            d.text((PAD, y), line, font=f_small, fill=gray)
            right = f"{fmt_money(i['amount_cents'])}  [{st}]"
            rw = d.textlength(right, font=f_small)
            d.text((W - PAD - rw, y), right, font=f_small, fill=dark)
            y += 36
        y += 10

    # Rodape
    footer = (company or {}).get("receipt_footer") or "Obrigado pela preferencia!"
    d.line([(PAD, y), (W - PAD, y)], fill=(235, 238, 240), width=1); y += 16
    d.text((PAD, y), footer, font=f_small, fill=gray); y += 30
    d.text((PAD, y), "Gerado pelo FinGestor", font=_font(16), fill=(180, 185, 190))
    y += 30

    return img.crop((0, 0, W, min(height, y + PAD)))


def _inst_status(inst, sale):
    from db import Database
    return Database.installment_status(inst)


def save_receipt(sale, company, out_dir, fmt="both"):
    """Gera o cupom e salva. Retorna dict {'png': path, 'pdf': path}."""
    os.makedirs(out_dir, exist_ok=True)
    img = render_receipt_image(sale, company)
    base = os.path.join(out_dir, f"cupom_{sale['id']:05d}")
    out = {}
    if fmt in ("png", "both"):
        p = base + ".png"
        img.save(p, "PNG")
        out["png"] = p
    if fmt in ("pdf", "both"):
        p = base + ".pdf"
        img.convert("RGB").save(p, "PDF", resolution=150.0)
        out["pdf"] = p
    return out


# ---------------------------------------------------------------------------
# Relatorios (PDF / PNG)
# ---------------------------------------------------------------------------

def render_report_image(title, company, sections, subtitle=""):
    """sections = [(heading, [(left, right), ...]), ...]. Retorna PIL.Image."""
    f_title = _font(38, bold=True)
    f_sub = _font(22)
    f_h = _font(26, bold=True)
    f = _font(23)
    dark = (33, 37, 41)
    gray = (110, 116, 122)
    primary = (33, 82, 165)

    total_rows = sum(len(rows) for _, rows in sections)
    height = 240 + len(sections) * 70 + total_rows * 38 + 120
    img = Image.new("RGB", (W, height), "white")
    d = ImageDraw.Draw(img)
    y = PAD

    d.text((PAD, y), (company or {}).get("name") or "Minha Empresa",
           font=f_h, fill=primary)
    y += 40
    d.text((PAD, y), title, font=f_title, fill=dark)
    y += 48
    if subtitle:
        d.text((PAD, y), subtitle, font=f_sub, fill=gray)
        y += 32
    d.line([(PAD, y), (W - PAD, y)], fill=(220, 224, 228), width=2)
    y += 20

    for heading, rows in sections:
        d.text((PAD, y), heading, font=f_h, fill=primary)
        y += 40
        if not rows:
            d.text((PAD, y), "(sem dados)", font=f, fill=gray)
            y += 38
        for left, right in rows:
            d.text((PAD, y), str(left), font=f, fill=dark)
            rw = d.textlength(str(right), font=f)
            d.text((W - PAD - rw, y), str(right), font=f, fill=dark)
            y += 38
        y += 10
        d.line([(PAD, y), (W - PAD, y)], fill=(235, 238, 240), width=1)
        y += 16

    d.text((PAD, y + 6), "Gerado pelo FinGestor", font=_font(16), fill=(180, 185, 190))
    return img.crop((0, 0, W, min(height, y + 50)))


def save_report(title, company, sections, out_dir, filename, subtitle="", fmt="pdf"):
    os.makedirs(out_dir, exist_ok=True)
    img = render_report_image(title, company, sections, subtitle)
    base = os.path.join(out_dir, filename)
    out = {}
    if fmt in ("png", "both"):
        p = base + ".png"; img.save(p, "PNG"); out["png"] = p
    if fmt in ("pdf", "both"):
        p = base + ".pdf"; img.convert("RGB").save(p, "PDF", resolution=150.0)
        out["pdf"] = p
    return out


# ---------------------------------------------------------------------------
# Compartilhamento (Android)
# ---------------------------------------------------------------------------

def app_docs_dir(sub, fallback):
    """Diretorio de saida para arquivos compartilhaveis.
    No Android usa getExternalFilesDir (coberto pelo FileProvider e mais
    acessivel); no desktop usa 'fallback'."""
    base = fallback
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        ctx = PythonActivity.mActivity
        f = ctx.getExternalFilesDir(None)
        if f is not None:
            base = f.getAbsolutePath()
    except Exception:
        pass
    d = os.path.join(base, sub)
    os.makedirs(d, exist_ok=True)
    return d


def _share_via_mediastore(path, mime, text):
    """Publica o arquivo no MediaStore (Download/FinGestor) e compartilha a
    content:// URI. Funciona em Android 10+ (API 29) e e aceita pelo WhatsApp."""
    from jnius import autoclass, cast
    VERSION = autoclass("android.os.Build$VERSION")
    if VERSION.SDK_INT < 29:
        raise RuntimeError("MediaStore requer Android 10+")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    ContentValues = autoclass("android.content.ContentValues")
    MediaStore = autoclass("android.provider.MediaStore")
    Downloads = autoclass("android.provider.MediaStore$Downloads")
    String = autoclass("java.lang.String")

    activity = PythonActivity.mActivity
    resolver = activity.getContentResolver()
    name = os.path.basename(path)

    values = ContentValues()
    values.put("_display_name", name)
    values.put("mime_type", mime)
    values.put("relative_path", "Download/FinGestor")
    uri = resolver.insert(Downloads.EXTERNAL_CONTENT_URI, values)
    if uri is None:
        raise RuntimeError("MediaStore insert retornou nulo")

    with open(path, "rb") as f:
        data = f.read()
    ostream = resolver.openOutputStream(uri)
    ostream.write(data)
    ostream.flush()
    ostream.close()

    intent = Intent(Intent.ACTION_SEND)
    intent.setType(mime)
    intent.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
    intent.putExtra(Intent.EXTRA_TEXT, cast("java.lang.CharSequence", String(text)))
    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    title = cast("java.lang.CharSequence", String("Compartilhar"))
    chooser = Intent.createChooser(intent, title)
    chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    chooser.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    activity.startActivity(chooser)


def _share_via_provider(path, mime, text):
    from jnius import autoclass, cast
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    File = autoclass("java.io.File")
    String = autoclass("java.lang.String")
    activity = PythonActivity.mActivity
    context = activity.getApplicationContext()
    authority = str(context.getPackageName()) + ".fileprovider"
    jfile = File(path)
    errs = []
    uri = None
    for cls in ("org.kivy.android.GenericFileProvider",
                "androidx.core.content.FileProvider",
                "android.support.v4.content.FileProvider"):
        try:
            FP = autoclass(cls)
            uri = FP.getUriForFile(context, authority, jfile)
            break
        except Exception as e:
            errs.append(f"{cls.split('.')[-1]}={type(e).__name__}")
    if uri is None:
        raise RuntimeError("FileProvider: " + ", ".join(errs))
    intent = Intent(Intent.ACTION_SEND)
    intent.setType(mime)
    intent.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
    intent.putExtra(Intent.EXTRA_TEXT, cast("java.lang.CharSequence", String(text)))
    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    title = cast("java.lang.CharSequence", String("Compartilhar"))
    chooser = Intent.createChooser(intent, title)
    chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    chooser.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    activity.startActivity(chooser)


def _share_via_fromfile(path, mime, text):
    from jnius import autoclass, cast
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    Uri = autoclass("android.net.Uri")
    File = autoclass("java.io.File")
    String = autoclass("java.lang.String")
    # Desativa o StrictMode para permitir file:// (evita FileUriExposedException)
    StrictMode = autoclass("android.os.StrictMode")
    VmBuilder = autoclass("android.os.StrictMode$VmPolicy$Builder")
    StrictMode.setVmPolicy(VmBuilder().build())
    activity = PythonActivity.mActivity
    uri = Uri.fromFile(File(path))
    intent = Intent(Intent.ACTION_SEND)
    intent.setType(mime)
    intent.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
    intent.putExtra(Intent.EXTRA_TEXT, cast("java.lang.CharSequence", String(text)))
    title = cast("java.lang.CharSequence", String("Compartilhar"))
    chooser = Intent.createChooser(intent, title)
    chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    activity.startActivity(chooser)


def share_file(path, mime="application/pdf", text="Segue seu comprovante."):
    """Abre o share sheet do Android. Tenta FileProvider e, se falhar,
    usa file:// com StrictMode desativado. Retorna (True, '') ou
    (False, mensagem_detalhada)."""
    errors = []
    for strategy in (_share_via_mediastore, _share_via_provider, _share_via_fromfile):
        try:
            strategy(path, mime, text)
            return True, ""
        except Exception as e:
            import traceback
            traceback.print_exc()
            errors.append(f"{strategy.__name__}: {type(e).__name__}: {e}")
    return False, " || ".join(errors) if errors else "jnius indisponivel (desktop)"
