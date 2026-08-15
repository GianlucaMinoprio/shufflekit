"""shufflekit: flash music onto iPod shuffle 3rd/4th gen without iTunes."""

__version__ = "0.1.0"

from .detect import find_shuffles
from .library import ShuffleLibrary
from .itunes_sd import parse_itunes_sd, write_itunes_sd, Track

__all__ = [
    "find_shuffles",
    "ShuffleLibrary",
    "parse_itunes_sd",
    "write_itunes_sd",
    "Track",
    "__version__",
]
