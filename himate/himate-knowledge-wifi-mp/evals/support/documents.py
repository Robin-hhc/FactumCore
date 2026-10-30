"""Synthetic native documents and isolated Git commands."""
import io
import os
import subprocess

def git(repository, *arguments):
    return subprocess.check_output([
        "git", "-c", "core.hooksPath=" + os.devnull, "-c", "core.autocrlf=false",
        "-c", "user.name=Isolated fixture", "-c", "user.email=fixture@example.invalid",
        "-C", str(repository), *arguments,
    ], stderr=subprocess.STDOUT).decode().strip()


def document_bytes(kind):
    text = "Capture marker is a documented rule."
    if kind == "md":
        return ("# Source\n" + text + "\n").encode(), {"kind": "lines", "start": 1, "end": 2}
    if kind == "docx":
        import docx
        document = docx.Document()
        document.add_paragraph(text)
        stream = io.BytesIO()
        document.save(stream)
        return stream.getvalue(), {"kind": "paragraph", "paragraph": 1}
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=100)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    content = DecodedStreamObject()
    content.set_data(("BT /F1 12 Tf 10 50 Td (" + text + ") Tj ET").encode())
    page[NameObject("/Contents")] = writer._add_object(content)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue(), {"kind": "page", "page": 1}
