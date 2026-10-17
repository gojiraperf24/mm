"""Build the team's editable manual, Markdown manual and evidence journal.

Run using the Codex bundled Python runtime (python-docx and Pillow).
Render the DOCX with Word/LibreOffice before releasing it.
"""
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'; OUT.mkdir(exist_ok=True)
ASSETS=OUT/'assets'; ASSETS.mkdir(exist_ok=True)


def diagram(name,title,boxes,edges,notes):
    im=Image.new('RGB',(1500,640),'#f3f6fa'); draw=ImageDraw.Draw(im)
    font_path='C:/Windows/Fonts/segoeui.ttf'
    font=ImageFont.truetype(font_path,25); small=ImageFont.truetype(font_path,22)
    draw.text((32,20),title,font=ImageFont.truetype(font_path,35),fill='#1c3044')
    for key,(x,y,w,h,text) in boxes.items():
        draw.rounded_rectangle((x,y,x+w,y+h),radius=15,fill='white',outline='#12636b',width=3)
        lines=text.split('\n')
        for i,line in enumerate(lines): draw.text((x+18,y+18+i*34),line,font=font,fill='#1c3044')
    for a,b in edges:
        x,y,w,h,_=boxes[a]; xx,yy,ww,hh,_=boxes[b]
        start=(x+w,y+h//2); end=(xx,yy+hh//2)
        draw.line((start,end),fill='#12636b',width=4)
        draw.polygon([(end[0],end[1]),(end[0]-12,end[1]-7),(end[0]-12,end[1]+7)],fill='#12636b')
    for i,line in enumerate(notes): draw.text((35,480+i*32),line,font=small,fill='#425971')
    path=ASSETS/(name+'.png'); im.save(path); return path


ARCH=diagram('architecture','From finger bend to a speech event',{
 'a':(30,110,260,160,'Glove\n5 bend sensors\nMPU6050'),
 'b':(345,110,280,160,'ESP32\n25 sensor scans / s\nUSB serial G1'),
 'c':(680,110,360,160,'Glove Studio\nCalibrate + classify\nConfidence + time gate'),
 'd':(1095,110,370,160,'Output\nEnglish / Hindi text\nWindows TTS or clips')},[('a','b'),('b','c'),('c','d')],
 ['TRAINING: labeled recordings -> participant-separated partitions -> Random Forest -> saved model',
  'INFERENCE: the same normalized features -> stable gesture -> one word event',
  'Sensor faults and motion suppress output. The laptop performs classification in this implementation.',
  'The simulator supplies synthetic packets through the same host feature and event pipeline.'])
WIRING=diagram('direct_wiring','One glove with direct ESP32 analog inputs',{
 'a':(40,110,490,210,'3.3 V -> flex sensor -> junction\nJunction -> fixed resistor -> GND\nJunction is the analog signal\nRepeat for each of 5 fingers'),
 'b':(660,90,790,270,'Thumb -> GPIO32     Index -> GPIO33\nMiddle -> GPIO34     Ring -> GPIO35\nLittle -> GPIO36 / VP\nMPU6050 SDA -> 21     SCL -> 22\nAll grounds connected; USB powers ESP32')},[('a','b')],
 ['Begin with five potentiometers if the bend sensors are not available; pots test the electronics only.',
  'MPU6050 breakout power and I2C pull-ups must be verified for 3.3 V operation.',
  'The multiplexer alternative uses C0..C4 -> SIG -> GPIO34 and S0..S3 -> 18,19,23,25.',
  'Do not apply 5 V to ESP32 analog inputs. Identify the TP4065 module before battery integration.'])
SPLIT=diagram('data_partitions','Six participants stay in separate evaluation groups',{
 'a':(40,110,420,170,'Training\n3 complete participants\nLearn gesture boundaries'),
 'b':(540,110,420,170,'Validation\n1 complete participant\nChoose confidence cutoff'),
 'c':(1040,110,420,170,'Test\n2 complete participants\nFinal untouched evaluation')},[],
 ['This is the actual split size from the six-participant synthetic integration check.',
  'Real split membership is saved in model.partitions.csv and model.metrics.json.',
  'Participant mode tests unseen people; session mode tests fresh visits and may reuse people.',
  'Synthetic performance verifies code paths and must never be used as physical glove accuracy.'])

# Each chapter starts on a new page, keeping bench instructions easy to locate.
# Content is the shared source for DOCX and Markdown; no fabricated measurements.
CHAPTERS=[
('Your project and the starting point',[
 ('p','This manual takes Group 39 from the supplied proposal to a working small-vocabulary gesture-to-speech prototype. The implemented system uses one ESP32 glove, five finger-bend inputs and an MPU6050, with recognition and speech on a Windows laptop. A second glove and wearable audio have optional firmware configurations.'),
 ('p','Available hardware confirmed by Tarun: ESP32, MPU6050 and a module described as TP4065. Flex sensors, resistors, glove materials and interconnects still need to be assembled. Begin with USB power. The battery module needs its exact markings and circuit identified before wiring.'),
 ('h','What you can use immediately'),
 ('steps',['Double-click Start-Glove-Demo.cmd in the project folder. It opens the packaged native application without installing Python.','Choose OPEN_PALM in Live recognition. Hold the simulated pose: its mapped phrase appears once. Choose REST, then OPEN_PALM again to test repeat control.','Select Check voices. Enable Auto speech only when you want audible output. English uses installed Windows voices; Hindi uses the included offline eSpeak NG voice.','Read the hardware chapter, gather five sensor channels and wire one glove. Use the calibration and recording tabs to build the real dataset.']),
 ('h','Evidence and completion boundary'),
 ('p','Automated unit checks, serial loopback, native UI simulation, and synthetic collection/training/model reload are software verification. They do not establish physical recognition accuracy, fit, comfort, radio range or speech audibility. Record those measurements using the acceptance protocol in this manual. The supplied image alphabet model remains a separate CV experiment.'),
 ('p','All eight word mappings are arbitrary team-defined demonstration gestures. They are not verified Indian Sign Language or American Sign Language signs. A small static recognizer does not capture language grammar, facial expression, two-hand relationships or continuous signing.')]),
('How the system works and why',[
 ('image',ARCH),
 ('p','A bend sensor changes electrical resistance when a finger bends. A resistor divider turns that change into a voltage. The ESP32 measures the five voltages and reads hand acceleration and rotation rate from the MPU6050. Firmware sends a complete packet about every 40 milliseconds; the host validates it before using it.'),
 ('p','Calibration translates each finger reading into an approximate bend value from 0 to 1. The host also converts acceleration to a unit gravity direction and subtracts a stationary gyro bias. One glove therefore provides eleven features: five bends, three gravity-direction values and three normalized angular-rate values.'),
 ('p','A Random Forest learns combinations of these numbers from labeled examples. Its highest class score is compared with a cutoff chosen using validation participants. A stable candidate must persist for 0.45 seconds before it generates a word event. REST must persist for 0.35 seconds to permit repeating the same word.'),
 ('h','Why the laptop is in the loop'),
 ('p','The laptop provides a visible calibration tool, an editable dataset, repeatable training, metrics and installed speech engines. The ESP32 remains a sensor and optional audio endpoint. Embedded inference and an Android app are future ports; neither is represented as delivered here. This keeps the first demonstration measurable and makes failures easy to trace.')]),
('Prepare the hardware and your bench',[
 ('table',(['Item','Status and purpose'],[
 ['ESP32 and USB data cable','ESP32 confirmed. Verify the board is an original ESP32 DevKit/WROOM-compatible board; the build targets esp32dev. USB cable must carry data.'],
 ['MPU6050 breakout','Confirmed. One IMU for the first glove; mount its axes consistently and inspect supply/pull-up wiring.'],
 ['Five bend sensors','Needed for a physical glove. Commercial flex sensors or characterized DIY sensors; five potentiometers can first emulate them.'],
 ['Five fixed resistors','Select near the measured straight sensor resistance; 10 kOhm is a bench starting point, not a guaranteed best value.'],
 ['Glove and harness','Stretch glove, removable sensor sleeves, flexible wire, heat shrink and detachable connectors.'],
 ['Meter and breadboard','Measure resistance, voltages, continuity and channel order before wearing the glove.'],
 ['CD74HC4067','Optional for one glove; useful for ten channels. Use HC at a verified 3.3 V supply in the ESP32 path.'],
 ['TP4065 module','Exact identity unconfirmed. Keep disconnected during the first USB-powered build.'],
 ['DFPlayer, speaker and SD card','Optional wearable recorded-word output; not needed for laptop speech.']])),
 ('steps',['Record the exact board and module markings in the bench log. Photograph your own assembly for the final report.','With power removed, check the breadboard ground rail, resistor values and sensor continuity. Measure each sensor flat and comfortably bent; do not force the active region.','Start with one voltage divider and verify its output changes smoothly. Extend to five channels only after this works.','Use a data USB cable and close other serial monitors before connecting Glove Studio.']),
 ('p','Why: faults are easier to locate in one channel than in a sewn, ten-sensor harness. Potentiometers can prove scanning, packets and calibration while the sensors are being sourced, but cannot prove wearable gesture performance. Obtain current quotes before purchasing; the old documents contain estimates rather than a verified current budget.')]),
('Wire the ESP32 and the sensors',[
 ('image',WIRING),
 ('steps',['Build each divider as 3.3 V -> sensor -> signal junction -> fixed resistor -> GND. Connect the five junctions to the pins in the diagram. This topology makes increasing sensor resistance lower the measured voltage.','Connect MPU6050 SDA to GPIO21, SCL to GPIO22 and GND to the common ground. Use a breakout verified for the chosen 3.3 V supply and pull-up voltage. Set AD0 low for address 0x68.','Measure each analog junction before connecting it to the ESP32. Keep it inside the board input limits and away from clipping at the ADC rails.','Use the esp32-direct build for these five direct channels. For a multiplexer, use esp32-usb instead: mux VCC 3.3 V, GND and EN low, S0/S1/S2/S3 to GPIO18/19/23/25, SIG to GPIO34, C0..C4 in thumb-to-little order.']),
 ('p','The mux firmware waits 300 microseconds after selecting a channel, discards one ADC conversion, and averages four conversions. The settling delay is an initial engineering setting; confirm it on your actual high-impedance sensor dividers. Direct wiring also averages four readings, but avoids the multiplexer entirely.'),
 ('p','Why: all chosen classic ESP32 analog inputs use ADC1, and the protocol keeps finger order constant across wiring choices. The ADC reports normalized sensor positions, not an accurate voltage measurement or joint angle. ESP32 ADC nonlinearity and a soft sensor response are handled approximately by endpoints and varied training data.')]),
('Fit the glove and make the wrist housing',[
 ('steps',['Put on the bare glove and mark the back of each finger. Make soft sleeves or guides so each active sensor region follows a finger bend without twisting.','Anchor the sensor lead end and route slack wire along the back of the hand. Keep joints and fingertips free. Use removable attachment while tuning positions.','Mount the MPU6050 rigidly on the back of the hand with a marked axis direction. Mount the controller on the wrist, and add strain relief before every connector.','Open cad/wrist_enclosure.scad in OpenSCAD. Measure the actual controller board and connector heights; change inside_length, inside_width and inside_height. Defaults are a 60 x 32 x 22 mm cavity, not a board-specific fit.','Render base and lid separately, export STL and print a fit sample before the final enclosure. Use rounded finishing, insulation and a comfortable strap. Recalibrate after fitting or moving a sensor.']),
 ('h','Why fit changes the data'),
 ('p','A different sleeve position changes which part of the sensor bends. A loose IMU changes the coordinate frame. A tight wire can restrict the gesture and introduce intermittent connections. Good mechanical mounting improves the dataset more than adding classifier complexity to unstable hardware.'),
 ('h','What remains to measure'),
 ('p','Check reach of motion, donning time, sensor strain, connector retention and comfort after a ten-minute wear period. Record qualitative feedback and enclosure dimensions. The CAD file is an editable enclosure concept; it has not been physically printed or fitted. Do not seal a battery inside this first USB-powered design.'),
 ('p','For an identified future battery system, verify cell chemistry, charger, protection, regulated board supply, power-path/load behavior and connector polarity from the actual module documentation. A charging board alone does not establish a complete safe ESP32 supply. The string TP4065 is insufficient to specify those connections.')]),
('Compile and flash your firmware',[
 ('steps',['For development on a fresh machine, install 64-bit Python 3.12, then run Setup-Glove.ps1 from the project root. It creates a project virtual environment and installs the listed dependencies. The portable desktop app needs none of this setup.','Use Device Manager or Refresh ports in Glove Studio to identify the ESP32 COM port. Disconnect Glove Studio before uploading.','For five direct analog channels, run the command below, replacing COM7 with the real port. If upload waits at Connecting, follow the board boot-button procedure and verify the USB cable.','Open Glove Studio, select the same COM port, choose 115200 and Connect glove. Allow the reset/startup interval. Valid sensor packets produce CALIBRATE.']),
 ('code',r'.\glove\Flash-ESP32.ps1 -Port COM7 -Environment esp32-direct'),
 ('h','Firmware configurations'),
 ('table',(['Environment','Use'],[['esp32-direct','One glove, five ADC1 pins, USB. Recommended first build.'],['esp32-usb','One glove through CD74HC4067, USB.'],['esp32-two-hands','Ten mux channels and two IMUs on 0x68/0x69.'],['esp32-bluetooth','One mux glove, USB plus original ESP32 Classic SPP.'],['esp32-audio','One mux glove, USB and optional DFPlayer.'],['nano-usb','Alternative Nano/mux version from the later plan.'],['nano-bluetooth','Nano plus HC-05 at 9600 baud; slower 250 ms scan.']])),
 ('p','Invoke-Firmware.ps1 compiles through a temporary unused drive alias because the ESP32 compiler does not reliably handle spaces in its own directory. It removes the alias afterward. tools/pio.py also fixes the pinned PlatformIO package-script quoting issue. These helpers do not change the firmware behavior.'),
 ('p','Compilation checks source compatibility and memory size. It cannot verify wiring, an upload, IMU axes or actual scan stability. Preserve the version and firmware hashes with each final experiment.')]),
('Explore the software before collecting real data',[
 ('steps',['Launch Start-Glove-Demo.cmd. The banner explicitly identifies synthetic input. The simulator supplies 25 readings per second and uses known template poses.','Select OPEN_PALM, FIST and INDEX_UP in turn. A stable pose produces its label and mapped phrase. A new candidate temporarily becomes UNKNOWN while its hold time accumulates.','Keep FIST selected for several seconds. Confirm that only one word event appears. Select REST long enough to rearm, then FIST again.','Switch language to hi. Text changes to Hindi. Check voices lists the Windows voices and the included compact offline English/Hindi engine.','Disconnect, then connect the physical glove. Synthetic calibration and models are removed at this boundary.']),
 ('h','Why simulation exists'),
 ('p','The simulator permits checking the UI, feature schema, recording format, training path and speech-event logic without a finished glove. tools/demo_check.py separately creates 2,160 synthetic labeled rows across six named synthetic participants, trains a model, reloads it and verifies all eight word events.'),
 ('p','Those clean artificial signals can yield perfect classification, but that says nothing about sensor noise, user variation or actual unknown gestures. The program records source provenance and rejects synthetic models on hardware. Real experiments start with a new hardware calibration and samples.csv.'),
 ('h','Files you own'),
 ('p','Each app keeps settings and recordings under user_data beside its source or executable. It copies the starter vocabulary on first launch. Dataset CSVs, calibration JSON, model files, metrics, events.csv and activity.log stay local. Copy the complete application folder to another computer; do not move just the EXE.')]),
('Calibrate each finger for each participant',[
 ('steps',['Connect the glove and wait for valid packets. Enter a participant pseudonym such as p01, then fit the glove comfortably.','Press Capture open hand. There is a three-second preparation period, followed by 2.4 seconds of readings. Extend the fingers without forcing them and hold the wrist still.','Press Capture closed hand and repeat with a comfortable fist. Only the open and closed endpoint captures belong to this calibration.','Press Save calibration. The program requires at least 30 readings per pose, enough bend span, quiet flex readings and a still wrist. It saves a fingerprinted JSON profile.','Return to Live recognition and check that each gauge moves near 0 for open and 1 for closed. Recalibrate if a sensor moves, the wearer changes, or an endpoint clips.']),
 ('h','The calculation'),
 ('code','bend[i] = (raw[i] - open[i]) / (closed[i] - open[i])'),
 ('p','The median of the endpoint captures resists occasional spikes. The denominator may be negative: in the chosen divider, increasing flex resistance decreases voltage. The same equation still maps open to 0 and closed to 1. A span smaller than 6% of ADC range is rejected. Endpoint rails and excessive capture variation are rejected rather than silently training on a broken channel.'),
 ('p','The stationary gyro median is the bias to subtract during recognition. Acceleration provides a gravity direction while the wrist is still; its magnitude must remain between 0.85 g and 1.15 g. Angular speed above 35 degrees per second suppresses recognition. These are configurable source constants and initial bench limits, not universal sensor specifications.'),
 ('p','Calibration is a normalization procedure, not a measurement of true finger angle. Inspect each real sensor channel before assuming the model can correct it. A calibration belongs to one participant, hardware layout and physical fitting.')]),
('Freeze a vocabulary your sensors can distinguish',[
 ('table',(['Label','Physical pose','Demo phrase'],[
 ['REST','Relaxed moderate finger bends','No speech'],['OPEN_PALM','All fingers extended','Hello'],['FIST','All fingers bent','Yes'],['THUMB_UP','Thumb extended; other fingers bent','Thank you'],['INDEX_UP','Index extended; others bent','Water'],['V_SHAPE','Index and middle extended','Help'],['THREE_FINGERS','Index, middle and ring extended','Food'],['LITTLE_UP','Little extended; others bent','No'],['THUMB_LITTLE','Thumb and little extended','Goodbye']])),
 ('p','These word meanings are arbitrary demo mappings. Discuss which messages are useful, and obtain competent signer review if you want to use verified language signs. Record the exact pose definition, hand, orientation, English phrase and Hindi phrase before collection.'),
 ('steps',['In the Vocabulary tab, disconnect the device, choose a label and edit its pose description and phrases. Save the word mapping.','Keep REST distinct from every active target. Include several relaxed hand configurations in its examples. UNKNOWN is a runtime outcome; it is not a training label.','For a different class list, edit user_data/vocabulary.json while the app is closed, preserve its schema and REST, and restart. Choose a new dataset path and retrain.','Use gestures distinguishable in finger bend and gravity orientation. For example, finger spread alone is not measured; two poses with the same bends can be indistinguishable.']),
 ('p','The MPU6050 measures gravity direction and angular rate. It does not provide a drift-free absolute yaw heading. This implementation does not integrate gyros into yaw or recognize motion sequences. A rotated hand about the gravity axis may therefore remain ambiguous. Reduce vocabulary scope when the available measurements do not separate two gestures.')]),
('Collect a real dataset without leakage',[
 ('steps',['Calibrate p01 after fitting the glove. Use a session ID representing the entire recording visit, such as 20261003-visit1. Keep that session name for every label collected during the visit.','Select a label and 40 samples, then Record trial. After three seconds to prepare, the collector saves at most five valid readings per second and stops automatically. Keep the label unchanged throughout the trial.','Lower the hand, relax and reform the pose before another trial. Collect three trials for every gesture and REST. Vary comfortable wrist tilt and finger position within the pose definition.','Repeat for all six people. Repeat on a later visit with a fresh fit and calibration. Do not invent new participant or session IDs to make one recording appear independent.','Use one real CSV for compatible recordings. If definitions, feature code or hand count change, begin a new dataset and train a new model.']),
 ('p','With six people, nine labels, three 40-sample trials and two visits, the plan yields 12,960 valid rows. The adjacent readings within a trial are still correlated. More independent people and visits improve evaluation more than repeatedly holding one pose for thousands of nearly identical readings.'),
 ('h','What a row contains'),
 ('p','Each row stores label, participant, session, trial, UTC timestamp, source, hand count, feature version, vocabulary fingerprint, calibration fingerprint and f00..f10 for one hand. Two hands use f00..f21. Calibration profiles are saved separately for interpretation. The collector stores normalized features rather than images or audio.'),
 ('p','Only valid, approximately still readings are recorded. Faulty and moving readings are skipped; a long unusable trial times out. Watch the usable-sample count. Do not label transitions as active target gestures. REST should have varied ordinary idle poses and roughly comparable counts. Keep a bench log of fit changes and environmental conditions.')]),
('Train and understand the evaluation',[
 ('image',SPLIT),
 ('steps',['Stop recording and open Train and evaluate. Select the real samples.csv and choose an output model path. Leave Allow synthetic unchecked.','Choose participant grouping for an unseen-person evaluation. Session grouping instead keeps participant/visit pairs separate and measures a new visit rather than necessarily a new wearer.','Press Train model. Validation checks every label, REST, finite features, compatible fingerprints and source, and at least 30 rows per class across three independent groups. The normal collection recommendation is stronger than this minimum.','Review the raw accuracy, accepted accuracy, coverage, threshold, validation target and confusion CSV. Load trusted model only after checking these results.']),
 ('p','Training learns the patterns from training groups. Validation tries confidence cutoffs from 0.50 to 0.95 and aims for 95% accepted accuracy with at least 50% coverage. If none meets that target, it reports the failure and chooses a fallback by validation macro F1. Test data are held aside until the cutoff is chosen; the saved classifier is not refitted with test data.'),
 ('p','Accuracy is the fraction of known test rows correctly classified. Coverage is the fraction accepted above the cutoff. Accepted accuracy measures just those accepted rows. Overall accuracy with rejection counts UNKNOWN as incorrect for a known gesture. Examine all four; tiny coverage can make an impressive accepted accuracy unhelpful.'),
 ('p','The forest score is a heuristic vote score, not a calibrated correctness probability. Unknown poses can still receive a high score. Evaluate them explicitly. If you repeatedly change the vocabulary using test results, collect a fresh final test group. Do not reuse the archive alphabet accuracy as a glove result.')]),
('Use recognition and speech deliberately',[
 ('steps',['Connect the physical glove, calibrate it and load the model trained on real recordings for that vocabulary and hand count.','Form a static pose and hold it. A candidate must meet its confidence cutoff continuously for 0.45 seconds before a phrase is added. UNKNOWN clears an unstable candidate.','Hold the same gesture: it produces one event. Sustain REST for 0.35 seconds to repeat the same word, or form a different stable gesture to speak a new word directly.','Enable Auto speech and choose en or hi. Windows speech runs in a worker so it cannot block serial processing. Speak phrase history can read the accumulated text manually.','For an optional DFPlayer-equipped glove, select DFPlayer on glove. Automatic word events send PLAY commands for numbered recordings rather than laptop TTS.']),
 ('h','Fault behavior'),
 ('p','A missing IMU mask, corrupt packet, ADC rail, calibration mismatch, excessive movement or more than 0.5 seconds without a fresh packet suppresses recognition. Invalid data do not rearm the last word, so a reconnect/noisy gap cannot automatically repeat a held gesture. A stalled input queue is discarded instead of treating old buffered data as a new sustained gesture.'),
 ('h','English and Hindi output'),
 ('p','The current machine exposes Microsoft David Desktop and Microsoft Zira Desktop, both en-US. English normally uses these installed voices. Hindi uses the bundled eSpeak NG 1.52.0 engine to generate a local WAV and play it in the speech worker. The portable engine also provides an English fallback. No account or internet connection is needed for live synthesis.'),
 ('p','The compact eSpeak voice sounds synthetic and its Hindi pronunciation needs team listening review. Silent checks confirmed nonempty English/Hindi waveforms, not audibility or pronunciation quality. For polished output, use reviewed recorded clips on DFPlayer; a future native Hindi voice integration can replace the fallback.'),
 ('p','Recorded-word output avoids dependence on installed voices. Store agreed recordings on the SD card in /mp3/0001.mp3 through /mp3/0008.mp3 for English, and /mp3/0101.mp3 through /mp3/0108.mp3 for Hindi. REST has no recording. Playback commands are logged as sent, not confirmed audible.')]),
('Add Bluetooth or wearable audio after USB works',[
 ('h','Original ESP32 Bluetooth'),
 ('steps',['Confirm the board is an original ESP32 with Classic Bluetooth support. The SPP build is not a BLE implementation and is not compatible with every ESP32-family chip.','Wire the mux configuration and flash esp32-bluetooth. Pair Group39-Glove in Windows Bluetooth settings. Find its outgoing virtual COM port.','Connect that COM port in Glove Studio at 115200. Repeat calibration, packet stability and disconnect tests over the radio.','Measure end-to-end latency and dropouts at the intended demonstration distance. Keep USB as the rehearsal fallback.']),
 ('h','DFPlayer output'),
 ('steps',['For esp32-audio, connect ESP32 TX GPIO17 through a 1 kOhm series resistor to DFPlayer RX. GPIO16 is reserved as player RX on the controller. Use a common ground and a correctly rated supply for the actual module.','Connect the compatible speaker to the player speaker terminals according to its documentation. Prepare the FAT-formatted SD card and numbered /mp3 files. Use recordings reviewed by your team.','With the sensor glove still on USB, load the real model and choose DFPlayer on glove plus Auto speech. Verify each English and Hindi track individually before testing recognition.','Record audio completion and supply stability during playback. Firmware only confirms command transmission; it does not report successful SD decoding or audible sound.']),
 ('p','The shipped Bluetooth and audio environments are separate builds. To combine them, define both ENABLE_BT and ENABLE_DFPLAYER in a new environment, then compile and bench-test the combined configuration. Do not introduce wireless, battery and audio faults while basic sensing is still unstable.'),
 ('p','The alternative Nano version uses a mux, A0 and S0..S3 on D2..D5; I2C is A4/A5. Its HC-05 pins are D10 receive and D11 transmit through appropriate voltage conversion for the module. The 9600-baud radio version scans every 250 ms to fit its bandwidth. This is an optional path from the later plan; use your ESP32 first.')]),
('Verify the physical prototype and keep evidence',[
 ('table',(['Experiment','Record and pass target proposed by the team'],[
 ['Channel bench check','All five channels vary in the expected direction; no clipped or intermittent readings during slow bends.'],
 ['Still-hand capture','Sufficient endpoint span for every finger; capture succeeds without moving the wrist.'],
 ['Held-out people','Aim for >=90% raw accuracy with >=80% coverage; document accepted accuracy and per-class recall. These are targets, not measured results.'],
 ['Idle and unknown poses','Ten minutes of varied REST and unseen poses; count false word events and report the time denominator. Target zero idle events.'],
 ['Repeated gesture','Hold each pose for 5 seconds; exactly one event. Return to REST and repeat; one new event.'],
 ['Fault injection','Unplug an IMU/sensor or serial cable on the bench; no new automatic word event from invalid input.'],
 ['Latency','Measure pose completion to text event and audible onset separately; report median and 95th percentile. Proposed text target median <=1.5 s.'],
 ['Wearability','Ten-minute wear trial; log discomfort, restricted motion, connector strain and mounting shifts.']])),
 ('p','Use acceptance_log.csv for experimental records. Note firmware environment/hash, model/hash, calibration ID, participant, session, expected label, observed label, timestamp and a pass/fail observation. Preserve the training metrics and partitions. Use consenting participant pseudonyms and keep personally identifying notes outside the feature dataset.'),
 ('p','Repeat the final experiment on groups not used to tune the vocabulary or confidence settings. Known-class test accuracy does not describe rejection of arbitrary gestures. Report false activation counts, transition errors and faults alongside the classifier metrics.'),
 ('p','The included software unit tests and synthetic checks exercise repeatability, not hardware. Bluetooth range, actual sensor faults, speech audibility, comfort, real Hindi output, printed enclosure fit and real recognition remain bench deliverables until this log is filled.')]),
('Troubleshoot from the first failing stage',[
 ('table',(['Symptom','Check and reason'],[
 ['No COM port','Use a data cable, inspect Device Manager and install the driver matching the board USB chip if needed. No port was present during this build session.'],
 ['Port busy','Disconnect the app before flashing; close Arduino Serial Monitor and other readers. One reader owns the serial device.'],
 ['CALIBRATE stays visible','This is expected without a valid profile. Capture both endpoint poses and Save calibration.'],
 ['IMU fault','Check SDA/SCL, supply, ground, AD0/address and module identity. A two-hand build requires both IMUs.'],
 ['Bend span too small','Check sensor placement, channel order, resistance and divider choice; do not force your fingers to compensate for wiring.'],
 ['ADC rail or clipping','Measure junction voltage and inspect disconnected leads or short circuits. Recalibration cannot repair a clipped signal.'],
 ['MOVING repeatedly','Hold wrist still, inspect IMU mounting and gyro bias, and verify physical units and sensor configuration.'],
 ['Vocabulary mismatch','Definitions changed. Select a new dataset and retrain instead of deleting fingerprint checks.'],
 ['Cannot split groups','Record every label for additional full participants/visits. Do not random-split adjacent rows.'],
 ['UNKNOWN on real gestures','Inspect held-out confusion, fitting and variability before lowering the threshold. A high score is not proof.'],
 ['Hindi speech error','Keep the complete portable folder including vendor/espeak-ng data and DLLs. Review the activity error and verify the default output device.'],
 ['DFPlayer silent','Check firmware audio flag, power, common ground, SD filesystem, file numbering and speaker wiring. Command acknowledgement is not playback confirmation.']])),
 ('p','For the existing CV add-on, follow CV/hand_sign_cv/README.md. Its real landmark dataset is separate from this sensor dataset. The archive HOG/SVM was trained on alphabet images; it has no matched glove vocabulary or REST coverage. No automatic camera failsafe is claimed by this build.'),
 ('p','Keep the failure logs. If you change feature calculations, increment FEATURE_VERSION and recollect or explicitly convert compatible source recordings. Do not quietly mix old and new feature meanings.')]),
('Finish the team work and report it honestly',[
 ('table',(['Suggested owner','Next concrete deliverable'],[
 ['Tarun and software partner','Run the app, manage vocabulary/datasets, train, review metrics and keep the software evidence.'],
 ['Hardware pair','Build dividers, validate the IMU/ADC channels, make a labeled detachable harness and bench log.'],
 ['Mechanical pair','Fit sensor sleeves, provide strain relief, measure the board, adapt/print enclosure and record comfort feedback.'],
 ['All six members','Provide consented varied recordings across two visits and take part in final acceptance tests.'],
 ['Team lead','Agree the vocabulary and success targets, track dependencies, and approve the final report scope.']])),
 ('h','Suggested next sequence'),
 ('steps',['Session 1: five pots or one sensor, USB packets and calibration. Finish the electronics check before sewing.','Session 2: fit one complete glove and collect a pilot dataset across three people. Remove ambiguous poses.','Sessions 3 and 4: freeze definitions, collect the six-person/two-visit dataset, train and inspect held-out errors.','Session 5: real speech-event tests, idle/unknown/fault trials and latency measurements. Add radio/audio only after this succeeds.','Final session: rehearse with a cold app start, prepare fallback USB cable, freeze software/firmware/model hashes and complete the report.']),
 ('p','REPORT_TEMPLATE.md contains the technical structure and explicitly marks measurements that require your bench data. Preserve the original proposal and prototype plan. Explain the final one-glove/laptop scope and the reasons for it. Separate what is implemented, what is verified by software, and what is measured on the device.'),
 ('p','BUILD_JOURNAL.md records the implementation sequence, the purpose of each module, actual checks and Windows build fixes. Repeatable scripts, source files, compiled firmware and the portable app are included in the transfer package; recorded participant data are excluded by default.')]),
('Technical references and file map',[
 ('p','The implementation follows the manufacturer/controller APIs and grouped-evaluation guidance below. Hardware pin limits, module supply ratings and board variants must be checked against the exact purchased parts.'),
 ('refs',[
 ('Espressif Arduino ESP32 ADC API','https://docs.espressif.com/projects/arduino-esp32/en/latest/api/adc.html'),
 ('TI CD74HC4067 product and datasheet','https://www.ti.com/product/CD74HC4067'),
 ('Adafruit MPU6050 source and examples','https://github.com/adafruit/Adafruit_MPU6050'),
 ('DFRobot DFPlayer Mini documentation','https://wiki.dfrobot.com/dfr0299'),
 ('scikit learn GroupShuffleSplit','https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html'),
 ('scikit learn leakage and common pitfalls','https://scikit-learn.org/stable/common_pitfalls.html'),
 ('Microsoft SpeechSynthesizer API','https://learn.microsoft.com/en-us/dotnet/api/system.speech.synthesis.speechsynthesizer'),
 ('eSpeak NG official release and Hindi support','https://github.com/espeak-ng/espeak-ng/releases/tag/1.52.0')]),
 ('table',(['File','Purpose'],[['app.py','Native collection/training/live UI and event log.'],['core.py','Wire protocol, fingerprints, calibration, features and event gate.'],['dataset.py','Validated CSV recordings with provenance.'],['training.py','Grouped partitions, forest, cutoff and metrics.'],['transport.py','Bounded serial reader and DFPlayer commands.'],['speech.py and speech_worker.ps1','Nonblocking local Windows speech.'],['simulator.py and tools/demo_check.py','Synthetic-only software checks.'],['firmware/src/main.cpp','Sensor scans and optional audio/Bluetooth endpoint.'],['cad/wrist_enclosure.scad','Editable wrist box concept.'],['tests/test_system.py','Protocol, calibration, dataset, event and serial regression tests.'],['Invoke-Firmware.ps1','Repeatable compiler and optional upload entry.'],['tools/build.ps1','Source verification and portable packaging.'],['artifacts','Test results, simulation and firmware build evidence.']])),
 ('p','Source documents: project_proposal (1) (1) (1) (2).docx and Sign_Friendly_Gloves_Prototype_Plan (1).pdf in the project root. Hardware inventory and deliverables were updated for the 3 October 2026 implementation session.')])
]


def table(doc,headers,rows):
    t=doc.add_table(rows=1,cols=len(headers)); t.style='Light Shading Accent 1'
    for c,text in zip(t.rows[0].cells,headers): c.text=text
    repeat=OxmlElement('w:tblHeader'); t.rows[0]._tr.get_or_add_trPr().append(repeat)
    for row in rows:
        cells=t.add_row().cells
        for c,text in zip(cells,row):
            c.text=text
            for p in c.paragraphs:
                p.paragraph_format.space_after=Pt(3)
                for run in p.runs: run.font.size=Pt(9.5)
        trpr=t.rows[-1]._tr.get_or_add_trPr(); trpr.append(OxmlElement('w:cantSplit'))
    doc.add_paragraph()


def build():
    doc=Document(); sec=doc.sections[0]
    sec.page_width=Inches(8.27); sec.page_height=Inches(11.69)
    sec.top_margin=sec.bottom_margin=Inches(.7); sec.left_margin=sec.right_margin=Inches(.72)
    normal=doc.styles['Normal']; normal.font.name='Calibri'; normal.font.size=Pt(11)
    normal.paragraph_format.space_after=Pt(7); normal.paragraph_format.line_spacing=1.06
    for name in ('Title','Heading 1','Heading 2'):
        doc.styles[name].font.name='Calibri'; doc.styles[name].font.color.rgb=RGBColor.from_string('000000')
    doc.styles['Heading 1'].font.size=Pt(22); doc.styles['Heading 2'].font.size=Pt(13)
    doc.core_properties.title='Gesture to Speech Glove Build and Use Manual'
    doc.core_properties.subject='Group 39 Engineering Design prototype'
    doc.core_properties.author='Group 39'
    foot=sec.footer.paragraphs[0]; foot.alignment=2
    field=OxmlElement('w:fldSimple'); field.set(qn('w:instr'),'PAGE'); foot._p.append(field)
    md=['# Gesture to Speech Glove Build and Use Manual','', 'Group 39 | ID1050A | IIT Palakkad | 3 October 2026','']
    for n,(title,blocks) in enumerate(CHAPTERS,1):
        if n==1:
            doc.add_paragraph('Gesture to Speech Glove\nBuild and Use Manual','Title')
            doc.add_paragraph('Group 39  |  ID1050A  |  IIT Palakkad  |  3 October 2026')
        else: doc.add_page_break()
        doc.add_heading(f'{n} {title}',level=1); md+=['## '+str(n)+' '+title,'']
        for kind,value in blocks:
            if kind=='p': doc.add_paragraph(value); md += [value,'']
            elif kind=='h': doc.add_heading(value,level=2); md += ['### '+value,'']
            elif kind=='steps':
                for i,step in enumerate(value,1): doc.add_paragraph(f'{i}. {step}'); md += [f'{i}. {step}']
                md.append('')
            elif kind=='code':
                p=doc.add_paragraph(); run=p.add_run(value); run.font.name='Consolas'; run.font.size=Pt(9)
                md += ['```powershell' if value.startswith('.\\') else '```',value,'```','']
            elif kind=='image':
                doc.add_picture(str(value),width=Inches(6.75)); md += [f'![{value.stem}](assets/{value.name})','']
            elif kind=='table':
                headers,rows=value; table(doc,headers,rows)
                md += ['| '+' | '.join(headers)+' |','| '+' | '.join('---' for _ in headers)+' |']
                md += ['| '+' | '.join(row)+' |' for row in rows]; md.append('')
            elif kind=='refs':
                for label,url in value:
                    p=doc.add_paragraph(label+'\n'+url)
                    for run in p.runs: run.font.size=Pt(9)
                    md += [f'- [{label}]({url})']
                md.append('')
    # Strip default-template paragraph borders, including Word's Title rule.
    for element in (doc.element,doc.styles.element):
        for border in list(element.iter(qn('w:pBdr'))): border.getparent().remove(border)
    doc.save(OUT/'Gesture_Glove_Manual.docx')
    (OUT/'MANUAL.md').write_text('\n'.join(md),encoding='utf-8')
    print('Saved manual with',len(CHAPTERS),'chapters')


if __name__=='__main__': build()
