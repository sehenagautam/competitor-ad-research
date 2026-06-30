from abc import ABC, abstractmethod

class BaseCollector(ABC):
    @abstractmethod
    async def collect(self, query: str):
        pass

    @abstractmethod
    def save(self, data):
        pass
