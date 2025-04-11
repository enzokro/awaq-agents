"""Processing documents for Agents."""

import logging
import pandas as pd
import time
import torch
from pathlib import Path
from docling_core.types.doc import ImageRefMode, PictureItem, TableItem
from docling.datamodel.base_models import FigureElement, InputFormat, Table
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc.document import DoclingDocument

from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    EasyOcrOptions,
    OcrMacOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
    TesseractCliOcrOptions,
    TesseractOcrOptions,
)

OCR_TYPES = {
    "easy": EasyOcrOptions,
    "mac": OcrMacOptions,
    "rapid": RapidOcrOptions,
    "tesseract": TesseractOcrOptions,
    "tesseract_cli": TesseractCliOcrOptions,
}

IMAGE_RESOLUTION_SCALE = 2.0

DEVICE = ("cuda" if torch.cuda.is_available() else 
         ("mps"  if torch.backends.mps.is_available() else 
          "cpu"))

accelerator_device = AcceleratorDevice.MPS if torch.backends.mps.is_available() else AcceleratorDevice.CUDA if torch.cuda.is_available() else AcceleratorDevice.CPU

accelerator_options = AcceleratorOptions(
    num_threads=8, device=accelerator_device
)


class Converter:
    def __init__(self, pipeline_options: PdfPipelineOptions):
        pipeline_options.accelerator_options = accelerator_options
        self.doc_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

    def run(self, input_doc_path: Path):
        return self.doc_converter.convert(input_doc_path)

class SimpleConverter(Converter):
    def __init__(self):
        self.pipeline_options = PdfPipelineOptions()
        self.pipeline_options.do_ocr = False
        self.pipeline_options.do_table_structure = False
        super().__init__(self.pipeline_options)

class TableConverter(Converter):
    def __init__(self):
        self.pipeline_options = PdfPipelineOptions()
        self.pipeline_options.do_ocr = False
        self.pipeline_options.do_table_structure = True
        self.pipeline_options.table_structure_options.do_cell_matching = True
        super().__init__(self.pipeline_options)

class OCRConverter(Converter):
    def __init__(self, ocr_type: str = "easy"):
        self.pipeline_options = PdfPipelineOptions()
        self.pipeline_options.do_ocr = True
        self.pipeline_options.do_table_structure = False
        self.pipeline_options.ocr_options = OCR_TYPES[ocr_type](force_full_page_ocr=True)
        super().__init__(self.pipeline_options)

class ImageConverter(Converter):
    def __init__(self, image_scale: float = IMAGE_RESOLUTION_SCALE):
        self.pipeline_options = PdfPipelineOptions()
        self.pipeline_options.do_ocr = False
        self.pipeline_options.do_table_structure = False
        # Important: For operating with page images, we must keep them, otherwise the DocumentConverter
        # will destroy them for cleaning up memory.
        # This is done by setting PdfPipelineOptions.images_scale, which also defines the scale of images.
        # scale=1 correspond of a standard 72 DPI image
        # The PdfPipelineOptions.generate_* are the selectors for the document elements which will be enriched
        # with the image field
        self.pipeline_options.images_scale = image_scale
        self.pipeline_options.generate_page_images = True
        self.pipeline_options.generate_picture_images = True
        super().__init__(self.pipeline_options)

class FullConverter(Converter):
    def __init__(
            self,
            ocr_type: str = "easy",
            image_scale: float = IMAGE_RESOLUTION_SCALE
    ):
        self.pipeline_options = PdfPipelineOptions()
        self.pipeline_options.do_ocr = True
        self.pipeline_options.do_table_structure = True
        self.pipeline_options.images_scale = image_scale
        self.pipeline_options.generate_page_images = True
        self.pipeline_options.generate_picture_images = True
        self.pipeline_options.table_structure_options.do_cell_matching = True
        self.pipeline_options.ocr_options = OCR_TYPES[ocr_type](force_full_page_ocr=True)
        super().__init__(self.pipeline_options)


def load_docling(json_path: Path):
    return DoclingDocument.load_from_json(json_path)


def convert(
        input_doc_path: Path,
        converter_cls: Converter = FullConverter
    ):
    print(f"Converting document: {input_doc_path.resolve()}")
    start_time = time.time()
    converter = converter_cls()
    conv_res = converter.run(input_doc_path)
    end_time = time.time()
    print(f'Document "{input_doc_path}" converted and processed in {end_time - start_time:.2f} seconds.')
    return conv_res


def parse_document(
        input_doc_path: Path, 
        output_dir: Path, 
        converter_cls: Converter = FullConverter
    ):

    doc_filename = input_doc_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    # convert the document if it does not exist
    output_json = output_dir / f"{doc_filename}.json"
    if not output_json.exists():
        print(f"Converting document: {input_doc_path.resolve()}")
        conv_res = convert(input_doc_path, converter_cls)
        # save the result to a json file
        conv_res.document.save_as_json(output_json)
        doc = conv_res.document
    else:
        print(f"Loading document from previously saved JSON: {output_json.resolve()}")
        doc = DoclingDocument.load_from_json(output_json)

    # stores tables and picture
    tables_elements = []
    pictures_elements = []

    # Save page images
    for page_no, page in doc.pages.items():
        page_no = page.page_no
        page_image_filename = output_dir / f"{doc_filename}-{page_no}.png"
        with page_image_filename.open("wb") as fp:
            page.image.pil_image.save(fp, format="PNG")

    # Save images of figures and tables
    table_counter = 0
    picture_counter = 0
    for element, _level in doc.iterate_items():
        if isinstance(element, TableItem):
            tables_elements.append(element)
            table_df: pd.DataFrame = element.export_to_dataframe()

            table_counter += 1
            element_image_filename = (
                output_dir / f"{doc_filename}-table-{table_counter}.png"
            )
            with element_image_filename.open("wb") as fp:
                element.get_image(doc).save(fp, "PNG")
            # Save the table as csv
            element_csv_filename = output_dir / f"{doc_filename}-table-{table_counter}.csv"
            table_df.to_csv(element_csv_filename)

        if isinstance(element, PictureItem):
            pictures_elements.append(element)
            picture_counter += 1
            element_image_filename = (
                output_dir / f"{doc_filename}-picture-{picture_counter}.png"
            )
            with element_image_filename.open("wb") as fp:
                element.get_image(doc).save(fp, "PNG")

    # Save markdown with externally referenced pictures
    md_filename = output_dir / f"{doc_filename}_image_refs.md"
    doc.save_as_markdown(md_filename, image_mode=ImageRefMode.REFERENCED)

    # Save document as JSON so we can load it later
    doc.save_as_json(output_dir / f"{doc_filename}.json")

    return doc
