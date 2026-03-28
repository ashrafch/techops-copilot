import threading
import time
from collections import defaultdict, deque

_LOCK = threading.Lock()
_WINDOWS: dict[str, deque[float]] = defaultdict(deque)


def is_rate_limited(key: str, max_requests: int, window_seconds: int = 60) -> bool:
    if max_requests <= 0:
        return False

    now = time.time()
    with _LOCK:
        window = _WINDOWS[key]
        cutoff = now - window_seconds
        while window and window[0] <= cutoff:
            window.popleft()

        if len(window) >= max_requests:
            return True

        window.append(now)
        return False


def reset_rate_limit_state() -> None:
    with _LOCK:
        _WINDOWS.clear()
