# NequiPay Monitor

Aplicación de escritorio para Windows que recibe por un módem USB **A7670G** (con SIM 4G) los SMS de
confirmación de pago de Nequi, los guarda y los anuncia por el altavoz del PC:

> "Recibiste un pago con valor 200 pesos de Rafael Sanchez"

El valor y el nombre se leen del propio SMS:
`notificacion Nequi: el negocio PORTAWARE recibio $200 de RAFAEL HERNANDO SANCHEZ CAMPO el 25/10/2026 a las 02:08 a.m a travez de  Bre-B.`

## Dos programas

| Programa | Para quién | Qué hace |
|---|---|---|
| **NequiPayMonitor.exe** | Cliente | Recibe los SMS y anuncia los pagos. Exige activación en cada PC. |
| **NequiPayKeygen.exe** | Solo el administrador | Genera el serial de un PC a partir de su ID. |

### Activación (licencia por PC)

1. El cliente abre NequiPay Monitor. Si el PC no está activado aparece la ventana **Activación del producto**
   (la app no se puede usar hasta activar) con el **ID del equipo** (ej. `55CQ-BSLC-BPQL-KN5V`) y un botón *Copiar ID*.
2. El cliente le envía ese ID al administrador.
3. El administrador abre **NequiPayKeygen**, pega el ID, pulsa *Generar serial* y le devuelve el serial.
4. El cliente pega el serial y pulsa **Activar**. Queda guardado en `%APPDATA%\NequiPayMonitor\license.json`
   y no vuelve a pedirse en ese PC.

Detalles:
- El serial está firmado (Ed25519) con la **llave privada** del administrador y solo vale para el PC cuyo ID se usó;
  copiarlo a otro PC no sirve. La app solo contiene la llave **pública**, así que no puede fabricar seriales.
- El ID cambia si se reinstala Windows; en ese caso se pide un serial nuevo.
- El keygen necesita `private.key` junto al .exe y guarda cada serial emitido en `seriales_emitidos.csv`.
- **`keygen/private.key` es secreta**: no la subas a GitHub (ya está en `.gitignore`), no la compartas y
  guarda una copia de respaldo. Si la pierdes no podrás generar más seriales; si se filtra, cualquiera podría hacerlo.
  Usa un repositorio **privado**.
- Para cambiar de llaves: `python tools/new_keypair.py --force` (los seriales ya entregados dejan de valer en las
  versiones nuevas de la app).

### Mensaje de voz personalizado

En **Configuración → Mensaje de Voz** puedes cambiar el texto que se anuncia, por ejemplo
`Llegó un pago de {nombre} por {valor} pesos`. Las marcas `{valor}` y `{nombre}` son obligatorias (la app no deja
guardar sin ellas) y se reemplazan con el monto y el remitente reales del SMS. Hay vista previa y botón
*Restaurar original*.

## 1. Compilar el .exe con GitHub Actions

1. Crea un repositorio nuevo en GitHub y sube **el contenido de esta carpeta** (que `.github/` quede en la raíz).
2. Entra a la pestaña **Actions**. El workflow *Build Windows EXE* corre solo con cada `push`
   (o ejecútalo a mano con **Run workflow**).
3. Al terminar, abre la ejecución y descarga **NequiPayMonitor-windows** (`NequiPayMonitor.exe`, para el cliente) y
   **NequiPayKeygen-windows** (`NequiPayKeygen.exe`, solo para ti; ponle al lado tu `private.key`).
4. Opcional: crea un tag (`git tag v1.0.0 && git push --tags`) y `NequiPayMonitor.exe` se publica también en **Releases** (el keygen nunca).

> Windows SmartScreen puede avisar "editor desconocido" porque el .exe no está firmado digitalmente:
> *Más información → Ejecutar de todas formas*.

## 2. Preparar el módem

- Instala el **driver SimTech / SIMCom** del A7670G. Debe aparecer en el Administrador de dispositivos
  (Puertos COM) un puerto tipo *"SimTech HS-USB AT Port"*.
- La SIM debe tener **el PIN desactivado** y estar registrada en la red (la app muestra la señal 4G).
- En **Configuración → Dispositivo USB** deja *Detección automática* o elige el puerto; si no aparece,
  escríbelo en *Agregar manualmente* (ej. `COM5`).

## 3. Voz

El motor principal es **Edge TTS**, que usa las voces neuronales de Microsoft en español colombiano
(**Salomé** y **Gonzalo**, se eligen en *Configuración → Voz y Notificaciones*). Necesita **conexión a internet**.

Si no hay internet (o Edge TTS falla), la app usa automáticamente **la voz de Windows** como respaldo y no vuelve a
intentar con Edge durante 1 minuto para que los anuncios no se retrasen. Para que el respaldo lea bien en español
instala una voz: *Configuración de Windows → Hora e idioma → Voz → Agregar voces* (Español).
El botón **Probar voz** sirve para comprobar el altavoz y la voz elegida.

## Cómo funciona

- Cada ~2 s consulta la SIM (`AT+CMGL`). Los SMS que coinciden con el formato de Nequi se guardan, se anuncian
  y se **borran de la SIM**. Los demás SMS no se tocan.
- Los SMS largos que lleguen en varias partes se unen automáticamente.
- Si el módem se desconecta, reintenta cada 4 s.
- Al cerrar la ventana la app queda en la **bandeja del sistema** (sigue anunciando pagos). Para salir: clic derecho → *Salir*.
- Los SMS de más de 12 h de antigüedad (los que estaban en la SIM antes de abrir la app) se guardan pero no se anuncian.
- Datos en `%APPDATA%\NequiPayMonitor\` (`payments.db`, `config.json`, `logo.png`, `nequipay.log`).
  Si un SMS de Nequi no se reconoce, queda registrado en `nequipay.log`.

## Ejecutar desde código (desarrollo)

```bash
pip install -r requirements.txt
python src/main.py
python keygen/keygen.py   # programa del administrador
python -m pytest        # pruebas del lector de SMS
```
