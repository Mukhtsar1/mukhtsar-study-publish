"""
Slide layouts. One renderer, four paths.

Layout kinds:
  cover        - hook slide (optional photo window)
  item         - numbered content slide (optional photo window)
  checklist    - list of short lines with check icons
  cta          - closing call-to-action (never has a photo window)

The only difference between 'A'/'B' and their '-img' variants is whether a
transparent photo window is drawn at the top and the text block moves down.
"""
from config.themes import CANVAS
from config.icons import icon

WIN = CANVAS["window"]          # (x0, y0, x1, y1)
WIN_TOP, WIN_H = 150, 520       # css position of the window


def _css(t: dict, assets: str, fonts: str) -> str:
    return f"""
@font-face {{ font-family:'Cairo'; src:url('{fonts}/Cairo-600.ttf'); font-weight:600; }}
@font-face {{ font-family:'Cairo'; src:url('{fonts}/Cairo-700.ttf'); font-weight:700; }}
@font-face {{ font-family:'Cairo'; src:url('{fonts}/Cairo-800.ttf'); font-weight:800; }}
@font-face {{ font-family:'Cairo'; src:url('{fonts}/Cairo-900.ttf'); font-weight:900; }}
@font-face {{ font-family:'Pixel'; src:url('{fonts}/PressStart2P.ttf'); }}
@page {{ size:{CANVAS['w']}px {CANVAS['h']}px; margin:0; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:{CANVAS['w']}px; height:{CANVAS['h']}px; font-family:'Cairo',sans-serif;
  color:{t['text']}; background-color:{t['bg']};
  background-image:url('{assets}/tiles/{t['grid']}'); background-repeat:repeat;
  position:relative; overflow:hidden; }}
.checker {{ position:absolute; bottom:0; left:0; width:{CANVAS['w']}px; height:22px;
  background-image:url('{assets}/tiles/{t['checker']}'); background-repeat:repeat-x; }}
.logo {{ position:absolute; top:44px; left:52px; }} .logo img {{ width:250px; }}
.tag {{ position:absolute; top:52px; right:52px; }}
.tagin {{ position:relative; display:inline-block; }}
.tagsh {{ position:absolute; top:7px; right:-7px; width:100%; height:100%;
  background:{t['tag_shadow']}; border-radius:8px; }}
.tagf {{ position:relative; background:{t['tag_bg']}; color:{t['tag_text']};
  font-weight:800; font-size:29px; padding:8px 28px; border-radius:8px; }}
.eyebrow {{ font-family:'Liberation Sans',Arial,sans-serif; font-weight:bold;
  font-size:23px; letter-spacing:6px; color:{t['accent_2']};
  direction:ltr; unicode-bidi:isolate; }}
.ltr {{ direction:ltr; unicode-bidi:isolate; display:inline-block; }}
.px {{ font-family:'Pixel'; color:{t['pixel_fill']}; }}
.pxsh {{ font-family:'Pixel'; color:{t['pixel_shadow']}; position:absolute; }}
.dots span {{ display:inline-block; width:13px; height:13px;
  background:{t['dot']}; margin:0 6px; }}
.footer {{ position:absolute; bottom:44px; left:0; width:100%; text-align:center;
  font-family:'Liberation Sans',Arial,sans-serif; font-weight:bold; font-size:23px;
  letter-spacing:3px; color:{t['footer']}; }}
.src {{ position:absolute; bottom:95px; left:0; width:100%; text-align:center;
  font-weight:600; font-size:22px; color:{t['source_note']}; }}
.photowin {{ position:absolute; top:{WIN_TOP}px; left:60px; width:960px; height:{WIN_H}px;
  background:#FF00FF; border:4px solid {t['frame_border']}; border-radius:26px; }}
.hl {{ color:{t['accent']}; font-weight:800; }}
.hl2 {{ color:{t['accent_2']}; font-weight:800; }}
"""


def _pixel(text: str, size: int, height: int) -> str:
    return (f'<div style="position:relative; height:{height}px">'
            f'<div class="pxsh" style="font-size:{size}px; top:9px; width:100%;'
            f' text-align:center; text-indent:9px; direction:ltr">{text}</div>'
            f'<div class="px" style="font-size:{size}px; position:absolute; top:0;'
            f' width:100%; text-align:center; direction:ltr">{text}</div></div>')


def _dots(n: int = 4) -> str:
    return '<div class="dots" style="margin:22px 0">' + "".join(
        "<span></span>" for _ in range(n)) + "</div>"


def _layered_icon(name: str, size: int, t: dict) -> str:
    """Gold/navy icon with the hard offset shadow behind it."""
    h = int(size * 1.2)
    return (f'<div style="position:relative; height:{h}px">'
            f'<div style="position:absolute; width:100%; text-align:center; top:8px;'
            f' text-indent:8px">{icon(name, size, t["shadow"])}</div>'
            f'<div style="position:absolute; width:100%; text-align:center; top:0">'
            f'{icon(name, size, t["pixel_fill"] if t["name"]=="Option B" else t["accent"])}</div></div>')


def _shell(t: dict, assets: str, fonts: str, body: str, tag: str,
           source: str = "") -> str:
    src_html = f'<div class="src">{source}</div>' if source else ""
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<style>{_css(t, assets, fonts)}</style></head><body>
<div class="logo"><img src="{assets}/{t.get('logo','logo_big.png')}"></div>
<div class="tag"><span class="tagin"><span class="tagsh"></span><span class="tagf">{tag}</span></span></div>
{body}{src_html}
<div class="footer">MUKHTSAR.COM</div>
<div class="checker"></div>
</body></html>"""


# ---------------------------------------------------------------- cover
def cover(t, assets, fonts, *, eyebrow, pixel, headline, highlight,
          subline, tag, with_image, icon_name=None, source=""):
    win = '<div class="photowin"></div>' if with_image else ""
    top = 715 if with_image else 250
    ico = "" if with_image or not icon_name else \
        f'<div style="margin-top:32px">{_layered_icon(icon_name, 92, t)}</div>'
    psize, pheight = (104, 138) if with_image else (130, 175)
    hsize = 62 if with_image else 68
    body = f"""{win}
<div style="position:absolute; top:{top}px; left:0; width:100%; text-align:center; padding:0 80px">
  <div class="eyebrow">{eyebrow}</div>
  {ico}
  <div style="margin-top:20px">{_pixel(pixel, psize, pheight)}</div>
  <div style="font-weight:900; font-size:{hsize}px; line-height:1.34; margin-top:8px">
    {headline}<br><span style="color:{t['accent']}">{highlight}</span></div>
  {_dots(4)}
  <div style="font-weight:600; font-size:30px; color:{t['text_muted']}; line-height:1.68">{subline}</div>
</div>
<div style="position:absolute; bottom:{104 if with_image else 150}px; left:60px">
  {icon('arrow', 50, t['accent'])}</div>"""
    return _shell(t, assets, fonts, body, tag, source)


# ---------------------------------------------------------------- item
def item(t, assets, fonts, *, index, total, icon_name, title, subtitle,
         body_html, tip, tag, with_image, eyebrow=None, source=""):
    if with_image:
        chip = (f'<span style="display:inline-block; background:'
                f'{t["card_bg"] if t["name"]=="Option A" else t["tag_bg"]};'
                f' border:2px solid {t["frame_border"]}; border-radius:50px;'
                f' padding:8px 26px; font-weight:700; font-size:26px;'
                f' color:{t["footer"] if t["name"]=="Option A" else t["tag_text"]}">'
                f'{index} / {total}</span>')
        tip_html = ("" if not tip else
                    f'<div style="margin-top:22px; font-weight:700; font-size:28px;'
                    f' color:{t["accent_2"]}; line-height:1.65">'
                    f'{icon("bulb", 29, t["accent_2"])} نصيحة مختصر: {tip}</div>')
        body = f"""<div class="photowin"></div>
<div style="position:absolute; top:715px; left:0; width:100%; padding:0 70px; text-align:right">
  <div style="display:table; width:100%">
    <div style="display:table-cell; vertical-align:middle">
      <div style="font-weight:900; font-size:54px; color:{t['text']}">
        {icon(icon_name, 46, t['accent'])} {title}</div>
      <div style="font-weight:700; font-size:27px; color:{t['accent_2']}; margin-top:4px">{subtitle}</div>
    </div>
    <div style="display:table-cell; vertical-align:middle; width:150px; text-align:left">{chip}</div>
  </div>
  {_dots(3)}
  <div style="font-weight:700; font-size:32px; color:{t['text_body']}; line-height:1.85">{body_html}</div>
  {tip_html}
</div>"""
    else:
        eb = eyebrow or f"{index} OF {total}"
        tip_html = ("" if not tip else f"""
  <div style="position:relative; margin:34px 40px 0 40px">
    <div style="position:absolute; top:9px; right:-9px; width:100%; height:100%;
         background:{t['shadow']}; border-radius:18px"></div>
    <div style="position:relative; background:{t['card_bg']};
         border:2px solid {t['accent_2']}; border-radius:18px; padding:24px 26px">
      <div style="font-weight:700; font-size:29px; color:{t['accent_2']}; line-height:1.6">
        {icon('check', 30, t['accent_2'])} {tip}</div>
    </div>
  </div>""")
        body = f"""
<div style="position:absolute; top:244px; left:0; width:100%; padding:0 80px; text-align:center">
  <div class="eyebrow">{eb}</div>
  <div style="margin-top:30px">{_layered_icon(icon_name, 84, t)}</div>
  <div style="margin-top:14px">{_pixel(f'{index:02d}', 118, 156)}</div>
  <div style="font-weight:900; font-size:56px; line-height:1.42; margin-top:8px">{title}</div>
  <div style="font-weight:700; font-size:27px; color:{t['accent_2']}; margin-top:4px">{subtitle}</div>
  {_dots(3)}
  <div style="font-weight:700; font-size:33px; color:{t['text_body']}; line-height:1.85">{body_html}</div>
  {tip_html}
</div>"""
    return _shell(t, assets, fonts, body, tag, source)


# ---------------------------------------------------------------- checklist
def checklist(t, assets, fonts, *, eyebrow, title, lines, tag, source=""):
    rows = ""
    for ln in lines:
        rows += (f'<div style="display:table; width:100%; margin-bottom:22px; text-align:right">'
                 f'<div style="display:table-cell; vertical-align:middle; width:54px">'
                 f'{icon("check", 38, t["accent"])}</div>'
                 f'<div style="display:table-cell; vertical-align:middle; padding-right:18px;'
                 f' font-weight:700; font-size:32px; color:{t["text_body"]}; line-height:1.55">{ln}</div>'
                 f'</div>')
    body = f"""
<div style="position:absolute; top:250px; left:0; width:100%; padding:0 80px; text-align:center">
  <div class="eyebrow">{eyebrow}</div>
  <div style="font-weight:900; font-size:60px; line-height:1.4; margin-top:26px">{title}</div>
  {_dots(3)}
  <div style="margin-top:14px">{rows}</div>
</div>"""
    return _shell(t, assets, fonts, body, tag, source)


# ---------------------------------------------------------------- cta
def cta(t, assets, fonts, *, eyebrow, icon_name, headline, highlight,
        body_text, button, save_line, tag):
    body = f"""
<div style="position:absolute; top:250px; left:0; width:100%; text-align:center; padding:0 90px">
  <div class="eyebrow">{eyebrow}</div>
  <div style="margin-top:34px">{_layered_icon(icon_name, 104, t)}</div>
  <div style="font-weight:900; font-size:62px; line-height:1.38; margin-top:26px">
    {headline}<br><span style="color:{t['accent']}">{highlight}</span></div>
  {_dots(4)}
  <div style="font-weight:700; font-size:33px; color:{t['text_body']}; line-height:1.9;
       margin-bottom:40px">{body_text}</div>
  <div style="position:relative; margin:0 70px">
    <div style="position:absolute; top:12px; right:-12px; width:100%; height:100%;
         background:{t['cta_shadow']}; border-radius:22px"></div>
    <div style="position:relative; background:{t['cta_bg']}; border-radius:22px; padding:34px 30px">
      <div style="font-weight:900; font-size:46px; color:{t['cta_text']}">
        {icon('whatsapp', 44, t['cta_text'])} {button}</div>
      <div style="font-weight:800; font-size:32px; color:{t['cta_sub']}; margin-top:8px">
        عبر الرابط في البايو</div>
    </div>
  </div>
  <div style="font-weight:700; font-size:29px; color:{t['accent_2']}; margin-top:28px">{save_line}</div>
</div>"""
    return _shell(t, assets, fonts, body, tag)


LAYOUTS = {"cover": cover, "item": item, "checklist": checklist, "cta": cta}
