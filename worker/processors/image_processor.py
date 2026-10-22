from io import BytesIO
from PIL import Image
from models import ProcessingResult
import uuid


class ImageProcessor:
    async def process(self, file_bytes: bytes, operations: list, job_id: int, db, progress_callback=None) -> list:
        results = []
        img = Image.open(BytesIO(file_bytes))
        img = img.convert("RGB")

        total = len(operations) or 1
        for i, op in enumerate(operations):
            if progress_callback:
                await progress_callback((i / total) * 100)

            if op == "resize":
                resized = img.resize((800, 600), Image.Resampling.LANCZOS)
                buf = BytesIO()
                resized.save(buf, format="JPEG", quality=85)
                buf.seek(0)
                key = f"results/{job_id}/resized_{uuid.uuid4().hex}.jpg"
                from storage import storage
                storage.upload_file(key, buf, buf.getbuffer().nbytes, "image/jpeg")
                results.append(ProcessingResult(
                    job_id=job_id, type="resized", storage_key=key, file_name="resized.jpg"
                ))

            elif op == "compress":
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=50)
                buf.seek(0)
                key = f"results/{job_id}/compressed_{uuid.uuid4().hex}.jpg"
                from storage import storage
                storage.upload_file(key, buf, buf.getbuffer().nbytes, "image/jpeg")
                results.append(ProcessingResult(
                    job_id=job_id, type="compressed", storage_key=key, file_name="compressed.jpg"
                ))

            elif op == "thumbnail":
                thumb = img.copy()
                thumb.thumbnail((200, 200))
                buf = BytesIO()
                thumb.save(buf, format="JPEG", quality=70)
                buf.seek(0)
                key = f"results/{job_id}/thumb_{uuid.uuid4().hex}.jpg"
                from storage import storage
                storage.upload_file(key, buf, buf.getbuffer().nbytes, "image/jpeg")
                results.append(ProcessingResult(
                    job_id=job_id, type="thumbnail", storage_key=key, file_name="thumbnail.jpg"
                ))

        if progress_callback:
            await progress_callback(100.0)
        return results
