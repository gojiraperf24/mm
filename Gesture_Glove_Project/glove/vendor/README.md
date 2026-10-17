# Portable speech component

Glove Studio invokes the unmodified eSpeak NG 1.52.0 command-line program as a separate process to render local waveforms. Hindi uses this compact synthetic voice. English normally uses installed Windows speech voices, with the portable engine available for waveform export/fallback.

The runtime in `espeak-ng/` was extracted from the official MSI without a system-wide install:

- [Official release](https://github.com/espeak-ng/espeak-ng/releases/tag/1.52.0)
- [Official language list](https://github.com/espeak-ng/espeak-ng/blob/1.52.0/docs/languages.md)
- [Corresponding source archive](https://github.com/espeak-ng/espeak-ng/archive/refs/tags/1.52.0.zip)

The original source archive is included as `espeak-ng-1.52.0-source.zip`. The component and its notices retain their upstream licenses, including GPL version 3 or later. The CLI/data files are not modified by this project. Preserve this directory, the included source, and license notices when redistributing the transfer package. Its notices also identify third-party runtime components.

Voice naturalness and Hindi pronunciation should be reviewed by the team. The local tests verify valid, nonempty waveforms; they do not claim a human listening test or speaker playback verification.
