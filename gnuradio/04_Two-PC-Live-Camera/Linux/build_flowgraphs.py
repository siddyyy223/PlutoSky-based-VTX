#!/usr/bin/env python3
"""Regenerate the Linux TX/RX live-camera flowgraphs (.grc + runnable .py) from the vendor ones.

Source of truth:
  ../TX/TX_CAMERA_PC_A.grc, ../RX/RX_VIDEO_PC_B.grc  -- the Windows flowgraphs,
      used unmodified
  src/tx_video_source.py, src/rx_video_receiver.py           -- the embedded Python
      blocks, ported to Linux (edit these, not the generated *_epy_block_*.py)

What this changes relative to the vendor flowgraphs:
  * per-PC settings become GRC `parameter` blocks, so the generated scripts take
    command-line flags (--tx-uri, --rx-uri, --freq, --tx-attenuation, --rx-gain, ...)
    instead of needing each PC's copy edited in GRC;
  * TX attenuation defaults to 30 dB instead of 10 dB (safer for a first test,
    especially with a cable or short antenna path between the boards);
  * the embedded block source is replaced with the Linux port from src/.
DSP, rates and the over-the-air packet format are untouched, so a Linux end
interoperates with an unmodified vendor (Windows) end.

Run after editing src/*.py:   python3 build_flowgraphs.py
"""
import os
import subprocess
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))

# name: (type, value, label)   type is a GRC parameter type ('str', 'eng_float', 'intx')
TX_PARAMS = {
    'tx_uri': ('str', 'ip:192.168.2.1', 'TX Pluto URI'),
    'freq': ('eng_float', '2.0e9', 'Carrier frequency [Hz]'),
    'tx_attenuation': ('eng_float', '30.0', 'TX attenuation [dB]'),
    'source_mode': ('str', 'camera', "'camera' or 'test' (moving test pattern)"),
    'camera_name': ('str', 'default', "Camera: 'default', /dev/videoN, or Qt camera name"),
    'video_fps': ('intx', '10', 'Video frame rate'),
    'jpeg_quality': ('intx', '65', 'JPEG quality (10-90)'),
}
RX_PARAMS = {
    'rx_uri': ('str', 'ip:192.168.2.1', 'RX Pluto URI'),
    'freq': ('eng_float', '2.0e9', 'Carrier frequency [Hz]'),
    'rx_gain': ('eng_float', '35', 'RX manual gain [dB]'),
}
# Vendor name is a leftover from a USRP template. It is a live GUI slider, which is
# kept; --rx-gain only sets its starting value (see SLIDER_INIT).
RENAME = {'uhd_gain': 'rx_gain_db'}
SLIDER_INIT = {'rx_gain_db': 'rx_gain'}  # slider name -> parameter giving its start value


def rename_refs(value):
    if isinstance(value, str):
        for old, new in RENAME.items():
            value = value.replace(old, new)
    return value


def convert(grc_in, grc_out, flow_id, title, params, epy_src):
    d = yaml.safe_load(open(grc_in))
    d['options']['parameters']['id'] = flow_id
    d['options']['parameters']['title'] = title
    seen = set()
    new_blocks = []
    for b in d['blocks']:
        b['name'] = rename_refs(b['name'])
        b['parameters'] = {k: rename_refs(v) for k, v in b['parameters'].items()}
        if b['id'] == 'variable' and b['name'] in params:
            ptype, value, label = params[b['name']]
            b['id'] = 'parameter'
            b['parameters'] = {'alias': '', 'comment': b['parameters'].get('comment', ''),
                               'hide': 'none', 'label': label, 'short_id': '',
                               'type': ptype, 'value': value}
            seen.add(b['name'])
        elif b['id'] == 'variable_qtgui_range' and SLIDER_INIT.get(b['name']) in params:
            pname = SLIDER_INIT[b['name']]
            ptype, value, label = params[pname]
            b['parameters']['value'] = pname
            new_blocks.append({'name': pname, 'id': 'parameter',
                               'parameters': {'alias': '', 'comment': '', 'hide': 'none',
                                              'label': label, 'short_id': '',
                                              'type': ptype, 'value': value},
                               'states': dict(b['states'])})
            seen.add(pname)
        elif b['id'] == 'epy_block':
            b['parameters']['_source_code'] = open(epy_src).read()
    for nb in new_blocks:  # place the parameter block just below its slider in GRC
        x, y = nb['states'].get('coordinate', [0, 0])
        nb['states']['coordinate'] = [x, y + 120]
    d['blocks'].extend(new_blocks)
    missing = set(params) - seen
    if missing:
        sys.exit(f'{grc_in}: variables not found: {sorted(missing)}')
    with open(grc_out, 'w') as f:
        yaml.safe_dump(d, f, sort_keys=False, allow_unicode=True, width=10**6)
    subprocess.run(['grcc', '-o', HERE, grc_out], check=True)
    print('generated', flow_id + '.py')


def main():
    convert(os.path.join(HERE, '../TX/TX_CAMERA_PC_A.grc'),
            os.path.join(HERE, 'tx_camera.grc'), 'r2_camera_tx',
            'PlutoSky R2 live camera TX (PC A)', TX_PARAMS,
            os.path.join(HERE, 'src/tx_video_source.py'))
    convert(os.path.join(HERE, '../RX/RX_VIDEO_PC_B.grc'),
            os.path.join(HERE, 'rx_video.grc'), 'r2_camera_rx',
            'PlutoSky R2 live video RX (PC B)', RX_PARAMS,
            os.path.join(HERE, 'src/rx_video_receiver.py'))


if __name__ == '__main__':
    main()
