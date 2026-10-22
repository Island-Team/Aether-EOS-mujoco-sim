#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/tools/launcher-common.sh"
load_launch_config
umask 077

usage() {
  cat <<'EOF'
Usage: ./launch.sh [--scene pick-place|navigation|PATH] [--gui|--no-gui]
                   [--run-dir PATH] [--executable PATH] [--manual-step]

Start the standalone simulator in the background. --gui also opens MuJoCo's
independent viewer for the same XML; it does not display the live EOS state.
Defaults match launch.conf.example and can be overridden by launch.conf.
Use ./kill.sh [--run-dir PATH] to stop processes started by this script.
EOF
}

scene=$SIM_SCENE
run_dir=$SIM_RUN_DIR
executable=$SIM_EXECUTABLE
gui=$SIM_GUI
manual_step=$SIM_MANUAL_STEP
while (($#)); do
  case "$1" in
    --scene|--run-dir|--executable)
      if (($# < 2)); then usage >&2; exit 2; fi
      case "$1" in
        --scene) scene=$2 ;;
        --run-dir) run_dir=$2 ;;
        --executable) executable=$2 ;;
      esac
      shift 2 ;;
    --gui) gui=true; shift ;;
    --no-gui) gui=false; shift ;;
    --manual-step) manual_step=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

case "$scene" in
  pick-place) scene=assets/scene.xml ;;
  navigation) scene=assets/scenes/navigation/scene.xml ;;
esac
scene=$(resolve_launch_path "$scene")
run_dir=$(resolve_launch_path "$run_dir")
executable=$(resolve_launch_path "$executable")
[[ -f "$scene" ]] || { echo "Scene not found: $scene" >&2; exit 2; }
[[ -x "$executable" ]] || { echo "Build the simulator first: $executable" >&2; exit 2; }
[[ "$gui" == true || "$gui" == false ]] || { echo "SIM_GUI must be true or false" >&2; exit 2; }
[[ "$manual_step" == true || "$manual_step" == false ]] || {
  echo "SIM_MANUAL_STEP must be true or false" >&2; exit 2;
}
if [[ "$gui" == true ]]; then
  [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] || {
    echo "--gui requires a desktop display; use --no-gui on a headless host" >&2
    exit 2
  }
  "$launcher_root/tools/scene-view.sh" --check --scene "$scene" >/dev/null
fi

if [[ ! -e "$run_dir" ]]; then mkdir -p -m 700 -- "$run_dir"; fi
private_run_dir "$run_dir" || {
  echo "Run directory must be owned by you and accessible only to you: $run_dir" >&2
  exit 2
}
exec 9>"$run_dir/launcher.lock"
flock -w 10 9 || { echo "Another launcher operation is active" >&2; exit 1; }
sim_pid_file="$run_dir/simulator.pid"
viewer_pid_file="$run_dir/viewer.pid"
socket="$run_dir/simulator.sock"
benchmark_socket="$run_dir/benchmark.sock"
if managed_pid "$sim_pid_file" >/dev/null || managed_pid "$viewer_pid_file" >/dev/null; then
  echo "A managed process is already running in $run_dir; use ./kill.sh first" >&2
  exit 1
fi
rm -f -- "$sim_pid_file" "$viewer_pid_file"
if [[ -e "$socket" || -S "$socket" || -e "$benchmark_socket" || -S "$benchmark_socket" ]]; then
  echo "Socket already exists in $run_dir; check for another server before removing it" >&2
  exit 1
fi

command=("$executable" --socket "$socket" --benchmark-socket "$benchmark_socket" --scene "$scene")
if [[ "$manual_step" == true ]]; then command+=(--manual-step); fi
nohup "${command[@]}" >"$run_dir/simulator.log" 2>&1 </dev/null 9>&- &
sim_pid=$!
if ! record_process "$sim_pid_file" "$sim_pid"; then
  echo "Simulator exited during startup; see $run_dir/simulator.log" >&2
  exit 1
fi

startup_failed() {
  echo "$1; see $run_dir/simulator.log" >&2
  terminate_managed "$viewer_pid_file" || true
  terminate_managed "$sim_pid_file" || true
  rm -f -- "$socket" "$benchmark_socket"
  exit 1
}

ready=false
for ((attempt = 0; attempt < 100; ++attempt)); do
  if [[ -S "$socket" && -S "$benchmark_socket" ]]; then ready=true; break; fi
  if ! managed_pid "$sim_pid_file" >/dev/null; then break; fi
  sleep 0.1
done
[[ "$ready" == true ]] || startup_failed "Simulator did not open both sockets"

if [[ "$gui" == true ]]; then
  nohup "$launcher_root/tools/scene-view.sh" --scene "$scene" >"$run_dir/viewer.log" 2>&1 </dev/null 9>&- &
  viewer_pid=$!
  record_process "$viewer_pid_file" "$viewer_pid" || startup_failed "Viewer exited during startup"
  sleep 0.4
  managed_pid "$viewer_pid_file" >/dev/null || startup_failed "Viewer exited during startup"
fi

echo "Simulator started (PID $sim_pid)"
echo "Scene: $scene"
echo "EOS socket: $socket"
echo "Benchmark socket: $benchmark_socket"
echo "Log: $run_dir/simulator.log"
if [[ "$gui" == true ]]; then
  echo "Independent viewer started (PID $viewer_pid); log: $run_dir/viewer.log"
fi
