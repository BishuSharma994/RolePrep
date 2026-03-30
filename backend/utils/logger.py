import time


def log_event(event_type, data):
    print(
        {
            "ts": int(time.time()),
            "event": event_type,
            "data": data,
        }
    )
