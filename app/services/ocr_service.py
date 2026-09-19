import io
import os
import shutil
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract

from app.config import get_settings

settings = get_settings()


class PageContent:
    def __init__(
        self,
        page_number: int,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        is_ocr: bool = False,
        ocr_confidence: float = 1.0,
        has_images: bool = False,
        warnings: Optional[List[str]] = None,
    ):
        self.page_number = page_number
        self.text = text
        self.blocks = blocks or []
        self.is_ocr = is_ocr
        self.ocr_confidence = ocr_confidence
        self.has_images = has_images
        self.warnings = warnings or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            'page_number': self.page_number,
            'text': self.text,
            'blocks': self.blocks,
            'is_ocr': self.is_ocr,
            'ocr_confidence': self.ocr_confidence,
            'has_images': self.has_images,
            'warnings': self.warnings,
        }


def is_tesseract_available() -> bool:
    """Checks if Tesseract binary is available on the system."""
    if settings.tesseract_cmd and os.path.exists(settings.tesseract_cmd):
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        return True
    
    cmd = shutil.which('tesseract')
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
        return True
        
    # Check common Windows paths
    win_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    ]
    for p in win_paths:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return True
            
    return False


def preprocess_image_for_ocr(image: Image.Image) -> Tuple[Image.Image, List[str]]:
    """
    Applies image preprocessing:
    - Grayscale conversion
    - Contrast enhancement
    - Median filter to reduce noise
    - Returns processed image and warnings
    """
    warnings = []
    width, height = image.size
    
    if width < 600 or height < 600:
        warnings.append('low_resolution_image')

    # Convert to grayscale
    gray_image = image.convert('L')
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(gray_image)
    enhanced = enhancer.enhance(1.8)
    
    # Mild sharpening
    sharpened = enhanced.filter(ImageFilter.SHARPEN)
    
    return sharpened, warnings


def run_ocr_on_pil_image(image: Image.Image) -> Tuple[str, float, List[Dict[str, Any]], List[str]]:
    """Runs OCR on a PIL image using pytesseract if available, or returns fallback."""
    preprocessed, warnings = preprocess_image_for_ocr(image)
    
    if not is_tesseract_available():
        warnings.append('tesseract_not_installed')
        return '', 0.0, [], warnings

    try:
        data = pytesseract.image_to_data(preprocessed, output_type=pytesseract.Output.DICT)
        text_pieces = []
        confidences = []
        blocks = []
        
        n_boxes = len(data['text'])
        current_block = []
        current_block_num = -1

        for i in range(n_boxes):
            word = data['text'][i].strip()
            conf = float(data['conf'][i])
            b_num = data['block_num'][i]

            if word:
                text_pieces.append(word)
                if conf > 0:
                    confidences.append(conf)

                if b_num != current_block_num:
                    if current_block:
                        blocks.append({
                            'text': ' '.join([w['text'] for w in current_block]),
                            'bbox': [
                                min(w['bbox'][0] for w in current_block),
                                min(w['bbox'][1] for w in current_block),
                                max(w['bbox'][2] for w in current_block),
                                max(w['bbox'][3] for w in current_block),
                            ],
                            'confidence': sum(w['conf'] for w in current_block) / len(current_block),
                        })
                        current_block = []
                    current_block_num = b_num

                current_block.append({
                    'text': word,
                    'bbox': [
                        data['left'][i],
                        data['top'][i],
                        data['left'][i] + data['width'][i],
                        data['top'][i] + data['height'][i],
                    ],
                    'conf': conf,
                })

        if current_block:
            blocks.append({
                'text': ' '.join([w['text'] for w in current_block]),
                'bbox': [
                    min(w['bbox'][0] for w in current_block),
                    min(w['bbox'][1] for w in current_block),
                    max(w['bbox'][2] for w in current_block),
                    max(w['bbox'][3] for w in current_block),
                ],
                'confidence': sum(w['conf'] for w in current_block) / len(current_block),
            })

        extracted_text = pytesseract.image_to_string(preprocessed)
        avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.5
        
        if avg_conf < settings.ocr_confidence_threshold:
            warnings.append('low_ocr_confidence')

        return extracted_text, avg_conf, blocks, warnings
    except Exception as exc:
        warnings.append(f'ocr_error: {str(exc)}')
        return '', 0.0, [], warnings


def extract_pages_from_pdf(file_path: str) -> List[PageContent]:
    """Extracts text and layout from PDF using PyMuPDF and OCR for scanned pages."""
    doc = fitz.open(file_path)
    pages: List[PageContent] = []

    try:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_number = page_idx + 1
            warnings: List[str] = []
            
            # Check rotation
            if page.rotation != 0:
                warnings.append(f'page_rotated_{page.rotation}_degrees')

            # Check for embedded images
            image_list = page.get_images(full=True)
            has_images = len(image_list) > 0

            # Extract native text blocks: (x0, y0, x1, y1, "lines", block_no, block_type)
            raw_blocks = page.get_text('blocks')
            text_blocks = []
            full_text_pieces = []

            for b in raw_blocks:
                if b[6] == 0:  # text block
                    block_text = b[4].strip()
                    if block_text:
                        text_blocks.append({
                            'text': block_text,
                            'bbox': [b[0], b[1], b[2], b[3]],
                            'confidence': 1.0,
                        })
                        full_text_pieces.append(block_text)

            full_text = '\n\n'.join(full_text_pieces).strip()

            # If native text is sufficient (digital PDF)
            if len(full_text) >= 40:
                pages.append(
                    PageContent(
                        page_number=page_number,
                        text=full_text,
                        blocks=text_blocks,
                        is_ocr=False,
                        ocr_confidence=1.0,
                        has_images=has_images,
                        warnings=warnings,
                    )
                )
            else:
                # Scanned or image-based PDF page -> Render to image and run OCR
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes('png')
                pil_image = Image.open(io.BytesIO(img_bytes))
                
                ocr_text, ocr_conf, ocr_blocks, ocr_warnings = run_ocr_on_pil_image(pil_image)
                warnings.extend(ocr_warnings)
                
                final_text = ocr_text.strip() if ocr_text.strip() else full_text
                
                pages.append(
                    PageContent(
                        page_number=page_number,
                        text=final_text,
                        blocks=ocr_blocks if ocr_blocks else text_blocks,
                        is_ocr=True,
                        ocr_confidence=ocr_conf if ocr_text.strip() else 0.4,
                        has_images=has_images,
                        warnings=warnings,
                    )
                )
    finally:
        doc.close()

    return pages


def extract_pages_from_image(file_path: str) -> List[PageContent]:
    """Extracts text from image file using PIL and OCR."""
    pil_image = Image.open(file_path)
    ocr_text, ocr_conf, ocr_blocks, warnings = run_ocr_on_pil_image(pil_image)
    
    return [
        PageContent(
            page_number=1,
            text=ocr_text,
            blocks=ocr_blocks,
            is_ocr=True,
            ocr_confidence=ocr_conf,
            has_images=True,
            warnings=warnings,
        )
    ]


def extract_document_pages(file_path: str, mime_type: str) -> List[PageContent]:
    """Universal document extractor dispatching PDF or Image processing."""
    if mime_type == 'application/pdf':
        return extract_pages_from_pdf(file_path)
    elif mime_type.startswith('image/'):
        return extract_pages_from_image(file_path)
    else:
        raise ValueError(f"Unsupported MIME type for document extraction: '{mime_type}'")
