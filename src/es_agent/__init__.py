"""ERDOS-GREEDY-AGENT — autonomous experimental number theory."""

__version__ = "0.1.0"

from .agent import GreedyAgent  # noqa: F401
from .domain import (greedy_index, greedy_witness, scan,  # noqa: F401
                     step_certificate)
