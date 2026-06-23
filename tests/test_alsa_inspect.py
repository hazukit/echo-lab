from __future__ import annotations

import unittest

from echolab.devices.alsa import parse_arecord_list, parse_hw_params, render_inspect_markdown


class AlsaInspectTest(unittest.TestCase):
    def test_parse_arecord_list_detects_respeaker_style_device(self) -> None:
        output = """
**** List of CAPTURE Hardware Devices ****
card 2: ArrayUAC10 [ReSpeaker 4 Mic Array (UAC1.0)], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
"""

        devices = parse_arecord_list(output)

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].alsa_hw, "hw:2,0")
        self.assertEqual(devices[0].alsa_plughw, "plughw:2,0")
        self.assertEqual(devices[0].device_name, "ReSpeaker 4 Mic Array (UAC1.0)")

    def test_parse_arecord_list_detects_japanese_locale_output(self) -> None:
        output = """
**** ハードウェアデバイス CAPTURE のリスト ****
カード 2: ArrayUAC10 [ReSpeaker 4 Mic Array (UAC1.0)], デバイス 0: USB Audio [USB Audio]
  サブデバイス: 1/1
  サブデバイス #0: subdevice #0
"""

        devices = parse_arecord_list(output)

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].alsa_hw, "hw:2,0")
        self.assertEqual(devices[0].alsa_plughw, "plughw:2,0")
        self.assertEqual(devices[0].device_name, "ReSpeaker 4 Mic Array (UAC1.0)")

    def test_parse_hw_params_extracts_native_values(self) -> None:
        output = """
HW Params of device "hw:2,0":
--------------------
FORMAT: S16_LE
CHANNELS: 6
RATE: 16000
"""

        native_format, native_rate, native_channels, formats, rates, channels = parse_hw_params(output)

        self.assertEqual(native_format, "S16_LE")
        self.assertEqual(native_rate, 16000)
        self.assertEqual(native_channels, 6)
        self.assertEqual(formats, ("S16_LE",))
        self.assertEqual(rates, (16000,))
        self.assertEqual(channels, (6,))

    def test_render_inspect_markdown_handles_no_devices(self) -> None:
        rendered = render_inspect_markdown([])

        self.assertIn("No ALSA capture devices", rendered)
