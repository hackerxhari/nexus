"""
Shared pytest fixtures and configuration for Nexus test suite.
Sets up minimal env so settings can load without a real .env file.
"""

import os
import sys
from pathlib import Path

import pytest

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Minimum environment required for core.config to load in tests
os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-key-must-be-at-least-32-characters-long",
)
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture
def sample_chunks():
    return [
        "The leave policy entitles every employee to 20 paid days per year.",
        "Expense reports must be submitted within 30 days of incurring the expense.",
        "Security guidelines require all laptops to use full-disk encryption.",
    ]


@pytest.fixture
def sample_sources():
    return ["hr_policy.pdf", "finance_handbook.pdf", "security_policy.pdf"]
