"""Versioned glove protocol, calibration, features, and speech-event gate.

Pure standard-library code so wire/calibration rules can be tested separately.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

FEATURE_VERSION = "flex5_gravity3_gyro3_v1"
PROTOCOL = "G1"
FINGERS = ("thumb", "index", "middle", "ring", "little")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    tmp.replace(path)


def load_vocabulary(path):
    v = json.loads(Path(path).read_text(encoding="utf-8"))
    labels = v.get("labels", {})
    if "REST" not in labels or len(labels) < 3:
        raise ValueError("Vocabulary must contain REST and at least two gestures")
    tracks = []
    for label, item in labels.items():
        if not label or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789" for c in label):
            raise ValueError("Labels must be uppercase ASCII letters, digits or underscores")
        if label in {"UNKNOWN", "DISCONNECTED", "FAULT", "MOVING"}:
            raise ValueError(f"Reserved label: {label}")
        if not isinstance(item.get("pose"), str) or not item["pose"].strip():
            raise ValueError(f"Describe the pose for {label}")
        if not all(isinstance(item.get(k), str) for k in ("en", "hi")):
            raise ValueError(f"Missing English/Hindi phrases for {label}")
        track = item.get("track")
        if not isinstance(track, int) or not 0 <= track <= 99 or (label != "REST" and track == 0):
            raise ValueError("Tracks must be 1..99, with 0 reserved for REST")
        if label != "REST": tracks.append(track)
    if len(tracks) != len(set(tracks)) or labels["REST"]["track"] != 0:
        raise ValueError("Use distinct tracks; REST must use track 0")
    if labels["REST"]["en"] or labels["REST"]["hi"]:
        raise ValueError("REST must have empty speech text")
    return v


@dataclass(frozen=True)
class Packet:
    seq: int
    ms: int
    hands: int
    adc_max: int
    imu_mask: int
    values: tuple[float, ...]

    @classmethod
    def parse(cls, line):
        if isinstance(line, bytes): line = line.decode("ascii", errors="strict")
        if len(line) > 1000: raise ValueError("Packet too long")
        fields = line.strip().split(",")
        if len(fields) < 6 or fields[0] != PROTOCOL: raise ValueError("Not a G1 sensor packet")
        seq, ms, hands, adc_max, mask = map(int, fields[1:6])
        if hands not in (1, 2) or adc_max not in (1023, 4095): raise ValueError("Unsupported hardware layout")
        if not 0 <= seq <= 0xffffffff or not 0 <= ms <= 0xffffffff:
            raise ValueError("Sequence or timestamp outside uint32")
        if mask != (1 << hands) - 1: raise ValueError("IMU missing or read failed")
        if len(fields) != 6 + 11 * hands: raise ValueError("Wrong sensor count")
        values = tuple(float(x) for x in fields[6:])
        if not all(math.isfinite(x) for x in values): raise ValueError("Non-finite sensor")
        for h in range(hands):
            raw = values[h*11:(h+1)*11]
            if any(not 0 <= x <= adc_max for x in raw[:5]): raise ValueError("ADC out of range")
            if any(abs(x) > 2.1 for x in raw[5:8]): raise ValueError("Accelerometer out of range")
            if any(abs(x) > 251 for x in raw[8:]): raise ValueError("Gyroscope out of range")
        return cls(seq, ms, hands, adc_max, mask, values)

    def encode(self):
        return ",".join([PROTOCOL, str(self.seq), str(self.ms), str(self.hands),
                         str(self.adc_max), str(self.imu_mask)] + [f"{x:.5f}" for x in self.values]) + "\n"


class StreamGuard:
    """Reject replay, reset and long gaps; accepts uint32 counter rollover."""
    def __init__(self): self.previous = None

    def accept(self, packet):
        old = self.previous
        self.previous = packet
        if old is None: return
        if (packet.hands, packet.adc_max) != (old.hands, old.adc_max):
            raise ValueError("Hardware layout changed; reconnect")
        seq_delta = (packet.seq - old.seq) & 0xffffffff
        ms_delta = (packet.ms - old.ms) & 0xffffffff
        if not 0 < seq_delta < 1000 or not 0 < ms_delta <= 500:
            raise ValueError("Duplicate packet, device reset or stream gap; recognition reset")


@dataclass
class Calibration:
    hands: int
    adc_max: int
    open_values: list[float]
    closed_values: list[float]
    gyro_bias: list[float]
    participant: str
    source: str = "hardware"
    version: int = 1

    def validate(self):
        if self.version != 1 or self.hands not in (1, 2) or self.adc_max not in (1023, 4095):
            raise ValueError("Incompatible calibration")
        if not self.participant.strip() or self.source not in ("hardware", "synthetic"):
            raise ValueError("Calibration needs participant and valid source")
        if len(self.open_values) != self.hands*5 or len(self.closed_values) != self.hands*5 or len(self.gyro_bias) != self.hands*3:
            raise ValueError("Calibration has wrong sensor count")
        if not all(math.isfinite(x) for x in self.open_values+self.closed_values+self.gyro_bias):
            raise ValueError("Invalid calibration value")
        if any(not 0 <= x <= self.adc_max for x in self.open_values+self.closed_values):
            raise ValueError("Calibration ADC out of range")
        if any(abs(x) > 20 for x in self.gyro_bias): raise ValueError("Gyro moved during calibration")
        for a, b in zip(self.open_values, self.closed_values):
            if abs(a-b) < self.adc_max*.06: raise ValueError("Bend span too small; inspect each sensor")
            if min(a,b) < self.adc_max*.01 or max(a,b) > self.adc_max*.99:
                raise ValueError("Calibration endpoint at ADC rail; inspect wiring")

    @property
    def id(self): return fingerprint(self.__dict__)

    def save(self, path):
        self.validate()
        atomic_json(path, self.__dict__)

    @classmethod
    def load(cls, path):
        result = cls(**json.loads(Path(path).read_text(encoding="utf-8")))
        result.validate()
        return result

    @classmethod
    def from_samples(cls, opened, closed, participant, source="hardware"):
        if min(len(opened), len(closed)) < 30: raise ValueError("Capture at least 30 readings for each pose")
        p = opened[0]
        if any((s.hands, s.adc_max) != (p.hands, p.adc_max) for s in opened+closed):
            raise ValueError("Mixed device layouts")
        for s in opened+closed:
            for h in range(s.hands):
                v = s.values[h*11:(h+1)*11]
                if not .85 <= math.sqrt(sum(x*x for x in v[5:8])) <= 1.15 or max(abs(x) for x in v[8:]) > 20:
                    raise ValueError("Hold the glove still during calibration")
        def med(samples, offsets):
            return [statistics.median(p.values[h*11+i] for p in samples)
                    for h in range(samples[0].hands) for i in offsets]
        for samples in (opened, closed):
            for h in range(p.hands):
                for i in range(5):
                    vals = [s.values[h*11+i] for s in samples]
                    if statistics.pstdev(vals) > p.adc_max*.03:
                        raise ValueError("Flex readings unstable; hold pose or inspect contacts")
        result = cls(p.hands, p.adc_max, med(opened, range(5)), med(closed, range(5)),
                     med(opened+closed, range(8,11)), participant, source)
        result.validate()
        return result

    def features(self, packet):
        if (packet.hands, packet.adc_max) != (self.hands, self.adc_max):
            raise ValueError("Packet differs from calibration")
        output = []
        for h in range(self.hands):
            raw = packet.values[h*11:(h+1)*11]
            bends = []
            for i, x in enumerate(raw[:5]):
                k = h*5+i
                if x < self.adc_max*.01 or x > self.adc_max*.99: raise ValueError("Flex at ADC rail; check cable")
                bend = (x-self.open_values[k]) / (self.closed_values[k]-self.open_values[k])
                if not -.25 <= bend <= 1.25: raise ValueError("Flex outside calibration; recalibrate")
                bends.append(min(1., max(0., bend)))
            mag = math.sqrt(sum(x*x for x in raw[5:8]))
            if not .85 <= mag <= 1.15: raise ValueError("MOVING: acceleration differs from gravity")
            gyro = [raw[8+i]-self.gyro_bias[h*3+i] for i in range(3)]
            if max(abs(x) for x in gyro) > 35: raise ValueError("MOVING: hold gesture still")
            output += bends + [x/mag for x in raw[5:8]] + [x/250. for x in gyro]
        return output


class EventGate:
    """Time debounce, REST rearm and invalid-input suppression.

    One speech event per gesture. A different stable gesture can speak directly;
    repeating the same gesture needs a sustained REST interval. Faults never rearm.
    """
    def __init__(self, hold=.45, release=.35):
        self.hold, self.release = hold, release
        self.last_emitted = None
        self.reset()

    def reset(self):
        self.candidate = None
        self.since = None
        self.last_time = None
        self.stable = "UNKNOWN"

    def update(self, label, confidence, threshold, now=None):
        now = time.monotonic() if now is None else now
        if self.last_time is not None and (now-self.last_time > .5 or now < self.last_time): self.reset()
        self.last_time = now
        if label in {"FAULT", "UNKNOWN", "DISCONNECTED", "MOVING"} or not math.isfinite(confidence) or confidence < threshold:
            self.candidate = None
            self.since = None
            self.stable = label if label in {"FAULT", "DISCONNECTED", "MOVING"} else "UNKNOWN"
            return self.stable, None
        if label != self.candidate:
            self.candidate, self.since = label, now
        required = self.release if label == "REST" else self.hold
        if now-self.since < required:
            self.stable = "UNKNOWN"
            return self.stable, None
        self.stable = label
        if label == "REST":
            self.last_emitted = None
            return label, None
        if label != self.last_emitted:
            self.last_emitted = label
            return label, label
        return label, None
