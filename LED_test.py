#!/usr/bin/python3
import time
import threading
import RPi.GPIO as GPIO

class LED(object):

    LED_OFF = 0
    LED_ON = 1
    LED_BLINK = 2
    LED_ERROR = 3
    LED_FINISH = 4

    FAST_CYCLE = 1

    def __init__(self,led_pin=27):
        #Create threadig event, which can be stopped when exiting program
        self.pin_stop = threading.Event()
        #setup led pin and GPIO
        self.__led_pin = led_pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.__led_pin, GPIO.OUT)

        #Initiaite with LED off
        self.__ledmode = LED.LED_OFF
        self.off()

        #Create thread and keep reference to exit later
        self.__thread = threading.Thread(name='ledthread',target=self.__blink_pin)
        #Start thread (run self.__blink_pin)
        self.__thread.start()


    #These functions describe LED modes. Ledmode is set such that self.__blink_pin
    #knows what the latest mode is.

    def blink(self,time_on = 0.05, time_off = 0.7):
        #Start blinking at the end of a previous cylce, so it doens't interfere
        self.__ledmode = LED.LED_BLINK
        self.__turnledon()
        time.sleep(time_on)
        self.__turnledoff()
        time.sleep(time_off)

    def error(self,time_on = 0.1, time_off = 0.7):
        #Start blinking at the end of a previous cylce, so it doens't interfere
        self.__ledmode = LED.LED_ERROR
        self.__turnledon()
        time.sleep(time_on)
        self.__turnledoff()
        time.sleep(time_off)
        self.__turnledon()
        time.sleep(time_on)
        self.__turnledoff()
        time.sleep(time_on)
        self.__turnledon()
        time.sleep(time_on)
        self.__turnledoff()
        time.sleep(time_off)

    def finish(self):
        #Start blinking at the end of a previous cylce, so it doens't interfere
        self.__ledmode = LED.LED_FINISH
        intervals = [0.05, 0.08, 0.1, 0.15,0.15,0.15, 0.2, 0.2, 0.2, 0.2, 0.25, 0.3, 0.4, 0.5, 0.7]
        off_int = 0.05
        for inter in intervals:
            self.__turnledon()
            time.sleep(inter)
            self.__turnledoff()
            time.sleep(off_int)

    def off(self):
        self.__ledmode = LED.LED_OFF
        self.__turnledoff()
        time.sleep(LED.FAST_CYCLE)

    def on(self):
        self.__ledmode = LED.LED_ON
        self.__turnledon()
        time.sleep(LED.FAST_CYCLE)

    def reset(self):
        self.pin_stop.set()
        self.__thread.join()
        GPIO.cleanup()

    ####PRIVATE METHODS: cannot be called like the ones above#####
    #Switching the LED pin on and off:
    def __turnledon(self):
        pin = self.__led_pin
        GPIO.output(pin, GPIO.HIGH)

    def __turnledoff(self):
        pin = self.__led_pin
        GPIO.output(pin, GPIO.LOW)

    #Workhorse function. Keeps looping and reruns the active state function
    def __blink_pin(self):
        while not self.pin_stop.is_set():
            if self.__ledmode == LED.LED_ON:
                self.on()
            if self.__ledmode == LED.LED_OFF:
                self.off()
            if self.__ledmode == LED.LED_ERROR:
                self.error()
            if self.__ledmode == LED.LED_BLINK:
                self.blink()
            if self.__ledmode == LED.LED_FINISH:
                self.finish()













def blink_thread():
    t = threading.Thread(name='blink_thread',target=led_control)
    t.blink = True
    t.error = False
    t.finish = False
    t.start()
    return t

def led_control():
    LEDpin = 27
    blink_interval = 0.7
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(LEDpin,GPIO.OUT)
    while:
        GPIO.output(LEDpin,GPIO.HIGH)
        time.sleep(blink_interval)
        GPIO.output(LEDpin,GPIO.LOW)
        time.sleep(blink_interval)
    return

x = blink_thread()

#END TEST SECTION
def led_on(LEDpin = 27):
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(LEDpin,GPIO.OUT)
    GPIO.output(LEDpin,GPIO.HIGH)
    print('LED on')
    return


def start_blink():
    t = threading.Thread(target = led_blink)
    t.start()
    return t

def start_error():
    t = threading.Thread(target = led_error)
    t.start()
    return t

def stop_led(t):
    t.do_led_action = False
    t.join()
    return

def led_blink(interval = 0.5):
    LEDpin = 27
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(LEDpin,GPIO.OUT)
    t = threading.currentThread()
    while getattr(t, "do_led_action", True):
        GPIO.output(LEDpin,GPIO.HIGH)
        time.sleep(interval)
        GPIO.output(LEDpin,GPIO.LOW)
        time.sleep(interval)
    print('Stopping blink thread')
    led_off()
    return

def led_off(LEDpin = 27):
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(LEDpin,GPIO.OUT)
    GPIO.output(LEDpin,GPIO.LOW)
    print('LED off')
    return

def led_error(interval = 0.5):
    LEDpin = 27
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(LEDpin,GPIO.OUT)
    t = threading.currentThread()
    while getattr(t, "do_led_action", True):
        GPIO.output(LEDpin,GPIO.HIGH)
        time.sleep(interval/2)
        GPIO.output(LEDpin,GPIO.LOW)
        time.sleep(interval/2)
        GPIO.output(LEDpin,GPIO.HIGH)
        time.sleep(interval/2)
        GPIO.output(LEDpin,GPIO.LOW)
        time.sleep(interval/2)
        GPIO.output(LEDpin,GPIO.HIGH)
        time.sleep(interval/2)
        GPIO.output(LEDpin,GPIO.LOW)
        time.sleep(interval/2)
        GPIO.output(LEDpin,GPIO.HIGH)
        time.sleep(interval/2)
        GPIO.output(LEDpin,GPIO.LOW)
        time.sleep(interval*3)
    print('Error blink')
    return

def led_succes(LEDpin = 27):
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(LEDpin,GPIO.OUT)
    intervallist = [.04,.06,.08,.09,.1,.2,.4,.6,.7,.8]
    repeats = [4,4,4,3,3,2,2,2,1,1]
    repeat_ix = 0
    for interval in intervallist:
        reps = 0
        while reps<repeats[repeat_ix]:
            GPIO.output(LEDpin,GPIO.HIGH)
            time.sleep(interval)
            GPIO.output(LEDpin,GPIO.LOW)
            time.sleep(interval)
            reps += 1
        repeat_ix +=1
    led_on()
    return
