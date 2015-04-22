import picamera
import RPi.GPIO as GPIO
import threading
import os
import time
import logging

logging.basicConfig(filename='timelapse.log', level=logging.DEBUG, format='%(asctime)s %(message)s')
logging.getLogger().addHandler(logging.StreamHandler())

event_start = threading.Event()

GPIO_INPUT_BCM = 4 # pin 7
GPIO.setmode(GPIO.BCM) # BCM mode is required to easily control camera LED
GPIO.setup(GPIO_INPUT_BCM, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def event_update():
    if GPIO.input(GPIO_INPUT_BCM) == 1:
        logging.info('Event set - recording allowed')
        event_start.set()
    else:
        logging.info('Event cleared - recording blocked')
        if camera.recording:
            logging.info('...but still recording')
        event_start.clear()

def toggle_cb(channel):
    time.sleep(0.1) # It seems like a small delay can be helpful...
    event_update()

# Add a callback for GPIO input changes
GPIO.add_event_detect(GPIO_INPUT_BCM, GPIO.BOTH, callback=toggle_cb, bouncetime=200)

# Configure camera and start preview
camera = picamera.PiCamera()
camera.framerate = 5
camera.resolution = (1296, 730)
camera.video_stabilization = True
#camera.resolution = (1920, 1080)
camera.start_preview()
camera.led = False

# Make sure initial state of event_start is correct
event_update()

# Exception handling loop - just try again if something fails
# (also folder creation as new folder is required to prevent overwrites) 
while 1:
    try:
        if not os.path.exists('videos'):
            os.makedirs('videos')
        
        contents = os.listdir('videos/')
        dir_name = 'videos/%05d' % len(contents)
        os.makedirs(dir_name)
    
        # Unlimited recording loop
        for filename in camera.record_sequence(
                (dir_name + '/%05d.h264' % i for i in range(1, 99999))):
            camera.led = False
            if not event_start.is_set():
                logging.info('Loop: Blocked')
            event_start.wait()
            camera.led = True # LED should only be enabled when recording - not for preview
            logging.info('Loop: Recording to %s' % filename)
            camera.wait_recording(60)
            logging.info('Loop: Recording complete')
    
    except Exception as e:
        logging.error('ERROR - retrying: %s' % (str(e)))
        time.sleep(1) # Prevents crazy loop and allows for double CTRL-C to quit

camera.close()