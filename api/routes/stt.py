"""
Speech-to-Text route for Project Nexus.
Accepts audio file upload, returns transcribed text.
Uses Vosk (local, no cloud API).
"""

import json

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect, Query
from starlette.websockets import WebSocketState
from api.dependencies import (
    get_current_user,
    get_request_id,
    CurrentUser
)
from api.schemas.response import APIResponse
from core.logger import get_logger
from db.base import get_db_session
from services.auth_service import AuthService

logger = get_logger(__name__)

router = APIRouter(prefix="/stt", tags=["Speech-to-Text"])


@router.post("/transcribe", response_model=APIResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id)
):
    """
    Transcribe an audio file to text using Vosk.
    Accepts WAV, WebM, or raw PCM audio.
    Returns {"text": "transcribed text..."}.
    """
    from services.stt_service import stt_service

    if not stt_service.is_available:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "STT_UNAVAILABLE",
                "message": "Speech-to-text service is not available. "
                           "Vosk model may not be installed."
            }
        )

    # Validate file size (max 25MB for audio)
    MAX_AUDIO_SIZE = 30 * 1024 * 1024
    content = await audio.read()

    if len(content) > MAX_AUDIO_SIZE:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "AUDIO_TOO_LARGE",
                "message": f"Audio file too large. Max size is 25MB."
            }
        )

    if len(content) < 100:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "AUDIO_TOO_SHORT",
                "message": "Audio file is too short or empty."
            }
        )

    try:
        text = stt_service.transcribe(content)

        logger.info(
            "stt_transcription_completed",
            user_id=current_user.id,
            audio_size_bytes=len(content),
            text_length=len(text),
            filename=audio.filename
        )

        return APIResponse.ok({
            "text": text,
            "audio_size_bytes": len(content),
            "filename": audio.filename
        }, request_id)

    except Exception as e:
        logger.error(
            "stt_transcription_failed",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "STT_ERROR",
                "message": "Transcription failed. Please try again."
            }
        )


@router.get("/status", response_model=APIResponse)
async def stt_status(
    request_id: str = Depends(get_request_id)
):
    """Check if STT service is available."""
    from services.stt_service import stt_service

    return APIResponse.ok({
        "available": stt_service.is_available,
        "engine": "vosk"
    }, request_id)


@router.websocket("/stream")
async def stt_stream(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    sample_rate: int = Query(default=16000)
):
    from services.stt_service import stt_service

    await websocket.accept()

    if not stt_service.is_available:
        await websocket.send_json({"type": "error", "message": "STT unavailable"})
        await websocket.close(code=1011)
        return

    if token:
        try:
            with get_db_session() as db:
                AuthService(db).validate_token(token)
        except Exception:
            await websocket.send_json({"type": "error", "message": "Unauthorized"})
            await websocket.close(code=1008)
            return

    recognizer = stt_service.create_recognizer(sample_rate)
    if not recognizer:
        await websocket.send_json({"type": "error", "message": "Recognizer init failed"})
        await websocket.close(code=1011)
        return

    try:
        await websocket.send_json({"type": "ready"})
    except Exception:
        await websocket.close()
        return

    try:
        while True:
            message = await websocket.receive()
            if message.get("bytes"):
                data = message["bytes"]
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "")
                    if text:
                        await websocket.send_json({"type": "final", "text": text})
                else:
                    partial = json.loads(recognizer.PartialResult()).get("partial", "")
                    await websocket.send_json({"type": "partial", "text": partial})
            elif message.get("text"):
                if message["text"] == "stop":
                    break
    except (WebSocketDisconnect, RuntimeError):
        return
    except Exception as e:
        logger.error("stt_stream_error", error=str(e))
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_json({"type": "error", "message": "Stream failed"})
            except Exception:
                pass
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                final = json.loads(recognizer.FinalResult()).get("text", "")
                if final:
                    await websocket.send_json({"type": "final", "text": final})
            except Exception:
                pass
            try:
                await websocket.close()
            except Exception:
                pass
