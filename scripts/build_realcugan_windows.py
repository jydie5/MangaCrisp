from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import struct
import subprocess
import urllib.request
import zipfile
from pathlib import Path

import pefile
from fetch_realcugan_windows import (
    ARCHIVE_SHA256 as MODEL_ARCHIVE_SHA256,
)
from fetch_realcugan_windows import (
    ARCHIVE_URL as MODEL_ARCHIVE_URL,
)
from fetch_realcugan_windows import (
    RELEASE,
    REQUIRED_MODEL_DIRS,
)
from fetch_realcugan_windows import (
    ensure_realcugan as ensure_official_package,
)
from fetch_vulkan_sdk_windows import (
    INSTALLER_SHA256 as VULKAN_INSTALLER_SHA256,
)
from fetch_vulkan_sdk_windows import (
    INSTALLER_URL as VULKAN_INSTALLER_URL,
)
from fetch_vulkan_sdk_windows import (
    VERSION as VULKAN_VERSION,
)
from fetch_vulkan_sdk_windows import (
    verify_sdk,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
VENDOR_DIR = ROOT_DIR / "build" / "vendor"
SOURCE_DIR = VENDOR_DIR / "realcugan-source"
BUILD_DIR = ROOT_DIR / "build" / "windows" / "realcugan-zig-release"
PACKAGE_DIR = VENDOR_DIR / f"realcugan-ncnn-vulkan-{RELEASE}-windows-zig"
SOURCE_REPOSITORY = "https://github.com/nihui/realcugan-ncnn-vulkan.git"
SOURCE_COMMIT = "395302c5c70f1bff604c974e92e0a87e45c9f9ee"
SOURCE_DATE_EPOCH = "1658966400"
SUBMODULE_COMMITS = {
    "src/libwebp": "b9d2f9cd3bec5b0970edeb11ea03c0a4ea06e332",
    "src/ncnn": "066614351391d309c96ae1e00c6fb1bd873b4949",
    "src/ncnn/glslang": "86ff4bca1ddc7e2262f119c16e7228d0efb67610",
    "src/ncnn/python/pybind11": "70a58c577eaf067748c2ec31bfd0b0a614cffba6",
}
ZIG_VERSION = "0.16.0"
ZIG_ARCHIVE_NAME = f"zig-x86_64-windows-{ZIG_VERSION}.zip"
ZIG_ARCHIVE_URL = f"https://ziglang.org/download/{ZIG_VERSION}/{ZIG_ARCHIVE_NAME}"
ZIG_ARCHIVE_SHA256 = "68659eb5f1e4eb1437a722f1dd889c5a322c9954607f5edcf337bc3684a75a7e"
EXPECTED_CMAKE_VERSION = "4.4.0"
EXPECTED_NINJA_VERSION_PREFIX = "1.13.0"
ENGINE_NAME = "realcugan-ncnn-vulkan.exe"
# LLD derives these PE/CodeView metadata fields from a per-build hash. They are
# not used at runtime, but make otherwise identical builds differ byte-for-byte.
# These canonical values preserve the exact binary used for the NVIDIA evidence.
CANONICAL_PE_TIMESTAMP = 0x8571046E
CANONICAL_LLD_PDB_HASH = bytes.fromhex("b610d34f41fa34bc")
FORBIDDEN_IMPORT_PREFIXES = (
    "libgcc",
    "libgomp",
    "libstdc++",
    "libwinpthread",
    "msvcp",
    "vcomp",
    "vcruntime",
)
ALLOWED_IMPORTS = {
    "kernel32.dll",
    "ole32.dll",
    "oleaut32.dll",
    "vulkan-1.dll",
}
LICENSE_SOURCES = {
    "realcugan-ncnn-vulkan-MIT.txt": Path("LICENSE"),
    "ncnn-BSD-3-Clause-and-third-party.txt": Path("src/ncnn/LICENSE.txt"),
    "glslang-license-notices.txt": Path("src/ncnn/glslang/LICENSE.txt"),
    "libwebp-COPYING.txt": Path("src/libwebp/COPYING"),
    "libwebp-PATENTS.txt": Path("src/libwebp/PATENTS"),
}
ZIG_LICENSE_SOURCES = {
    "Zig-MIT.txt": Path("LICENSE"),
    "Zig-MinGW-w64-COPYING.txt": Path("lib/libc/mingw/COPYING"),
    "LLVM-libcxx-LICENSE.txt": Path("lib/libcxx/LICENSE.TXT"),
    "LLVM-libcxxabi-LICENSE.txt": Path("lib/libcxxabi/LICENSE.TXT"),
    "LLVM-libunwind-LICENSE.txt": Path("lib/libunwind/LICENSE.TXT"),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_verified(url: str, destination: Path, expected_sha256: str) -> Path:
    if destination.is_file() and sha256_file(destination) == expected_sha256:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    with urllib.request.urlopen(url) as response, temporary.open("wb") as output:
        shutil.copyfileobj(response, output)
    actual = sha256_file(temporary)
    if actual != expected_sha256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"SHA-256 mismatch for {destination.name}: "
            f"expected {expected_sha256}, got {actual}"
        )
    temporary.replace(destination)
    return destination


def safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for info in archive.infolist():
        target = (destination / info.filename).resolve()
        if target != root and root not in target.parents:
            raise RuntimeError(f"unsafe ZIP member: {info.filename}")
    archive.extractall(destination)


def command_output(command: list[str], *, cwd: Path | None = None) -> str:
    return subprocess.check_output(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).strip()


def ensure_zig(destination: Path = VENDOR_DIR) -> Path:
    zig_root = destination / f"zig-x86_64-windows-{ZIG_VERSION}"
    zig = zig_root / "zig.exe"
    if zig.is_file() and command_output([str(zig), "version"]) == ZIG_VERSION:
        return zig_root

    archive_path = download_verified(
        ZIG_ARCHIVE_URL,
        destination / ZIG_ARCHIVE_NAME,
        ZIG_ARCHIVE_SHA256,
    )
    extract_root = destination / f".zig-{ZIG_VERSION}-extract"
    shutil.rmtree(extract_root, ignore_errors=True)
    extract_root.mkdir(parents=True)
    with zipfile.ZipFile(archive_path) as archive:
        safe_extract(archive, extract_root)
    extracted = extract_root / zig_root.name
    if not extracted.is_dir():
        raise RuntimeError(f"expected Zig package root was not found: {extracted}")
    shutil.rmtree(zig_root, ignore_errors=True)
    shutil.move(str(extracted), str(zig_root))
    shutil.rmtree(extract_root, ignore_errors=True)
    if not zig.is_file() or command_output([str(zig), "version"]) != ZIG_VERSION:
        raise RuntimeError(
            "the extracted Zig compiler did not match the pinned version"
        )
    return zig_root


def git_output(source_dir: Path, *arguments: str) -> str:
    return command_output(["git", "-C", str(source_dir), *arguments])


def ensure_source(source_dir: Path = SOURCE_DIR) -> Path:
    if not (source_dir / ".git").is_dir():
        if source_dir.exists():
            raise RuntimeError(
                f"source directory exists but is not a Git clone: {source_dir}"
            )
        source_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--no-checkout", SOURCE_REPOSITORY, str(source_dir)],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(source_dir), "checkout", "--detach", SOURCE_COMMIT],
            check=True,
        )
    if git_output(source_dir, "rev-parse", "HEAD") != SOURCE_COMMIT:
        raise RuntimeError(
            f"Real-CUGAN source is not at the pinned commit: {source_dir}"
        )
    subprocess.run(
        ["git", "-C", str(source_dir), "submodule", "update", "--init", "--recursive"],
        check=True,
    )
    for relative, expected in SUBMODULE_COMMITS.items():
        actual = git_output(source_dir / relative, "rev-parse", "HEAD")
        if actual != expected:
            raise RuntimeError(
                f"submodule mismatch for {relative}: expected {expected}, got {actual}"
            )
    return source_dir


def executable_imports(executable: Path) -> list[str]:
    pe = pefile.PE(str(executable), fast_load=True)
    try:
        pe.parse_data_directories(
            directories=[
                pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
            ]
        )
        entries = getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])
        return sorted(
            {entry.dll.decode("ascii", errors="replace").lower() for entry in entries}
        )
    finally:
        pe.close()


def validate_runtime_imports(imports: list[str]) -> None:
    forbidden = sorted(
        imported
        for imported in imports
        if imported.startswith(FORBIDDEN_IMPORT_PREFIXES)
    )
    unexpected = sorted(
        imported
        for imported in imports
        if imported not in ALLOWED_IMPORTS
        and not imported.startswith("api-ms-win-crt-")
    )
    if forbidden:
        raise RuntimeError(f"forbidden runtime imports: {forbidden}")
    if unexpected:
        raise RuntimeError(f"unexpected runtime imports: {unexpected}")
    if "vulkan-1.dll" not in imports:
        raise RuntimeError("the built engine does not import vulkan-1.dll")


def tool_version(executable: str, expected: str, *, prefix: bool = False) -> str:
    path = shutil.which(executable)
    if path is None:
        raise RuntimeError(
            f"{executable} was not found. Run: uv sync --extra dev --extra app"
        )
    output = command_output([path, "--version"])
    first_line = output.splitlines()[0]
    actual = first_line.rsplit(" ", 1)[-1]
    valid = actual.startswith(expected) if prefix else actual == expected
    if not valid:
        raise RuntimeError(
            f"{executable} version mismatch: expected {expected}, got {actual}"
        )
    return path


def write_build_helpers(build_dir: Path, zig: Path) -> tuple[Path, Path, Path]:
    build_dir.mkdir(parents=True, exist_ok=True)
    zig_ar = build_dir / "zig-ar.cmd"
    zig_ranlib = build_dir / "zig-ranlib.cmd"
    hook = build_dir / "realcugan-zig-target-options.cmake"
    quoted_zig = f'"{zig}"'
    zig_ar.write_text(f"@echo off\n{quoted_zig} ar %*\n", encoding="utf-8")
    zig_ranlib.write_text(
        f"@echo off\n{quoted_zig} ranlib %*\n",
        encoding="utf-8",
    )
    hook.write_text(
        "function(mangacrisp_configure_realcugan_zig_target)\n"
        "    if(MINGW AND TARGET realcugan-ncnn-vulkan)\n"
        "        target_link_options(realcugan-ncnn-vulkan PRIVATE -municode)\n"
        "    endif()\n"
        "endfunction()\n\n"
        "cmake_language(\n"
        "    DEFER\n"
        '    DIRECTORY "${CMAKE_SOURCE_DIR}"\n'
        "    CALL mangacrisp_configure_realcugan_zig_target\n"
        ")\n",
        encoding="utf-8",
    )
    return zig_ar, zig_ranlib, hook


def apply_lld_metadata_normalization(
    data: bytearray,
    *,
    file_timestamp_offset: int,
    debug_timestamp_offsets: list[int],
    codeview_offset: int,
) -> None:
    codeview_header = bytes(data[codeview_offset : codeview_offset + 20])
    if (
        len(codeview_header) != 20
        or codeview_header[:4] != b"RSDS"
        or codeview_header[12:20] != b"LLD PDB."
    ):
        raise RuntimeError("unexpected LLD CodeView build-id format")

    timestamp = struct.pack("<I", CANONICAL_PE_TIMESTAMP)
    data[file_timestamp_offset : file_timestamp_offset + 4] = timestamp
    for offset in debug_timestamp_offsets:
        data[offset : offset + 4] = timestamp
    data[codeview_offset + 4 : codeview_offset + 12] = CANONICAL_LLD_PDB_HASH


def normalize_lld_metadata(executable: Path) -> None:
    data = bytearray(executable.read_bytes())
    pe = pefile.PE(data=bytes(data))
    debug_entries = getattr(pe, "DIRECTORY_ENTRY_DEBUG", [])
    codeview_entries = [entry for entry in debug_entries if entry.struct.Type == 2]
    if len(codeview_entries) != 1:
        raise RuntimeError("expected exactly one LLD CodeView debug entry")

    apply_lld_metadata_normalization(
        data,
        file_timestamp_offset=pe.FILE_HEADER.get_field_absolute_offset("TimeDateStamp"),
        debug_timestamp_offsets=[
            entry.struct.get_field_absolute_offset("TimeDateStamp")
            for entry in debug_entries
        ],
        codeview_offset=codeview_entries[0].struct.PointerToRawData,
    )
    executable.write_bytes(data)


def build_engine(
    source_dir: Path,
    build_dir: Path,
    zig_root: Path,
    vulkan_sdk: Path,
    *,
    clean: bool,
) -> tuple[Path, dict[str, str]]:
    if clean:
        shutil.rmtree(build_dir, ignore_errors=True)
    cmake = Path(tool_version("cmake", EXPECTED_CMAKE_VERSION))
    ninja = Path(tool_version("ninja", EXPECTED_NINJA_VERSION_PREFIX, prefix=True))
    zig = zig_root / "zig.exe"
    zig_ar, zig_ranlib, hook = write_build_helpers(build_dir, zig)
    environment = os.environ.copy()
    environment["SOURCE_DATE_EPOCH"] = SOURCE_DATE_EPOCH
    environment["VULKAN_SDK"] = str(vulkan_sdk)
    environment["PATH"] = f"{vulkan_sdk / 'Bin'}{os.pathsep}{environment['PATH']}"
    configure = [
        str(cmake),
        "--no-warn-unused-cli",
        "-S",
        str(source_dir / "src"),
        "-B",
        str(build_dir),
        "-G",
        "Ninja",
        f"-DCMAKE_MAKE_PROGRAM={ninja}",
        f"-DCMAKE_C_COMPILER={zig}",
        "-DCMAKE_C_COMPILER_ARG1=cc",
        f"-DCMAKE_CXX_COMPILER={zig}",
        "-DCMAKE_CXX_COMPILER_ARG1=c++",
        "-DCMAKE_C_COMPILER_TARGET=x86_64-windows-gnu",
        "-DCMAKE_CXX_COMPILER_TARGET=x86_64-windows-gnu",
        f"-DCMAKE_AR:FILEPATH={zig_ar}",
        f"-DCMAKE_RANLIB:FILEPATH={zig_ranlib}",
        f"-DCMAKE_C_COMPILER_AR:FILEPATH={zig_ar}",
        f"-DCMAKE_C_COMPILER_RANLIB:FILEPATH={zig_ranlib}",
        f"-DCMAKE_CXX_COMPILER_AR:FILEPATH={zig_ar}",
        f"-DCMAKE_CXX_COMPILER_RANLIB:FILEPATH={zig_ranlib}",
        f"-DCMAKE_PROJECT_INCLUDE={hook}",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_DISABLE_FIND_PACKAGE_OpenMP=TRUE",
        "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
        f"-DNCNN_VERSION={RELEASE}",
        "-DNCNN_AVX=OFF",
        "-DNCNN_COMPILER_SUPPORT_X86_AVX=OFF",
        "-DNCNN_COMPILER_SUPPORT_X86_FMA=OFF",
        "-DNCNN_COMPILER_SUPPORT_X86_XOP=OFF",
        "-DNCNN_COMPILER_SUPPORT_X86_F16C=OFF",
        "-DNCNN_COMPILER_SUPPORT_X86_AVX2=OFF",
        "-DNCNN_COMPILER_SUPPORT_X86_AVX_VNNI=OFF",
        "-DNCNN_COMPILER_SUPPORT_X86_AVX512=OFF",
        "-DNCNN_COMPILER_SUPPORT_X86_AVX512_VNNI=OFF",
        "-DNCNN_COMPILER_SUPPORT_X86_AVX512_BF16=OFF",
        "-DNCNN_COMPILER_SUPPORT_X86_AVX512_FP16=OFF",
        "-DWEBP_ENABLE_SIMD=ON",
        f"-DVulkan_INCLUDE_DIR={vulkan_sdk / 'Include'}",
        f"-DVulkan_LIBRARY={vulkan_sdk / 'Lib' / 'vulkan-1.lib'}",
        "-DUSE_SYSTEM_NCNN=OFF",
        "-DUSE_SYSTEM_WEBP=OFF",
    ]
    subprocess.run(configure, cwd=ROOT_DIR, env=environment, check=True)
    subprocess.run(
        [str(cmake), "--build", str(build_dir), "--parallel"],
        cwd=ROOT_DIR,
        env=environment,
        check=True,
    )
    executable = build_dir / ENGINE_NAME
    if not executable.is_file():
        raise RuntimeError(f"build did not create {executable}")
    normalize_lld_metadata(executable)
    imports = executable_imports(executable)
    validate_runtime_imports(imports)
    versions = {
        "zig": command_output([str(zig), "version"]),
        "cmake": command_output([str(cmake), "--version"]).splitlines()[0],
        "ninja": command_output([str(ninja), "--version"]),
    }
    return executable, versions


def copy_licenses(
    package_dir: Path,
    source_dir: Path,
    zig_root: Path,
) -> dict[str, str]:
    licenses_dir = package_dir / "licenses"
    licenses_dir.mkdir(parents=True)
    for filename, relative in LICENSE_SOURCES.items():
        source = source_dir / relative
        if not source.is_file():
            raise RuntimeError(f"required license was not found: {source}")
        shutil.copy2(source, licenses_dir / filename)
    for filename, relative in ZIG_LICENSE_SOURCES.items():
        source = zig_root / relative
        if not source.is_file():
            raise RuntimeError(f"required Zig runtime license was not found: {source}")
        shutil.copy2(source, licenses_dir / filename)
    return {
        path.name: sha256_file(path)
        for path in sorted(licenses_dir.iterdir())
        if path.is_file()
    }


def model_hashes(package_dir: Path) -> dict[str, str]:
    return {
        path.relative_to(package_dir).as_posix(): sha256_file(path)
        for directory in REQUIRED_MODEL_DIRS
        for path in sorted((package_dir / directory).iterdir())
        if path.is_file()
    }


def stage_package(
    executable: Path,
    source_dir: Path,
    zig_root: Path,
    official_package: Path,
    imports: list[str],
    versions: dict[str, str],
    destination: Path = PACKAGE_DIR,
) -> Path:
    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True)
    shutil.copy2(executable, destination / ENGINE_NAME)
    for directory in REQUIRED_MODEL_DIRS:
        shutil.copytree(official_package / directory, destination / directory)
    shutil.copy2(source_dir / "LICENSE", destination / "LICENSE")
    shutil.copy2(official_package / "README.md", destination / "README.md")
    licenses = copy_licenses(destination, source_dir, zig_root)
    engine_hash = sha256_file(destination / ENGINE_NAME)
    payload = {
        "schema_version": 2,
        "component": "Real-CUGAN ncnn Vulkan",
        "purpose": "Windows AI image enhancement engine",
        "release": RELEASE,
        "architecture": "x64",
        "source": {
            "repository": SOURCE_REPOSITORY,
            "commit": SOURCE_COMMIT,
            "submodules": SUBMODULE_COMMITS,
            "modified": False,
        },
        "models": {
            "archive_url": MODEL_ARCHIVE_URL,
            "archive_sha256": MODEL_ARCHIVE_SHA256,
            "files": model_hashes(destination),
        },
        "build": {
            "target": "x86_64-windows-gnu",
            "source_date_epoch": SOURCE_DATE_EPOCH,
            "ncnn_version": RELEASE,
            "openmp": False,
            "ncnn_cpu_avx": False,
            "webp_simd": True,
            "toolchain": {
                "name": "Zig",
                "version": ZIG_VERSION,
                "archive_url": ZIG_ARCHIVE_URL,
                "archive_sha256": ZIG_ARCHIVE_SHA256,
                "components": "Clang/LLVM, libc++, compiler-rt, MinGW-w64",
            },
            "cmake": versions["cmake"],
            "ninja": versions["ninja"],
            "vulkan_sdk": {
                "version": VULKAN_VERSION,
                "installer_url": VULKAN_INSTALLER_URL,
                "installer_sha256": VULKAN_INSTALLER_SHA256,
                "build_time_only": True,
            },
            "lld_metadata_normalization": {
                "pe_timestamp": CANONICAL_PE_TIMESTAMP,
                "codeview_pdb_hash": CANONICAL_LLD_PDB_HASH.hex(),
                "scope": "non-runtime PE and CodeView build metadata only",
            },
        },
        "engine": {
            "filename": ENGINE_NAME,
            "sha256": engine_hash,
            "imports": imports,
        },
        "runtime": {
            "bundled_dlls": [],
            "windows_10_or_11_ucrt_api_set": True,
            "vulkan_loader_from_gpu_driver": True,
            "vcomp_required": False,
            "visual_cpp_redistributable_required": False,
            "end_user_installer_required": False,
        },
        "licenses": licenses,
        "redistribution_approved": True,
        "redistribution_basis": (
            "The engine and statically linked components use permissive licenses "
            "whose notices are bundled. No Microsoft VC/OpenMP DLL, MinGW runtime "
            "DLL, Vulkan SDK file, or other non-system runtime is distributed."
        ),
        "review_scope": (
            "Practical engineering record for this build; not legal advice."
        ),
    }
    provenance = destination / "realcugan-provenance.json"
    provenance.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def verify_package(package_dir: Path) -> None:
    executable = package_dir / ENGINE_NAME
    provenance = package_dir / "realcugan-provenance.json"
    if not executable.is_file() or not provenance.is_file():
        raise RuntimeError("staged Real-CUGAN package is incomplete")
    payload = json.loads(provenance.read_text(encoding="utf-8"))
    if payload.get("engine", {}).get("sha256") != sha256_file(executable):
        raise RuntimeError(
            "staged Real-CUGAN executable hash does not match provenance"
        )
    validate_runtime_imports(executable_imports(executable))
    forbidden = [path.name for path in package_dir.rglob("*.dll") if path.is_file()]
    if forbidden:
        raise RuntimeError(f"the staged engine must not bundle DLLs: {forbidden}")
    for directory in REQUIRED_MODEL_DIRS:
        if not any((package_dir / directory).glob("*.bin")):
            raise RuntimeError(f"model binaries are missing: {directory}")
        if not any((package_dir / directory).glob("*.param")):
            raise RuntimeError(f"model parameters are missing: {directory}")


def verify_package_recipe(package_dir: Path) -> None:
    verify_package(package_dir)
    provenance = package_dir / "realcugan-provenance.json"
    payload = json.loads(provenance.read_text(encoding="utf-8"))
    source = payload.get("source", {})
    build = payload.get("build", {})
    runtime = payload.get("runtime", {})
    engine = payload.get("engine", {})
    if not all(
        isinstance(section, dict) for section in (source, build, runtime, engine)
    ):
        raise RuntimeError("staged Real-CUGAN provenance has invalid sections")
    toolchain = build.get("toolchain", {})
    normalization = build.get("lld_metadata_normalization", {})
    if not isinstance(toolchain, dict):
        raise TypeError("staged Real-CUGAN toolchain provenance is invalid")
    if not isinstance(normalization, dict):
        raise TypeError("staged Real-CUGAN normalization provenance is invalid")
    if (
        payload.get("schema_version") != 2
        or source.get("commit") != SOURCE_COMMIT
        or source.get("submodules") != SUBMODULE_COMMITS
        or build.get("target") != "x86_64-windows-gnu"
        or build.get("source_date_epoch") != SOURCE_DATE_EPOCH
        or build.get("ncnn_version") != RELEASE
        or build.get("openmp") is not False
        or build.get("ncnn_cpu_avx") is not False
        or build.get("webp_simd") is not True
        or toolchain.get("version") != ZIG_VERSION
        or toolchain.get("archive_sha256") != ZIG_ARCHIVE_SHA256
        or normalization.get("pe_timestamp") != CANONICAL_PE_TIMESTAMP
        or normalization.get("codeview_pdb_hash") != CANONICAL_LLD_PDB_HASH.hex()
        or normalization.get("scope")
        != "non-runtime PE and CodeView build metadata only"
        or runtime.get("bundled_dlls") != []
        or runtime.get("vcomp_required") is not False
        or runtime.get("visual_cpp_redistributable_required") is not False
        or payload.get("redistribution_approved") is not True
    ):
        raise RuntimeError("staged Real-CUGAN package recipe does not match")

    imports = executable_imports(package_dir / ENGINE_NAME)
    if sorted(engine.get("imports", [])) != imports:
        raise RuntimeError("staged Real-CUGAN imports do not match provenance")

    models = payload.get("models", {})
    model_hashes = models.get("files", {}) if isinstance(models, dict) else {}
    if not isinstance(model_hashes, dict) or not model_hashes:
        raise RuntimeError("staged Real-CUGAN model manifest is empty")
    for relative, expected_hash in model_hashes.items():
        path = package_dir / str(relative)
        if not path.is_file() or sha256_file(path) != expected_hash:
            raise RuntimeError(f"staged model does not match provenance: {relative}")

    license_hashes = payload.get("licenses", {})
    if not isinstance(license_hashes, dict) or not license_hashes:
        raise RuntimeError("staged Real-CUGAN license manifest is empty")
    for filename, expected_hash in license_hashes.items():
        path = package_dir / "licenses" / str(filename)
        if not path.is_file() or sha256_file(path) != expected_hash:
            raise RuntimeError(f"staged license does not match provenance: {filename}")


def ensure_built_realcugan(
    *,
    source_dir: Path = SOURCE_DIR,
    build_dir: Path = BUILD_DIR,
    destination: Path = PACKAGE_DIR,
    vulkan_sdk: Path | None = None,
    clean: bool = False,
) -> Path:
    """Build, stage, and verify the pinned distributable Windows engine."""
    if platform.system() != "Windows":
        raise RuntimeError("Windows Real-CUGAN builds must run on Windows.")
    if platform.machine().lower() not in {"amd64", "x86_64"}:
        raise RuntimeError(f"Windows x64 is required, found: {platform.machine()}")

    resolved_destination = destination.resolve()
    if not clean and resolved_destination.is_dir():
        try:
            verify_package_recipe(resolved_destination)
        except (RuntimeError, json.JSONDecodeError):
            pass
        else:
            return resolved_destination

    sdk_root = (
        vulkan_sdk
        if vulkan_sdk is not None
        else VENDOR_DIR / f"VulkanSDK-{VULKAN_VERSION}"
    ).resolve()
    if not verify_sdk(sdk_root):
        raise RuntimeError(
            "The pinned copy-only Vulkan SDK was not found. Run:\n"
            "uv run python scripts/fetch_vulkan_sdk_windows.py --accept-licenses"
        )

    resolved_source = ensure_source(source_dir.resolve())
    zig_root = ensure_zig()
    executable, versions = build_engine(
        resolved_source,
        build_dir.resolve(),
        zig_root,
        sdk_root,
        clean=clean,
    )
    imports = executable_imports(executable)
    official_package = ensure_official_package(VENDOR_DIR)
    package_dir = stage_package(
        executable,
        resolved_source,
        zig_root,
        official_package,
        imports,
        versions,
        resolved_destination,
    )
    verify_package_recipe(package_dir)
    return package_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the pinned Windows Real-CUGAN engine with Zig and no "
            "Microsoft VC/OpenMP runtime redistribution."
        )
    )
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    parser.add_argument("--build-dir", type=Path, default=BUILD_DIR)
    parser.add_argument("--destination", type=Path, default=PACKAGE_DIR)
    parser.add_argument(
        "--vulkan-sdk",
        type=Path,
        default=VENDOR_DIR / f"VulkanSDK-{VULKAN_VERSION}",
    )
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    package_dir = ensure_built_realcugan(
        source_dir=args.source_dir,
        build_dir=args.build_dir,
        destination=args.destination,
        vulkan_sdk=args.vulkan_sdk,
        clean=args.clean,
    )
    print(f"Real-CUGAN: {package_dir}")
    print(f"engine_sha256: {sha256_file(package_dir / ENGINE_NAME)}")
    print("redistribution_approved=true")


if __name__ == "__main__":
    main()
