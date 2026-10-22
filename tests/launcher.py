#!/usr/bin/env python3
"""Check standalone launcher ownership, readiness, and shutdown."""

from pathlib import Path
from subprocess import run
from sys import argv
from tempfile import TemporaryDirectory
import os


def main() -> None:
  if len(argv) != 4:
    raise SystemExit('usage: launcher.py LAUNCH KILL SIMULATOR')
  launcher, killer, simulator = map(Path, argv[1:])
  with TemporaryDirectory() as temporary:
    folder = Path(temporary)
    run_dir = folder / 'run'
    command = [str(launcher), '--run-dir', str(run_dir), '--executable', str(simulator),
               '--scene', 'navigation', '--no-gui']
    try:
      started = run(command, cwd=folder, capture_output=True, text=True, check=True, timeout=20)
      assert 'Simulator started' in started.stdout
      assert (run_dir / 'simulator.sock').is_socket()
      assert (run_dir / 'benchmark.sock').is_socket()
      duplicate = run(command, cwd=folder, capture_output=True, text=True, timeout=5)
      assert duplicate.returncode != 0 and 'already running' in duplicate.stderr
    finally:
      run([str(killer), '--run-dir', str(run_dir)], cwd=folder, check=True, timeout=10)
    assert not (run_dir / 'simulator.sock').exists()
    assert not (run_dir / 'benchmark.sock').exists()
    assert not (run_dir / 'simulator.pid').exists()

    (run_dir / 'simulator.pid').write_text(f'{os.getpid()} 0\n')
    (run_dir / 'simulator.sock').write_text('leave unrelated state alone')
    run([str(killer), '--run-dir', str(run_dir)], cwd=folder, check=True, timeout=5)
    assert (run_dir / 'simulator.sock').read_text() == 'leave unrelated state alone'

    headless = dict(os.environ)
    headless.pop('DISPLAY', None)
    headless.pop('WAYLAND_DISPLAY', None)
    gui = run([str(launcher), '--run-dir', str(folder / 'gui'), '--executable', str(simulator),
               '--gui'], cwd=folder, env=headless, capture_output=True, text=True, timeout=5)
    assert gui.returncode != 0 and 'desktop display' in gui.stderr
    assert not (folder / 'gui' / 'simulator.pid').exists()


if __name__ == '__main__':
  main()
