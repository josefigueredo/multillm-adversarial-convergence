"""Sandbox subsystem — backend seam for execution substrate extensibility."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .backends.container import ContainerBackend
from .backends.local_process import LocalProcessBackend

if TYPE_CHECKING:
    from ..config import SandboxConfig

from .backends.base import SandboxBackend


def select_sandbox_backend(config: "SandboxConfig", output_dir: Path) -> SandboxBackend:
    """Return the appropriate :class:`SandboxBackend` for *config*.

    Parameters
    ----------
    config:
        The ``security.sandbox`` configuration block.
    output_dir:
        The run output directory.  The host-side workspace is created as a
        sub-directory of this path.

    Returns
    -------
    SandboxBackend
        A :class:`LocalProcessBackend` when ``config.backend == "local_process"``,
        or a :class:`ContainerBackend` when ``config.backend == "container"``.

    Raises
    ------
    ValueError
        When ``config.backend`` is not a recognised value.
    """
    host_workspace = output_dir / ".workspace"

    if config.backend == "local_process":
        return LocalProcessBackend(workspace_dir=host_workspace)

    if config.backend == "container":
        return ContainerBackend(
            image=config.container.image,
            host_workspace=host_workspace,
            container_workspace=config.container.container_workspace,
        )

    raise ValueError(
        f"Unknown sandbox backend {config.backend!r}. "
        f"Valid values: local_process, container"
    )


__all__ = ["ContainerBackend", "LocalProcessBackend", "select_sandbox_backend"]
