# custom_components/virgin_modem_status/const.py

DOMAIN = "virgin_modem_status"

# --- Modem access defaults ---
DEFAULT_HOST = "192.168.100.1"
DEFAULT_COMMUNITY = "public"   # for SNMP v2c (only used if you use SNMP)
DEFAULT_PORT = 161
DEFAULT_SCAN_INTERVAL = 90  # seconds

# Optional HTTP endpoint (keep if you also parse the status page elsewhere)
ROUTER_STATUS_PATH = "/getRouterStatus"

# --- DOCSIS Event Table (standard MIB, 20 rows assumed) ---
# Time and Message columns you already had:
EVENT_TIME_OIDS = [f"1.3.6.1.2.1.69.1.5.8.1.2.{i}" for i in range(1, 21)]  # eventDateTime
EVENT_MSG_OIDS  = [f"1.3.6.1.2.1.69.1.5.8.1.7.{i}" for i in range(1, 21)]  # eventText

# Some modems also expose a PRIORITY/SEVERITY column (OID varies by model/firmware).
# This list is best-effort; keep it empty if your device doesn’t provide it and
# we’ll fall back to priority inference rules below.
EVENT_PRI_OIDS: list[str] = [
    # Example (commented): replace with your modem’s OIDs if you find them via snmpwalk.
    # f"1.3.6.1.2.1.69.1.5.8.1.3.{i}" for i in range(1, 21)  # eventPriority (if present)
]

# Keywords that clearly indicate trouble (used for binary "problem" and priority inference)
TROUBLE_KEYWORDS = [
    "partial service",
    "loss of sync",
    "no ranging response",
    "retries exhausted",
    "t3 time-out",
    "t4 time-out",
    "sync timing",
]

# Priority inference rules (used when PRIORITY OID isn’t available)
# Order matters: first match wins.
PRIORITY_RULES = [
    ("t4 time-out",          "critical"),
    ("loss of sync",         "critical"),
    ("sync timing",          "critical"),
    ("no ranging response",  "critical"),
    ("retries exhausted",    "critical"),
    ("t3 time-out",          "warning"),
    ("partial service",      "warning"),
]

DEFAULT_PRIORITY = "notice"  # fallback when nothing matches

# Custom event names for Logbook entries (used by logbook.py and coordinator)
EVENT_GENERAL = f"{DOMAIN}_event"
EVENT_ERROR   = f"{DOMAIN}_error"
