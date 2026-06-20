"""
Global Nexus OS configuration.

This file loads all environment variables
and exposes them to the application.
"""

import os

from dotenv import load_dotenv

# Load .env file from project root
load_dotenv()

# OpenAlex API key
OPENALEX_API_KEY = os.getenv(
    "OPENALEX_API_KEY"
)