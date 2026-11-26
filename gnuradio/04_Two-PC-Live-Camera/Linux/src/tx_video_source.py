"""Version 1 live JPEG video transport, independent of the old file protocol.

Ported from OpenSourceSDRLab PlutoSky-R2 gnuradio/04_Two-PC-Live-Camera (Apache-2.0).
Linux changes (gnuradio/04_Two-PC-Live-Camera/Linux): QtMultimedia is optional; a V4L2 camera is
read through an ffmpeg subprocess when QtMultimedia is missing or camera_name is a
/dev/video* path. The radio protocol is unchanged, so it interoperates with the
vendor Windows flowgraphs."""
import struct
import time
import zlib
import numpy as np

SYNC = bytes.fromhex('acdda4e2f28c20fc')
HEADER = struct.Struct('!BBHIIHH')
PAYLOAD = 768
WIRE_SIZE = len(SYNC) + HEADER.size + PAYLOAD + 4
MAX_UNIT = 256 * 1024
MAX_PARTS = (MAX_UNIT + 4 + PAYLOAD - 1) // PAYLOAD
IDLE_PAYLOAD = np.random.default_rng(1407).integers(0, 256, PAYLOAD, dtype=np.uint8).tobytes()


def packet(kind, session, sequence, index, count, payload):
    if len(payload) > PAYLOAD:
        raise ValueError('Payload too large')
    body = HEADER.pack(1, kind, len(payload), session, sequence, index, count)
    body += payload.ljust(PAYLOAD, b'\0')
    return SYNC + body + struct.pack('!I', zlib.crc32(body) & 0xffffffff)


def idle_packet(session):
    return packet(0, session, 0, 0, 1, IDLE_PAYLOAD)


def split_unit(data, session, sequence):
    if not 0 < len(data) <= MAX_UNIT:
        raise ValueError('Invalid compressed frame size')
    unit = struct.pack('!I', zlib.crc32(data) & 0xffffffff) + data
    count = (len(unit) + PAYLOAD - 1) // PAYLOAD
    return [packet(1, session, sequence, i, count, unit[i*PAYLOAD:(i+1)*PAYLOAD])
            for i in range(count)]


def newer(a, b):
    return 0 < ((a - b) & 0xffffffff) < 0x80000000


class BitDeframer:
    """Search all eight bit alignments; never assumes scheduler byte alignment."""
    def __init__(self):
        self.bits = np.empty(0, dtype=np.uint8)
        self.bad_crc = 0
        self.valid_packets = 0

    def feed(self, bits):
        self.bits = np.concatenate((self.bits, np.asarray(bits, dtype=np.uint8) & 1))
        records = []
        offset = 0
        while len(self.bits) - offset >= 64:
            view = self.bits[offset:]
            best = None
            for phase in range(8):
                pos = np.packbits(view[phase:]).tobytes().find(SYNC)
                if pos >= 0:
                    at = pos * 8 + phase
                    if best is None or at < best:
                        best = at
            if best is None:
                offset = len(self.bits) - 63
                break
            start = offset + best
            if len(self.bits) - start < WIRE_SIZE * 8:
                offset = start
                break
            raw = np.packbits(self.bits[start:start+WIRE_SIZE*8]).tobytes()
            body = raw[8:-4]
            if zlib.crc32(body) & 0xffffffff != int.from_bytes(raw[-4:], 'big'):
                self.bad_crc += 1
                offset = start + 1
                continue
            version, kind, size, session, sequence, index, count = HEADER.unpack(body[:HEADER.size])
            if (version != 1 or kind not in (0, 1) or size > PAYLOAD
                    or not 1 <= count <= MAX_PARTS or not 0 <= index < count
                    or (kind == 1 and (size == 0 or (index < count-1 and size != PAYLOAD)))):
                offset = start + 1
                continue
            records.append((kind, session, sequence, index, count, body[HEADER.size:HEADER.size+size]))
            self.valid_packets += 1
            offset = start + WIRE_SIZE * 8
        if offset:
            self.bits = self.bits[offset:].copy()
        return records


class UnitAssembler:
    """Keep at most one bounded video frame; newer frames supersede incomplete ones."""
    def __init__(self):
        self.session = None
        self.sequence = None
        self.parts = {}
        self.count = 0
        self.complete = False
        self.deadline = 0
        self.lost_units = 0
        self.duplicates = 0
        self.bad_units = 0
        self.idle_packets = 0
        self.units = 0

    def feed(self, record, now=None):
        now = time.monotonic() if now is None else now
        kind, session, sequence, index, count, data = record
        if kind == 0:
            self.idle_packets += 1
            if self.parts and now > self.deadline:
                self.parts.clear()
                self.complete = True
                self.lost_units += 1
            return None
        if session != self.session:
            self.session, self.sequence = session, None
            self.parts.clear()
        if self.sequence is None or newer(sequence, self.sequence):
            if self.sequence is not None:
                delta = (sequence - self.sequence) & 0xffffffff
                self.lost_units += delta - 1 + int(not self.complete)
            self.sequence = sequence
            self.count = count
            self.parts = {}
            self.complete = False
            self.deadline = now + 0.75
        elif sequence != self.sequence:
            return None
        if self.complete or index in self.parts:
            self.duplicates += 1
            return None
        if now > self.deadline or count != self.count:
            self.parts.clear()
            self.complete = True
            self.lost_units += 1
            return None
        self.parts[index] = data
        if len(self.parts) != self.count:
            return None
        raw = b''.join(self.parts[i] for i in range(self.count))
        self.parts.clear()
        self.complete = True
        if len(raw) < 5 or len(raw)-4 > MAX_UNIT or zlib.crc32(raw[4:]) & 0xffffffff != int.from_bytes(raw[:4], 'big'):
            self.bad_units += 1
            self.lost_units += 1
            return None
        self.units += 1
        return session, sequence, raw[4:]

import os
import sys
import shutil
import subprocess
import threading
from PyQt5 import QtCore, QtGui, QtWidgets
try:
    from PyQt5 import QtMultimedia
except ImportError:  # Ubuntu: python3-pyqt5.qtmultimedia not installed
    QtMultimedia = None


def live_test_image(index, width, height):
    x=np.arange(width,dtype=np.uint16)[None,:]
    y=np.arange(height,dtype=np.uint16)[:,None]
    rgb=np.empty((height,width,3),dtype=np.uint8)
    rgb[:,:,0]=(x//3+index*3)%256
    rgb[:,:,1]=(y//2+index*2)%256
    rgb[:,:,2]=((x+y)//5)%256
    left=(index*7)%max(1,width-50)
    rgb[height//3:height//3+40,left:left+50]=(255,230,30)
    return QtGui.QImage(rgb.data,width,height,width*3,QtGui.QImage.Format_RGB888).copy()


if QtMultimedia is not None:
    def live_frame_image(frame):
        """Detach camera image, including the YUV formats common on Windows webcams."""
        if not frame.map(QtMultimedia.QAbstractVideoBuffer.ReadOnly):
            raise RuntimeError('Cannot read the camera video buffer')
        try:
            w,h,stride=frame.width(),frame.height(),frame.bytesPerLine()
            fmt=frame.pixelFormat()
            qfmt=QtMultimedia.QVideoFrame.imageFormatFromPixelFormat(fmt)
            if qfmt!=QtGui.QImage.Format_Invalid:
                return QtGui.QImage(frame.bits(),w,h,stride,qfmt).copy()
            ptr=frame.bits();ptr.setsize(frame.mappedBytes())
            raw=np.frombuffer(ptr,dtype=np.uint8)
            VF=QtMultimedia.QVideoFrame
            if fmt==VF.Format_BGR24:
                rgb=raw[:h*stride].reshape(h,stride)[:,:w*3].reshape(h,w,3)[:,:,::-1].copy()
            else:
                if fmt in (VF.Format_YUYV,VF.Format_UYVY):
                    a=raw[:h*stride].reshape(h,stride)[:,:w*2].reshape(h,w//2,4)
                    yy=np.empty((h,w),dtype=np.float32)
                    if fmt==VF.Format_YUYV:
                        yy[:,0::2]=a[:,:,0];yy[:,1::2]=a[:,:,2]
                        uu=a[:,:,1].repeat(2,axis=1);vv=a[:,:,3].repeat(2,axis=1)
                    else:
                        yy[:,0::2]=a[:,:,1];yy[:,1::2]=a[:,:,3]
                        uu=a[:,:,0].repeat(2,axis=1);vv=a[:,:,2].repeat(2,axis=1)
                elif fmt in (VF.Format_NV12,VF.Format_NV21,VF.Format_YUV420P,VF.Format_YV12):
                    yy=raw[:h*stride].reshape(h,stride)[:,:w].astype(np.float32)
                    if fmt in (VF.Format_NV12,VF.Format_NV21):
                        cs=frame.bytesPerLine(1)
                        p=frame.bits(1);p.setsize(cs*((h+1)//2))
                        a=np.frombuffer(p,dtype=np.uint8).reshape((h+1)//2,cs)[:,:w].reshape((h+1)//2,w//2,2)
                        uu,vv=a[:,:,0],a[:,:,1]
                        if fmt==VF.Format_NV21:uu,vv=vv,uu
                    else:
                        planes=[]
                        for plane in (1,2):
                            cs=frame.bytesPerLine(plane)
                            p=frame.bits(plane);p.setsize(cs*((h+1)//2))
                            planes.append(np.frombuffer(p,dtype=np.uint8).reshape((h+1)//2,cs)[:,:w//2])
                        uu,vv=planes
                        if fmt==VF.Format_YV12:uu,vv=vv,uu
                    uu=uu.repeat(2,axis=0).repeat(2,axis=1)[:h,:w]
                    vv=vv.repeat(2,axis=0).repeat(2,axis=1)[:h,:w]
                else:
                    raise RuntimeError('Unsupported camera pixel format: '+str(fmt))
                c=yy-16.0;d=uu.astype(np.float32)-128;e=vv.astype(np.float32)-128
                rgb=np.stack((1.164*c+1.596*e,1.164*c-.392*d-.813*e,1.164*c+2.017*d),axis=2)
                rgb=np.ascontiguousarray(np.clip(rgb,0,255),dtype=np.uint8)
            return QtGui.QImage(rgb.data,w,h,w*3,QtGui.QImage.Format_RGB888).copy()
        finally:
            frame.unmap()


    class LiveVideoSurface(QtMultimedia.QAbstractVideoSurface):
        frame_ready=QtCore.pyqtSignal(QtGui.QImage)
        problem=QtCore.pyqtSignal(str)

        def __init__(self,fps,parent=None):
            super().__init__(parent)
            self.period=1.0/fps
            self.due=0
            self._image_lock=threading.Lock()
            self._latest_image=None
            self._image_serial=0

        def supportedPixelFormats(self,handleType=QtMultimedia.QAbstractVideoBuffer.NoHandle):
            if handleType!=QtMultimedia.QAbstractVideoBuffer.NoHandle:return []
            VF=QtMultimedia.QVideoFrame
            return [VF.Format_RGB32,VF.Format_ARGB32,VF.Format_ARGB32_Premultiplied,
                    VF.Format_RGB24,VF.Format_BGR24,VF.Format_BGR32,VF.Format_BGRA32,
                    VF.Format_YUYV,VF.Format_UYVY,VF.Format_NV12,VF.Format_NV21,
                    VF.Format_YUV420P,VF.Format_YV12]

        def present(self,video_frame):
            now=time.monotonic()
            if now+0.002<self.due:return True
            if not self.due or now-self.due>self.period:self.due=now
            self.due+=self.period
            frame=QtMultimedia.QVideoFrame(video_frame)
            try:
                image=live_frame_image(frame)
                if self.surfaceFormat().scanLineDirection()==QtMultimedia.QVideoSurfaceFormat.BottomToTop:
                    image=image.mirrored(False,True)
                with self._image_lock:
                    self._image_serial+=1
                    self._latest_image=(self._image_serial,image)
                return True
            except Exception as exc:
                self.problem.emit(str(exc))
                return False


class LiveQtBridge(QtCore.QObject):
    start_requested=QtCore.pyqtSignal()
    stop_requested=QtCore.pyqtSignal()

    def __init__(self,block,role):
        super().__init__()
        self.block,self.role=block,role
        self.start_requested.connect(self.begin)
        self.stop_requested.connect(self.finish)
        self.panel=None
        self.camera=None
        self.video_timer=None
        self.capture_timer=None
        self.serial=None
        self.pixmap=None
        self.last_size=None
        self.test_index=0
        self._stopping=False
        self._preview_kind=None
        self._last_print=0.0
        self.ffmpeg=None
        self.ffmpeg_thread=None

    @QtCore.pyqtSlot()
    def begin(self):
        self._stopping=False
        try:
            self._make_player()
            if self.role=='tx':
                if self.block._mode=='test':
                    self.capture_timer=QtCore.QTimer(self)
                    self.capture_timer.timeout.connect(self._test_tick)
                    self.capture_timer.start(max(1,round(1000/self.block._fps)))
                    self._test_tick()
                else:
                    self._start_camera()
        except Exception as exc:
            self.block._error='Start failed: '+str(exc)
            print('[Live video] '+self.block._error,flush=True)

    def _make_player(self):
        top=None
        for widget in QtWidgets.QApplication.topLevelWidgets():
            if getattr(widget,'epy_block_1',None) is self.block or getattr(widget,'epy_block_0',None) is self.block:
                top=widget;break
        # The combined software graph shows the received video, so it has one player.
        if self.role=='tx' and top is not None and hasattr(top,'epy_block_0'):
            return
        if self.panel is None:
            self.panel=QtWidgets.QWidget()
            layout=QtWidgets.QVBoxLayout(self.panel)
            self.title=QtWidgets.QLabel('Transmitter: original camera image' if self.role=='tx' else 'Receiver: live video')
            self.title.setStyleSheet('font-size:17px;font-weight:600;padding:4px')
            layout.addWidget(self.title)
            controls=QtWidgets.QHBoxLayout()
            if self.role=='tx':
                self.preview_choice=QtWidgets.QComboBox()
                self.preview_choice.addItems(['Original camera image','Image sent over the air'])
                controls.addWidget(self.preview_choice)
            self.enlarge=QtWidgets.QCheckBox('Fit to window (may look blurry)')
            self.enlarge.setChecked(False)
            controls.addWidget(self.enlarge)
            controls.addStretch(1)
            layout.addLayout(controls)
            self.picture=QtWidgets.QLabel('Waiting for the camera image...' if self.role=='tx' else 'Waiting for received video...')
            self.picture.setAlignment(QtCore.Qt.AlignCenter)
            self.picture.setMinimumSize(480,360)
            self.picture.setSizePolicy(QtWidgets.QSizePolicy.Ignored,QtWidgets.QSizePolicy.Ignored)
            self.picture.setStyleSheet('background:#10151d;color:#dee8f5;font-size:20px')
            layout.addWidget(self.picture,1)
            self.status=QtWidgets.QLabel(self.block.get_status())
            self.status.setWordWrap(True)
            layout.addWidget(self.status)
            if top is not None and hasattr(top,'monitor_tabs_layout_0'):
                top.monitor_tabs_layout_0.addWidget(self.panel)
            else:
                self.panel.setWindowTitle('PlutoSky VTX - live video')
                self.panel.resize(800,650)
                self.panel.show()
        self.video_timer=QtCore.QTimer(self)
        self.video_timer.timeout.connect(self.update_player)
        self.video_timer.start(25)

    @QtCore.pyqtSlot()
    def update_player(self):
        original=self.role=='tx' and self.preview_choice.currentIndex()==0
        kind='original' if original else 'transmitted'
        if kind!=self._preview_kind:
            self._preview_kind=kind;self.serial=None;self.last_size=None
            if self.role=='tx':self.title.setText('Transmitter: original camera image' if original else 'Image sent over the air (the same JPEG as the receiver gets)')
        latest=self.block.get_original_frame() if original else self.block.get_latest_frame()
        if latest and latest[0]!=self.serial:
            self.serial,payload=latest
            image=payload if original else QtGui.QImage.fromData(payload,'JPEG')
            if image.isNull():
                self.block._error='The received image cannot be decoded'
            else:
                self.pixmap=QtGui.QPixmap.fromImage(image)
                self.last_size=None
                if self.role=='rx':self.block.displayed_frames+=1
        size=self.picture.size();render_key=(size.width(),size.height(),self.enlarge.isChecked())
        if self.pixmap is not None and render_key!=self.last_size:
            target=size if self.enlarge.isChecked() else QtCore.QSize(min(size.width(),self.pixmap.width()),min(size.height(),self.pixmap.height()))
            self.picture.setPixmap(self.pixmap.scaled(target,QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation))
            self.last_size=render_key
        status=self.block.get_status()
        self.status.setText(status)
        now=time.monotonic()
        if now-self._last_print>=2.0:  # same status line in the terminal, every 2 s
            self._last_print=now
            print('['+('TX' if self.role=='tx' else 'RX')+' '+time.strftime('%H:%M:%S')+'] '+status,flush=True)

    def _test_tick(self):
        self.block.accept_image(live_test_image(self.test_index,self.block._width,self.block._height))
        self.test_index+=1

    def _start_camera(self):
        name=self.block._camera
        if QtMultimedia is None or name.startswith('/dev/') or (name.lower()=='default' and sys.platform.startswith('linux')):
            self._start_ffmpeg_camera('/dev/video0' if name.lower()=='default' else name)
            return
        devices=QtMultimedia.QCameraInfo.availableCameras()
        if name.lower()=='default':
            if not devices:raise RuntimeError('No camera found: check the connection and that no other program is using it')
            info=QtMultimedia.QCameraInfo.defaultCamera()
            if info.isNull():info=devices[0]
        else:
            info=next((d for d in devices if d.description()==name or d.deviceName()==name),None)
            if info is None:
                raise RuntimeError('Camera not found: '+name+'; available: '+', '.join(d.description() for d in devices))
        self.block._camera_label=info.description()
        self.camera=QtMultimedia.QCamera(info,self)
        self.surface=LiveVideoSurface(self.block._fps,self)
        self._camera_serial=None
        self.capture_timer=QtCore.QTimer(self)
        self.capture_timer.timeout.connect(self.poll_camera)
        self.capture_timer.start(max(10,round(500/self.block._fps)))
        self.surface.problem.connect(self.camera_problem)
        self.camera.setViewfinder(self.surface)
        self.camera.error.connect(lambda code:self.camera_problem(self.camera.errorString() if self.camera else ''))
        self.camera.statusChanged.connect(self.camera_status)
        self._camera_configured=False
        self.camera.load()

    def _start_ffmpeg_camera(self,device):
        """Linux V4L2 capture: ffmpeg decodes the camera to fixed-size RGB24 frames."""
        if shutil.which('ffmpeg') is None:
            raise RuntimeError('ffmpeg not found (sudo apt install ffmpeg), or install python3-pyqt5.qtmultimedia')
        if not os.path.exists(device):
            raise RuntimeError('Camera device not found: '+device)
        w,h=self.block._width,self.block._height
        w-=w%2;h-=h%2
        vf=(f'fps={self.block._fps},scale={w}:{h}:force_original_aspect_ratio=decrease,'
            f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2')
        out=['-vf',vf,'-f','rawvideo','-pix_fmt','rgb24','-']
        attempts=[['-input_format','mjpeg','-video_size','1280x720'],[]]
        self.block._camera_label='V4L2 '+device+' via ffmpeg'
        def run():
            for extra in attempts:
                if self._stopping:return
                cmd=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-f','v4l2',*extra,'-i',device,*out]
                self.ffmpeg=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                size=w*h*3;frames=0
                while not self._stopping:
                    raw=self.ffmpeg.stdout.read(size)
                    if len(raw)<size:break
                    frames+=1
                    self.block.accept_image(QtGui.QImage(raw,w,h,w*3,QtGui.QImage.Format_RGB888).copy())
                proc,self.ffmpeg=self.ffmpeg,None
                if proc.poll() is None:proc.kill()
                err=proc.stderr.read().decode(errors='replace').strip()
                proc.wait()
                if self._stopping:return
                if frames:  # camera ran, then died: report it, do not silently retry
                    self.block._error='Camera stopped: '+(err.splitlines()[-1] if err else 'ffmpeg exited')
                    print('[Live camera] '+self.block._error,flush=True)
                    return
                print('[Live camera] ffmpeg '+(' '.join(extra) or '(default format)')+' failed: '+(err.splitlines()[-1] if err else '?'),flush=True)
            self.block._error='Cannot open camera '+device+' with ffmpeg'
        self.ffmpeg_thread=threading.Thread(target=run,name='v4l2-ffmpeg-camera',daemon=True)
        self.ffmpeg_thread.start()

    def camera_status(self,status):
        if self._stopping:return
        if status==QtMultimedia.QCamera.LoadedStatus and not self._camera_configured:
            self._camera_configured=True
            formats=self.surface.supportedPixelFormats()
            settings=[s for s in self.camera.supportedViewfinderSettings() if s.pixelFormat() in formats]
            if settings:
                # Use an actual supported mode; never force an unsupported camera size.
                def rank(s):
                    size=s.resolution()
                    target_w=max(1280,self.block._width);target_h=max(720,self.block._height)
                    return (size.width()<target_w or size.height()<target_h,abs(size.width()-target_w)+abs(size.height()-target_h),-s.maximumFrameRate())
                self.camera.setViewfinderSettings(min(settings,key=rank))
            QtCore.QTimer.singleShot(0,self.camera.start)

    @QtCore.pyqtSlot(QtGui.QImage)
    def camera_frame(self,image):
        if not self._stopping:self.block.accept_image(image)

    @QtCore.pyqtSlot()
    def poll_camera(self):
        with self.surface._image_lock:latest=self.surface._latest_image
        if latest is not None and latest[0]!=self._camera_serial:
            self._camera_serial=latest[0]
            self.camera_frame(latest[1])

    @QtCore.pyqtSlot(str)
    def camera_problem(self,message):
        if not self._stopping:
            self.block._error='Camera: '+message
            print('[Live camera] '+message,flush=True)

    @QtCore.pyqtSlot()
    def finish(self):
        self._stopping=True
        if self.capture_timer:self.capture_timer.stop()
        if self.video_timer:self.video_timer.stop()
        proc=self.ffmpeg
        if proc is not None and proc.poll() is None:proc.kill()
        if self.camera:
            self.camera.stop()
            self.camera.unload()
            self.camera.deleteLater()
            self.camera=None

import collections
import secrets
from gnuradio import gr


class VideoSource(gr.sync_block):
    """Self-contained camera (Qt on Windows, ffmpeg/V4L2 on Linux) -> JPEG video stream."""
    def __init__(self,source_mode='camera',camera_name='default',video_width=320,
                 video_height=240,video_fps=8,jpeg_quality=65,max_frame_bytes=10000,
                 radio_bitrate=1024000):
        gr.sync_block.__init__(self,name='Camera Live Stream (Qt/JPEG)',in_sig=None,out_sig=[np.uint8])
        self.set_max_output_buffer(65536)
        self.set_max_noutput_items(4096)
        self._consumed_bytes=None
        self._mode,self._camera=str(source_mode),str(camera_name)
        self._width,self._height=int(video_width),int(video_height)
        self._fps,self._quality=int(video_fps),int(jpeg_quality)
        self._max_bytes=int(max_frame_bytes)
        self._radio_bitrate=int(radio_bitrate)
        if self._mode not in ('camera','test') or not 1<=self._fps<=30 or not 10<=self._quality<=90 or min(self._width,self._height)<64 or not 2000<=self._max_bytes<=20000:
            raise ValueError('Invalid video settings')
        if self._fps*((self._max_bytes+4+PAYLOAD-1)//PAYLOAD)*WIRE_SIZE*8>0.85*self._radio_bitrate:
            raise ValueError('The video exceeds the link budget: lower video_fps or max_frame_bytes')
        self._lock=threading.Lock()
        self._queue=collections.deque()
        self._pending=b'';self._position=0
        self._session=0;self._idle=idle_packet(0)
        self._latest=None;self._error='';self._last_frame=0
        self._original=None;self._original_serial=0;self._next_encode=0.0
        self._encode_condition=threading.Condition()
        self._raw_pending=None;self._encoder_stop=threading.Event();self._encoder_thread=None
        self._capture_size=(0,0);self._last_quality=0;self._last_size=0;self._tx_size=(0,0)
        self.oversize_frames=0
        self._camera_label='Opening the default camera' if self._mode=='camera' else 'Software test pattern (not the camera)'
        self.encoded_frames=0;self.dropped_frames=0;self.sent_packets=0;self.encoded_bytes=0
        self._bridge=LiveQtBridge(self,'tx')

    def start(self):
        self._session=secrets.randbits(32)
        self._idle=idle_packet(self._session)
        self._queue.clear();self._pending=b'';self._position=0
        self._error=''
        self._next_encode=0.0
        self._encoder_stop.clear();self._raw_pending=None
        self._encoder_thread=threading.Thread(target=self._encode_loop,name='live-jpeg-encoder',daemon=True)
        self._encoder_thread.start()
        self._bridge.start_requested.emit()
        return True

    def stop(self):
        self._encoder_stop.set()
        with self._encode_condition:self._encode_condition.notify_all()
        if self._encoder_thread:self._encoder_thread.join(timeout=2)
        self._bridge.stop_requested.emit()
        return True

    def accept_image(self,image):
        if image.isNull():return
        with self._lock:
            self._original_serial+=1
            self._original=(self._original_serial,image.copy())
            self._capture_size=(image.width(),image.height())
        with self._encode_condition:
            self._raw_pending=image.copy()
            self._encode_condition.notify()

    def _encode_loop(self):
        while not self._encoder_stop.is_set():
            with self._encode_condition:
                self._encode_condition.wait_for(lambda:self._raw_pending is not None or self._encoder_stop.is_set(),timeout=.1)
                if self._encoder_stop.is_set():break
                image=self._raw_pending;self._raw_pending=None
            if image is not None:self._encode_image(image)

    def _encode_image(self,image):
        try:
            now=time.monotonic()
            if now+0.002<self._next_encode:return
            if not self._next_encode or now-self._next_encode>1.0/self._fps:self._next_encode=now
            self._next_encode+=1.0/self._fps
            image=image.scaled(self._width,self._height,QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation)
            quality=self._last_quality or self._quality
            if self._last_size<self._max_bytes*.75:quality=min(self._quality,quality+5)
            while True:
                buffer=QtCore.QBuffer()
                buffer.open(QtCore.QIODevice.WriteOnly)
                if not image.save(buffer,'JPEG',quality):raise RuntimeError('Qt JPEG encoding failed')
                jpeg=bytes(buffer.data())
                if len(jpeg)<=self._max_bytes:break
                minimum=min(40,self._quality)
                if quality>minimum:quality=max(minimum,quality-5)
                else:
                    if image.width()<=160 or image.height()<=90:
                        self.oversize_frames+=1
                        return
                    image=image.scaled(round(image.width()*.85),round(image.height()*.85),QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation)
            sequence=self.encoded_frames & 0xffffffff
            wire=b''.join(split_unit(jpeg,self._session,sequence))
            with self._lock:
                if len(self._queue)>=1:self._queue.popleft();self.dropped_frames+=1
                self._queue.append(wire)
                self.encoded_frames+=1;self.encoded_bytes+=len(jpeg)
                self._latest=(self.encoded_frames,jpeg)
                self._last_quality=quality;self._last_size=len(jpeg);self._tx_size=(image.width(),image.height())
                self._last_frame=time.monotonic()
        except Exception as exc:
            self._error=str(exc)

    def get_latest_frame(self):
        with self._lock:return self._latest

    def get_original_frame(self):
        with self._lock:return self._original

    def get_status(self):
        if self._error:return self._error
        if self._last_frame and time.monotonic()-self._last_frame>3:return 'Camera image lost: check whether another program is using the camera'
        cw,ch=self._capture_size;tw,th=self._tx_size
        return (f'{self._camera_label} | Original {cw}x{ch} | Over the air {tw}x{th}, target {self._fps} fps'
                f' | JPEG quality {self._last_quality}, {self._last_size/1024:.1f}KB'
                f' | Encoded {self.encoded_frames} | Dropped (overload) {self.dropped_frames} | Too large, not sent {self.oversize_frames}')

    def work(self,input_items,output_items):
        out=output_items[0]
        if self._consumed_bytes is not None:
            # Limit bytes ahead of the actual hardware consumer, even when the OS
            # rounds GNU Radio buffers up to 64 KiB. The radio remains the clock.
            credit=16384+int(self._consumed_bytes())-int(self.nitems_written(0))
            wait_until=time.monotonic()+0.05
            while credit<=0 and time.monotonic()<wait_until:
                time.sleep(0.001)
                credit=16384+int(self._consumed_bytes())-int(self.nitems_written(0))
            if credit<=0:
                return 0
            out=out[:min(len(out),4096,credit)]
        written=0
        while written<len(out):
            if self._position==len(self._pending):
                with self._lock:self._pending=self._queue.popleft() if self._queue else self._idle
                self._position=0;self.sent_packets+=len(self._pending)//WIRE_SIZE
            count=min(len(out)-written,len(self._pending)-self._position)
            out[written:written+count]=np.frombuffer(self._pending,dtype=np.uint8,count=count,offset=self._position)
            written+=count;self._position+=count
        return written
