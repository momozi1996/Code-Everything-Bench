"""Code-Everything Bench: executable evidence for community-sourced tasks.

The core package has no third-party dependencies. Optional layers are loaded
lazily and always report their absence rather than silently degrading:

    playwright  -> browser execution, console capture, 360px overflow
    PyYAML      -> full YAML task specs (JSON always works)
    numpy/scipy -> IRT, bootstrap, effect sizes

This design is deliberate. A benchmark that measures unverified claims must not
itself emit one: if a check could not run, its status is SKIP, never PASS.
"""

__version__ = "0.1.0"
__title__ = "Code-Everything Bench: Can Agents Deliver and Verify What Real Users Actually Ask For?"

from . import config  # noqa: F401

__all__ = ["__version__", "__title__", "config"]
