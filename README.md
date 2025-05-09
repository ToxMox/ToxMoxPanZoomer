# Mouse Pan & Zoom for OBS Studio

A powerful Python script for OBS Studio that enables smooth mouse-controlled panning and zooming for any source. Track your mouse position to control which part of your content is displayed, with customizable transition effects.

## Features

- **Direct 1:1 Mouse Control**: Pan any source by moving your mouse - the source follows your cursor in real-time
- **Customizable Zoom**: Easily zoom in/out with configurable levels from 1x to 5x
- **Smooth Transitions**: Professional animated transitions when toggling zoom with configurable durations
- **Multi-Monitor Support**: Works across multiple displays with proper monitor selection
- **Performance Optimized**: Configurable update frequency (30-240 FPS) to match your display refresh rate
- **Flexible Viewport Definition**: Define the panning area using a color source scaled to any size in your scene
- **Hotkey Control**: Toggle panning and zooming on/off using customizable OBS hotkeys

## Demo/Setup
https://github.com/user-attachments/assets/fc5f0f8c-acfa-4ac4-9c35-959b0d9c3456

https://github.com/user-attachments/assets/9b61c53e-ab09-447e-9b06-b76438e2003b

## Requirements

- OBS Studio 31.0+ & Python
- Tested with Windows 11 and Python version 3.12.10 x64 installed

## Installation

1. Download the `ToxMoxPanZoomer.py` script from this repository
2. In OBS Studio, go to **Tools** → **Scripts**
3. In the Python Settings tab, ensure your Python installation is properly configured
4. In the Scripts tab, click the "+" button and select the downloaded script
5. The script is now installed and ready to configure

## Configuration

1. **Target Source**: Select which source you want to pan and zoom
2. **Viewport Source**: Create a Color Source in OBS and scale it in your scene to define the panning area, then select it here
3. **Monitor Selection**: Choose which monitor to track mouse movement on
4. **Zoom Level**: Set your desired zoom level (1x to 5x)
5. **Transition Durations**: Configure separate durations for zoom-in and zoom-out animations
6. **Update Frequency**: Recommend starting at same fps as OBS output fps or higher as needed for smoother movement

## Usage

1. After configuration, enable the script with the **Enable Mouse Pan** checkbox
2. Set up hotkeys in OBS Settings → Hotkeys for:
   - **Toggle ToxMox's Pan Zoomer - Panning**: Starts/stops mouse tracking
   - **Toggle Toxmox's Pan Zoomer - Zooming**: Activates/deactivates zoom with smooth transitions (Panning Hotkey must be toggled on for Zoom to work)

When panning is active, your mouse position determines which part of the source is shown within the viewport area. Zooming works in conjunction with panning and scales the content around your mouse position.

## Tips

- You can use a small Color Source (e.g., 400x400) and scale it to your desired size in the scene to define the panning area
- Set 0 seconds for transition duration if you prefer instant zooming
- If you experience ghosting/stutter, try increasing the Update Frequency

## Troubleshooting

- If OBS crashes on startup, check your Python installation is compatible
- Enable Debug Mode for detailed logging to solve complex issues

## Acknowledgement

This script was inspired by https://github.com/BlankSourceCode/obs-zoom-to-mouse

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
``` 
