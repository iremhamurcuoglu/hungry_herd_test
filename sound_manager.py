"""
Sound Manager for Feed the Herd
Generates all sounds programmatically using pure Python - no numpy needed.
Works on desktop AND web (pygbag/emscripten).
"""

import pygame
import math
import struct
import array
import io
import sys
import random

SAMPLE_RATE = 22050  # Lower rate for web compatibility


def _make_sound_from_samples(samples):
    """Convert a list of int16 sample values into a pygame.mixer.Sound via WAV in memory."""
    # Use array module instead of struct.pack(*samples) to avoid arg limit on web
    arr = array.array('h', samples)
    raw = arr.tobytes()
    n = len(samples)
    buf = io.BytesIO()
    data_size = n * 2
    buf.write(b'RIFF')
    buf.write(struct.pack('<I', 36 + data_size))
    buf.write(b'WAVE')
    buf.write(b'fmt ')
    buf.write(struct.pack('<I', 16))
    buf.write(struct.pack('<H', 1))
    buf.write(struct.pack('<H', 1))
    buf.write(struct.pack('<I', SAMPLE_RATE))
    buf.write(struct.pack('<I', SAMPLE_RATE * 2))
    buf.write(struct.pack('<H', 2))
    buf.write(struct.pack('<H', 16))
    buf.write(b'data')
    buf.write(struct.pack('<I', data_size))
    buf.write(raw)
    buf.seek(0)
    return pygame.mixer.Sound(buf)


def _generate_melody(notes, note_duration=0.15, volume=0.25, wave_type="sine"):
    """Generate a melody from a list of (frequency, duration_multiplier) tuples."""
    all_samples = []
    two_pi = 2.0 * math.pi

    for freq, dur_mult in notes:
        dur = note_duration * dur_mult
        n_samples = int(SAMPLE_RATE * dur)

        if freq == 0:
            all_samples.extend([0] * n_samples)
        else:
            attack = min(int(n_samples * 0.05), 500)
            decay = int(n_samples * 0.4)
            for i in range(n_samples):
                t = i / SAMPLE_RATE
                if wave_type == "sine":
                    val = math.sin(two_pi * freq * t)
                elif wave_type == "square":
                    val = 1.0 if math.sin(two_pi * freq * t) >= 0 else -1.0
                elif wave_type == "triangle":
                    phase = (t * freq) % 1.0
                    val = 4.0 * abs(phase - 0.5) - 1.0
                elif wave_type == "sawtooth":
                    phase = (t * freq) % 1.0
                    val = 2.0 * phase - 1.0
                else:
                    val = math.sin(two_pi * freq * t)
                if attack > 0 and i < attack:
                    val *= i / attack
                if decay > 0 and i >= n_samples - decay:
                    val *= (n_samples - i) / decay
                all_samples.append(max(-32767, min(32767, int(val * volume * 32767))))

    return _make_sound_from_samples(all_samples)


def _generate_noise_burst(duration=0.1, volume=0.15):
    """Short noise burst for earthy/dirty sounds."""
    n_samples = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n_samples):
        noise = random.uniform(-1, 1)
        env = (1.0 - i / n_samples) ** 2
        samples.append(max(-32767, min(32767, int(noise * env * volume * 32767))))
    return _make_sound_from_samples(samples)


# Note frequencies
C4 = 261.63; D4 = 293.66; E4 = 329.63; F4 = 349.23
G4 = 392.00; A4 = 440.00; B4 = 493.88
C5 = 523.25; D5 = 587.33; E5 = 659.25; F5 = 698.46
G5 = 783.99; A5 = 880.00


class SoundManager:
    def __init__(self):
        self.enabled = False
        self.music_playing = False
        self.sounds = {}
        self._bg_channel = None
        self._bg_sound = None
        self._bg_volume = 0.15

        try:
            # Re-init mixer at our sample rate for consistent WAV playback
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=1024)
            pygame.mixer.set_num_channels(16)
            self.enabled = True
        except Exception as e:
            print(f"SoundManager mixer init warning: {e}")
            self.enabled = False
            return

        try:
            self._generate_all_sounds()
        except Exception as e:
            print(f"SoundManager sound gen warning: {e}")

        try:
            self._bg_channel = pygame.mixer.Channel(0)
            self._bg_sound = self._generate_background_music()
        except Exception as e:
            print(f"SoundManager music gen warning: {e}")

    def _generate_all_sounds(self):
        self.sounds["plant"] = _generate_melody([(C5, 0.6), (E5, 0.6), (G5, 1.0)], note_duration=0.08, volume=0.25)
        self.sounds["harvest_carrot"] = _generate_melody([(E5, 0.5), (G5, 0.5), (C5, 1.2)], note_duration=0.07, volume=0.3)
        self.sounds["harvest_apple"] = _generate_melody([(G4, 0.8), (C5, 0.5), (E5, 1.0)], note_duration=0.09, volume=0.3)
        self.sounds["feed"] = _generate_melody([(C5, 0.5), (D5, 0.5), (E5, 0.5), (G5, 1.5)], note_duration=0.08, volume=0.3)
        self.sounds["horse_done"] = _generate_melody([(C5, 0.7), (E5, 0.7), (G5, 0.7), (C5*2, 2.0)], note_duration=0.12, volume=0.35)
        self.sounds["poop_spawn"] = _generate_melody([(G4*0.5, 0.8), (E4*0.4, 1.5)], note_duration=0.12, volume=0.2, wave_type="sawtooth")
        self.sounds["poop_collect"] = _generate_noise_burst(duration=0.15, volume=0.2)
        self.sounds["coin"] = _generate_melody([(E5, 0.4), (A5, 1.5)], note_duration=0.06, volume=0.3)
        self.sounds["buy"] = _generate_melody([(A4, 0.5), (C5, 0.5), (E5, 0.5), (A5, 1.0)], note_duration=0.06, volume=0.25)
        self.sounds["shop_open"] = _generate_melody([(C5, 0.8), (G5, 1.2)], note_duration=0.1, volume=0.2)
        self.sounds["shop_close"] = _generate_melody([(G5, 0.8), (C5, 1.2)], note_duration=0.1, volume=0.2)
        self.sounds["trash"] = _generate_melody([(A4, 0.6), (F4, 0.6), (C4, 1.2)], note_duration=0.06, volume=0.2, wave_type="sawtooth")
        self.sounds["level_up"] = _generate_melody([(C5, 1), (E5, 1), (G5, 1), (0, 0.5), (C5, 0.8), (E5, 0.8), (G5, 0.8), (C5*2, 3)], note_duration=0.15, volume=0.4)
        self.sounds["step"] = _generate_noise_burst(duration=0.04, volume=0.05)

    def _generate_background_music(self):
        melody_notes = [
            (C4, 2), (E4, 1), (G4, 1), (E4, 2), (C4, 2),
            (D4, 2), (F4, 1), (A4, 1), (G4, 2), (E4, 2),
            (G4, 2), (A4, 1), (G4, 1), (E4, 2), (D4, 2),
            (C4, 2), (D4, 1), (E4, 1), (C4, 4),
            (E4, 2), (G4, 1), (A4, 1), (G4, 2), (E4, 2),
            (F4, 2), (E4, 1), (D4, 1), (C4, 4),
            (0, 4),
        ]
        return _generate_melody(melody_notes, note_duration=0.22, volume=0.12)

    def play(self, sound_name):
        if not self.enabled:
            return
        snd = self.sounds.get(sound_name)
        if snd:
            snd.play()

    def start_music(self):
        if not self.enabled or not self._bg_channel:
            return
        self._bg_channel.play(self._bg_sound, loops=-1)
        self._bg_channel.set_volume(self._bg_volume)
        self.music_playing = True

    def stop_music(self):
        if self._bg_channel:
            self._bg_channel.stop()
        self.music_playing = False

    def toggle_music(self):
        if self.music_playing:
            self.stop_music()
        else:
            self.start_music()

    def toggle_sfx(self):
        self.enabled = not self.enabled

    def set_music_volume(self, vol: float):
        self._bg_volume = max(0.0, min(1.0, vol))
        if self._bg_channel:
            self._bg_channel.set_volume(self._bg_volume)
