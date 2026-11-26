# PlutoSky VTX — live camera video between two PCs (Linux / Pop!_OS)

This folder has everything needed to send **live camera video** from one PC to
another over radio, using **two PlutoSky (PlutoSDR-compatible) boards**. Follow
the steps below in order on a fresh Pop!_OS 24.04 (or Ubuntu 24.04) PC; no
other document is needed.

```
 PC A  (TRANSMITTER)                                   PC B  (RECEIVER)
 webcam ─► run_tx.sh ─► Pluto A ──TX1 antenna~~~ 2 GHz ~~~RX1 antenna── Pluto B ─► run_rx.sh ─► video window
```

- **PC A** has the webcam and Pluto A. It runs `./run_tx.sh`.
- **PC B** has Pluto B. It runs `./run_rx.sh` and shows the video.
- Each PC talks only to its own Pluto over USB. The PCs do not need to be on the
  same network.

---

## What you need

| Item | PC A (transmitter) | PC B (receiver) |
|---|---|---|
| PC with Pop!_OS 24.04 and internet (for the one-time setup) | ✔ | ✔ |
| PlutoSky board + USB cable (to the board's **USB2.0/OTG** port, not DEBUG) | Pluto A | Pluto B |
| Antenna for ~2 GHz | on **TX1** | on **RX1** |
| USB webcam (or built-in camera) | ✔ | — |

> **Safety: connect the antennas before running anything.** If you join the two
> boards with a coax cable instead of antennas, put **at least 30 dB of
> attenuators** in the cable. Connecting TX straight into RX can overload or damage
> the receiver.

---

## Step 1 — Get the files (do this on BOTH PCs)

Open a terminal (Super key → type "Terminal") and run:

```bash
sudo apt install -y git
git clone -b linux-live-camera https://github.com/siddyyy223/PlutoSky-based-VTX.git
cd PlutoSky-based-VTX/gnuradio/04_Two-PC-Live-Camera/Linux
```

(No internet on that PC? On another PC download
<https://github.com/siddyyy223/PlutoSky-based-VTX/archive/refs/heads/linux-live-camera.zip>,
copy it over on a USB stick, unzip it, and `cd` into
`gnuradio/04_Two-PC-Live-Camera/Linux`. Step 2 still needs internet once to
install packages.)

All the commands below are run **from this `Linux` folder**.

## Step 2 — Install the software (once per PC, BOTH PCs)

```bash
./setup_pc.sh
```

It asks for your password once, installs GNU Radio, the Pluto (libiio) tools,
Qt and ffmpeg, then checks everything. It must end with **`Setup OK`**. If it
says it added you to the `video` group, log out and log back in once.

To re-check later without installing anything: `./setup_pc.sh --check`.

## Step 3 — Connect and find each Pluto (BOTH PCs)

1. Screw the antenna on (PC A: **TX1**, PC B: **RX1**).
2. Plug the Pluto into its PC's USB using the **USB2.0/OTG** port. Wait about 20 seconds.
3. Run:
   ```bash
   ./find_pluto.sh
   ```
   It prints the board's address, for example `ip:192.168.2.1`. If it says
   *No Pluto found*, follow the hints it prints.

### TX and RX board labels

The boards are labelled in `pluto_boards.conf` (already in the repository), so
`run_tx.sh` always uses the TX board and `run_rx.sh` the RX board, even with
both plugged into one PC:

| Role | Board IP (`config.txt` on the board) |
|---|---|
| TX | `192.168.3.1` |
| RX | `192.168.2.1` |

A board is recognised by its **own IP address**, not its serial number. These
PlutoSky boards are clones that report the **same serial number and MAC address**,
so those can't tell them apart. `./find_pluto.sh --list` shows what is
attached and which label each board has.

To label a new or replaced board, plug in only that board and run
`./label_pluto.sh tx` (or `rx`). If the other board is also plugged in and
already labelled, the new one is picked automatically.

Two boards plugged into the **same PC** must have different IP subnets. If
`label_pluto.sh` reports that two boards use the same IP, change one. Open its
USB drive (*PlutoSDR*) in the file manager and edit `config.txt`: in `[NETWORK]`
set `ipaddr = 192.168.3.1` and `ipaddr_host = 192.168.3.10`. Save, eject the
drive, and wait for the board to reboot.

## Step 4 — Start the RECEIVER first (PC B)

```bash
./run_rx.sh
```

A window titled **PlutoSky VTX - Receiver (PC B)** opens. Click the **Live video**
tab. It says *Waiting for received video...* until the transmitter starts.

## Step 5 — Start the TRANSMITTER (PC A)

The first time, use the built-in test pattern so you can check the radio link
without the camera:

```bash
./run_tx.sh --source-mode test
```

When moving coloured stripes appear on PC B, close the transmitter window and
start it with the camera:

```bash
./run_tx.sh
```

A window titled **PlutoSky VTX - Transmitter (PC A)** opens. Its **Live video**
tab shows the camera, and PC B now shows the same picture. The drop-down on PC A
can switch to *Image sent over the air*, which shows exactly what PC B receives.

## Step 6 — Stop

Close the windows (or press Ctrl-C in the terminals). `run_tx.sh` switches the
transmitter off when it exits. If the transmitter was force-killed, or you're not
sure it stopped, run `./mute_tx.sh` on PC A.

---

## Reading the receiver window

- **Status line** (under the picture): *Complete video frames* should keep
  rising. *Bad CRC packets* and *Lost video frames* should stay small.
- **Receiver constellations (4 stages)** tab: the last plot (after the Costas loop)
  should show **four tight dots/clusters** when the link is good.
- **RX Gain** slider (top): adjust it live. Lower it if the picture breaks up
  with the boards close together; raise it if they are far apart.

## Settings

All settings are options on the run scripts. Nothing has to be edited.
`./run_tx.sh --help` and `./run_rx.sh --help` list them all.

| Option | Script | Default | Meaning |
|---|---|---|---|
| `--freq 2.0e9` | both | 2.0 GHz | radio frequency, **must be the same on both PCs** |
| `--tx-attenuation 30` | tx | 30 dB | lower number = more power (e.g. 10–20 for longer distances) |
| `--rx-gain 35` | rx | 35 dB | receiver gain at start (also the live slider) |
| `--source-mode test` | tx | camera | send a moving test pattern instead of the camera |
| `--camera-name /dev/video2` | tx | `/dev/video0` | pick another camera (`ls /dev/video*` lists them) |
| `--video-fps 10` | tx | 10 | frames per second (the link fits about 10 fps of 640×360) |
| `--jpeg-quality 65` | tx | 65 | starting picture quality; lowered automatically if frames get too big |

Example, longer range at 2.2 GHz:

```bash
./run_rx.sh --freq 2.2e9 --rx-gain 50        # PC B
./run_tx.sh --freq 2.2e9 --tx-attenuation 10 # PC A
```

If the Pluto has a non-default address, give it explicitly:
`PLUTO_URI=ip:192.168.3.1 ./run_tx.sh`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No Pluto found` | Use the USB2.0/OTG port, wait 20 s, check `ip -br addr` shows a `192.168.2.x` interface, try another cable. |
| `No camera (/dev/video*) found` | Plug in the webcam, check `ls /dev/video*`, close other programs using it (browser, Zoom, Cheese). |
| Receiver shows *Waiting for the RF signal* | Transmitter not running, frequencies differ, or antennas not on TX1/RX1. |
| Picture freezes, many *Bad CRC packets* | Signal too weak (raise RX gain / lower TX attenuation) or too strong (opposite, if boards are close). |
| Window opens, then Python error mentioning `iio` | The Pluto was unplugged or is still booting; wait and restart. |
| `setup_pc.sh` shows FAIL | Run `./setup_pc.sh` again (without `--check`) while online, and read the line that failed. |

## How it works (for reference)

- **PC A:** camera → JPEG (640×360, ~10 fps, ≤19 KB/frame) → 796-byte packets,
  each with sync word, header and CRC32 → differential QPSK, 1.024 Msym/s,
  4 samples/symbol (4.096 MSPS), RRC 0.35 → Pluto TX1 at 2 GHz.
- **PC B:** Pluto RX1 → polyphase clock sync → CMA equalizer → Costas loop →
  DQPSK decode → packet sync + CRC → frame reassembly → live display.
- The radio format matches the original Windows flowgraphs in `../TX` and `../RX`,
  so a Linux PC can also talk to a Windows PC running those.
- Camera on Linux: always read through `ffmpeg` (V4L2) for `default` or a
  `/dev/videoN` name. A Qt Multimedia camera name is used only if
  `python3-pyqt5.qtmultimedia` is installed.

## Test without any hardware

```bash
python3 test_sw_loopback.py                    # test pattern, 15 s
python3 test_sw_loopback.py --camera default   # real webcam
```

This runs the real transmitter and receiver code over a simulated radio channel
(noise, frequency and clock offset) and checks every received picture byte for
byte. It should print `PASS`. Measured: 149/149 frames (test pattern) and
141/141 frames (webcam) received byte-exact.

## Files in this folder

| File | What it is |
|---|---|
| `setup_pc.sh` | one-time install and check |
| `find_pluto.sh` | prints the address of the TX/RX board (`./find_pluto.sh tx`, `rx`, `--list`) |
| `label_pluto.sh` | labels a board as TX or RX (saved in `pluto_boards.conf`) |
| `pluto_boards.conf` | which board is TX and which is RX (by board IP) |
| `run_tx.sh` / `run_rx.sh` | start the transmitter (PC A) / receiver (PC B) |
| `mute_tx.sh` | emergency stop for the transmitter |
| `r2_camera_tx.py`, `r2_camera_rx.py`, `*_epy_block_*.py` | the GNU Radio programs (generated, don't edit) |
| `tx_camera.grc`, `rx_video.grc` | the same flowgraphs for GNU Radio Companion |
| `src/tx_video_source.py`, `src/rx_video_receiver.py` | camera/packet/player code; after editing run `python3 build_flowgraphs.py` |
| `build_flowgraphs.py` | rebuilds the `.grc`/`.py` files from `src/` and `../TX`, `../RX` |
| `test_sw_loopback.py` | hardware-free test |
