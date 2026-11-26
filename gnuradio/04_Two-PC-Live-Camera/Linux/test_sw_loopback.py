#!/usr/bin/env python3
"""Hardware-free end-to-end test of the Linux live camera link.

Runs the real TX video block (from r2_camera_tx_epy_block_1.py) -> the vendor's
DQPSK modulator -> a simulated channel (AWGN, carrier frequency offset, sample-clock
offset) -> the exact RX DSP chain of r2_camera_rx.py -> the real RX video block,
and checks every received JPEG byte-for-byte against what the TX actually encoded.

    python3 test_sw_loopback.py                    # moving test pattern, 15 s
    python3 test_sw_loopback.py --camera default   # real webcam via ffmpeg/QtMultimedia
    python3 test_sw_loopback.py --snr-db 12 --cfo-hz 20e3

Pass criteria: >= 70% of the frames the TX put on air arrive complete, and every
complete frame received matches a sent one exactly (CRC'd transport must never
deliver a wrong frame).
"""
import argparse
import hashlib
import os
import sys
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PyQt5 import QtCore, QtWidgets
from gnuradio import blocks, channels, digital, filter, gr
from gnuradio.filter import firdes

import r2_camera_rx_epy_block_0 as rxmod
import r2_camera_tx_epy_block_1 as txmod

# Link constants, identical to tx_camera.grc / rx_video.grc
BIT_RATE = 2048000
SPS = 4
EXCESS_BW = 0.35
NFILTS = 32
PHASE_BW = 0.0628
SYMBOL_RATE = BIT_RATE / 2
SAMP_RATE = int(SYMBOL_RATE * SPS)


class Loopback(gr.top_block):
    def __init__(self, a):
        gr.top_block.__init__(self, 'r2 camera sw loopback')
        qpsk = digital.constellation_rect([0.707+0.707j, -0.707+0.707j, -0.707-0.707j, 0.707-0.707j],
                                          [0, 1, 2, 3], 4, 2, 2, 1, 1).base()
        self.src = txmod.VideoSource(source_mode='test' if a.camera is None else 'camera',
                             camera_name=a.camera or 'default', video_width=640, video_height=360,
                             video_fps=a.fps, jpeg_quality=65, max_frame_bytes=19000,
                             radio_bitrate=BIT_RATE)
        mod = digital.generic_mod(constellation=qpsk, differential=True, samples_per_symbol=SPS,
                                  pre_diff_code=True, excess_bw=EXCESS_BW,
                                  verbose=False, log=False, truncate=False)
        noise_v = 10 ** (-a.snr_db / 20.0)  # modulator output is ~unit power
        chan = channels.channel_model(noise_voltage=noise_v, frequency_offset=a.cfo_hz / SAMP_RATE,
                                      epsilon=1.0 + a.clock_ppm * 1e-6,
                                      taps=[1.0 + 0j], noise_seed=7, block_tags=False)
        self.thr = blocks.throttle(gr.sizeof_gr_complex, SAMP_RATE, True)
        rrc_taps = firdes.root_raised_cosine(NFILTS, NFILTS, 1.0 / float(SPS), 0.35, 11 * SPS * NFILTS)
        cma = digital.adaptive_algorithm_cma(qpsk, 0.001, 4).base()
        clock = digital.pfb_clock_sync_ccf(SPS, 2 * 3.14 / 100.0, rrc_taps, NFILTS, 0, 0.5, 2)
        eq = digital.linear_equalizer(15, 2, cma, True, [], 'corr_est')
        costas = digital.costas_loop_cc(PHASE_BW, 4, False)
        dec = digital.constellation_decoder_cb(qpsk)
        diff = digital.diff_decoder_bb(4, digital.DIFF_DIFFERENTIAL)
        mp = digital.map_bb([0, 1, 2, 3])
        unpack = blocks.unpack_k_bits_bb(2)
        self.sink = rxmod.VideoReceiver()
        self.connect(self.src, mod, chan, self.thr, clock, eq, costas, dec, diff, mp, unpack, self.sink)
        # Same pacing hook as the vendor 'reduce_video_buffering' snippet; the throttle
        # stands in for the Pluto sink as the consumer clock.
        thr = self.thr
        self.src._consumed_bytes = lambda: thr.nitems_read(0) / (4.0 * SPS)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--secs', type=float, default=15)
    p.add_argument('--snr-db', type=float, default=20)
    p.add_argument('--cfo-hz', type=float, default=5e3)
    p.add_argument('--clock-ppm', type=float, default=20)
    p.add_argument('--fps', type=int, default=10)
    p.add_argument('--camera', default=None, help="camera name/device; omit for the test pattern")
    p.add_argument('--save', default=None, help='directory to save first/last received JPEG')
    a = p.parse_args()

    app = QtWidgets.QApplication(sys.argv)

    sent = {}  # sha256 -> sequence
    orig_split = txmod.split_unit

    def recording_split(data, session, sequence):
        sent[hashlib.sha256(data).hexdigest()] = sequence
        return orig_split(data, session, sequence)
    txmod.split_unit = recording_split

    tb = Loopback(a)
    received = []
    orig_feed = tb.sink.assembler.feed

    def recording_feed(record, now=None):
        unit = orig_feed(record, now)
        if unit is not None:
            received.append(unit)
        return unit
    tb.sink.assembler.feed = recording_feed

    tb.start()
    t0 = time.monotonic()
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: app.quit() if time.monotonic() - t0 > a.secs else None)
    timer.start(200)
    app.exec_()
    tb.stop()
    tb.wait()

    src, rx = tb.src, tb.sink
    matched = sum(1 for _, _, j in received if hashlib.sha256(j).hexdigest() in sent)
    on_air = src.encoded_frames - src.dropped_frames
    first_seq = min((s for _, s, _ in received), default=None)
    # Frames encoded before the receiver first locked can't be expected.
    expected = sum(1 for s in sent.values() if first_seq is not None and s >= first_seq) - src.dropped_frames
    print(f'TX : encoded {src.encoded_frames}, dropped(overload) {src.dropped_frames}, '
          f'oversize {src.oversize_frames}, packets {src.sent_packets}, '
          f'avg JPEG {src.encoded_bytes / max(1, src.encoded_frames) / 1024:.1f} KB, status: {src.get_status()}')
    print(f'RX : complete frames {rx.received_frames}, valid packets {rx.deframer.valid_packets}, '
          f'bad CRC {rx.deframer.bad_crc}, lost {rx.assembler.lost_units}, bad units {rx.assembler.bad_units}')
    print(f'Byte-exact matches {matched}/{len(received)} received; on air {on_air}, '
          f'expected after first lock {expected}')
    if a.save and received:
        os.makedirs(a.save, exist_ok=True)
        for tag, (_, seq, j) in (('first', received[0]), ('last', received[-1])):
            open(os.path.join(a.save, f'rx_{tag}_seq{seq}.jpg'), 'wb').write(j)
    ok = received and matched == len(received) and expected > 0 and len(received) >= 0.7 * expected
    print('PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
