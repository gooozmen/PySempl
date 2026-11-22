import librosa
import numpy as np
import sounddevice as sd
import pedalboard


PAD_COUNT = 8
SAMPLE_RATE = 44100
SCOPE_SIZE = 2048


class AudioEngine:
    def __init__(self, sample_rate=SAMPLE_RATE, pad_count=PAD_COUNT):
        self.sample_rate = sample_rate
        self.pad_count = pad_count

        self.y = None
        self.sr = None
        self.splited_parts = []

        self.volume = 0.5
        self.dry_sounds = [None] * pad_count
        self.sounds = [None] * pad_count
        self.play_positions = [0] * pad_count
        self.playing = [False] * pad_count
        self.parts_ready = False
        self.stream = None
        self.effects = [self._default_effects() for _ in range(pad_count)]
        # кольцевой буфер последних сэмплов выхода - для визуализатора
        self.scope = np.zeros(SCOPE_SIZE, dtype=np.float32)

    def _default_effects(self):
        return {
            "distortion": False,
            "distortion_level": 0.5,
            "reverb": False,
            "reverb_level": 0.3,
        }

    def load(self, file_path):
        self.y, self.sr = librosa.load(file_path, sr=self.sample_rate, mono=True)

        return self.y, self.sr

    def split(self):
        if self.y is None or self.sr is None:
            return False

        self.stop_all()
        self.splited_parts = []
        self.parts_ready = False

        one_part_long = len(self.y) / self.sr / self.pad_count

        for i in range(self.pad_count):
            start = int(self.sr * one_part_long * i)
            end = int(self.sr * one_part_long * (i + 1))
            part = self.y[start:end]
            self.splited_parts.append(part)

            dry = np.column_stack((part, part)).astype(np.float32)
            self.dry_sounds[i] = dry
            self.sounds[i] = dry
            self.play_positions[i] = 0
            self.effects[i] = self._default_effects()

        self.parts_ready = True
        return True

    def apply_effects(self, target=None, distortion=False, distortion_level=0.0,
                      reverb=False, reverb_level=0.0):
        if not self.parts_ready:
            return

        self.stop_all()

        if target is None:
            pads = range(self.pad_count)
        else:
            pads = [target]

        for i in pads:
            dry = self.dry_sounds[i]
            if dry is None:
                continue

            samples = dry
            if distortion:
                samples = self._apply_distortion(samples, distortion_level)
            if reverb:
                samples = self._apply_reverb(samples, reverb_level)

            self.sounds[i] = np.clip(samples, -1.0, 1.0)
            self.effects[i] = {
                "distortion": distortion,
                "distortion_level": distortion_level,
                "reverb": reverb,
                "reverb_level": reverb_level,
            }

    def _apply_distortion(self, samples, level):
        effect = pedalboard.Distortion(drive_db=level * 24)
        return effect(samples.T, self.sample_rate).T

    def _apply_reverb(self, samples, level):
        effect = pedalboard.Reverb(
            room_size=0.6,
            wet_level=level,
            dry_level=1.0 - level,
        )
        return effect(samples.T, self.sample_rate).T

    def set_volume(self, volume):
        self.volume = min(max(volume, 0.0), 1.0)

    def play(self, index, polyphonic=False):
        if not self.parts_ready or not (0 <= index < self.pad_count):
            print("Нет нарезанных звуков")
            return
        if self.sounds[index] is None:
            print("Нет нарезанных звуков")
            return

        if not polyphonic:
            self.stop_all()

        if not self._ensure_stream():
            return

        self.play_positions[index] = 0
        self.playing[index] = True

    def stop_all(self):
        for i in range(self.pad_count):
            self.playing[i] = False
            self.play_positions[i] = 0

    def _ensure_stream(self):
        if self.stream is not None:
            return True

        try:
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=2,
                dtype='float32',
                callback=self._audio_callback,
            )
            self.stream.start()
        except Exception as e:
            print(f"Ошибка аудио: {e}")
            self.stream = None
            return False

        return True

    def _audio_callback(self, outdata, frames, time_info, status):
        outdata.fill(0)
        volume = self.volume

        for i in range(self.pad_count):
            if not self.playing[i]:
                continue

            data = self.sounds[i]
            if data is None:
                self.playing[i] = False
                continue

            pos = self.play_positions[i]
            chunk = data[pos:pos + frames]
            count = len(chunk)
            if count:
                outdata[:count] += chunk * volume
                self.play_positions[i] = pos + count

            if count < frames:
                self.playing[i] = False
                self.play_positions[i] = 0

        np.clip(outdata, -1.0, 1.0, out=outdata)
        self._push_scope(outdata)

    def _push_scope(self, outdata):
        mono = outdata.mean(axis=1)
        n = len(mono)
        if n >= SCOPE_SIZE:
            self.scope[:] = mono[-SCOPE_SIZE:]
        else:
            self.scope[:-n] = self.scope[n:]
            self.scope[-n:] = mono

    def close(self):
        self.stop_all()
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
