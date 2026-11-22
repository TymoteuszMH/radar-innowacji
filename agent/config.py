import math
import os


def env_int(name: str, default: int, minimum: int, maximum: int | None = None) -> int:
    value = os.getenv(name)
    try:
        result = default if value is None else int(value)
    except ValueError as error:
        raise ValueError(f"{name} musi być liczbą całkowitą") from error
    if result < minimum or (maximum is not None and result > maximum):
        raise ValueError(f"{name} musi być w zakresie [{minimum}, {maximum if maximum is not None else '∞'}]")
    return result


def env_float(name: str, default: float, minimum: float, maximum: float | None = None) -> float:
    value = os.getenv(name)
    try:
        result = default if value is None else float(value)
    except ValueError as error:
        raise ValueError(f"{name} musi być liczbą") from error
    if not math.isfinite(result) or result < minimum or (maximum is not None and result > maximum):
        raise ValueError(f"{name} musi być w zakresie [{minimum}, {maximum if maximum is not None else '∞'}]")
    return result
