from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

from datetime import datetime


def generate_report(
    results,
    title="Report",
    output_file="report.pdf"
):

    doc = SimpleDocTemplate(
        output_file
    )

    styles = getSampleStyleSheet()

    elements = []

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    elements.append(
        Paragraph(
            title,
            styles["Title"]
        )
    )

    elements.append(
        Paragraph(
            f"Generated: {timestamp}",
            styles["Normal"]
        )
    )

    elements.append(
        Spacer(1, 12)
    )

    if not results:

        elements.append(
            Paragraph(
                "No records found.",
                styles["Normal"]
            )
        )

        doc.build(elements)

        return

    headers = [
        h
        for h in results[0].keys()
        if h != "path"
    ]

    data = [headers]

    for item in results:

        row = []

        for header in headers:

            row.append(
                str(
                    item.get(
                        header,
                        ""
                    )
                )
            )

        data.append(row)

    table = Table(data)

    table.setStyle(
        TableStyle([
            (
                "GRID",
                (0, 0),
                (-1, -1),
                1,
                colors.black
            ),
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.lightgrey
            )
        ])
    )

    elements.append(
        table
    )

    doc.build(
        elements
    )