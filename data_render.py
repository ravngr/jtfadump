import argparse
import os
import re

import numpy as np
import matplotlib.pyplot as plt
import mpl_toolkits.mplot3d

import scipy.io as sio

def main():
    parse = argparse.ArgumentParser(description='Experiment System')
    parse.add_argument('directory', help='Directories to search for mat files', nargs='+')

    args = parse.parse_args()

    # Import data from mat file
    files = []

    for dir in args.directory:
        files.extend([os.path.join(dir, file) for file in os.listdir(dir)])

    mat_pattern = re.compile('.*\.mat$')
    mat_files = filter(mat_pattern.match, files)

    pulse_time = []
    pulse_data_in = {}
    pulse_data_out = {}

    for mat_file in mat_files:
        mat_data = sio.loadmat(mat_file)

        if len(pulse_time) == 0:
            pulse_time = np.rot90(mat_data['result_scope_time'], -1)

        for idx, temperature in enumerate(mat_data['result_sensor_temperature'][0]):
            if temperature in pulse_data_out:
                pulse_data_in[temperature].append(mat_data['result_scope_in'][idx])
                pulse_data_out[temperature].append(mat_data['result_scope_out'][idx])
            else:
                pulse_data_in[temperature] = [mat_data['result_scope_in'][idx]]
                pulse_data_out[temperature] = [mat_data['result_scope_out'][idx]]

    pulse_data_in = {key: np.mean(value, axis=0) for (key, value) in pulse_data_in.iteritems()}
    pulse_data_out = {key: np.mean(value, axis=0) for (key, value) in pulse_data_out.iteritems()}

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    colormap = plt.cm.gist_rainbow
    ax.set_color_cycle([colormap(i) for i in np.linspace(0, 0.9, len(pulse_data_out))])

    for (temperature, waveform) in pulse_data_out.iteritems():
        plt.plot(pulse_time, waveform, zs=temperature)

    plt.show()


if __name__ == "__main__":
    main()
