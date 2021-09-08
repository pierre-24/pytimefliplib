# (Corrected) data transfer protocol sheet

Based on <https://github.com/DI-GROUP/TimeFlip.Docs/blob/master/Hardware/BLE_device_commutication_protocol_v3.0_en.md>.



Timeflip uses the [Bluetooth Low Energy](https://en.wikipedia.org/wiki/Bluetooth_Low_Energy) protocol.
It seems to use *little endian* everywhere.

## Services

The chip exposes 3 services:

+ Device information (`0x180a`),
+ Battery service (`0x180f`),
+ Timeflip (custom UUID).


## Characteristics

The generic characteristics are listed in the table below.
UUID for those characteristic is `0000XXXX-0000-1000-8000-00805f9b34fb`, where `XXXX` depends on the characteristic.
Property may be `R` (reading), `W` (writting) and/or `N` (notification).

Characteristic's name | UUID (`0xXXX`) | Size | Properties | Note
----------------------|--------------|------|------------|-----
Firmware revision | `0x2a26` | 6 | R | Value is `0x544676332E31` (ASCII string)
Battery level | `0x2a19` | 1 | R, N (?) | Value ranges from 0 to 100


The specific timeflip's characteristics are listed in the table below.
UUID for those characteristic is `f119XXXX-71a4-11e6-bdf4-0800200c9a66`.

Characteristic's name | UUID (`0xXXXX`) | Size | Properties | Note
----------------------|--------------|------|------------|-----
Accelerometer vector | `0x6f51` | 6 | R | Accelerometer vector: 3 signed two bytes numbers (x, y and z), ranging from -32768 (-2G) to 32768 (+2G).
Facet | `0x6f52` | 1 | R, N | Facet value, ranges between 0 and 47.
Command output | `0x6f53` | 21  | R | *see below*
Command input | `0x6f54` | 21  | R, W | *see below*
Double tap | `0x6f55` | 1 | N (?) | *reserved for future use*
Calibration version | `0x6f56` | 4 | R, W | Number used as a synchronisation token between a client and the Timeflip device. Default is zero, and it is reset to default if battery is pulled out or the reset (`0x03`) command is issued.
Password | `0x6f57` | 6 | W | Default password is `000000` (encoded in ASCII).

Writing password in `0x6f57` is **mandatory** before any other action. 

## Commands (require password)

To do specific action with the TimeFlip, one can use different command.
A command is one byte long (`0xXX`), but can have argument(s). 
The whole thing (command + arguments) have to be written in `0x6f54`.
Reading `0x6f54` after writting a command results in a two byte response of the form `0xXXYY`, where `XX` is the command and `YY` is a result code: `YY`=`02` if the command was executed, `01` if there was an error. 
If there is an output, it is to be read in `0x6f53`.

### Available commands

Command (`0xXX`) | Name | Arguments | Output (in `0x6f53`) | Note
-----------------|------|-----------|----------------------|------
`0x01` | History read out | *no* | History packages | *See below*
`0x02` | History delete | *no* | *no* | Clear all history packages
`0x03` | Calibration reset | *no* | *no* | Reset calibration number and facets numbers
`0x04` | Lock | `0x01` (lock on) or `0x02` (lock off) | *no* | Lock the device on the current facet, which is not changed if turned (the new face is notified when lock is off, if any)
`0x05` | Auto-pause | `0xXXXX`: two bytes number representing the number of minutes | *no* | Automatically set the time count on pause after the given number of minutes
`0x06` | Pause | `0x01` (pause on) or `0x02` (pause off) | *no* | Facet continue to be notified, but in history, facet value will be 63.
`0x10` | Status request | *no* | `0xXXYYZZZZ` (4 bytes), where `XX` is `0x01` if device is locked (`0x02` if not), `YY` is `0x01` if pause is set (`0x02` if not) and `ZZZZ` is the auto-pause timer (2 bytes) | -
`0x15` | Device name | `0xXXYY...`, where `XX` is the number of characters that the name contains (max 19) and `YY..` is the device name (ASCII-encoded) | no | -
`0x30` | Set new password | `0xXXXXXXXXXXXX`: 6 bytes ASCII-encoded string | *no* | -

`0x50` (reset firmware) is also available, but was not tested.
 
### About history
 
History is read from packages of 21 bytes (maximum size of the `0xf653` characteristic).
Every package contains 7 history blocks of 3 bytes each.
The structure of a history block is the following:
 
Bit number | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 
-----------|---|---|---|---|---|---|---|---|---|---|----|----|----|----|----|----|----|----|----|----|----|----|----|----
Byte number| 0 |   |   |   |   |   |   |   | 1 |   |    |    |    |    |    |    | 2
Duration   | x | x | x | x | x | x | x | x | x | x | x  | x  | x  | x  | x  | x  |    |    |    |    |    |    | x  | x
Facet value|   |   |   |   |   |   |   |   |   |   |    |    |    |    |    |    | x  | x  | x  | x  | x  | x 


Thus, the two first bytes (plus the additional 2 last bytes) contains the duration (in second) during which the facet was up.
The facet is in the last byte, but start at position 16 and end at position 21 (included).

To get all the history packages, continuously read value of `0x6f53`, until you get a package full of zeros.
Then, the penultimate (the package before the full-zeros one) contains the number of sent blocks in its two first bytes (website claim that the device only stores 1166 flips, thus two bits are not needed).

**According to documentation**, the facets should be inside the 6 last bits, but somewhere, something is ensuring little endian, thus resulting in this weird scheme.

