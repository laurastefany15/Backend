from datetime import date, datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from services.nomina_service import receipt_data

MESES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]


def _money(value):
    if value is None:
        return "$ 0"
    return "$ {:,.2f}".format(value).replace(",", "X").replace(".", ",").replace("X", ".")


def _fecha_larga(iso):
    if not iso:
        return "-"
    fecha = date.fromisoformat(iso)
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


def _periodo_texto(periodo):
    return f"{_fecha_larga(periodo['fecha_inicio'])} al {_fecha_larga(periodo['fecha_fin'])}"


def _conceptos_table(styles, titulo, filas, con_porcentaje=False):
    cell = styles["cell"]
    encabezados = ["Concepto", "Cantidad", "Valor unitario"]
    if con_porcentaje:
        encabezados.append("%")
    encabezados.append("Valor")
    data = [[Paragraph(f"<b>{h}</b>", cell) for h in encabezados]]
    total = 0.0
    for fila in filas:
        valor = fila["valor"] or 0.0
        total += valor
        cantidad = fila["cantidad"]
        unitario = fila["valor_unitario"]
        columnas = [
            Paragraph(fila["nombre"], cell),
            Paragraph("-" if cantidad is None else f"{cantidad:g}", cell),
            Paragraph("-" if unitario is None else _money(unitario), cell),
        ]
        if con_porcentaje:
            pct = fila["porcentaje_aplicado"]
            columnas.append(Paragraph("-" if pct is None else f"{pct:g}%", cell))
        columnas.append(Paragraph(_money(valor), cell))
        data.append(columnas)

    anchos = [70 * mm, 22 * mm, 33 * mm]
    if con_porcentaje:
        anchos.append(18 * mm)
    anchos.append(33 * mm)

    tabla = Table(data, colWidths=anchos, hAlign="LEFT")
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b57")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4d0")),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef2f6")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return titulo, tabla, total


def build_receipt(current_user, nomina_id):
    """Genera el recibo de nómina en PDF y devuelve (bytes, nombre_archivo)."""
    datos = receipt_data(current_user, nomina_id)
    empresa = datos["empresa"]
    contrato = datos["contrato"]
    nomina = datos["nomina"]
    empleado = nomina["empleado"]
    periodo = nomina["periodo"]
    detalles = nomina.get("detalles", [])

    devengados = [d for d in detalles if d["tipo"] == "DEVENGADO"]
    deducciones = [d for d in detalles if d["tipo"] == "DEDUCCION"]

    base_styles = getSampleStyleSheet()
    styles = {
        "titulo": ParagraphStyle(
            "titulo",
            parent=base_styles["Title"],
            fontSize=16,
            textColor=colors.HexColor("#1f3b57"),
            spaceAfter=2,
        ),
        "empresa": ParagraphStyle(
            "empresa", parent=base_styles["Normal"], fontSize=9, leading=12
        ),
        "seccion": ParagraphStyle(
            "seccion",
            parent=base_styles["Heading2"],
            fontSize=11,
            textColor=colors.HexColor("#1f3b57"),
            spaceBefore=10,
            spaceAfter=4,
        ),
        "cell": ParagraphStyle("cell", parent=base_styles["Normal"], fontSize=9, leading=11),
        "pie": ParagraphStyle(
            "pie",
            parent=base_styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#6b7682"),
        ),
    }

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=f"Recibo de nómina {nomina['id']}",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    elementos = []
    elementos.append(Paragraph("Comprobante de pago de nómina", styles["titulo"]))

    encabezado_empresa = [empresa["razon_social"], f"NIT {empresa['nit']}"]
    if empresa.get("direccion"):
        encabezado_empresa.append(empresa["direccion"])
    contacto = " · ".join(
        parte for parte in (empresa.get("telefono"), empresa.get("correo")) if parte
    )
    if contacto:
        encabezado_empresa.append(contacto)
    elementos.append(Paragraph("<br/>".join(encabezado_empresa), styles["empresa"]))
    elementos.append(Spacer(1, 6))

    info = [
        [
            Paragraph("<b>Empleado</b>", styles["cell"]),
            Paragraph(f"{empleado['nombres']} {empleado['apellidos']}", styles["cell"]),
            Paragraph("<b>Documento</b>", styles["cell"]),
            Paragraph(
                f"{empleado['tipo_documento']} {empleado['numero_documento']}",
                styles["cell"],
            ),
        ],
        [
            Paragraph("<b>Cargo</b>", styles["cell"]),
            Paragraph(contrato["cargo"] or "-", styles["cell"]),
            Paragraph("<b>Contrato</b>", styles["cell"]),
            Paragraph(contrato["tipo_contrato"] or "-", styles["cell"]),
        ],
        [
            Paragraph("<b>Periodo</b>", styles["cell"]),
            Paragraph(_periodo_texto(periodo), styles["cell"]),
            Paragraph("<b>Tipo</b>", styles["cell"]),
            Paragraph(periodo["tipo"], styles["cell"]),
        ],
        [
            Paragraph("<b>Estado nómina</b>", styles["cell"]),
            Paragraph(nomina["estado"], styles["cell"]),
            Paragraph("<b>Nómina N.°</b>", styles["cell"]),
            Paragraph(str(nomina["id"]), styles["cell"]),
        ],
    ]
    tabla_info = Table(info, colWidths=[28 * mm, 66 * mm, 28 * mm, 52 * mm], hAlign="LEFT")
    tabla_info.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4d0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dce3ea")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elementos.append(tabla_info)

    titulo_dev, tabla_dev, total_dev = _conceptos_table(
        styles, "Devengados", devengados, con_porcentaje=True
    )
    elementos.append(Paragraph(titulo_dev, styles["seccion"]))
    elementos.append(tabla_dev)

    titulo_ded, tabla_ded, total_ded = _conceptos_table(
        styles, "Deducciones", deducciones, con_porcentaje=True
    )
    elementos.append(Paragraph(titulo_ded, styles["seccion"]))
    elementos.append(tabla_ded)

    elementos.append(Spacer(1, 8))
    totales = [
        [Paragraph("<b>Total devengado</b>", styles["cell"]), Paragraph(_money(nomina["total_devengado"]), styles["cell"])],
        [Paragraph("<b>Total deducciones</b>", styles["cell"]), Paragraph(_money(nomina["total_deducciones"]), styles["cell"])],
        [Paragraph("<b>Neto a pagar</b>", styles["cell"]), Paragraph(f"<b>{_money(nomina['neto_pagar'])}</b>", styles["cell"])],
    ]
    tabla_totales = Table(totales, colWidths=[140 * mm, 34 * mm], hAlign="RIGHT")
    tabla_totales.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEABOVE", (0, 0), (-1, 0), 0.4, colors.HexColor("#b8c4d0")),
                ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#1f3b57")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eef2f6")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elementos.append(tabla_totales)

    pagos = nomina.get("pagos", [])
    if pagos:
        elementos.append(Paragraph("Pagos registrados", styles["seccion"]))
        data_pagos = [
            [Paragraph(f"<b>{h}</b>", styles["cell"]) for h in ("Fecha", "Medio", "Referencia", "Valor")]
        ]
        for pago in pagos:
            data_pagos.append(
                [
                    Paragraph(_fecha_larga(pago["fecha_pago"]), styles["cell"]),
                    Paragraph(pago["medio"], styles["cell"]),
                    Paragraph(pago.get("referencia") or "-", styles["cell"]),
                    Paragraph(_money(pago["valor"]), styles["cell"]),
                ]
            )
        tabla_pagos = Table(data_pagos, colWidths=[52 * mm, 40 * mm, 48 * mm, 34 * mm], hAlign="LEFT")
        tabla_pagos.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b57")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4d0")),
                    ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elementos.append(tabla_pagos)

    elementos.append(Spacer(1, 14))
    generado = datetime.now().strftime("%d/%m/%Y %H:%M")
    elementos.append(
        Paragraph(
            f"Documento generado el {generado}. Este comprobante es informativo "
            "y no reemplaza los soportes contables oficiales.",
            styles["pie"],
        )
    )

    doc.build(elementos)
    buffer.seek(0)

    documento = f"{empleado['numero_documento']}_{periodo['fecha_inicio']}_{periodo['fecha_fin']}"
    return buffer, f"recibo_nomina_{documento}.pdf"
