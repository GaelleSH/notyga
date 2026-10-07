# -*- coding: utf-8 -*-
"""Generate the Notyga static pages from a single copy deck.

The site ships as plain HTML and needs no build step to deploy. This script
exists only so the English and French pages cannot drift apart structurally:
edit the COPY dict below, re-run `python tools/build_pages.py`, commit the
generated HTML.

Text taken from the previous notyga.fr is marked "verbatim" and must not be
reworded here.
"""
import argparse
import io
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Iconography: 24px line icons, inheriting colour from the card.
# ---------------------------------------------------------------------------

ICONS = {
    # folded map — geospatial
    "geo": '<path d="M9 3 3 5.5v15L9 18l6 3 6-2.5v-15L15 6 9 3Z"/><path d="M9 3v15M15 6v15"/>',
    # compass — destinations, visitors
    "tourism": '<circle cx="12" cy="12" r="9"/><path d="m15.6 8.4-2.1 5.1-5.1 2.1 2.1-5.1 5.1-2.1Z"/>',
    # routed path between two nodes — flows
    "mobility": '<circle cx="6" cy="18.5" r="2.5"/><circle cx="18" cy="5.5" r="2.5"/>'
                '<path d="M15.5 5.5H10a3.5 3.5 0 0 0 0 7h4a3.5 3.5 0 0 1 0 7H8.5"/>',
    # activity trace — training load
    "sport": '<path d="M3 12h3.5l2.5-7 4.5 14 2.5-7H21"/>',
    # chart panel — dashboards
    "dataviz": '<rect x="3" y="4.5" width="18" height="15" rx="2.5"/>'
               '<path d="M8 15.5v-3.5M12 15.5v-6.5M16 15.5v-2.5"/>',
    # shield with a flagged signal — anomalies
    "fraud": '<path d="M12 3 4.5 6v6c0 4.2 3.1 7.7 7.5 9 4.4-1.3 7.5-4.8 7.5-9V6L12 3Z"/>'
             '<path d="M12 8.5v4"/><circle cx="12" cy="15.6" r=".7" fill="currentColor" stroke="none"/>',
    # concentric target — segmentation, catchment areas
    "market": '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/>'
              '<circle cx="12" cy="12" r="1.1" fill="currentColor" stroke="none"/>',
}

ARROW = ('<svg class="arrow" width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">'
         '<path d="M2 8h11M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.6" '
         'stroke-linecap="round" stroke-linejoin="round"/></svg>')

EMAIL = "contact@notyga.com"
SITE_NAME = "notyga.com"         # how the legal page names the site

# ---------------------------------------------------------------------------
# Legal details, for the "mentions légales" (French LCEN, art. 6-III) and the
# privacy policy. Company data comes from the public company register
# (annuaire-entreprises.data.gouv.fr, SIREN 903 594 703). Fill in every None:
# until then the page shows a highlighted placeholder and the build warns.
# ---------------------------------------------------------------------------

LEGAL = {
    "company": "Saryga",
    "legal_form": {"fr": "SAS (société par actions simplifiée)",
                   "en": "SAS (simplified joint-stock company)"},
    "capital": "2 000 €",    # share capital (Kbis or statuts)
    "address": "566 chemin de la Carrière, 71700 Tournus",
    "siren": "903 594 703",
    "siret": "903 594 703 00014",
    "rcs_city": "Mâcon",     # city of the RCS registry (Kbis)
    "vat": "FR05 903 594 703",
    "phone": "09 71 16 45 62",
    "phone_intl": "+33 9 71 16 45 62",
    # A company's publication director is its legal representative.
    "director": "Gaëlle Saint-Hilary",
}

LEGAL_UPDATED = (2026, 10, 7)   # (year, month, day) shown as "last updated"

# Who processes the emails sent to contact@notyga.com (MX: Exchange Online).
MAIL_PROVIDER = "Microsoft 365"

# The legal page must name whoever actually serves the site. Switch HOST when
# the site moves, rebuild, and deploy the result to the new host.
HOSTS = {
    # GitHub Pages: GitHub runs the server and keeps its logs, in the US.
    "github": {
        "label": {"fr": "GitHub Pages", "en": "GitHub Pages"},
        "logs": "provider",
        "name": "GitHub, Inc.",
        "address": "88 Colton Street, San Francisco, CA 94107",
        "country": {"en": "United States", "fr": "États-Unis"},
        "phone": "+1 877 448 4820",
        "url": "https://github.com",
        "privacy": "https://docs.github.com/en/site-policy/privacy-policies/"
                   "github-general-privacy-statement",
    },
    # OVH shared web hosting: OVH runs the server and keeps the logs for us.
    "ovh_web": {
        "label": {"fr": "hébergement web mutualisé OVH",
                  "en": "OVH shared web hosting"},
        "logs": "hosted",
        "name": "OVH SAS",
        "address": "2 rue Kellermann, 59100 Roubaix",
        "country": {"en": "France", "fr": "France"},
        "phone": "+33 9 72 10 10 07",
        "url": "https://www.ovhcloud.com",
    },
    # OVH VPS: we run the web server ourselves on a machine rented from OVH.
    "ovh_vps": {
        "label": {"fr": "serveur privé virtuel (VPS) OVH",
                  "en": "OVH virtual private server (VPS)"},
        "logs": "vps",
        "log_days": 14,          # must match logrotate on the server (README);
                                 # None shows a highlighted "X (à décider)"
        "name": "OVH SAS",
        "address": "2 rue Kellermann, 59100 Roubaix",
        "country": {"en": "France", "fr": "France"},
        "phone": "+33 9 72 10 10 07",
        "url": "https://www.ovhcloud.com",
    },
}

HOST = HOSTS["ovh_vps"]

# ---------------------------------------------------------------------------
# Deploy targets
#
# Asset URLs are relative, so they survive any base path untouched. What does
# depend on where the site is mounted is the pair of language links, the brand
# link and the absolute URLs in the head. Those are all derived from here.
#
#   base       path the site is served from, leading and trailing slash
#   origin     scheme + host, for absolute URLs only
#   indexable  production. False also adds noindex and a disallow-all
#              robots.txt, so a preview copy cannot compete with the real site
#              in search results or be found by anyone not given the link.
# ---------------------------------------------------------------------------

TARGETS = {
    # The real site, served from the root of its own domain. The OVH VPS
    # redirects notyga.com to www.notyga.com, so www is the canonical host.
    "production": {
        "base": "/",
        "origin": "https://www.notyga.com",
        "indexable": True,
    },
    # To build a private preview elsewhere, add a target here with its own
    # base and origin and "indexable": False.
}

# ---------------------------------------------------------------------------
# Copy deck
# ---------------------------------------------------------------------------

COPY = {
    "en": {
        "lang": "en",
        "locale": "en_GB",
        "dir": "",                 # served at <base>
        "asset_prefix": "assets/",
        "title": "Notyga — Data intelligence for better decisions",
        "meta": "Notyga uses data analysis and artificial intelligence to help "
                "businesses and organizations make better decisions. Geodata, "
                "mobility, tourism, sport, dashboards, fraud detection and market research.",

        "skip": "Skip to content",
        "nav": [("#expertise", "Expertise"), ("#approach", "Approach"),
                ("#about", "About"), ("#contact", "Contact")],
        "nav_label": "Main",
        "menu_label": "Open menu",
        "cta_nav": "Get in touch",

        # verbatim — hero
        "hero_eyebrow": "Data intelligence",
        "hero_h1": "Turn your data into decisions",
        "hero_lede": "Notyga uses data analysis and artificial intelligence to help "
                     "businesses and organizations make better decisions",
        "hero_cta1": "Explore our expertise",
        "hero_cta2": "Start a conversation",
        "hero_alt": "Territorial landscape with hills, roads and river",

        "expertise_eyebrow": "What we do",
        "expertise_h2": "Our areas of expertise",
        "expertise_lede": "From territorial planning to athletic performance, the same "
                          "discipline applies: understand the decision, model the data, "
                          "deliver something you can act on.",
        "cta_card_h": "Not sure where your question fits?",
        "cta_card_p": "Describe the decision you need to make. We will tell you which "
                      "approach applies — or say so plainly if data is not the answer.",
        "cta_card_link": "Talk to us",

        # verbatim — the seven services
        "services": [
            ("geo", "Geodata analysis",
             "Analyse territories, infrastructure and networks through geospatial data. "
             "We combine spatial analysis, mapping and AI to identify patterns, assess "
             "impacts and support planning and operational decisions."),
            ("tourism", "Tourism and territorial attractiveness",
             "Identify, track and understand your visitors. Through flow analysis, "
             "attendance metrics, and economic indicators, we help you drive your "
             "tourism strategies effectively."),
            ("mobility", "Mobility, transport and urban planning",
             "Model flows, analyze mobility behaviors, and optimize your infrastructure. "
             "We support local authorities and operators in making informed decisions on "
             "planning and transportation."),
            ("sport", "Performance sport and physical training",
             "Put data at the service of performance. We help coaches and athletes monitor "
             "training load, personalize programs, and make better decisions."),
            ("dataviz", "Data visualization and dashboards",
             "Track your key indicators with dynamic data representation tools. We design "
             "interactive dashboards (e.g. Shiny apps) to make your data clear, actionable, "
             "and easy to explore at a glance."),
            ("fraud", "Fraud detection",
             "We detect abnormal behavior through data analysis and artificial intelligence, "
             "identifying weak signals and anomalies to prevent fraud across various sectors "
             "(e-commerce, transport, insurance, etc.)."),
            ("market", "Market research and commercial strategy",
             "Understand your customers, improve targeting and segmentation, and assess your "
             "local market potential. We help you make informed decisions through detailed "
             "analysis of consumer behavior and catchment areas."),
        ],

        "approach_eyebrow": "How we work",
        "approach_h2": "From question to decision",
        "approach_lede": "Every engagement is tailored. The path through it stays the same.",
        "approach_banner_alt": "Aerial view of a winding river and surrounding landscape",
        "steps": [
            ("Frame",
             "We start with your decision, not your dataset. What has to be decided, by whom, "
             "and on what timeline — that is what defines the work and what we measure it against."),
            ("Model",
             "Spatial analysis, statistical modelling, machine learning or deep learning: we use "
             "the method the question actually calls for, and we are explicit about what it can "
             "and cannot show."),
            ("Deliver",
             "Results arrive in a form you can use — an interactive dashboard, a map, a model you "
             "can re-run — together with a clear reading of what they mean for your next decision."),
        ],
        "chips_label": "Disciplines we combine",
        "chips": ["Applied mathematics", "Artificial intelligence", "Deep learning",
                  "Spatial analysis", "Programming", "Data design and visualization"],

        # verbatim — about
        "about_eyebrow": "About us",
        "about_h2": "A team of researchers, data scientists and developers",
        "founder_name": "Gaëlle Saint-Hilary, PhD",
        "founder_role": "Founder of Notyga",
        "founder_alt": "Portrait of Gaëlle Saint-Hilary, founder of Notyga",
        "founder_p1": "Gaëlle Saint-Hilary is an engineer graduated from <strong>ENSAI</strong> and "
                      "holds a PhD in applied mathematics from the <strong>Polytechnic University "
                      "of Turin</strong>. After twenty years of experience in the healthcare "
                      "industry, she founded several data science-focused organizations, including "
                      "<strong>Notyga</strong>, a brand of the company Saryga.",
        "founder_p2": "She leads a team of experts working on data analysis and artificial "
                      "intelligence projects across various sectors. Their mission: to deliver "
                      "tailored solutions that support strategic and operational decision-making.",
        "team_h3": "Our team",
        "team_p1": "Notyga relies on a multidisciplinary team of <strong>researchers</strong>, "
                   "<strong>data scientists</strong>, and <strong>developers</strong> from top "
                   "institutions.",
        "team_p2": "They combine their expertise in applied mathematics, artificial intelligence, "
                   "deep learning, and programming – as well as data design and visualization – to "
                   "address complex challenges with rigor, agility, and creativity.",

        # verbatim — contact
        "contact_eyebrow": "Contact",
        "contact_h2": "Reach out and let’s find the right data-driven solution for you",
        "contact_lede": "Tell us the decision you are facing. We will tell you whether data can "
                        "help answer it.",

        "footer_tagline": "Notyga puts data analysis and artificial intelligence at the service of "
                          "businesses and territories. Notyga is a brand of the company Saryga.",
        "footer_cols": [("Expertise", "nav"), ("Company", "company")],
        "footer_company": [("#about", "About us"), ("#approach", "Approach"),
                           ("#contact", "Contact"), ("mailto:" + EMAIL, EMAIL)],
        "footer_rights": "All rights reserved.",
        "lang_label": "Language",
        "legal_dir": "legal/",     # served at <base>legal/
        "legal_link": "Legal notice &amp; privacy",

        "404_title": "Page not found — Notyga",
        "404_h1": "This page does not exist",
        "404_p": "The page you are looking for may have been moved or removed.",
        "404_cta": "Back to the homepage",
    },

    "fr": {
        "lang": "fr",
        "locale": "fr_FR",
        "dir": "fr/",              # served at <base>fr/
        "asset_prefix": "../assets/",
        "title": "Notyga — La data intelligence au service de vos décisions",
        "meta": "Notyga met l’analyse de données et l’intelligence artificielle au service des "
                "entreprises et des territoires : geodata, mobilité, tourisme, sport, tableaux de "
                "bord, détection de fraudes et études de marché.",

        "skip": "Aller au contenu",
        "nav": [("#expertise", "Expertises"), ("#approach", "Méthode"),
                ("#about", "À propos"), ("#contact", "Contact")],
        "nav_label": "Principale",
        "menu_label": "Ouvrir le menu",
        "cta_nav": "Nous contacter",

        # verbatim — hero
        "hero_eyebrow": "Data intelligence",
        "hero_h1": "Transformez vos données en décisions",
        "hero_lede": "Notyga met l’analyse de données et l’intelligence artificielle au service "
                     "des entreprises et des territoires",
        "hero_cta1": "Découvrir nos expertises",
        "hero_cta2": "Parlons de votre projet",
        "hero_alt": "Paysage territorial avec collines, routes et fleuve",

        "expertise_eyebrow": "Ce que nous faisons",
        "expertise_h2": "Nos domaines d’expertise",
        "expertise_lede": "De l’aménagement du territoire à la performance sportive, la même "
                          "exigence s’applique : comprendre la décision à prendre, modéliser la "
                          "donnée, livrer un résultat exploitable.",
        "cta_card_h": "Votre question n’entre dans aucune case ?",
        "cta_card_p": "Décrivez-nous la décision que vous devez prendre. Nous vous dirons quelle "
                      "approche s’applique — ou, tout simplement, si la donnée n’est pas la réponse.",
        "cta_card_link": "Échangeons",

        # verbatim — the seven services
        "services": [
            ("geo", "Analyse geodata",
             "Analysez les territoires, les infrastructures et les réseaux grâce aux geodata. Nous "
             "combinons analyse spatiale, cartographie et intelligence artificielle pour identifier "
             "des tendances, évaluer les impacts et accompagner les décisions de planification et "
             "opérationnelles."),
            ("tourism", "Tourisme et attractivité territoriale",
             "Identifiez, suivez et comprenez vos visiteurs. Grâce à des analyses de flux, des "
             "mesures de fréquentation et des indicateurs économiques, nous vous aidons à piloter "
             "vos politiques touristiques."),
            ("mobility", "Mobilité, déplacements et aménagement",
             "Modélisez les flux, analysez les comportements de déplacement, optimisez vos "
             "infrastructures. Nous accompagnons territoires et opérateurs dans leurs choix "
             "d’aménagement et de mobilité."),
            ("sport", "Sport de performance et préparation physique",
             "Mettez la donnée au service de la performance. Nous aidons les coachs et les athlètes "
             "à suivre la charge d’entraînement, individualiser les plans et mieux décider."),
            ("dataviz", "Visualisation de données et tableaux de bord",
             "Suivez vos indicateurs clés grâce à des outils de représentation dynamique des "
             "données. Nous concevons des tableaux de bord interactifs (par exemple, app Shiny) "
             "pour rendre vos données lisibles, utiles et exploitables en un coup d’œil."),
            ("fraud", "Détection de fraudes",
             "Nous détectons les comportements anormaux grâce à l’analyse de données et à "
             "l’intelligence artificielle, en identifiant les signaux faibles et les anomalies pour "
             "prévenir les fraudes dans divers secteurs (e-commerce, transports, assurances…)."),
            ("market", "Études de marché et stratégie commerciale",
             "Comprendre ses clients, mieux cibler, segmenter et évaluer son potentiel local. Nous "
             "vous aidons à prendre des décisions éclairées grâce à une analyse fine des "
             "comportements et des zones de chalandise."),
        ],

        "approach_eyebrow": "Notre méthode",
        "approach_h2": "De la question à la décision",
        "approach_lede": "Chaque mission est sur mesure. La démarche, elle, reste la même.",
        "approach_banner_alt": "Vue aérienne d'un fleuve et des territoires environnants",
        "steps": [
            ("Cadrer",
             "Nous partons de votre décision, pas de vos données. Ce qu’il faut décider, par qui et "
             "dans quel délai : c’est ce qui définit la mission et ce à quoi nous la mesurons."),
            ("Modéliser",
             "Analyse spatiale, modélisation statistique, machine learning ou deep learning : nous "
             "retenons la méthode qu’exige réellement la question, et nous disons explicitement ce "
             "qu’elle peut — ou ne peut pas — montrer."),
            ("Restituer",
             "Les résultats sont livrés sous une forme directement exploitable — tableau de bord "
             "interactif, cartographie, modèle réutilisable — accompagnés d’une lecture claire de "
             "ce qu’ils impliquent pour votre prochaine décision."),
        ],
        "chips_label": "Les expertises que nous combinons",
        "chips": ["Mathématiques appliquées", "Intelligence artificielle", "Deep learning",
                  "Analyse spatiale", "Programmation", "Design et visualisation de données"],

        # verbatim — about
        "about_eyebrow": "À propos de nous",
        "about_h2": "Une équipe de chercheurs, data scientists et développeurs",
        "founder_name": "Gaëlle Saint-Hilary, PhD",
        "founder_role": "Fondatrice de Notyga",
        "founder_alt": "Portrait de Gaëlle Saint-Hilary, fondatrice de Notyga",
        "founder_p1": "Gaëlle Saint-Hilary est ingénieure diplômée de l’<strong>ENSAI</strong> et "
                      "titulaire d’un doctorat en mathématiques appliquées de l’<strong>École "
                      "Polytechnique de Turin</strong>. Après vingt ans d’expérience dans "
                      "l’industrie de la santé, elle a fondé plusieurs structures spécialisées en "
                      "data science, dont <strong>Notyga</strong> qui fait partie de la société "
                      "Saryga.",
        "founder_p2": "Elle y pilote une équipe d’experts mobilisés sur des projets d’<strong>analyse "
                      "de données</strong> et d’<strong>intelligence artificielle</strong> dans des "
                      "secteurs variés. Leur mission : proposer des solutions sur mesure pour "
                      "éclairer les décisions stratégiques et opérationnelles.",
        "team_h3": "Notre équipe",
        "team_p1": "Notyga s’appuie sur une équipe pluridisciplinaire composée de "
                   "<strong>chercheurs</strong>, <strong>data scientists</strong> et "
                   "<strong>développeurs</strong> issus des meilleures écoles.",
        "team_p2": "Ils mettent en commun leurs expertises en mathématiques appliquées, intelligence "
                   "artificielle, deep learning, programmation, mais aussi en design et "
                   "visualisation de données, pour répondre aux problématiques les plus complexes "
                   "avec rigueur, agilité et créativité.",

        # verbatim — contact
        "contact_eyebrow": "Contact",
        "contact_h2": "Parlons de votre projet",
        "contact_lede": "Dites-nous la décision que vous devez prendre. Nous vous dirons si la "
                        "donnée peut y répondre.",

        "footer_tagline": "Notyga met l’analyse de données et l’intelligence artificielle au service "
                          "des entreprises et des territoires. Notyga est une marque de la société "
                          "Saryga.",
        "footer_cols": [("Expertises", "nav"), ("Société", "company")],
        "footer_company": [("#about", "À propos"), ("#approach", "Méthode"),
                           ("#contact", "Contact"), ("mailto:" + EMAIL, EMAIL)],
        "footer_rights": "Tous droits réservés.",
        "lang_label": "Langue",
        "legal_dir": "fr/mentions-legales/",
        "legal_link": "Mentions légales et confidentialité",

        "404_title": "Page introuvable — Notyga",
        "404_h1": "Cette page n’existe pas",
        "404_p": "La page que vous cherchez a peut-être été déplacée ou supprimée.",
        "404_cta": "Retour à l’accueil",
    },
}


# ---------------------------------------------------------------------------
# Fragments
# ---------------------------------------------------------------------------

def resolve(lang, target):
    """Merge a language's copy with a deploy target into one render context."""
    t = TARGETS[target]
    c = dict(COPY[lang])
    base, origin = t["base"], t["origin"]

    c["base"] = base
    c["origin"] = origin
    c["indexable"] = t["indexable"]
    c["href"] = base + c["dir"]                     # this page
    c["home"] = base + c["dir"]                     # this language's homepage
    c["en_href"] = base                             # English homepage
    c["fr_href"] = base + "fr/"                     # French homepage
    c["legal_href"] = base + c["legal_dir"]         # this language's legal page
    # Prefix for links to homepage sections (#expertise...). Empty on the
    # homepage itself; other pages point back at it.
    c["anchor"] = ""
    return c


def head(c, *, page_title=None, canonical=True):
    a = c["asset_prefix"]
    o = c["origin"]
    title = page_title or c["title"]

    if c["indexable"] and canonical:
        discovery = (
            f'  <link rel="alternate" hreflang="en" href="{o}{c["en_href"]}">\n'
            f'  <link rel="alternate" hreflang="fr" href="{o}{c["fr_href"]}">\n'
            f'  <link rel="alternate" hreflang="x-default" href="{o}{c["en_href"]}">\n'
            f'  <link rel="canonical" href="{o}{c["href"]}">\n')
    elif not c["indexable"]:
        # Keep the review copy out of search results entirely: no canonical or
        # hreflang, which would only invite indexing of the wrong host.
        discovery = '  <meta name="robots" content="noindex, nofollow">\n'
    else:
        discovery = ''

    return f"""<!DOCTYPE html>
<html lang="{c['lang']}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{c['meta']}">
  <meta name="theme-color" content="#006401">
{discovery}
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Notyga">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{c['meta']}">
  <meta property="og:locale" content="{c['locale']}">
  <meta property="og:url" content="{o}{c['href']}">
  <meta property="og:image" content="{o}{c['base']}assets/img/logo-full.png">
  <meta name="twitter:card" content="summary_large_image">

  <link rel="icon" href="{a}img/favicon-32.png" sizes="32x32">
  <link rel="icon" href="{a}img/favicon-512.png" sizes="512x512">
  <link rel="apple-touch-icon" href="{a}img/apple-touch-icon.png">

  <link rel="preload" href="{a}fonts/inter-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="{a}css/styles.css">
  <script src="{a}js/main.js" defer></script>
</head>"""


def header(c):
    a = c["asset_prefix"]
    links = "\n".join(
        f'            <a class="nav__link" href="{c["anchor"]}{href}">{label}</a>'
        for href, label in c["nav"]
    )
    en_current = ' aria-current="page"' if c["lang"] == "en" else ""
    fr_current = ' aria-current="page"' if c["lang"] == "fr" else ""
    en_href, fr_href = c["en_href"], c["fr_href"]

    return f"""  <a class="skip-link" href="#main">{c['skip']}</a>

  <header class="header" data-header>
    <div class="wrap header__inner">
      <a class="brand" href="{c['home']}" aria-label="Notyga — {c['hero_eyebrow']}">
        <img src="{a}img/logo.svg" alt="Notyga — Data intelligence" width="524" height="229">
      </a>

      <button class="nav-toggle" type="button" data-nav-toggle
              aria-expanded="false" aria-controls="site-nav" aria-label="{c['menu_label']}">
        <svg class="icon-open" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
        <svg class="icon-close" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
      </button>

      <div class="header__nav" id="site-nav" data-nav-panel>
        <nav class="nav" aria-label="{c['nav_label']}">
{links}
        </nav>
        <div class="header__actions">
          <p class="lang" role="group" aria-label="{c['lang_label']}">
            <a href="{en_href}" hreflang="en"{en_current}>EN</a>
            <span class="lang__sep" aria-hidden="true">|</span>
            <a href="{fr_href}" hreflang="fr"{fr_current}>FR</a>
          </p>
          <a class="btn" href="{c['anchor']}#contact">{c['cta_nav']}{ARROW}</a>
        </div>
      </div>
    </div>
  </header>"""


def hero(c):
    a = c["asset_prefix"]
    domains = [name for _, name, _ in c["services"]]
    items = "\n".join(
        f'          <span class="marquee__item">{d}</span>' for d in domains
    )
    return f"""    <section class="hero">
      <div class="hero__grid" aria-hidden="true"></div>
      <div class="wrap hero__inner">
        <div class="hero__content">
          <p class="eyebrow" data-reveal>{c['hero_eyebrow']}</p>
          <h1 data-reveal>{c['hero_h1']}</h1>
          <p class="lede" data-reveal>{c['hero_lede']}</p>
          <div class="hero__actions" data-reveal>
            <a class="btn" href="#expertise">{c['hero_cta1']}{ARROW}</a>
            <a class="btn btn--ghost" href="#contact">{c['hero_cta2']}</a>
          </div>
        </div>
        <figure class="hero__media" data-reveal>
          <img src="{a}img/hero.jpg" alt="{c['hero_alt']}" width="1200" height="1500"
               fetchpriority="high" decoding="async">
        </figure>
      </div>

      <div class="marquee">
        <div class="marquee__track" data-marquee aria-hidden="true">
{items}
        </div>
      </div>
    </section>"""


def expertise(c):
    a = c["asset_prefix"]
    cards = []
    for i, (icon, title, body) in enumerate(c["services"], start=1):
        cards.append(f"""        <article class="card" data-reveal>
          <div class="card__media">
            <img src="{a}img/expertise-{icon}.jpg" alt="" width="960" height="640"
                 loading="lazy" decoding="async">
          </div>
          <div class="card__top">
            <span class="card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
                   stroke-linecap="round" stroke-linejoin="round">{ICONS[icon]}</svg>
            </span>
            <span class="card__num" aria-hidden="true">{i:02d}</span>
          </div>
          <h3>{title}</h3>
          <p>{body}</p>
        </article>""")

    cards.append(f"""        <article class="card card--cta" data-reveal>
          <h3>{c['cta_card_h']}</h3>
          <p>{c['cta_card_p']}</p>
          <p><a class="link" href="#contact">{c['cta_card_link']}{ARROW}</a></p>
        </article>""")

    return f"""    <section class="section section--tint" id="expertise">
      <div class="wrap">
        <div class="section-head">
          <p class="eyebrow" data-reveal>{c['expertise_eyebrow']}</p>
          <h2 data-reveal>{c['expertise_h2']}</h2>
          <p class="lede" data-reveal>{c['expertise_lede']}</p>
        </div>
        <div class="cards">
{chr(10).join(cards)}
        </div>
      </div>
    </section>"""


def approach(c):
    a = c["asset_prefix"]
    steps = "\n".join(
        f"""          <article class="step" data-reveal>
            <p class="step__num">{i:02d}</p>
            <h3>{title}</h3>
            <p>{body}</p>
          </article>"""
        for i, (title, body) in enumerate(c["steps"], start=1)
    )
    chips = "\n".join(f'          <li class="chip">{x}</li>' for x in c["chips"])
    return f"""    <section class="section" id="approach">
      <div class="wrap">
        <div class="section-head">
          <p class="eyebrow" data-reveal>{c['approach_eyebrow']}</p>
          <h2 data-reveal>{c['approach_h2']}</h2>
          <p class="lede" data-reveal>{c['approach_lede']}</p>
        </div>
        <figure class="approach__banner" data-reveal>
          <img src="{a}img/banner-approach.jpg" alt="{c['approach_banner_alt']}"
               width="2000" height="860" loading="lazy" decoding="async">
        </figure>
        <div class="steps">
{steps}
        </div>
        <h3 class="visually-hidden">{c['chips_label']}</h3>
        <ul class="chips" data-reveal>
{chips}
        </ul>
      </div>
    </section>"""


def about(c):
    a = c["asset_prefix"]
    return f"""    <section class="section section--tint" id="about">
      <div class="wrap">
        <div class="section-head">
          <p class="eyebrow" data-reveal>{c['about_eyebrow']}</p>
          <h2 data-reveal>{c['about_h2']}</h2>
        </div>

        <div class="founder">
          <figure class="founder__media" data-reveal>
            <img src="{a}img/founder.jpg" alt="{c['founder_alt']}"
                 width="900" height="1125" loading="lazy" decoding="async">
          </figure>
          <div class="founder__body" data-reveal>
            <p class="founder__role">{c['founder_role']}</p>
            <h3 class="founder__name">{c['founder_name']}</h3>
            <p>{c['founder_p1']}</p>
            <p>{c['founder_p2']}</p>
          </div>
        </div>

        <div class="team">
          <h3 data-reveal>{c['team_h3']}</h3>
          <div class="team__body">
            <p data-reveal>{c['team_p1']}</p>
            <p data-reveal>{c['team_p2']}</p>
          </div>
        </div>
      </div>
    </section>"""


def contact(c):
    return f"""    <section class="section section--dark contact" id="contact">
      <div class="wrap contact__inner">
        <p class="eyebrow" data-reveal>{c['contact_eyebrow']}</p>
        <h2 data-reveal>{c['contact_h2']}</h2>
        <p class="lede" data-reveal>{c['contact_lede']}</p>
        <a class="contact__email" href="mailto:{EMAIL}" data-reveal>{EMAIL}</a>
      </div>
    </section>"""


def footer(c):
    a = c["asset_prefix"]
    # The expertise column lists the actual domains, not a copy of the nav.
    nav_col = "\n".join(
        f'            <li><a href="{c["anchor"]}#expertise">{name}</a></li>'
        for _, name, _ in c["services"]
    )
    company_col = "\n".join(
        f'            <li><a href="{c["anchor"] + href if href.startswith("#") else href}">{label}</a></li>'
        for href, label in c["footer_company"]
    )
    nav_title, company_title = c["footer_cols"][0][0], c["footer_cols"][1][0]
    return f"""  <footer class="footer">
    <div class="wrap">
      <div class="footer__top">
        <div class="footer__brand">
          <img src="{a}img/logo-white.svg" alt="Notyga — Data intelligence"
               width="524" height="229" loading="lazy">
          <p>{c['footer_tagline']}</p>
        </div>

        <nav class="footer__col" aria-label="{nav_title}">
          <h3>{nav_title}</h3>
          <ul>
{nav_col}
          </ul>
        </nav>

        <nav class="footer__col" aria-label="{company_title}">
          <h3>{company_title}</h3>
          <ul>
{company_col}
          </ul>
        </nav>
      </div>

      <div class="footer__bottom">
        <p>&copy; <span data-year>2026</span> Notyga. {c['footer_rights']}
          <span class="footer__sep" aria-hidden="true">·</span>
          <a class="footer__legal" href="{c['legal_href']}">{c['legal_link']}</a></p>
        <p class="lang">
          <a href="{c['en_href']}" hreflang="en">EN</a>
          <span class="lang__sep" aria-hidden="true">|</span>
          <a href="{c['fr_href']}" hreflang="fr">FR</a>
        </p>
      </div>
    </div>
  </footer>"""


def schema(c):
    # Structured data always describes the real site, never a review copy.
    return """  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "Notyga",
    "url": "%(o)s/",
    "logo": "%(o)s/assets/img/logo-full.png",
    "email": "contact@notyga.com",
    "description": "Data analysis and artificial intelligence for businesses and territories.",
    "parentOrganization": { "@type": "Organization", "name": "Saryga" },
    "founder": {
      "@type": "Person",
      "name": "Ga\\u00eblle Saint-Hilary",
      "jobTitle": "Founder"
    }
  }
  </script>""" % {"o": TARGETS["production"]["origin"]}


def page(c):
    return "\n".join([
        head(c),
        "<body>",
        header(c),
        '  <main id="main">',
        hero(c),
        expertise(c),
        approach(c),
        about(c),
        contact(c),
        "  </main>",
        footer(c),
        schema(c),
        "</body>",
        "</html>",
        "",
    ])


def error_page(c):
    # Served for any missing URL, at any depth, so relative asset paths would
    # resolve against the wrong directory. Root them at the base instead.
    c = dict(c, asset_prefix=c["base"] + "assets/", anchor=c["home"])
    return "\n".join([
        head(c, page_title=c["404_title"], canonical=False),
        "<body>",
        header(c),
        '  <main id="main">',
        '    <section class="section wrap error">',
        f'      <h1>{c["404_h1"]}</h1>',
        f'      <p>{c["404_p"]}</p>',
        f'      <a class="btn" href="{c["href"]}">{c["404_cta"]}{ARROW}</a>',
        "    </section>",
        "  </main>",
        footer(c),
        "</body>",
        "</html>",
        "",
    ])


LEGAL_LABELS = {
    "en": {"capital": "share capital", "rcs_city": "registry city",
           "legal_form": "legal form", "address": "registered office",
           "vat": "VAT number", "phone": "phone number",
           "director": "publication director"},
    "fr": {"capital": "capital social", "rcs_city": "ville du greffe",
           "legal_form": "forme juridique", "address": "adresse du siège",
           "vat": "n° de TVA", "phone": "numéro de téléphone",
           "director": "directeur ou directrice de la publication"},
}

MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"],
}


def hosting_block(h, lang):
    site = h["url"].split("//")[1]
    return (f'<p>{h["name"]}<br>{h["address"]}, {h["country"][lang]}<br>\n'
            f'          {h["phone"]} · <a href="{h["url"]}">{site}</a></p>')


def logs_paragraph(h, lang):
    co, name, kind = LEGAL["company"], h["name"], h["logs"]
    # Retention not decided yet (None): a highlighted "X" in its place.
    if h.get("log_days", 0) is None:
        todo = "à décider" if lang == "fr" else "to be decided"
        h = dict(h, log_days=f'<mark class="legal__todo">X ({todo})</mark>')
    if lang == "fr":
        intro = ("Comme tout serveur web, celui qui héberge ce site reçoit, à chaque visite, "
                 "votre adresse IP, la page demandée, la date et l’heure, et des informations "
                 "sur votre navigateur.")
        basis = "ce qui relève de l’intérêt légitime (article 6.1.f du RGPD)"
        if kind == "vps":
            rest = (f"Ce serveur est administré par {co}, sur une machine louée à {name} et "
                    "située dans l’Union européenne. Il enregistre ces données dans ses journaux "
                    f"techniques pour assurer la sécurité et le bon fonctionnement du site, {basis}. "
                    f"{name} fournit l’infrastructure en tant que sous-traitant et n’exploite pas "
                    "ces données, qui ne font l’objet d’aucun transfert hors de l’Union. Nous ne "
                    "les consultons qu’en cas d’incident ou d’abus, et elles sont supprimées "
                    f"automatiquement au bout de {h['log_days']} jours.")
        elif kind == "hosted":
            rest = (f"Ces données sont enregistrées par {name} dans ses journaux techniques pour "
                    f"assurer la sécurité et le bon fonctionnement du service, {basis}. Ces "
                    f"journaux sont hébergés par {name} pour le compte de {co}, sur des serveurs "
                    "situés dans l’Union européenne : ils ne font l’objet d’aucun transfert hors "
                    "de l’Union. Nous ne les consultons qu’en cas d’incident ou d’abus, et ils "
                    "sont conservés au plus un an.")
        else:
            rest = (f"Ces données sont enregistrées par {name} dans ses journaux techniques pour "
                    f"assurer la sécurité et le bon fonctionnement du service, {basis}. {co} n’y "
                    f"a pas accès et ne les exploite pas. {name} étant établie aux "
                    f"{h['country']['fr']}, ces données peuvent y être transférées ; leur durée de "
                    "conservation et les garanties encadrant ce transfert sont décrites dans "
                    f"<a href=\"{h['privacy']}\">sa déclaration de confidentialité</a>.")
    else:
        intro = ("Like any web server, the one hosting this site receives your IP address, the "
                 "page requested, the date and time, and information about your browser on "
                 "every visit.")
        basis = "which is a legitimate interest (Article 6(1)(f) GDPR)"
        if kind == "vps":
            rest = (f"This server is run by {co}, on a machine rented from {name} and located in "
                    "the European Union. It records this data in its server logs to keep the "
                    f"site secure and running, {basis}. {name} provides the infrastructure as a "
                    "processor and does not use this data, which is not transferred outside the "
                    "EU. We only look at it to investigate an incident or abuse, and it is "
                    f"deleted automatically after {h['log_days']} days.")
        elif kind == "hosted":
            rest = (f"{name} records this data in its server logs to keep the service secure and "
                    f"running, {basis}. These logs are hosted by {name} on behalf of {co}, on "
                    "servers located in the European Union: they are not transferred outside the "
                    "EU. We only look at them to investigate an incident or abuse, and they are "
                    "kept for no more than one year.")
        else:
            rest = (f"{name} records this data in its server logs to keep the service secure and "
                    f"running, {basis}. {co} has no access to these logs and does not use them. "
                    f"As {name} is based in the {h['country']['en']}, the data may be transferred "
                    "there; how long it is kept and the safeguards that apply to the transfer are "
                    f"set out in <a href=\"{h['privacy']}\">its privacy statement</a>.")
    return f"<p>{intro} {rest}</p>"


def by_host(hosts, lang, render):
    """One host: its text. Several (review copy): each distinct text, labelled."""
    texts = [render(h, lang) for h in hosts]
    if len(set(texts)) == 1:
        return texts[0]
    boxes = "\n".join(
        f'          <div class="legal__variant">\n'
        f'            <p class="legal__variant-label">Option {chr(65 + i)} · '
        f'{h["label"][lang]}</p>\n            {t}\n          </div>'
        for i, (h, t) in enumerate(zip(hosts, texts)))
    return f'<div class="legal__variants">\n{boxes}\n        </div>'


def review_note(hosts, lang):
    """Banner explaining the options, on a review copy only."""
    if len(hosts) < 2:
        return ""
    sep = " : " if lang == "fr" else ": "
    labels = " ; ".join(f"{chr(65 + i)}{sep}{h['label'][lang]}" for i, h in enumerate(hosts))
    if lang == "fr":
        text = ("<strong>Version de relecture.</strong> Les passages qui dépendent du mode "
                f"d’hébergement sont proposés en plusieurs options ({labels}). Une seule "
                "sera publiée.")
    else:
        text = ("<strong>Review copy.</strong> Passages that depend on how the site is hosted "
                f"are given as options ({labels}). Only one will be published.")
    return f'\n        <p class="legal__review">{text}</p>\n'


def legal_sections(lang, hosts=None):
    """Title, "last updated" line and body of the legal page, per language.

    Structure follows the Saryga site's legal page, corrected per the
    September 2026 audit of that site: the publisher is the company itself,
    not whoever built the site, the publication director is a named
    person, the company details are complete, the cookie section describes
    what the site actually does, and the privacy policy gives the legal basis,
    retention, recipients, transfers and rights for each processing.
    """
    def v(key):
        val = LEGAL[key]
        if isinstance(val, dict):
            val = val[lang]
        if val is not None:
            return val
        todo = "À compléter :" if lang == "fr" else "To fill in:"
        return f'<mark class="legal__todo">{todo} {LEGAL_LABELS[lang][key]}</mark>'

    y, m, d = LEGAL_UPDATED
    co = LEGAL["company"]
    mail = f'<a href="mailto:{EMAIL}">{EMAIL}</a>'
    hosts = hosts or [HOST]
    hosting = by_host(hosts, lang, hosting_block)
    logs = by_host(hosts, lang, logs_paragraph)
    note = review_note(hosts, lang)
    rcs = f"RCS {v('rcs_city')} {LEGAL['siren']}"

    if lang == "fr":
        return "Mentions légales et confidentialité", \
            f"Dernière mise à jour : {d} {MONTHS['fr'][m - 1]} {y}", f"""{note}
        <h2 id="editeur">Éditeur du site</h2>
        <p>Le site {SITE_NAME} est édité par la société {co}. Notyga est une marque de {co}.</p>
        <dl>
          <dt>Raison sociale</dt><dd>{co}</dd>
          <dt>Forme juridique</dt><dd>{v('legal_form')}</dd>
          <dt>Capital social</dt><dd>{v('capital')}</dd>
          <dt>Siège social</dt><dd>{v('address')}</dd>
          <dt>Immatriculation</dt><dd>{rcs}</dd>
          <dt>SIRET</dt><dd>{LEGAL['siret']}</dd>
          <dt>TVA intracommunautaire</dt><dd>{v('vat')}</dd>
          <dt>Téléphone</dt><dd>{v('phone')}</dd>
          <dt>E-mail</dt><dd>{mail}</dd>
        </dl>

        <h2 id="publication">Direction de la publication</h2>
        <p>{v('director')}, présidente de {co}.</p>

        <h2 id="hebergement">Hébergement</h2>
        {hosting}

        <h2 id="propriete-intellectuelle">Propriété intellectuelle</h2>
        <p>L’ensemble du contenu du site {SITE_NAME}, notamment les textes, images, graphismes,
          logos et icônes, ainsi que leur mise en forme, est la propriété exclusive de {co},
          à l’exception des marques, logos ou contenus appartenant à d’autres sociétés ou
          auteurs.</p>
        <p>Toute reproduction, distribution, modification, adaptation, retransmission ou
          publication de ces éléments, même partielle, est interdite sans l’autorisation
          écrite préalable de {co}. Elle constitue une contrefaçon sanctionnée par les
          articles L.335-2 et suivants du Code de la propriété intellectuelle.</p>

        <h2 id="confidentialite">Politique de confidentialité</h2>
        <p>Cette politique explique quelles données personnelles sont traitées lorsque vous
          consultez {SITE_NAME} ou lorsque vous nous écrivez, pourquoi, pendant combien de
          temps, et comment exercer vos droits. Elle s’appuie sur le Règlement général sur la
          protection des données (RGPD) et la loi Informatique et Libertés.</p>

        <h3>Responsable du traitement</h3>
        <p>{co}, {v('address')}, joignable à {mail}.</p>

        <h3>Ce que le site ne collecte pas</h3>
        <p>Vous pouvez consulter {SITE_NAME} sans nous communiquer aucune donnée. Le site n’a
          ni formulaire, ni compte utilisateur, ni espace de commentaires. Il ne dépose
          <strong>aucun cookie</strong>, n’utilise aucun outil de mesure d’audience, de
          publicité ou de réseau social, et n’intègre aucun contenu provenant d’autres sites :
          même les polices de caractères sont hébergées sur le site. C’est pourquoi aucun
          bandeau de consentement ne vous est présenté.</p>

        <h3>Journaux techniques du serveur</h3>
        {logs}

        <h3>Messages que vous nous envoyez</h3>
        <p>Si vous nous écrivez à {mail}, nous traitons votre adresse e-mail, votre nom et le
          contenu de votre message.</p>
        <ul>
          <li><strong>Finalité :</strong> vous répondre et donner suite à votre demande,
            y compris préparer une éventuelle collaboration.</li>
          <li><strong>Base légale :</strong> notre intérêt légitime à répondre aux demandes
            qui nous sont adressées et, lorsque vous nous sollicitez en vue d’un contrat, les
            mesures précontractuelles prises à votre demande (article 6.1.b et 6.1.f du
            RGPD).</li>
          <li><strong>Durée de conservation :</strong> trois ans à compter de notre dernier
            échange, puis suppression. Si une collaboration s’engage, les échanges sont
            conservés pendant sa durée, puis le temps imposé par nos obligations légales.</li>
          <li><strong>Destinataires :</strong> les seules personnes de {co} chargées de
            traiter votre demande. Notre messagerie est fournie par Microsoft
            ({MAIL_PROVIDER}), qui agit pour notre compte et peut traiter certaines données
            hors de l’Union européenne, dans le cadre des garanties prévues par le RGPD.</li>
        </ul>
        <p>Vos données ne sont ni vendues, ni louées, ni cédées, et ne font l’objet d’aucune
          décision automatisée ni d’aucun profilage.</p>

        <h3>Vos droits</h3>
        <p>Vous disposez à tout moment des droits suivants sur vos données :</p>
        <ul>
          <li>droit d’accès, de rectification et d’effacement ;</li>
          <li>droit à la limitation du traitement et droit d’opposition ;</li>
          <li>droit à la portabilité ;</li>
          <li>droit de définir des directives sur le sort de vos données après votre
            décès.</li>
        </ul>
        <p>Pour les exercer, écrivez-nous à {mail} ou par courrier à {co},
          {v('address')}. Nous vous répondrons dans un délai d’un mois. Si un doute
          raisonnable existe sur votre identité, nous pourrons vous demander d’en
          justifier.</p>
        <p>Si vous estimez, après nous avoir contactés, que vos droits ne sont pas respectés,
          vous pouvez adresser une réclamation à la CNIL, 3 place de Fontenoy, TSA 80715,
          75334 Paris Cedex 07, ou en ligne sur <a href="https://www.cnil.fr">cnil.fr</a>.</p>

        <h3>Modifications</h3>
        <p>Cette page peut évoluer, notamment si le site ajoute un service qui traite de
          nouvelles données. La date de dernière mise à jour figure en haut de page.</p>"""

    return "Legal notice and privacy", \
        f"Last updated: {d} {MONTHS['en'][m - 1]} {y}", f"""{note}
        <h2 id="publisher">Publisher</h2>
        <p>The {SITE_NAME} website is published by {co}. Notyga is a brand of {co}.</p>
        <dl>
          <dt>Company name</dt><dd>{co}</dd>
          <dt>Legal form</dt><dd>{v('legal_form')}</dd>
          <dt>Share capital</dt><dd>{v('capital')}</dd>
          <dt>Registered office</dt><dd>{v('address')}, France</dd>
          <dt>Registration</dt><dd>{rcs}</dd>
          <dt>SIRET</dt><dd>{LEGAL['siret']}</dd>
          <dt>EU VAT number</dt><dd>{v('vat')}</dd>
          <dt>Phone</dt><dd>{LEGAL['phone_intl'] or v('phone')}</dd>
          <dt>Email</dt><dd>{mail}</dd>
        </dl>

        <h2 id="publication">Publication director</h2>
        <p>{v('director')}, President of {co}.</p>

        <h2 id="hosting">Hosting</h2>
        {hosting}

        <h2 id="intellectual-property">Intellectual property</h2>
        <p>All content on {SITE_NAME}, including text, images, graphics, logos and icons, and
          their layout, is the exclusive property of {co}, except for trademarks, logos or
          content belonging to other companies or authors.</p>
        <p>Any reproduction, distribution, modification, adaptation, retransmission or
          publication of this content, even in part, is prohibited without the prior written
          consent of {co}. It constitutes infringement under Articles L.335-2 et seq. of the
          French Intellectual Property Code.</p>

        <h2 id="privacy">Privacy policy</h2>
        <p>This policy explains what personal data is processed when you visit {SITE_NAME} or
          write to us, why, for how long, and how to exercise your rights. It is based on the
          General Data Protection Regulation (GDPR) and the French Data Protection Act.</p>

        <h3>Data controller</h3>
        <p>{co}, {v('address')}, France, reachable at {mail}.</p>

        <h3>What this site does not collect</h3>
        <p>You can browse {SITE_NAME} without giving us any data. The site has no forms, no user
          accounts and no comments. It sets <strong>no cookies</strong>, uses no analytics,
          advertising or social media tools, and embeds no content from other sites: even the
          fonts are hosted on the site itself. That is why you are not shown a consent
          banner.</p>

        <h3>Server logs</h3>
        {logs}

        <h3>Messages you send us</h3>
        <p>If you write to {mail}, we process your email address, your name and the content of
          your message.</p>
        <ul>
          <li><strong>Purpose:</strong> to reply and follow up on your request, including
            preparing a possible collaboration.</li>
          <li><strong>Legal basis:</strong> our legitimate interest in answering the requests
            we receive and, where you contact us with a view to a contract, steps taken at
            your request before entering into it (Article 6(1)(b) and (f) GDPR).</li>
          <li><strong>Retention:</strong> three years from our last exchange, then deleted. If
            we work together, correspondence is kept for the duration of the engagement, then
            for as long as the law requires.</li>
          <li><strong>Recipients:</strong> only the people at {co} who handle your request. Our
            email is provided by Microsoft ({MAIL_PROVIDER}), which acts on our behalf and may
            process some data outside the European Union, under the safeguards provided by the
            GDPR.</li>
        </ul>
        <p>Your data is never sold, rented or passed on, and is not used for automated
          decision-making or profiling.</p>

        <h3>Your rights</h3>
        <p>You have the following rights over your data at any time:</p>
        <ul>
          <li>right of access, rectification and erasure;</li>
          <li>right to restriction of processing and right to object;</li>
          <li>right to data portability;</li>
          <li>right to give instructions on what happens to your data after your death.</li>
        </ul>
        <p>To exercise them, write to {mail} or by post to {co}, {v('address')}, France. We
          will reply within one month. If we have reasonable doubts about your identity, we
          may ask you to confirm it.</p>
        <p>If, after contacting us, you believe your rights have not been respected, you can
          lodge a complaint with the CNIL, the French data protection authority: 3 place de
          Fontenoy, TSA 80715, 75334 Paris Cedex 07, France, or online at
          <a href="https://www.cnil.fr">cnil.fr</a>.</p>

        <h3>Changes</h3>
        <p>This page may change, for example if the site adds a service that processes new
          data. The date of the last update is shown at the top of the page.</p>"""


def legal_page(c, other, hosts=None):
    # Lives one or two folders down: root the assets, point section links and
    # the language switcher at the matching pages.
    c = dict(c, asset_prefix=c["base"] + "assets/", anchor=c["home"],
             href=c["legal_href"])
    c[f"{c['lang']}_href"] = c["legal_href"]
    c[f"{other['lang']}_href"] = other["legal_href"]
    title, updated, body = legal_sections(c["lang"], hosts)

    return "\n".join([
        head(c, page_title=f"{title} — Notyga"),
        "<body>",
        header(c),
        '  <main id="main">',
        '    <article class="section wrap legal">',
        f'      <h1>{title}</h1>',
        f'      <p class="legal__updated">{updated}</p>',
        '      <div class="legal__body">' + body,
        "      </div>",
        "    </article>",
        "  </main>",
        footer(c),
        "</body>",
        "</html>",
        "",
    ])


def sitemap(en, fr):
    o = en["origin"]
    entries = "\n".join(f"""  <url>
    <loc>{o}{c['href']}</loc>
    <xhtml:link rel="alternate" hreflang="en" href="{o}{en['href']}"/>
    <xhtml:link rel="alternate" hreflang="fr" href="{o}{fr['href']}"/>
    <changefreq>monthly</changefreq>
    <priority>1.0</priority>
  </url>""" for c in (en, fr))

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
{entries}
</urlset>
"""


def build(target, out_dir):
    en, fr = resolve("en", target), resolve("fr", target)
    files = {
        "index.html": page(en),
        "fr/index.html": page(fr),
        "404.html": error_page(en),
        en["legal_dir"] + "index.html": legal_page(en, fr),
        fr["legal_dir"] + "index.html": legal_page(fr, en),
    }

    missing = [k for k, v in LEGAL.items() if v is None]
    if missing:
        print("WARNING  legal page still has fields to fill in LEGAL: "
              + ", ".join(missing))

    if en["indexable"]:
        files["robots.txt"] = (
            f"User-agent: *\nAllow: /\n\nSitemap: {en['origin']}{en['base']}sitemap.xml\n")
        files["sitemap.xml"] = sitemap(en, fr)
    else:
        # Belt and braces alongside the noindex meta tag.
        files["robots.txt"] = (
            "# Private review copy. Not for indexing.\n"
            "User-agent: *\nDisallow: /\n")
        # Pages would otherwise run the output through Jekyll.
        files[".nojekyll"] = ""

    print(f"target={target}  base={en['base']}  "
          f"indexable={en['indexable']}  ->  {out_dir}")

    for relpath, content in files.items():
        path = os.path.join(out_dir, relpath)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        print("  %-16s %6d bytes" % (relpath, len(content.encode("utf-8"))))

    # Building somewhere other than the repo root means we are assembling a
    # standalone deployable tree, so the static assets have to come along.
    if os.path.abspath(out_dir) != os.path.abspath(ROOT):
        src = os.path.join(ROOT, "assets")
        dst = os.path.join(out_dir, "assets")
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        n = sum(len(f) for _, _, f in os.walk(dst))
        print("  assets/          %d files copied" % n)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", choices=sorted(TARGETS), default="production",
                    help="deploy target (default: production)")
    ap.add_argument("--out", default=None,
                    help="output directory (default: the repository root)")
    args = ap.parse_args()

    build(args.target, args.out or ROOT)
