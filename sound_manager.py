"""
Sound Manager for Feed the Herd
Generates all sounds programmatically - no external files needed.
Drop this file next to game.py and integrate with minimal changes.
"""

import pygame
import numpy as np
import math
import struct
import io

SAMPLE_RATE = 44100


def _generate_tone(frequency, duration, volume=0.3, wave_type="sine", fade_out=True):
    """Generate a raw tone as a pygame Sound object."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    if wave_type == "sine":
        wave = np.sin(2 * np.pi * frequency * t)
    elif wave_type == "square":
        wave = np.sign(np.sin(2 * np.pi * frequency * t))
    elif wave_type == "triangle":
        wave = 2 * np.abs(2 * (t * frequency - np.floor(t * frequency + 0.5))) - 1
    elif wave_type == "sawtooth":
        wave = 2 * (t * frequency - np.floor(t * frequency + 0.5))
    else:
        wave = np.sin(2 * np.pi * frequency * t)

    if fade_out:
        fade_len = int(n_samples * 0.3)
        if fade_len > 0:
            fade = np.linspace(1.0, 0.0, fade_len)
            wave[-fade_len:] *= fade

    # Fade in to avoid click
    fade_in_len = min(int(n_samples * 0.02), 200)
    if fade_in_len > 0:
        wave[:fade_in_len] *= np.linspace(0.0, 1.0, fade_in_len)

    wave = (wave * volume * 32767).astype(np.int16)
    stereo = np.column_stack((wave, wave))
    return pygame.sndarray.make_sound(stereo)


def _generate_melody(notes, note_duration=0.15, volume=0.25, wave_type="sine"):
    """Generate a melody from a list of (frequency, duration_multiplier) tuples."""
    all_samples = np.array([], dtype=np.int16)

    for freq, dur_mult in notes:
        dur = note_duration * dur_mult
        n_samples = int(SAMPLE_RATE * dur)
        t = np.linspace(0, dur, n_samples, endpoint=False)

        if freq == 0:  # Rest
            wave = np.zeros(n_samples)
        else:
            wave = np.sin(2 * np.pi * freq * t)
            # Envelope
            attack = min(int(n_samples * 0.05), 500)
            decay = int(n_samples * 0.4)
            if attack > 0:
                wave[:attack] *= np.linspace(0, 1, attack)
            if decay > 0:
                wave[-decay:] *= np.linspace(1, 0, decay)

        samples = (wave * volume * 32767).astype(np.int16)
        all_samples = np.concatenate((all_samples, samples))

    stereo = np.column_stack((all_samples, all_samples))
    return pygame.sndarray.make_sound(stereo)


def _generate_noise_burst(duration=0.1, volume=0.15):
    """Short noise burst for earthy/dirty sounds."""
    n_samples = int(SAMPLE_RATE * duration)
    noise = np.random.uniform(-1, 1, n_samples)
    # Low-pass filter (simple moving average)
    kernel_size = 20
    kernel = np.ones(kernel_size) / kernel_size
    noise = np.convolve(noise, kernel, mode='same')
    # Envelope
    env = np.linspace(1, 0, n_samples) ** 2
    noise *= env
    samples = (noise * volume * 32767).astype(np.int16)
    stereo = np.column_stack((samples, samples))
    return pygame.sndarray.make_sound(stereo)


# ──────────────────────────────────────────────
#  Note frequencies (octave 4-5)
# ──────────────────────────────────────────────
C4 = 261.63; D4 = 293.66; E4 = 329.63; F4 = 349.23
G4 = 392.00; A4 = 440.00; B4 = 493.88
C5 = 523.25; D5 = 587.33; E5 = 659.25; F5 = 698.46
G5 = 783.99; A5 = 880.00


class SoundManager:
    """
    Manages all game sounds. Call play_*() methods from your game code.
    """

    def __init__(self):
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=512)
        pygame.mixer.set_num_channels(16)

        self.enabled = True
        self.music_playing = False

        # ── Sound Effects ──
        self.sounds = {}
        self._generate_all_sounds()

        # ── Background Music ──
        self._bg_channel = pygame.mixer.Channel(0)
        self._bg_sound = self._generate_background_music()
        self._bg_volume = 0.15

    def _generate_all_sounds(self):
        """Pre-generate all sound effects."""

        # 🌱 PLANTING - soft ascending notes
        self.sounds["plant"] = _generate_melody([
            (C5, 0.6), (E5, 0.6), (G5, 1.0)
        ], note_duration=0.08, volume=0.25, wave_type="sine")

        # 🥕 HARVEST CARROT - cheerful pluck
        self.sounds["harvest_carrot"] = _generate_melody([
            (E5, 0.5), (G5, 0.5), (C5, 1.2)
        ], note_duration=0.07, volume=0.3, wave_type="triangle")

        # 🍎 HARVEST APPLE - deeper, rounder pop
        self.sounds["harvest_apple"] = _generate_melody([
            (G4, 0.8), (C5, 0.5), (E5, 1.0)
        ], note_duration=0.09, volume=0.3, wave_type="sine")

        # 🐴 FEED HORSE - happy ascending jingle
        self.sounds["feed"] = _generate_melody([
            (C5, 0.5), (D5, 0.5), (E5, 0.5), (G5, 1.5)
        ], note_duration=0.08, volume=0.3, wave_type="sine")

        # 🐴✅ HORSE FINISHED (all items given) - triumphant fanfare
        self.sounds["horse_done"] = _generate_melody([
            (C5, 0.7), (E5, 0.7), (G5, 0.7), (C5 * 2, 2.0)
        ], note_duration=0.12, volume=0.35, wave_type="sine")

        # 💩 POOP SPAWN - funny low blurp
        self.sounds["poop_spawn"] = _generate_melody([
            (G4 * 0.5, 0.8), (E4 * 0.4, 1.5)
        ], note_duration=0.12, volume=0.2, wave_type="sawtooth")

        # 💩 POOP COLLECT - squelchy noise
        self.sounds["poop_collect"] = _generate_noise_burst(duration=0.15, volume=0.2)

        # 💰 COIN / SELL POOP - classic coin ding
        self.sounds["coin"] = _generate_melody([
            (E5, 0.4), (A5, 1.5)
        ], note_duration=0.06, volume=0.3, wave_type="sine")

        # 🛒 BUY ITEM - cash register feel
        self.sounds["buy"] = _generate_melody([
            (A4, 0.5), (C5, 0.5), (E5, 0.5), (A5, 1.0)
        ], note_duration=0.06, volume=0.25, wave_type="triangle")

        # 🛒 SHOP OPEN
        self.sounds["shop_open"] = _generate_melody([
            (C5, 0.8), (G5, 1.2)
        ], note_duration=0.1, volume=0.2, wave_type="sine")

        # 🛒 SHOP CLOSE
        self.sounds["shop_close"] = _generate_melody([
            (G5, 0.8), (C5, 1.2)
        ], note_duration=0.1, volume=0.2, wave_type="sine")

        # 🗑️ TRASH - woosh down
        self.sounds["trash"] = _generate_melody([
            (A4, 0.6), (F4, 0.6), (C4, 1.2)
        ], note_duration=0.06, volume=0.2, wave_type="sawtooth")

        # ⬆️ LEVEL UP - grand ascending fanfare
        self.sounds["level_up"] = _generate_melody([
            (C5, 1), (E5, 1), (G5, 1), (0, 0.5),
            (C5, 0.8), (E5, 0.8), (G5, 0.8), (C5 * 2, 3)
        ], note_duration=0.15, volume=0.4, wave_type="sine")

        # 👟 FOOTSTEP - very subtle soft tap (optional)
        self.sounds["step"] = _generate_noise_burst(duration=0.04, volume=0.05)

    def _generate_background_music(self):
        """Generate a calm, looping farm melody."""
        # Pastoral melody ~ 8 bars
        melody_notes = [
            # Bar 1-2: Gentle intro
            (C4, 2), (E4, 1), (G4, 1), (E4, 2), (C4, 2),
            # Bar 3-4: Rising phrase
            (D4, 2), (F4, 1), (A4, 1), (G4, 2), (E4, 2),
            # Bar 5-6: Peak
            (G4, 2), (A4, 1), (G4, 1), (E4, 2), (D4, 2),
            # Bar 7-8: Resolution
            (C4, 2), (D4, 1), (E4, 1), (C4, 4),
            # Bar 9-10: Variation
            (E4, 2), (G4, 1), (A4, 1), (G4, 2), (E4, 2),
            # Bar 11-12: Calm ending
            (F4, 2), (E4, 1), (D4, 1), (C4, 4),
            # Rest before loop
            (0, 4),
        ]
        return _generate_melody(melody_notes, note_duration=0.22, volume=0.12, wave_type="sine")

    # ──────────────────────────────────────────────
    #  Public API - Call these from game.py
    # ──────────────────────────────────────────────

    def play(self, sound_name):
        """Play a named sound effect."""
        if not self.enabled:
            return
        snd = self.sounds.get(sound_name)
        if snd:
            snd.play()

    def start_music(self):
        """Start background music loop."""
        if not self.enabled:
            return
        self._bg_channel.play(self._bg_sound, loops=-1)
        self._bg_channel.set_volume(self._bg_volume)
        self.music_playing = True

    def stop_music(self):
        """Stop background music."""
        self._bg_channel.stop()
        self.music_playing = False

    def toggle_music(self):
        """Toggle background music on/off."""
        if self.music_playing:
            self.stop_music()
        else:
            self.start_music()

    def toggle_sfx(self):
        """Toggle all sound effects on/off."""
        self.enabled = not self.enabled

    def set_music_volume(self, vol: float):
        """Set background music volume (0.0 - 1.0)."""
        self._bg_volume = max(0.0, min(1.0, vol))
        self._bg_channel.set_volume(self._bg_volume)
