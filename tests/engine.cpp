#include "engine.h"

#include <chrono>
#include <cmath>
#include <iostream>
#include <string>
#include <thread>

namespace {
bool Near(double a, double b, double eps = 1e-8) { return std::abs(a - b) < eps; }
int Fail(const char* message) {
  std::cerr << message << '\n';
  return 1;
}
}  // namespace
int main(int argc, char** argv) {
  if (argc != 2) return Fail("usage: engine-test SCENE");
  eos_mujoco::SimEngine engine(argv[1]);
  std::string error;
  if (!engine.Load(&error)) return Fail(error.c_str());
  if (!engine.Reset(42, &error)) return Fail(error.c_str());
  const auto initial = engine.GetSnapshot();
  engine.Step(20);
  if (engine.GetScore().grasp) return Fail("momentary/no pad contact scored as retained grasp");
  engine.Reset(42, &error);
  const auto replay = engine.GetSnapshot();
  for (int k = 0; k < 3; ++k)
    if (!Near(initial.object_position[k], replay.object_position[k]))
      return Fail("same seed changed object pose");
  for (int i = 0; i < 2; ++i)
    for (int k = 0; k < 2; ++k)
      if (!Near(initial.obstacle_positions[i][k], replay.obstacle_positions[i][k]))
        return Fail("same seed changed obstacle pose");
  engine.Reset(43, &error);
  const auto variant = engine.GetSnapshot();
  if (Near(initial.object_position[0], variant.object_position[0]) &&
      Near(initial.object_position[1], variant.object_position[1]))
    return Fail("distinct seeds did not vary object pose");
  eos_mujoco::Command joint{};
  joint.type = eos_mujoco::Command::Type::ArmMoveJ;
  joint.values = {-1.2, -1.4, 1.3, -1.5, -1.4, 0, 0};
  const auto base_before_arm = engine.GetSnapshot().base_pose;
  auto result = engine.Execute(joint);
  if (!result.accepted) return Fail("joint motion failed");
  const auto base_after_arm = engine.GetSnapshot().base_pose;
  for (int i = 0; i < 3; ++i)
    if (std::abs(base_before_arm[i] - base_after_arm[i]) > 0.025)
      return Fail("arm motion backdrove held base");
  if (std::abs(engine.GetSnapshot().joint_positions_rad[0] + 1.2) > 0.05)
    return Fail("joint completion reported before movement");
  eos_mujoco::Command staging{};
  staging.type = eos_mujoco::Command::Type::BaseNavigateRelative;
  staging.values = {0.6, 0, 0};
  if (!engine.Execute(staging).accepted || !engine.GetScore().navigation)
    return Fail("reachable staging pose did not score navigation");
  eos_mujoco::Command impossible{};
  impossible.type = eos_mujoco::Command::Type::ArmMoveL;
  impossible.values = {8, 0, 0.4, 0, 0, 0, 1};
  result = engine.Execute(impossible);
  if (result.accepted || result.error_code != "workspace")
    return Fail("out of workspace target accepted");
  auto frame1 = engine.RenderCamera(), frame2 = engine.RenderCamera();
  if (frame1.jpeg.size() < 4 || frame2.jpeg.size() < 4 || frame1.jpeg[0] != 0xff ||
      frame2.jpeg[1] != 0xd8)
    return Fail("repeated JPEG capture failed");
  engine.Reset(42, &error);
  eos_mujoco::Command far{};
  far.type = eos_mujoco::Command::Type::BaseNavigateRelative;
  far.values = {0, -3, 0, 0, 0, 0, 0};
  eos_mujoco::CommandResult motion;
  std::thread worker([&] { motion = engine.Execute(far); });
  auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(1);
  while (!engine.MotionActive() && std::chrono::steady_clock::now() < deadline)
    std::this_thread::yield();
  if (!engine.MotionActive()) return Fail("navigation did not enter active state");
  eos_mujoco::Command stop{};
  stop.type = eos_mujoco::Command::Type::BaseStop;
  if (!engine.Execute(stop).accepted) return Fail("base stop rejected");
  worker.join();
  if (motion.accepted || motion.error_code != "interrupted") {
    std::cerr << "motion=" << motion.accepted << " error=" << motion.error_code << "\n";
    return Fail("stop did not interrupt active navigation");
  }
  eos_mujoco::Command halt{};
  halt.type = eos_mujoco::Command::Type::Halt;
  if (!engine.Execute(halt).accepted || engine.Execute(joint).accepted)
    return Fail("halt did not disable motion");
  if (!engine.Reset(42, &error) || !engine.Execute(joint).accepted)
    return Fail("reset did not clear halt");
  // Deterministic benchmark oracle: all actions use the same public motion API as EOS agents.
  if (!engine.Reset(42, &error)) return Fail("oracle reset failed");
  eos_mujoco::Command oracle_command{};
  oracle_command.type = eos_mujoco::Command::Type::BaseNavigateRelative;
  oracle_command.values = {0.6, 0, 0};
  if (!engine.Execute(oracle_command).accepted) return Fail("oracle navigation failed");
  oracle_command.type = eos_mujoco::Command::Type::ArmMoveJ;
  const std::array<double, 7> above = {2.7368, -0.4246, -1.1208, -0.4245, 4.7113, -2.1504, 0};
  const std::array<double, 7> pickup = {2.7604, -0.2680, -1.1200, -0.2037, 4.6546, -2.1504, 0};
  const std::array<double, 7> placement = {3.3459, -0.2874, -1.1062, -0.2623, 4.6620, -2.1504, 0};
  oracle_command.values = above;
  if (!engine.Execute(oracle_command).accepted) return Fail("oracle above-object move failed");
  oracle_command.values = pickup;
  if (!engine.Execute(oracle_command).accepted) return Fail("oracle pickup move failed");
  oracle_command.type = eos_mujoco::Command::Type::GripperMove;
  oracle_command.close = true;
  oracle_command.force_n = 5;
  if (!engine.Execute(oracle_command).accepted) return Fail("oracle grasp closure failed");
  engine.Step(200);
  if (engine.GetScore().grasp) return Fail("tabletop-only grasp scored as retained lift");
  oracle_command.type = eos_mujoco::Command::Type::ArmMoveJ;
  oracle_command.values = above;
  if (!engine.Execute(oracle_command).accepted) return Fail("oracle lift failed");
  engine.Step(200);
  if (!engine.GetScore().grasp || engine.GetSnapshot().object_position[2] < 0.82)
    return Fail("lifted bilateral grasp was not scored");
  oracle_command.values = placement;
  if (!engine.Execute(oracle_command).accepted) return Fail("oracle placement move failed");
  oracle_command.type = eos_mujoco::Command::Type::GripperMove;
  oracle_command.close = false;
  oracle_command.force_n = 0;
  if (!engine.Execute(oracle_command).accepted) return Fail("oracle release failed");
  engine.Step(300);
  const auto score = engine.GetScore();
  if (!score.navigation || !score.grasp || !score.placement)
    return Fail("oracle did not score placement");
  if (!engine.GetSnapshot().object_held_id.empty()) return Fail("placed object remained held");
  std::cout << "engine ok: oracle score 1/1/1, collisions=" << score.collisions
            << ", sim_time=" << score.elapsed_s << "\n";
  return 0;
}
