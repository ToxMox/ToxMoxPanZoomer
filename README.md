# ToxMox's Pan Zoomer for OBS Studio

A powerful Python script for OBS Studio that enables smooth mouse-controlled panning and zooming for display sources. Track your mouse position to control which part of your content is displayed, with customizable zoom transition speed.

**Version: 10.4.9**

## Features

- **Dual Configuration Support**: Control two different sources independently with separate settings
- **Direct 1:1 Mouse Control**: Pan any source by moving your mouse - the source follows your cursor in real-time
- **Customizable Zoom**: Easily zoom in/out with configurable levels from 1x to 5x
- **Smooth Transitions**: Simple smooth transitions when toggling zoom with configurable durations
- **Multi-Monitor Support**: Enhanced detection and support for multiple displays with proper monitor selection
- **Performance Optimized**: Configurable update frequency (30-240 FPS)
- **Flexible Viewport Definition**: Define the panning area using a color source or use scene dimensions directly
- **Hotkey Control**: Toggle panning, zooming, deadzone, and pause using customizable OBS hotkeys for each configuration
- **Direct Source Mode**: Support for plugin sources
- **Offset Support**: Allow changing the mouse tracking center point inside the viewport
- **Deadzone Feature**: Create a rectangular area where the mouse doesn't cause panning until pushed to the edges
- **Pause Feature**: Temporarily freeze panning and zooming while keeping the feature enabled
- **Collapsible UI Sections**: Streamlined interface with collapsible sections for better organization

Script settings example:

<img src="https://github.com/user-attachments/assets/7d63a020-3707-4e5d-840a-ab2a1a312202" width="300px">

Quick basic demo (just shows simple panning and zooming, I'll make some more demo videos eventually showing Deadzone, Offsets, and Pause features etc.):

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
9. **Deadzone Settings**:
   - Enable/disable deadzone functionality
   - Set horizontal and vertical deadzone percentages
   - Configure transition duration when disabling deadzone

### Global Settings
- **Update Frequency**: Set the refresh rate for mouse tracking (30-240 FPS)
- **Refresh Scenes and Sources**: Button to refresh all dropdown lists if sources change

## Setup and Usage

1. Select **Target Scene**, **Target Source** to Pan/Zoom, **Viewport Source** from dropdowns.
2. The script will set target source's **Positional Alignment** to **Center** (via Edit Transform)
3. Viewport Source needs Top Left setting for Positional Alignment (this is default when adding sources)
4. Select the **Target Monitor** to track the mouse on.
5. Adjust **Offset X/Y** values to shift the panning center if desired.
6. Configure **Deadzone** percentages to create an area where mouse movement doesn't affect panning.
7. Enable **Config 1 and/or Config 2** and set **Zoom Level** (1x-5x)
8. Configure **Transition Durations** for zoom and deadzone transitions.
9. Set **Update Frequency** in Global Settings for smoother or more efficient performance.
10. Use hotkeys to toggle features (configure in OBS Settings - Hotkeys):
    - **Toggle ToxMox Pan Zoomer - Config # - Panning**
      Enables/disables mouse tracking (must be enabled first)
    - **Toggle ToxMox Pan Zoomer - Config # - Zooming**
      Enables/disables zoom with smooth transitions
    - **Toggle ToxMox Pan Zoomer - Config # - Deadzone**
      Creates a non-responsive area around mouse position
    - **Toggle ToxMox Pan Zoomer - Config # - Pause**
      Freezes current position regardless of mouse movement
11. Note: Panning must be activated with hotkey before other features will work

When panning is active, your mouse position determines which part of the source is shown within the viewport area. Zooming works in conjunction with panning and scales the content around your mouse position.

## Tips

- You can now control two different sources independently using Config 1 and Config 2
- The "Use Scene Dimensions" option eliminates the need to create a separate color source for the viewport
- If you experience alignment issues, the script will warn you with a message to set the viewport source alignment to Top Left
- Set 0 seconds for transition duration if you prefer instant zooming
- If you experience ghosting/stutter, try increasing the Update Frequency
- For plugin sources, the script will automatically detect the appropriate properties to modify
- Use the Deadzone feature when you want more stable panning with less sensitivity to small mouse movements
- The Pause feature is useful when you need to temporarily freeze the current view while keeping panning enabled
- Collapsible UI sections help keep the interface organized - you can expand only the sections you need
- The Deadzone % settings refer to the percent from center to edge of the full Target Source. I'd like to make this use the Viewport Source instead for the calculation but I couldn't get it to work that way. (if you're a genius python person feel free to tell me how to make that work)

## Troubleshooting

- If OBS crashes on startup, check your Python installation is compatible
- If viewport alignment is incorrect, you'll see a warning in the script UI - set the viewport source alignment to Top Left in Edit Transform
- If sources aren't appearing in dropdowns, use the "Refresh Scenes and Sources" button

## Acknowledgements

- Huge thanks to Jhuderis of BEACN who inspired me to make this script, gave me feature ideas, and helped test. Check out https://www.beacn.com/ for some awesome audio equipment geared towards streamers!
- This script was inspired by https://github.com/BlankSourceCode/obs-zoom-to-mouse
- I am not a programmer. Just a very technical person who kind of undestands code. This script was generated largely by AI.

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
