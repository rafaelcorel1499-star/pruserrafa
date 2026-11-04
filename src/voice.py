"""Anuncia los pagos por el altavoz.

Motor principal: Edge TTS (voces neuronales de Microsoft, p. ej. es-CO-SalomeNeural). Necesita internet.
Respaldo (sin internet o si Edge falla): voz de Windows, primero pyttsx3 y luego PowerShell (System.Speech).
"""
from __future__ import annotations

import asyncio
import ctypes
import logging
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time

log = logging.getLogger("nequipay")

DEFAULT_VOICE = "es-CO-SalomeNeural"
VOICES = [
    ("Salomé (mujer, Colombia)", "es-CO-SalomeNeural"),
    ("Gonzalo (hombre, Colombia)", "es-CO-GonzaloNeural"),
]

EDGE_TIMEOUT = 10        # segundos máximos para generar el audio con Edge TTS
EDGE_RETRY_AFTER = 60    # tras un fallo (sin internet), no insistir con Edge durante este tiempo


class VoiceAnnouncer:
    def __init__(self, volume_percent: int = 75, voice: str = DEFAULT_VOICE):
        self.volume = max(0, min(100, volume_percent)) / 100
        self.voice = voice or DEFAULT_VOICE
        self._edge_blocked_until = 0.0
        self._q: "queue.Queue[str | None]" = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def set_volume(self, percent: int):
        self.volume = max(0, min(100, percent)) / 100

    def set_voice(self, voice: str):
        self.voice = voice or DEFAULT_VOICE
        self._edge_blocked_until = 0.0  # al cambiar de voz (o al probar) se reintenta Edge de inmediato

    def speak(self, text: str):
        self._q.put(text)

    def stop(self):
        self._q.put(None)

    def _run(self):
        try:  # COM para este hilo (necesario para SAPI en Windows)
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass
        while True:
            text = self._q.get()
            if text is None:
                break
            self._speak_now(text)

    def _speak_now(self, text: str):
        """Edge TTS -> pyttsx3 -> PowerShell. Pasa al siguiente motor si el anterior falla."""
        if time.monotonic() >= self._edge_blocked_until:
            try:
                self._say_edge(text)
                return
            except Exception as exc:
                self._edge_blocked_until = time.monotonic() + EDGE_RETRY_AFTER
                log.warning("Edge TTS no disponible (%s: %s); usando la voz de Windows", type(exc).__name__, exc)
        try:
            self._say_pyttsx3(text)
        except Exception as exc:
            log.warning("pyttsx3 falló (%s); usando PowerShell", exc)
            try:
                self._say_powershell(text)
            except Exception as exc2:
                log.error("No se pudo reproducir la voz: %s", exc2)

    # ------------------------------------------------------------------ Edge TTS (principal)
    def _say_edge(self, text: str):
        import edge_tts

        fd, path = tempfile.mkstemp(prefix="nequipay_", suffix=".mp3")
        os.close(fd)
        try:
            async def synth():
                await asyncio.wait_for(edge_tts.Communicate(text, self.voice).save(path), EDGE_TIMEOUT)
            asyncio.run(synth())
            if os.path.getsize(path) == 0:
                raise RuntimeError("Edge TTS devolvió un audio vacío")
            _play_mp3(path, self.volume)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    # ------------------------------------------------------------------ voz de Windows (respaldo)
    def _say_pyttsx3(self, text: str):
        import pyttsx3
        engine = pyttsx3.init()
        try:
            for v in engine.getProperty("voices"):
                blob = f"{v.name} {v.id}".lower()
                if any(k in blob for k in ("spanish", "español", "es-co", "es-mx", "es-es", "es-us",
                                           "sabina", "helena", "pablo", "laura", "raul", "dalia", "jorge")):
                    engine.setProperty("voice", v.id)
                    break
            engine.setProperty("volume", self.volume)
            engine.setProperty("rate", 165)
            engine.say(text)
            engine.runAndWait()
        finally:
            try:
                engine.stop()
            except Exception:
                pass

    def _say_powershell(self, text: str):
        # El texto va por variable de entorno (nunca dentro del script) -> sin inyección
        script = (
            "Add-Type -AssemblyName System.Speech;"
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            f"$s.Volume = {int(self.volume * 100)};"
            "try { $s.SelectVoiceByHints('NotSet','NotSet',0,[Globalization.CultureInfo]'es-CO') } catch {};"
            "$s.Speak($env:NEQUI_TEXT)"
        )
        env = dict(os.environ, NEQUI_TEXT=text)
        flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env,
                       creationflags=flags, timeout=30, check=False)


def _play_mp3(path: str, volume: float):
    """Reproduce un MP3 y espera a que termine, usando MCI de Windows (sin dependencias extra)."""
    if sys.platform != "win32":
        raise OSError("La reproducción de MP3 solo está implementada para Windows")
    mci = ctypes.windll.winmm
    alias = f"nequipay{threading.get_ident()}"

    def send(cmd: str, check: bool = True) -> None:
        err = mci.mciSendStringW(cmd, None, 0, None)
        if err and check:
            buf = ctypes.create_unicode_buffer(256)
            mci.mciGetErrorStringW(err, buf, 255)
            raise OSError(f"MCI: {buf.value or err} ({cmd.split()[0]})")

    send(f'open "{path}" type mpegvideo alias {alias}')
    try:
        send(f"setaudio {alias} volume to {int(max(0.0, min(1.0, volume)) * 1000)}", check=False)
        send(f"play {alias} wait")
    finally:
        send(f"close {alias}", check=False)
