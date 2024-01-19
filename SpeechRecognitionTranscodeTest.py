#!/usr/bin/env python3

# prerequisites: as described in https://alphacephei.com/vosk/install and also python module `sounddevice` (simply run command `pip install sounddevice`)
# Example usage using Dutch (nl) recognition model: `python test_microphone.py -m nl`
# For more help run: `python test_microphone.py -h`

import time
import os
import argparse
import queue
import sys
import sounddevice as sd
import json
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *

from vosk import Model, KaldiRecognizer

class WorkerSignals(QObject):
    result = pyqtSignal(object)

class Transcribe(QRunnable):
    def init(self):
        self.location = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
        self.signals = WorkerSignals()
    
    def build(self):
        self.signals.result.emit("loading model")
        self.q = queue.Queue()
    
        self.parser = argparse.ArgumentParser(add_help=False)
        self.parser.add_argument(
            "-l", "--list-devices", action="store_true",
            help="show list of audio devices and exit")
        self.args, remaining = self.parser.parse_known_args()
        if self.args.list_devices:
            print(sd.query_devices())
            self.parser.exit(0)
        parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            parents=[self.parser])
        self.parser.add_argument(
            "-f", "--filename", type=str, metavar="FILENAME",
            help="audio file to store recording to")
        self.parser.add_argument(
            "-d", "--device", type=self.int_or_str,
            help="input device (numeric ID or substring)")
        self.parser.add_argument(
            "-r", "--samplerate", type=int, help="sampling rate")
        self.parser.add_argument(
            "-m", "--model", type=str, help="language model; e.g. en-us, fr, nl; default is en-us")
        self.args = self.parser.parse_args(remaining)
        
        if self.args.samplerate is None:
                device_info = sd.query_devices(self.args.device, "input")
                # soundfile expects an int, sounddevice provides a float:
                self.args.samplerate = int(device_info["default_samplerate"])
        if self.args.model is None:
            #self.model = Model(lang="en-us")
            self.model = Model(os.path.join(self.location, 'vosk-model-en-us-0.42-gigaspeech'))
            #self.model = Model(os.path.join(self.location, 'vosk-model-small-en-us-0.15'))
        else:
            self.model = Model(lang=self.args.model)
        if self.args.filename:
            self.dump_fn = open(self.args.filename, "wb")
        else:
            self.dump_fn = None
        self.signals.result.emit("loaded model")
        time.sleep(1)

    @pyqtSlot()
    def run(self):
        self.build()
        try:
            with sd.RawInputStream(samplerate=self.args.samplerate, blocksize = 8000, device=self.args.device,
                    dtype="int16", channels=1, callback=self.callback):
                print("#" * 80)
                print("Press Ctrl+C to stop the recording")
                print("#" * 80)

                rec = KaldiRecognizer(self.model, self.args.samplerate)
                while True:
                    data = self.q.get()
                    if rec.AcceptWaveform(data):
                        rec = KaldiRecognizer(self.model, self.args.samplerate)
                        """
                        text = json.loads(rec.Result())["text"]
                        text = ' '.join(text.split(' ')[-8:])
                        self.signals.result.emit(text)
                        """
                    else:
                        print(rec.PartialResult())
                        text = json.loads(rec.PartialResult())["partial"]
                        text = text.split(' ')[-10:]
                        text = ' '.join(text[-5:])
                        self.signals.result.emit(text)
                        
                    if self.dump_fn is not None:
                        self.dump_fn.write(data)

        except KeyboardInterrupt:
            print("\nDone")
            self.parser.exit(0)
        except Exception as e:
            self.parser.exit(type(e).__name__ + ": " + str(e))

    def int_or_str(text):
        """Helper function for argument parsing."""
        try:
            return int(text)
        except ValueError:
            return text

    def callback(self, indata, frames, time, status):
        """This is called (from a separate thread) for each audio block."""
        if status:
            print(status, file=sys.stderr)
        self.q.put(bytes(indata))

class MainWindow(QMainWindow):


    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("""
QMainWindow {background-color: black}
QLabel {font: helvetica; font-size: 30pt; font-weight: bold; color: white; }
""")
        
        layout = QVBoxLayout()

        self.l = QLabel("Start")
        #b = QPushButton("DANGER!")
        #b.pressed.connect(self)

        layout.addWidget(self.l)
        #layout.addWidget(b)

        w = QWidget()
        w.setLayout(layout)

        self.setCentralWidget(w)

        transcribe = Transcribe()
        transcribe.init()
        
        transcribe.signals.result.connect(self.update_label)
        self.threadpool = QThreadPool()
        print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())

        self.threadpool.start(transcribe)
        
        self.show()

    def update_label(self, s):
        self.resize(0,0)
        self.l.setText(s)

    def mousePressEvent(self, event):
        self.dragPos = event.globalPosition().toPoint()


    def mouseMoveEvent(self, event):
         self.move(self.pos() + event.globalPosition().toPoint() - self.dragPos )
         self.dragPos = event.globalPosition().toPoint()
         event.accept()
         
if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    app.exec()
    
    #transcribe.run()
