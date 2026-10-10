"""Host simulation of the real Uno sketch; no attached hardware is accessed.

Run: python3 -m unittest discover -s tests -p 'test_uno_levels.py'
Requires g++ for the sketch simulation.
"""
import ast
from pathlib import Path
import re
import subprocess
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]

STUBS = r'''
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
using byte = uint8_t;
using std::isnan;
#define F(x) x
#define _BV(x) (1 << (x))
const int LOW=0, HIGH=1, OUTPUT=1, INPUT_PULLUP=2, BIN=2;
const int A0=14, A1=15, A2=16, A3=17;
const int WDRF=3, WDTO_15MS=0, WDTO_8S=9;
byte MCUSR=0;
unsigned long clockMs=0;
int pins[20]={};
unsigned long millis(){return clockMs;}
void delay(unsigned long ms){clockMs+=ms;}
void pinMode(int,int){}
int digitalRead(int pin){return pins[pin];}
void digitalWrite(int pin,int value){pins[pin]=value;}
void wdt_disable(){}
void wdt_enable(int){}
void wdt_reset(){}
char* dtostrf(double v, signed char, unsigned char decimals, char* out){
    std::sprintf(out,"%.*f",int(decimals),v); return out;
}
struct Console {
    void begin(int){}
    template<class... T> void print(T...){}
    template<class... T> void println(T...){}
    void flush(){}
} Serial;
struct SoftwareSerial : Console { SoftwareSerial(int,int){} };
struct Eeprom {
    byte data[256]={};
    byte read(int addr){return data[addr];}
    void update(int addr,byte value){data[addr]=value;}
} EEPROM;
struct WireStub {void begin(){}} Wire;
struct OneWire {OneWire(int){}};
const int DEVICE_DISCONNECTED_C=-127;
struct DallasTemperature {
    DallasTemperature(OneWire*){}
    void begin(){}
    void setWaitForConversion(bool){}
    void requestTemperatures(){}
    float getTempCByIndex(int){return 20;}
};
struct DateTime {
    int year()const{return 2026;} int month()const{return 10;}
    int day()const{return 8;} int hour()const{return 1;}
    int minute()const{return 0;} int second()const{return 0;}
};
struct RTC_DS3231 {bool begin(){return true;} DateTime now(){return DateTime();}};
'''

SCENARIOS = r'''
void boot(byte saved, bool low=false, bool full=false) {
    EEPROM.data[0]=saved;
    clockMs=0;
    for(int pin=0;pin<20;++pin) pins[pin]=HIGH;
    pins[FLOAT_1]=low?LOW:HIGH;
    pins[FLOAT_2]=full?LOW:HIGH;
    pump1_active=pump2_active=false;
    error_pump1=error_pump2=false;
    pumpSeq=IDLE;
    lastModeReadTime=0;
    setup();
}
void advance(unsigned long ms) {
    for(unsigned long i=0;i<ms;++i) {
        ++clockMs;
        updateFloatInputs(clockMs);
        checkMode();
        updatePumps();
        updatePumpSequence();
    }
}
void assertStopped() {
    assert(!pump1_active && !pump2_active && pumpSeq==IDLE);
    assert(pins[PUMP1_PIN]==LOW && pins[PUMP2_PIN]==LOW);
    assert(!error_pump1 && !error_pump2);
}
int main(int argc,char** argv) {
    assert(argc==2);
    int scenario=std::atoi(argv[1]);
    if(scenario==0) { // Saved high survives reboot between the limits.
        boot(1); assert(modeIndex==1); advance(1000);
        assert(modeIndex==1 && EEPROM.read(0)==1);
        runCycle(); assert(pump2_active && pump2_runMs==PUMP2_HIGH_MODE_MS);
    } else if(scenario==1) { // Startup glitch must not overwrite high mode.
        boot(1,true); assert(modeIndex==1);
        runCycle(); assertStopped();
        advance(100); pins[FLOAT_1]=HIGH; advance(1000);
        assert(modeIndex==1 && EEPROM.read(0)==1);
        runCycle(); assert(pump2_active);
    } else if(scenario==2) { // Full -> middle -> reboot -> low -> middle.
        boot(0,false,true); advance(1000);
        assert(modeIndex==1 && EEPROM.read(0)==1);
        pins[FLOAT_2]=HIGH; advance(1000); assert(modeIndex==1);
        boot(EEPROM.read(0)); advance(1000); assert(modeIndex==1);
        pins[FLOAT_1]=LOW; advance(1000);
        assert(modeIndex==0 && EEPROM.read(0)==0);
        runCycle(); assertStopped();
        pins[FLOAT_1]=HIGH; advance(1000); assertStopped();
        assert(modeIndex==0);
        runCycle(); assert(pump2_active && pump2_runMs==PUMP2_LOW_MODE_MS);
    } else if(scenario==3) { // Low level aborts Pump2 without timeout fault.
        boot(1); advance(1000); runCycle(); assert(pump2_active);
        pins[FLOAT_1]=LOW; advance(1000); assertStopped();
        advance(100000); assertStopped();
        startPumpOutBio(PUMP2_HIGH_MODE_MS);
        startPumpFromSettler(); assertStopped();
    } else if(scenario==4) { // Low level aborts Pump1 without a latched fault.
        boot(1); advance(1000); startPumpFromSettler(); assert(pump1_active);
        pins[FLOAT_1]=LOW; advance(1000); assertStopped();
    } else if(scenario==5) { // Abort waiting sequence, do not resume out of schedule.
        boot(1); advance(1000);
        pins[FLOAT_3]=LOW; advance(1000);
        pumpSeq=PUMP1_WAITING;
        pins[FLOAT_1]=LOW; advance(1000); assertStopped();
        pins[FLOAT_1]=HIGH; pins[FLOAT_3]=HIGH; advance(1000); assertStopped();
    } else if(scenario==6) { // Float4 remains unfiltered; other floats reject pulses.
        boot(1); advance(1000);
        pins[FLOAT_4]=LOW; advance(1); assert(isFloatClosed(3));
        pins[FLOAT_4]=HIGH; advance(1); assert(!isFloatClosed(3));
        for(int pin=FLOAT_1;pin<=FLOAT_3;++pin) {
            pins[pin]=LOW; advance(100);
            assert(!isFloatClosed(pin-FLOAT_1));
            pins[pin]=HIGH; advance(1000);
        }
        assert(modeIndex==1);
    } else if(scenario==7) { // Conflicting levels do not change mode, minimum blocks.
        boot(0,true,true); advance(1000);
        assert(modeIndex==0); runCycle(); assertStopped();
    } else if(scenario==8) { // Saved low and the existing fault interlock survive.
        boot(0); advance(1000); assert(modeIndex==0);
        error_pump2=true; runCycle();
        assert(!pump2_active && error_pump2);
    } else if(scenario==9) { // Existing Pump2 float4 verification still works.
        boot(1); advance(1000); pins[FLOAT_4]=LOW; advance(1);
        runCycle(); advance(10000); pins[FLOAT_4]=HIGH; advance(1);
        assert(pump2Float4OpenedAfterClosed);
        advance(PUMP2_HIGH_MODE_MS);
        assert(!pump2_active && !error_pump2);
    }
}
'''


class UnoLevelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='uno-levels-')
        cls.addClassCleanup(cls.temp.cleanup)
        sketch = (ROOT / 'arduino_cov/uno_vs3_vytezovac/uno_vs3_vytezovac.ino').read_text()
        sketch = re.sub(r'^#include[^\n]*\n', '', sketch, flags=re.M)
        # Arduino generates these declarations before compiling the sketch.
        signatures = re.findall(r'^(?:void|bool|uint8_t) \w+\([^\n]*\) (?=\{)', sketch, re.M)
        source = Path(cls.temp.name) / 'simulation.cpp'
        source.write_text(STUBS + '\n'.join(s + ';' for s in signatures) + sketch + SCENARIOS)
        cls.binary = Path(cls.temp.name) / 'simulation'
        subprocess.run(['g++', '-std=c++11', '-Wall', '-Wextra', str(source),
                        '-o', str(cls.binary)], check=True, capture_output=True, text=True)

    def test_level_and_restart_scenarios(self):
        for scenario in range(10):
            with self.subTest(scenario=scenario):
                subprocess.run([str(self.binary), str(scenario)], check=True,
                               capture_output=True, text=True)


class CovStatusTests(unittest.TestCase):
    def test_levels_are_information_and_actual_faults_remain_errors(self):
        tree = ast.parse((ROOT / 'rpi4/app/gui.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == 'update_system_status')
        namespace = dict(time=types.SimpleNamespace(time=lambda: 100),
                         GREEN_OK='green', RED_ERR='red')
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<status>', 'exec'), namespace)

        class Label(dict):
            def config(self, **kwargs):
                self.update(kwargs)

        for low, full, fault, float3 in ((0, 1, 0, 0), (1, 0, 0, 0),
                                        (0, 1, 1, 0), (0, 1, 0, 1), (0, 0, 0, 0)):
            with self.subTest(low=low, full=full, fault=fault, float3=float3):
                monitoring = types.SimpleNamespace(float1=low, float2=full,
                    float3=float3, error_pump1=False, error_pump2=fault)
                gui = types.SimpleNamespace(state=types.SimpleNamespace(monitoring=monitoring),
                    last_cov_data_ts=100, no_data=False, COV_WATCHDOG_TIMEOUT=30,
                    status_label=Label(), status_reason=Label(),
                    values={'cov_status': Label(), 'cov_reason': Label()})
                namespace['update_system_status'](gui)
                expected = 'ERROR' if fault or float3 else 'OK'
                self.assertEqual(gui.values['cov_status']['text'], expected)
                self.assertEqual(gui.status_label['text'], 'STAV: ' + expected)
                text = gui.status_reason['text']
                self.assertEqual(text, gui.values['cov_reason']['text'])
                if full:
                    self.assertIn('PLOVÁK 2 SEPNUTÝ – NÁDRŽ PLNÁ', text)
                if low:
                    self.assertIn('ČERPÁNÍ BLOKOVÁNO', text)


if __name__ == '__main__':
    unittest.main()
