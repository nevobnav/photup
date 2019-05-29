#!/usr/bin/python3

from scripts import test_internet
from time import sleep
from LED import *
from multiprocessing import Process
import logging

logger = logging.getLogger('myapp')
hdlr = logging.FileHandler('/usr/bin/photup/conn.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.WARNING)


def loop_score(no_of_loop,sleep_time,led,breakout=True):
    score = 0
    while score <= no_of_loop:
        print(score)
        logger.error(score)
        we_live = test_internet(timeout = 1)
        logger.error('we live equals:'+str(we_live))
        if we_live:
            score+=1
            led.on()
            sleep(sleep_time)
        else:
            if breakout:
                score = 100         #Set score to 100 to breakout and go to smaller loop
                led.off()
            else:
                score = 0           #Set score to 0 to keep looping
                led.off()
                sleep(sleep_time)
    outcome = (score == no_of_loop+1) #True if loop was succesfull, false if breakout
    return outcome


def conn_LED(led):
    looping = True
    while looping is True:
        med_run = False
        long_run = False
        longest_run = False
        print('start short run..')
        short_run = loop_score(10,5,led,breakout=False)
        print(short_run)
        if short_run:
            print('starting med run...')
            med_run = loop_score(20,10,led,breakout=True)
            print('med run:', med_run)
        if med_run:
            print('starting long run ..')
            long_run = loop_score(10,60,led,breakout=True)
            print(long_run)
        if long_run:
            print('starting longest run ..')
            longest_run = loop_score(10,300,led,breakout=True)
            print(longest_run)
        while longest_run:
            print('starting longest run loop..')
            longest_run = loop_score(10,900,led,breakout=True)
        print('end of main looping while')


if __name__ == '__main__':
    led = LED(led_pin=4)
    led.reset()
    led.off()
    conn_LED(led)
