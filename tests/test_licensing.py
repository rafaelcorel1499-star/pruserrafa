import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import keygen_core
import licensing

PC = "K7QD-2XHM-PA4T-7RWB"


@pytest.fixture()
def pair():
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    return key, pub


def test_machine_id_estable_y_con_formato():
    a, b = licensing.machine_id(), licensing.machine_id()
    assert a == b and licensing.normalize_pc_id(a) == a


def test_normalize_pc_id():
    assert licensing.normalize_pc_id("k7qd 2xhm-pa4t7rwb") == PC
    assert licensing.normalize_pc_id("corto") is None
    assert licensing.normalize_pc_id("") is None


def test_serial_valido_solo_en_su_equipo(pair):
    key, pub = pair
    serial = keygen_core.generate_serial(key, PC)
    assert licensing.verify_serial(serial, PC, pub)
    assert licensing.verify_serial(serial.lower().replace("-", " "), "k7qd2xhmpa4t7rwb", pub)  # tolerante al formato
    assert not licensing.verify_serial(serial, "AAAA-BBBB-CCCC-DDDD", pub)  # otro PC


def test_serial_alterado_o_de_otro_admin(pair):
    key, pub = pair
    serial = keygen_core.generate_serial(key, PC)
    bad = serial[:-1] + ("A" if serial[-1] != "A" else "B")
    assert not licensing.verify_serial(bad, PC, pub)
    assert not licensing.verify_serial(serial[:-10], PC, pub)
    assert not licensing.verify_serial("", PC, pub)
    assert not licensing.verify_serial("!!!", PC, pub)
    other_pub = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    assert not licensing.verify_serial(serial, PC, other_pub)


def test_keygen_rechaza_id_invalido(pair):
    with pytest.raises(ValueError):
        keygen_core.generate_serial(pair[0], "1234")


def test_guardar_y_activar(monkeypatch, tmp_path, pair):
    key, pub = pair
    monkeypatch.setattr(licensing, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(licensing, "PUBLIC_KEY_HEX", pub)
    assert not licensing.is_activated()
    licensing.save_serial(keygen_core.generate_serial(key, licensing.machine_id()))
    assert licensing.is_activated()
    licensing.save_serial(keygen_core.generate_serial(key, PC))  # serial de otro PC
    assert not licensing.is_activated()


def test_historial_csv(tmp_path):
    keygen_core.log_issued(tmp_path, "Cliente 1", PC, "SERIAL")
    keygen_core.log_issued(tmp_path, "Cliente 2", PC, "SERIAL2")
    lines = (tmp_path / "seriales_emitidos.csv").read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 3 and PC in lines[1]
