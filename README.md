# `pytimefliplib`

A Python library TimeFlip devices v3.

The communication protocol (empirically corrected) is described [here](./protocol_v3_corrected.md).

## Install and use

```bash
pip install --upgrade git+https://github.com/pierre-24/pytimefliplib.git
```

Provides, with [a simple Python API](./pytimefliplib/async_client.py), 
convenient scripts to interact with the device:

- Change its name:
  ```
  $ timeflip-set-name -a 98:07:2D:EE:21:0E MyFlip
  ! Connected to 98:07:2D:EE:21:0E
  ! Password communicated
  ! Changed device name from "TimeFlip" to "MyFlip"
  ```

- Get its status:
  ```
  $ timeflip-check -a 98:07:2D:EE:21:0E
  ! Connected to 98:07:2D:EE:21:0E
  ! Password communicated
  TimeFlip characteristics::
  - Name: MyFlip
  - Firmware: TFv3.1
  - Battery: 83
  - Calibration: 0
  - Current facet: 9
  - Accelerometer vector: 0.832, -0.438, 0.262
  - Status: {'locked': False, 'paused': False, 'auto_pause_time': 0}
  History::
  - Facet=0, during 2 seconds
  - Facet=1, during 712 seconds
  (...)
  ```

The options you have to gives to every scripts are `-a`, the MAC address of the device
and, eventually, `-p`, the password (if it differs from the default password, `000000`)