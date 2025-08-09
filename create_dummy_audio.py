import wave
import numpy as np

# Parameters
duration = 1  # seconds
sample_rate = 16000
n_samples = int(duration * sample_rate)

# Create silent audio data
audio_data = np.zeros(n_samples, dtype=np.int16)

# Write to a WAV file
with wave.open('dummy_audio.wav', 'w') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)  # 16-bit
    wf.setframerate(sample_rate)
    wf.writeframes(audio_data.tobytes())

print("dummy_audio.wav created.")
