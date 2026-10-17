"""Glove Studio: local native Windows collection, training and speech console."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
if sys.platform=='win32':
    # Keep Tk and app-only capture coordinates consistent under Windows scaling.
    import ctypes
    try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError,OSError): pass
from core import Calibration, EventGate, StreamGuard, atomic_json, load_vocabulary
from dataset import Recorder
from simulator import Simulator, DemoClassifier
from speech import Speech

BASE = Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent
ASSETS = Path(getattr(sys,'_MEIPASS',BASE))


class Studio:
    def __init__(self,root,data_dir=None,schedule=True):
        self.root=root
        self.data_dir=Path(data_dir) if data_dir else BASE/'user_data'
        self.data_dir.mkdir(parents=True,exist_ok=True)
        self.vocab_path=self.data_dir/'vocabulary.json'
        if not self.vocab_path.exists():
            original=BASE/'vocabulary.json'
            if not original.exists(): original=ASSETS/'vocabulary.json'
            atomic_json(self.vocab_path,load_vocabulary(original))
        self.vocabulary=load_vocabulary(self.vocab_path)
        self.events=queue.Queue()
        self.speech=Speech(lambda text:self.events.put(('log',text)))
        self.transport=None; self.sim=None; self.cal=None; self.model=None
        self.guard=StreamGuard(); self.gate=EventGate()
        self.last_packet=None; self.last_features=None; self.last_received=None
        self.recorder=None; self.record_started=None; self.record_deadline=None; self.record_next=0
        self.cal_capture=None; self.cal_open=[]; self.cal_closed=[]; self.training_busy=False
        self.source=None; self.trial_number=1; self.session_events=[]
        self.event_file=(self.data_dir/'events.csv').open('a',newline='',encoding='utf-8')
        self.event_writer=csv.writer(self.event_file)
        if self.event_file.tell()==0: self.event_writer.writerow(['utc','source','candidate','score','stable','event','language','phrase'])
        self._build()
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.log('Ready. Start simulator to explore, or connect your ESP32 to collect real data.')
        if schedule: self.root.after(40,self.tick)

    def _build(self):
        r=self.root; r.title('Glove Studio | Group 39'); r.geometry('1130x810'); r.minsize(1000,740)
        style=ttk.Style(r); style.theme_use('clam')
        style.configure('.',font=('Segoe UI',10),background='#f3f6fa',foreground='#1c3044')
        style.configure('TNotebook.Tab',padding=(17,9))
        style.configure('Title.TLabel',font=('Segoe UI',23,'bold'))
        style.configure('Result.TLabel',font=('Segoe UI',28,'bold'),foreground='#12636b')
        container=ttk.Frame(r); container.pack(fill='both',expand=True)
        canvas=tk.Canvas(container,background='#f3f6fa',highlightthickness=0)
        scrollbar=ttk.Scrollbar(container,orient='vertical',command=canvas.yview)
        scrollbar.pack(side='right',fill='y'); canvas.pack(side='left',fill='both',expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        outer=ttk.Frame(canvas,padding=20)
        content=canvas.create_window((0,0),window=outer,anchor='nw')
        outer.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(content,width=e.width))
        def wheel(event):
            if not isinstance(event.widget,tk.Text): canvas.yview_scroll(-int(event.delta/120),'units')
        r.bind_all('<MouseWheel>',wheel)
        ttk.Label(outer,text='Glove Studio',style='Title.TLabel').pack(anchor='w')
        ttk.Label(outer,text='Gesture to speech prototype  •  ID1050A  •  IIT Palakkad  •  Group 39').pack(anchor='w',pady=(0,12))
        link=ttk.LabelFrame(outer,text='1  Sensor connection',padding=10); link.pack(fill='x')
        self.mode=tk.StringVar(value='Disconnected'); self.port=tk.StringVar(); self.baud=tk.StringVar(value='115200')
        self.hands=tk.IntVar(value=1)
        self.port_box=ttk.Combobox(link,textvariable=self.port,width=11); self.port_box.grid(row=0,column=0,padx=4)
        ttk.Button(link,text='Refresh ports',command=self.refresh_ports).grid(row=0,column=1,padx=4)
        ttk.Combobox(link,textvariable=self.baud,values=['115200','9600'],width=8,state='readonly').grid(row=0,column=2,padx=4)
        ttk.Button(link,text='Connect glove',command=self.connect).grid(row=0,column=3,padx=4)
        ttk.Button(link,text='Start simulator',command=self.start_sim).grid(row=0,column=4,padx=4)
        ttk.Button(link,text='Disconnect',command=self.disconnect).grid(row=0,column=5,padx=4)
        ttk.Label(link,text='Hands').grid(row=0,column=6,padx=(15,3))
        ttk.Combobox(link,textvariable=self.hands,values=[1,2],width=3,state='readonly').grid(row=0,column=7)
        ttk.Label(link,textvariable=self.mode,foreground='#12636b').grid(row=1,column=0,columnspan=8,sticky='w',pady=(8,0))
        self.tabs=ttk.Notebook(outer); self.tabs.pack(fill='both',expand=True,pady=12)
        live=ttk.Frame(self.tabs,padding=16); collect=ttk.Frame(self.tabs,padding=16)
        learn=ttk.Frame(self.tabs,padding=16); words=ttk.Frame(self.tabs,padding=16)
        self.tabs.add(live,text='Live recognition'); self.tabs.add(collect,text='Calibrate and record')
        self.tabs.add(learn,text='Train and evaluate'); self.tabs.add(words,text='Vocabulary')
        self.result=tk.StringVar(value='DISCONNECTED'); self.detail=tk.StringVar(value='Connect a glove or start the simulator')
        ttk.Label(live,textvariable=self.result,style='Result.TLabel').pack(anchor='w')
        ttk.Label(live,textvariable=self.detail).pack(anchor='w',pady=8)
        self.sim_label=tk.StringVar(value='REST')
        simulation=ttk.Frame(live); simulation.pack(fill='x',pady=6)
        ttk.Label(simulation,text='Simulator pose').pack(side='left')
        ttk.Combobox(simulation,textvariable=self.sim_label,values=list(self.vocabulary['labels']),state='readonly',width=22).pack(side='left',padx=8)
        ttk.Label(simulation,text='Synthetic readings demonstrate software only').pack(side='left')
        gauge=ttk.LabelFrame(live,text='Normalized finger bend   0 = open   1 = closed',padding=8); gauge.pack(fill='x',pady=10)
        self.bars=[]
        for h in range(2):
            for i,name in enumerate(('Thumb','Index','Middle','Ring','Little')):
                row=h*2
                ttk.Label(gauge,text=f'{"Right / first" if h==0 else "Left / second"} {name}').grid(row=row,column=i,padx=8,sticky='w')
                b=ttk.Progressbar(gauge,length=155,maximum=1); b.grid(row=row+1,column=i,padx=8,pady=(3,8)); self.bars.append(b)
        controls=ttk.Frame(live); controls.pack(fill='x',pady=8)
        self.language=tk.StringVar(value='en'); self.auto_speech=tk.BooleanVar(value=False); self.dfplayer=tk.BooleanVar(value=False)
        ttk.Label(controls,text='Speech language').pack(side='left')
        ttk.Combobox(controls,textvariable=self.language,values=['en','hi'],width=4,state='readonly').pack(side='left',padx=8)
        ttk.Checkbutton(controls,text='Auto speech',variable=self.auto_speech).pack(side='left',padx=10)
        ttk.Checkbutton(controls,text='DFPlayer on glove',variable=self.dfplayer).pack(side='left',padx=10)
        ttk.Button(controls,text='Check voices',command=lambda:self.speech.send(action='voices')).pack(side='left')
        ttk.Label(live,text='Recognized phrase history   •   Hold a pose to add it; return to REST to repeat it').pack(anchor='w',pady=(10,5))
        self.sentence=tk.Text(live,height=3,font=('Segoe UI',13),wrap='word',relief='flat',background='white'); self.sentence.pack(fill='x')
        actions=ttk.Frame(live); actions.pack(fill='x',pady=8)
        ttk.Button(actions,text='Speak phrase history',command=self.speak_sentence).pack(side='left',padx=(0,8))
        ttk.Button(actions,text='Clear history',command=lambda:self.sentence.delete('1.0','end')).pack(side='left')
        ttk.Label(live,text='Word mappings are team-defined demo gestures. Verify a vocabulary with a signer before making sign-language claims.',wraplength=970).pack(anchor='w',pady=5)
        form=ttk.Frame(collect); form.pack(fill='x')
        self.participant=tk.StringVar(value='p01'); self.session=tk.StringVar(value=datetime.now().strftime('%Y%m%d')+'-visit1')
        self.label=tk.StringVar(value='REST'); self.burst=tk.IntVar(value=40)
        for i,(title,var) in enumerate([('Participant pseudonym',self.participant),('Recording visit / session',self.session)]):
            ttk.Label(form,text=title).grid(row=0,column=i,sticky='w',padx=(0,20))
            ttk.Entry(form,textvariable=var,width=30).grid(row=1,column=i,sticky='w',padx=(0,20),pady=5)
        ttk.Label(collect,text='2  Calibrate each person after fitting the glove',font=('Segoe UI',14,'bold')).pack(anchor='w',pady=(18,8))
        ttk.Label(collect,text='Open: fingers straight. Closed: comfortable fist. Hold the wrist still. Each capture waits 3 seconds and samples for 2.4 seconds.',wraplength=960).pack(anchor='w')
        calbuttons=ttk.Frame(collect); calbuttons.pack(fill='x',pady=10)
        ttk.Button(calbuttons,text='Capture open hand',command=lambda:self.begin_cal('open')).pack(side='left',padx=(0,8))
        ttk.Button(calbuttons,text='Capture closed hand',command=lambda:self.begin_cal('closed')).pack(side='left',padx=8)
        ttk.Button(calbuttons,text='Save calibration',command=self.save_cal).pack(side='left',padx=8)
        ttk.Button(calbuttons,text='Load calibration',command=self.load_cal).pack(side='left',padx=8)
        self.cal_status=tk.StringVar(value='No real calibration loaded. Simulator uses its own synthetic profile.')
        ttk.Label(collect,textvariable=self.cal_status,wraplength=950).pack(anchor='w',pady=5)
        ttk.Label(collect,text='3  Record labeled trials',font=('Segoe UI',14,'bold')).pack(anchor='w',pady=(18,8))
        rows=ttk.Frame(collect); rows.pack(fill='x')
        self.label_box=ttk.Combobox(rows,textvariable=self.label,values=list(self.vocabulary['labels']),width=24,state='readonly'); self.label_box.pack(side='left')
        ttk.Label(rows,text='Samples per trial').pack(side='left',padx=(15,8))
        ttk.Spinbox(rows,textvariable=self.burst,from_=15,to=200,width=5).pack(side='left')
        ttk.Button(rows,text='Record trial',command=self.begin_record).pack(side='left',padx=10)
        ttk.Button(rows,text='Stop recording',command=self.stop_record).pack(side='left')
        self.record_status=tk.StringVar(value='No recording active')
        ttk.Label(collect,textvariable=self.record_status,wraplength=970).pack(anchor='w',pady=10)
        ttk.Label(collect,text='Use one session ID for the entire visit. Lower and reform the hand between trials. Record every gesture plus varied REST for every participant. Aim for six people and at least two visits per person.',wraplength=940).pack(anchor='w',pady=8)
        ttk.Label(collect,text='The collector stores normalized sensor features and pseudonyms, without camera images or audio.',wraplength=940).pack(anchor='w')
        ttk.Label(learn,text='4  Train from your recorded glove data',font=('Segoe UI',16,'bold')).pack(anchor='w')
        self.dataset_path=tk.StringVar(value=str(self.data_dir/'samples.csv'))
        self.model_path=tk.StringVar(value=str(self.data_dir/'glove_model.joblib'))
        for title,var,save in [('Dataset CSV',self.dataset_path,False),('Model output',self.model_path,True)]:
            ttk.Label(learn,text=title).pack(anchor='w',pady=(12,4))
            row=ttk.Frame(learn); row.pack(fill='x')
            ttk.Entry(row,textvariable=var,width=87).pack(side='left',fill='x',expand=True)
            ttk.Button(row,text='Browse',command=lambda v=var,s=save:self.browse(v,s)).pack(side='left',padx=8)
        self.group_by=tk.StringVar(value='participant'); self.allow_synthetic=tk.BooleanVar(value=False)
        opts=ttk.Frame(learn); opts.pack(fill='x',pady=18)
        ttk.Label(opts,text='Hold out entire').pack(side='left')
        ttk.Combobox(opts,textvariable=self.group_by,values=['participant','session'],width=15,state='readonly').pack(side='left',padx=8)
        ttk.Checkbutton(opts,text='Allow synthetic software test data',variable=self.allow_synthetic).pack(side='left',padx=12)
        self.train_button=ttk.Button(opts,text='Train model',command=self.begin_train); self.train_button.pack(side='left',padx=8)
        ttk.Button(opts,text='Load trusted model',command=self.load_model).pack(side='left')
        self.metrics_text=tk.Text(learn,height=12,font=('Consolas',11),wrap='word',relief='flat',background='white'); self.metrics_text.pack(fill='both',expand=True)
        self.metrics_text.insert('end','Three disjoint partitions:\n  Training learns the gesture patterns.\n  Validation chooses a confidence cutoff.\n  Test measures performance on untouched groups.\n\nA minimum of 30 rows per label across 3 groups is enforced. More users, visits and varied trials are recommended.\n\nOnly load joblib models you trained or trust; the format can execute code.\nSynthetic data and models are never accepted on the real glove.\n')
        ttk.Label(words,text='5  Define your team vocabulary',font=('Segoe UI',16,'bold')).pack(anchor='w')
        ttk.Label(words,text='Edit only while disconnected. A changed pose or phrase creates a new vocabulary fingerprint and requires a new dataset and model.',wraplength=950).pack(anchor='w',pady=10)
        self.word_label=tk.StringVar(value='OPEN_PALM')
        self.word_box=ttk.Combobox(words,textvariable=self.word_label,values=list(self.vocabulary['labels']),state='readonly',width=28); self.word_box.pack(anchor='w')
        self.word_box.bind('<<ComboboxSelected>>',lambda e:self.show_word())
        self.word_vars={k:tk.StringVar() for k in ('pose','en','hi','track')}
        for k,title in [('pose','Physical pose definition'),('en','English phrase'),('hi','Hindi phrase'),('track','DFPlayer English track number 1 to 99')]:
            ttk.Label(words,text=title).pack(anchor='w',pady=(10,3))
            ttk.Entry(words,textvariable=self.word_vars[k],width=105).pack(fill='x')
        ttk.Button(words,text='Save word mapping',command=self.save_word).pack(anchor='w',pady=15)
        self.show_word()
        logbox=ttk.LabelFrame(outer,text='Activity and explanations',padding=6); logbox.pack(fill='x')
        self.log_text=tk.Text(logbox,height=5,font=('Consolas',9),wrap='word',relief='flat',background='#e9eef4'); self.log_text.pack(fill='x')
        self.refresh_ports()
        r.bind('<Escape>',lambda e:self.stop_record())
        r.bind('<Control-q>',lambda e:self.close())

    def log(self,text):
        line=datetime.now().strftime('%H:%M:%S')+'  '+str(text)
        self.log_text.insert('end',line+'\n'); self.log_text.see('end')
        with (self.data_dir/'activity.log').open('a',encoding='utf-8') as f: f.write(line+'\n')

    def refresh_ports(self):
        try:
            from transport import ports
            available=ports(); self.port_box['values']=available
            if available and not self.port.get(): self.port.set(available[0])
        except ImportError: self.port_box['values']=[]

    def connect(self):
        try:
            if not self.port.get().strip(): raise ValueError('Select a serial COM port')
            self.disconnect()
            from transport import SerialTransport
            self.transport=SerialTransport(self.port.get().strip(),int(self.baud.get()))
            self.source='hardware'; self.mode.set('REAL GLOVE • Waiting for valid sensor packets')
            self.log('Connected. ESP32 may reset on serial open; allow two seconds for startup.')
        except Exception as exc: self.error(exc)

    def start_sim(self):
        self.disconnect()
        self.sim=Simulator(self.hands.get()); self.source='synthetic'
        self.cal=self.sim.calibration(self.participant.get().strip()); self.model=DemoClassifier()
        self.mode.set('SIMULATOR • Synthetic readings and template demo • No real accuracy claim')
        self.cal_status.set('Synthetic simulator calibration; never used for physical hardware')
        self.dataset_path.set(str(self.data_dir/'synthetic_samples.csv'))
        self.log('Simulator started. Choose a pose in Live recognition to exercise filtering and speech-event logic.')

    def disconnect(self):
        self.stop_record()
        if self.transport: self.transport.close(); self.transport=None
        self.sim=None; self.cal=None; self.model=None; self.source=None
        self.last_received=None; self.last_packet=None; self.last_features=None
        self.cal_capture=None; self.cal_open=[]; self.cal_closed=[]
        self.guard=StreamGuard(); self.gate=EventGate()
        self.result.set('DISCONNECTED'); self.mode.set('Disconnected'); self.detail.set('Connect a glove or start simulator')
        self.cal_status.set('Calibration not loaded')
        for b in self.bars: b['value']=0
        self.dataset_path.set(str(self.data_dir/'samples.csv'))

    def error(self,exc):
        self.log(str(exc)); messagebox.showerror('Glove Studio',str(exc),parent=self.root)

    def begin_cal(self,kind):
        try:
            if not self.last_packet or not self.source: raise ValueError('Wait for a valid sensor packet first')
            if self.recorder: raise ValueError('Stop recording before calibration')
            self.cal_capture=(kind,time.monotonic()+3,[])
            self.cal=None; self.model=DemoClassifier() if self.sim else None
            self.gate.reset(); self.last_features=None
            self.cal_status.set(f'{kind.upper()}: prepare for 3 seconds, then hold still for 2.4 seconds')
            self.log(f'Calibration {kind}: median endpoints resist isolated sensor spikes; gyro bias uses the still hand.')
        except Exception as exc: self.error(exc)

    def save_cal(self):
        try:
            self.cal=Calibration.from_samples(self.cal_open,self.cal_closed,self.participant.get().strip(),self.source)
            folder=self.data_dir/'calibrations'
            path=folder/(self.cal.id[:16]+'.json'); self.cal.save(path)
            self.cal_status.set(f'Calibrated {self.cal.hands} hand(s) for {self.cal.participant}. Saved {path.name}')
            self.log('Calibration saved. Each finger now has its own open/closed range; decreasing voltages are supported.')
        except Exception as exc: self.error(exc)

    def load_cal(self):
        try:
            if not self.source: raise ValueError('Connect first, then load a matching calibration')
            name=filedialog.askopenfilename(initialdir=self.data_dir/'calibrations',filetypes=[('Calibration JSON','*.json')])
            if not name: return
            cal=Calibration.load(name)
            if cal.source!=self.source or cal.participant!=self.participant.get().strip(): raise ValueError('Calibration source or participant differs')
            if self.last_packet and (cal.hands,cal.adc_max)!=(self.last_packet.hands,self.last_packet.adc_max): raise ValueError('Calibration hardware layout differs')
            self.cal=cal; self.gate.reset()
            self.cal_status.set(f'Loaded calibration for {cal.participant}; confirm current glove fit before use')
        except Exception as exc: self.error(exc)

    def begin_record(self):
        try:
            if self.recorder: raise ValueError('A trial is already recording')
            if self.cal_capture: raise ValueError('Complete calibration capture first')
            if not self.cal or self.last_features is None or self.last_received is None or time.monotonic()-self.last_received>.5:
                raise ValueError('Calibrate and hold a valid still pose before recording')
            target=int(self.burst.get())
            if not 15<=target<=200: raise ValueError('Use 15 to 200 samples per trial')
            self.record_target=target; self.record_label=self.label.get()
            self.recorder=Recorder(self.dataset_path.get(),self.vocabulary,self.cal,self.participant.get().strip(),self.session.get().strip(),
                                   datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+f'-{self.trial_number}')
            self.trial_number+=1
            self.record_started=time.monotonic()+3; self.record_deadline=self.record_started+target*.2+15
            self.record_next=self.record_started
            self.record_status.set(f'Prepare {self.record_label}: recording begins in 3 seconds')
            self.log(f'Trial {self.record_label}: recording at most 5 usable readings per second. Keep the label fixed while recording.')
        except Exception as exc: self.error(exc)

    def stop_record(self):
        if self.recorder:
            count=self.recorder.count; self.recorder.close(); self.recorder=None
            self.record_status.set(f'Trial saved: {count} samples. Lower the hand and reform it before another trial.')
            self.log(f'Recording stopped; {count} rows flushed to disk.')

    def browse(self,var,save):
        name=(filedialog.asksaveasfilename if save else filedialog.askopenfilename)(initialdir=self.data_dir)
        if name: var.set(name)

    def begin_train(self):
        if self.training_busy: return
        if self.recorder: self.error(ValueError('Stop recording before training')); return
        dataset=self.dataset_path.get(); vocab=str(self.vocab_path); output=self.model_path.get()
        group=self.group_by.get(); synthetic=self.allow_synthetic.get()
        self.training_busy=True; self.train_button['state']='disabled'
        self.log('Training checks labels and provenance, then separates complete groups before fitting the model.')
        def job():
            try:
                from training import train
                metrics=train(dataset,vocab,output,group,synthetic,lambda s:self.events.put(('log',s)))
                self.events.put(('trained',metrics))
            except Exception as exc: self.events.put(('train_error',str(exc)))
        threading.Thread(target=job,daemon=True).start()

    def load_model(self):
        try:
            if self.recorder: raise ValueError('Stop recording before loading a model')
            if not self.cal: raise ValueError('Calibrate the connected glove first')
            from training import Classifier
            self.model=Classifier(self.model_path.get(),self.vocabulary,self.cal.hands,self.source)
            self.gate.reset(); self.log(f'Model loaded. Candidate confidence cutoff {self.model.threshold:.3f}. Hold each pose for 0.45 seconds.')
        except Exception as exc: self.error(exc)

    def show_word(self):
        item=self.vocabulary['labels'][self.word_label.get()]
        for k,v in self.word_vars.items(): v.set(str(item[k]))

    def save_word(self):
        try:
            if self.source or self.training_busy: raise ValueError('Disconnect and finish training before editing vocabulary')
            candidate=json.loads(json.dumps(self.vocabulary)); item=candidate['labels'][self.word_label.get()]
            item.update({k:v.get().strip() for k,v in self.word_vars.items() if k!='track'})
            item['track']=int(self.word_vars['track'].get()); candidate['version']+=1
            temp=self.vocab_path.with_suffix('.validate.json'); atomic_json(temp,candidate)
            try: load_vocabulary(temp)
            finally: temp.unlink(missing_ok=True)
            atomic_json(self.vocab_path,candidate); self.vocabulary=candidate
            self.log('Vocabulary saved. Use a new dataset path and retrain; older recordings have a different fingerprint.')
        except Exception as exc: self.error(exc)

    def speak_sentence(self):
        text=self.sentence.get('1.0','end').strip()
        if text: self.speech.send(text,self.language.get())

    def fault(self,text,disconnected=False):
        self.last_features=None
        state='DISCONNECTED' if disconnected else 'MOVING' if text.startswith('MOVING') else 'FAULT'
        self.gate.update(state,0,1); self.result.set(state); self.detail.set(text)
        for b in self.bars: b['value']=0
        if disconnected: self.stop_record()

    def process(self,packet,now=None):
        now=time.monotonic() if now is None else now
        self.last_received=now; self.last_packet=packet
        try: self.guard.accept(packet)
        except ValueError as exc: self.fault(str(exc)); return
        if self.cal_capture:
            kind,start,samples=self.cal_capture
            if start<=now<start+2.4:
                samples.append(packet); self.cal_status.set(f'Capturing {kind}: {len(samples)} readings')
            elif now>=start+2.4:
                if kind=='open': self.cal_open=samples
                else: self.cal_closed=samples
                self.cal_capture=None; self.cal_status.set(f'{kind.upper()} captured: {len(samples)} readings. Capture the other pose, then save calibration.')
        if not self.cal:
            self.last_features=None; self.result.set('CALIBRATE'); self.detail.set('Valid sensor input. Capture open and closed hand, then save calibration.'); return
        try: features=self.cal.features(packet)
        except ValueError as exc: self.fault(str(exc)); return
        self.last_features=features
        for h in range(2):
            for i in range(5): self.bars[h*5+i]['value']=features[h*11+i] if h<packet.hands else 0
        if self.recorder and now>=self.record_next:
            try:
                self.recorder.write(self.record_label,features); self.record_next=now+.2
                self.record_status.set(f'{self.record_label}: {self.recorder.count}/{self.record_target} samples')
                if self.recorder.count>=self.record_target: self.stop_record()
            except Exception as exc: self.stop_record(); self.fault(str(exc)); self.log(str(exc))
        if not self.model:
            self.result.set('READY TO RECORD'); self.detail.set('Calibration valid. Collect labeled trials, train, then load the real glove model.'); return
        candidate,score=self.model.predict(features)
        stable,event=self.gate.update(candidate,score,self.model.threshold,now)
        self.result.set(stable); self.detail.set(f'Candidate {candidate}   |   score {score:.3f}   |   cutoff {self.model.threshold:.3f}   |   {"SYNTHETIC" if self.source=="synthetic" else "REAL SENSOR INPUT"}')
        if event:
            language=self.language.get(); item=self.vocabulary['labels'][event]; phrase=item[language]
            if phrase: self.sentence.insert('end',phrase+'  '); self.sentence.see('end')
            self.session_events.append(event)
            self.event_writer.writerow([datetime.now(timezone.utc).isoformat(),self.source,candidate,f'{score:.5f}',stable,event,language,phrase]); self.event_file.flush()
            self.log(f'{event} -> {phrase}. Event debounced; a held gesture will not repeat automatically.')
            if self.auto_speech.get() and phrase:
                if self.dfplayer.get():
                    if not self.transport: self.log('DFPlayer needs a real connected glove; simulator event has no hardware output')
                    else:
                        try: self.transport.play(item['track']+(100 if language=='hi' else 0))
                        except Exception as exc: self.log('DFPlayer command failed: '+str(exc))
                else: self.speech.send(phrase,language)

    def tick(self):
        if self.sim:
            self.sim.label=self.sim_label.get(); self.process(self.sim.packet())
        if self.transport:
            # A stalled GUI must not debounce stale buffered packets into speech.
            if self.transport.queue.qsize()>8:
                while True:
                    try: self.transport.queue.get_nowait()
                    except queue.Empty: break
                self.fault('Input backlog discarded; wait for fresh sensor packets')
                self.guard=StreamGuard()
            else:
                for _ in range(8):
                    try: kind,value=self.transport.queue.get_nowait()
                    except queue.Empty: break
                    if kind=='packet': self.process(value)
                    elif kind=='info': self.log(value)
                    elif kind=='disconnect': self.fault(value,True); self.log('Serial connection lost: '+value)
                    else: self.fault(value)
        now=time.monotonic()
        if self.source and self.last_received is not None and now-self.last_received>.5:
            self.fault('No fresh sensor packet for 0.5 seconds',True)
        if self.recorder and now>self.record_deadline:
            self.stop_record(); self.log('Trial timed out waiting for usable still readings. Check posture, wiring and calibration.')
        if self.cal_capture and now>self.cal_capture[1]+4:
            self.cal_capture=None; self.cal_status.set('Capture failed: no fresh stream. Reconnect and repeat.')
        while True:
            try: kind,value=self.events.get_nowait()
            except queue.Empty: break
            if kind in ('trained','train_error'):
                self.training_busy=False; self.train_button['state']='normal'
                if kind=='train_error': self.error(ValueError(value))
                else:
                    summary={k:value[k] for k in ['claim','rows','group_by','threshold','validation_target_met','raw_accuracy','coverage','accepted_accuracy','overall_accuracy_with_rejection','partitions']}
                    self.metrics_text.delete('1.0','end'); self.metrics_text.insert('end',json.dumps(summary,indent=2,ensure_ascii=False))
                    self.log('Training complete. Inspect saved metrics and confusion CSV, then Load trusted model.')
            else: self.log(value)
        self.root.after(40,self.tick)

    def close(self):
        self.stop_record()
        if self.transport: self.transport.close()
        self.speech.close(); self.event_file.close(); self.root.destroy()


def smoke_test(output):
    root=tk.Tk(); root.withdraw(); app=Studio(root,Path(output)/'gui_data',schedule=False)
    app.start_sim()
    for label in ['OPEN_PALM','REST','FIST','REST','INDEX_UP']:
        app.sim.label=label
        for _ in range(30):
            p=app.sim.packet(); app.process(p,now=p.ms/1000)
    result=dict(events=app.session_events,final=app.result.get(),synthetic=True)
    assert result['events']==['OPEN_PALM','FIST','INDEX_UP'],result
    assert result['final']=='INDEX_UP',result
    atomic_json(Path(output)/'gui_smoke.json',result)
    app.close()
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo',action='store_true'); parser.add_argument('--data-dir')
    parser.add_argument('--smoke-test',metavar='OUTPUT_DIR')
    parser.add_argument('--full-check',metavar='OUTPUT_DIR')
    a=parser.parse_args()
    if a.full_check:
        from tools.demo_check import run
        from speech import render_offline
        out=Path(a.full_check)
        run(out/'integration')
        smoke_test(out/'gui')
        voices=[render_offline('Hello. Thank you.','en',out/'english.wav'),
                render_offline('नमस्ते। धन्यवाद।','hi',out/'hindi.wav')]
        atomic_json(out/'speech_render.json',voices)
    elif a.smoke_test: smoke_test(a.smoke_test)
    else:
        root=tk.Tk()
        try:
            studio=Studio(root,a.data_dir)
            if a.demo: studio.start_sim()
            root.mainloop()
        except Exception as exc:
            messagebox.showerror('Glove Studio startup',str(exc)); root.destroy(); raise
