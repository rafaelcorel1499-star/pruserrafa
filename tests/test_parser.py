from datetime import datetime

from sms_parser import format_money, parse_amount, parse_sms, short_name, spoken_phrase

SAMPLE = ("notificacion Nequi: el negocio PORTAWARE recibio $200 de RAFAEL HERNANDO SANCHEZ CAMPO "
          "el 25/10/2026 a las 02:08 a.m a travez de  Bre-B.")


def test_sample_sms():
    p = parse_sms(SAMPLE)
    assert p is not None
    assert p.business == "PORTAWARE"
    assert p.amount == 200
    assert p.sender == "RAFAEL HERNANDO SANCHEZ CAMPO"
    assert p.paid_at == datetime(2026, 10, 25, 2, 8)
    assert p.channel == "Bre-B"


def test_spoken_phrase():
    p = parse_sms(SAMPLE)
    assert spoken_phrase(p.amount, p.sender) == "Recibiste un pago con valor 200 pesos de Rafael Sanchez"


def test_pm_and_thousands():
    p = parse_sms("notificación Nequi: el negocio X recibió $1.500 de ANA TORRES el 03/11/2026 "
                  "a las 12:30 p.m. a través de Bre-B.")
    assert p.amount == 1500
    assert p.paid_at == datetime(2026, 11, 3, 12, 30)
    p2 = parse_sms("Nequi: el negocio X recibio $5 de ANA TORRES el 03/11/2026 a las 12:30 a.m. a travez de Bre-B.")
    assert p2.paid_at.hour == 0


def test_not_nequi():
    assert parse_sms("Tu codigo de verificacion es 123456") is None


def test_amount_formats():
    assert parse_amount("200") == 200
    assert parse_amount("1.000") == 1000
    assert parse_amount("1,000") == 1000
    assert parse_amount("1.000,50") == 1000.5
    assert format_money(48500) == "$48,500"


def test_short_name():
    assert short_name("MARIA GOMEZ") == "Maria Gomez"
    assert short_name("JUAN PEREZ GOMEZ") == "Juan Gomez"
    assert short_name("ANA MARIA DE LA CRUZ PEREZ") == "Ana De La Cruz"
    assert short_name("CARLOS") == "Carlos"
