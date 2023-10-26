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