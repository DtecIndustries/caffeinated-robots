"""
Minimal Feetech SCS/STS servo client over serial.
No external SDK required — implements the packet protocol directly via pyserial.

Packet format: 0xFF 0xFF ID LEN INST [params] CHECKSUM
Checksum     : (~(ID + LEN + INST + params)) & 0xFF
"""
import serial
import time

_BAUD        = 1_000_000
_TIMEOUT     = 0.1          # seconds to wait for a response

# Register addresses (SCS/STS series)
_REG_TORQUE_ENABLE    = 40
_REG_GOAL_POSITION    = 42  # 2 bytes, little-endian
_REG_GOAL_SPEED       = 46  # 2 bytes — 0 = max speed, lower = slower
_REG_PRESENT_POSITION = 56  # 2 bytes, little-endian

_INST_READ  = 0x02
_INST_WRITE = 0x03


def _checksum(data: list[int]) -> int:
    return (~sum(data)) & 0xFF


def _build_packet(servo_id: int, instruction: int, params: list[int]) -> bytes:
    length = len(params) + 2  # params + instruction + checksum
    body = [servo_id, length, instruction] + params
    return bytes([0xFF, 0xFF] + body + [_checksum(body)])


class ServoClient:
    def __init__(self, port: str, servo_ids: list[int]):
        self._port_name = port
        self._ids = servo_ids
        self._ser: serial.Serial | None = None

    def connect(self):
        self._ser = serial.Serial(self._port_name, baudrate=_BAUD, timeout=_TIMEOUT)

    def disconnect(self):
        if self._ser and self._ser.is_open:
            self._ser.close()

    # ------------------------------------------------------------------ reads

    def _read_register(self, servo_id: int, reg: int, length: int) -> bytes | None:
        pkt = _build_packet(servo_id, _INST_READ, [reg, length])
        self._ser.reset_input_buffer()
        self._ser.write(pkt)
        resp = self._ser.read(6 + length)
        if len(resp) == 6 + length and resp[0] == 0xFF and resp[1] == 0xFF and resp[2] == servo_id:
            return resp[5:5 + length]
        return None

    def read_position(self, servo_id: int) -> int | None:
        """Return current position (0–4095) or None if no response."""
        raw = self._read_register(servo_id, _REG_PRESENT_POSITION, 2)
        if raw:
            return raw[0] | (raw[1] << 8)
        return None

    def read_torque_enabled(self, servo_id: int) -> bool | None:
        """Return torque state, or None if no response."""
        raw = self._read_register(servo_id, _REG_TORQUE_ENABLE, 1)
        if raw is not None:
            return bool(raw[0])
        return None

    def read_positions(self) -> dict[int, int | None]:
        return {sid: self.read_position(sid) for sid in self._ids}

    # ----------------------------------------------------------------- writes

    def set_speed(self, servo_id: int, speed: int):
        """Set max speed for a servo. Lower = slower. 0 = maximum speed."""
        lo, hi = speed & 0xFF, (speed >> 8) & 0xFF
        pkt = _build_packet(servo_id, _INST_WRITE, [_REG_GOAL_SPEED, lo, hi])
        self._ser.write(pkt)

    def set_speed_all(self, speed: int):
        for sid in self._ids:
            self.set_speed(sid, speed)

    def set_position(self, servo_id: int, position: int):
        lo, hi = position & 0xFF, (position >> 8) & 0xFF
        pkt = _build_packet(servo_id, _INST_WRITE, [_REG_GOAL_POSITION, lo, hi])
        self._ser.write(pkt)

    def set_position_slow(self, servo_id: int, target: int, duration: float = 2.0, steps: int = 40):
        """Interpolate from current position to target over `duration` seconds."""
        current = self.read_position(servo_id)
        if current is None:
            raise RuntimeError(f"Servo {servo_id} did not respond")
        delay = duration / steps
        for i in range(1, steps + 1):
            pos = int(current + (target - current) * i / steps)
            self.set_position(servo_id, pos)
            time.sleep(delay)

    def set_positions(self, targets: dict[int, int]):
        for sid, pos in targets.items():
            self.set_position(sid, pos)

    def enable_torque(self, servo_id: int, enabled: bool = True):
        pkt = _build_packet(servo_id, _INST_WRITE, [_REG_TORQUE_ENABLE, int(enabled)])
        self._ser.write(pkt)

    def enable_torque_all(self, enabled: bool = True):
        for sid in self._ids:
            self.enable_torque(sid, enabled)
