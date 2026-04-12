from __future__ import annotations

from abc import ABC, abstractmethod


class BaseStage(ABC):
    name: str

    @abstractmethod
    def run(self, ctx: "PipelineContext") -> dict[str, str]:
        raise NotImplementedError
