# Notyga — showcase website

Static redesign of [notyga.fr](https://notyga.fr). Plain HTML, CSS and a small
amount of vanilla JavaScript: **no build step, no dependencies, no runtime.**
Copy the folder onto any web host and it works.

```
.
├── index.html            English homepage      ─┐
├── fr/index.html         French homepage        │ production build,
├── 404.html              Not-found page         │ committed, deploy as-is
├── robots.txt                                   │
├── sitemap.xml                                 ─┘
├── .github/workflows/
│   └── pages.yml         Builds + deploys the GitHub Pages review copy
├── assets/
│   ├── css/styles.css    The whole design system + page styles
│   ├── js/main.js        Progressive enhancement only
│   └── img/              Logo variants, founder portrait, favicons
└── tools/                Optional authoring scripts (not deployed)
    ├── build_pages.py    Regenerates the HTML from one copy deck
    ├── build_assets.py   Regenerates the logo/image assets (needs Pillow)
    └── source/           Original full-resolution logo and portrait
```

`tools/` is for authoring only. You can upload it with the rest — nothing links
to it — or leave it out of the deploy; the site does not use it at runtime.

## Viewing it locally

```bash
python -m http.server 8000
# then open http://localhost:8000
```

Opening `index.html` directly with `file://` mostly works, but the root-relative
language links (`/` and `/fr/`) only resolve over HTTP.

## Deploying

There are two build targets, defined at the top of `tools/build_pages.py`:

| Target | Served from | Indexable | Used for |
| --- | --- | --- | --- |
| `production` (default) | `https://notyga.fr/` | yes | the real site |
| `github` | `https://hadjurh.github.io/notyga/` | **no** | private review copy |

They differ only in the base path and the search-engine directives. Asset URLs
are relative, so they work unchanged at any mount point.

### Production — notyga.fr

The committed HTML at the repository root *is* the production build. Upload the
contents to the web root; nothing needs compiling.

- **Netlify / Vercel / Cloudflare Pages** — drag the folder in, or connect the
  repo with no build command and the project root as the publish directory.
- **OVH / classic shared hosting / FTP** — upload everything into `www/`.

`404.html` is picked up automatically by Netlify and Cloudflare Pages. On
Apache, add `ErrorDocument 404 /404.html` to `.htaccess`.

### Review copy — GitHub Pages

A project page lives under a subpath, so the root-relative language links have
to be rebuilt for `/notyga/`. `.github/workflows/pages.yml` does this on every
push to `main` and deploys the result, so nothing extra is committed.

One-time setup:

1. Create a repository named **`notyga`** under your account and push this
   folder to `main`. The repository name must match the `base` in the `github`
   target, or the links will point at the wrong subpath.
2. **Settings → Pages → Source: GitHub Actions.**
3. Push. The workflow builds, checks that no link escapes `/notyga/`, and
   publishes to `https://hadjurh.github.io/notyga/`.

To produce that variant locally:

```bash
python tools/build_pages.py --target github --out _site
```

Deploying somewhere else, or renaming the repo, means editing `base` and
`origin` in the `github` target — that one place is all that needs to change.

## A word on the review copy and privacy

**GitHub Pages cannot password-protect a site.** A public repository serves a
public site, and serving Pages only to repository collaborators is a GitHub
Enterprise Cloud feature — not available on Free, Pro or Team. There is no
server in front of it, so no Basic Auth and no `.htaccess`.

What the `github` target does instead is keep the copy *unlisted*:

- `<meta name="robots" content="noindex, nofollow">` on every page
- `robots.txt` with `Disallow: /`
- no `canonical` or `hreflang` tags, which would otherwise invite indexing of
  the wrong host and let the preview compete with notyga.fr in search results

That keeps it out of search engines. It does **not** keep out anyone who has, or
guesses, the URL. Treat the link as semi-public: fine for showing colleagues a
draft, not a place for anything confidential.

If you later need real authentication, **Cloudflare Pages + Cloudflare Access**
is free for up to 50 users and gates the site at the edge, so unauthenticated
visitors never receive the HTML at all. The site itself needs no changes — only
a target with `base: "/"` and the new origin.

## Editing the content

`index.html` and `fr/index.html` are ordinary HTML and can be edited by hand.

They are, however, **generated from a single copy deck** so the two languages
cannot drift apart structurally. The recommended flow is:

1. Edit the `COPY` dictionary in `tools/build_pages.py`.
2. Run `python tools/build_pages.py`.
3. Commit the regenerated HTML.

The GitHub Pages copy rebuilds itself from the same deck on push, so a copy
change only ever needs making once.

Only the Python standard library is needed. If you would rather not keep the
generator, delete `tools/` — the site is fully self-contained without it.

### Where the words came from

Every heading and paragraph carried over from the old site is reproduced
**verbatim** and marked `# verbatim` in the copy deck. The text added for this
redesign is structural only — navigation labels, section eyebrows, the
"From question to decision" method section, the discipline chips and CTA
microcopy. No client names, figures, metrics, testimonials or case studies were
invented; if you want those on the page, they need to come from you.

## Design notes

- **Palette.** One hue family, sampled from the logo file (`#006401`), plus warm
  neutrals. Tokens live at the top of `styles.css`. No second brand colour is
  introduced anywhere.
- **Logo.** Unchanged. The originals were flat JPEGs on white; `build_assets.py`
  keys out the white to produce transparent PNGs in three lockups (mark,
  wordmark, full) and a reversed white set for the dark sections.
- **Type.** Inter for everything, JetBrains Mono for the small uppercase labels,
  both from Google Fonts. To self-host instead, drop the woff2 files in
  `assets/fonts/`, replace the `<link>` in `tools/build_pages.py` with
  `@font-face` rules, and rebuild.
- **Motion.** Scroll reveals, the sticky header state and the domain marquee are
  all progressive enhancement — with JavaScript disabled the page still renders
  and reads completely. Everything is disabled under
  `prefers-reduced-motion: reduce`.

## Accessibility

Skip link, landmark elements, visible focus rings, labelled nav toggle with
`aria-expanded`, `aria-current` on the active section and language, alt text on
meaningful images and `alt=""` on decorative ones. Every text pairing in the
palette meets WCAG AA (lowest is 4.94:1); the decorative card numbers sit at
~3:1 and are `aria-hidden`.

## Still to do

- **Legal pages.** A French company site must publish *mentions légales* and a
  privacy policy. There is a `TODO` comment in the footer markup marking where
  they go. These need real company details — SIREN, registered address,
  publication director, hosting provider — so they were deliberately not
  invented here.
- **Social links.** No LinkedIn or other profile was present on the old site;
  add them to the footer when you have the URLs.
- **Open Graph image.** Currently the logo. A purpose-made 1200×630 card would
  preview better when the site is shared.
