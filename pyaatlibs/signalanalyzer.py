import numpy as np


def sort_values(signal):
    signal = np.array(signal)
    idices = np.argsort(signal, axis=0)
    return zip(list(idices), list(signal[idices]))


def find_peaks(signal):
    peaks = []
    max_idx = np.argmax(signal)
    peaks.append((max_idx, signal[max_idx] + 1e-50))
    return peaks
