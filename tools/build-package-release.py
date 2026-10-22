#!/usr/bin/env python3
"""Build an Island package candidate locally; publishing requires human review."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://github.com/Island-Team/Aether-EOS-mujoco-sim"
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")


def checked_path(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.is_file():
        raise ValueError(f"required file is missing: {path}")
    return path


def template(source: Path, target: Path, replacements: dict[str, str]) -> None:
    content = source.read_text()
    for old, new in replacements.items():
        if old not in content:
            raise ValueError(f"expected setting {old!r} is missing from {source}")
        content = content.replace(old, new, 1)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


def stage_release(stage: Path, binary: Path, eos_root: Path) -> None:
    (stage / "bin").mkdir()
    shutil.copy2(binary, stage / "bin/eos-mujoco-sim.real")
    (stage / "bin/eos-mujoco-sim.real").chmod(0o755)
    wrapper = stage / "bin/eos-mujoco-sim"
    wrapper.write_text(
        "#!/bin/sh\nset -eu\n"
        ': "${MUJOCO_ROOT:?Install MuJoCo 3.16.0 and set MUJOCO_ROOT}"\n'
        'test -f "$MUJOCO_ROOT/lib/libmujoco.so.3.16.0" || '
        '{ echo "MuJoCo 3.16.0 library is missing" >&2; exit 1; }\n'
        'root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)\n'
        'LD_LIBRARY_PATH="$MUJOCO_ROOT/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" '
        'exec "$root/bin/eos-mujoco-sim.real" "$@"\n'
    )
    wrapper.chmod(0o755)
    shutil.copytree(ROOT / "assets", stage / "assets")
    shutil.copy2(ROOT / "LICENSE", stage / "LICENSE")
    template(checked_path(eos_root, "etc/eos/eos.mujoco.toml"), stage / "config/eos.toml", {})
    template(checked_path(eos_root, "etc/eos/sim.toml"), stage / "config/sim.toml", {
        'backend = "demo"': 'backend = "mujoco"',
        'width_px = 1920': 'width_px = 640',
        'height_px = 1080': 'height_px = 480',
    })
    sim = stage / "config/sim.toml"
    sim.write_text("\n".join(
        line for line in sim.read_text().splitlines()
        if "/home/" not in line and "# [simulator.mujoco]" not in line
    ) + "\n")
    with sim.open("a") as out:
        out.write('\n[simulator.mujoco]\nexecutable = {{package_executable}}\nscene = {{package_scene}}\n')
    (stage / "config/backends").mkdir(parents=True)
    shutil.copy2(checked_path(eos_root, "etc/eos/backends/mujoco.toml"), stage / "config/backends/mujoco.toml")


def required_libraries(binary: Path) -> list[str]:
    result = subprocess.run(["ldd", str(binary)], check=True, capture_output=True, text=True)
    if "not found" in result.stdout:
        raise ValueError(f"binary has unresolved libraries:\n{result.stdout}")
    names = set(re.findall(r"^\s*(\S+\.so(?:\.\S+)?)\s+=>", result.stdout, re.MULTILINE))
    if "libmujoco.so.3.16.0" not in names:
        raise ValueError("binary must link to exactly MuJoCo 3.16.0")
    return sorted(names)


def minimum_glibc(binary: Path) -> tuple[int, int]:
    result = subprocess.run(["objdump", "-T", str(binary)], check=True, capture_output=True, text=True)
    versions = [(int(a), int(b)) for a, b in re.findall(r"GLIBC_([0-9]+)\.([0-9]+)", result.stdout)]
    if not versions:
        raise ValueError("cannot determine glibc symbols required by binary")
    return max(versions)


def host_ubuntu_version() -> str | None:
    values = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip('"')
    return values.get("VERSION_ID") if values.get("ID") == "ubuntu" else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="SemVer x.y.z, matching the intended GitHub vX.Y.Z tag")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build")
    parser.add_argument("--eos-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--glibc-min", required=True, help="minimum glibc version established by target testing")
    parser.add_argument("--tested-ubuntu", action="append", required=True, help="Ubuntu release tested on this binary")
    parser.add_argument("--skip-tests", action="store_true", help="inspection only; candidate marked unqualified")
    args = parser.parse_args()
    if not VERSION.fullmatch(args.version):
        parser.error("--version must be x.y.z")
    if not re.fullmatch(r"[0-9]+\.[0-9]+", args.glibc_min):
        parser.error("--glibc-min must be major.minor")
    arch = {"AMD64": "x86_64", "arm64": "aarch64"}.get(platform.machine(), platform.machine())
    if arch not in ("x86_64", "aarch64") or platform.system() != "Linux":
        parser.error("release builder supports native Linux x86_64 or aarch64 only")
    ubuntu = host_ubuntu_version()
    if ubuntu is None or args.tested_ubuntu != [ubuntu]:
        parser.error("--tested-ubuntu must name this Ubuntu host's VERSION_ID exactly once; build each target on its own host")
    binary = checked_path(args.build_dir, "eos-mujoco-sim")
    if not os.access(binary, os.X_OK):
        parser.error(f"binary is not executable: {binary}")
    libraries = required_libraries(binary)
    claimed_glibc = tuple(int(part) for part in args.glibc_min.split("."))
    actual_glibc = minimum_glibc(binary)
    if claimed_glibc < actual_glibc:
        parser.error(f"binary needs glibc {actual_glibc[0]}.{actual_glibc[1]} or newer")
    if not args.skip_tests:
        subprocess.run(["ctest", "--test-dir", str(args.build_dir), "--output-on-failure"], check=True)
    args.output.mkdir(parents=True, exist_ok=True)
    asset_name = f"mujoco-sim-v{args.version}-linux-{arch}.tar.gz"
    archive = args.output / asset_name
    with tempfile.TemporaryDirectory(prefix="island-mujoco-package-") as tmp:
        stage = Path(tmp)
        stage_release(stage, binary, args.eos_root)
        with tarfile.open(archive, "w:gz") as tar:
            for file in sorted(stage.rglob("*")):
                tar.add(file, arcname=file.relative_to(stage).as_posix(), recursive=False)
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    url = f"{SOURCE}/releases/download/v{args.version}/{asset_name}"
    manifest = {
        "schema_version": 1,
        "id": "island/mujoco-sim",
        "kind": "extension",
        "version": args.version,
        "description": "MuJoCo benchmark simulator for EOS",
        "source_url": SOURCE,
        "release_url": f"{SOURCE}/releases/tag/v{args.version}",
        "license": "Apache-2.0",
        "assets": [{
            "name": asset_name, "url": url, "sha256": digest,
            "size_bytes": archive.stat().st_size, "os": "linux", "arch": arch,
            "glibc_min": args.glibc_min, "eos_contract": "eos.simulator.v1",
            "required_libraries": libraries,
            "tested_ubuntu": args.tested_ubuntu,
        }],
        "config_inputs": [],
        "activation": {
            "entrypoint": "bin/eos-mujoco-sim", "scene": "assets/scene.xml",
            "eos_template": "config/eos.toml", "simulator_template": "config/sim.toml",
            "backend_template": "config/backends/mujoco.toml",
        },
    }
    draft = args.output / f"{asset_name}.manifest.draft.json"
    draft.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Built {archive}\nSHA-256 {digest}\nDraft {draft}")
    if args.skip_tests:
        print("UNQUALIFIED: tests were skipped; do not submit this draft for approval")
    else:
        print("Local tests passed. Review target requirements and uploaded release bytes before approval.")


if __name__ == "__main__":
    main()
