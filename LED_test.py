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

    def blink(self,interval = 0.6):
        #Start blinking at the end of a previous cylce, so it doens't interfere
        self.__ledmode = LED.LED_BLINK
        self.__turnledon()
        time.sleep(interval)
        self.__turnledoff()
        time.sleep(interval)

    def error(self,time_on = 0.1, time_off = 1):
        #Start blinking at the end of a previous cylce, so it doens't interfere
        self.__ledmode = LED.LED_ERROR
        self.__turnledon()
        time.sleep(time_on)
        self.__turnledoff()
        time.sleep(time_on)
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
        self.__turnledon()


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
