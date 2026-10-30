#include "v2_service.h"

#include <google/protobuf/struct.pb.h>
#include <google/protobuf/util/json_util.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

#include <array>
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

#include "engine.h"

namespace eos_mujoco {
namespace {
using Struct = google::protobuf::Struct;
using Value = google::protobuf::Value;
constexpr std::uint32_t kMaxMetadata = 65536;
constexpr std::uint32_t kMaxPayload = 8 * 1024 * 1024;

bool ReadAll(int fd, void* buffer, size_t length) {
  auto* bytes = static_cast<unsigned char*>(buffer);
  while (length) {
    const auto count = ::read(fd, bytes, length);
    if (count <= 0) return false;
    bytes += count;
    length -= static_cast<size_t>(count);
  }
  return true;
}
bool WriteAll(int fd, const void* buffer, size_t length) {
  const auto* bytes = static_cast<const unsigned char*>(buffer);
  while (length) {
    const auto count = ::send(fd, bytes, length, MSG_NOSIGNAL);
    if (count <= 0) return false;
    bytes += count;
    length -= static_cast<size_t>(count);
  }
  return true;
}
std::uint32_t Decode32(const unsigned char* bytes) {
  return std::uint32_t(bytes[0]) | (std::uint32_t(bytes[1]) << 8) |
         (std::uint32_t(bytes[2]) << 16) | (std::uint32_t(bytes[3]) << 24);
}
void Encode32(std::uint32_t value, unsigned char* bytes) {
  for (int i = 0; i < 4; ++i)
    bytes[i] = static_cast<unsigned char>(value >> (8 * i));
}
const Value* Field(const Struct& value, const char* key) {
  const auto it = value.fields().find(key);
  return it == value.fields().end() ? nullptr : &it->second;
}
std::string String(const Struct& value, const char* key) {
  const auto* field = Field(value, key);
  return field && field->kind_case() == Value::kStringValue
             ? field->string_value()
             : "";
}
bool Number(const Struct& value, const char* key, double* output) {
  const auto* field = Field(value, key);
  if (!field || field->kind_case() != Value::kNumberValue ||
      !std::isfinite(field->number_value()))
    return false;
  *output = field->number_value();
  return true;
}
void Set(Struct* value, const char* key, const std::string& text) {
  (*value->mutable_fields())[key].set_string_value(text);
}
void Set(Struct* value, const char* key, const char* text) {
  Set(value, key, std::string(text));
}
void Set(Struct* value, const char* key, double number) {
  (*value->mutable_fields())[key].set_number_value(number);
}
void Set(Struct* value, const char* key, bool boolean) {
  (*value->mutable_fields())[key].set_bool_value(boolean);
}
template <size_t N>
void SetArray(Struct* value, const char* key,
              const std::array<double, N>& values) {
  auto* list = (*value->mutable_fields())[key].mutable_list_value();
  for (double number : values) list->add_values()->set_number_value(number);
}
void Reject(Struct* reply, const std::string& message) {
  Set(reply, "ok", false);
  Set((*reply->mutable_fields())["error"].mutable_struct_value(), "message",
      message);
}
void Handle(int fd, SimEngine& engine) {
  unsigned char header[8];
  if (!ReadAll(fd, header, sizeof(header))) return;
  const auto metadata_size = Decode32(header);
  const auto payload_size = Decode32(header + 4);
  if (!metadata_size || metadata_size > kMaxMetadata || payload_size) return;
  std::string body(metadata_size, '\0');
  if (!ReadAll(fd, body.data(), body.size())) return;
  Struct request;
  if (!google::protobuf::util::JsonStringToMessage(body, &request).ok()) return;
  Struct reply;
  Set(&reply, "version", "2.0.0");
  Set(&reply, "id", String(request, "id"));
  Set(&reply, "ok", true);
  const auto snapshot = engine.GetSnapshot();
  Set(&reply, "timestamp_ns", snapshot.simulation_time_s * 1e9);
  Set(&reply, "sequence", static_cast<double>(snapshot.sequence));
  std::vector<std::uint8_t> payload;
  if (String(request, "version") != "2.0.0" || String(request, "id").empty()) {
    Reject(&reply, "invalid protocol version or request ID");
  } else {
    const auto op = String(request, "op");
    if (op == "health") {
      Set(&reply, "accepted", true);
    } else if (op == "camera_capture") {
      const auto frame = engine.RenderCamera();
      if (frame.jpeg.empty())
        Reject(&reply, "camera render unavailable");
      else {
        Set(&reply, "format", "jpeg");
        Set(&reply, "rgb_length", static_cast<double>(frame.jpeg.size()));
        Set(&reply, "depth_available", false);
        Set(&reply, "width_px", static_cast<double>(frame.width));
        Set(&reply, "height_px", static_cast<double>(frame.height));
        Set(&reply, "timestamp_ns", static_cast<double>(frame.timestamp_ns));
        Set(&reply, "sequence", static_cast<double>(frame.sequence));
        payload = frame.jpeg;
      }
    } else if (op == "base_observe") {
      SetArray(
          &reply, "position_m",
          std::array<double, 2>{snapshot.base_pose[0], snapshot.base_pose[1]});
      SetArray(&reply, "linear_velocity_m_s",
               std::array<double, 2>{snapshot.base_velocity[0],
                                     snapshot.base_velocity[1]});
      Set(&reply, "yaw_rad", snapshot.base_pose[2]);
      Set(&reply, "angular_velocity_rad_s", snapshot.base_velocity[2]);
    } else if (op == "manipulator_observe") {
      SetArray(&reply, "joint_positions_rad", snapshot.joint_positions_rad);
      SetArray(&reply, "joint_velocities_rad_s",
               snapshot.joint_velocities_rad_s);
      SetArray(&reply, "end_position_m", snapshot.ee_position);
      SetArray(&reply, "end_orientation_xyzw", snapshot.ee_orientation_xyzw);
    } else if (op == "base_move") {
      Command command{Command::Type::BaseDrive};
      double duration = 0;
      if (!Number(request, "linear_x_m_s", &command.values[0]) ||
          !Number(request, "linear_y_m_s", &command.values[1]) ||
          !Number(request, "angular_z_rad_s", &command.values[2]) ||
          !Number(request, "valid_for_ms", &duration) || duration <= 0 ||
          duration > 5000) {
        Reject(&reply, "invalid base movement");
      } else {
        command.values[3] = duration / 1000.0;
        const auto result = engine.Execute(command);
        Set(&reply, "accepted", result.accepted);
        if (!result.accepted) Reject(&reply, result.error_code);
      }
    } else if (op == "manipulator_move") {
      Command command{Command::Type::ArmMoveJ};
      const auto* positions = Field(request, "joint_positions_rad");
      if (!positions || positions->kind_case() != Value::kListValue ||
          positions->list_value().values_size() != 6) {
        Reject(&reply, "joint_positions_rad must contain six values");
      } else {
        bool valid = true;
        for (int i = 0; i < 6; ++i) {
          const auto& field = positions->list_value().values(i);
          valid &= field.kind_case() == Value::kNumberValue &&
                   std::isfinite(field.number_value());
          command.values[i] = field.number_value();
        }
        if (!valid)
          Reject(&reply, "invalid joint position");
        else {
          const auto result = engine.Execute(command);
          Set(&reply, "accepted", result.accepted);
          if (!result.accepted) Reject(&reply, result.error_code);
        }
      }
    } else if (op == "stop") {
      const auto base = engine.Execute(Command{Command::Type::BaseStop});
      const auto arm = engine.Execute(Command{Command::Type::ArmStop});
      Set(&reply, "accepted", base.accepted && arm.accepted);
      if (!base.accepted || !arm.accepted) Reject(&reply, "stop failed");
    } else {
      Reject(&reply, "unsupported operation");
    }
  }
  std::string encoded;
  if (!google::protobuf::util::MessageToJsonString(reply, &encoded).ok() ||
      encoded.size() > kMaxMetadata || payload.size() > kMaxPayload)
    return;
  Encode32(static_cast<std::uint32_t>(encoded.size()), header);
  Encode32(static_cast<std::uint32_t>(payload.size()), header + 4);
  WriteAll(fd, header, sizeof(header)) &&
      WriteAll(fd, encoded.data(), encoded.size()) &&
      WriteAll(fd, payload.data(), payload.size());
}
}  // namespace

V2Server::V2Server(const std::filesystem::path& socket, SimEngine& engine)
    : socket_(socket), engine_(engine) {
  std::filesystem::create_directories(socket_.parent_path());
  if (socket_.string().size() >= sizeof(sockaddr_un::sun_path))
    throw std::invalid_argument("v2 socket path is too long");
  listener_ = ::socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
  if (listener_ < 0) throw std::runtime_error("cannot create v2 socket");
  sockaddr_un address{};
  address.sun_family = AF_UNIX;
  std::strcpy(address.sun_path, socket_.c_str());
  std::error_code ignored;
  std::filesystem::remove(socket_, ignored);
  if (::bind(listener_, reinterpret_cast<sockaddr*>(&address),
             sizeof(address)) < 0 ||
      ::chmod(socket_.c_str(), S_IRUSR | S_IWUSR) < 0 ||
      ::listen(listener_, 16) < 0) {
    ::close(listener_);
    std::filesystem::remove(socket_, ignored);
    throw std::runtime_error("cannot bind or secure v2 socket");
  }
  worker_ = std::thread([this] { Run(); });
}
V2Server::~V2Server() {
  stopping_.store(true);
  ::shutdown(listener_, SHUT_RDWR);
  ::close(listener_);
  if (worker_.joinable()) worker_.join();
  std::error_code ignored;
  std::filesystem::remove(socket_, ignored);
}
void V2Server::Run() {
  while (!stopping_.load()) {
    const int fd = ::accept4(listener_, nullptr, nullptr, SOCK_CLOEXEC);
    if (fd < 0) continue;
    timeval timeout{2, 0};
    ::setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    ::setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    Handle(fd, engine_);
    ::close(fd);
  }
}
}  // namespace eos_mujoco
