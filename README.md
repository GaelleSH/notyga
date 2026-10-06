# Notyga — showcase website

Static redesign of [notyga.fr](https://notyga.fr). Plain HTML, CSS and a small
amount of vanilla JavaScript: **no build step, no dependencies, no runtime.**
Copy the folder onto any web host and it works.

```
.
├── index.html                   English homepage     ─┐
├── fr/index.html                French homepage       │
├── legal/index.html             Legal notice (EN)     │ production build,
├── fr/mentions-legales/…        Mentions légales (FR) │ generated, committed
├── 404.html                     Not-found page        │
├── robots.txt                                         │
├── sitemap.xml                                       ─┘
├── CNAME                        Custom domain for GitHub Pages
├── .github/workflows/
│   └── pages.yml                Builds + deploys notyga.fr on every push
├── assets/
│   ├── css/styles.css           The whole design system + page styles
│   ├── js/main.js               Progressive enhancement only
│   ├── fonts/                   Self-hosted Inter + JetBrains Mono (OFL)
│   └── img/                     Logo variants, founder portrait, favicons
└── tools/                       Authoring scripts (not deployed)
    ├── build_pages.py           Regenerates the HTML from one copy deck
    ├── build_share.py           Exports a page as standalone HTML + PDF (_share/)
    ├── build_assets.py          Regenerates the logo/image assets (needs Pillow)
    └── source/                  Original full-resolution logo and portrait
```

`tools/` is for authoring only; the site does not use it at runtime.

## Viewing it locally

```bash
python -m http.server 8000
# then open http://localhost:8000
```

Opening `index.html` directly with `file://` mostly works, but the root-relative
links (`/`, `/fr/`, `/legal/`) only resolve over HTTP. `http.server` does not
serve `404.html` for missing pages; open `/404.html` to look at it.

## Deploying

**notyga.fr is served by GitHub Pages.** `.github/workflows/pages.yml` runs on
every push to `main`: it rebuilds the `production` target into `_site/`, copies
`CNAME`, fails if any link still points at the old `/notyga/` subpath, and
deploys. Nothing else to do — push and wait a minute.

One-time settings, already done:

- **Settings → Pages → Source: GitHub Actions.**
- **Settings → Pages → Custom domain: `notyga.fr`.** With an Actions deploy,
  GitHub takes the domain from this setting, not from the `CNAME` file. If the
  site ever stops answering on notyga.fr, remove the domain there, save, put it
  back and save again.

Because the site is served from the root of the domain, every page links with
paths rooted at `/`. The 404 and legal pages also load their assets from
`/assets/…`, since they can be served at any depth.

### Build targets

`tools/build_pages.py` defines two targets:

| Target | Served from | Indexable | Used for |
| --- | --- | --- | --- |
| `production` (default) | `https://notyga.fr/` | yes | the real site |
| `github` | `https://hadjurh.github.io/notyga/` | **no** | old review copy, unused |

The `github` target adds `noindex`, a disallow-all `robots.txt` and the
`/notyga/` base path. It is no longer deployed; keep it only if you want a
private preview elsewhere (`python tools/build_pages.py --target github --out _site`).

### Moving from GitHub Pages to an OVH VPS

The site is planned to move to an OVH VPS, with data hosted in Europe. A VPS
is a bare Linux server: unlike GitHub Pages, the web server, HTTPS certificate,
updates and security are ours to run. The commands below assume Debian or
Ubuntu, Nginx and Let's Encrypt (certbot).

Steps 1–5 can be done in advance without affecting the live site; steps 6–8
are the switch.

**1. Legal page.** In `tools/build_pages.py`:

- set `HOST = HOSTS["ovh_vps"]`, and check its details (company, address,
  phone) against the OVH contract. The VPS variant says the logs are written
  by our own server on a machine rented from OVH, and deleted after
  `log_days` (14) days: keep that number in line with the log rotation set in
  step 3. (`HOSTS["ovh_web"]` is the shared-hosting variant, kept for
  comparison);
- bump `LEGAL_UPDATED`, then run `python tools/build_pages.py`.

Do not push this to `main` before the switch: GitHub Pages would then serve a
page naming OVH as the host. Keep it on a branch, or commit it on switch day.

**2. Secure the server.** Once, logged in as root or a sudo user:

```bash
apt update && apt upgrade -y
apt install -y nginx certbot python3-certbot-nginx ufw unattended-upgrades rsync
dpkg-reconfigure -plow unattended-upgrades        # automatic security updates
ufw allow OpenSSH && ufw allow 'Nginx Full' && ufw enable
```

Then in `/etc/ssh/sshd_config`: `PasswordAuthentication no` and
`PermitRootLogin prohibit-password` (log in with SSH keys only), and
`systemctl reload ssh`. Check you can still log in with your key from a second
terminal before closing the first one.

Create the folder the site is served from, and an account that can only
deploy into it:

```bash
adduser --disabled-password --gecos "" deploy
mkdir -p /var/www/notyga && chown deploy:deploy /var/www/notyga
# paste the deploy public key into /home/deploy/.ssh/authorized_keys
```

**3. Nginx, HTTP only for now.** The certificate can only be issued once the
DNS points at the VPS (step 6), so start without HTTPS. Create
`/etc/nginx/sites-available/notyga`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name notyga.fr www.notyga.fr;

    root /var/www/notyga;
    index index.html;
    error_page 404 /404.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/notyga /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

Access logs (`/var/log/nginx/access.log`) hold visitors' IP addresses. On
Debian/Ubuntu, logrotate keeps them 14 days by default
(`/etc/logrotate.d/nginx`, `rotate 14`): well within what the legal page says.

**4. Deploy the files.** Build the site into `_site/`, which contains exactly
what the server needs (pages, `robots.txt`, `sitemap.xml`, `assets/`) and
nothing else:

```bash
python tools/build_pages.py --out _site
rsync -az --delete _site/ deploy@<VPS-IP>:/var/www/notyga/
```

On Windows without `rsync`, upload the contents of `_site/` with WinSCP
(SFTP, `deploy` account), deleting what is no longer in `_site/`.

To deploy on every push instead, replace `.github/workflows/pages.yml` with a
workflow that builds `_site/` the same way and ends with:

```yaml
      - name: Upload to the VPS
        env:
          SSH_KEY: ${{ secrets.VPS_SSH_KEY }}           # deploy's private key
          KNOWN_HOSTS: ${{ secrets.VPS_KNOWN_HOSTS }}   # output of ssh-keyscan <VPS-IP>
          HOST: ${{ secrets.VPS_HOST }}
        run: |
          mkdir -p ~/.ssh
          echo "$SSH_KEY" > ~/.ssh/id_ed25519 && chmod 600 ~/.ssh/id_ed25519
          echo "$KNOWN_HOSTS" >> ~/.ssh/known_hosts
          rsync -az --delete _site/ "deploy@$HOST:/var/www/notyga/"
```

The three values go in Settings → Secrets and variables → Actions. Drop the
`cp CNAME _site/` line from the build step: it only matters to GitHub Pages.

**5. Test before switching.** Add `<VPS-IP> notyga.fr` to your own `hosts`
file (`C:\Windows\System32\drivers\etc\hosts`, as administrator), then open
`http://notyga.fr`. Check `/`, `/fr/`, `/legal/`, `/fr/mentions-legales/` and
a missing page (the 404 must be styled). Remove the line afterwards.

**6. DNS.** Where `notyga.fr` is registered, replace the GitHub Pages records
(`A` 185.199.108.153 to 185.199.111.153, `AAAA` 2606:50c0:8000::153 to
…8003::153, and `www` CNAME → `*.github.io`) with an `A` record (and `AAAA` if
the VPS has IPv6) pointing at the VPS, for both `notyga.fr` and `www`.
Changes can take a few hours to reach everyone.

**7. HTTPS.** Once `notyga.fr` resolves to the VPS:

```bash
certbot certonly --nginx -d notyga.fr -d www.notyga.fr
```

Then replace `/etc/nginx/sites-available/notyga` with the final version: one
canonical address (`https://notyga.fr`, no `www`), security headers, caching.

```nginx
# http:// and www → https://notyga.fr
server {
    listen 80;
    listen [::]:80;
    server_name notyga.fr www.notyga.fr;
    return 301 https://notyga.fr$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name www.notyga.fr;
    ssl_certificate     /etc/letsencrypt/live/notyga.fr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/notyga.fr/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    return 301 https://notyga.fr$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name notyga.fr;
    ssl_certificate     /etc/letsencrypt/live/notyga.fr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/notyga.fr/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;

    root /var/www/notyga;
    index index.html;
    error_page 404 /404.html;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    location / {
        try_files $uri $uri/ =404;
    }

    # Static assets: let browsers cache them for a week. `expires` rather
    # than add_header, so the security headers above still apply here.
    location ~* \.(css|js|woff2|png|jpg|svg)$ {
        expires 7d;
    }
}
```

```bash
nginx -t && systemctl reload nginx
```

Certbot renews the certificate automatically (`systemctl list-timers` shows
`certbot.timer`). `Strict-Transport-Security` tells browsers to use HTTPS only,
for a year: add it once HTTPS works, not before.

**8. Switch GitHub Pages off.** Once notyga.fr answers from the VPS: in
GitHub, Settings → Pages, remove the custom domain and unpublish; delete or
replace `.github/workflows/pages.yml` (otherwise every push still deploys
there); delete `CNAME`. Then update the "Deploying" section of this README.

From then on, keeping the server up to date is on us: security updates are
automatic (step 2), but check from time to time that the VPS is running, that
the certificate renews, and plan major OS upgrades. The site itself needs no
backup beyond this repository; keep a copy of the Nginx config here or
elsewhere.

### Other hosts

The committed HTML at the repository root is the production build, so the
folder also works as-is on Netlify, Vercel or Cloudflare Pages (no build
command, project root as publish directory), which pick up `404.html`
automatically. Whatever the host, add it to `HOSTS` in `build_pages.py` and
select it: the legal page must always name the host actually serving the site.

## Editing the content

`index.html` and `fr/index.html` are ordinary HTML and can be edited by hand.

They are, however, **generated from a single copy deck** so the two languages
cannot drift apart structurally. The recommended flow is:

1. Edit the `COPY` dictionary in `tools/build_pages.py`.
2. Run `python tools/build_pages.py`.
3. Commit the regenerated HTML.

The deploy workflow rebuilds from the same deck on push, so forgetting to
commit the regenerated HTML does not break the live site — but keep them in
sync anyway, the committed HTML is what other hosts would serve.

### Legal page

The legal notice and privacy policy (`/legal/`, `/fr/mentions-legales/`) are
generated from the `LEGAL` dictionary and the selected `HOST` (one of
`HOSTS`) near the top of `tools/build_pages.py`. Any field left at `None` shows on the page as a
highlighted *"À compléter"* placeholder, and the build prints a warning listing
them. Bump `LEGAL_UPDATED` whenever the content changes.

To send the page to someone outside the site (for a legal review, say), run
`python tools/build_share.py`: it writes a standalone HTML file and a PDF of
the French legal page into `_share/` (`python tools/build_share.py
legal/index.html` for the English one).

While the hosting is not settled, `python tools/build_share.py --compare
ovh_web ovh_vps` writes a review copy (`…-relecture.html/.pdf`) where every
passage that depends on the host is shown as labelled options A and B, under a
banner saying only one will be published. It is rendered in memory: the site's
own pages are not touched.

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
- **Logo.** Used whole, as supplied. `assets/img/logo.svg` (green) and
  `logo-white.svg` (reversed, for the footer) are the vector paths extracted
  from `assets/img/Logo Notyga V2.pdf`. The header and footer both show the
  full lockup (motif + wordmark + tagline); it is never split into parts.
  `logo-full.png` is kept only as the raster Open Graph / JSON-LD image.
- **Type.** Inter for everything, JetBrains Mono for the small uppercase labels.
  Both are self-hosted variable fonts in `assets/fonts/` (latin + latin-ext
  subsets, SIL Open Font License, licences alongside), declared at the top of
  `styles.css`. Nothing is loaded from Google, so visitors' IP addresses are not
  sent to a third party and the site needs no cookie or consent banner.
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

- **Move to the OVH VPS.** See "Moving from GitHub Pages to an OVH VPS" above.
- **Legal review.** The legal page follows the structure of Saryga's, corrected
  per the September 2026 site audit (publisher = Saryga, named publication
  director, full privacy policy). Company data comes from the public register
  and the Kbis. Worth a read by counsel before it is relied on.
- **Social links.** No LinkedIn or other profile was present on the old site;
  add them to the footer when you have the URLs.
- **Open Graph image.** Currently the logo. A purpose-made 1200×630 card would
  preview better when the site is shared.
