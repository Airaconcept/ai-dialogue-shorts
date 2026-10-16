"""中英双语字幕条渲染（PIL，像素级可控）。

中文白字 52px + 英文黄字 36px，底部居中，黑描边。
输入：每镜 (cn_lines, en_lines)；输出：透明 PNG。
"""
from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont

W = 1080
NOTO = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def _font(size: int):
    try:
        return ImageFont.truetype(NOTO, size, index=3)
    except OSError:
        return ImageFont.truetype(NOTO, size)


def render_subtitle(cn_lines: list[str], en_lines: list[str],
                    out_path: str) -> str:
    f_cn, f_en = _font(52), _font(36)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))

    def measure(lines, font):
        hs, ws = [], []
        for ln in lines:
            b = probe.textbbox((0, 0), ln, font=font, stroke_width=2)
            hs.append(b[3] - b[1])
            ws.append(b[2] - b[0])
        return hs, ws

    cn_h, cn_w = measure(cn_lines, f_cn)
    en_h, en_w = measure(en_lines, f_en)
    assert max(cn_w + en_w, default=0) <= W - 60, "字幕行超宽，请手动断行"

    total_h = (sum(cn_h) + 12 * max(len(cn_lines) - 1, 0) + 18
               + sum(en_h) + 10 * max(len(en_lines) - 1, 0) + 20)
    img = Image.new("RGBA", (W, total_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = 10
    for ln in cn_lines:
        d.text((W / 2, y), ln, font=f_cn, fill=(255, 255, 255, 255),
               anchor="ma", stroke_width=2, stroke_fill=(0, 0, 0, 200))
        y += cn_h[cn_lines.index(ln)] + 12
    y += 6
    for ln in en_lines:
        d.text((W / 2, y), ln, font=f_en, fill=(255, 224, 130, 255),
               anchor="ma", stroke_width=2, stroke_fill=(0, 0, 0, 200))
        y += en_h[en_lines.index(ln)] + 10
    img.save(out_path)
    return out_path


def split_cn(text: str, width: int = 18) -> list[str]:
    """按标点把中文断成短行（每行至多 width 字）。"""
    seps = "，。；：、！？—…"
    lines, cur = [], ""
    for ch in text:
        cur += ch
        if ch in seps and len(cur) >= 8:
            lines.append(cur)
            cur = ""
    if cur:
        lines.append(cur)
    # 合并过短的行
    merged = []
    for ln in lines:
        if merged and len(merged[-1]) + len(ln) <= width:
            merged[-1] += ln
        else:
            merged.append(ln)
    # 仍超宽的硬切
    out = []
    for ln in merged:
        while len(ln) > width:
            out.append(ln[:width])
            ln = ln[width:]
        out.append(ln)
    return out


def split_en(text: str, width: int = 44) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines
