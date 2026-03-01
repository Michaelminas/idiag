"""WebSocket endpoint for real-time device events."""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services import device_service

router = APIRouter()
logger = logging.getLogger(__name__)

# Connected WebSocket clients — safe under single-threaded asyncio (no await between mutations)
_clients: set[WebSocket] = set()


async def broadcast(event: str, data: dict) -> None:
    """Send an event to all connected WebSocket clients."""
    message = json.dumps({"event": event, "data": data})
    disconnected = []
    for ws in list(_clients):  # iterate a copy
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        _clients.discard(ws)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    _clients.add(ws)
    logger.info("WebSocket client connected (%d total)", len(_clients))
    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"event": "error", "data": {"message": "Invalid JSON"}}))
                continue

            if msg.get("action") == "scan":
                devices = await asyncio.to_thread(device_service.list_connected_devices)
                await ws.send_text(json.dumps({
                    "event": "device_list",
                    "data": {"udids": devices},
                }))
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)
        logger.info("WebSocket client disconnected (%d remaining)", len(_clients))


async def device_poll_loop() -> None:
    """Background task that polls for device connect/disconnect events."""
    known_devices: set[str] = set()

    while True:
        try:
            current = set(device_service.list_connected_devices())

            connected = current - known_devices
            disconnected = known_devices - current

            for udid in connected:
                logger.info("Device connected: %s", udid)
                info = device_service.get_device_info(udid)
                await broadcast("device_connected", {
                    "udid": udid,
                    "info": info.model_dump() if info else {},
                })

            for udid in disconnected:
                logger.info("Device disconnected: %s", udid)
                await broadcast("device_disconnected", {"udid": udid})

            known_devices = current
        except Exception as e:
            logger.error("Device poll error: %s", e)

        await asyncio.sleep(2)
