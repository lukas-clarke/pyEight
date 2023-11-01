# pyEight #
This is python code to interact with Eight Sleeps new OAuth2 API

This work is now wrapped into a Home Assistant integration at https://github.com/lukas-clarke/eight_sleep

I will likely be maintaining that repo over this one.

## Introduction ##
Python code to set temperature using the Eight Sleep API

### Thanks ###
Thanks to gitgub user @mezz64 for developing the initial pyEight python library. 

## Requirements ##

- python >= 3.11
- aiohttps >= 2.0
- asyncio
- httpx
### Authentication ###
Additionally to get the OAuth2 login to work you need:

- client_id
- client_secret
- user email
- user password

To get the client_id and client_secret you can setup a packet capture and a mitm CA to get the unencrypted traffic from your app. You can also decompile the APK to get the values.

## Usage ##
As of now this code can only be used to set the temperature of your Eight Sleep device.  
An example tests case:

```commandline
from pyeight.eight import EightSleep
import time
import asyncio

async def test_device_temperature():
    eight = EightSleep("<email>", "<password>", "<client_id>",
                       "<client_secret>")
    await eight.start()
    print("Set heating levels")
    await eight.set_heating_level(50, "<user1>")
    await eight.set_heating_level(50, "<user2>")
    await eight.set_heating_level(50, "left")
    await eight.set_heating_level(50, "right")
    time.sleep(5) # pause to check device was set
    print("Turning off sides")
    await eight.turn_off_side("<user1>")
    await eight.turn_off_side("<user2>")

    print("Set heating levels with duration")
    await eight.set_heating_and_duration_level(50, 1000, "<user1>")
    await eight.set_heating_and_duration_level(50, 1000, "<user2>")
    await eight.set_heating_and_duration_level(50, 1000, "left")
    await eight.set_heating_and_duration_level(50, 1000, "right")
    time.sleep(5)  # pause to check device was set
    print("Turning off sides")
    await eight.turn_off_side("left")
    await eight.turn_off_side("right")

asyncio.run(test_device_temperature())
```

## TODO ##

- Add in more detailed documentation on how to get the client_id and client_secret
- Implement more functionality from EightSleep API. Would maybe be helpful to merge this with work from @mezz64 
    - NOTE: I only use the set temperature functionality. So unless there is an actual desire for more functionality I likely won't add it. I don't want to maintain unused code for and undocumented API, that will likely change in the future.
- Port this to Home Assistant. Since I use Home Assistant, that is my desired end target for this code.