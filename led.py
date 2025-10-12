# led.py
import time
import RPi.GPIO as GPIO

# Sätt True om LED är aktiv-låg (0% = på, 100% = av). False för vanlig aktiv-hög.
LED_ACTIVE_LOW = False
LED_PIN = 17
PWM_FREQ = 1000

pwm = None
ON_DUTY  = 0   if LED_ACTIVE_LOW else 100
OFF_DUTY = 100 if LED_ACTIVE_LOW else 0

def setup_led():
    global pwm
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(LED_PIN, GPIO.OUT)
    pwm = GPIO.PWM(LED_PIN, PWM_FREQ)
    pwm.start(OFF_DUTY)  # starta släckt

def led_on():
    pwm.ChangeDutyCycle(ON_DUTY)

def led_off():
    pwm.ChangeDutyCycle(OFF_DUTY)

def led_blink(duration=0.25):
    """Enkel, blockerande blink."""
    led_on()
    time.sleep(duration)
    led_off()

def cleanup_led():
    try:
        if pwm is not None:
            pwm.stop()
    except Exception:
        pass
    try:
        GPIO.cleanup()
    except Exception:
        pass
