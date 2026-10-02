import os
import sys
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

logger = logging.getLogger("nexus.notifications")


class Notification(BaseModel):
    id: str
    user_id: str
    type: str  # "email", "in_app"
    event: str  # "report_ready", "report_failed"
    title: str
    message: str
    report_id: Optional[str] = None
    retry_action: Optional[Any] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    read: bool = False


class NotificationService:
    _in_memory_notifications: List[Notification] = []
    _sent_emails: List[Any] = []

    @classmethod
    def send_notification(
        cls,
        user_id: str,
        event: str,
        title: str,
        message: str,
        report_id: Optional[str] = None,
        retry_action: Optional[Any] = None,
        user_email: Optional[str] = None,
    ) -> dict:
        notif_id = f"notif_{int(time.time() * 1000)}_{len(cls._in_memory_notifications)}"
        
        # In-app notification
        in_app = Notification(
            id=notif_id,
            user_id=user_id,
            type="in_app",
            event=event,
            title=title,
            message=message,
            report_id=report_id,
            retry_action=retry_action,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        cls._in_memory_notifications.append(in_app)

        # Email notification
        email_record = {
            "id": f"email_{notif_id}",
            "user_id": user_id,
            "to_email": user_email or f"{user_id}@nexus.internal",
            "subject": title,
            "body": message,
            "event": event,
            "report_id": report_id,
            "retry_action": retry_action,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        cls._sent_emails.append(email_record)
        logger.info(
            "[Notification Dispatched] user=%s event=%s title='%s' report_id=%s retry_action=%s",
            user_id, event, title, report_id, bool(retry_action)
        )
        return {"in_app": in_app.dict(), "email": email_record}

    @classmethod
    def notify_report_ready(cls, user_id: str, report_id: str, topic: str, user_email: Optional[str] = None) -> dict:
        return cls.send_notification(
            user_id=user_id,
            event="report_ready",
            title=f"Report Ready: {topic}",
            message=f"Your research report for '{topic}' has completed synthesis and is ready for download.",
            report_id=report_id,
            retry_action=None,
            user_email=user_email,
        )

    @classmethod
    def notify_report_failed(
        cls,
        user_id: str,
        report_id: str,
        topic: str,
        reason: str,
        retry_payload: Optional[Any] = None,
        user_email: Optional[str] = None,
    ) -> dict:
        retry_action = {
            "endpoint": f"/api/reports/{report_id}/retry",
            "method": "POST",
            "payload": retry_payload or {},
        }
        return cls.send_notification(
            user_id=user_id,
            event="report_failed",
            title=f"Report Generation Failed: {topic}",
            message=f"Report synthesis for '{topic}' failed: {reason}. You can retry this request.",
            report_id=report_id,
            retry_action=retry_action,
            user_email=user_email,
        )

    @classmethod
    def get_user_notifications(cls, user_id: str) -> List[Dict[str, Any]]:
        return [n.dict() for n in cls._in_memory_notifications if n.user_id == user_id]

    @classmethod
    def get_sent_emails(cls, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if user_id:
            return [e for e in cls._sent_emails if e["user_id"] == user_id]
        return list(cls._sent_emails)

    @classmethod
    def clear_all(cls) -> None:
        cls._in_memory_notifications.clear()
        cls._sent_emails.clear()
