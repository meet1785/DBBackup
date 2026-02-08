"""Slack notification support."""

import logging
import requests

logger = logging.getLogger("db_backup")


def send_slack_notification(webhook_url: str, message: str) -> bool:
    """Send a notification message to a Slack channel via webhook.

    Args:
        webhook_url: Slack incoming webhook URL.
        message: The message text to send.

    Returns:
        True if the notification was sent successfully.
    """
    if not webhook_url:
        logger.debug("No Slack webhook configured – skipping notification.")
        return False

    payload = {"text": message}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info("Slack notification sent successfully.")
            return True
        else:
            logger.warning("Slack notification failed (HTTP %s): %s", resp.status_code, resp.text)
            return False
    except requests.RequestException as exc:
        logger.error("Failed to send Slack notification: %s", exc)
        return False
