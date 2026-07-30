#!/usr/bin/env python3
"""Evaluator plugin registry with multi-source discovery.

Discovery order (first match wins, later sources do not override):
1. Explicitly registered evaluators (``@register`` decorator or
   ``register()`` method).
2. Built-in evaluators (loaded via ``_load_builtins()`` at import time).
3. Entry-point group ``model_benchmark.evaluators`` (installed packages).
4. Directory scan of ``tests/evaluators/*.py`` (drop-in plugins).
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from .base import Evaluator


class RegistryError(Exception):
    """Raised when an evaluator cannot be found or loaded."""


# Type alias for the factory function that creates an Evaluator instance.
EvaluatorFactory = Callable[..., Evaluator]


class EvaluatorRegistry:
    """Registry mapping evaluator names to factory callables.

    Use ``get_evaluator(name, **params)`` to obtain an instance.
    """

    def __init__(self) -> None:
        self._factories: dict[str, EvaluatorFactory] = {}
        self._builtins_loaded = False
        self._loaded_entry_points = False
        self._scanned_dirs: set[Path] = set()

    def register(self, name: str, factory: EvaluatorFactory) -> None:
        """Register a factory that creates an Evaluator instance."""
        self._factories[name] = factory

    def unregister(self, name: str) -> None:
        """Remove a registered evaluator."""
        self._factories.pop(name, None)

    def names(self) -> list[str]:
        """Return all known evaluator names."""
        self._ensure_loaded()
        return sorted(self._factories)

    def get_factory(self, name: str) -> EvaluatorFactory:
        """Return the factory for ``name`` or raise RegistryError."""
        self._ensure_loaded()
        if name not in self._factories:
            raise RegistryError(
                f"Unknown evaluator '{name}'. Available: {self.names()}. "
                f"Register via @register or place a plugin in tests/evaluators/."
            )
        return self._factories[name]

    def get_evaluator(self, name: str, **params: Any) -> Evaluator:
        """Instantiate the evaluator ``name`` with ``params``."""
        factory = self.get_factory(name)
        return factory(**params)

    def _ensure_loaded(self) -> None:
        """Lazily load built-in, entry-point, and directory-scanned plugins."""
        self._load_builtins()
        self._load_entry_points()
        self._scan_plugin_dirs()

    def _load_builtins(self) -> None:
        """Import ``.builtin`` which registers built-in evaluators."""
        if self._builtins_loaded:
            return
        self._builtins_loaded = True
        try:
            from . import builtin  # noqa: F401 — import for side effects
        except Exception as e:  # pragma: no cover
            print(
                f"[evaluators] warning: failed to load built-in evaluators: {e}",
                file=sys.stderr,
            )

    def _load_entry_points(self) -> None:
        """Discover evaluators from the ``model_benchmark.evaluators`` group."""
        if self._loaded_entry_points:
            return
        self._loaded_entry_points = True
        try:
            import importlib.metadata as ilm
            eps = ilm.entry_points()
            group_eps: list[Any] = []
            if hasattr(eps, "select"):
                group_eps = list(eps.select(group="model_benchmark.evaluators"))
            elif isinstance(eps, dict):
                group_eps = list(eps.get("model_benchmark.evaluators", []))
            for ep in group_eps:
                try:
                    loaded = ep.load()
                    if callable(loaded):
                        self.register(ep.name, loaded)  # type: ignore[arg-type]
                except Exception as e:
                    print(
                        f"[evaluators] warning: failed to load entry point "
                        f"'{ep.name}': {e}",
                        file=sys.stderr,
                    )
        except Exception:
            pass

    def _scan_plugin_dirs(self) -> None:
        """Scan ``tests/evaluators/*.py`` for drop-in plugins.

        Each discovered ``.py`` file is imported as a module. Plugins register
        themselves via the module-level ``@register`` decorator (which uses
        the global registry) or by calling ``registry.register()`` at import
        time.
        """
        default_dir = Path(__file__).parent.parent / "tests" / "evaluators"
        dirs_to_scan = [default_dir]
        for d in dirs_to_scan:
            if d in self._scanned_dirs:
                continue
            self._scanned_dirs.add(d)
            if not d.is_dir():
                continue
            for py_file in sorted(d.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                self._load_plugin_file(py_file)

    def _load_plugin_file(self, path: Path) -> None:
        """Import a single ``.py`` file as a module so its register calls run."""
        mod_name = f"_mb_plugin_{path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if spec is None or spec.loader is None:
                return
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
        except Exception as e:
            print(
                f"[evaluators] warning: failed to load plugin '{path}': {e}",
                file=sys.stderr,
            )

    def clear(self) -> None:
        """Reset the registry (useful for tests)."""
        self._factories.clear()
        self._builtins_loaded = False
        self._loaded_entry_points = False
        self._scanned_dirs.clear()


# ── Module-level singleton ─────────────────────────────────────────────

_registry: Optional[EvaluatorRegistry] = None


def get_registry() -> EvaluatorRegistry:
    """Return the global registry singleton."""
    global _registry
    if _registry is None:
        _registry = EvaluatorRegistry()
    return _registry


def reset_registry() -> EvaluatorRegistry:
    """Reset the global registry to a fresh instance (used in tests)."""
    global _registry
    _registry = EvaluatorRegistry()
    return _registry


def register(name: str) -> Callable[[type], type]:
    """Class decorator that registers an Evaluator subclass in the global registry.

    Example::

        @register("my_evaluator")
        class MyEvaluator(Evaluator):
            name = "my_evaluator"
            def evaluate(self, response, expected, context=None):
                ...

    The decorator returns the class unchanged so it can be used normally.
    """
    def decorator(cls: type) -> type:
        def factory(**params: Any) -> Evaluator:
            return cls(**params)  # type: ignore[arg-type]
        get_registry().register(name, factory)
        return cls
    return decorator


def register_evaluator(name: str, factory: EvaluatorFactory) -> None:
    """Explicitly register a factory callable in the global registry."""
    get_registry().register(name, factory)
