"""Probabilistic sampler"""
import random


class Sampler:
    """Probabilistic sampler"""
    
    def __init__(self, sampling_rate: float = 1.0):
        self.sampling_rate = max(0.0, min(1.0, sampling_rate))
    
    def should_sample(self) -> bool:
        """Sample decision"""
        if self.sampling_rate >= 1.0:
            return True
        if self.sampling_rate <= 0.0:
            return False
        return random.random() < self.sampling_rate
