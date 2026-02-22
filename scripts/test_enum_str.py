from enum import Enum

class Platform(str, Enum):
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"

print(f"str(Platform.TELEGRAM) = '{str(Platform.TELEGRAM)}'")
print(f"Platform.TELEGRAM.value = '{Platform.TELEGRAM.value}'")
