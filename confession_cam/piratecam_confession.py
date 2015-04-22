import picamera
import RPi.GPIO as GPIO
import threading
import os
import time
import logging
import subprocess
import signal

logging.basicConfig(filename='confession.log', level=logging.DEBUG, format='%(asctime)s %(message)s')
logging.getLogger().addHandler(logging.StreamHandler())

event_start = threading.Event()
event_stop = threading.Event()
#timer = threading.Timer()

MAX_TIME = 120
GPIO_INPUT_BCM = 4 # pin 7
GPIO.setmode(GPIO.BCM) # BCM mode is required to easily control camera LED
GPIO.setup(GPIO_INPUT_BCM, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def event_update():
    if GPIO.input(GPIO_INPUT_BCM) == 1:
        logging.info('Event set - recording allowed')
        event_start.set()
        event_stop.clear()
    else:
        logging.info('Event cleared - recording stopped')
        event_start.clear()
        event_stop.set()

def toggle_cb(channel):
    time.sleep(0.2)
    event_update()

arecord_hdl = None

def audio_record(filename):
    global arecord_hdl
    audio_stop()
    arecord_hdl = subprocess.Popen(['arecord', '-c', '1', '-r', '24000', '-f', 'cd', '-D', 'plughw:1,0', filename]) 

def audio_stop():
    global arecord_hdl
    if arecord_hdl:
        arecord_hdl.send_signal(signal.SIGINT)
        arecord_hdl = None

# Add a callback for GPIO input changes
GPIO.add_event_detect(GPIO_INPUT_BCM, GPIO.BOTH, callback=toggle_cb, bouncetime=100)

# Configure camera and start preview
camera = picamera.PiCamera()
camera.framerate = 25
camera.resolution = (1920, 1080)
camera.led = False

# Make sure initial state of event_start is correct
event_update()

if not os.path.exists('videos'):
    os.makedirs('videos')

contents = os.listdir('videos/')
dir_name = 'videos/%05d' % len(contents)
os.makedirs(dir_name)
logging.info('Folders created: %s' % dir_name)

# Exception handling loop - just try again if something fails
i = 0
while 1:
    try:
        i += 1
        camera.led = False
        video_file = dir_name + '/%05d.h264' % i
        audio_file = dir_name + '/%05d.wav' % i
        event_start.wait()
        logging.info ('Done waiting for start...')
        logging.info('Enabling LED...')
        camera.led = True # LED should only be enabled when recording - not for preview
        camera.start_preview()
        logging.info('Recording to %s' % video_file)
        camera.start_recording(video_file)
        audio_record(audio_file)
        logging.info('Waiting for stop event for up to %d seconds' % MAX_TIME)
        if event_stop.wait(MAX_TIME):
            logging.info('Recording stopped due to event')
        else:
            logging.info('Recording stopped due to timeout (%d seconds)' % MAX_TIME)
        if camera.recording:
            camera.stop_recording()
        audio_stop()
        camera.stop_preview()
        logging.info('Record stopped')
        event_start.clear()
    
    except Exception as e:
        logging.error('ERROR - retrying: %s' % (str(e)))
        time.sleep(1) # Prevents crazy loop and allows for double CTRL-C to quit

camera.close()