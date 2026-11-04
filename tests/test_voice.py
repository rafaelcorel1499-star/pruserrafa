"""Prueba la cadena de respaldo de la voz: Edge TTS -> pyttsx3 -> PowerShell (sin audio real)."""
import voice
from voice import VoiceAnnouncer


def make(monkeypatch, edge=None, pyttsx3=None, ps=None):
    calls = []

    def fake(name, fn):
        def inner(self, text):
            calls.append(name)
            if fn:
                raise fn
        return inner

    monkeypatch.setattr(VoiceAnnouncer, "_say_edge", fake("edge", edge))
    monkeypatch.setattr(VoiceAnnouncer, "_say_pyttsx3", fake("pyttsx3", pyttsx3))
    monkeypatch.setattr(VoiceAnnouncer, "_say_powershell", fake("ps", ps))
    return VoiceAnnouncer(75), calls


def test_usa_edge_cuando_funciona(monkeypatch):
    v, calls = make(monkeypatch)
    v._speak_now("hola")
    assert calls == ["edge"]


def test_sin_internet_cae_a_voz_de_windows_y_no_insiste(monkeypatch):
    v, calls = make(monkeypatch, edge=OSError("sin red"))
    v._speak_now("uno")
    v._speak_now("dos")  # Edge está en pausa: va directo a la voz de Windows
    assert calls == ["edge", "pyttsx3", "pyttsx3"]


def test_reintenta_edge_pasada_la_pausa(monkeypatch):
    v, calls = make(monkeypatch, edge=OSError("sin red"))
    v._speak_now("uno")
    v._edge_blocked_until = 0
    v._speak_now("dos")
    assert calls == ["edge", "pyttsx3", "edge", "pyttsx3"]


def test_cadena_completa_hasta_powershell(monkeypatch):
    v, calls = make(monkeypatch, edge=OSError("x"), pyttsx3=RuntimeError("y"))
    v._speak_now("hola")
    assert calls == ["edge", "pyttsx3", "ps"]


def test_set_voice_reactiva_edge(monkeypatch):
    v, calls = make(monkeypatch, edge=OSError("x"))
    v._speak_now("uno")
    v.set_voice("es-CO-GonzaloNeural")
    assert v.voice == "es-CO-GonzaloNeural" and v._edge_blocked_until == 0
