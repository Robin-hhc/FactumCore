"""Keep DOCX picture locations while omitting decorative image assets."""

from base64 import b64decode
from functools import cache
from io import BytesIO
from pathlib import Path

from .runtime import native_path
from .validation import ContractError, sha256_bytes


_WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_WORD_DRAWING = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
_PICTURE = "{http://schemas.openxmlformats.org/drawingml/2006/picture}"
_BLIP = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
_EMBED = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
_ALTERNATE = "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"
_PNG_DATA = "data:image/png;base64,"


@cache
def docx_picture_backend():
    """Load the DOCX backend when the converter selects Word input."""
    from docling.backend.docx.drawingml import utils as drawingml
    from docling.backend.msword_backend import MsWordDocumentBackend
    from docx.text.paragraph import Paragraph
    from docx.text.run import Run

    class DocxPictureBackend(MsWordDocumentBackend):
        """Track individual body embeddings before Docling separates content layers."""

        def _body_embeddings(self, element):
            if element.tag == _ALTERNATE:
                branch = self._select_alternate_content_branch(element)
                if branch is not None:
                    yield from self._body_embeddings(branch)
                return
            if element.tag == _BLIP and element.get(_EMBED):
                yield element
            for child in element:
                yield from self._body_embeddings(child)

        def convert(self):
            self.body_pictures = dict.fromkeys(self._body_embeddings(self.docx_obj.element.body))
            self.omitted_pictures = set()
            self.libreoffice_missing = set()
            return super().convert()

        def _is_invisible_spacer(self, image):
            if image is None:
                return False
            if image.mode in {"RGBA", "LA"}:
                return image.getchannel("A").getextrema() == (0, 0)
            return image.mode == "RGB" and image.getextrema() == ((255, 255),) * 3

        def _add_picture_to_doc(self, doc, parent, pil_image, is_spacer=False):
            ref = super()._add_picture_to_doc(doc, parent, pil_image, is_spacer=is_spacer)
            if is_spacer:
                self.omitted_pictures.add(ref.cref)
            return ref

        def _record_hidden_pictures(self, elements, refs):
            for element, ref in zip(elements or (), refs, strict=True):
                if _drawing_hidden(element):
                    self.omitted_pictures.add(ref.cref)
                    continue
                if not self._uses_hidden_text:
                    continue
                run = next(element.iterancestors(_WORD + "r"), None)
                paragraph = next(element.iterancestors(_WORD + "p"), None)
                if run is not None and paragraph is not None:
                    paragraph = Paragraph(paragraph, self.docx_obj)
                    if self._is_hidden_run(Run(run, paragraph), self._get_style_chain(paragraph.style)):
                        self.omitted_pictures.add(ref.cref)

        def _handle_pictures(self, drawing_blip, doc):
            refs = super()._handle_pictures(drawing_blip, doc)
            for element, ref in zip(drawing_blip or (), refs, strict=True):
                if element in self.body_pictures:
                    self.body_pictures[element] = ref.cref
            self._record_hidden_pictures(drawing_blip, refs)
            return refs

        def _handle_vml_pictures(self, vml_imagedatas, doc):
            refs = super()._handle_vml_pictures(vml_imagedatas, doc)
            self._record_hidden_pictures(vml_imagedatas, refs)
            return refs

        def _convert_elements_via_docx(self, elements, element_tag=None):
            image = super()._convert_elements_via_docx(elements, element_tag=element_tag)
            if (image is None and self.docx_to_pdf_converter is None
                    and not isinstance(elements, list) and elements in self.body_pictures):
                relation = self.docx_obj.part.rels.get(elements.get(_EMBED))
                if (relation is not None and not relation.is_external
                        and Path(relation.target_part.partname).suffix.lower() in {".emf", ".wmf"}
                        and drawingml.get_libreoffice_cmd() is None):
                    self.libreoffice_missing.add(elements)
            return image

    return DocxPictureBackend


def _drawing_hidden(element):
    frame = next(element.iterancestors(_WORD_DRAWING + "inline", _WORD_DRAWING + "anchor"), None)
    picture = next(element.iterancestors(_PICTURE + "pic"), None)
    frame_props = frame.find(_WORD_DRAWING + "docPr") if frame is not None else None
    picture_props = picture.find(f"{_PICTURE}nvPicPr/{_PICTURE}cNvPr") if picture is not None else None
    return any(props is not None and props.get("hidden") in {"1", "true"} for props in (frame_props, picture_props))


def _in_page_header(picture, document):
    from docling_core.types.doc import ContentLayer, GroupItem

    node = picture
    while node.parent is not None:
        node = node.parent.resolve(document)
        if isinstance(node, GroupItem) and node.content_layer == ContentLayer.FURNITURE and node.name == "page header":
            return True
    return False


def _png_bytes(picture, limit):
    from PIL import Image

    uri = str(picture.image.uri) if picture.image else ""
    if not uri.startswith(_PNG_DATA):
        return None
    encoded = uri[len(_PNG_DATA):]
    if len(encoded) > limit * 4 // 3 + 4:
        raise ContractError("PARSE_OUTPUT_LIMIT", "DOCX picture exceeds max_output_bytes", picture.self_ref)
    try:
        data = b64decode(encoded, validate=True)
        with Image.open(BytesIO(data), formats=("PNG",)) as image:
            image.verify()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        return None
    return data


def export_docx(document, backend, output, layers, *, max_bytes, max_images):
    """Write local PNGs once, keeping the original references for every picture node."""
    from docling_core.transforms.serializer.common import create_ser_result
    from docling_core.transforms.serializer.markdown import MarkdownDocSerializer, MarkdownParams, MarkdownPictureSerializer
    from docling_core.types.doc import ContentLayer, ImageRefMode

    class PictureSerializer(MarkdownPictureSerializer):
        def __init__(self, omitted):
            self.omitted = omitted

        def _serialize_image_part(self, *, item, **kwargs):
            if item.self_ref in self.omitted:
                return create_ser_result(text="", span_source=item)
            return super()._serialize_image_part(item=item, **kwargs)

    omitted = backend.omitted_pictures | {pic.self_ref for pic in document.pictures if _in_page_header(pic, document)}
    rendered, assets, total_bytes = set(), set(), 0
    for picture in document.pictures:
        if picture.self_ref in omitted:
            picture.image = None
            continue
        data = _png_bytes(picture, max_bytes)
        if data is None:
            picture.image = None
            continue
        ref = "images/" + sha256_bytes(data) + ".png"
        if ref not in assets:
            total_bytes += len(data)
            if total_bytes > max_bytes or len(assets) >= max_images:
                raise ContractError("PARSE_OUTPUT_LIMIT", "DOCX image assets exceed the output budget")
            destination = Path(native_path(output / ref))
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes(data)
            assets.add(ref)
        picture.image.uri = Path(ref)
        rendered.add(picture.self_ref)

    markdown = MarkdownDocSerializer(
        doc=document, picture_serializer=PictureSerializer(omitted=omitted),
        params=MarkdownParams(layers=layers or {ContentLayer.BODY}, image_mode=ImageRefMode.REFERENCED,
                              traverse_pictures=True, mark_meta=True),
    ).serialize().text
    exported = document.export_to_dict()
    for picture in exported.get("pictures", []):
        if picture.get("image"):
            picture["image"]["uri"] = picture["image"]["uri"].replace("\\", "/")
    accounted_for = rendered | omitted
    missing = sum(ref not in accounted_for for ref in backend.body_pictures.values())
    needs_libreoffice = any(backend.body_pictures[element] not in accounted_for
                            for element in backend.libreoffice_missing)
    return markdown, exported, omitted, missing, needs_libreoffice
