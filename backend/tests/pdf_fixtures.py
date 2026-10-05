"""Deterministic geometry fixtures: coordinates are independent of extraction."""

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject


def geometry_pdf(pages: list[str], bitmap: bool = False) -> bytes:
    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')}))
    image = DecodedStreamObject()
    image.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'),
        NameObject('/Width'): NumberObject(2), NameObject('/Height'): NumberObject(2),
        NameObject('/ColorSpace'): NameObject('/DeviceRGB'), NameObject('/BitsPerComponent'): NumberObject(8)})
    image.set_data(bytes([30, 90, 160, 80, 150, 210, 210, 120, 40, 30, 90, 160]))
    image_ref = writer._add_object(image) if bitmap else None
    for commands in pages:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
            DictionaryObject({NameObject('/F1'): font})})
        if image_ref is not None:
            page['/Resources'][NameObject('/XObject')] = DictionaryObject({NameObject('/Im1'): image_ref})
        stream = DecodedStreamObject()
        stream.set_data(commands.encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    result = BytesIO()
    writer.write(result)
    return result.getvalue()


def line(text: str, x: int, y: int, size: int = 12) -> str:
    escaped = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    return f'BT /F1 {size} Tf {x} {y} Td ({escaped}) Tj ET\n'
