# This file is executed on every boot (including wake-boot from deepsleep)
# It is derived from the stock boot.py

import gc
import uos  # pylint: disable=import-error
import webrepl  # pylint: disable=import-error

webrepl.start()
gc.collect()

if "app.py" in uos.listdir():
    import app

    try:
        app.main()  # pylint: disable=no-member
    except (NameError, AttributeError):
        pass

