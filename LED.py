#!/usr/bin/python3
import time
import threading
import RPi.GPIO as GPIO


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
