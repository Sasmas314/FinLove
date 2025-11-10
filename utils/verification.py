# utils/verification.py

import random
import re
import smtplib
import ssl
from email.mime.text import MIMEText

from utils.settings import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL

EMAIL_PATTERN = re.compile(r"^[^@\s]+@(edu\.fa\.ru|fa\.ru)$", re.IGNORECASE)


def is_valid_university_email(email: str) -> bool:
    return EMAIL_PATTERN.match(email) is not None


def generate_code(length: int = 6) -> str:
    return "".join(random.choice("0123456789") for _ in range(length))


def send_verification_email(to_email: str, code: str):
    subject = "Код подтверждения FinLove"
    body = (
        f"Ваш код подтверждения для бота знакомств FinLove: {code}\n\n"
        "Если вы не запрашивали код, просто игнорируйте это письмо."
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email

    context = ssl.create_default_context()

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls(context=context)
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
