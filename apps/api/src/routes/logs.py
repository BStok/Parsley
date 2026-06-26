# apps/api/src/routes/logs.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from apps.api.src.lib.log_store import get_logs, subscribe, unsubscribe
from apps.api.src.db.database import get_db
from apps.api.src.db.models import Build
import asyncio

router = APIRouter(tags=["logs"])


@router.websocket("/ws/builds/{build_id}/logs")
async def stream_build_logs(websocket: WebSocket, build_id: str):
    await websocket.accept()

    db = next(get_db())
    build = db.query(Build).filter(Build.build_id == build_id).first()

    if not build:
        await websocket.send_text("Build not found")
        await websocket.close()
        return

    # send existing lines first so late joiners catch up
    for line in get_logs(build_id):
        await websocket.send_text(line)

    # if build already finished, close immediately
    if build.status in ("success", "failed"):
        await websocket.send_text("__done__")
        await websocket.close()
        return

    # subscribe to new lines as they arrive
    queue = subscribe(build_id)

    try:
        while True:
            try:
                line = await asyncio.wait_for(queue.get(), timeout=30)
                if line == "__done__":
                    await websocket.send_text("__done__")
                    break
                await websocket.send_text(line)
            except asyncio.TimeoutError:
                # send a keepalive ping so connection doesn't drop
                await websocket.send_text("__ping__")

    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe(build_id, queue)
        db.close()


@router.websocket("/ws/containers/{container_name}/logs")
async def stream_container_logs(websocket: WebSocket, container_name: str):
    """Streams live runtime logs from a running container."""
    await websocket.accept()

    import subprocess
    import asyncio

    loop = asyncio.get_event_loop()

    try:
        process = await loop.run_in_executor(
            None,
            lambda: subprocess.Popen(
                ["docker", "logs", "--follow", container_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
        )

        async def read_lines():
            while True:
                line = await loop.run_in_executor(None, process.stdout.readline)
                if not line:
                    break
                await websocket.send_text(line.rstrip())

        await read_lines()

    except WebSocketDisconnect:
        process.terminate()
    except Exception as e:
        await websocket.send_text(f"Error: {e}")
        await websocket.close()
    finally:
        if process:
            process.terminate()