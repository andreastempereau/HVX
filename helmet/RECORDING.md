# Full Recording System

The helmet now supports **full experience recording** that captures:
- ✅ **Video**: Complete display output including camera feed + all QML widgets/overlays
- ✅ **Audio**: Microphone input (your voice)
- ✅ **Muxing**: Synchronized audio/video in a single MP4 file

## What Gets Recorded

When you start a recording, it captures:

### Video (30 FPS)
- Front camera feed
- All HUD elements (FPS, battery, temperature, etc.)
- Rear camera mirror
- Orientation crosshair
- Detection overlays
- Captions
- Any other visible widgets

The recording shows **exactly what you see** on the helmet display.

### Audio (48kHz, mono)
- Microphone input (lavalier mic, device index 4)
- Your voice as you speak
- Ambient sounds picked up by the mic

**Note**: Speaker output (assistant responses) is NOT currently captured. Only microphone input.

## How to Use

### Via Voice Commands (Recommended)

1. **Start Recording**:
   - Say: *"Hey Jarvis, start recording"*
   - Or: *"Hey Jarvis, record video"*
   - Or: *"Hey Jarvis, start recording for 30 seconds"* (timed recording)

2. **Stop Recording**:
   - Say: *"Hey Jarvis, stop recording"*
   - Or: *"Hey Jarvis, end recording"*

3. **Check Status**:
   - Say: *"Hey Jarvis, are you recording?"*
   - Or: *"Hey Jarvis, recording status"*

### Via Python API

```python
# In your code
from full_recorder import FullRecorder

# Initialize
recorder = FullRecorder(
    output_dir="recordings",
    fps=30,
    mic_device_index=4,  # Lavalier mic
    enable_audio=True
)

# Start recording (unlimited duration)
filename = recorder.start_recording()

# Or start with time limit
filename = recorder.start_recording(duration_seconds=30)

# Stop recording
saved_path = recorder.stop_recording()

# Check status
info = recorder.get_recording_info()
print(f"Recording: {info['recording']}")
print(f"Duration: {info['duration']}s")
print(f"Frames: {info['frames']}")
```

## Output Files

Recordings are saved to: `/home/hvx/HVX/helmet/recordings/`

Format: `helmet_full_YYYYMMDD_HHMMSS.mp4`

Example: `helmet_full_20251009_143052.mp4`

## Technical Details

### Architecture

1. **Video Pipeline**:
   - QML window captured at 30 FPS using `grabWindow()`
   - Frames piped to ffmpeg via stdin
   - Encoded to H.264 with ultrafast preset (optimized for Jetson)
   - Saved to temporary `.h264` file

2. **Audio Pipeline**:
   - PyAudio captures mic input at 48kHz
   - Saved to temporary `.wav` file
   - Runs in parallel with video capture

3. **Muxing**:
   - After recording stops, ffmpeg muxes video + audio
   - Audio encoded to AAC 128kbps
   - Final output: MP4 with H.264 video + AAC audio
   - Temporary files cleaned up automatically

### Performance

- **CPU Impact**: ~15-20% increase during recording (ffmpeg encoding)
- **Storage**: ~10-15 MB per minute (1920x1080 @ 30fps, CRF 23)
- **Latency**: No perceptible impact on helmet operation

### Dependencies

Required packages (already installed):
- `opencv-python` (cv2)
- `pyaudio`
- `numpy`
- `ffmpeg` (system package)

## Configuration

Edit `configs/profiles/dev.json`:

```json
{
  "system": {
    "recording_dir": "recordings"  // Output directory
  },
  "assistant": {
    "input_device_index": 4  // Microphone for audio recording
  }
}
```

## Troubleshooting

### No Audio in Recording
- Check mic device index: `python3 -m pyaudio` to list devices
- Update `assistant.input_device_index` in config
- Verify mic is not in use by another process

### Video is Choppy
- Reduce recording FPS (edit `fps=30` to `fps=20` in `full_recorder.py`)
- Increase ffmpeg CRF value (23 → 28) for faster encoding
- Close other CPU-intensive processes

### File Size Too Large
- Increase CRF value in `full_recorder.py` (23 → 28, lower quality)
- Reduce FPS (30 → 20)
- Reduce resolution (would require QML changes)

### Recording Failed to Start
- Check disk space: `df -h`
- Check ffmpeg is installed: `which ffmpeg`
- Check logs in `logs/visor-ui.log`

## Future Enhancements

Planned features:
- [ ] Speaker output capture (loopback recording)
- [ ] Adjustable recording quality profiles (high/medium/low)
- [ ] Real-time recording indicator on HUD
- [ ] Automatic recording triggers (low battery, high temp, etc.)
- [ ] Cloud upload support
- [ ] Thumbnail generation for recordings

## Examples

Watch example recordings:
```bash
# Play with mpv
mpv recordings/helmet_full_20251009_143052.mp4

# Play with VLC
vlc recordings/helmet_full_20251009_143052.mp4

# List all recordings
ls -lh recordings/
```

## Safety Notes

⚠️ **Important**:
- Recordings consume disk space - monitor available storage
- Long recordings can use significant power
- Recording does NOT pause/stop automatically on low battery
- Always verify recording stopped before removing power
