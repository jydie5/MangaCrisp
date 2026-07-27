from __future__ import annotations

import sys

if sys.platform == "darwin":
    from mangacrisp_app.platform.macos import (
        application_directories,
        bundled_archive_tool_candidates,
        engine_executable_names,
        open_directory,
        subprocess_window_kwargs,
    )
elif sys.platform == "win32":
    from mangacrisp_app.platform.windows import (
        application_directories,
        bundled_archive_tool_candidates,
        engine_executable_names,
        open_directory,
        subprocess_window_kwargs,
    )
else:
    from mangacrisp_app.platform.common import (
        application_directories,
        bundled_archive_tool_candidates,
        engine_executable_names,
        open_directory,
        subprocess_window_kwargs,
    )

__all__ = [
    "application_directories",
    "bundled_archive_tool_candidates",
    "engine_executable_names",
    "open_directory",
    "subprocess_window_kwargs",
]
