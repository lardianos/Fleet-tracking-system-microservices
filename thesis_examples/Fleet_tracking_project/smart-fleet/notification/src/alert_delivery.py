import logging
import os
import smtplib

from datetime import datetime, timezone
from email.message import EmailMessage
from uuid import NAMESPACE_URL, uuid5

logger = logging.getLogger(__name__)


def deliver_alert(alert, context, producer, completed):
    plate = context["plate_number"]

    title = f"Fleet alert: {alert['rule_id']} - {plate}"
    message = f"Rule {alert['rule_id']} was triggered for vehicle {plate}."

    if alert["rule_id"] == "SPEED_LIMIT":
        title = f"Speed limit exceeded - {plate}"
        message = (
            f"Speed {alert['speed_kmh']} km/h exceeded "
            f"the {alert['speed_limit_kmh']} km/h limit."
        )

    event_time = datetime.fromtimestamp(
        alert["timestamp_ms"] / 1000,
        timezone.utc,
    ).isoformat()

    for recipient in context["recipients"]:
        user_id = recipient["user_id"]

        notification_id = str(uuid5(
            NAMESPACE_URL,
            f"smart-fleet:{alert['alert_id']}:{user_id}",
        ))

        dashboard_key = (user_id, "dashboard")
        email_key = (user_id, "email")

        if "dashboard" in recipient["channels"] and dashboard_key not in completed:
            # Κάθε ειδοποίηση αφορά συγκεκριμένο Keycloak user.
            event = {
                "event_type": "notification.created",
                "recipient_user_id": user_id,
                "notification_id": notification_id,
                "alert_id": alert["alert_id"],
                "timestamp_ms": alert["timestamp_ms"],
                "title": title,
                "message": message,
                "vehicle_id": alert["vehicle_id"],
                "plate_number": plate,
                "driver_name": context["driver_name"],
                "rule_id": alert["rule_id"],
            }

            producer.send(
                os.getenv("KAFKA_TOPIC_DASHBOARD_NOTIFICATIONS", "notifications.dashboard"),
                key=user_id,
                value=event,
            ).get(timeout=10)

            completed.add(dashboard_key)

            logger.info(
                "Dashboard notification published: alert_id=%s user_id=%s",
                alert["alert_id"],
                user_id,
            )

        if "email" in recipient["channels"] and email_key not in completed:
            address = recipient.get("email")

            if not address:
                logger.warning(
                    "Alert email skipped because recipient has no email: user_id=%s",
                    user_id,
                )
                completed.add(email_key)
                continue

            email = EmailMessage()
            email["From"] = os.getenv("SMTP_FROM", "no-reply@smart-fleet.test")
            email["To"] = address
            email["Subject"] = title
            email["Message-ID"] = f"<{notification_id}@smart-fleet.test>"

            email.set_content(
                f"{message}\n\n"
                f"Vehicle: {plate}\n"
                f"Time (UTC): {event_time}\n"
                f"Alert ID: {alert['alert_id']}\n"
            )

            # Τα alert emails αποστέλλονται από το Notification μέσω SMTP.
            with smtplib.SMTP(
                os.getenv("SMTP_HOST", "mailpit"),
                int(os.getenv("SMTP_PORT", "1025")),
                timeout=10,
            ) as smtp:
                smtp.send_message(email)

            completed.add(email_key)

            logger.info(
                "Alert email sent: alert_id=%s user_id=%s",
                alert["alert_id"],
                user_id,
            )