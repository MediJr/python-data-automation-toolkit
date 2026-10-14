"""Allow ``python -m data_automation``."""

import sys

from .cli import main

sys.exit(main())
