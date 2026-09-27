from __future__ import annotations

import smtplib
import logging
from email.mime.text import MIMEText
from typing import Optional

from core.config import get_settings


settings = get_settings()
logger = logging.getLogger(__name__)


class NotificationService:
    _disabled_reason: Optional[str] = None

    @staticmethod
    def is_smtp_configured() -> bool:
        return bool(
            settings.SMTP_HOST
            and settings.SMTP_PORT
            and settings.SMTP_USERNAME
            and settings.SMTP_PASSWORD
            and settings.SMTP_FROM_EMAIL
        )

    @classmethod
    def get_smtp_runtime_status(cls) -> dict:
        return {
            "configured": cls.is_smtp_configured(),
            "disabled_reason": cls._disabled_reason,
        }

    @classmethod
    def send_alpha_code_status(
        cls,
        to_email: str,
        run_id: str,
        status: str,
        summary: Optional[str] = None,
    ) -> None:
        if cls._disabled_reason:
            return

        if not cls.is_smtp_configured() or not to_email:
            return

        subject = f"Nexarch Alpha Code Run {status.upper()} - {run_id}"
        body = "\n".join(
            [
                f"Run ID: {run_id}",
                f"Status: {status}",
                "",
                summary or "Your alpha code generation run has changed status.",
            ]
        )

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = to_email

        try:
            if settings.SMTP_USE_TLS:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
                try:
                    server.starttls()
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
                finally:
                    server.quit()
            else:
                server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
                try:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
                finally:
                    server.quit()
        except Exception as exc:
            error_text = str(exc)
            # Gmail and similar providers return 535 for invalid app credentials.
            # Disable further attempts in this process to avoid repeated noisy logs.
            if "535" in error_text:
                cls._disabled_reason = "SMTP authentication failed (535)."
                logger.warning(
                    "SMTP auth failed; email notifications disabled until restart. "
                    "Use valid SMTP credentials or Gmail App Password. Last run=%s status=%s",
                    run_id,
                    status,
                )
                return

            logger.warning("SMTP notification skipped for run %s (%s): %s", run_id, status, exc)

    @classmethod
    def send_system_architecture_status(
        cls,
        to_email: str,
        repository_name: str,
        architecture_document_key: str,
        status: str,
        summary: Optional[str] = None,
    ) -> dict:
        smtp_status = cls.get_smtp_runtime_status()
        if not to_email:
            return {
                "attempted": False,
                "sent": False,
                "reason": "no-recipient",
                "configured": smtp_status.get("configured", False),
            }

        if cls._disabled_reason:
            return {
                "attempted": False,
                "sent": False,
                "reason": cls._disabled_reason,
                "configured": smtp_status.get("configured", False),
            }

        if not cls.is_smtp_configured() or not to_email:
            return {
                "attempted": False,
                "sent": False,
                "reason": "smtp-not-configured",
                "configured": False,
            }

        subject = f"Nexarch System Architecture {status.upper()} - {repository_name}"
        body = "\n".join(
            [
                f"Repository: {repository_name}",
                f"Architecture Document Key: {architecture_document_key}",
                f"Status: {status}",
                "",
                summary or "System architecture analysis and variant generation status updated.",
            ]
        )

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = to_email

        try:
            if settings.SMTP_USE_TLS:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
                try:
                    server.starttls()
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
                finally:
                    server.quit()
            else:
                server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
                try:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
                finally:
                    server.quit()

            return {
                "attempted": True,
                "sent": True,
                "reason": None,
                "configured": True,
            }
        except Exception as exc:
            error_text = str(exc)
            if "535" in error_text:
                cls._disabled_reason = "SMTP authentication failed (535)."
                logger.warning(
                    "SMTP auth failed; architecture notifications disabled until restart. "
                    "Repo=%s key=%s status=%s",
                    repository_name,
                    architecture_document_key,
                    status,
                )
                return {
                    "attempted": True,
                    "sent": False,
                    "reason": cls._disabled_reason,
                    "configured": True,
                }

            logger.warning(
                "SMTP architecture notification skipped for repo %s (%s): %s",
                repository_name,
                status,
                exc,
            )
            return {
                "attempted": True,
                "sent": False,
                "reason": str(exc),
                "configured": True,
            }
