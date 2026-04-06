import os
from dotenv import load_dotenv

load_dotenv()

# WE portal credentials
LND_NUMBER: str = os.getenv("LND_NUMBER")
LND_PASS: str = os.getenv("LND_PASS")

# Derived account ID (FBB + number without leading digit)
ACCT_ID: str = "FBB" + LND_NUMBER[1:]

# Database
DATABASE_URL: str = os.getenv("DATABASE_URL")
START_GB: int = int(os.getenv("START_GB"))
