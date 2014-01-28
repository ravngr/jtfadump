import instrument
import pid
import time
import threading

def main():
    psu = instrument.PowerSupply("ASRL4::INSTR")
    psu_lock = threading.Semaphore()
    temp = instrument.TemperatureLogger("COM3")
    temp_lock = threading.Semaphore()

    print psu.get_id()
    psu.set_output(True)

    def get_temp():
        temp_lock.acquire()
        t = temp.get_temp(2)
        temp_lock.release()
        print('R: ' + str(t))
        return t

    def set_volt(v):
        psu_lock.acquire()
        print('W: ' + str(v))
        psu.set_voltage(v)
        psu_lock.release()

    Kp = 1.0
    Ki = 0.05
    Kd = 0.5
    target = 55.0
    interval = 3.0

    p = pid.PID(get_temp, set_volt, 0, target, pid.Limit(0, 5), Kp, Ki, Kd, interval)

    t = temp.get_temp(2)
    ramp_time = 60.0
    ramp_steps = 10
    dt = (target - t) / ramp_steps

    p.start()

    #while t < target:
    #    t += dt
    #    p.set_target(t)
    #    print('T: ' + str(t))
    #    time.sleep(ramp_time / ramp_steps)

    #print('T: Fixed')

    while True:
        time.sleep(1)

if __name__ == '__main__':
    main()
