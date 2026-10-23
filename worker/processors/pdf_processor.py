import uuid
from io import BytesIO
from typing import List, Callable, Awaitable, Optional
import fitz  # PyMuPDF
from sqlalchemy.ext.asyncio import AsyncSession
from models import ProcessingResult
from storage import storage
from processors.base import BaseProcessor


class PDFProcessor(BaseProcessor):
    async def process(
        self,
        file_bytes: bytes,
        operations: List[str],
        job_id: int,
        db: AsyncSession,
        progress_callback: Optional[Callable[[float], Awaitable[None]]] = None,
    ) -> List[ProcessingResult]:
        results: List[ProcessingResult] = []
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page_count = len(doc)
        total_ops = max(1, len(operations))

        try:
            for i, op in enumerate(operations):
                if progress_callback:
                    stage_progress = round(10.0 + (i / total_ops) * 80.0, 1)
                    await progress_callback(stage_progress)

                if op == "extract_text":
                    text_parts = []
                    for page_num in range(page_count):
                        page = doc[page_num]
                        text_parts.append(f"--- Page {page_num + 1} ---\n" + page.get_text())
                    
                    full_text = "\n\n".join(text_parts)
                    encoded_text = full_text.encode("utf-8")
                    key = f"results/{job_id}/extracted_text_{uuid.uuid4().hex}.txt"

                    storage.upload_file(key, BytesIO(encoded_text), len(encoded_text), "text/plain")

                    results.append(
                        ProcessingResult(
                            job_id=job_id,
                            type="text",
                            storage_key=key,
                            file_name="extracted_text.txt",
                            result_metadata={"pages": page_count, "char_count": len(full_text)},
                        )
                    )

                elif op == "generate_preview":
                    if page_count > 0:
                        page = doc[0]
                        # 2x scale for crisp rendered preview
                        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
                        png_bytes = pix.tobytes("png")
                        key = f"results/{job_id}/preview_{uuid.uuid4().hex}.png"

                        storage.upload_file(key, BytesIO(png_bytes), len(png_bytes), "image/png")

                        results.append(
                            ProcessingResult(
                                job_id=job_id,
                                type="preview",
                                storage_key=key,
                                file_name="first_page_preview.png",
                                result_metadata={"pages": page_count, "width": pix.width, "height": pix.height},
                            )
                        )

            if progress_callback:
                await progress_callback(100.0)

        finally:
            doc.close()

        return results
