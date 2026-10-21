#!/usr/bin/env python3
"""Exercise a timed benchmark episode against the private socket."""

import json
from pathlib import Path
from subprocess import Popen, run
from sys import argv
from tempfile import TemporaryDirectory
from time import sleep


def main() -> None:
  if len(argv) != 5:
    raise SystemExit('usage: eval.py SIMULATOR EVALUATOR SCENE TASK')
  simulator, evaluator, scene = map(Path, argv[1:4])
  task = argv[4]
  with TemporaryDirectory() as temporary:
    folder = Path(temporary)
    socket = folder / 'simulator.sock'
    benchmark_socket = folder / 'benchmark.sock'
    process = Popen([str(simulator), '--socket', str(socket),
                     '--benchmark-socket', str(benchmark_socket), '--scene', str(scene)])
    try:
      for _ in range(100):
        if benchmark_socket.is_socket():
          break
        if process.poll() is not None:
          raise RuntimeError(f'simulator exited: {process.returncode}')
        sleep(0.05)
      else:
        raise RuntimeError('benchmark socket did not become ready')
      result = run([str(evaluator), '--benchmark-socket', str(benchmark_socket),
                    '--task', task, '--seed', '42', '--duration-s', '0.05'],
                   capture_output=True, text=True, check=True, timeout=15)
      score = json.loads(result.stdout)
      assert score['task'] == task and score['seed'] == 42
      assert score['elapsed_sim_s'] > 0 and score['success'] is False
      assert score['collisions'] == 0
    finally:
      process.terminate()
      process.wait(timeout=5)


if __name__ == '__main__':
  main()
