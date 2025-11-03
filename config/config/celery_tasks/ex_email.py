from config.celery_config import app
import resend
from django.conf import settings

resend.api_key = settings.RESEND_API_KEY

@app.task(queue='tasks', name='send_email_task', autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_email_task(to_email: str, subject: str, html_body: str):
    """
    ارسال ایمیل از طریق Resend با Celery
    """
    try:
        params = {
            "from": "Macoui <onboarding@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "html": html_body
        }
        resend.Emails.send(params)
        print(f"✅ Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Email send failed: {e}")
        raise e  # تا Celery بتواند آن را Retry کند