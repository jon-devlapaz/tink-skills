"""Shared constants for skill-gate analysis modules."""

SCHEMA_VERSION = "1.0.0"

SENSITIVE_ENV_PATTERNS = [
    r"(?:^|_)(?:SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL|PRIVATE|ACCESS_KEY|APIKEY|SIGNING|SESSION)(?:$|_)",
    r"(?:^|_)API_KEY(?:$|_)",
    r"(?:^|_)(?:CLIENT_SECRET|AUTH_TOKEN|REFRESH_TOKEN)(?:$|_)",
]

BENIGN_ENV_NAMES = {
    "USER", "HOME", "PATH", "LANG", "SHELL", "PWD", "TERM", "TMPDIR",
    "EDITOR", "PAGER", "TZ", "HOSTNAME", "LOGNAME"
}
