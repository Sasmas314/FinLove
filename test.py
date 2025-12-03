import smtplib
from email.mime.text import MIMEText

msg = MIMEText("Тестовое письмо от FinLove бота", "plain", "utf-8")
msg["Subject"] = "FinLove Test"
msg["From"] = "lidiafisher123@gmail.com"
msg["To"] = "lidiafisher123@gmail.com"

server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
server.set_debuglevel(1)  # печать всего диалога с сервером

server.starttls()
server.login("lidiafisher123@gmail.com", "slkk oxya eluc lika")
server.send_message(msg)
server.quit()
