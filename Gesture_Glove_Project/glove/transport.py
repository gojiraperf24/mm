"""Bounded serial input queue and explicit disconnect reporting."""
import queue
import threading
import serial
from serial.tools import list_ports
from core import Packet


def ports(): return [p.device for p in list_ports.comports()]


class SerialTransport:
    def __init__(self,port,baud=115200):
        self.queue=queue.Queue(maxsize=256)
        self.stop=threading.Event()
        self.serial=serial.Serial(port,baud,timeout=.15,write_timeout=.3)
        self.dropped=0
        self.thread=threading.Thread(target=self._read,daemon=True); self.thread.start()

    def _put(self,kind,value):
        try: self.queue.put_nowait((kind,value))
        except queue.Full:
            self.dropped+=1
            try: self.queue.get_nowait()
            except queue.Empty: pass
            try: self.queue.put_nowait((kind,value))
            except queue.Full: pass

    def _read(self):
        pending=b''
        try:
            while not self.stop.is_set():
                chunk=self.serial.read_until(b'\n',1001)
                if not chunk: continue
                pending+=chunk
                if len(pending)>1000:
                    pending=b''; self._put('fault','Oversized serial packet'); continue
                if not pending.endswith(b'\n'): continue
                line,pending=pending,b''
                if line.startswith(b'#'):
                    self._put('info',line.decode('ascii',errors='replace').strip()); continue
                try: self._put('packet',Packet.parse(line))
                except (ValueError,UnicodeError) as exc: self._put('fault',str(exc))
        except (serial.SerialException,OSError) as exc:
            self._put('disconnect',str(exc))

    def play(self,track):
        if not 1 <= track <= 199: raise ValueError('Invalid DFPlayer track')
        self.serial.write(f'PLAY {track}\n'.encode('ascii'))

    def close(self):
        self.stop.set()
        self.thread.join(timeout=.5)
        self.serial.close()
