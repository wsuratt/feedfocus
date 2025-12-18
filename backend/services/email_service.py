"""Email Service for FeedFocus Lite using AWS SES"""
import os
import sqlite3
import secrets
from typing import List, Dict
from datetime import datetime

try:
    import boto3
    from botocore.exceptions import ClientError
    SES_AVAILABLE = True
except ImportError:
    SES_AVAILABLE = False

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")


class EmailService:
    """Send emails via AWS SES"""

    def __init__(self):
        self.from_email = os.getenv('FROM_EMAIL', 'insights@feedfocus.app')
        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')

        if SES_AVAILABLE:
            self.ses_client = boto3.client(
                'ses',
                region_name=self.aws_region,
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
        else:
            self.ses_client = None

    def send_insights_email(self, email: str, topic: str, insights: List[Dict]) -> bool:
        """
        Send insights email to user.

        Args:
            email: Recipient email address
            topic: Topic requested
            insights: List of insight dicts with keys: text, source_url, source_domain, quality_score

        Returns:
            True if email sent successfully, False otherwise
        """
        if not SES_AVAILABLE or not self.ses_client:
            print(f"⚠️  AWS SES not configured. Would send email to {email} about {topic}")
            return False

        sub_token = self._generate_subscription_token(email, topic)
        subject = f"Your {topic} insights are ready"
        html_body = self._build_email_html(topic, insights, sub_token)
        text_body = self._build_email_text(topic, insights, sub_token)

        try:
            response = self.ses_client.send_email(
                Source=self.from_email,
                Destination={'ToAddresses': [email]},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                        'Text': {'Data': text_body, 'Charset': 'UTF-8'}
                    }
                }
            )
            print(f"✅ Email sent to {email} - MessageId: {response['MessageId']}")
            return True

        except ClientError as e:
            print(f"❌ Failed to send email: {e.response['Error']['Message']}")
            return False

    def _generate_subscription_token(self, email: str, topic: str) -> str:
        """Generate and store a unique subscription token"""
        token = secrets.token_urlsafe(32)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE lite_leads
            SET subscription_token = ?
            WHERE email = ? AND topic = ?
        """, (token, email, topic))

        conn.commit()
        conn.close()
        return token

    def _build_email_html(self, topic: str, insights: List[Dict], sub_token: str) -> str:
        """Build HTML email body"""
        insights_html = ""
        for i, insight in enumerate(insights, 1):
            insights_html += f"""
            <div style="margin-bottom: 24px; padding: 20px; background: #f8fafc; border-radius: 8px; border-left: 4px solid #3b82f6;">
                <p style="margin: 0 0 12px 0; font-size: 16px; line-height: 1.6; color: #1e293b;">
                    {insight['text']}
                </p>
                <a href="{insight['source_url']}" style="color: #3b82f6; text-decoration: none; font-size: 14px;">
                    → Read more at {insight['source_domain']}
                </a>
            </div>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
                <div style="text-align: center; margin-bottom: 32px;">
                    <h1 style="margin: 0; font-size: 28px; color: #1e293b;">
                        Your {topic} Insights
                    </h1>
                    <p style="margin: 8px 0 0 0; color: #64748b; font-size: 16px;">
                        We curated the best insights for you
                    </p>
                </div>

                {insights_html}

                <div style="margin-top: 40px; padding: 24px; background: #eff6ff; border-radius: 8px; text-align: center;">
                    <p style="margin: 0 0 16px 0; font-size: 16px; color: #1e293b;">
                        Want weekly {topic} insights?
                    </p>
                    <a href="https://feed-focus.com/subscribe?token={sub_token}" style="display: inline-block; background: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 500; margin-bottom: 12px;">
                        Subscribe to Weekly Updates
                    </a>
                    <p style="margin: 12px 0 0 0; font-size: 12px; color: #64748b;">
                        We'll send you fresh {topic} insights every week
                    </p>
                </div>

                <div style="margin-top: 32px; padding-top: 24px; border-top: 1px solid #e2e8f0; text-align: center;">
                    <p style="margin: 0 0 8px 0; font-size: 12px; color: #94a3b8;">
                        FeedFocus · Curated insights delivered to your inbox
                    </p>
                    <a href="https://feed-focus.com/unsubscribe?token={sub_token}" style="color: #94a3b8; text-decoration: none; font-size: 11px;">
                        Unsubscribe
                    </a>
                </div>
            </div>
        </body>
        </html>
        """

    def _build_email_text(self, topic: str, insights: List[Dict], sub_token: str) -> str:
        """Build plain text email body"""
        insights_text = ""
        for i, insight in enumerate(insights, 1):
            insights_text += f"\n{i}. {insight['text']}\n"
            insights_text += f"   Source: {insight['source_url']}\n"

        return f"""
Your {topic} Insights
{'=' * 50}

{insights_text}

{'=' * 50}

Want weekly {topic} insights?
Subscribe: https://feed-focus.com/subscribe?token={sub_token}

---
FeedFocus · Curated insights delivered to your inbox
Unsubscribe: https://feed-focus.com/unsubscribe?token={sub_token}
        """

    def get_top_insights(self, topic: str, limit: int = 10) -> List[Dict]:
        """
        Get top quality insights for a topic from database.

        Args:
            topic: Topic name
            limit: Number of insights to return (default 10)

        Returns:
            List of insight dicts
        """
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, text, source_url, source_domain, quality_score, category
            FROM insights
            WHERE topic = ?
              AND is_archived = 0
              AND quality_score >= 7
            ORDER BY quality_score DESC, engagement_score DESC
            LIMIT ?
        """, (topic, limit))

        insights = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return insights

    def record_lead(self, email: str, topic: str, status: str = 'pending') -> int:
        """
        Record a lite lead submission.

        Args:
            email: User email
            topic: Topic requested
            status: Lead status ('pending', 'immediate', 'queued')

        Returns:
            Lead ID
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR IGNORE INTO lite_leads
            (email, topic, status, created_at)
            VALUES (?, ?, ?, ?)
        """, (email, topic, status, datetime.now().isoformat()))

        lead_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return lead_id

    def mark_email_sent(self, email: str, topic: str, insights_count: int):
        """Mark that email was sent for a lead"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE lite_leads
            SET email_sent_at = ?,
                insights_sent = ?
            WHERE email = ? AND topic = ?
        """, (datetime.now().isoformat(), insights_count, email, topic))

        conn.commit()
        conn.close()
