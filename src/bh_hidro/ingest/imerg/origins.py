"""Stable origen_imerg IDs. Lower is better."""

ORIGIN = {
    "ImergCalib": 1,
    "calib": 1,
    "final": 2,
    "late": 3,
    "early": 4,
}

DAILY_ORDER = ("late", "early")


def better_or_equal_already(loaded_origin: int | None, candidate: int) -> bool:
    if loaded_origin is None:
        return False
    return loaded_origin <= candidate
