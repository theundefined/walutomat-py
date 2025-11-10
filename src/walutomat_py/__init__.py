# SPDX-FileCopyrightText: 2025-present Your Name <your@email.com>
#
# SPDX-License-Identifier: MIT
"""
A Python library for the Walutomat.pl API
"""

__version__ = "0.0.20251110.201342"

from .client import WalutomatAPIError, WalutomatClient

__all__ = ["WalutomatClient", "WalutomatAPIError"]
