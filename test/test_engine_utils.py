from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest
from PIL import Image

from mangacrisp_app.engine_utils import run_realcugan


@pytest.mark.parametrize("tta", [False, True])
@pytest.mark.parametrize("model", ["models-pro", "models-se"])
def test_realcugan_uses_accurate_sync_for_pro(tmp_path: Path, model: str, tta: bool):
    executable = tmp_path / "engine" / "realcugan-ncnn-vulkan"
    source = tmp_path / "page.png"
    output = tmp_path / "cache" / "page.png"
    Image.new("RGB", (12, 15), (20, 30, 40)).save(source)

    def run(command, **kwargs):
        assert command[0] == str(executable)
        assert command[command.index("-m") + 1] == model
        assert command[command.index("-i") + 1] == str(source)
        temporary_output = Path(command[command.index("-o") + 1])
        assert temporary_output != output
        assert temporary_output.parent.parent == output.parent
        assert kwargs["cwd"] == str(executable.parent)
        if model == "models-pro":
            assert command[command.index("-c") + 1] == "1"
        else:
            assert "-c" not in command
        assert ("-x" in command) == tta
        Image.new("RGB", (36, 45), (80, 90, 100)).save(temporary_output)
        return CompletedProcess(command, 0, stdout="done\n")

    with (
        patch("mangacrisp_app.engine_utils.realcugan_executable", return_value=executable),
        patch("mangacrisp_app.engine_utils.subprocess.run", side_effect=run),
    ):
        result = run_realcugan(source, output, model=model, scale=3, noise=3, tta=tta)

    assert result.returncode == 0
    assert result.output_exists
    assert result.output_size == output.stat().st_size
    assert result.input == str(source)
    assert result.output == str(output)
    assert result.stdout == "done"
    assert not list(output.parent.glob(".mangacrisp-page-*"))


def test_realcugan_publishes_valid_output_atomically(tmp_path: Path) -> None:
    executable = tmp_path / "engine" / "realcugan-ncnn-vulkan"
    source = tmp_path / "page.png"
    output = tmp_path / "cache" / "page.png"
    Image.new("RGB", (8, 10), (20, 30, 40)).save(source)
    output.parent.mkdir()
    Image.new("RGB", (16, 20), (1, 2, 3)).save(output)
    previous = output.read_bytes()

    def run(command, **kwargs):
        temporary_output = Path(command[command.index("-o") + 1])
        assert output.read_bytes() == previous
        Image.new("RGB", (16, 20), (200, 201, 202)).save(temporary_output)
        return CompletedProcess(command, 0, stdout="published")

    with (
        patch("mangacrisp_app.engine_utils.realcugan_executable", return_value=executable),
        patch("mangacrisp_app.engine_utils.subprocess.run", side_effect=run),
    ):
        result = run_realcugan(source, output, scale=2)

    assert result.returncode == 0
    assert output.read_bytes() != previous
    with Image.open(output) as image:
        assert image.size == (16, 20)


def test_realcugan_keeps_existing_output_when_engine_returns_failure(tmp_path: Path) -> None:
    executable = tmp_path / "engine" / "realcugan-ncnn-vulkan"
    source = tmp_path / "page.png"
    output = tmp_path / "cache" / "page.png"
    Image.new("RGB", (8, 10), (20, 30, 40)).save(source)
    output.parent.mkdir()
    Image.new("RGB", (16, 20), (1, 2, 3)).save(output)
    previous = output.read_bytes()

    def run(command, **kwargs):
        Path(command[command.index("-o") + 1]).write_bytes(b"partial output")
        return CompletedProcess(command, 7, stdout="engine failed")

    with (
        patch("mangacrisp_app.engine_utils.realcugan_executable", return_value=executable),
        patch("mangacrisp_app.engine_utils.subprocess.run", side_effect=run),
    ):
        result = run_realcugan(source, output, scale=2)

    assert result.returncode == 7
    assert result.stdout == "engine failed"
    assert output.read_bytes() == previous
    assert result.output_exists
    assert not list(output.parent.glob(".mangacrisp-page-*"))


def test_realcugan_rejects_zero_exit_with_wrong_size_and_keeps_cache(tmp_path: Path) -> None:
    executable = tmp_path / "engine" / "realcugan-ncnn-vulkan"
    source = tmp_path / "page.png"
    output = tmp_path / "cache" / "page.png"
    Image.new("RGB", (8, 10), (20, 30, 40)).save(source)
    output.parent.mkdir()
    Image.new("RGB", (16, 20), (1, 2, 3)).save(output)
    previous = output.read_bytes()

    def run(command, **kwargs):
        temporary_output = Path(command[command.index("-o") + 1])
        Image.new("RGB", (15, 20), (200, 201, 202)).save(temporary_output)
        return CompletedProcess(command, 0, stdout="done")

    with (
        patch("mangacrisp_app.engine_utils.realcugan_executable", return_value=executable),
        patch("mangacrisp_app.engine_utils.subprocess.run", side_effect=run),
    ):
        result = run_realcugan(source, output, scale=2)

    assert result.returncode != 0
    assert "dimensions do not match" in result.stdout
    assert output.read_bytes() == previous
    assert result.output_exists


def test_realcugan_rejects_corrupt_zero_exit_output_and_cleans_temp(tmp_path: Path) -> None:
    executable = tmp_path / "engine" / "realcugan-ncnn-vulkan"
    source = tmp_path / "page.png"
    output = tmp_path / "cache" / "page.png"
    Image.new("RGB", (8, 10), (20, 30, 40)).save(source)

    def run(command, **kwargs):
        Path(command[command.index("-o") + 1]).write_bytes(b"not a png")
        return CompletedProcess(command, 0, stdout="done")

    with (
        patch("mangacrisp_app.engine_utils.realcugan_executable", return_value=executable),
        patch("mangacrisp_app.engine_utils.subprocess.run", side_effect=run),
    ):
        result = run_realcugan(source, output, scale=2)

    assert result.returncode != 0
    assert "corrupt PNG" in result.stdout
    assert not output.exists()
    assert not list(output.parent.glob(".mangacrisp-page-*"))


def test_realcugan_cleans_temp_output_when_subprocess_raises(tmp_path: Path) -> None:
    executable = tmp_path / "engine" / "realcugan-ncnn-vulkan"
    source = tmp_path / "page.png"
    output = tmp_path / "cache" / "page.png"
    Image.new("RGB", (8, 10), (20, 30, 40)).save(source)
    output.parent.mkdir()
    Image.new("RGB", (16, 20), (1, 2, 3)).save(output)
    previous = output.read_bytes()

    def run(command, **kwargs):
        Path(command[command.index("-o") + 1]).write_bytes(b"partial output")
        raise RuntimeError("subprocess interrupted")

    with (
        patch("mangacrisp_app.engine_utils.realcugan_executable", return_value=executable),
        patch("mangacrisp_app.engine_utils.subprocess.run", side_effect=run),
        pytest.raises(RuntimeError, match="subprocess interrupted"),
    ):
        run_realcugan(source, output, scale=2)

    assert output.read_bytes() == previous
    assert not list(output.parent.glob(".mangacrisp-page-*"))


def test_realcugan_resolves_paths_before_changing_subprocess_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "engine" / "realcugan-ncnn-vulkan"
    source = tmp_path / "page.png"
    output = tmp_path / "cache" / "page.png"
    Image.new("RGB", (8, 10), (20, 30, 40)).save(source)
    monkeypatch.chdir(tmp_path)

    def run(command, **kwargs):
        assert command[command.index("-i") + 1] == str(source)
        temporary_output = Path(command[command.index("-o") + 1])
        assert temporary_output.is_absolute()
        assert kwargs["cwd"] == str(executable.parent)
        Image.new("RGB", (16, 20), (200, 201, 202)).save(temporary_output)
        return CompletedProcess(command, 0, stdout="done")

    with (
        patch("mangacrisp_app.engine_utils.realcugan_executable", return_value=executable),
        patch("mangacrisp_app.engine_utils.subprocess.run", side_effect=run),
    ):
        result = run_realcugan(Path("page.png"), Path("cache/page.png"), scale=2)

    assert result.returncode == 0
    assert result.input == str(source)
    assert result.output == str(output)
    assert output.is_file()
