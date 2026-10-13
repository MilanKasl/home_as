"""Read-only USB/udev inventory. Does not open serial ports or send bytes."""
import json
from app.communication import usb_inventory, IDENTITY_KEYS

if __name__ == '__main__':
    print(json.dumps([
        {'device': device,
         'identity': {key: props[key] for key in sorted(IDENTITY_KEYS) if key in props},
         'links': props.get('DEVLINKS', ''),
         'driver': props.get('ID_USB_DRIVER')}
        for device, props in usb_inventory()
    ], ensure_ascii=False, indent=2))
