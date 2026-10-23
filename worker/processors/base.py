from abc import ABC, abstractmethod
from typing import Callable, Awaitable, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from models import ProcessingResult


class BaseProcessor(ABC):
    """
    Common abstraction for file processors.
    """

    @abstractmethod
    async def process(
        self,
        file_bytes: bytes,
        operations: List[str],
        job_id: int,
        db: AsyncSession,
        progress_callback: Optional[Callable[[float], Awaitable[None]]] = None,
    ) -> List[ProcessingResult]:
        """
        Process the input file bytes for specified operations.
        Returns a list of ProcessingResult objects to be persisted.
        """
        pass
