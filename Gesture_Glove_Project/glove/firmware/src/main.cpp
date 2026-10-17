// Group 39 gesture glove. USB serial first; Bluetooth/audio are optional.
// Each packet: G1,seq,ms,hands,adc_max,imu_mask,11 fields per hand.
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <math.h>

#ifndef GLOVE_HANDS
#define GLOVE_HANDS 1
#endif
#ifndef ENABLE_BT
#define ENABLE_BT 0
#endif
#ifndef ENABLE_DFPLAYER
#define ENABLE_DFPLAYER 0
#endif
#ifndef SAMPLE_PERIOD_MS
#define SAMPLE_PERIOD_MS 40
#endif
#ifndef USE_DIRECT_FLEX
#define USE_DIRECT_FLEX 0
#endif
static_assert(GLOVE_HANDS == 1 || GLOVE_HANDS == 2, "Use one or two hands");

#ifdef ARDUINO_ARCH_ESP32
const uint8_t MUX_PINS[] = {18, 19, 23, 25};
const uint8_t ADC_PIN = 34; // ADC1; input-only pin is suitable here.
const uint16_t ADC_MAX_VALUE = 4095;
#if USE_DIRECT_FLEX
static_assert(GLOVE_HANDS == 1, "Direct wiring supports the one-glove prototype");
const uint8_t FLEX_PINS[] = {32,33,34,35,36};
#endif
#if ENABLE_BT
#include <BluetoothSerial.h>
BluetoothSerial radio;
#endif
#if ENABLE_DFPLAYER
HardwareSerial player(2); // RX16, TX17; optional DFPlayer input via 1k series.
#endif
#else
const uint8_t MUX_PINS[] = {2, 3, 4, 5};
const uint8_t ADC_PIN = A0;
const uint16_t ADC_MAX_VALUE = 1023;
#if ENABLE_BT || ENABLE_DFPLAYER
#include <SoftwareSerial.h>
#endif
#if ENABLE_BT
SoftwareSerial radio(10, 11); // HC-05 TX -> D10; D11 -> divider -> HC-05 RX.
#endif
#if ENABLE_DFPLAYER
SoftwareSerial player(8, 9);
#endif
#endif

Adafruit_MPU6050 imus[GLOVE_HANDS];
bool imuReady[GLOVE_HANDS];
float readings[GLOVE_HANDS * 11];
uint32_t sequence = 0, lastSample = 0;

void emit(Print &out, uint32_t timestamp, uint8_t mask) {
  out.print(F("G1,")); out.print(sequence); out.print(',');
  out.print(timestamp); out.print(','); out.print(GLOVE_HANDS); out.print(',');
  out.print(ADC_MAX_VALUE); out.print(','); out.print(mask);
  for (uint8_t i = 0; i < GLOVE_HANDS * 11; ++i) {
    out.print(','); out.print(readings[i], i % 11 < 5 ? 0 : 5);
  }
  out.println();
}

uint16_t readMux(uint8_t channel) {
#if USE_DIRECT_FLEX && defined(ARDUINO_ARCH_ESP32)
  const uint8_t pin = FLEX_PINS[channel];
  analogRead(pin);
  uint32_t sum=0;
  for (uint8_t i=0; i<4; ++i) sum+=analogRead(pin);
  return sum/4;
#else
  for (uint8_t i=0; i<4; ++i) digitalWrite(MUX_PINS[i], (channel >> i) & 1);
  delayMicroseconds(300); // Conservative initial settling; verify with actual sensors.
  analogRead(ADC_PIN); // Discard first conversion after changing channel.
  uint32_t sum = 0;
  for (uint8_t i=0; i<4; ++i) sum += analogRead(ADC_PIN);
  return sum / 4;
#endif
}

#if ENABLE_DFPLAYER
void playerCommand(uint8_t cmd, uint16_t parameter) {
  uint8_t frame[] = {0x7e,0xff,0x06,cmd,0x00,uint8_t(parameter>>8),uint8_t(parameter),0,0,0xef};
  uint16_t checksum = uint16_t(0 - (0xff + 0x06 + cmd + frame[5] + frame[6]));
  frame[7] = checksum >> 8; frame[8] = checksum & 0xff;
  player.write(frame,sizeof(frame));
}
#endif

void handleCommand(char *text, Print &reply) {
  if (strcmp(text,"PING")==0) { reply.println(F("#A,PONG")); return; }
  if (strncmp(text,"PLAY ",5)!=0) { reply.println(F("#E,Unknown command")); return; }
  char *end;
  long track = strtol(text+5,&end,10);
  if (*end != '\0' || track<1 || track>199) { reply.println(F("#E,Track must be 1..199")); return; }
#if ENABLE_DFPLAYER
  static uint32_t lastPlay = 0;
  if (lastPlay && millis()-lastPlay<600) { reply.println(F("#E,Audio command too soon")); return; }
  lastPlay = millis(); playerCommand(0x12,uint16_t(track)); // /mp3/NNNN.mp3
  reply.println(F("#A,Audio command sent; playback not confirmed"));
#else
  reply.println(F("#E,DFPlayer disabled in this firmware build"));
#endif
}

struct CommandBuffer { char text[40]; uint8_t used = 0; bool overflow = false; };
CommandBuffer usbBuffer;
#if ENABLE_BT
CommandBuffer btBuffer;
#endif
void pollCommands(Stream &input, CommandBuffer &b) {
  uint8_t budget = 32;
  while (input.available() && budget--) {
    char c = input.read();
    if (c=='\r') continue;
    if (c=='\n') {
      if (b.overflow) input.println(F("#E,Command too long"));
      else { b.text[b.used] = 0; handleCommand(b.text,input); }
      b.used=0; b.overflow=false;
    } else if (b.used<sizeof(b.text)-1 && !b.overflow) b.text[b.used++]=c;
    else b.overflow=true;
  }
}

void setup() {
  Serial.begin(115200);
#ifdef ARDUINO_ARCH_ESP32
  Wire.begin(21,22);
  Wire.setTimeOut(30);
  analogReadResolution(12);
  analogSetPinAttenuation(ADC_PIN, ADC_11db);
#if USE_DIRECT_FLEX
  for (uint8_t i=0; i<5; ++i) analogSetPinAttenuation(FLEX_PINS[i],ADC_11db);
#endif
#else
  Wire.begin();
  Wire.setWireTimeout(30000,true);
#endif
  Wire.setClock(100000);
  for (uint8_t i=0; i<4; ++i) { pinMode(MUX_PINS[i],OUTPUT); digitalWrite(MUX_PINS[i],LOW); }
#if ENABLE_BT
#ifdef ARDUINO_ARCH_ESP32
  radio.begin("Group39-Glove");
#else
  radio.begin(9600);
#endif
#endif
#if ENABLE_DFPLAYER
#ifdef ARDUINO_ARCH_ESP32
  player.begin(9600,SERIAL_8N1,16,17);
#else
  player.begin(9600);
#endif
  delay(1500); playerCommand(0x06,20);
#endif
  for (uint8_t h=0; h<GLOVE_HANDS; ++h) {
    imuReady[h] = imus[h].begin(0x68+h,&Wire);
    if (imuReady[h]) {
      imus[h].setAccelerometerRange(MPU6050_RANGE_2_G);
      imus[h].setGyroRange(MPU6050_RANGE_250_DEG);
      imus[h].setFilterBandwidth(MPU6050_BAND_21_HZ);
    }
  }
  Serial.println(F("#I,Group39 glove protocol G1; accel g; gyro degrees/s"));
  Serial.println(F("#I,Missing IMU or failed I2C read clears mask; host refuses recognition"));
}

void loop() {
  pollCommands(Serial,usbBuffer);
#if ENABLE_BT
#ifndef ARDUINO_ARCH_ESP32
  radio.listen();
#endif
  pollCommands(radio,btBuffer);
#endif
  const uint32_t now = millis();
  if (now-lastSample<SAMPLE_PERIOD_MS) return;
  lastSample=now;
  uint8_t mask=0;
  for (uint8_t h=0; h<GLOVE_HANDS; ++h) {
    for (uint8_t i=0; i<5; ++i) readings[h*11+i]=readMux(h*5+i);
    // Read all 14 bytes once, checking the bus result before decoding. This avoids
    // using stale values when a library hides an I2C read failure.
    Wire.beginTransmission(0x68+h); Wire.write(0x3b);
    bool ok = Wire.endTransmission(false)==0;
    if (ok) ok = Wire.requestFrom(uint8_t(0x68+h),uint8_t(14))==14;
    if (imuReady[h] && ok) {
      int16_t raw[7];
      for (uint8_t i=0; i<7; ++i) {
        const uint8_t hi=Wire.read(), lo=Wire.read();
        raw[i]=int16_t((uint16_t(hi)<<8)|lo);
      }
      // Ranges set in setup: +/-2g = 16384 LSB/g; +/-250deg/s = 131 LSB/(deg/s).
      for (uint8_t i=0; i<3; ++i) {
        readings[h*11+5+i]=raw[i]/16384.0f;
        readings[h*11+8+i]=raw[i+4]/131.0f;
      }
      for (uint8_t i=5; i<11; ++i) ok = ok && isfinite(readings[h*11+i]);
      if (ok) mask |= 1 << h;
    } else {
      for (uint8_t i=5; i<11; ++i) readings[h*11+i]=0;
    }
    while (Wire.available()) Wire.read();
  }
  ++sequence;
  emit(Serial,now,mask);
#if ENABLE_BT
  emit(radio,now,mask);
#endif
}
