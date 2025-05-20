# ToxMox's Pan Zoomer for OBS Studio

A powerful Python script for OBS Studio that enables smooth mouse-controlled panning and zooming for display sources. Track your mouse position to control which part of your content is displayed, with customizable zoom transition speed.

**Version: 10.1.2**

## Features

- **Dual Configuration Support**: Control two different sources independently with separate settings
- **Direct 1:1 Mouse Control**: Pan any source by moving your mouse - the source follows your cursor in real-time
- **Customizable Zoom**: Easily zoom in/out with configurable levels from 1x to 5x
- **Smooth Transitions**: Simple smooth transitions when toggling zoom with configurable durations
- **Multi-Monitor Support**: Enhanced detection and support for multiple displays with proper monitor selection
- **Performance Optimized**: Configurable update frequency (30-240 FPS)
- **Flexible Viewport Definition**: Define the panning area using a color source or use scene dimensions directly
- **Hotkey Control**: Toggle panning and zooming on/off using customizable OBS hotkeys for each configuration
- **Direct Source Mode**: Support for plugin sources
- **Offset Support**: Allow changing the mouse tracking center point inside the viewport

Script settings example:

<img src="https://github.com/user-attachments/assets/7d63a020-3707-4e5d-840a-ab2a1a312202" width="300px">

Quick demo:

https://github.com/user-attachments/assets/f048b893-2e64-43ee-886c-bb458b5cda24



## Requirements

- OBS Studio 31.0+
- Python version 3.12.10 x64 or compatible
- Tested with Windows 11

## Installation

1. Download the `ToxMoxPanZoomer.py` script from this repository
2. In OBS Studio, go to **Tools** → **Scripts**
3. In the Python Settings tab, ensure your Python installation is properly configured
4. In the Scripts tab, click the "+" button and select the downloaded script
5. The script is now installed and ready to configure

## Configuration

### Global Settings
- **Update Frequency**: Set the refresh rate for mouse tracking (30-240 FPS)
- **Refresh Scenes and Sources**: Button to refresh all dropdown lists if sources change

### Configuration 1 & 2
Each configuration allows you to control a separate source with these settings:

1. **Enable Config**: Master switch for this configuration set
2. **Target Scene**: Select which scene contains your sources
3. **Target Source**: Select which source you want to pan and zoom
4. **Viewport Source**: Either:
   - Select a Color Source that defines the panning area
   - Use "Use Scene Dimensions" to use the entire scene as the viewport
5. **Target Monitor**: Choose which monitor to track mouse movement on
6. **Offset X/Y**: Fine-tune the panning position with pixel offsets
7. **Zoom Level**: Set your desired zoom level (1x to 5x)
8. **Transition Durations**: Configure separate durations for zoom-in and zoom-out animations

## Usage

1. After configuration, enable the desired config(s) with the **Enable Config** checkbox
2. Set up hotkeys in OBS Settings → Hotkeys for:
   - **Toggle ToxMox Pan Zoomer - Config 1 - Panning**: Starts/stops mouse tracking for Config 1
   - **Toggle ToxMox Pan Zoomer - Config 1 - Zooming**: Activates/deactivates zoom for Config 1
   - **Toggle ToxMox Pan Zoomer - Config 2 - Panning**: Starts/stops mouse tracking for Config 2
   - **Toggle ToxMox Pan Zoomer - Config 2 - Zooming**: Activates/deactivates zoom for Config 2

When panning is active, your mouse position determines which part of the source is shown within the viewport area. Zooming works in conjunction with panning and scales the content around your mouse position.

**Important**: Panning must be activated with hotkey before Zooming hotkey works.

## Setup Instructions

1. Select **Target Scene**, **Target Source** to Pan/Zoom, **Viewport Source** from dropdowns
2. The script will set target source's **Positional Alignment** to **Center** (via Edit Transform)
3. Viewport Source needs Top Left setting for Positional Alignment (this is default when adding sources)
4. Select the **Target Monitor** to track the mouse on
5. Adjust offset values to shift from center the Target Source panning if desired
6. Enable **Config 1 and/or Config 2** and set **Zoom Level** (1x-5x)
7. Configure **Transition Durations** and **Update Frequency**
8. Use hotkeys to toggle panning/zooming (configure in OBS Settings - Hotkeys)
9. Panning must be activated with hotkey before Zooming hotkey works

## Tips

- You can now control two different sources independently using Config 1 and Config 2
- The "Use Scene Dimensions" option eliminates the need to create a separate color source for the viewport
- If you experience alignment issues, the script will warn you with a message to set the viewport source alignment to Top Left
- Set 0 seconds for transition duration if you prefer instant zooming
- If you experience ghosting/stutter, try increasing the Update Frequency
- For plugin sources, the script will automatically detect the appropriate properties to modify

## Troubleshooting

- If OBS crashes on startup, check your Python installation is compatible
- If viewport alignment is incorrect, you'll see a warning in the script UI - set the viewport source alignment to Top Left in Edit Transform
- If sources aren't appearing in dropdowns, use the "Refresh Scenes and Sources" button

## Acknowledgements

- Huge thanks to Jhuderis of BEACN who inspired me to make this script, gave me feature ideas, and helped test. Check out https://www.beacn.com/ for some awesome audio equipment geared towards streamers!
- This script was inspired by https://github.com/BlankSourceCode/obs-zoom-to-mouse
- I am not a programmer. Just a very technical person. This script was generated largely by AI.

## License

```
MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
