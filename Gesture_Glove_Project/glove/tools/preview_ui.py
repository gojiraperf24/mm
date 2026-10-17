"""Capture only Glove Studio's own client rectangle for visual review."""
from pathlib import Path
import sys
import tkinter as tk
import time
from PIL import ImageGrab
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Studio

root=tk.Tk(); output=Path(__file__).resolve().parents[1]/'artifacts'/'ui_preview'
app=Studio(root,output/'preview_data',schedule=False); app.start_sim()
root.attributes('-topmost',True)
root.update()
now=time.monotonic(); app.sim.label='OPEN_PALM'; app.sim_label.set('OPEN_PALM')
for i in range(20): app.process(app.sim.packet(),now+i*.04)
for index,name in enumerate(('live','calibration','training','vocabulary')):
    app.tabs.select(index); root.update(); root.after(150); root.update()
    box=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())
    ImageGrab.grab(bbox=box).save(output/(name+'.png'))
app.close()
print('Saved four app-only UI snapshots')
