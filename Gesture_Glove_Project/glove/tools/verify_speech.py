"""Silently export every starter phrase; validate PCM frames, not audibility."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import atomic_json, load_vocabulary
from speech import render_offline

root=Path(__file__).resolve().parents[1]
out=root/'artifacts'/'speech'
vocabulary=load_vocabulary(root/'vocabulary.json')
results=[]
for label,item in vocabulary['labels'].items():
    if label=='REST': continue
    for lang in ('en','hi'):
        track=item['track']+(100 if lang=='hi' else 0)
        result=render_offline(item[lang],lang,out/lang/f'{track:04}.wav')
        result['label']=label; result['phrase']=item[lang]; results.append(result)
atomic_json(out/'waveform_checks.json',results)
print(f'Validated {len(results)} nonempty offline speech waveforms; listening/playback not verified.')
