# config/utils.py

from enum import Enum

class ComplianceZone(Enum):
    """Compliance zones for data handling"""
    GENERAL = "general"
    HIPAA = "hipaa"
    GDPR = "gdpr"
