import pyaudio
import struct

#Configuration Options
FS = 48000 #Sample Rate, Try 16000, 32000, 96000, 192000
FRAME_SIZE = 2048 #Try powers of two in the 256-8192 range
IDEAL_FREQ = 255.0 #ish, will be adjusted later
VOLUME = 0.1 #more is louder
CHANNELS = 1 #one or two please

class Stream():
    def __init__(self):
        self.last_level = 0
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paFloat32,
                            channels=CHANNELS,
                            rate=FS,
                            input=True,
                            stream_callback=self.callback,
                            frames_per_buffer=FRAME_SIZE)
        self.stream.start_stream()
        self.last_reported = 0

    def kill(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

    # define callback
    def callback(self, in_data, frame_count, time_info, status):
        data = in_data
        in_data = struct.unpack( "f"*frame_count*CHANNELS, in_data )
        self.last_reported=max(in_data)
        return (data, pyaudio.paContinue)
    
    def query(self):
        return self.last_reported
