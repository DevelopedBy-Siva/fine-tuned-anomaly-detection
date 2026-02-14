import re
import hashlib


def normalize_message(message: str) -> str:
    """
    Remove variable parts (IDs, numbers, timestamps) to create stable pattern.
    This is KEY to clustering similar errors together.
    """
    msg = message

    msg = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "UUID",
        msg,
        flags=re.IGNORECASE,
    )

    msg = re.sub(r"ORD-\d+", "ORD-N", msg)

    msg = re.sub(r"user_id=\d+", "user_id=N", msg)

    msg = re.sub(r"upload_\d+", "upload_N", msg)

    msg = re.sub(r"(?<!\d)(\d+)(?!s|ms|MB)", "N", msg)

    msg = re.sub(r"/tmp/\S+", "/tmp/FILE", msg)

    msg = re.sub(r"token=[0-9a-f]+", "token=HASH", msg)

    msg = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", msg)

    return msg.strip()


def generate_signature(source: str, parsed_log) -> str:
    """
    Create stable hash for clustering similar logs.
    Same error pattern = same signature, regardless of variable data.
    """
    components = [
        source,
        parsed_log.level,
        normalize_message(parsed_log.message),
    ]

    if parsed_log.exception_type:
        components.append(parsed_log.exception_type)

    key = "|".join(components)
    return hashlib.md5(key.encode()).hexdigest()
