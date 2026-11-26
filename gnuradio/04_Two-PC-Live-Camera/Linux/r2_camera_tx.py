#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: PlutoSky VTX - Transmitter (PC A)
# GNU Radio version: 3.10.9.2

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio import blocks
from gnuradio import digital
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import iio
import r2_camera_tx_epy_block_1 as epy_block_1  # embedded python block
import sip


def snipfcn_reduce_video_buffering(self):
    # Keep scheduler batches small; Windows rounds byte buffers to at least 64 KiB.
    for name in ('blocks_char_to_float_0_0_1_0','blocks_unpack_k_bits_bb_0',
                 'blocks_throttle2_1','channels_channel_model_0',
                 'digital_pfb_clock_sync_xxx_0','digital_linear_equalizer_0',
                 'digital_costas_loop_cc_0','digital_constellation_decoder_cb_0',
                 'digital_diff_decoder_bb_0','digital_map_bb_0'):
        block=getattr(self,name,None)
        if block is not None:
            if hasattr(block,'set_max_noutput_items'):block.set_max_noutput_items(8192)
    modulator=getattr(self,'digital_constellation_modulator_0',None)
    if modulator is not None:
        for name in ('bytes2chunks','symbol_mapper','diffenc','chunks2symbols','rrc_filter'):
            block=getattr(modulator,name,None)
            if block is not None:
                block.set_max_noutput_items(8192)
    source=getattr(self,'epy_block_1',None)
    if source is not None:
        consumer=getattr(self,'r2_sink',None)
        if consumer is None:consumer=getattr(self,'blocks_throttle2_1',None)
        if consumer is not None:
            samples_per_byte=4*float(self.sps)
            source._consumed_bytes=lambda: consumer.nitems_read(0)/samples_per_byte


def snippets_main_after_init(tb):
    snipfcn_reduce_video_buffering(tb)

class r2_camera_tx(gr.top_block, Qt.QWidget):

    def __init__(self, camera_name='default', freq=2.0e9, jpeg_quality=65, source_mode='camera', tx_attenuation=30.0, tx_uri='ip:192.168.2.1', video_fps=10):
        gr.top_block.__init__(self, "PlutoSky VTX - Transmitter (PC A)", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("PlutoSky VTX - Transmitter (PC A)")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "r2_camera_tx")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)

        ##################################################
        # Parameters
        ##################################################
        self.camera_name = camera_name
        self.freq = freq
        self.jpeg_quality = jpeg_quality
        self.source_mode = source_mode
        self.tx_attenuation = tx_attenuation
        self.tx_uri = tx_uri
        self.video_fps = video_fps

        ##################################################
        # Variables
        ##################################################
        self.bit_rate = bit_rate = 2048000
        self.symbol_rate = symbol_rate = bit_rate/2
        self.sps = sps = 4
        self.video_width = video_width = 640
        self.video_height = video_height = 360
        self.samp_rate_after_constellation = samp_rate_after_constellation = int(symbol_rate*sps)
        self.qpsk = qpsk = digital.constellation_rect([0.707+0.707j, -0.707+0.707j, -0.707-0.707j, 0.707-0.707j], [0, 1, 2, 3],
        4, 2, 2, 1, 1).base()
        self.one_frame_data = one_frame_data = 796
        self.max_frame_bytes = max_frame_bytes = 19000
        self.excess_bw = excess_bw = 0.35
        self.bandwidth = bandwidth = int(symbol_rate*1.2)

        ##################################################
        # Blocks
        ##################################################

        self.monitor_tabs = Qt.QTabWidget()
        self.monitor_tabs_widget_0 = Qt.QWidget()
        self.monitor_tabs_layout_0 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.monitor_tabs_widget_0)
        self.monitor_tabs_grid_layout_0 = Qt.QGridLayout()
        self.monitor_tabs_layout_0.addLayout(self.monitor_tabs_grid_layout_0)
        self.monitor_tabs.addTab(self.monitor_tabs_widget_0, 'Live video')
        self.monitor_tabs_widget_1 = Qt.QWidget()
        self.monitor_tabs_layout_1 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.monitor_tabs_widget_1)
        self.monitor_tabs_grid_layout_1 = Qt.QGridLayout()
        self.monitor_tabs_layout_1.addLayout(self.monitor_tabs_grid_layout_1)
        self.monitor_tabs.addTab(self.monitor_tabs_widget_1, 'Constellation and spectrum')
        self.monitor_tabs_widget_2 = Qt.QWidget()
        self.monitor_tabs_layout_2 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.monitor_tabs_widget_2)
        self.monitor_tabs_grid_layout_2 = Qt.QGridLayout()
        self.monitor_tabs_layout_2.addLayout(self.monitor_tabs_grid_layout_2)
        self.monitor_tabs.addTab(self.monitor_tabs_widget_2, 'Time domain before and after modulation')
        self.top_grid_layout.addWidget(self.monitor_tabs, 1, 0, 1, 4)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.tx_spectrum = qtgui.freq_sink_c(
            1024, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            freq, #fc
            samp_rate_after_constellation, #bw
            'TX spectrum', #name
            1,
            None # parent
        )
        self.tx_spectrum.set_update_time(0.10)
        self.tx_spectrum.set_y_axis((-120), 20)
        self.tx_spectrum.set_y_label('Relative Gain', 'dB')
        self.tx_spectrum.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.tx_spectrum.enable_autoscale(False)
        self.tx_spectrum.enable_grid(True)
        self.tx_spectrum.set_fft_average(1.0)
        self.tx_spectrum.enable_axis_labels(True)
        self.tx_spectrum.enable_control_panel(False)
        self.tx_spectrum.set_fft_window_normalized(False)

        self.tx_spectrum.disable_legend()


        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.tx_spectrum.set_line_label(i, "Data {0}".format(i))
            else:
                self.tx_spectrum.set_line_label(i, labels[i])
            self.tx_spectrum.set_line_width(i, widths[i])
            self.tx_spectrum.set_line_color(i, colors[i])
            self.tx_spectrum.set_line_alpha(i, alphas[i])

        self._tx_spectrum_win = sip.wrapinstance(self.tx_spectrum.qwidget(), Qt.QWidget)
        self.monitor_tabs_grid_layout_1.addWidget(self._tx_spectrum_win, 0, 1, 1, 1)
        for r in range(0, 1):
            self.monitor_tabs_grid_layout_1.setRowStretch(r, 1)
        for c in range(1, 2):
            self.monitor_tabs_grid_layout_1.setColumnStretch(c, 1)
        self.tx_constellation = qtgui.const_sink_c(
            1024, #size
            'TX I/Q constellation (after RRC shaping)', #name
            1, #number of inputs
            None # parent
        )
        self.tx_constellation.set_update_time(0.10)
        self.tx_constellation.set_y_axis((-2), 2)
        self.tx_constellation.set_x_axis((-2), 2)
        self.tx_constellation.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.tx_constellation.enable_autoscale(False)
        self.tx_constellation.enable_grid(True)
        self.tx_constellation.enable_axis_labels(True)

        self.tx_constellation.disable_legend()

        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "red", "red", "red",
            "red", "red", "red", "red", "red"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.tx_constellation.set_line_label(i, "Data {0}".format(i))
            else:
                self.tx_constellation.set_line_label(i, labels[i])
            self.tx_constellation.set_line_width(i, widths[i])
            self.tx_constellation.set_line_color(i, colors[i])
            self.tx_constellation.set_line_style(i, styles[i])
            self.tx_constellation.set_line_marker(i, markers[i])
            self.tx_constellation.set_line_alpha(i, alphas[i])

        self._tx_constellation_win = sip.wrapinstance(self.tx_constellation.qwidget(), Qt.QWidget)
        self.monitor_tabs_grid_layout_1.addWidget(self._tx_constellation_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.monitor_tabs_grid_layout_1.setRowStretch(r, 1)
        for c in range(0, 1):
            self.monitor_tabs_grid_layout_1.setColumnStretch(c, 1)
        self.r2_sink = iio.fmcomms2_sink_fc32(tx_uri if tx_uri else iio.get_pluto_uri(), [True, True], 32768, False)
        self.r2_sink.set_len_tag_key('')
        self.r2_sink.set_bandwidth(bandwidth)
        self.r2_sink.set_frequency(int(freq))
        self.r2_sink.set_samplerate(samp_rate_after_constellation)
        self.r2_sink.set_attenuation(0, tx_attenuation)
        self.r2_sink.set_filter_params('Auto', '', 0, 0)
        self.qtgui_time_sink_x_1_1_0 = qtgui.time_sink_f(
            2048, #size
            int(bit_rate/8), #samp_rate
            "Before modulation", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_time_sink_x_1_1_0.set_update_time(1)
        self.qtgui_time_sink_x_1_1_0.set_y_axis(-200, 200)

        self.qtgui_time_sink_x_1_1_0.set_y_label('Amplitude', "")

        self.qtgui_time_sink_x_1_1_0.enable_tags(True)
        self.qtgui_time_sink_x_1_1_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.qtgui_time_sink_x_1_1_0.enable_autoscale(False)
        self.qtgui_time_sink_x_1_1_0.enable_grid(True)
        self.qtgui_time_sink_x_1_1_0.enable_axis_labels(True)
        self.qtgui_time_sink_x_1_1_0.enable_control_panel(False)
        self.qtgui_time_sink_x_1_1_0.enable_stem_plot(False)


        labels = ['Signal 1', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_time_sink_x_1_1_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_time_sink_x_1_1_0.set_line_label(i, labels[i])
            self.qtgui_time_sink_x_1_1_0.set_line_width(i, widths[i])
            self.qtgui_time_sink_x_1_1_0.set_line_color(i, colors[i])
            self.qtgui_time_sink_x_1_1_0.set_line_style(i, styles[i])
            self.qtgui_time_sink_x_1_1_0.set_line_marker(i, markers[i])
            self.qtgui_time_sink_x_1_1_0.set_line_alpha(i, alphas[i])

        self._qtgui_time_sink_x_1_1_0_win = sip.wrapinstance(self.qtgui_time_sink_x_1_1_0.qwidget(), Qt.QWidget)
        self.monitor_tabs_grid_layout_2.addWidget(self._qtgui_time_sink_x_1_1_0_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.monitor_tabs_grid_layout_2.setRowStretch(r, 1)
        for c in range(0, 1):
            self.monitor_tabs_grid_layout_2.setColumnStretch(c, 1)
        self.qtgui_time_sink_x_1 = qtgui.time_sink_c(
            2048, #size
            samp_rate_after_constellation, #samp_rate
            "After modulation", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_time_sink_x_1.set_update_time(0.10)
        self.qtgui_time_sink_x_1.set_y_axis(-1.5, 1.5)

        self.qtgui_time_sink_x_1.set_y_label('Amplitude', "")

        self.qtgui_time_sink_x_1.enable_tags(True)
        self.qtgui_time_sink_x_1.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.qtgui_time_sink_x_1.enable_autoscale(False)
        self.qtgui_time_sink_x_1.enable_grid(True)
        self.qtgui_time_sink_x_1.enable_axis_labels(True)
        self.qtgui_time_sink_x_1.enable_control_panel(False)
        self.qtgui_time_sink_x_1.enable_stem_plot(False)


        labels = ['Signal 1', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(2):
            if len(labels[i]) == 0:
                if (i % 2 == 0):
                    self.qtgui_time_sink_x_1.set_line_label(i, "Re{{Data {0}}}".format(i/2))
                else:
                    self.qtgui_time_sink_x_1.set_line_label(i, "Im{{Data {0}}}".format(i/2))
            else:
                self.qtgui_time_sink_x_1.set_line_label(i, labels[i])
            self.qtgui_time_sink_x_1.set_line_width(i, widths[i])
            self.qtgui_time_sink_x_1.set_line_color(i, colors[i])
            self.qtgui_time_sink_x_1.set_line_style(i, styles[i])
            self.qtgui_time_sink_x_1.set_line_marker(i, markers[i])
            self.qtgui_time_sink_x_1.set_line_alpha(i, alphas[i])

        self._qtgui_time_sink_x_1_win = sip.wrapinstance(self.qtgui_time_sink_x_1.qwidget(), Qt.QWidget)
        self.monitor_tabs_grid_layout_2.addWidget(self._qtgui_time_sink_x_1_win, 0, 1, 1, 1)
        for r in range(0, 1):
            self.monitor_tabs_grid_layout_2.setRowStretch(r, 1)
        for c in range(1, 2):
            self.monitor_tabs_grid_layout_2.setColumnStretch(c, 1)
        self.epy_block_1 = epy_block_1.VideoSource(source_mode=source_mode, camera_name=camera_name, video_width=video_width, video_height=video_height, video_fps=video_fps, jpeg_quality=jpeg_quality, max_frame_bytes=max_frame_bytes, radio_bitrate=bit_rate)
        self.digital_constellation_modulator_0 = digital.generic_mod(
            constellation=qpsk,
            differential=True,
            samples_per_symbol=sps,
            pre_diff_code=True,
            excess_bw=excess_bw,
            verbose=False,
            log=False,
            truncate=False)
        self.blocks_char_to_float_0_0_1_0 = blocks.char_to_float(1, 1)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.blocks_char_to_float_0_0_1_0, 0), (self.qtgui_time_sink_x_1_1_0, 0))
        self.connect((self.digital_constellation_modulator_0, 0), (self.qtgui_time_sink_x_1, 0))
        self.connect((self.digital_constellation_modulator_0, 0), (self.r2_sink, 0))
        self.connect((self.digital_constellation_modulator_0, 0), (self.tx_constellation, 0))
        self.connect((self.digital_constellation_modulator_0, 0), (self.tx_spectrum, 0))
        self.connect((self.epy_block_1, 0), (self.blocks_char_to_float_0_0_1_0, 0))
        self.connect((self.epy_block_1, 0), (self.digital_constellation_modulator_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "r2_camera_tx")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_camera_name(self):
        return self.camera_name

    def set_camera_name(self, camera_name):
        self.camera_name = camera_name

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        self.freq = freq
        self.r2_sink.set_frequency(int(self.freq))
        self.tx_spectrum.set_frequency_range(self.freq, self.samp_rate_after_constellation)

    def get_jpeg_quality(self):
        return self.jpeg_quality

    def set_jpeg_quality(self, jpeg_quality):
        self.jpeg_quality = jpeg_quality

    def get_source_mode(self):
        return self.source_mode

    def set_source_mode(self, source_mode):
        self.source_mode = source_mode

    def get_tx_attenuation(self):
        return self.tx_attenuation

    def set_tx_attenuation(self, tx_attenuation):
        self.tx_attenuation = tx_attenuation
        self.r2_sink.set_attenuation(0,self.tx_attenuation)

    def get_tx_uri(self):
        return self.tx_uri

    def set_tx_uri(self, tx_uri):
        self.tx_uri = tx_uri

    def get_video_fps(self):
        return self.video_fps

    def set_video_fps(self, video_fps):
        self.video_fps = video_fps

    def get_bit_rate(self):
        return self.bit_rate

    def set_bit_rate(self, bit_rate):
        self.bit_rate = bit_rate
        self.set_symbol_rate(self.bit_rate/2)
        self.qtgui_time_sink_x_1_1_0.set_samp_rate(int(self.bit_rate/8))

    def get_symbol_rate(self):
        return self.symbol_rate

    def set_symbol_rate(self, symbol_rate):
        self.symbol_rate = symbol_rate
        self.set_bandwidth(int(self.symbol_rate*1.2))
        self.set_samp_rate_after_constellation(int(self.symbol_rate*self.sps))

    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps
        self.set_samp_rate_after_constellation(int(self.symbol_rate*self.sps))

    def get_video_width(self):
        return self.video_width

    def set_video_width(self, video_width):
        self.video_width = video_width

    def get_video_height(self):
        return self.video_height

    def set_video_height(self, video_height):
        self.video_height = video_height

    def get_samp_rate_after_constellation(self):
        return self.samp_rate_after_constellation

    def set_samp_rate_after_constellation(self, samp_rate_after_constellation):
        self.samp_rate_after_constellation = samp_rate_after_constellation
        self.qtgui_time_sink_x_1.set_samp_rate(self.samp_rate_after_constellation)
        self.r2_sink.set_samplerate(self.samp_rate_after_constellation)
        self.tx_spectrum.set_frequency_range(self.freq, self.samp_rate_after_constellation)

    def get_qpsk(self):
        return self.qpsk

    def set_qpsk(self, qpsk):
        self.qpsk = qpsk

    def get_one_frame_data(self):
        return self.one_frame_data

    def set_one_frame_data(self, one_frame_data):
        self.one_frame_data = one_frame_data

    def get_max_frame_bytes(self):
        return self.max_frame_bytes

    def set_max_frame_bytes(self, max_frame_bytes):
        self.max_frame_bytes = max_frame_bytes

    def get_excess_bw(self):
        return self.excess_bw

    def set_excess_bw(self, excess_bw):
        self.excess_bw = excess_bw

    def get_bandwidth(self):
        return self.bandwidth

    def set_bandwidth(self, bandwidth):
        self.bandwidth = bandwidth
        self.r2_sink.set_bandwidth(self.bandwidth)



def argument_parser():
    parser = ArgumentParser()
    parser.add_argument(
        "--camera-name", dest="camera_name", type=str, default='default',
        help="Set Camera: 'default', /dev/videoN, or Qt camera name [default=%(default)r]")
    parser.add_argument(
        "--freq", dest="freq", type=eng_float, default=eng_notation.num_to_str(float(2.0e9)),
        help="Set Carrier frequency [Hz] [default=%(default)r]")
    parser.add_argument(
        "--jpeg-quality", dest="jpeg_quality", type=intx, default=65,
        help="Set JPEG quality (10-90) [default=%(default)r]")
    parser.add_argument(
        "--source-mode", dest="source_mode", type=str, default='camera',
        help="Set 'camera' or 'test' (moving test pattern) [default=%(default)r]")
    parser.add_argument(
        "--tx-attenuation", dest="tx_attenuation", type=eng_float, default=eng_notation.num_to_str(float(30.0)),
        help="Set TX attenuation [dB] [default=%(default)r]")
    parser.add_argument(
        "--tx-uri", dest="tx_uri", type=str, default='ip:192.168.2.1',
        help="Set TX Pluto URI [default=%(default)r]")
    parser.add_argument(
        "--video-fps", dest="video_fps", type=intx, default=10,
        help="Set Video frame rate [default=%(default)r]")
    return parser


def main(top_block_cls=r2_camera_tx, options=None):
    if options is None:
        options = argument_parser().parse_args()

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls(camera_name=options.camera_name, freq=options.freq, jpeg_quality=options.jpeg_quality, source_mode=options.source_mode, tx_attenuation=options.tx_attenuation, tx_uri=options.tx_uri, video_fps=options.video_fps)
    snippets_main_after_init(tb)
    tb.start()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
