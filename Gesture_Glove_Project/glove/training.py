"""Participant/session-separated training. No live hardware claims from simulation."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import csv
import joblib
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit
from core import FEATURE_VERSION, atomic_json, fingerprint, load_vocabulary
from dataset import read_dataset, columns, META


def split_groups(y,groups,seed=39):
    required=set(y)
    indices=np.arange(len(y))
    for a,b in GroupShuffleSplit(n_splits=250,test_size=.2,random_state=seed).split(indices,y,groups):
        if set(y[a]) != required or set(y[b]) != required: continue
        for ta,va in GroupShuffleSplit(n_splits=80,test_size=.25,random_state=seed+1).split(a,y[a],groups[a]):
            train,valid=a[ta],a[va]
            if set(y[train]) == required and set(y[valid]) == required:
                return train,valid,b
    raise ValueError("Cannot form three complete disjoint partitions. Record all labels for more participants/sessions.")


def train(dataset_path, vocabulary_path, output_path, group_by="participant", allow_synthetic=False, log=print):
    vocabulary=load_vocabulary(vocabulary_path)
    rows=read_dataset(dataset_path,vocabulary)
    synthetic=rows[0]['source']=="synthetic"
    if synthetic and not allow_synthetic: raise ValueError("Synthetic samples are for software checks only; use --allow-synthetic explicitly")
    hands=int(rows[0]['hands'])
    y=np.array([r['label'] for r in rows])
    X=np.array([[float(r[k]) for k in columns(hands)[len(META):]] for r in rows])
    if group_by not in {"participant","session"}: raise ValueError("group_by must be participant or session")
    groups=np.array([r['participant'] if group_by=="participant" else r['participant']+"/"+r['session'] for r in rows])
    counts=Counter(y)
    if set(y)!=set(vocabulary['labels']): raise ValueError("Every configured gesture and REST must be recorded")
    for label in vocabulary['labels']:
        if counts[label]<30 or len(set(groups[y==label]))<3:
            raise ValueError(f"{label}: need >=30 samples across >=3 independent {group_by} groups")
    # Identical feature vectors crossing groups are a likely replay/leakage mistake.
    seen={}
    for r,g in zip(rows,groups):
        key=tuple(r[k] for k in columns(hands)[len(META):])
        if key in seen and seen[key]!=g: raise ValueError("Exact duplicate feature vectors cross evaluation groups")
        seen[key]=g
    ti,vi,si=split_groups(y,groups)
    log(f"Validated {len(rows)} samples, {hands} hand(s), {len(set(groups))} groups. Train {len(ti)}, validation {len(vi)}, test {len(si)}.")
    model=RandomForestClassifier(n_estimators=200,min_samples_leaf=2,class_weight="balanced",random_state=39,n_jobs=2)
    model.fit(X[ti],y[ti])
    vp=model.predict_proba(X[vi]); vc=vp.max(axis=1); vl=model.classes_[vp.argmax(axis=1)]
    sweep=[]
    for threshold in np.arange(.5,.951,.025):
        keep=vc>=threshold
        pred=np.where(keep,vl,"UNKNOWN")
        sweep.append(dict(threshold=round(float(threshold),3),coverage=float(keep.mean()),
                          accepted_accuracy=float((vl[keep]==y[vi][keep]).mean()) if keep.any() else None,
                          macro_f1=float(f1_score(y[vi],pred,labels=list(model.classes_),average="macro",zero_division=0))))
    eligible=[r for r in sweep if r['coverage']>=.5 and (r['accepted_accuracy'] or 0)>=.95]
    selected=max(eligible,key=lambda r:(r['coverage'],r['threshold'])) if eligible else max(sweep,key=lambda r:(r['macro_f1'],r['coverage'],r['threshold']))
    probs=model.predict_proba(X[si]); conf=probs.max(axis=1); pred=model.classes_[probs.argmax(axis=1)]
    accepted=conf>=selected['threshold']; gated=np.where(accepted,pred,"UNKNOWN")
    path=Path(output_path); path.parent.mkdir(parents=True,exist_ok=True)
    artifact=dict(version=1,feature_version=FEATURE_VERSION,hands=hands,vocabulary_id=fingerprint(vocabulary),
                  sklearn_version=sklearn.__version__,threshold=selected['threshold'],synthetic=synthetic,model=model)
    metrics=dict(created_utc=datetime.now(timezone.utc).isoformat(),source="synthetic" if synthetic else "hardware",
                 claim="Software smoke test only" if synthetic else f"Held-out {group_by} evaluation on recorded prototype data",
                 dataset_sha256=hashlib.sha256(Path(dataset_path).read_bytes()).hexdigest(),
                 feature_version=FEATURE_VERSION,vocabulary_id=fingerprint(vocabulary),hands=hands,rows=len(rows),
                 class_counts=dict(counts),group_by=group_by,threshold=selected['threshold'],validation_target_met=bool(eligible),
                 threshold_sweep=sweep,raw_accuracy=float((pred==y[si]).mean()),coverage=float(accepted.mean()),
                 accepted_accuracy=float((pred[accepted]==y[si][accepted]).mean()) if accepted.any() else None,
                 overall_accuracy_with_rejection=float((gated==y[si]).mean()),
                 raw_classification_report=classification_report(y[si],pred,output_dict=True,zero_division=0),
                 partitions={k:dict(groups=sorted(set(groups[idx])),rows=len(idx),class_counts=dict(Counter(y[idx])))
                             for k,idx in [('train',ti),('validation',vi),('test',si)]})
    tmp=path.with_suffix('.tmp'); joblib.dump(artifact,tmp); tmp.replace(path)
    atomic_json(path.with_suffix('.metrics.json'),metrics)
    with path.with_suffix('.confusion.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f); writer.writerow(['actual/predicted']+list(model.classes_)+['UNKNOWN'])
        matrix=confusion_matrix(y[si],gated,labels=list(model.classes_)+['UNKNOWN'])
        for label,row in zip(model.classes_,matrix): writer.writerow([label]+row.tolist())
    with path.with_suffix('.partitions.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f); writer.writerow(['csv_row','partition','participant','session','label'])
        for name,idx in [('train',ti),('validation',vi),('test',si)]:
            for i in idx: writer.writerow([int(i)+2,name,rows[i]['participant'],rows[i]['session'],y[i]])
    log(f"Saved model. {'SYNTHETIC ONLY. ' if synthetic else ''}Test accuracy {metrics['raw_accuracy']:.1%}; coverage {metrics['coverage']:.1%}; threshold {selected['threshold']:.3f}.")
    if not eligible: log("Validation target of 95% accepted accuracy at 50% coverage was not met. Inspect the confusion matrix and gather more data.")
    return metrics


class Classifier:
    def __init__(self,path,vocabulary,hands,source):
        # joblib is executable serialization: load only trusted locally trained files.
        a=joblib.load(path)
        if a.get('version')!=1 or a.get('feature_version')!=FEATURE_VERSION: raise ValueError("Incompatible model schema")
        if a.get('sklearn_version')!=sklearn.__version__: raise ValueError("Model scikit-learn version differs; retrain")
        if a.get('vocabulary_id')!=fingerprint(vocabulary) or a.get('hands')!=hands: raise ValueError("Model vocabulary/hardware differs")
        if a.get('synthetic') != (source=='synthetic'): raise ValueError("Synthetic models cannot run on real glove data")
        self.model=a['model']; self.threshold=float(a['threshold']); self.synthetic=a['synthetic']
        if set(self.model.classes_) != set(vocabulary['labels']): raise ValueError("Model classes differ from vocabulary")

    def predict(self,features):
        p=self.model.predict_proba([features])[0]; i=int(p.argmax())
        return str(self.model.classes_[i]),float(p[i])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset'); parser.add_argument('--vocabulary',default=str(Path(__file__).with_name('vocabulary.json')))
    parser.add_argument('--output',default='artifacts/glove_model.joblib')
    parser.add_argument('--group-by',choices=['participant','session'],default='participant')
    parser.add_argument('--allow-synthetic',action='store_true'); a=parser.parse_args()
    train(a.dataset,a.vocabulary,a.output,a.group_by,a.allow_synthetic)
