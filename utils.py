import re
from typing import Optional, Dict, Any

def parse_utm_params(text: str) -> Dict[str, str]:
    """Парсинг UTM-параметров из текста."""
    utm_params = {}
    patterns = {
        'utm_source': r'[?&]utm_source=([^&]+)',
        'utm_medium': r'[?&]utm_medium=([^&]+)',
        'utm_campaign': r'[?&]utm_campaign=([^&]+)'
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            utm_params[key] = match.group(1)
    
    return utm_params

def extract_referral_id(text: str) -> Optional[int]:
    """Извлечение referral ID из текста."""
    match = re.search(r'[?&]ref=([0-9]+)', text)
    if match:
        return int(match.group(1))
    return None

def get_command_with_args(text: str) -> tuple:
    """Извлечение команды и аргументов из сообщения."""
    parts = text.strip().split()
    if not parts:
        return None, []
    
    command = parts[0].lower()
    args = parts[1:]
    return command, args