"""One-shot introduction email to a friend about the kite alert service.

Triggered manually via GitHub Actions (workflow `intro-email.yml`).
Reuses GMAIL_USER / GMAIL_APP_PASSWORD / FRIEND_EMAIL / CC_EMAIL secrets.
"""

import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
FRIEND_EMAIL = os.environ.get("FRIEND_EMAIL")
CC_EMAIL = os.environ.get("CC_EMAIL")
DASHBOARD_URL = os.environ.get(
    "DASHBOARD_URL",
    "https://julien-lavergne-roberge.github.io/kite-quebec-alerts/",
)

SUBJECT = "🪁 Nouveau service météo kite (c'est moi, pas un spammeur)"

BODY = f"""Salut!

T'es l'heureux bénéficiaire d'un service de notification météo-kitesurf
entièrement gratuit, artisanal, et d'une générosité sans borne. 🪁

Le concept: chaque matin, un bot scanne 3 sources météo (incluant le modèle
d'Environnement Canada) pour 7 spots autour de Montréal, et quand demain
s'annonce EXCELLENT (3h+ consécutives de vent 14-24 nœuds dans la bonne
direction, température clémente, pas de pluie forte), un courriel part
automatiquement pour qu'on puisse planifier nos congés kite avec conviction.

Quelques précisions honnêtes:
  • Oui, je suis tanné de checker Windguru à 6h du matin
  • Non, il n'y a pas de bouton « désabonnement » officiel — mais envoie-moi
    juste un texto si ça te saoule et je te retire de la liste
  • Oui, j'ai codé ça avec l'aide de Claude (l'IA d'Anthropic). C'est moi qui
    tape « envoie » cependant, alors toute faute de frappe est la mienne
  • Le dashboard est consultable en tout temps: {DASHBOARD_URL}

Ce courriel-ci n'est qu'un test d'introduction. Les vrais courriels viendront
SEULEMENT quand les conditions sont vraiment excellentes demain — pas tous
les jours, le seuil est exigeant pour pas te déranger pour rien.

Bon kite!
— Julien

PS: Si tu reçois des courriels du bot même quand il fait -20 en janvier,
signale-le-moi, c'est un bug.
"""


def main():
    if not (GMAIL_USER and GMAIL_APP_PASSWORD and FRIEND_EMAIL):
        print("Missing GMAIL_USER / GMAIL_APP_PASSWORD / FRIEND_EMAIL.", file=sys.stderr)
        sys.exit(1)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = SUBJECT
    msg["From"] = GMAIL_USER
    msg["To"] = FRIEND_EMAIL
    if CC_EMAIL:
        msg["Cc"] = CC_EMAIL
    msg.attach(MIMEText(BODY, "plain", "utf-8"))

    recipients = [FRIEND_EMAIL]
    if CC_EMAIL:
        recipients.append(CC_EMAIL)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, recipients, msg.as_string())

    print(f"Intro email sent to {FRIEND_EMAIL}" + (f" (CC {CC_EMAIL})" if CC_EMAIL else ""))


if __name__ == "__main__":
    main()
