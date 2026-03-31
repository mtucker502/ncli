from netmiko.ssh_dispatcher import CLASS_MAPPER_BASE

VALID_DEVICE_TYPES = set(CLASS_MAPPER_BASE.keys())


def validate_device_config(name: str, config: dict) -> None:
    if "host" not in config:
        raise ValueError(f"Device '{name}' is missing required field 'host'")

    if "device_type" not in config:
        raise ValueError(f"Device '{name}' is missing required field 'device_type'")

    device_type = config["device_type"]
    if device_type not in VALID_DEVICE_TYPES:
        raise ValueError(
            f"Device '{name}' has invalid device_type '{device_type}'. "
            f"Must be one of the supported netmiko device types."
        )
