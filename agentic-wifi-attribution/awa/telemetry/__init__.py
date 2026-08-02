"""Telemetry ingestion, normalisation and quality scoring (prompt Module 3)."""

from .quality import IncidentWindow, build_incident_window

__all__ = ["IncidentWindow", "build_incident_window"]
