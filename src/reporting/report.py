"""Report generation for violation evidence."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from src.config import AppConfig
from src.models import EvidencePacket
from src.utils.geocoder import ReverseGeocoder

logger = logging.getLogger(__name__)

# IST timezone offset
IST = timezone(timedelta(hours=5, minutes=30))

# Violation type display names
VIOLATION_DISPLAY_NAMES = {
    "no_helmet": "Riding Without Helmet",
    "red_light_jump": "Red Light Violation",
    "wrong_side": "Wrong Side Driving",
}


@dataclass
class Report:
    """A generated violation report ready for sending."""
    subject: str
    html_body: str
    text_body: str
    attachments: list[tuple[str, bytes]] = field(default_factory=list)
    violation_id: str = ""


class ReportGenerator:
    """Generates human-readable violation reports using Jinja2 templates."""

    def __init__(self, config: AppConfig, template_dir: str = "config",
                 geocoder: Optional[ReverseGeocoder] = None):
        self._config = config
        self._geocoder = geocoder
        template_path = Path(template_dir)
        if template_path.exists():
            self._env = Environment(
                loader=FileSystemLoader(str(template_path)),
                autoescape=True,
            )
        else:
            self._env = None
            logger.warning("Template directory not found: %s", template_dir)

    def generate(self, evidence: EvidencePacket) -> Report:
        """Generate a report from an evidence packet.

        Args:
            evidence: The evidence packet to generate a report for.

        Returns:
            Report object with HTML/text body and attachments.
        """
        violation = evidence.violation
        vtype = violation.violation_type.value if violation else "unknown"
        display_name = VIOLATION_DISPLAY_NAMES.get(vtype, vtype)

        # Format timestamp in IST
        timestamp = violation.timestamp if violation else datetime.now(timezone.utc)
        timestamp_ist = timestamp.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S IST")

        # GPS info
        gps_lat = violation.gps.latitude if violation and violation.gps else None
        gps_lon = violation.gps.longitude if violation and violation.gps else None
        maps_url = ""
        location_address = ""
        location_short = ""
        if gps_lat and gps_lon:
            maps_url = f"https://www.google.com/maps?q={gps_lat},{gps_lon}"
            # Reverse geocode to get address
            if self._geocoder:
                try:
                    geo = self._geocoder.reverse(gps_lat, gps_lon)
                    if geo:
                        location_address = geo.medium_address
                        location_short = geo.short_address
                except Exception as e:
                    logger.warning("Geocoding failed in report: %s", e)

        # Template context
        ctx = {
            "violation_id": evidence.violation_id,
            "violation_type": display_name,
            "timestamp_ist": timestamp_ist,
            "gps_lat": gps_lat,
            "gps_lon": gps_lon,
            "maps_url": maps_url,
            "location_address": location_address,
            "location_short": location_short,
            "plate_text": violation.plate_text if violation else None,
            "plate_confidence": violation.plate_confidence if violation else 0,
            "overall_confidence": violation.confidence if violation else 0,
            "cloud_verified": evidence.metadata.get("cloud_verified", False),
            "cloud_provider": self._config.cloud.provider,
        }

        # Render HTML
        html_body = self._render_html(ctx)

        # Generate plain text
        text_body = self._generate_text(ctx)

        # Subject line
        subject = f"Traffic Violation Report: {display_name} [{evidence.violation_id[:8]}]"

        # Attachments: include best frames
        attachments = []
        for i, jpeg_data in enumerate(evidence.best_frames_jpeg):
            attachments.append((f"evidence_{i:02d}.jpg", jpeg_data))

        return Report(
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            attachments=attachments,
            violation_id=evidence.violation_id,
        )

    def _render_html(self, ctx: dict) -> str:
        """Render HTML email body from template."""
        if self._env is None:
            return self._generate_text(ctx)
        try:
            template = self._env.get_template("email_template.html")
            return template.render(**ctx)
        except Exception as e:
            logger.warning("Template rendering failed: %s", e)
            return self._generate_text(ctx)

    @staticmethod
    def _generate_text(ctx: dict) -> str:
        """Generate plain text report."""
        lines = [
            "TRAFFIC VIOLATION REPORT",
            "=" * 40,
            f"Violation ID: {ctx['violation_id']}",
            f"Type: {ctx['violation_type']}",
            f"Date/Time: {ctx['timestamp_ist']}",
        ]

        if ctx.get("gps_lat") and ctx.get("gps_lon"):
            lines.append(f"Location: {ctx['gps_lat']}, {ctx['gps_lon']}")
            if ctx.get("location_address"):
                lines.append(f"Address: {ctx['location_address']}")
            lines.append(f"Maps: {ctx['maps_url']}")
        else:
            lines.append("Location: GPS data unavailable")

        if ctx.get("plate_text"):
            lines.append(
                f"License Plate: {ctx['plate_text']} "
                f"({ctx['plate_confidence'] * 100:.0f}% confidence)"
            )

        lines.append(f"Overall Confidence: {ctx['overall_confidence'] * 100:.1f}%")

        if ctx.get("cloud_verified"):
            lines.append(f"Cloud Verified: Yes ({ctx['cloud_provider']})")

        lines.extend([
            "",
            "DISCLAIMER: This is a potential traffic violation detected by an",
            "automated system. The evidence is submitted for review and should",
            "not be treated as a definitive accusation.",
        ])

        return "\n".join(lines)
