from io import BytesIO
import fitz  # PyMuPDF
from models import ProcessingResult
import uuid


class PDFProcessor:
    async def process(self, file_bytes: bytes, operations: list, job_id: int, db, progress_callback=None) -> list:
        results = []
        doc = fitz.open(stream=file_bytes, filetype="pdf")

        total = len(operations) or 1
        for i, op in enumerate(operations):
            if progress_callback:
                await progress_callback((i / total) * 100)

            if op == "extract_text":
                text = ""
                for page in doc:
                    text += page.get_text()
                key = f"results/{job_id}/text_{uuid.uuid4().hex}.txt"
                from storage import storage
                buf = BytesIO(text.encode("utf-8"))
                storage.upload_file(key, buf, len(text.encode()), "text/plain")
                results.append(ProcessingResult(
                    job_id=job_id, type="text", storage_key=key, file_name="extracted.txt"
                ))

            elif op == "generate_preview":
                if len(doc) > 0:
                    page = doc[0]
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                    img_bytes = pix.tobytes("png")
                    key = f"results/{job_id}/preview_{uuid.uuid4().hex}.png"
                    from storage import storage
                    buf = BytesIO(img_bytes)
                    storage.upload_file(key, buf, len(img_bytes), "image/png")
                    results.append(ProcessingResult(
                        job_id=job_id, type="preview", storage_key=key, file_name="preview.png"
                    ))

        doc.close()
        if progress_callback:
            await progress_callback(100.0)
        return results
