import uuid
from io import BytesIO
from typing import List, Callable, Awaitable, Optional
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from models import ProcessingResult
from storage import storage
from processors.base import BaseProcessor


class ImageProcessor(BaseProcessor):
    async def process(
        self,
        file_bytes: bytes,
        operations: List[str],
        job_id: int,
        db: AsyncSession,
        progress_callback: Optional[Callable[[float], Awaitable[None]]] = None,
    ) -> List[ProcessingResult]:
        results: List[ProcessingResult] = []
        img = Image.open(BytesIO(file_bytes))
        
        # Convert paletted or RGBA to RGB for standard JPEG conversion if needed
        if img.mode in ("RGBA", "P"):
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "RGBA":
                rgb_img.paste(img, mask=img.split()[3])
            else:
                rgb_img.paste(img.convert("RGBA"))
            img = rgb_img
        elif img.mode != "RGB":
            img = img.convert("RGB")

        total_ops = max(1, len(operations))

        for i, op in enumerate(operations):
            # Report stage progress (e.g. 10%, 40%, 70%)
            if progress_callback:
                stage_progress = round(10.0 + (i / total_ops) * 80.0, 1)
                await progress_callback(stage_progress)

            if op == "resize":
                # Standard web resize: max 800x600 keeping aspect ratio
                resized = img.copy()
                resized.thumbnail((800, 600), Image.Resampling.LANCZOS)
                buf = BytesIO()
                resized.save(buf, format="JPEG", quality=85)
                buf.seek(0)
                data = buf.getvalue()

                key = f"results/{job_id}/resize_{uuid.uuid4().hex}.jpg"
                storage.upload_file(key, BytesIO(data), len(data), "image/jpeg")

                results.append(
                    ProcessingResult(
                        job_id=job_id,
                        type="resized",
                        storage_key=key,
                        file_name="resized.jpg",
                        result_metadata={"width": resized.width, "height": resized.height, "bytes": len(data)},
                    )
                )

            elif op == "compress":
                # Aggressive JPEG compression for storage efficiency
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=45, optimize=True)
                buf.seek(0)
                data = buf.getvalue()

                key = f"results/{job_id}/compress_{uuid.uuid4().hex}.jpg"
                storage.upload_file(key, BytesIO(data), len(data), "image/jpeg")

                results.append(
                    ProcessingResult(
                        job_id=job_id,
                        type="compressed",
                        storage_key=key,
                        file_name="compressed.jpg",
                        result_metadata={"bytes": len(data), "quality": 45},
                    )
                )

            elif op == "thumbnail":
                # Square/compact thumbnail 200x200
                thumb = img.copy()
                thumb.thumbnail((200, 200), Image.Resampling.LANCZOS)
                buf = BytesIO()
                thumb.save(buf, format="JPEG", quality=75)
                buf.seek(0)
                data = buf.getvalue()

                key = f"results/{job_id}/thumb_{uuid.uuid4().hex}.jpg"
                storage.upload_file(key, BytesIO(data), len(data), "image/jpeg")

                results.append(
                    ProcessingResult(
                        job_id=job_id,
                        type="thumbnail",
                        storage_key=key,
                        file_name="thumbnail.jpg",
                        result_metadata={"width": thumb.width, "height": thumb.height, "bytes": len(data)},
                    )
                )

        if progress_callback:
            await progress_callback(100.0)

        return results
