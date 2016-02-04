import logging
import time
import sys

import mks

def main():
    log_file_path = 'mks.log'

    # Setup loggers
    log_handle_console = logging.StreamHandler()
    log_handle_console.setLevel(logging.INFO)
    log_format_console = logging.Formatter(fmt='%(asctime)s [%(levelname)-5s] %(name)s: %(message)s', datefmt='%H:%M:%S')
    log_handle_console.setFormatter(log_format_console)

    log_handle_file = logging.FileHandler(log_file_path)
    log_handle_file.setLevel(logging.DEBUG)
    log_format_file = logging.Formatter(fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%Y%m%d %H:%M:%S')
    log_handle_file.setFormatter(log_format_file)
    
    root_logger = logging.getLogger(__name__)
    mks_logger = logging.getLogger(mks.__name__)
    
    for logger in [root_logger, mks_logger]:
        logger.handlers = []
        logger.setLevel(logging.DEBUG)
        logger.addHandler(log_handle_console)
        logger.addHandler(log_handle_file)
        
    root_logger.info("python {}".format(sys.version))

    m = mks.MKSSerialMonitor('COM3')
    
    # Wait for start of MKS data
    root_logger.info("Waiting for MKS...")
    m.wait()
    
    n = m.get_state()
    
    with open('mks.csv', 'a') as f:
        f.write('# ' + ', '.join(n.keys()) + '\n')
    
        while True:
            b = m.get_state()
            
            if b != n:
                print b
                f.write(', '.join([str(x) for x in b.values()]) + '\n')
                
                n = b
                
            time.sleep(1)

if __name__ == "__main__":
    main()
