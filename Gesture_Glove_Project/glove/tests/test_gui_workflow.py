"""Native Tk controller tests: run on a desktop-capable Windows session."""
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Studio
from dataset import read_dataset


class GuiWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        try:
            self.root=tk.Tk(); self.root.withdraw()
        except tk.TclError as exc:
            self.tmp.cleanup(); self.skipTest('Desktop Tk unavailable in this execution sandbox: '+str(exc))
        self.app=Studio(self.root,self.tmp.name,schedule=False)
        self.errors=[]
        self.app.error=lambda exc:self.errors.append(str(exc))
        self.app.start_sim()

    def tearDown(self):
        if hasattr(self,'app'): self.app.close(); self.tmp.cleanup()

    def frame(self,now): self.app.process(self.app.sim.packet(),now)

    def test_real_record_button_writes_fixed_label_and_burst(self):
        now=time.monotonic(); self.frame(now)
        self.app.burst.set(15); self.app.label.set('REST'); self.app.begin_record()
        self.assertFalse(self.errors)
        start=self.app.record_started
        # Changing the visible dropdown must not relabel a trial in progress.
        self.app.label.set('FIST')
        for i in range(100): self.frame(start+i*.04)
        self.assertIsNone(self.app.recorder)
        rows=read_dataset(self.app.dataset_path.get(),self.app.vocabulary)
        self.assertEqual(len(rows),15)
        self.assertEqual({r['label'] for r in rows},{'REST'})

    def test_calibration_buttons_capture_and_save(self):
        now=time.monotonic(); self.frame(now)
        for kind,pose in [('open','OPEN_PALM'),('closed','FIST')]:
            self.app.sim.label=pose; self.app.begin_cal(kind)
            start=self.app.cal_capture[1]
            for i in range(62): self.frame(start+i*.04)
            self.assertIsNone(self.app.cal_capture)
        self.app.save_cal(); self.assertFalse(self.errors)
        self.assertEqual(self.app.cal.participant,'p01')
        self.assertEqual(self.app.cal.source,'synthetic')
        self.assertTrue(list((Path(self.tmp.name)/'calibrations').glob('*.json')))

    def test_fault_clears_display_and_features(self):
        self.app.sim.label='FIST'; now=time.monotonic()
        for i in range(20): self.frame(now+i*.04)
        self.assertEqual(self.app.result.get(),'FIST')
        self.app.fault('Cable unplugged',True)
        self.assertEqual(self.app.result.get(),'DISCONNECTED')
        self.assertIsNone(self.app.last_features)
        self.assertTrue(all(float(b['value'])==0 for b in self.app.bars))

    def test_disconnect_drops_synthetic_model_and_calibration(self):
        self.app.disconnect()
        self.assertIsNone(self.app.cal); self.assertIsNone(self.app.model)
        self.assertEqual(self.app.result.get(),'DISCONNECTED')


if __name__=='__main__': unittest.main()
