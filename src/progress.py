_status_callback = None


def set_callback(fn):
    global _status_callback
    _status_callback = fn


def report(message: str):
    if _status_callback:
        _status_callback(message)
