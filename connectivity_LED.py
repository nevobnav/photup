#!/usr/bin/python3

from scripts import test_internet
from time import sleep
from LED import led_on, led_off
from multiprocessing import Process
import logging

logger = logging.getLogger('myapp')
hdlr = logging.FileHandler('/usr/bin/photup/conn.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.WARNING)


def loop_score(no_of_loop,sleep_time,breakout=True):
    score = 0
    while score <= no_of_loop:
        print(score)
        logger.error(score)
        we_live = test_internet(timeout = 1)
        logger.error('we live equals:'+str(we_live))
        if we_live:
            score+=1
            led_on(LEDpin=4)
            sleep(sleep_time)
        else:
            if breakout:
                score = 100         #Set score to 100 to breakout and go to smaller loop
                led_off(LEDpin=4)
            else:
                score = 0           #Set score to 0 to keep looping
                led_off(LEDpin=4)
                sleep(sleep_time)
    outcome = (score == no_of_loop+1) #True if loop was succesfull, false if breakout
    return outcome


def conn_LED():
    looping = True
    while looping is True:
        med_run = False
        long_run = False
        longest_run = False
        print('start short run..')
        short_run = loop_score(10,5,breakout=False)
        print(short_run)
        if short_run:
            print('starting med run...')
            med_run = loop_score(20,10,breakout=True)
            print('med run:', med_run)
        if med_run:
            print('starting long run ..')
            long_run = loop_score(10,60,breakout=True)
            print(long_run)
        if long_run:
            print('starting longest run ..')
            longest_run = loop_score(10,300,breakout=True)
            print(longest_run)
        while longest_run:
            print('starting longest run loop..')
            longest_run = loop_score(10,900,breakout=True)
        print('end of main looping while')


if __name__ == '__main__':
    led_off(LEDpin=4)
    p = Process(target=conn_LED)
    p.daemon=True
    p.start()
    p.join()
