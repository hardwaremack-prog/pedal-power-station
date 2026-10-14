# Pedal Power Station - Pico 2 firmware settings
# Every pin and limit lives here so the rest of the code never hard-codes them.

# ---------------------------------------------------------------- pins (spec v0.2, section 5)
PIN_PI_UART_TX = 0      # GP0 -> Pi GPIO15 (RX)
PIN_PI_UART_RX = 1      # GP1 <- Pi GPIO14 (TX)
PIN_I2C_SDA = 4         # INA2xx x4 + DS3231 clock
PIN_I2C_SCL = 5
PIN_MOTOR_UART_TX = 8   # UART1 to the motor controller
PIN_MOTOR_UART_RX = 9
PIN_OUT_USB = 10        # load-switch enables
PIN_OUT_13V8 = 11
PIN_OUT_PI = 12
PIN_OUT_LIGHTS = 27
PIN_BTN_MODE = 13       # buttons pull to ground
PIN_BTN_MINUS = 14
PIN_BTN_PLUS = 15
PIN_LCD_CS = 16         # Sharp Memory LCD (SPI0)
PIN_LCD_SCK = 18
PIN_LCD_MOSI = 19
PIN_LCD_DISP = 20
PIN_FRONTLIGHT = 21     # PWM
PIN_BRAKE = 22          # brake-lever cut-off switches, pull to ground when squeezed
PIN_LIGHT_SENSOR = 28   # ADC2, photoresistor divider (higher = brighter)
PIN_PI_HALTED = 26      # Pi GPIO26 goes high once Linux has shut down

# Added after spec v0.2 (Sun Wings and the station-mode dump load):
PIN_WINGS_LOCKED = 2    # reed switch, closed (low) = both Sun Wings folded and latched
PIN_DUMP_LOAD = 3       # MOSFET for the dump resistor that keeps pedal feel when the pack is full

# ---------------------------------------------------------------- sensors
# The pack runs 36-43.8 V. The INA226 named in the spec only reads up to 36 V on its bus pin,
# so the pack-side sensors default to the INA228 (85 V). Set a sensor to "ina226" if you
# fit one on a low-voltage branch.
SENSORS = {
    # name: (i2c address, chip, shunt ohms, max amps)
    "battery": (0x40, "ina228", 0.002, 40.0),   # + = charging, - = discharging
    "solar":   (0x41, "ina228", 0.010, 5.0),    # boost MPPT output
    "motor":   (0x44, "ina228", 0.002, 30.0),   # + = generating into pack, - = assist draw
    "loads":   (0x45, "ina228", 0.010, 10.0),   # all low-voltage converters together
}
RTC_ADDR = 0x68

# ---------------------------------------------------------------- battery
PACK_CELLS = 12            # 12S LiFePO4
PACK_AH = 15.0
PACK_WH = 540.0
CELL_FULL_V = 3.60         # pack considered full at 43.2 V with tiny charge current
CELL_REST_FULL_V = 3.40    # resting voltage that means "really full" for re-syncing
CELL_EMPTY_V = 2.90
FULL_SYNC_AMPS = 0.3       # charge current below this at full voltage -> SOC = 100 %

# ---------------------------------------------------------------- rules
SPEED_CAP_MPH = 15.0
SPEED_FADE_START_MPH = 14.0
RESERVE_PCT = 25.0         # assist stops here; the rest is kept for emergencies
OUTPUT_CUTOFF_PCT = 3.0    # below this, USB / 13.8 V / Pi go off to protect the pack
OUTPUT_RESUME_PCT = 6.0
WH_PER_MILE = 10.0         # flat-ground assist estimate used for "miles left"
PEDAL_TO_PACK_EFF = 0.72   # legs -> pack (generator 0.82 x controller 0.92 x battery 0.95)

# Assist A1-A3: max assist amps.  Harvest H1-H3 and station L1-L5: regen amps (= pedal resistance).
ASSIST_AMPS = (0, 4.0, 8.0, 12.0)
HARVEST_AMPS = (0, 1.0, 2.0, 3.5)
STATION_AMPS = (0, 1.5, 2.5, 3.5, 4.5, 6.0)
BRAKE_REGEN_AMPS = 6.0

# ---------------------------------------------------------------- lights
DUSK_ON = 0.18             # light sensor fraction (0-1) below which lights turn on
DUSK_OFF = 0.26            # ... and above which they turn off again (hysteresis)

# ---------------------------------------------------------------- timing
LOOP_MS = 100              # sensor + rules loop
SCREEN_MS = 1000           # status screen refresh
PI_STATUS_MS = 2000        # status message to the Pi
SAVE_MS = 300_000          # persist SOC and energy counters
PI_HALT_GRACE_MS = 2000    # after the Pi says halted, wait this long before cutting its rail
PI_SHUTDOWN_TIMEOUT_MS = 60_000

# ---------------------------------------------------------------- motor controller
MOTOR_BAUD = 115200
MOTOR_SLAVE_ID = 1
# Values are sent as amps x 10 and mph x 10 - check your controller uses the same scaling.
# Register numbers for the controller's Modbus map. These are PLACEHOLDERS: look them up in
# your controller's own parameter list (for a Phaserunner, Grin's register docs / Phaserunner
# Suite) before riding. Until MOTOR_REGISTERS_VERIFIED is True the firmware never sends
# assist or regen commands - it only reads, and logs that it is in safe mode.
MOTOR_REGISTERS_VERIFIED = False
MOTOR_REG = {
    "speed_x10_mph": None,      # read: vehicle speed
    "assist_limit_amps": None,  # write: max battery amps for assist
    "regen_amps": None,         # write: regen current (resistance)
    "speed_limit_x10_mph": None,# write: controller's own speed cap
}
