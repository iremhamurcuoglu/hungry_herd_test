"""
Sound Manager for Feed the Herd
Pure Python sound generation - works on desktop AND web (pygbag/emscripten).
Web audio fix: file-based loading + audio unlock on first user gesture.
"""

import pygame
import math
import struct
import array
import io
import sys
import os
import random

IS_WEB = sys.platform == "emscripten"
SAMPLE_RATE = 22050

# Note frequencies
C4=261.63; D4=293.66; E4=329.63; F4=349.23
G4=392.00; A4=440.00; B4=493.88
C5=523.25; D5=587.33; E5=659.25; F5=698.46
G5=783.99; A5=880.00


def _make_wav_bytes(samples):
    """Build WAV bytes from int16 sample list."""
    arr = array.array('h', samples)
    raw = arr.tobytes()
    n = len(samples)
    ds = n * 2
    buf = io.BytesIO()
    buf.write(b'RIFF')
    buf.write(struct.pack('<I', 36 + ds))
    buf.write(b'WAVE')
    buf.write(b'fmt ')
    buf.write(struct.pack('<IHHIIHH', 16, 1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16))
    buf.write(b'data')
    buf.write(struct.pack('<I', ds))
    buf.write(raw)
    return buf.getvalue()


_snd_counter = 0

def _make_sound(samples):
    """Build a pygame Sound from int16 sample list.
    Writes a real WAV file then loads it - most reliable on all platforms."""
    global _snd_counter
    _snd_counter += 1
    wav_data = _make_wav_bytes(samples)
    fname = f"_sfx_{_snd_counter}.wav"
    try:
        with open(fname, "wb") as f:
            f.write(wav_data)
        snd = pygame.mixer.Sound(fname)
        if not IS_WEB:
            try:
                os.remove(fname)
            except Exception:
                pass
        return snd
    except Exception as e:
        print(f"Sound create error: {e}")
        # Fallback: try BytesIO (works on desktop)
        try:
            return pygame.mixer.Sound(io.BytesIO(wav_data))
        except Exception:
            pass
    return None


def _tone(freq, dur, vol=0.3):
    """Generate a simple sine tone."""
    n = int(SAMPLE_RATE * dur)
    tp = 2.0 * math.pi * freq / SAMPLE_RATE
    v = int(vol * 32767)
    out = []
    for i in range(n):
        s = math.sin(tp * i)
        # fade in/out
        if i < 200:
            s *= i / 200.0
        elif i > n - 200:
            s *= (n - i) / 200.0
        out.append(max(-32767, min(32767, int(s * v))))
    return _make_sound(out)


def _melody(notes, nd=0.15, vol=0.25):
    """Melody from [(freq, dur_mult), ...] tuples."""
    out = []
    tp_base = 2.0 * math.pi / SAMPLE_RATE
    v = int(vol * 32767)
    for freq, dm in notes:
        n = int(SAMPLE_RATE * nd * dm)
        if freq == 0:
            out.extend([0] * n)
        else:
            tp = tp_base * freq
            decay_start = int(n * 0.6)
            for i in range(n):
                s = math.sin(tp * i)
                if i < 80:
                    s *= i / 80.0
                if i >= decay_start:
                    s *= (n - i) / (n - decay_start)
                out.append(max(-32767, min(32767, int(s * v))))
    return _make_sound(out)


def _noise(dur=0.1, vol=0.15):
    """Noise burst."""
    n = int(SAMPLE_RATE * dur)
    v = int(vol * 32767)
    out = []
    for i in range(n):
        env = (1.0 - i / n) ** 2
        out.append(max(-32767, min(32767, int(random.uniform(-1, 1) * env * v))))
    return _make_sound(out)


# Sound effect definitions (lazy - generated on first access)
_SOUND_DEFS = {
    "plant":          lambda: _melody([(C5,.6),(E5,.6),(G5,1)], nd=.08, vol=.25),
    "harvest_carrot": lambda: _melody([(E5,.5),(G5,.5),(C5,1.2)], nd=.07, vol=.3),
    "harvest_apple":  lambda: _melody([(G4,.8),(C5,.5),(E5,1)], nd=.09, vol=.3),
    "feed":           lambda: _melody([(C5,.5),(D5,.5),(E5,.5),(G5,1.5)], nd=.08, vol=.3),
    "horse_done":     lambda: _melody([(C5,.7),(E5,.7),(G5,.7),(C5*2,2)], nd=.12, vol=.35),
    "poop_spawn":     lambda: _tone(G4*0.5, 0.2, 0.15),
    "poop_collect":   lambda: _noise(dur=.12, vol=.18),
    "coin":           lambda: _melody([(E5,.4),(A5,1.5)], nd=.06, vol=.3),
    "buy":            lambda: _melody([(A4,.5),(C5,.5),(E5,.5),(A5,1)], nd=.06, vol=.25),
    "shop_open":      lambda: _melody([(C5,.8),(G5,1.2)], nd=.1, vol=.2),
    "shop_close":     lambda: _melody([(G5,.8),(C5,1.2)], nd=.1, vol=.2),
    "trash":          lambda: _tone(200, 0.15, 0.2),
    "level_up":       lambda: _melody([(C5,1),(E5,1),(G5,1),(0,.5),(C5,.8),(E5,.8),(G5,.8),(C5*2,3)], nd=.12, vol=.35),
    "step":           lambda: _noise(dur=.03, vol=.04),
}

# Shorter music for web
_MUSIC_NOTES = [
    (C4,2),(E4,1),(G4,1),(E4,2),(C4,2),
    (D4,2),(F4,1),(A4,1),(G4,2),(E4,2),
    (C4,2),(D4,1),(E4,1),(C4,4),
    (0,2),
]


class SoundManager:
    def __init__(self):
        self.enabled = False
        self.music_playing = False
        self._sounds = {}
        self._bg_channel = None
        self._bg_sound = None
        self._bg_volume = 0.20
        self._audio_unlocked = not IS_WEB  # Desktop: unlocked immediately
        self._pending_music = False

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=1024)
            pygame.mixer.set_num_channels(8)
            self._bg_channel = pygame.mixer.Channel(0)
            self.enabled = True
            print(f"SoundManager OK: mixer={pygame.mixer.get_init()}")
        except Exception as e:
            print(f"SoundManager init warning: {e}")
            self.enabled = False

    def unlock_audio(self):
        """Call on first user interaction (key/click) to unlock web AudioContext.
        Browsers block audio until a user gesture occurs."""
        if self._audio_unlocked:
            return
        self._audio_unlocked = True
        print("Audio unlocked by user gesture")
        try:
            silent = [0] * 1024
            snd = _make_sound(silent)
            if snd:
                snd.play()
        except Exception as e:
            print(f"Audio unlock error: {e}")
        if self._pending_music:
            self._pending_music = False
            self.start_music()

    def _get_sound(self, name):
        """Lazy-generate a sound on first use."""
        if name not in self._sounds:
            gen = _SOUND_DEFS.get(name)
            if gen:
                try:
                    self._sounds[name] = gen()
                except Exception as e:
                    print(f"Sound gen error ({name}): {e}")
                    self._sounds[name] = None
            else:
                self._sounds[name] = None
        return self._sounds[name]

    def _ensure_music(self):
        """Lazy-generate background music."""
        if self._bg_sound is None:
            try:
                self._bg_sound = _melody(_MUSIC_NOTES, nd=0.2, vol=0.10)
            except Exception as e:
                print(f"Music gen error: {e}")

    def play(self, sound_name):
        if not self.enabled or not self._audio_unlocked:
            return
        try:
            snd = self._get_sound(sound_name)
            if snd:
                snd.play()
        except Exception:
            pass

    def start_music(self):
        if not self.enabled or not self._bg_channel:
            return
        if not self._audio_unlocked:
            self._pending_music = True
            return
        try:
            self._ensure_music()
            if self._bg_sound:
                self._bg_channel.play(self._bg_sound, loops=-1)
                self._bg_channel.set_volume(self._bg_volume)
                self.music_playing = True
        except Exception as e:
            print(f"Music play error: {e}")

    def stop_music(self):
        try:
            if self._bg_channel:
                self._bg_channel.stop()
        except Exception:
            pass
        self.music_playing = False
        self._pending_music = False

    def toggle_music(self):
        if self.music_playing:
            self.stop_music()
        else:
            self.start_music()

    def toggle_sfx(self):
        self.enabled = not self.enabled

    def set_music_volume(self, vol):
        self._bg_volume = max(0.0, min(1.0, vol))
        try:
            if self._bg_channel:
                self._bg_channel.set_volume(self._bg_volume)
        except Exception:
            pass
