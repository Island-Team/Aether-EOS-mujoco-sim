#include "service.h"

#include <atomic>
#include <csignal>
#include <exception>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
std::atomic_bool stop{false};
void StopSignal(int) { stop.store(true); }
}

int main(int argc, char** argv) {
  try {
    std::filesystem::path socket;
    std::filesystem::path benchmark_socket;
    std::filesystem::path scene;
    bool manual_step = false;
    for (int i = 1; i < argc; ++i) {
      const std::string key = argv[i];
      if (key == "--manual-step") { manual_step = true; continue; }
      if (key == "--help") {
        std::cout << "Usage: eos-mujoco-sim --socket PATH --benchmark-socket PATH --scene PATH [--manual-step]\n";
        return 0;
      }
      if (i + 1 >= argc) throw std::invalid_argument("missing value for " + key);
      const std::string value = argv[++i];
      if (key == "--socket") socket = value;
      else if (key == "--benchmark-socket") benchmark_socket = value;
      else if (key == "--scene") scene = value;
      else throw std::invalid_argument("unknown option: " + key);
    }
    if (!socket.is_absolute() || !benchmark_socket.is_absolute() || !scene.is_absolute())
      throw std::invalid_argument("--socket, --benchmark-socket, and --scene must be absolute paths");
    if (socket == benchmark_socket)
      throw std::invalid_argument("simulator and benchmark sockets must differ");
    if (!std::filesystem::is_regular_file(scene))
      throw std::invalid_argument("scene does not exist: " + scene.string());
    std::signal(SIGINT, StopSignal);
    std::signal(SIGTERM, StopSignal);
    eos_mujoco::Serve(socket, benchmark_socket, scene, stop, manual_step);
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "eos-mujoco-sim: " << error.what() << '\n';
    return 1;
  }
}
