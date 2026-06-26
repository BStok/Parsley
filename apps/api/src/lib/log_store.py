from collections import defaultdict
import asyncio

# in-memory store: build_id -> list of log lines
build_logs: dict[str, list[str]] = defaultdict(list)

# listeners: build_id -> list of asyncio queues waiting for new lines
build_listeners: dict[str, list[asyncio.Queue]] = defaultdict(list)


def append_log(build_id: str, line: str) -> None:
    """Called by the build thread to add a new log line."""
    build_logs[build_id].append(line)
    # notify all waiting WebSocket clients
    for queue in build_listeners[build_id]:
        queue.put_nowait(line)


def get_logs(build_id: str) -> list[str]:
    """Returns all existing log lines for a build."""
    return build_logs.get(build_id, [])


def subscribe(build_id: str) -> asyncio.Queue:
    """WebSocket client calls this to get a queue of incoming lines."""
    queue = asyncio.Queue()
    build_listeners[build_id].append(queue)
    return queue


def unsubscribe(build_id: str, queue: asyncio.Queue) -> None:
    """Called when WebSocket disconnects."""
    listeners = build_listeners.get(build_id, [])
    if queue in listeners:
        listeners.remove(queue)


def clear(build_id: str) -> None:
    """Called after logs expire (1hr cron job)."""
    build_logs.pop(build_id, None)
    build_listeners.pop(build_id, None)