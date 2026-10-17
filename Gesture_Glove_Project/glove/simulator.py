"""Deterministic synthetic hardware. Never a real training or accuracy source."""
import random
from core import Calibration, Packet

POSES = {
    "REST": [.35,.45,.45,.45,.45],
    "OPEN_PALM": [0,0,0,0,0], "FIST": [1,1,1,1,1],
    "THUMB_UP": [0,1,1,1,1], "INDEX_UP": [1,0,1,1,1],
    "V_SHAPE": [1,0,0,1,1], "THREE_FINGERS": [1,0,0,0,1],
    "LITTLE_UP": [1,1,1,1,0], "THUMB_LITTLE": [0,1,1,1,0],
}


class Simulator:
    def __init__(self, hands=1, seed=39):
        self.hands = hands
        self.rng = random.Random(seed)
        self.seq = 0
        self.label = "REST"

    def calibration(self, participant="demo"):
        return Calibration(self.hands,4095,[3000.]*5*self.hands,[1300.]*5*self.hands,
                           [0.]*3*self.hands,participant,"synthetic")

    def packet(self):
        self.seq += 1
        vals=[]
        for h in range(self.hands):
            bends = POSES.get(self.label, POSES["REST"]) if h == 0 else POSES["REST"]
            vals += [3000-1700*b+self.rng.gauss(0,8) for b in bends]
            vals += [self.rng.gauss(0,.005), self.rng.gauss(0,.005), 1.+self.rng.gauss(0,.005)]
            vals += [self.rng.gauss(0,.15) for _ in range(3)]
        return Packet(self.seq,self.seq*40,self.hands,4095,(1<<self.hands)-1,tuple(vals))


class DemoClassifier:
    threshold = .75
    synthetic = True
    def predict(self, features):
        distances = sorted((sum((a-b)**2 for a,b in zip(features[:5], p))**.5, name)
                           for name,p in POSES.items())
        d,name = distances[0]
        return name, max(0.,1.-d)
