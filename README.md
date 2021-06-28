# epicspythm1176

For use with the Metrolab THM-1176 probe, `pcaspy_server.py` makes connection with the probe and broadcasts the measured values as EPICS values.

Interface to the probe derived from [pyTHM1176](https://github.com/Hyperfine/pyTHM1176)

## Requirements

* [PCASpy](https://github.com/paulscherrerinstitute/pcaspy)
* [python USBTMC](https://github.com/python-ivi/python-usbtmc) or [PyVISA](https://github.com/pyvisa/pyvisa)
* [NumPy](https://numpy.org/)

Note that the `pcaspy_server.py` uses the usbtmc interface, but it should be simple to switch to a pyvisa based one.

## List of available EPICS variables

EPICS name | Description
-----------|------------
METROLAB:Block | Length of block captures
METROLAB:Average | Number of averaged values per block
METROLAB:Period | Length of time between triggers for a measurement
METROLAB:Trigger | Trigger source
METROLAB:Range | Range used by the probe
METROLAB:B | Total magnetic field (read only)
METROLAB:Bx | Magnetic field in the x-direction (read only)
METROLAB:By | Magnetic field in the y-direction (read only)
METROLAB:Bz | Magnetic field in the z-direction (read only)
METROLAB:dt | Estimated time between measurements (read only)
METROLAB:dBx | Estimated change in magnetic field in the x-direction (read only)
METROLAB:dBy | Estimated change in magnetic field in the y-direction (read only)
METROLAB:dBz | Estimated change in magnetic field in the z-direction (read only)
METROLAB:Timer | Time between new values published via EPICS
METROLAB:Connected | Indicates connected/disconnected state

## Installation

No pip or conda installs are ready yet. Install the listed requirements and manually copy the files to a folder and run the `pcaspy_server.py` file.

## Disclaimer

While the communication with the device works, there is no automated testing and most commands have been briefly tested. However, bugs and unexpected behaviour are both very possible. Please open an issue if you encounter something!
