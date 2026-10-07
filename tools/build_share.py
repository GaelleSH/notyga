# -*- coding: utf-8 -*-
"""Make standalone copies of a generated page, for sharing outside the site.

Writes into _share/ (git-ignored) a single HTML file with the stylesheet,
fonts, logos and script embedded, plus a PDF printed by Edge or Chrome when
one is installed. Links to other pages point at the live site.

    python tools/build_pages.py        # regenerate the site first
    python tools/build_share.py        # default: the French legal page
    python tools/build_share.py legal/index.html

For a review before the hosting is settled, --compare renders the legal page
with each host-dependent passage shown as labelled options (keys of HOSTS in
build_pages.py). The site's own pages are not touched:

    python tools/build_share.py --compare ovh_web ovh_vps
"""
import argparse
import base64
import io
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_share")
ORIGIN = "https://www.notyga.com"

PAGES = {
    "fr/mentions-legales/index.html": "notyga-mentions-legales",
    "legal/index.html": "notyga-legal-notice",
}

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def data_uri(relpath, mime):
    with open(os.path.join(ROOT, relpath), "rb") as fh:
        return f"data:{mime};base64," + base64.b64encode(fh.read()).decode()


def read(relpath):
    with io.open(os.path.join(ROOT, relpath), encoding="utf-8") as fh:
        return fh.read()


def sub(pattern, repl, text):
    """re.sub that fails loudly if the page no longer matches."""
    text, n = re.subn(pattern, repl, text)
    if not n:
        sys.exit(f"build_share: pattern not found, update the script: {pattern}")
    return text


def standalone(page, html=None):
    html = html if html is not None else read(page)
    css = re.sub(r'url\("\.\./fonts/([^"]+)"\)',
                 lambda m: f'url("{data_uri("assets/fonts/" + m.group(1), "font/woff2")}")',
                 read("assets/css/styles.css"))
    js = read("assets/js/main.js")

    html = sub(r'  <link rel="preload" href="/assets/fonts/[^"]+"[^>]*>\n', "", html)
    html = sub(r'<link rel="stylesheet" href="/assets/css/styles.css">',
               lambda m: "<style>\n" + css + "\n</style>", html)
    html = sub(r'<script src="/assets/js/main.js" defer></script>',
               lambda m: "<script>\n" + js + "\n</script>", html)
    html = re.sub(r'  <link rel="(icon|apple-touch-icon)" href="/assets/img/'
                  r'(favicon-512|apple-touch-icon)\.png"[^>]*>\n', "", html)
    html = sub(r'href="/assets/img/favicon-32.png"',
               f'href="{data_uri("assets/img/favicon-32.png", "image/png")}"', html)
    for svg in ("logo.svg", "logo-white.svg"):
        html = sub(rf'src="/assets/img/{svg}"',
                   f'src="{data_uri("assets/img/" + svg, "image/svg+xml")}"', html)

    # The page's own address stays in the file; every other page is the live one.
    self_path = "/" + page[:-len("index.html")]
    html = html.replace(f'href="{self_path}"', 'href="#main"')
    html = re.sub(r'(href|src)="/(?!/)', rf'\1="{ORIGIN}/', html)

    if re.search(r'(href|src)="/(?!/)', html):
        sys.exit("build_share: a root-relative URL survived; it would break offline")
    return html


def print_pdf(html_path, pdf_path):
    browser = next((b for b in BROWSERS if os.path.exists(b)), None) \
        or shutil.which("msedge") or shutil.which("google-chrome") or shutil.which("chromium")
    if not browser:
        print("  (no Edge/Chrome found: PDF skipped)")
        return
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
    url = "file:///" + html_path.replace(os.sep, "/").lstrip("/")
    profile = os.path.join(OUT, ".browser-profile")
    subprocess.run([browser, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}",
                    "--no-pdf-header-footer", "--print-to-pdf-no-header",
                    f"--print-to-pdf={pdf_path}", url],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    shutil.rmtree(profile, ignore_errors=True)
    if not os.path.exists(pdf_path):
        print("  (PDF printing failed)")


def compared_legal_page(page, host_keys):
    """The legal page rendered in memory with several hosts side by side."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import build_pages as bp
    unknown = [k for k in host_keys if k not in bp.HOSTS]
    if unknown:
        sys.exit(f"build_share: unknown host {unknown}; choose from {sorted(bp.HOSTS)}")
    en, fr = bp.resolve("en", "production"), bp.resolve("fr", "production")
    this, other = (fr, en) if page.startswith("fr/") else (en, fr)
    if page != this["legal_dir"] + "index.html":
        sys.exit("build_share: --compare only applies to the legal pages")
    # The log retention on our own server is still to be decided: leave it open.
    hosts = [dict(bp.HOSTS[k], log_days=None) if "log_days" in bp.HOSTS[k]
             else bp.HOSTS[k] for k in host_keys]
    return bp.legal_page(this, other, hosts=hosts)


def main(pages, compare=None):
    os.makedirs(OUT, exist_ok=True)
    for page in pages:
        name = PAGES.get(page) or page.strip("/").replace("/index.html", "").replace("/", "-")
        html = None
        if compare:
            html = compared_legal_page(page, compare)
            name += "-relecture" if page.startswith("fr/") else "-review"
        html_path = os.path.join(OUT, name + ".html")
        pdf_path = os.path.join(OUT, name + ".pdf")
        with io.open(html_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(standalone(page, html))
        print_pdf(html_path, pdf_path)
        for path in (html_path, pdf_path):
            if os.path.exists(path):
                print("  %-34s %5d KB" % (os.path.relpath(path, ROOT),
                                          os.path.getsize(path) // 1024))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pages", nargs="*", default=["fr/mentions-legales/index.html"],
                    help="generated pages to export (default: the French legal page)")
    ap.add_argument("--compare", nargs="+", metavar="HOST",
                    help="legal page only: show these HOSTS side by side, for review")
    args = ap.parse_args()
    main(args.pages, args.compare)
