import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
import datetime
import httpx

class NotificationService:
    """
    Enterprise Notification Dispatcher for Apex Family Diagnostic Lab.
    Handles automated appointment confirmations, fasting instructions, and lab reports
    via GMAIL (SMTP / HTML Email) and WhatsApp (Twilio / Meta / Exotel / Simulation).
    """
    def __init__(self):
        self._refresh_credentials()

    def _refresh_credentials(self):
        """Refreshes credential variables dynamically from environment on each dispatch."""
        self.gmail_host = os.getenv("GMAIL_SMTP_HOST", "smtp.gmail.com").strip()
        self.gmail_port = int(os.getenv("GMAIL_SMTP_PORT", "587").strip())
        self.gmail_sender = os.getenv("GMAIL_SENDER_EMAIL", "").strip()
        self.gmail_password = os.getenv("GMAIL_APP_PASSWORD", "").strip()
        self.gmail_sender_name = os.getenv("GMAIL_SENDER_NAME", "Apex Family Diagnostic Lab").strip()

        # WhatsApp Configuration
        self.whatsapp_provider = os.getenv("WHATSAPP_PROVIDER", "twilio").strip().lower()
        self.whatsapp_api_key = os.getenv("WHATSAPP_API_KEY", "").strip()
        self.whatsapp_phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
        self.twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        self.twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
        self.twilio_whatsapp_from = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886").strip()
        self.meta_whatsapp_token = os.getenv("META_WHATSAPP_TOKEN", "").strip()

    # =========================================================================
    # 1. GMAIL CONFIRMATION DISPATCH (HTML + PLAIN TEXT)
    # =========================================================================
    def send_gmail_confirmation(
        self,
        to_email: str,
        patient_name: str,
        appointment_id: int,
        appointment_type: str,
        scheduled_date: str,
        time_slot: str,
        tests_requested: str,
        pickup_address: str,
        fasting_instructions: str = "10 to 12 hours of overnight fasting (water is permitted). Avoid caffeine and heavy meals.",
        price: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Sends rich HTML and plain-text booking confirmation to the patient's Gmail.
        Operates in live SMTP mode when credentials exist, or high-fidelity simulation mode.
        """
        self._refresh_credentials()
        target_email = to_email or "patient@gmail.com"
        type_label = "Doorstep Home Sample Collection" if appointment_type == "home_collection" else "In-Situ Laboratory Clinic Visit"
        agent_name = os.getenv("AGENT_NAME", "Vinod")
        agent_phone = os.getenv("AGENT_PHONE_NUMBER", "+91 80 4388 8802")
        price_str = f"₹{price}" if isinstance(price, (int, float)) else (str(price) if price else "₹450")

        subject = f"Appointment Confirmed: {type_label} - Apex MediLab (Ref #{appointment_id})"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 20px; }}
            .card {{ background: #ffffff; max-width: 600px; margin: 0 auto; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 14px rgba(0,0,0,0.06); }}
            .header {{ background: linear-gradient(135deg, #0170B9, #005a96); color: #ffffff; padding: 24px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 22px; }}
            .header p {{ margin: 6px 0 0 0; opacity: 0.9; font-size: 14px; }}
            .content {{ padding: 24px; }}
            .badge {{ display: inline-block; background: #e0f2fe; color: #0284c7; padding: 4px 12px; border-radius: 9999px; font-weight: 700; font-size: 12px; }}
            .details-box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 18px 0; }}
            .detail-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed #cbd5e1; font-size: 14px; }}
            .detail-row:last-child {{ border-bottom: none; }}
            .label {{ font-weight: 600; color: #64748b; }}
            .value {{ font-weight: 700; color: #0f172a; text-align: right; }}
            .fasting-alert {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 6px; margin: 18px 0; font-size: 13px; color: #92400e; }}
            .footer {{ background: #f1f5f9; padding: 16px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
          </style>
        </head>
        <body>
          <div class="card">
            <div class="header">
              <h1>Apex Family Diagnostic Laboratory</h1>
              <p>Booking Confirmation & Clinical Pre-Test Instructions</p>
            </div>
            <div class="content">
              <span class="badge">BOOKING CONFIRMED • ID #{appointment_id}</span>
              <p style="margin-top: 14px;">Dear <strong>{patient_name}</strong>,</p>
              <p>Thank you for choosing Apex Family Diagnostic Lab. Your <strong>{type_label}</strong> has been successfully booked by your dedicated care coordinator, <strong>{agent_name}</strong>.</p>
              
              <div class="details-box">
                <div class="detail-row"><span class="label">Appointment ID:</span><span class="value">#{appointment_id}</span></div>
                <div class="detail-row"><span class="label">Service Type:</span><span class="value">{type_label}</span></div>
                <div class="detail-row"><span class="label">Scheduled Date:</span><span class="value">{scheduled_date}</span></div>
                <div class="detail-row"><span class="label">Time Slot:</span><span class="value">{time_slot}</span></div>
                <div class="detail-row"><span class="label">Diagnostic Tests:</span><span class="value">{tests_requested}</span></div>
                <div class="detail-row"><span class="label">Total Fee / Pricing:</span><span class="value" style="color: #059669; font-weight: 800;">{price_str}</span></div>
                <div class="detail-row"><span class="label">Location / Address:</span><span class="value">{pickup_address}</span></div>
              </div>

              <div class="fasting-alert">
                <strong>⚠️ Pre-Test Clinical Guidelines:</strong><br>
                {fasting_instructions}
              </div>

              <p style="font-size: 13px; color: #475569;">
                Our certified phlebotomist will arrive equipped with a sterile vacuum collection kit and temperature-controlled cold box (2°C - 8°C).
                If you have any doubts, questions, or wish to reschedule, simply reply to this email or call {agent_name} at <strong>{agent_phone}</strong>.
              </p>
            </div>
            <div class="footer">
              © {datetime.date.today().year} Apex Family Diagnostic Laboratory • NABL & CAP Accredited • 5580 E. 2nd St, Suite 206
            </div>
          </div>
        </body>
        </html>
        """

        plain_text = (
            f"Apex Family Diagnostic Lab - Booking Confirmed (#{appointment_id})\n\n"
            f"Dear {patient_name},\n"
            f"Your appointment has been confirmed by care coordinator {agent_name}:\n"
            f"• Service: {type_label}\n"
            f"• Date: {scheduled_date}\n"
            f"• Time Slot: {time_slot}\n"
            f"• Tests: {tests_requested}\n"
            f"• Fee / Price: {price_str}\n"
            f"• Address: {pickup_address}\n\n"
            f"Pre-Test Instructions: {fasting_instructions}\n\n"
            f"Support Hotline ({agent_name}): {agent_phone}\n"
        )

        # Send via Live Gmail SMTP if configured
        if self.gmail_sender and self.gmail_password:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"{self.gmail_sender_name} <{self.gmail_sender}>"
                msg["To"] = target_email

                msg.attach(MIMEText(plain_text, "plain"))
                msg.attach(MIMEText(html_body, "html"))

                context = ssl.create_default_context()
                with smtplib.SMTP(self.gmail_host, self.gmail_port, timeout=10) as server:
                    server.starttls(context=context)
                    server.login(self.gmail_sender, self.gmail_password)
                    server.sendmail(self.gmail_sender, target_email, msg.as_string())

                print(f"[Gmail] Successfully sent live confirmation email to {target_email}")
                return {
                    "status": "sent",
                    "provider": "gmail_live_smtp",
                    "recipient": target_email,
                    "subject": subject
                }
            except Exception as e:
                print(f"[Gmail] SMTP error ({e}). Falling back to simulation record.")

        # Simulation Mode
        print(f"[Gmail] Simulation: Formatted confirmation email generated for {target_email} (#{appointment_id})")
        return {
            "status": "simulated_sent",
            "provider": "gmail_simulation",
            "recipient": target_email,
            "subject": subject,
            "preview": plain_text[:200]
        }

    # =========================================================================
    # 2. WHATSAPP CONFIRMATION DISPATCH
    # =========================================================================
    def send_whatsapp_confirmation(
        self,
        to_phone: str,
        patient_name: str,
        appointment_id: int,
        appointment_type: str,
        scheduled_date: str,
        time_slot: str,
        tests_requested: str,
        pickup_address: str,
        fasting_instructions: str = "10 to 12 hours of overnight fasting (water is allowed).",
        price: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Sends formatted WhatsApp message with booking details, fasting rules, and clinic helpline.
        Supports Twilio WhatsApp API, Meta Cloud WhatsApp API, and simulated mode.
        """
        self._refresh_credentials()
        clean_phone = to_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not clean_phone.startswith("+"):
            default_cc = os.getenv("DEFAULT_COUNTRY_CODE", "+91")
            clean_phone = f"{default_cc}{clean_phone}" if len(clean_phone) == 10 else f"+{clean_phone}"

        type_label = "Doorstep Home Sample Collection 🏡" if appointment_type == "home_collection" else "In-Situ Laboratory Clinic Visit 🏥"
        agent_name = os.getenv("AGENT_NAME", "Vinod")
        agent_phone = os.getenv("AGENT_PHONE_NUMBER", "+91 80 4388 8802")
        price_str = f"₹{price}" if isinstance(price, (int, float)) else (str(price) if price else "₹450")

        whatsapp_message = (
            f"✅ *APEX FAMILY DIAGNOSTIC LAB - BOOKING CONFIRMED*\n\n"
            f"Hello *{patient_name}*,\n"
            f"Your appointment has been scheduled by care coordinator *{agent_name}*.\n\n"
            f"📋 *Appointment ID:* #{appointment_id}\n"
            f"🔬 *Service:* {type_label}\n"
            f"📅 *Date:* {scheduled_date}\n"
            f"⏰ *Time Slot:* {time_slot}\n"
            f"🧪 *Tests Requested:* {tests_requested}\n"
            f"💰 *Fee / Amount:* {price_str}\n"
            f"📍 *Location:* {pickup_address}\n\n"
            f"⚠️ *Fasting Guidelines:* {fasting_instructions}\n\n"
            f"🧊 Our phlebotomist will arrive with a sterile vacuum kit and cold chain preservation box.\n\n"
            f"📞 Questions or doubts? Call {agent_name} anytime at *{agent_phone}*."
        )

        # Twilio WhatsApp Dispatch
        if self.twilio_account_sid and self.twilio_auth_token:
            try:
                url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_account_sid}/Messages.json"
                payload = {
                    "From": self.twilio_whatsapp_from,
                    "To": f"whatsapp:{clean_phone}",
                    "Body": whatsapp_message
                }
                with httpx.Client(timeout=8.0) as client:
                    resp = client.post(url, data=payload, auth=(self.twilio_account_sid, self.twilio_auth_token))
                    if resp.status_code in [200, 201]:
                        print(f"[WhatsApp] Live Twilio WhatsApp confirmation sent to {clean_phone}")
                        return {
                            "status": "sent",
                            "provider": "twilio_whatsapp",
                            "recipient": clean_phone,
                            "sid": resp.json().get("sid")
                        }
            except Exception as e:
                print(f"[WhatsApp] Twilio dispatch error ({e}). Operating in simulation.")

        # Meta WhatsApp Cloud API Dispatch
        if self.meta_whatsapp_token and self.whatsapp_phone_id:
            try:
                url = f"https://graph.facebook.com/v18.0/{self.whatsapp_phone_id}/messages"
                headers = {
                    "Authorization": f"Bearer {self.meta_whatsapp_token}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "messaging_product": "whatsapp",
                    "to": clean_phone.replace("+", ""),
                    "type": "text",
                    "text": {"body": whatsapp_message}
                }
                with httpx.Client(timeout=8.0) as client:
                    resp = client.post(url, json=payload, headers=headers)
                    if resp.status_code in [200, 201]:
                        print(f"[WhatsApp] Live Meta WhatsApp confirmation sent to {clean_phone}")
                        return {
                            "status": "sent",
                            "provider": "meta_whatsapp",
                            "recipient": clean_phone
                        }
            except Exception as e:
                print(f"[WhatsApp] Meta dispatch error ({e}).")

        # Simulation Mode
        print(f"[WhatsApp] Simulation: Formatted WhatsApp message dispatched to {clean_phone} (#{appointment_id})")
        return {
            "status": "simulated_sent",
            "provider": "whatsapp_simulation",
            "recipient": clean_phone,
            "preview": whatsapp_message[:220]
        }

    # =========================================================================
    # 3. UNIFIED APPOINTMENT DISPATCH (GMAIL + WHATSAPP)
    # =========================================================================
    def send_appointment_confirmation(
        self,
        patient_name: str,
        patient_phone: str,
        patient_email: Optional[str],
        appointment_id: int,
        appointment_type: str,
        scheduled_date: str,
        time_slot: str,
        tests_requested: str,
        pickup_address: str,
        fasting_instructions: str = "10 to 12 hours of overnight fasting (water is allowed).",
        price: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Triggers simultaneous confirmation on both GMAIL and WHATSAPP.
        """
        email_result = self.send_gmail_confirmation(
            to_email=patient_email or f"{patient_name.lower().replace(' ', '.')}@gmail.com",
            patient_name=patient_name,
            appointment_id=appointment_id,
            appointment_type=appointment_type,
            scheduled_date=scheduled_date,
            time_slot=time_slot,
            tests_requested=tests_requested,
            pickup_address=pickup_address,
            fasting_instructions=fasting_instructions,
            price=price
        )

        whatsapp_result = self.send_whatsapp_confirmation(
            to_phone=patient_phone,
            patient_name=patient_name,
            appointment_id=appointment_id,
            appointment_type=appointment_type,
            scheduled_date=scheduled_date,
            time_slot=time_slot,
            tests_requested=tests_requested,
            pickup_address=pickup_address,
            fasting_instructions=fasting_instructions,
            price=price
        )

        return {
            "appointment_id": appointment_id,
            "gmail": email_result,
            "whatsapp": whatsapp_result,
            "dispatched_at": datetime.datetime.utcnow().isoformat()
        }

# Singleton instance
notification_service = NotificationService()
