"""Run the whole dataset -> fit -> reload -> event chain on synthetic data."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import EventGate, atomic_json, load_vocabulary
from dataset import Recorder
from simulator import Simulator, POSES
from training import train,Classifier


def run(output):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    vocab_path=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))/'vocabulary.json'
    vocab=load_vocabulary(vocab_path); data=output/'synthetic_samples.csv'
    if data.exists(): data.unlink()
    for i in range(6):
        sim=Simulator(seed=39+i); participant=f'synthetic_p{i+1:02}'
        cal=sim.calibration(participant)
        with_record=Recorder(data,vocab,cal,participant,'synthetic_visit1','trial1')
        try:
            for label in vocab['labels']:
                sim.label=label
                for _ in range(40): with_record.write(label,cal.features(sim.packet()))
        finally: with_record.close()
    model_path=output/'synthetic_model.joblib'
    metrics=train(data,vocab_path,model_path,allow_synthetic=True)
    predictor=Classifier(model_path,vocab,1,'synthetic'); sim=Simulator(seed=101); cal=sim.calibration()
    gate=EventGate(); events=[]
    for label in list(POSES):
        sim.label=label
        for _ in range(30):
            p=sim.packet(); name,score=predictor.predict(cal.features(p)); _,event=gate.update(name,score,predictor.threshold,p.ms/1000)
            if event: events.append(event)
    expected=[name for name in POSES if name!='REST']
    if events!=expected: raise AssertionError((events,expected))
    partitions=[set(v['groups']) for v in metrics['partitions'].values()]
    if any(partitions[i]&partitions[j] for i in range(3) for j in range(i+1,3)): raise AssertionError('Group overlap')
    result=dict(status='passed',source='synthetic',claim='Software integration verification only; no physical glove accuracy',
                sample_count=metrics['rows'],events=events,group_overlap=False)
    atomic_json(output/'integration_result.json',result)
    print(result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--output',default=str(Path(__file__).resolve().parents[1]/'artifacts'/'simulation'))
    run(p.parse_args().output)
