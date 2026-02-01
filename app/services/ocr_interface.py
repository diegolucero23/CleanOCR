from abc import ABC, abstractmethod
from typing import Any

class OCRProvider(ABC):
    @abstractmethod
    def generate_content(self, prompts: list, config: Any) -> str:
        """
        Generates content (text) from the underlying model.
        Returns the raw text response.
        """
        pass
