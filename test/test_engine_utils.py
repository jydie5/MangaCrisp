from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from mangacrisp_app.engine_utils import run_realcugan


@pytest.mark.parametrize("tta", [False, True])
@pytest.mark.parametrize("model", ["models-pro", "models-se"])
def test_realcugan_uses_accurate_sync_for_pro(tmp_path: Path, model: str, tta: bool):
    executable = tmp_path / "engine" / "realcugan-ncnn-vulkan"
    source = tmp_path / "page.png"
    output = tmp_path / "cache" / "page.png"

    def run(command, **kwargs):
        assert command[0] == str(executable)
        assert command[command.index("-m") + 1] == model
        assert command[command.index("-i") + 1] == str(source)
        assert command[command.index("-o") + 1] == str(output)
        assert kwargs["cwd"] == str(executable.parent)
        if model == "models-pro":
            assert command[command.index("-c") + 1] == "1"
        else:
            assert "-c" not in command
        assert ("-x" in command) == tta
        output.write_bytes(b"test-output")
        return CompletedProcess(command, 0, stdout="done\n")

    with (
        patch("mangacrisp_app.engine_utils.realcugan_executable", return_value=executable),
        patch("mangacrisp_app.engine_utils.subprocess.run", side_effect=run),
    ):
        result = run_realcugan(source, output, model=model, scale=3, noise=3, tta=tta)

    assert result.returncode == 0
    assert result.output_exists
    assert result.output_size == len(b"test-output")
    assert result.input == str(source)
    assert result.stdout == "done"
