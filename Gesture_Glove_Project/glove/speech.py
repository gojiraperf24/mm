"""Windows offline TTS; JSON over stdin keeps text out of shell code."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tempfile
import wave


def espeak_path():
    base=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
    return base/'vendor'/'espeak-ng'/'espeak-ng.exe'


def render_offline(text,language,path):
    """Render a genuine offline waveform; also usable for silent verification."""
    if language not in ('en','hi'): raise ValueError('Supported speech languages are en and hi')
    exe=espeak_path()
    if not exe.exists(): raise RuntimeError('Portable offline speech engine missing from application folder')
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    args=[str(exe),'--path='+str(exe.parent),'-v','hi' if language=='hi' else 'en-us',
          '-s','155','-b','1','--stdin','-w',str(path)]
    result=subprocess.run(args,input=text+'\n',text=True,encoding='utf-8',capture_output=True,
                          timeout=30,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
    if result.returncode: raise RuntimeError('Offline speech failed: '+result.stderr.strip())
    with wave.open(str(path),'rb') as f:
        if f.getnframes()<100: raise RuntimeError('Offline speech returned an empty waveform')
        return dict(engine='eSpeak NG 1.52.0',language=language,path=str(path),
                    frames=f.getnframes(),sample_rate=f.getframerate(),duration_seconds=f.getnframes()/f.getframerate())


class Speech:
    def __init__(self,report):
        self.report=report
        self.queue=queue.Queue(maxsize=2)
        self.proc=None
        self.thread=threading.Thread(target=self._work,daemon=True); self.thread.start()

    def send(self,text='',language='en',action='speak'):
        try: self.queue.put_nowait(dict(text=text,language=language,action=action))
        except queue.Full: self.report('Speech busy; event skipped')

    def _work(self):
        while True:
            req=self.queue.get()
            if req is None: break
            try:
                if sys.platform!='win32': raise RuntimeError('Offline speech is currently implemented for Windows')
                if req['action']=='speak' and req['language']=='hi':
                    self._fallback(req)
                    continue
                if self.proc is None or self.proc.poll() is not None:
                    script=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'speech_worker.ps1'
                    shell=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
                    self.proc=subprocess.Popen([str(shell),'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script)],
                        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                        text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
                self.proc.stdin.write(json.dumps(req,ensure_ascii=False)+'\n'); self.proc.stdin.flush()
                line=self.proc.stdout.readline()
                if not line: raise RuntimeError('Windows speech service closed')
                result=json.loads(line)
                if not result.get('ok'):
                    if req['action']=='speak': self._fallback(req)
                    else: self.report(result.get('error','Voice enumeration failed'))
                elif 'voices' in result:
                    self.report('Installed Windows voices: '+', '.join(result['voices']))
                    self.report('Portable offline voice: eSpeak NG English and Hindi (compact synthetic speech)')
                else: self.report('Speech completed: '+result.get('spoken',''))
            except Exception as exc: self.report('Speech: '+str(exc))

    def _fallback(self,req):
        import winsound
        with tempfile.TemporaryDirectory(prefix='glove-speech-') as folder:
            path=Path(folder)/'phrase.wav'
            render_offline(req['text'],req['language'],path)
            winsound.PlaySound(str(path),winsound.SND_FILENAME)
        self.report('Offline speech completed ('+req['language']+'): '+req['text'])

    def close(self):
        try: self.queue.put_nowait(None)
        except queue.Full: pass
        if self.proc and self.proc.poll() is None: self.proc.terminate()
