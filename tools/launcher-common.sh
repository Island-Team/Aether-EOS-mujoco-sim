#!/usr/bin/env bash

launcher_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

load_launch_config() {
  if [[ -f "$launcher_root/.env" ]]; then
    # The local environment and launch configuration are operator-owned shell files.
    source "$launcher_root/.env"
  fi
  SIM_EXECUTABLE=${SIM_EXECUTABLE:-build/eos-mujoco-sim}
  SIM_SCENE=${SIM_SCENE:-assets/scene.xml}
  SIM_RUN_DIR=${SIM_RUN_DIR:-.run/mujoco}
  SIM_GUI=${SIM_GUI:-false}
  SIM_MANUAL_STEP=${SIM_MANUAL_STEP:-false}
  if [[ -f "$launcher_root/launch.conf" ]]; then
    source "$launcher_root/launch.conf"
  fi
}

resolve_launch_path() {
  if [[ "$1" == /* ]]; then
    realpath -m "$1"
  else
    realpath -m "$launcher_root/$1"
  fi
}

private_run_dir() {
  local directory=$1 mode
  [[ -d "$directory" && -O "$directory" ]] || return 1
  mode=$(stat -c '%a' "$directory") || return 1
  (( (8#$mode & 077) == 0 ))
}

process_start() {
  local pid=$1 stat fields
  [[ "$pid" =~ ^[0-9]+$ && -r "/proc/$pid/stat" ]] || return 1
  stat=$(<"/proc/$pid/stat")
  stat=${stat##*) }
  read -r -a fields <<< "$stat"
  [[ ${#fields[@]} -ge 20 && ${fields[0]} != Z ]] || return 1
  printf '%s\n' "${fields[19]}"
}

managed_pid() {
  local file=$1 pid started current
  [[ -f "$file" ]] || return 1
  read -r pid started < "$file" || return 1
  [[ "$pid" =~ ^[0-9]+$ && "$started" =~ ^[0-9]+$ ]] || return 1
  current=$(process_start "$pid") || return 1
  [[ "$current" == "$started" ]] || return 1
  printf '%s\n' "$pid"
}

record_process() {
  local file=$1 pid=$2 started
  started=$(process_start "$pid") || return 1
  printf '%s %s\n' "$pid" "$started" > "$file"
}

terminate_managed() {
  local file=$1 pid attempt
  if ! pid=$(managed_pid "$file"); then
    rm -f -- "$file"
    return 1
  fi
  kill -TERM "$pid" 2>/dev/null || true
  for ((attempt = 0; attempt < 50; ++attempt)); do
    if ! managed_pid "$file" >/dev/null; then break; fi
    sleep 0.1
  done
  if managed_pid "$file" >/dev/null; then
    kill -KILL "$pid" 2>/dev/null || true
  fi
  rm -f -- "$file"
}
