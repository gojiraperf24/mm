"""Strict append-only labeled feature recordings with provenance."""
import csv
from datetime import datetime, timezone
import math
from pathlib import Path
from core import FEATURE_VERSION, fingerprint

META = ["label", "participant", "session", "trial", "utc", "source", "hands", "feature_version", "vocabulary_id", "calibration_id"]


def columns(hands): return META + [f"f{i:02}" for i in range(hands*11)]


class Recorder:
    def __init__(self, path, vocabulary, calibration, participant, session, trial):
        if not all(str(x).strip() for x in (participant,session,trial)): raise ValueError("Participant, session and trial are required")
        if participant != calibration.participant: raise ValueError("Calibrate for this participant first")
        self.path = Path(path)
        self.calibration = calibration
        self.vocabulary = vocabulary
        self.participant, self.session, self.trial = participant,session,trial
        self.vocabulary_id = fingerprint(vocabulary)
        self.count = 0
        self.file = None
        if self.path.exists() and self.path.stat().st_size:
            rows = read_dataset(self.path,vocabulary)
            if any(int(r["hands"]) != calibration.hands or r["source"] != calibration.source for r in rows):
                raise ValueError("Do not mix real/synthetic recordings or hardware layouts in one CSV")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        new = not self.path.exists() or not self.path.stat().st_size
        self.file = self.path.open("a",newline="",encoding="utf-8")
        self.writer = csv.DictWriter(self.file,fieldnames=columns(calibration.hands))
        if new: self.writer.writeheader(); self.file.flush()

    def write(self, label, features):
        if label not in self.vocabulary["labels"]: raise ValueError("Label outside vocabulary")
        if len(features) != self.calibration.hands*11 or not all(math.isfinite(x) for x in features):
            raise ValueError("Invalid feature vector")
        row = dict(label=label,participant=self.participant,session=self.session,trial=self.trial,
                   utc=datetime.now(timezone.utc).isoformat(),source=self.calibration.source,
                   hands=self.calibration.hands,feature_version=FEATURE_VERSION,
                   vocabulary_id=self.vocabulary_id,calibration_id=self.calibration.id)
        row.update({f"f{i:02}": f"{x:.8f}" for i,x in enumerate(features)})
        self.writer.writerow(row)
        self.file.flush()
        self.count += 1

    def close(self):
        if self.file: self.file.close(); self.file = None


def read_dataset(path, vocabulary):
    with Path(path).open(newline="",encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        header = reader.fieldnames
    if not rows: raise ValueError("Dataset has no recordings")
    hands = int(rows[0].get("hands","0"))
    if hands not in (1,2) or header != columns(hands): raise ValueError("CSV header/layout is incompatible")
    vid = fingerprint(vocabulary)
    for n,r in enumerate(rows,2):
        if None in r or any(x is None for x in r.values()): raise ValueError(f"Malformed CSV row {n}")
        if r["label"] not in vocabulary["labels"] or r["vocabulary_id"] != vid: raise ValueError(f"Vocabulary mismatch row {n}")
        if r["feature_version"] != FEATURE_VERSION or int(r["hands"]) != hands: raise ValueError(f"Feature schema mismatch row {n}")
        if r["source"] not in ("hardware","synthetic"): raise ValueError(f"Missing provenance row {n}")
        if not all(r[k].strip() for k in ("participant","session","trial","utc","calibration_id")): raise ValueError(f"Missing metadata row {n}")
        try: dt = datetime.fromisoformat(r["utc"])
        except ValueError as exc: raise ValueError(f"Invalid timestamp row {n}") from exc
        if dt.tzinfo is None or len(r["calibration_id"]) != 64: raise ValueError(f"Invalid metadata row {n}")
        vals = [float(r[k]) for k in columns(hands)[len(META):]]
        if not all(math.isfinite(x) for x in vals): raise ValueError(f"Non-finite feature row {n}")
        for h in range(hands):
            v=vals[h*11:(h+1)*11]
            if any(not 0 <= x <= 1 for x in v[:5]) or any(abs(x)>1.01 for x in v[5:]) or not .98 <= sum(x*x for x in v[5:8]) <= 1.02:
                raise ValueError(f"Feature outside normalized range row {n}")
    if len({r['source'] for r in rows}) != 1: raise ValueError("Mixed synthetic and hardware samples")
    return rows
