"""Assemble a transfer archive without venvs, toolchains or participant data."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[2]
GLOVE=ROOT/'glove'
DIST=ROOT/'deliverables'
STAGE=DIST/'Gesture_Glove_Project'


def copy_file(src,rel):
    dst=STAGE/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)


def copy_tree(src,rel,exclude=()):
    src=Path(src)
    for path in src.rglob('*'):
        if not path.is_file(): continue
        parts=path.relative_to(src).parts
        if any(p in exclude for p in parts) or path.suffix=='.pyc': continue
        copy_file(path,Path(rel)/path.relative_to(src))


def build():
    DIST.mkdir(exist_ok=True)
    if STAGE.exists():
        # No recursive delete: a new staging directory avoids losing prior data.
        raise FileExistsError('Transfer staging already exists. Choose a fresh stage or inspect it before updating.')
    for name in ['README.md','Start-Glove.cmd','Start-Glove-Demo.cmd','Setup-Glove.ps1']:
        copy_file(ROOT/name,name)
    for name in ['app.py','core.py','dataset.py','training.py','transport.py','speech.py','speech_worker.ps1',
                 'simulator.py','vocabulary.json','requirements.txt','requirements-build.txt','requirements-lock.txt',
                 'Flash-ESP32.ps1','Invoke-Firmware.ps1']:
        copy_file(GLOVE/name,Path('glove')/name)
    for name in ['tools','tests','docs','cad']:
        copy_tree(GLOVE/name,Path('glove')/name,exclude=('__pycache__',))
    copy_file(GLOVE/'firmware'/'platformio.ini','glove/firmware/platformio.ini')
    copy_file(GLOVE/'firmware'/'PREBUILT.md','glove/firmware/PREBUILT.md')
    copy_tree(GLOVE/'firmware'/'src','glove/firmware/src')
    for env in (GLOVE/'firmware'/'.pio'/'build').iterdir():
        if not env.is_dir(): continue
        for extension in ('*.bin','*.hex'):
            for p in env.glob(extension): copy_file(p,Path('glove/firmware/prebuilt')/env.name/p.name)
    boot=GLOVE/'.platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin'
    if boot.exists(): copy_file(boot,'glove/firmware/prebuilt/boot_app0.bin')
    copy_tree(GLOVE/'release'/'GloveStudio','glove/release/GloveStudio',exclude=('user_data','__pycache__'))
    copy_tree(GLOVE/'vendor'/'espeak-ng','glove/vendor/espeak-ng')
    for name in ['README.md','espeak-ng-1.52.0-source.zip']:
        copy_file(GLOVE/'vendor'/name,Path('glove/vendor')/name)
    for name in ['unit_tests.log','firmware_build.log','portable_build.log','verification.json']:
        copy_file(GLOVE/'artifacts'/name,Path('glove/artifacts')/name)
    for directory in ['simulation','portable_full_check','speech']:
        copy_tree(GLOVE/'artifacts'/directory,Path('glove/artifacts')/directory,exclude=('gui_data',))
    for path in ROOT.glob('*.docx'): copy_file(path,path.name)
    for path in ROOT.glob('*.pdf'): copy_file(path,path.name)
    cv=ROOT/'CV'/'hand_sign_cv'
    for path in cv.iterdir():
        if path.is_file() and path.suffix in ('.py','.md','.txt','.json'): copy_file(path,Path('CV/hand_sign_cv')/path.name)
    copy_tree(cv/'models','CV/hand_sign_cv/models')
    entries=[]
    for path in sorted(STAGE.rglob('*')):
        if path.is_file(): entries.append(dict(path=path.relative_to(STAGE).as_posix(),bytes=path.stat().st_size,
                                               sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (STAGE/'SHA256_MANIFEST.json').write_text(json.dumps(entries,indent=2),encoding='utf-8')
    archive=DIST/'Gesture_Glove_Project.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(STAGE.rglob('*')):
            if path.is_file(): z.write(path,Path(STAGE.name)/path.relative_to(STAGE))
    with zipfile.ZipFile(archive) as z:
        bad=z.testzip()
        if bad: raise AssertionError('Corrupt archive member: '+bad)
    print(json.dumps(dict(archive=str(archive),files=len(entries),archive_bytes=archive.stat().st_size,
                          sha256=hashlib.sha256(archive.read_bytes()).hexdigest()),indent=2))


if __name__=='__main__': build()
