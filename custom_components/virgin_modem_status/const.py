DOMAIN = "virgin_modem_status"
DEFAULT_HOST = "192.168.100.1"
DEFAULT_SCAN_INTERVAL = 90  # seconds
ROUTER_STATUS_PATH = "/getRouterStatus"

# OIDs we care about (trim as needed)
EVENT_TIME_OIDS = [f"1.3.6.1.2.1.69.1.5.8.1.2.{i}" for i in range(1, 21)]
EVENT_MSG_OIDS  = [f"1.3.6.1.2.1.69.1.5.8.1.7.{i}" for i in range(1, 21)]

TROUBLE_KEYWORDS = [
    "partial service", "loss of sync", "no ranging response", "retries exhausted",
    "t3 time-out", "t4 time-out", "sync timing"
]
