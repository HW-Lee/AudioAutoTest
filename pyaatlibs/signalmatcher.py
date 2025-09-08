import numpy as np
from librosa.core import load as audioload
from scipy.fftpack import fft
import matplotlib.pyplot as plt


class SignalMatcher(object):
    FRAME_MILLIS_PER_FEATURE = 20

    def __init__(self, refpath):
        self.refpath = refpath
        self.refsig, self.reffs = audioload(self.refpath, sr=None, mono=True)
        self._gen_feat()

    def _gen_feat(self):
        sig_len = len(self.refsig)
        framesize = int(np.round(self.reffs * SignalMatcher.FRAME_MILLIS_PER_FEATURE / 1000.0))
        nfft = int(2 ** np.ceil(np.log2(framesize)))
        self.feats = np.zeros([nfft / 2, int(np.ceil(sig_len * 1.0 / framesize))])

        frame_sig = np.zeros([framesize])
        for frame_idx in range(self.feats.shape[1]):
            frame_sig[:] = 0
            idx_from = frame_idx * framesize
            idx_to = min([idx_from + framesize, sig_len])
            frame_sig[: idx_to - idx_from] = self.refsig[idx_from:idx_to]
            self.feats[:, frame_idx] = np.abs(fft(frame_sig, nfft))[: nfft / 2]

    def visualize_feat(self, outpath):
        feats = np.array(self.feats)
        feats += 1e-32
        feats = 20 * np.log10(feats)
        plt.imshow(feats, vmax=np.max(feats), vmin=np.max(feats) - 40, cmap="gray", origin="lower")
        plt.colorbar()

        ticks = plt.gca().get_yticks() * 1.0 / feats.shape[0] * self.reffs / 2.0
        ticks = np.array(np.round(ticks), dtype=int)
        plt.gca().set_yticklabels(ticks)
        plt.gca().set_ylabel("frequency (Hz)")
        plt.gca().set_xlabel(
            "frame index ({} ms/frame)".format(SignalMatcher.FRAME_MILLIS_PER_FEATURE)
        )

        xlim = plt.gca().get_xlim()
        plt.gcf().set_size_inches(
            [(xlim[1] - xlim[0]) * SignalMatcher.FRAME_MILLIS_PER_FEATURE / 1000.0, 3]
        )

        plt.savefig(outpath, bbox_inches="tight", pad_inches=0, dpi=300)
        plt.gcf().clear()
