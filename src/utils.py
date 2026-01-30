import platform

CLI_VERSION = "0.1.5"  # Match current gemini-cli version

# ====================== User Agent Configuration ======================

GEMINICLI_USER_AGENT = f"GeminiCLI/{CLI_VERSION} (Windows; AMD64)"
ANTIGRAVITY_USER_AGENT = "antigravity/2.0.0 (Windows; AMD64)"


def get_user_agent():
    """Generate User-Agent string matching gemini-cli format."""
    version = CLI_VERSION
    system = platform.system()
    arch = platform.machine()
    return f"GeminiCLI/{version} ({system}; {arch})"


def get_antigravity_user_agent():
    """Generate User-Agent string for Antigravity API."""
    return ANTIGRAVITY_USER_AGENT


# ====================== OAuth Configuration ======================

# Antigravity OAuth Configuration
ANTIGRAVITY_CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
ANTIGRAVITY_CLIENT_SECRET = "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"
