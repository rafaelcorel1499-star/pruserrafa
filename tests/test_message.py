from sms_parser import DEFAULT_TEMPLATE, render_message, spoken_phrase, validate_template

SENDER = "RAFAEL HERNANDO SANCHEZ CAMPO"


def test_plantilla_original_no_cambia():
    assert spoken_phrase(200, SENDER) == "Recibiste un pago con valor 200 pesos de Rafael Sanchez"
    assert validate_template(DEFAULT_TEMPLATE) is None


def test_plantilla_personalizada():
    t = "Atención: {nombre} te pagó {valor} pesos, gracias"
    assert validate_template(t) is None
    assert render_message(t, 1500, SENDER) == "Atención: Rafael Sanchez te pagó 1500 pesos, gracias"


def test_valor_y_nombre_son_obligatorios():
    assert "{valor}" in validate_template("Pago de {nombre}")
    assert "{nombre}" in validate_template("Pago de {valor}")
    assert validate_template("Hola") is not None


def test_no_acepta_otras_marcas():
    assert validate_template("{valor} {nombre} {otra}") is not None
    assert validate_template("{valor} {nombre} }") is not None


def test_plantilla_invalida_usa_la_original():
    assert render_message("sin datos", 200, SENDER) == "Recibiste un pago con valor 200 pesos de Rafael Sanchez"


def test_valor_con_decimales():
    assert render_message("{valor} de {nombre}", 10.5, "ANA TORRES") == "10 con 50 de Ana Torres"
