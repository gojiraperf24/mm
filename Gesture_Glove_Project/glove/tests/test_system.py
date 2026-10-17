import csv
from dataclasses import replace
import json
import math
from pathlib import Path
import queue
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Calibration, Packet, EventGate, StreamGuard, load_vocabulary
from dataset import Recorder,read_dataset
from simulator import Simulator
from training import Classifier,train,split_groups
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


class PacketTests(unittest.TestCase):
    def setUp(self): self.p=Simulator().packet()
    def test_round_trip(self):
        parsed=Packet.parse(self.p.encode().encode()); self.assertEqual(parsed.seq,self.p.seq)
        self.assertEqual(len(parsed.values),11)
    def test_nan(self):
        fields=self.p.encode().strip().split(','); fields[7]='nan'
        with self.assertRaisesRegex(ValueError,'Non-finite'): Packet.parse(','.join(fields))
    def test_bad_mask(self):
        with self.assertRaisesRegex(ValueError,'IMU'): Packet.parse(replace(self.p,imu_mask=0).encode())
    def test_bad_shape(self):
        with self.assertRaisesRegex(ValueError,'count'): Packet.parse(self.p.encode().strip()+',1')
    def test_invalid_wire_units(self):
        values=list(self.p.values); values[8]=260
        with self.assertRaisesRegex(ValueError,'Gyroscope'): Packet.parse(replace(self.p,values=tuple(values)).encode())
    def test_uint32_bounds(self):
        with self.assertRaises(ValueError): Packet.parse(replace(self.p,seq=-1).encode())
    def test_two_hands(self): self.assertEqual(len(Packet.parse(Simulator(2).packet().encode()).values),22)
    def test_guard_duplicate_and_reset(self):
        guard=StreamGuard(); guard.accept(self.p)
        with self.assertRaises(ValueError): guard.accept(self.p)
        with self.assertRaises(ValueError): guard.accept(replace(self.p,seq=0,ms=0))
    def test_guard_counter_rollover(self):
        guard=StreamGuard(); guard.accept(replace(self.p,seq=0xffffffff,ms=0xfffffff0))
        guard.accept(replace(self.p,seq=0,ms=24))


class CalibrationTests(unittest.TestCase):
    def setUp(self): self.sim=Simulator(); self.cal=self.sim.calibration()
    def test_decreasing_voltage(self):
        self.sim.label='FIST'; self.assertTrue(all(x>.95 for x in self.cal.features(self.sim.packet())[:5]))
    def test_increasing_voltage(self):
        self.cal.open_values=[1300.]*5; self.cal.closed_values=[3000.]*5
        self.sim.label='OPEN_PALM'; self.assertTrue(all(x>.95 for x in self.cal.features(self.sim.packet())[:5]))
    def test_bad_span(self):
        self.cal.closed_values=self.cal.open_values.copy()
        with self.assertRaisesRegex(ValueError,'span'): self.cal.validate()
    def test_disconnected_flex_rail(self):
        p=self.sim.packet(); v=list(p.values); v[0]=0
        with self.assertRaisesRegex(ValueError,'rail'): self.cal.features(replace(p,values=tuple(v)))
    def test_moving_wrist(self):
        p=self.sim.packet(); v=list(p.values); v[8]=90
        with self.assertRaisesRegex(ValueError,'MOVING'): self.cal.features(replace(p,values=tuple(v)))
    def test_zero_acceleration(self):
        p=self.sim.packet(); v=list(p.values); v[5:8]=[0,0,0]
        with self.assertRaisesRegex(ValueError,'MOVING'): self.cal.features(replace(p,values=tuple(v)))
    def test_endpoint_capture(self):
        self.sim.label='OPEN_PALM'; opened=[self.sim.packet() for _ in range(50)]
        self.sim.label='FIST'; closed=[self.sim.packet() for _ in range(50)]
        cal=Calibration.from_samples(opened,closed,'p01','synthetic')
        self.assertTrue(all(abs(x-3000)<15 for x in cal.open_values))
    def test_reject_short_capture(self):
        p=self.sim.packet()
        with self.assertRaisesRegex(ValueError,'30'): Calibration.from_samples([p]*5,[p]*40,'p01')
    def test_save_reload_id(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'cal.json'; self.cal.save(path)
            self.assertEqual(Calibration.load(path).id,self.cal.id)
    def test_wrong_layout(self):
        with self.assertRaisesRegex(ValueError,'differs'): self.cal.features(Simulator(2).packet())


class GateTests(unittest.TestCase):
    def setUp(self): self.gate=EventGate()
    def feed(self,label,times,score=.9):
        events=[]
        for t in times:
            _,event=self.gate.update(label,score,.75,t)
            if event: events.append(event)
        return events
    def test_hold_speaks_once(self): self.assertEqual(self.feed('FIST',[0,.2,.46,.7,.9]),['FIST'])
    def test_uncertain_never_speaks(self): self.assertEqual(self.feed('FIST',[0,.2,.46,.7],.5),[])
    def test_fault_does_not_repeat(self):
        self.feed('FIST',[0,.2,.46]); self.feed('FAULT',[.5]); self.assertEqual(self.feed('FIST',[.6,.8,1.07]),[])
    def test_rest_rearms(self):
        self.feed('FIST',[0,.2,.46]); self.feed('REST',[.5,.7,.86]); self.assertEqual(self.feed('FIST',[.9,1.1,1.36]),['FIST'])
    def test_short_rest_does_not_rearm(self):
        self.feed('FIST',[0,.2,.46]); self.feed('REST',[.5,.6]); self.assertEqual(self.feed('FIST',[.7,.9,1.16]),[])
    def test_different_pose_can_speak(self):
        self.feed('FIST',[0,.2,.46]); self.assertEqual(self.feed('INDEX_UP',[.5,.7,.96]),['INDEX_UP'])
    def test_gap_resets_debounce(self): self.assertEqual(self.feed('FIST',[0,.2,1.0]),[])
    def test_candidate_change_clears_stable(self):
        self.feed('FIST',[0,.2,.46]); stable,event=self.gate.update('INDEX_UP',.9,.75,.5)
        self.assertEqual(stable,'UNKNOWN'); self.assertIsNone(event)


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'data.csv'
        self.vocab=load_vocabulary(ROOT/'vocabulary.json'); self.sim=Simulator(); self.cal=self.sim.calibration('p01')
    def tearDown(self): self.tmp.cleanup()
    def record(self,cal=None):
        cal=cal or self.cal
        r=Recorder(self.path,self.vocab,cal,'p01','visit1','trial1')
        r.write('REST',cal.features(self.sim.packet())); r.close()
    def test_metadata_roundtrip(self):
        self.record(); rows=read_dataset(self.path,self.vocab)
        self.assertEqual(rows[0]['calibration_id'],self.cal.id)
        self.assertEqual(rows[0]['source'],'synthetic')
    def test_vocabulary_change_rejected(self):
        self.record(); self.vocab['version']+=1
        with self.assertRaisesRegex(ValueError,'Vocabulary'): read_dataset(self.path,self.vocab)
    def test_participant_mismatch(self):
        with self.assertRaisesRegex(ValueError,'participant'): Recorder(self.path,self.vocab,self.cal,'p02','visit1','trial1')
    def test_no_mixed_sources(self):
        self.record(); cal=replace(self.cal,source='hardware')
        with self.assertRaisesRegex(ValueError,'mix'): self.record(cal)
    def test_synthetic_training_requires_opt_in(self):
        self.record()
        with self.assertRaisesRegex(ValueError,'Synthetic'): train(self.path,ROOT/'vocabulary.json',Path(self.tmp.name)/'m.joblib')
    def test_partition_groups_disjoint(self):
        groups=np.array([f'p{i}' for i in range(6) for _ in range(20)])
        y=np.array(['A','B']*60); ti,vi,si=split_groups(y,groups)
        sets=[set(groups[idx]) for idx in (ti,vi,si)]
        self.assertFalse(sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2])


class SerialTests(unittest.TestCase):
    def test_actual_reader_loopback_and_corruption(self):
        import serial
        from transport import SerialTransport
        loop=serial.serial_for_url('loop://',timeout=.15)
        with patch('transport.serial.Serial',return_value=loop): transport=SerialTransport('loop://')
        try:
            p=Simulator().packet(); loop.write(p.encode().encode())
            kind,value=transport.queue.get(timeout=2)
            self.assertEqual(kind,'packet'); self.assertEqual(value.seq,p.seq)
            loop.write(b'G1,garbage\n'); kind,value=transport.queue.get(timeout=2)
            self.assertEqual(kind,'fault')
        finally: transport.close()


if __name__=='__main__': unittest.main()
