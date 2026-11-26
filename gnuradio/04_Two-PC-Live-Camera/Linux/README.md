# Live camera video between two PCs — Linux

A Linux port of the `TX/` and `RX/` flowgraphs in this folder (chapter 5 of
[docs/GNU-Radio-Video-Transmission.md](../../../docs/GNU-Radio-Video-Transmission.md)).
The DSP, rates and over-the-air packet format are unchanged, so a Linux end also
works against the original Windows flowgraphs.

```
PC A: camera -> JPEG -> 768-byte CRC packets -> DQPSK (1.024 Msym/s, 4 sps) -> PlutoSky R2-A TX1
                                   ~2 GHz over the air / cable + attenuator
PC B: PlutoSky R2-B RX1 -> PFB clock sync -> CMA equalizer -> Costas -> DQPSK decode
      -> packet CRC + frame reassembly -> live video window
```

## What is different from the Windows flowgraphs

| | Windows (`../TX`, `../RX`) | Linux (this folder) |
|---|---|---|
| Camera | Qt Multimedia | ffmpeg reading V4L2 (`/dev/video0`) when `python3-pyqt5.qtmultimedia` is missing or `--camera-name /dev/videoN` is given; Qt Multimedia otherwise |
| Settings | edit variables in GRC | command-line flags (below), or edit `tx_camera.grc` / `rx_video.grc` in GRC |
| TX attenuation default | 10 dB | **30 dB** |
| TX script | only the `.grc` was provided | `r2_camera_tx.py` generated and ready to run |

## Requirements (both PCs)

Ubuntu 22.04/24.04 packages: `gnuradio` (3.10, includes gr-iio), `libiio-utils`,
`python3-pyqt5`, `python3-yaml`, and on PC A `ffmpeg`.

```
sudo apt install gnuradio libiio-utils python3-pyqt5 python3-yaml ffmpeg
```

Copy this whole `Linux/` folder to both PCs (or clone the repository on both).

## 1. Find each board

On each PC, with its PlutoSky R2 connected over USB:

```
iio_info -s                      # lists the board, e.g. ip:192.168.2.1 or usb:1.5.5
iio_info -u ip:192.168.2.1 | head
```

Each PC talks only to its own board, so both PCs can use `ip:192.168.2.1`.
If both boards are on one LAN instead, give each its own IP and pass that URI.

## 2. Start the receiver on PC B first

```
cd gnuradio/04_Two-PC-Live-Camera/Linux
python3 r2_camera_rx.py --rx-uri ip:192.168.2.1 --rx-gain 35
```

Open the **Live video** tab. The status line shows complete frames, displayed
frames, bad-CRC packets and lost frames. The *RX Gain* slider can be changed live.

## 3. Start the transmitter on PC A

```
cd gnuradio/04_Two-PC-Live-Camera/Linux
python3 r2_camera_tx.py --tx-uri ip:192.168.2.1 --tx-attenuation 30
```

Useful flags:

| Flag | Default | Meaning |
|---|---|---|
| `--freq` | `2.0e9` | carrier, must match on both PCs |
| `--tx-attenuation` | `30` | dB; lower it (e.g. 10–20) only for longer over-the-air distances |
| `--camera-name` | `default` | `default` = `/dev/video0`; or `/dev/videoN` |
| `--source-mode` | `camera` | `test` sends a moving test pattern (no camera needed) |
| `--video-fps` | `10` | target frame rate; the link carries ~10 fps of 640×360 JPEG |
| `--jpeg-quality` | `65` | starting quality; it is lowered automatically to stay under 19 KB/frame |

Start with `--source-mode test` to bring the link up first, then switch to the camera.

**RF levels.** With antennas a metre or two apart, 30 dB TX attenuation and
35 dB RX gain are a reasonable start. If the boards are joined by a cable,
use at least 30 dB of external attenuation (or `--tx-attenuation 60` and
`--rx-gain 10`). Never cable TX straight into RX at low attenuation: it can
overload or damage the receiver. Watch the received spectrum and the Costas
constellation: four tight clusters mean the link is locked.

Stop with the window's close button or Ctrl-C. If the TX script is killed with
`kill -9` it may leave the board transmitting; mute it with
`iio_attr -u ip:192.168.2.1 -c ad9361-phy voltage0 hardwaregain -o -89.75`.

## Test without hardware

```
python3 test_sw_loopback.py                    # moving test pattern, 15 s
python3 test_sw_loopback.py --camera default   # real webcam
python3 test_sw_loopback.py --snr-db 12 --cfo-hz 20e3
```

This runs the real TX and RX video blocks and the same DSP chain over a
simulated channel (AWGN, carrier offset, clock offset). It compares every
received JPEG byte for byte with the frames the TX sent. Results on the
development PC (20 dB SNR, 5 kHz CFO, 20 ppm clock offset, 15 s):

| Source | Sent | Received complete | Byte-exact | Bad CRC |
|---|---|---|---|---|
| test pattern | 151 | 149 | 149/149 | 0 |
| USB webcam (ffmpeg/V4L2) | 143 | 141 | 141/141 | 1 |

The frames not received are the first one or two, before the receiver locks.

## Files

| File | Edit? | Contents |
|---|---|---|
| `src/tx_video_source.py`, `src/rx_video_receiver.py` | yes | Embedded Python blocks (camera, JPEG, packets, player), Linux port |
| `build_flowgraphs.py` | yes | Rebuilds the `.grc` and `.py` files below from `../TX`, `../RX` and `src/` |
| `tx_camera.grc`, `rx_video.grc` | via the build script | GRC flowgraphs; open them in GNU Radio Companion |
| `r2_camera_tx.py`, `r2_camera_rx.py`, `*_epy_block_*.py` | no (generated) | Runnable scripts |
| `test_sw_loopback.py` | — | Test without hardware |

After changing anything in `src/`, run `python3 build_flowgraphs.py`.
