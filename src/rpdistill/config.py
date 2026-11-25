"""Validated, immutable training configuration without GPU dependencies."""
from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    teacher: str
    student: str
    batch_size: int = 8
    epochs: int = 1
    learning_rate: float = 1e-4
    seed: int = 42

    def __post_init__(self) -> None:
        for name in ("teacher", "student"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a nonempty identifier")
        for name in ("batch_size", "epochs"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if isinstance(self.learning_rate, bool) or not isinstance(
            self.learning_rate, (int, float)
        ) or not math.isfinite(self.learning_rate) or self.learning_rate <= 0:
            raise ValueError("learning_rate must be finite and positive")
        if type(self.seed) is not int or not 0 <= self.seed < 2**32:
            raise ValueError("seed must be an unsigned 32-bit integer")
