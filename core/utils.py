import os
import re
import bcrypt
import random
import string
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import session

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PASSWORD_SPECIAL_RE = re.compile(r"[!@#$%^&*()_\-+=\[\]{}|\\:;\"'<>,.?/`~]")

def normalize_email(value):
    return (value or "").strip().lower()

def is_valid_email(email):
    return bool(EMAIL_RE.fullmatch(email or ""))

def validate_password(password, minimum=8):
    if not isinstance(password, str):
        return False, "Password is required"
    if len(password) < minimum:
        return False, f"Password must be at least {minimum} characters"
    if not any(ch.isupper() for ch in password):
        return False, "Password must include at least one uppercase letter"
    if not any(ch.islower() for ch in password):
        return False, "Password must include at least one lowercase letter"
    if not any(ch.isdigit() for ch in password):
        return False, "Password must include at least one number"
    if not PASSWORD_SPECIAL_RE.search(password):
        return False, "Password must include at least one special character"
    return True, None

def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

def verify_password(password, hashed_password):
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password)

def start_user_session(user):
    session.permanent = False
    session["user_id"] = str(user["_id"])
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]


def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def send_email_otp(email, otp, purpose="password_reset"):
    email_host = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    email_port = int(os.getenv("EMAIL_PORT", "587"))
    email_username = os.getenv("EMAIL_USERNAME")
    email_password = os.getenv("EMAIL_PASSWORD")
    email_from = os.getenv("EMAIL_FROM") or email_username
    
    if not email_username or not email_password:
        print(f"DEMO OTP for {email}: {otp}", flush=True)
        return True, None

    try:
        msg_related = MIMEMultipart("related")
        msg_related['From'] = f"BuyMore Security <{email_from}>"
        msg_related['To'] = email
        
        if purpose == "admin_login":
            msg_related['Subject'] = "BuyMore - Admin Login OTP"
            title = "Admin Login Request"
            desc = "We received a request to log in to the admin dashboard. Use the security code below to proceed."
            plain_desc = "Your OTP for admin login is:"
        else:
            msg_related['Subject'] = "BuyMore - Password Reset OTP"
            title = "Password Reset Request"
            desc = "We received a request to reset your password. Use the security code below to proceed."
            plain_desc = "Your OTP for password reset is:"
            
        msg_alt = MIMEMultipart("alternative")
        msg_related.attach(msg_alt)
        
        logo_cid = "favicon"
        
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f7fbf9; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
                .header {{ background: linear-gradient(135deg, #16123f, #2a2566); padding: 30px 20px; text-align: center; }}
                .header img {{ width: 60px; height: 60px; margin-bottom: 10px; filter: brightness(0) invert(1); }}
                .header h1 {{ color: #ffffff; margin: 0; font-size: 24px; letter-spacing: 1px; }}
                .content {{ padding: 40px 30px; text-align: center; color: #16123f; }}
                .content h2 {{ margin-top: 0; font-size: 22px; color: #16123f; }}
                .content p {{ font-size: 16px; color: #4f5673; line-height: 1.6; margin-bottom: 30px; }}
                .otp-box {{ background-color: #f2f8f4; border: 2px dashed #75c9b7; border-radius: 8px; padding: 20px; font-size: 32px; font-weight: bold; color: #16123f; letter-spacing: 5px; margin: 0 auto 30px auto; max-width: 250px; text-align: center; }}
                .footer {{ background-color: #f1f5f9; padding: 20px; text-align: center; font-size: 14px; color: #64748b; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <img src="cid:{logo_cid}" alt="BuyMore Logo" />
                    <h1>BuyMore</h1>
                </div>
                <div class="content">
                    <h2>{title}</h2>
                    <p>{desc}</p>
                    <div class="otp-box">{otp}</div>
                    <p>This code is valid for <strong>10 minutes</strong>. If you didn't request this code, please ignore this email.</p>
                </div>
                <div class="footer">
                    &copy; {datetime.utcnow().year} BuyMore. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        
        msg_alt.attach(MIMEText(f"{plain_desc} {otp}\n\nValid for 10 minutes.", 'plain'))
        msg_alt.attach(MIMEText(html_body, 'html'))
        
        from email.mime.base import MIMEBase
        from email import encoders
        
        favicon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'images', 'favicon.svg')
        try:
            with open(favicon_path, 'rb') as f:
                img = MIMEBase('image', 'svg+xml')
                img.set_payload(f.read())
                encoders.encode_base64(img)
                img.add_header('Content-ID', f'<{logo_cid}>')
                img.add_header('Content-Disposition', 'inline', filename='favicon.svg')
                msg_related.attach(img)
        except Exception as e:
            print(f"Failed to attach favicon: {e}")
        
        server = smtplib.SMTP(email_host, email_port, timeout=30)
        server.starttls()
        server.login(email_username, email_password)
        server.send_message(msg_related)
        server.quit()
        return True, None
    except Exception as e:
        print(f"Email failed: {e}", flush=True)
        return False, str(e)


def create_otp_record(otp, ttl_minutes=10):
    return {
        "otp": otp,
        "expires_at": datetime.utcnow() + timedelta(minutes=ttl_minutes),
        "verified": False
    }

def normalize_text_value(value):
    return (value or "").strip().lower()

def get_current_user_id():
    return session.get("user_id")

