# Mukhtsar Carousel Pipeline

Automated Instagram carousel production and publishing for **@mukhtsar_study**.

Four design paths, one codebase:

| Path | Theme | Photos |
|------|-------|--------|
| `A` | Option A — dark navy, gold accents, red offset | no |
| `A-img` | Option A | yes (Pexels, automatic) |
| `B` | Option B — cream, navy text, teal accents, gold offset | no |
| `B-img` | Option B | yes (Pexels, automatic) |

---

## Install (Windows)

```powershell
cd C:\Users\Mzx\mukhtsar-study
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m tools.setup_assets
copy .env.example .env        # then fill it in
```

WeasyPrint needs GTK on Windows. If `import weasyprint` fails, install the
GTK3 runtime: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer

PNG rasterising uses **PyMuPDF**, not poppler — nothing else to install.

### Logo
Both wordmark variants are generated from Orbitron — no external asset needed:

```powershell
python -m tools.make_logo
```

`assets/logo_big.png` (gold, dark themes) and `assets/logo_big_light.png`
(navy + gold offset, Option B). The theme picks the right one automatically.
The original hand-keyed wordmark is kept as `assets/logo_big_original.png`.

### Legacy logo
Place your transparent pixel wordmark at `assets/logo_big.png`
(~1240px wide). Or extract it from an existing asset:

```powershell
python -m tools.setup_assets path\to\image_with_logo.png
```

---

## Daily use

Guided build — walks you through topic, design and photos, and warns if the
topic was already published or built:

```powershell
python -m src.run new
```

Or drive it directly:

```powershell
python -m src.run status                      # queue + quota
python -m src.run build --topic housing       # build one topic
python -m src.run build --topic dishes --path B-img   # override the path
python -m src.run build --next                # build whatever is next in the queue
python -m src.run publish --id 2026-09-14-housing --dry-run
python -m src.run publish --id 2026-09-14-housing
python -m src.run auto                        # build + QA + publish  (what cron runs)
```

Rendered slides land in `out/<date>-<topic>/` with `caption.txt`,
`meta.json` and — for image paths — `credits.json`.

---

## Adding a topic

Append to `content/topics.yaml`. Minimum shape:

```yaml
  - id: my-topic
    path: B-img                 # or omit to use the rotation
    tag: "دليل"
    hook: "الجملة الأولى في الكابشن"
    hashtags: ["الدراسة_في_ماليزيا", "مختصر"]
    cover:
      eyebrow: "SOMETHING IN CAPS"
      pixel: "5"
      headline: "السطر الأول"
      highlight: "السطر الثاني بالذهبي"
      subline: "سطرين توضيح<br>تحت العنوان"
      keywords: ["search term", "another term"]      # *-img paths only
    items:
      - icon: university                              # see config/icons.py
        title: "عنوان الشريحة"
        subtitle: "سطر صغير"
        body: "النص مع <span class='hl'>تمييز ذهبي</span>"
        tip: "نصيحة مختصر: ..."
        keywords: ["slide search term"]
    checklist:                                        # optional
      eyebrow: "BEFORE YOU..."
      title: "عنوان القائمة"
      lines: ["بند", "بند آخر"]
    cta:
      eyebrow: "CALL TO ACTION"
      icon: shield
      headline: "السطر الأول"
      highlight: "السطر الثاني"
      body: "شرح قصير<br>سطرين"
      button: "تواصل معنا على واتساب"
      save: "احفظ المنشور — وأرسله لمن يهمه"
```

Carousel length = 1 cover + N items + optional checklist + 1 CTA.
Keep the total between 3 and 10 (Instagram's limit).

---

## QA gate

Nothing publishes unless every check passes:

- Slide count 3–10, each exactly 1080×1350, under 8MB
- No unfilled photo window (magenta bleed)
- Content clears the footer band by ≥40px
- **No phone number** anywhere in slides or caption — CTAs use the bio link
- Caption ≤2,200 chars, ≤30 hashtags
- Photo frame border intact after compositing

Run a build locally and read the QA block before trusting a new topic.

---

## Images

`src/images.py` queries Pexels per slide keyword list, scores candidates on
resolution and how well they fit the 952×512 window, rejects portrait or
low-resolution results, skips anything whose metadata suggests swimwear,
alcohol or other content wrong for a Gulf family audience, and never reuses a
photo inside the same carousel. Photographer and source URL are written to
`credits.json`.

Pexels content is free for commercial use with no attribution required.
**Do not** swap in Google Images results — that is how watermarked and
mislabelled photos get published.

---

## Publishing

Instagram fetches images from a **public URL** — it cannot accept uploads.
`IMAGE_BASE_URL` must point at wherever `out/` is served from. With GitHub
that is:

```
https://raw.githubusercontent.com/<user>/mukhtsar-study/main/out
```

Requirements on the Meta side:
- @mukhtsar_study is a **Professional** account
- linked to a **Facebook Page**
- a Meta app with `instagram_basic`, `instagram_content_publish`,
  `pages_read_engagement`
- **Page Publishing Authorization** completed
- a long-lived `IG_ACCESS_TOKEN` (expires ~60 days — regenerate and update
  the secret; `python -m src.run status` shows quota and surfaces auth errors)

---

## Scheduling

`.github/workflows/publish.yml` runs Sunday / Tuesday / Thursday at 18:00 UTC
(21:00 KSA — peak for a Saudi audience; 02:00 Malaysia).

Secrets to set in the repo (Settings → Secrets → Actions):
`PEXELS_API_KEY`, `IG_USER_ID`, `IG_ACCESS_TOKEN`, `IMAGE_BASE_URL`.

Trigger a manual run from the Actions tab — it accepts a topic, a path, and a
dry-run toggle.

To run locally on Windows instead, point Task Scheduler at:

```
C:\Users\Mzx\mukhtsar-study\.venv\Scripts\python.exe -m src.run auto
```

(the machine must be awake at the scheduled time).

---

## Layout

```
config/   themes.py (A/B tokens) · layouts.py (slide templates) · icons.py · settings.yaml
content/  topics.yaml (the bank) · state.json (what's published)
assets/   fonts · logo · grid + checker tiles
src/      build · images · render · qa · publish · run
out/      rendered carousels (public — Instagram fetches from here)
tools/    setup_assets.py
```


---

## Fix log — 2026-09-14 (Linux verification run)

Verified on a clean install: 55/55 selftests pass, both text paths build and
pass QA end to end, `publish --dry-run` rehearses the full flow.

Fixed during that run:

1. **Eyebrow bidi** — item slides printed `OF 4 2` instead of `2 OF 4`.
   `.eyebrow` now carries `direction:ltr; unicode-bidi:isolate`.
2. **Counter chip bidi** — the tag chip printed `4 / 2`. Now wrapped in `.ltr`.
3. **Trailing neutral flipping** — `RM 15,000 – 50,000+` rendered as
   `+RM 15,000 – 50,000`, which reads as a leading plus and changes the meaning.
   `build.iso()` isolates Latin/number runs; applied to cover, item, checklist
   and CTA text. It is HTML-safe (skips anything between `<` and `>`).
4. **Raw tracebacks from the CLI** — `publish` and `auto` crashed with a stack
   trace when `IMAGE_BASE_URL` was unset. Dry runs now use a placeholder and
   warn; real failures print one clean line.
5. **Wordmark** — the shipped logo was hard-keyed with a dark outline baked in:
   invisible on Option A navy, dirty on Option B cream. Regenerated from
   Orbitron Black as two clean variants, selected by theme token `logo`.

6. **`.env` was never read** — every module looked its key up with
   `os.environ`, and nothing loaded the file, so a filled-in `.env` was
   silently ignored and `PEXELS_API_KEY is not set` came back anyway.
   `src/run.py` now loads it at startup (stdlib only, no new dependency).
   Real environment variables take precedence, so GitHub Actions secrets are
   never overridden by a stale local file.

7. **Guided build** — `python -m src.run new` added. Lists every topic with
   its status (published / built locally / free) and whether it has keywords
   for photos, then asks for design (A or B) and images (Y or N). Refuses to
   silently rebuild a published topic, and falls back to text-only if you ask
   for photos on a topic with no keywords.
8. **`publish` referenced before import** — the CLI error handler named
   `publish.PublishError` while the module was only imported lazily inside
   two commands, so any error from another command died with a `NameError`
   instead of its real message.

9. **People policy for sourced photos** — `config/settings.yaml` gained an
   `images.people` setting (`none` / `no_women` / `allow`, default `none`),
   and the banned-word list was widened considerably.
   What it can do: reject a photo whose Pexels description indicates a person.
   What it cannot do: judge how anyone in a photo is dressed. Pexels exposes
   only alt text and a URL slug — there is no clothing metadata to filter on,
   and a photo with blank alt text passes every text filter by default.
   `default none` is therefore the only setting that is reliable for this
   audience, because it does not depend on the description being accurate
   about clothing, only on whether a person is mentioned at all.
   Every sourced photo now prints its description during the build and is
   recorded in `credits.json`; any photo with no description is flagged
   `needs_review: true`. Those must be looked at before publishing.

Still untested: the `-img` paths against the live Pexels API (selftest covers
them with a stub), publishing against the live Graph API, and Windows.
