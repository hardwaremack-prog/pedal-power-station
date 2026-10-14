#!/usr/bin/env bash
# Pedal Power Station - Pi Zero 2 W setup. Run on Raspberry Pi OS (Bookworm or newer):
#   sudo ./install.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo "Run with sudo: sudo ./install.sh"; exit 1; fi
HERE="$(cd "$(dirname "$0")" && pwd)"
BOOT=/boot/firmware/config.txt; [[ -f $BOOT ]] || BOOT=/boot/config.txt

echo "== packages"
apt-get update
apt-get install -y python3-venv python3-dev fonts-dejavu-core git \
  python3-spidev python3-gpiozero python3-rpi.gpio

echo "== boot settings (UART to the Pico, SPI for e-paper, power-off signal on GPIO26)"
add_line() { grep -qxF "$1" "$BOOT" || echo "$1" >> "$BOOT"; }
add_line "# Pedal Power Station"
add_line "enable_uart=1"
add_line "dtoverlay=disable-bt"
add_line "dtparam=spi=on"
add_line "dtoverlay=gpio-poweroff,gpiopin=26"
# The serial console would talk over the Pico link - turn it off.
sed -i 's/console=serial0,[0-9]* //' /boot/firmware/cmdline.txt 2>/dev/null || true
systemctl disable --now hciuart 2>/dev/null || true

echo "== app"
mkdir -p /opt/pps /etc/pps /var/lib/pps
python3 -m venv --system-site-packages /opt/pps/venv   # reuse the apt GPIO/SPI libraries
/opt/pps/venv/bin/pip install --upgrade pip
/opt/pps/venv/bin/pip install "$HERE[mesh]"

echo "== Waveshare e-paper library"
if [[ ! -d /opt/pps/e-Paper ]]; then
  # The full repo is large; fetch only the Raspberry Pi Python driver.
  git clone --depth 1 --filter=blob:none --sparse https://github.com/waveshareteam/e-Paper /opt/pps/e-Paper
  git -C /opt/pps/e-Paper sparse-checkout set RaspberryPi_JetsonNano/python
fi
/opt/pps/venv/bin/pip install /opt/pps/e-Paper/RaspberryPi_JetsonNano/python

[[ -f /etc/pps/config.toml ]] || cp "$HERE/config.example.toml" /etc/pps/config.toml
ln -sf /opt/pps/venv/bin/pps-cli /usr/local/bin/pps-cli

cp "$HERE/pps.service" /etc/systemd/system/pps.service
systemctl daemon-reload
systemctl enable pps.service

echo
echo "Done. Reboot once so the UART, SPI and power-off settings take effect:  sudo reboot"
echo "Settings live in /etc/pps/config.toml.  Try:  pps-cli status"
