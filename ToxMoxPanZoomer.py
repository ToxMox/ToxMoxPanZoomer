"""
ToxMox's Pan Zoomer for OBS
Pans a selected source based on mouse position (1:1 mapping).
Features smooth transitions and customizable zoom controls.

For OBS Studio 31.0+
Tested with Windows 11 and Python version 3.12.10 x64 installed

MIT License
Copyright (c) 2025
"""

import obspython as obs
import ctypes
import platform
import time
import os
import datetime
import math # Add explicit math import for isnan, isinf functions

# Try to import wintypes separately to avoid attribute error
try:
    from ctypes import wintypes
    WINTYPES_AVAILABLE = True
except ImportError:
    WINTYPES_AVAILABLE = False

# Global variables
settings = {
    "source_name": "",
    "viewport_color_source_name": "",
    "master_enabled": False,
    "pan_enabled": False,
    "zoom_enabled": False,  # New zoom toggle
    "zoom_level": 1.0,      # New zoom level (1.0 to 5.0)
    "scene_name": "", # Current scene where the source lives
    "monitor_id": 0,
    "debug_mode": False,
    "file_logging": True,
    "direct_source_cache": None, # Cache for direct source reference
    "direct_mode": False, # Flag for direct plugin mode
    "direct_property_names": {"x": None, "y": None}, # Cache for plugin property names
    "update_fps": 60,  # Default update rate (FPS)
    "zoom_in_duration": 0.3,  # Zoom IN transition duration in seconds (default: 300ms)
    "zoom_out_duration": 0.3,  # Zoom OUT transition duration in seconds (default: 300ms)
}

# Source information cache
source_settings = {
    "viewport_width": 0,
    "viewport_height": 0,
    "viewport_scene_center_x": 0.0, # For storing viewport's scene center
    "viewport_scene_center_y": 0.0, # For storing viewport's scene center
    "source_base_width": 0,
    "source_base_height": 0,
    "is_initial_state_captured": False,
    "initial_pos_x": 0.0,
    "initial_pos_y": 0.0,
    "initial_scale_x": 1.0,
    "initial_scale_y": 1.0,
    "scene_item": None, # To store the current scene item
    # Zoom transition states
    "is_transitioning": False,  # Whether a zoom transition is in progress
    "transition_start_time": 0,  # When the transition started
    "transition_start_zoom": 1.0,  # Starting zoom level
    "transition_target_zoom": 1.0,  # Target zoom level
    "transition_duration": 0.3,   # Current transition duration (set dynamically)
    "is_zooming_in": False,       # Whether we're zooming in or out
}

# Screen info
monitor_info = {
    "screen_width": 1920,
    "screen_height": 1080,
    "screen_x_offset": 0,
    "screen_y_offset": 0,
}

# Add global variables for hotkeys
toggle_pan_hotkey_id = None
toggle_zoom_hotkey_id = None

# Add global variable for cached scene item at the top of the file near other globals
g_current_scene_item = None

# Get the script directory for the log file
script_path = os.path.dirname(os.path.realpath(__file__))
log_file_path = os.path.join(script_path, "mouse_pan_zoom_log.txt")

# Helper for logging warnings only once per interval
g_last_warning_time = {}
def log_warning_throttle(message, key="default", interval=1.0):
    """Log warning messages, but only once per interval to avoid spam"""
    now = time.time()
    last_time = g_last_warning_time.get(key, 0)
    if now - last_time > interval:
        log_warning(message)
        g_last_warning_time[key] = now

# Function to log to file
def log_to_file(message, level="INFO"):
    if not settings["file_logging"]:
        return
    
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with open(log_file_path, "a", encoding="utf-8") as log_file:
            log_file.write(f"[{timestamp}] [{level}] {message}\n")
    except Exception as e:
        print(f"[Mouse Pan & Zoom] ERROR: Failed to write to log file: {e}")

# Enhanced logging functions that write to both OBS and file
def log(message):
    print(f"[Mouse Pan & Zoom] {message}")
    log_to_file(message, "INFO")

def log_error(message):
    print(f"[Mouse Pan & Zoom] ERROR: {message}")
    log_to_file(message, "ERROR")

def log_warning(message):
    print(f"[Mouse Pan & Zoom] WARNING: {message}")
    log_to_file(message, "WARNING")

# Platform specific mouse position function
def get_mouse_pos():
    if platform.system() == "Windows":
        try:
            if WINTYPES_AVAILABLE:
                pt = wintypes.POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                return {"x": pt.x, "y": pt.y}
            else:
                class POINT(ctypes.Structure):
                    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                pt = POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                return {"x": pt.x, "y": pt.y}
        except Exception as e:
            print(f"[Mouse Pan & Zoom] Error getting mouse position: {e}")
            return {
                "x": monitor_info["screen_x_offset"] + (monitor_info["screen_width"] // 2),
                "y": monitor_info["screen_y_offset"] + (monitor_info["screen_height"] // 2)
            }
    elif platform.system() == "Linux":
        # For Linux, would use Xlib or similar
        # This is a placeholder implementation
        try:
            # Placeholder - in a real implementation, you'd use Xlib
            return {
                "x": monitor_info["screen_x_offset"] + (monitor_info["screen_width"] // 2),
                "y": monitor_info["screen_y_offset"] + (monitor_info["screen_height"] // 2)
            }
        except Exception as e:
            print(f"[Mouse Pan & Zoom] Error getting mouse position: {e}")
            return {
                "x": monitor_info["screen_x_offset"] + (monitor_info["screen_width"] // 2),
                "y": monitor_info["screen_y_offset"] + (monitor_info["screen_height"] // 2)
            }
    elif platform.system() == "Darwin":  # macOS
        # For macOS, would use Quartz or similar
        # This is a placeholder implementation
        return {
            "x": monitor_info["screen_x_offset"] + (monitor_info["screen_width"] // 2),
            "y": monitor_info["screen_y_offset"] + (monitor_info["screen_height"] // 2)
        }
    return {
        "x": monitor_info["screen_x_offset"] + (monitor_info["screen_width"] // 2),
        "y": monitor_info["screen_y_offset"] + (monitor_info["screen_height"] // 2)
    }

# Get monitor information (platform-specific)
def get_monitor_info():
    monitors = []
    
    if platform.system() == "Windows":
        try:
            # Get virtual screen dimensions
            SM_XVIRTUALSCREEN = 76
            SM_YVIRTUALSCREEN = 77
            SM_CXVIRTUALSCREEN = 78
            SM_CYVIRTUALSCREEN = 79
            SM_CMONITORS = 80
            
            try:
                x_virtual = ctypes.windll.user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
                y_virtual = ctypes.windll.user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
                cx_virtual = ctypes.windll.user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
                cy_virtual = ctypes.windll.user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
                monitor_count = ctypes.windll.user32.GetSystemMetrics(SM_CMONITORS)
                
                log_to_file(f"Virtual screen: X={x_virtual}, Y={y_virtual}, W={cx_virtual}, H={cy_virtual}, Monitors={monitor_count}", "DEBUG")
            except Exception as e:
                print(f"[Mouse Pan & Zoom] Error getting system metrics: {e}")
                # Fallback to default values
                x_virtual, y_virtual = 0, 0
                cx_virtual, cy_virtual = 1920, 1080
                monitor_count = 1
            
            # Add "All Monitors" option
            monitors.append({
                "id": 0,
                "name": "All Monitors (Virtual Screen)",
                "x": x_virtual,
                "y": y_virtual,
                "width": cx_virtual,
                "height": cy_virtual
            })
            
            # For more accurate monitor positions, we can use EnumDisplayMonitors 
            # This is a simplified approximation approach for now
            if monitor_count > 0:
                # If we have multiple monitors with different arrangements, we need a better way
                # Let's try to utilize a more precise logic based on observation
                
                # Attempt to use a better approach for multi-monitor setups
                try:
                    # Define structures for EnumDisplayMonitors
                    class RECT(ctypes.Structure):
                        _fields_ = [
                            ('left', ctypes.c_long),
                            ('top', ctypes.c_long),
                            ('right', ctypes.c_long),
                            ('bottom', ctypes.c_long)
                        ]
                    
                    class MONITORINFO(ctypes.Structure):
                        _fields_ = [
                            ('cbSize', ctypes.c_ulong),
                            ('rcMonitor', RECT),
                            ('rcWork', RECT),
                            ('dwFlags', ctypes.c_ulong)
                        ]
                    
                    # Define callback function type
                    MONITORENUMPROC = ctypes.WINFUNCTYPE(
                        ctypes.c_int,
                        ctypes.c_ulong,
                        ctypes.c_ulong,
                        ctypes.POINTER(RECT),
                        ctypes.c_double
                    )
                    
                    # Monitors list for callback function
                    detailed_monitors = []
                    
                    # Callback for EnumDisplayMonitors
                    def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
                        mi = MONITORINFO()
                        mi.cbSize = ctypes.sizeof(MONITORINFO)
                        if ctypes.windll.user32.GetMonitorInfoW(hMonitor, ctypes.byref(mi)):
                            monitor_rect = mi.rcMonitor
                            width = monitor_rect.right - monitor_rect.left
                            height = monitor_rect.bottom - monitor_rect.top
                            is_primary = (mi.dwFlags & 1) != 0  # 1 = MONITORINFOF_PRIMARY
                            
                            detailed_monitors.append({
                                "handle": hMonitor,
                                "x": monitor_rect.left,
                                "y": monitor_rect.top,
                                "width": width,
                                "height": height,
                                "is_primary": is_primary
                            })
                        return True  # Continue enumeration
                    
                    # Enumerate monitors
                    callback_ptr = MONITORENUMPROC(callback)
                    ctypes.windll.user32.EnumDisplayMonitors(None, None, callback_ptr, 0)
                    
                    # Process detailed monitor info
                    if detailed_monitors:
                        for i, mon in enumerate(detailed_monitors):
                            # Create more descriptive name with position and resolution
                            position_desc = ""
                            if mon["x"] < 0:
                                position_desc = "Left"
                            elif mon["x"] > 0:
                                position_desc = "Right"
                            else:
                                position_desc = "Center"
                                
                            name = f"Monitor {i+1} ({mon['width']}x{mon['height']})"
                            if mon["is_primary"]:
                                name += " - Primary"
                            if position_desc:
                                name += f" - {position_desc}"
                            
                            monitor_id = i+1
                            log_to_file(f"Found monitor: {name}, X={mon['x']}, Y={mon['y']}, W={mon['width']}, H={mon['height']}, Primary={mon['is_primary']}", "DEBUG")
                            
                            monitors.append({
                                "id": monitor_id,
                                "name": name,
                                "x": mon["x"],
                                "y": mon["y"],
                                "width": mon["width"],
                                "height": mon["height"]
                            })
                except Exception as e:
                    log_error(f"Failed to enumerate monitors: {e}, falling back to simplified approach")
                    # Fallback to simplified approach
                    avg_width = cx_virtual // monitor_count
                    for i in range(monitor_count):
                        name = f"Monitor {i+1}"
                        if i == 0:  # Assume first monitor might be primary
                            name += " (Likely Primary)"
                        
                        # Simple estimation assuming side-by-side arrangement
                        monitors.append({
                            "id": i+1,
                            "name": name,
                            "x": x_virtual + (avg_width * i),
                            "y": y_virtual,
                            "width": avg_width,
                            "height": cy_virtual
                        })
        except Exception as e:
            log_error(f"Error getting Windows monitor info: {e}")
    
    # If no monitors were found, add a default one
    if not monitors:
        monitors.append({
            "id": 0,
            "name": "Default Monitor",
            "x": 0,
            "y": 0,
            "width": 1920,  # Default fallback size
            "height": 1080
        })
    
    return monitors

# Set the selected monitor info
def update_selected_monitor():
    log("Attempting to update selected monitor...")
    try:
        monitors = get_monitor_info()
        selected_id = settings["monitor_id"]
        
        for monitor in monitors:
            if monitor["id"] == selected_id:
                monitor_info["screen_width"] = monitor["width"]
                monitor_info["screen_height"] = monitor["height"]
                monitor_info["screen_x_offset"] = monitor["x"]
                monitor_info["screen_y_offset"] = monitor["y"]
                
                # Log the monitor info for debugging
                log(f"Selected monitor UPDATED: {monitor['name']}, {monitor['width']}x{monitor['height']}, offset: {monitor['x']},{monitor['y']}")
                log(f"Global monitor_info check: W={monitor_info['screen_width']}, H={monitor_info['screen_height']}, X={monitor_info['screen_x_offset']}, Y={monitor_info['screen_y_offset']}")
                return
        
        # If we didn't find the selected monitor, use the first one
        if monitors:
            monitor = monitors[0]
            monitor_info["screen_width"] = monitor["width"]
            monitor_info["screen_height"] = monitor["height"] 
            monitor_info["screen_x_offset"] = monitor["x"]
            monitor_info["screen_y_offset"] = monitor["y"]
            log_warning(f"Selected monitor ID {selected_id} not found, using {monitor['name']} instead")
    except Exception as e:
        log_error(f"Error selecting monitor: {e}. Using default values.")
        # Keep the default values in monitor_info

# Find scene item by source name in a specific scene
def find_scene_item(scene_source, source_name):
    """Find a scene item by source name in a scene"""
    try:
        if not scene_source:
            return None
            
        scene = obs.obs_scene_from_source(scene_source)
        if not scene:
            return None
            
        # Use a safer approach that doesn't rely on the callback
        items = obs.obs_scene_enum_items(scene)
        found_item = None
        
        if items:
            for i in range(len(items)):
                item = items[i]
                if not item:
                    continue
                    
                source = obs.obs_sceneitem_get_source(item)
                if not source:
                    continue
                    
                current_name = obs.obs_source_get_name(source)
                if current_name == source_name:
                    # We found our match, save a reference
                    found_item = item
                    # Don't release this specific item
                    items[i] = None
                    break
                    
            # Release all other items
            for item in items:
                if item:
                    obs.obs_sceneitem_release(item)
                    
        return found_item
    except Exception as e:
        log_error(f"Error finding scene item: {e}")
        return None

# Get the scene item for a source
def get_source_scene_item(source_name):
    """Get the scene item for a source either in the current scene or any scene"""
    try:
        # If we're already in direct mode and have a valid direct source, use it
        if settings["direct_mode"] and settings["direct_source_cache"]:
            # Check if the cached source is still valid
            cached_source = settings["direct_source_cache"]
            if cached_source:
                current_name = obs.obs_source_get_name(cached_source)
                if current_name == source_name:
                    log_debug(f"Using cached direct source for '{source_name}'")
                    # Create our dummy item with the cached source
                    dummy_item = {
                        "is_direct_source": True,
                        "source": cached_source,
                        "pos_x": 0,
                        "pos_y": 0,
                        "scale_x": 1.0,
                        "scale_y": 1.0
                    }
                    return dummy_item
                else:
                    # Source changed, release the old one
                    obs.obs_source_release(cached_source)
                    settings["direct_source_cache"] = None
        
        # Try the current scene first (if we know it)
        if settings["scene_name"]:
            scene_source = obs.obs_get_source_by_name(settings["scene_name"])
            if scene_source:
                scene_item = find_scene_item(scene_source, source_name)
                obs.obs_source_release(scene_source)
                if scene_item:
                    return scene_item
        
        # If not found in current scene, try the current program scene
        current_scene = obs.obs_frontend_get_current_scene()
        if current_scene:
            scene_item = find_scene_item(current_scene, source_name)
            if scene_item:
                scene_name = obs.obs_source_get_name(current_scene)
                settings["scene_name"] = scene_name
                log(f"Found source '{source_name}' in current scene '{scene_name}'")
                obs.obs_source_release(current_scene)
                return scene_item
            obs.obs_source_release(current_scene)
        
        # If still not found, search through all scenes
        scenes = obs.obs_frontend_get_scenes()
        if scenes:
            for scene in scenes:
                scene_name = obs.obs_source_get_name(scene)
                
                # Skip if we already searched this scene
                if scene_name == settings["scene_name"]:
                    continue
                    
                try:
                    scene_item = find_scene_item(scene, source_name)
                    if scene_item:
                        settings["scene_name"] = scene_name
                        log(f"Found source '{source_name}' in scene '{scene_name}'")
                        obs.source_list_release(scenes)
                        return scene_item
                except Exception as e:
                    log_error(f"Error searching scene {scene_name}: {e}")
                    
            obs.source_list_release(scenes)
        
        # Special handling for plugin sources - direct source access when not found in scenes
        source = obs.obs_get_source_by_name(source_name)
        if source:
            # We found the source but couldn't find it in any scene
            # This can happen with plugin sources or other special sources
            settings["direct_mode"] = True
            settings["direct_source_cache"] = source
            log(f"Source '{source_name}' found but not in any standard scene - using direct source mode")
            
            # If we haven't discovered direct property names yet, do it now
            discover_direct_properties(source)
            
            # Create a dummy scene item that references just the source
            dummy_item = {
                "is_direct_source": True,
                "source": source,
                "pos_x": 0,
                "pos_y": 0,
                "scale_x": 1.0,
                "scale_y": 1.0
            }
            
            # Don't release source - we're keeping it in the cache
            return dummy_item
            
        log_error(f"Could not find source '{source_name}' in any scene or directly")
        return None
    except Exception as e:
        log_error(f"Error getting scene item: {e}")
        return None

# Discover property names used by some plugins
def discover_direct_properties(source):
    """Detect which property names plugins use for positioning"""
    try:
        if not source:
            return
            
        # Get the source settings
        settings_obj = obs.obs_source_get_settings(source)
        if not settings_obj:
            log_error("Could not get source settings for plugin property detection")
            return
        
        # List of possible position properties (expanded with more variants)
        x_candidates = [
            "x", "X", 
            "positionX", "PositionX", "position_x", "position-x",
            "pos_x", "pos-x", "posx", 
            "translateX", "translate_x", "translate-x",
            "movementX", "movement_x", "translationX",
            "offsetX", "offset_x", "offset-x",
            "xpos", "x_pos", "x-pos",
            "left"
        ]
        
        y_candidates = [
            "y", "Y", 
            "positionY", "PositionY", "position_y", "position-y",
            "pos_y", "pos-y", "posy", 
            "translateY", "translate_y", "translate-y",
            "movementY", "movement_y", "translationY",
            "offsetY", "offset_y", "offset-y",
            "ypos", "y_pos", "y-pos",
            "top"
        ]
        
        # Debug: print all property names to help identify patterns
        if settings["debug_mode"]:
            # Try to enumerate all properties
            property_names = []
            setting_obj_json = obs.obs_data_get_json(settings_obj)
            if setting_obj_json:
                log_to_file(f"Source settings JSON: {setting_obj_json}", "DEBUG")
        
        found_x = None
        found_y = None
        
        # Try all candidates
        for x_prop in x_candidates:
            if obs.obs_data_has_user_value(settings_obj, x_prop):
                found_x = x_prop
                log(f"Found plugin X position property: '{x_prop}'")
                break
                
        for y_prop in y_candidates:
            if obs.obs_data_has_user_value(settings_obj, y_prop):
                found_y = y_prop
                log(f"Found plugin Y position property: '{y_prop}'")
                break
        
        # As a fallback, check if we can find a position object/array
        if not found_x or not found_y:
            # Try to check for position as an array or nested object
            if obs.obs_data_has_user_value(settings_obj, "position"):
                log("Found 'position' property, but need to determine format")
                # We found a position property, but need to determine how to use it
                # This would need more complex handling
        
        # Store the property names for use later
        settings["direct_property_names"]["x"] = found_x
        settings["direct_property_names"]["y"] = found_y
        
        # If we found neither, use default fallbacks that might work
        if not found_x and not found_y:
            log_warning("Could not find position properties, using 'x' and 'y' as fallbacks")
            settings["direct_property_names"]["x"] = "x"
            settings["direct_property_names"]["y"] = "y"
            
        log(f"Plugin position properties - X: {settings['direct_property_names']['x']}, Y: {settings['direct_property_names']['y']}")
        
        # Release settings object
        obs.obs_data_release(settings_obj)
    except Exception as e:
        log_error(f"Error discovering plugin properties: {e}")
        # Use fallbacks
        settings["direct_property_names"]["x"] = "x"
        settings["direct_property_names"]["y"] = "y"

# New helper function for debug logs
def log_debug(message):
    """Log debug messages only if debug mode is enabled"""
    if settings["debug_mode"]:
        log(message)

# Get current position/scale from the scene item or direct source
def get_item_transform(scene_item):
    """Get position and scale from a scene item or direct source"""
    if not scene_item:
        return None, None, None, None
        
    try:
        # Handle direct source mode (plugin source)
        if isinstance(scene_item, dict) and scene_item.get("is_direct_source"):
            # Direct sources store their position directly
            return (
                scene_item.get("pos_x", 0), 
                scene_item.get("pos_y", 0),
                scene_item.get("scale_x", 1.0),
                scene_item.get("scale_y", 1.0)
            )
            
        # Normal scene item handling
        pos = obs.vec2()
        obs.obs_sceneitem_get_pos(scene_item, pos)
        
        scale = obs.vec2()
        obs.obs_sceneitem_get_scale(scene_item, scale)
        
        return pos.x, pos.y, scale.x, scale.y
    except Exception as e:
        log_error(f"Error getting item transform: {e}")
        return None, None, None, None

# Set position/scale on the scene item or direct source
def set_item_transform(scene_item, pos_x, pos_y, scale_x=None, scale_y=None):
    """Set position and scale on a scene item or direct source"""
    if not scene_item:
        return False
        
    try:
        # Handle direct source mode (plugin source)
        if isinstance(scene_item, dict) and scene_item.get("is_direct_source"):
            # For direct sources, we just update the stored position
            scene_item["pos_x"] = pos_x
            scene_item["pos_y"] = pos_y
            if scale_x is not None:
                scene_item["scale_x"] = scale_x
            if scale_y is not None:
                scene_item["scale_y"] = scale_y
                
            # Now we need to update the actual source properties
            source = scene_item.get("source")
            if source:
                # Get the source settings
                settings_obj = obs.obs_source_get_settings(source)
                if settings_obj:
                    # Use the discovered property names for plugins
                    x_prop = settings["direct_property_names"]["x"]
                    y_prop = settings["direct_property_names"]["y"]
                    
                    # Set position if properties were found
                    if x_prop:
                        obs.obs_data_set_double(settings_obj, x_prop, pos_x)
                    if y_prop:
                        obs.obs_data_set_double(settings_obj, y_prop, pos_y)
                        
                    # Apply settings back to source
                    obs.obs_source_update(source, settings_obj)
                    obs.obs_data_release(settings_obj)
            
            return True
            
        # Normal scene item handling
        pos = obs.vec2()
        pos.x = pos_x
        pos.y = pos_y
        obs.obs_sceneitem_set_pos(scene_item, pos)
        
        if scale_x is not None and scale_y is not None:
            scale = obs.vec2()
            scale.x = scale_x
            scale.y = scale_y
            obs.obs_sceneitem_set_scale(scene_item, scale)
        
        return True
    except Exception as e:
        log_error(f"Error setting item transform: {e}")
        return False

# Release resources (for scene items or direct sources)
def release_item_resources(scene_item):
    """Release any resources associated with a scene item or direct source"""
    if not scene_item:
        return
        
    # Handle direct source mode (plugin source)
    if isinstance(scene_item, dict) and scene_item.get("is_direct_source"):
        # For direct sources, do NOT release the source since we're caching it
        # Just disconnect it from the scene_item
        scene_item["source"] = None
        
# Helper function for interpolation during transitions
def ease_in_out_quad(t):
    """Quadratic easing for smooth transitions"""
    if t < 0.5:
        return 2 * t * t
    else:
        t = t * 2 - 1
        return -0.5 * (t * (t - 2) - 1)

# Main update function for panning - using the exact panning algorithm from working version
def update_pan_and_zoom():
    global g_current_scene_item
    
    # If master switch is off OR panning is off, do nothing. Zoom only works with panning.
    if not settings["master_enabled"] or not settings["pan_enabled"]:
        # If we were transitioning, stop the transition
        if source_settings["is_transitioning"]:
            source_settings["is_transitioning"] = False
        return
    
    # Check if we have viewport dimensions and a valid cached scene item
    if source_settings["viewport_width"] <= 0 or source_settings["viewport_height"] <= 0:
        return
        
    if g_current_scene_item is None:
        if settings["debug_mode"]:
            log_error("No cached scene item reference")
        return
    
    # We use the cached g_current_scene_item, avoiding repeated searches
    scene_item = g_current_scene_item
    
    # Get viewport's scene center (captured when panning was enabled)
    actual_viewport_center_x = source_settings.get("viewport_scene_center_x")
    actual_viewport_center_y = source_settings.get("viewport_scene_center_y")

    if actual_viewport_center_x is None or actual_viewport_center_y is None:
        # This should ideally not happen if toggle_panning ensures these are set
        log_error("Viewport center not captured. Please re-toggle panning.")
        return
    
    # --- Zoom transition handling ---
    current_zoom_level = 1.0  # Default to 1.0 when no zoom
    
    # Only apply zoom if zoom is enabled or we're in a zoom transition
    if settings["zoom_enabled"] or source_settings["is_transitioning"]:
        current_zoom_level = settings["zoom_level"]
        
        # Check if we're in a zoom transition
        if source_settings["is_transitioning"]:
            # Calculate how far we are in the transition
            elapsed_time = time.time() - source_settings["transition_start_time"]
            transition_duration = source_settings["transition_duration"]
            
            # Calculate progress (0.0 to 1.0)
            progress = min(1.0, elapsed_time / transition_duration)
            
            # Apply easing for a smooth transition
            eased_progress = ease_in_out_quad(progress)
            
            # Interpolate between start and target zoom
            start_zoom = source_settings["transition_start_zoom"]
            target_zoom = source_settings["transition_target_zoom"]
            current_zoom_level = start_zoom + (target_zoom - start_zoom) * eased_progress
            
            # More frequent debug logging during transitions if debug mode is on
            if settings["debug_mode"] and int(time.time() * 20) % 5 == 0:  # Log more frequently for debugging
                transition_type = "IN" if source_settings["is_zooming_in"] else "OUT"
                log_to_file(f"ZOOM {transition_type}: Progress={progress:.2f}, Eased={eased_progress:.2f}, " +
                            f"Level={current_zoom_level:.2f}, StartZoom={start_zoom:.2f}, " +
                            f"TargetZoom={target_zoom:.2f}, Duration={transition_duration:.2f}s", "DEBUG")
            
            # Check if transition is complete
            if progress >= 1.0:
                source_settings["is_transitioning"] = False
                current_zoom_level = target_zoom  # Ensure we land exactly on target
                log_debug(f"Zoom transition complete. Final zoom level: {current_zoom_level:.2f}")
                
            if settings["debug_mode"] and int(time.time() * 10) % 5 == 0:  # Log less frequently
                log_debug(f"Zoom transition: {progress:.2f}, level={current_zoom_level:.2f}, " + 
                         f"{'IN' if source_settings['is_zooming_in'] else 'OUT'}, duration={transition_duration:.2f}s")
    
    # --- Continue with the regular update ---
    
    # Get mouse position relative to monitor
    global_mouse = get_mouse_pos()
    relative_mouse_x = global_mouse["x"] - monitor_info["screen_x_offset"]
    relative_mouse_y = global_mouse["y"] - monitor_info["screen_y_offset"]
    
    # --- Monitor Boundary Check --- 
    if settings["monitor_id"] != 0: # Check only if a specific monitor is selected
        is_inside_selected_monitor = (
            relative_mouse_x >= 0 and 
            relative_mouse_x < monitor_info["screen_width"] and
            relative_mouse_y >= 0 and 
            relative_mouse_y < monitor_info["screen_height"]
        )
        if not is_inside_selected_monitor:
            # Skip this update if mouse is outside the target monitor
            return

    # Calculate percentage only if inside bounds (or if "All Monitors" selected)
    mouse_x_pct = relative_mouse_x / monitor_info["screen_width"]
    mouse_y_pct = relative_mouse_y / monitor_info["screen_height"]

    # Ensure mouse_pct is within 0-1
    mouse_x_pct = max(0.0, min(1.0, mouse_x_pct))
    mouse_y_pct = max(0.0, min(1.0, mouse_y_pct))

    # Get the base values for our calculations
    obs_viewport_center_x = source_settings["initial_pos_x"]
    obs_viewport_center_y = source_settings["initial_pos_y"]
    
    # Scale of the source item when "Capture Viewport" was pressed
    item_initial_scale_x = source_settings["initial_scale_x"] # Will be 1.0 if item wasn't found
    item_initial_scale_y = source_settings["initial_scale_y"] # Will be 1.0 if item wasn't found

    # Dimensions of the on-screen "window" we are panning content within
    V_w = source_settings["viewport_width"]
    V_h = source_settings["viewport_height"]

    # Native (unscaled) dimensions of the source media
    S_w_native = source_settings["source_base_width"]
    S_h_native = source_settings["source_base_height"]

    # Calculate zoom scale based on the current zoom level (which may be from a transition)
    zoom_scale_x = current_zoom_level
    zoom_scale_y = current_zoom_level
    
    # We'll calculate the actual scale as the initial scale multiplied by the zoom scale
    scale_x = item_initial_scale_x * zoom_scale_x
    scale_y = item_initial_scale_y * zoom_scale_y
    
    # Dimensions of the source item as it's rendered on screen (considering its scaled size)
    Rendered_S_w = S_w_native * scale_x
    Rendered_S_h = S_h_native * scale_y
    
    # Calculate original center and width/height
    original_rendered_width = S_w_native * item_initial_scale_x
    original_rendered_height = S_h_native * item_initial_scale_y
    
    # Only calculate panning if it's enabled
    if settings["pan_enabled"]:
        # Target center of the V_w x V_h selection rectangle, in coordinates relative to Rendered_S_w x Rendered_S_h.
        target_sel_center_x_on_RenderedS = mouse_x_pct * Rendered_S_w
        target_sel_center_y_on_RenderedS = mouse_y_pct * Rendered_S_h

        # Clamp this target selection center so the V_w x V_h selection rectangle stays within Rendered_S_w x Rendered_S_h.
        clamped_sel_center_x = target_sel_center_x_on_RenderedS
        if Rendered_S_w > V_w:  # Source is wider than the viewport window, so panning is possible
            min_center_x = V_w / 2.0
            max_center_x = Rendered_S_w - (V_w / 2.0)
            clamped_sel_center_x = max(min_center_x, min(max_center_x, target_sel_center_x_on_RenderedS))
        else:  # Source is not wider; its center must align with the selection rectangle's center
            clamped_sel_center_x = Rendered_S_w / 2.0

        clamped_sel_center_y = target_sel_center_y_on_RenderedS
        if Rendered_S_h > V_h:  # Source is taller than the viewport window
            min_center_y = V_h / 2.0
            max_center_y = Rendered_S_h - (V_h / 2.0)
            clamped_sel_center_y = max(min_center_y, min(max_center_y, target_sel_center_y_on_RenderedS))
        else:
            clamped_sel_center_y = Rendered_S_h / 2.0
            
        # Calculate the new top-left position of the target source so that
        # the clamped_sel_center_x/y point on the source aligns with the viewport's scene center.
        new_pos_x = actual_viewport_center_x - clamped_sel_center_x
        new_pos_y = actual_viewport_center_y - clamped_sel_center_y
    
    # Verify the positions are valid numbers
    if (math.isnan(new_pos_x) or math.isnan(new_pos_y) or
        math.isinf(new_pos_x) or math.isinf(new_pos_y) or
        abs(new_pos_x) > 30000 or abs(new_pos_y) > 30000): # Increased limit from 10000 to 30000
        log_error(f"Invalid position calculated: ({new_pos_x},{new_pos_y})")
        return  # Skip this update
    
    # Apply the position and scale - use direct OBS calls for all sources
    try:
        if isinstance(scene_item, dict) and scene_item.get("is_direct_source"):
            # For direct plugin sources, handle differently but efficiently
            source = scene_item.get("source")
            if source:
                # For direct source manipulation, try multiple approaches to find what works
                success = False
                
                # First try: Use the cached property names if available
                x_prop = settings["direct_property_names"]["x"] 
                y_prop = settings["direct_property_names"]["y"]
                
                if x_prop and y_prop:
                    try:
                        settings_obj = obs.obs_source_get_settings(source)
                        if settings_obj:
                            # Set both properties in one go
                            obs.obs_data_set_double(settings_obj, x_prop, new_pos_x)
                            obs.obs_data_set_double(settings_obj, y_prop, new_pos_y)
                            # We would need to add scale properties here for direct sources
                            # This would require discovering additional property names
                            obs.obs_source_update(source, settings_obj)
                            obs.obs_data_release(settings_obj)
                            success = True
                    except Exception as e:
                        log_error(f"Error using cached property names: {e}")
                
                # If first method failed, try the transform method (works for some plugins)
                if not success:
                    try:
                        # Try transform_info approach (works for some sources)
                        transform = obs.obs_transform_info()
                        transform.pos.x = new_pos_x
                        transform.pos.y = new_pos_y
                        # Set scale if zooming is enabled
                        if settings["zoom_enabled"]:
                            transform.scale.x = scale_x
                            transform.scale.y = scale_y
                        obs.obs_source_set_transform_info(source, transform)
                        success = True
                    except Exception as e:
                        # This is expected to fail for many sources
                        if settings["debug_mode"]:
                            log_to_file(f"Transform info method failed: {e}", "DEBUG")
                
                # If still failed, try manually creating and setting new settings
                if not success:
                    try:
                        # Try creating brand new settings and applying common property names
                        settings_obj = obs.obs_data_create()
                        
                        # Try all common property names for position
                        for x_name in ["x", "position_x", "positionX"]:
                            obs.obs_data_set_double(settings_obj, x_name, new_pos_x)
                            
                        for y_name in ["y", "position_y", "positionY"]:
                            obs.obs_data_set_double(settings_obj, y_name, new_pos_y)
                        
                        # Try common property names for scale if zooming is enabled
                        if settings["zoom_enabled"]:
                            for scale_x_name in ["scale_x", "scaleX", "width_scale"]:
                                obs.obs_data_set_double(settings_obj, scale_x_name, scale_x)
                                
                            for scale_y_name in ["scale_y", "scaleY", "height_scale"]:
                                obs.obs_data_set_double(settings_obj, scale_y_name, scale_y)
                            
                        # Update the source
                        obs.obs_source_update(source, settings_obj)
                        obs.obs_data_release(settings_obj)
                        
                        # Check if we should update our property names for next time
                        if not settings["direct_property_names"]["x"] or not settings["direct_property_names"]["y"]:
                            discover_direct_properties(source)
                    except Exception as e:
                        log_error(f"Error with fallback property setting: {e}")
        else:
            # For normal OBS scene items
            # Set position if we've calculated a new position
            current_pos = obs.vec2()
            current_pos.x = new_pos_x
            current_pos.y = new_pos_y
            obs.obs_sceneitem_set_pos(scene_item, current_pos)
            
            # Set scale if zooming is enabled
            if settings["zoom_enabled"] or source_settings["is_transitioning"]:
                current_scale = obs.vec2()
                current_scale.x = scale_x
                current_scale.y = scale_y
                obs.obs_sceneitem_set_scale(scene_item, current_scale)
    except Exception as e:
        log_error(f"Error applying new position/scale: {e}")
    
    # Debug logging - enhanced to include zoom information
    if settings["debug_mode"]:
        if int(time.time() * 2) % 2 == 0:  # Original timing: roughly every 0.5 seconds
            log_to_file(f"Update: MousePct=({mouse_x_pct:.2f},{mouse_y_pct:.2f}) "
                        f"RenderedSrc=({Rendered_S_w:.0f}x{Rendered_S_h:.0f}) VPort=({V_w:.0f}x{V_h:.0f}) "
                        f"NewPos=({new_pos_x:.1f},{new_pos_y:.1f}) "
                        f"Pan={settings['pan_enabled']} Zoom={settings['zoom_enabled']} ZoomLevel={current_zoom_level:.2f} "
                        f"Transitioning={source_settings['is_transitioning']}", "DEBUG")

# Toggle panning on/off
def toggle_panning(pressed):
    """Toggle panning on or off based on hotkey press"""
    global g_current_scene_item
    
    # Immediate bail if not pressed
    if not pressed:
        return
        
    # Check if main switch is enabled
    if not settings["master_enabled"]:
        log("Cannot toggle: Master switch is disabled")
        return
    
    # Toggle state
    settings["pan_enabled"] = not settings["pan_enabled"]
    
    if settings["pan_enabled"]:
        # Always clear cached values first to ensure fresh capture
        source_settings["viewport_width"] = 0
        source_settings["viewport_height"] = 0
        source_settings["viewport_scene_center_x"] = 0
        source_settings["viewport_scene_center_y"] = 0
        source_settings["is_initial_state_captured"] = False
        
        # Enable panning - verify we have required sources first
        target_source_name = settings["source_name"]
        viewport_source_name = settings["viewport_color_source_name"]
        
        # Basic Checks
        if not target_source_name:
            log_error("Cannot enable panning: No Target Source selected.")
            settings["pan_enabled"] = False
            return
            
        if not viewport_source_name:
            log_error("Cannot enable panning: No Viewport Source selected.")
            settings["pan_enabled"] = False
            return
        
        log(f"Capturing viewport dimensions for: {viewport_source_name}")
        
        # Find the viewport source in any scene to get its bounds
        viewport_scene_item = None
        viewport_found_in_scene = False
        
        # Check current scene first
        current_scene = obs.obs_frontend_get_current_scene()
        if current_scene:
            scene_obj = obs.obs_scene_from_source(current_scene)
            if scene_obj:
                viewport_scene_item = find_scene_item(current_scene, viewport_source_name)
                if viewport_scene_item:
                    viewport_found_in_scene = True
            obs.obs_source_release(current_scene)
        
        # If not found in current scene, search all scenes
        if not viewport_found_in_scene:
            scenes = obs.obs_frontend_get_scenes()
            if scenes:
                for scene in scenes:
                    scene_name = obs.obs_source_get_name(scene)
                    viewport_scene_item = find_scene_item(scene, viewport_source_name)
                    if viewport_scene_item:
                        viewport_found_in_scene = True
                        break
                obs.source_list_release(scenes)
        
        # If found in a scene, get its bounds
        if viewport_found_in_scene and viewport_scene_item:
            # Get position
            pos = obs.vec2()
            obs.obs_sceneitem_get_pos(viewport_scene_item, pos)
            
            # Get the source info for base dimensions
            viewport_source = obs.obs_sceneitem_get_source(viewport_scene_item)
            vp_base_width = obs.obs_source_get_width(viewport_source)
            vp_base_height = obs.obs_source_get_height(viewport_source)
            
            # Get scale to calculate bounds
            scale = obs.vec2()
            obs.obs_sceneitem_get_scale(viewport_scene_item, scale)
            
            # Calculate actual viewport dimensions based on bounds
            viewport_width = vp_base_width * scale.x
            viewport_height = vp_base_height * scale.y
            
            # If we need more accurate bounds, we can use the bounding box
            # Instead of just using scaled dimensions
            try:
                # Get rotation and alignment
                rot = obs.obs_sceneitem_get_rot(viewport_scene_item)
                alignment = obs.obs_sceneitem_get_alignment(viewport_scene_item)
                
                # If the item has rotation or special alignment, use bounding box
                # This ensures we get the true visible dimensions on screen
                if rot != 0.0 or alignment != 0:
                    # Create a bounding box struct
                    bounds_type = obs.OBS_BOUNDS_STRETCH  # Default bounds type
                    bounds = obs.vec2()
                    
                    # Get current bounds
                    obs.obs_sceneitem_get_bounds(viewport_scene_item, bounds)
                    bounds_type = obs.obs_sceneitem_get_bounds_type(viewport_scene_item)
                    
                    if bounds_type != obs.OBS_BOUNDS_NONE:
                        viewport_width = bounds.x
                        viewport_height = bounds.y
                        log(f"Using bounds values: {viewport_width}x{viewport_height}")
            except Exception as e:
                log_warning(f"Could not get precise bounds, using scaled dimensions: {e}")
            
            # Calculate viewport's center in the scene
            source_settings["viewport_scene_center_x"] = pos.x + (viewport_width / 2.0)
            source_settings["viewport_scene_center_y"] = pos.y + (viewport_height / 2.0)
            
            log(f"Found viewport source in scene with bounds: {viewport_width:.0f}x{viewport_height:.0f}, Pos: ({pos.x:.1f},{pos.y:.1f})")
            log(f"Viewport scene center calculated: ({source_settings['viewport_scene_center_x']:.1f},{source_settings['viewport_scene_center_y']:.1f})")
            
            # Store viewport dimensions
            source_settings["viewport_width"] = viewport_width
            source_settings["viewport_height"] = viewport_height
            log(f"Viewport dimensions set: {viewport_width:.0f}x{viewport_height:.0f}")
            
            # Now find and store the source item
            scene_item = get_source_scene_item(target_source_name)
            if not scene_item:
                log_error(f"Cannot enable panning: Target Source '{target_source_name}' not found in any scene.")
                settings["pan_enabled"] = False
                return
            
            # Cache the scene item reference for repeated use
            g_current_scene_item = scene_item
            
            # Get target source dimensions
            if isinstance(scene_item, dict) and scene_item.get("is_direct_source"):
                # For direct sources
                source = scene_item.get("source")
                if source:
                    source_width = obs.obs_source_get_width(source)
                    source_height = obs.obs_source_get_height(source)
                    # Don't release source - it's part of our cached reference
                else:
                    source_width = 1920  # Fallback
                    source_height = 1080  # Fallback
            else:
                # For standard scene items
                source = obs.obs_sceneitem_get_source(scene_item)
                if source:
                    source_width = obs.obs_source_get_width(source)
                    source_height = obs.obs_source_get_height(source)
                    # No need to release - just a reference
                else:
                    source_width = 1920  # Fallback
                    source_height = 1080  # Fallback
                
            # Store source dimensions
            source_settings["source_base_width"] = source_width
            source_settings["source_base_height"] = source_height
            
            # Get current position and scale for initial state
            pos_x, pos_y, scale_x, scale_y = get_item_transform(scene_item)
            if pos_x is not None and scale_x is not None:
                source_settings["initial_pos_x"] = pos_x
                source_settings["initial_pos_y"] = pos_y
                source_settings["initial_scale_x"] = scale_x
                source_settings["initial_scale_y"] = scale_y
                source_settings["is_initial_state_captured"] = True
                log(f"Initial state captured: Pos=({pos_x:.1f},{pos_y:.1f}), Scale=({scale_x:.2f},{scale_y:.2f})")
            else:
                # If position couldn't be determined, use defaults
                source_settings["initial_pos_x"] = 0
                source_settings["initial_pos_y"] = 0
                source_settings["initial_scale_x"] = 1.0
                source_settings["initial_scale_y"] = 1.0
                source_settings["is_initial_state_captured"] = True
                log_warning("Could not get initial transform values. Using defaults.")
            
            log(f"Panning ENABLED for: {target_source_name}")
        else:
            log_error(f"Viewport source '{viewport_source_name}' not found as an item in any scene. Panning cannot be enabled.")
            log_error("Please add the viewport source to a scene and ensure it's spelled correctly.")
            settings["pan_enabled"] = False # Crucial: Prevent enabling panning
            return
    else:
        # Panning is now disabled - restore position and clear cache
        if source_settings["is_initial_state_captured"] and g_current_scene_item:
            # Disable any ongoing zoom transition
            source_settings["is_transitioning"] = False
            settings["zoom_enabled"] = False 
            
            # Restore original position and scale
            set_item_transform(
                g_current_scene_item,
                source_settings["initial_pos_x"],
                source_settings["initial_pos_y"],
                source_settings["initial_scale_x"],
                source_settings["initial_scale_y"]
            )
            log(f"Restored position and scale to initial values")
        
        # Clear cached references
        g_current_scene_item = None
        
        settings["direct_mode"] = False
        source_settings["is_initial_state_captured"] = False
        log("Panning DISABLED")

# Toggle zooming on/off
def toggle_zooming(pressed):
    """Toggle zooming on or off based on hotkey press"""
    global g_current_scene_item
    
    # Bail if not pressed
    if not pressed:
        return
        
    # Check if main switch is enabled
    if not settings["master_enabled"]:
        log("Cannot toggle zooming: Master switch is disabled")
        return
    
    # Check if panning is enabled (required for zooming)
    if not settings["pan_enabled"]:
        log("Cannot toggle zooming: Panning must be enabled first")
        return
    
    if source_settings["viewport_width"] <= 0 or source_settings["viewport_height"] <= 0:
        log("Cannot toggle zooming: Viewport not set properly.")
        return
    
    # Toggle zoom state
    new_zoom_enabled = not settings["zoom_enabled"]
    settings["zoom_enabled"] = new_zoom_enabled
    
    # Only start a transition if we have a valid scene item
    if g_current_scene_item:
        # Determine current actual zoom level (might be mid-transition)
        current_zoom = settings["zoom_level"]
        
        # If we're in the middle of a transition, calculate the actual current zoom level
        if source_settings["is_transitioning"]:
            elapsed_time = time.time() - source_settings["transition_start_time"]
            progress = min(1.0, elapsed_time / source_settings["transition_duration"])
            eased_progress = ease_in_out_quad(progress)
            
            # Get the actual current interpolated zoom level
            start_zoom = source_settings["transition_start_zoom"]
            target_zoom = source_settings["transition_target_zoom"]
            current_zoom = start_zoom + (target_zoom - start_zoom) * eased_progress
            
            # Debug output
            log_debug(f"Mid-transition zoom toggle. Current calculated zoom: {current_zoom:.2f}")
        
        # Set up the transition
        source_settings["is_transitioning"] = True
        source_settings["transition_start_time"] = time.time()
        
        if new_zoom_enabled:
            # Transitioning from 1.0 to zoom_level (zoom IN)
            source_settings["transition_start_zoom"] = 1.0
            source_settings["transition_target_zoom"] = settings["zoom_level"]
            source_settings["transition_duration"] = settings["zoom_in_duration"]
            source_settings["is_zooming_in"] = True
            log(f"Zooming IN to {settings['zoom_level']}x over {settings['zoom_in_duration']}s")
        else:
            # Transitioning from current zoom level to 1.0 (zoom OUT)
            source_settings["transition_start_zoom"] = current_zoom
            source_settings["transition_target_zoom"] = 1.0
            source_settings["transition_duration"] = settings["zoom_out_duration"] 
            source_settings["is_zooming_in"] = False
            log(f"Zooming OUT to 1.0x over {settings['zoom_out_duration']}s from current zoom {current_zoom:.2f}")
    else:
        log_warning("Cannot perform zoom transition: No valid scene item")

# Initialize log file
def init_log_file():
    if not settings["file_logging"]:
        return
        
    try:
        with open(log_file_path, "w", encoding="utf-8") as log_file:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_file.write(f"[{timestamp}] [INFO] Mouse Pan & Zoom script started\n")
            log_file.write(f"[{timestamp}] [INFO] OBS Version: {obs.obs_get_version_string()}\n")
            log_file.write(f"[{timestamp}] [INFO] Platform: {platform.system()} {platform.release()}\n")
            log_file.write(f"[{timestamp}] [INFO] Python Version: {platform.python_version()}\n")
            log_file.write(f"[{timestamp}] [INFO] Log File: {log_file_path}\n")
        log("Log file initialized at: " + log_file_path)
    except Exception as e:
        print(f"[Mouse Pan & Zoom] ERROR: Failed to initialize log file: {e}")

# OBS Script Hooks
def script_description():
    return """<h2>ToxMox's Pan Zoomer</h2>
Pans and zooms a selected source based on mouse position with direct 1:1 mapping.<br>
<small>Version 5.2.1</small><br><br>
<b>Setup Instructions:</b><br>
1. Select your <b>Target Source Name</b> - the source you want to pan and zoom.<br>
2. Create a <b>Color Source</b> with any base dimensions, then <b>scale it in OBS</b> to match your desired viewport size.<br>
3. Select this Color Source as your <b>Viewport Source Name</b>.<br>
4. Enable the <b>Enable Mouse Pan</b> master switch.<br>
5. Set your desired <b>Zoom Level</b> (1x to 5x).<br>
6. Configure <b>Zoom In/Out Transition Durations</b> (0-1 sec) for smooth transitions.<br>
7. Adjust <b>Update Frequency</b> to match your OBS fps (higher = smoother).<br>
8. Use the assigned hotkeys to toggle panning and zooming on/off (set in OBS Settings > Hotkeys).<br><br>
"""

# Add a global variable to store the selected monitor ID across reloads
g_selected_monitor_id = 0

def script_properties():
    props = obs.obs_properties_create()
    
    obs.obs_properties_add_bool(props, "master_enabled", "Enable Mouse Pan")
    
    # Target Source
    target_source_list = obs.obs_properties_add_list(props, "source_name", "Target Source Name", 
                                           obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
    sources = obs.obs_enum_sources()
    if sources:
        for source in sources:
            name = obs.obs_source_get_name(source)
            obs.obs_property_list_add_string(target_source_list, name, name)
        obs.source_list_release(sources)
    
    # Viewport Source
    viewport_list = obs.obs_properties_add_list(props, "viewport_color_source_name", "Viewport Source Name", 
                                           obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
    sources = obs.obs_enum_sources()
    if sources:
        for source in sources:
            name = obs.obs_source_get_name(source)
            obs.obs_property_list_add_string(viewport_list, name, name)
        obs.source_list_release(sources)
    
    # Add refresh sources button
    obs.obs_properties_add_button(props, "refresh_sources", "Refresh Sources", refresh_sources_clicked)
    
    # Monitor list - using a string property for better persistence
    monitor_list = obs.obs_properties_add_list(props, "monitor_id_string", "Target Monitor (for mouse tracking)",
                                         obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    
    # Enumerate monitors and add them to the list
    monitors = get_monitor_info()
    
    for monitor in monitors:
        # Store both ID and name in a composite string value
        value = f"{monitor['id']}:{monitor['name']}"
        # Display just the name
        obs.obs_property_list_add_string(monitor_list, monitor["name"], value)
    
    # Add zoom level slider
    zoom_slider = obs.obs_properties_add_float_slider(props, "zoom_level", "Zoom Level", 
                                               1.0, 5.0, 0.1)
    obs.obs_property_float_set_suffix(zoom_slider, "x")
    
    # Add zoom transition sliders
    zoom_in_slider = obs.obs_properties_add_float_slider(props, "zoom_in_duration", 
                                                  "Zoom In Transition Duration", 
                                                  0.0, 1.0, 0.1)
    obs.obs_property_float_set_suffix(zoom_in_slider, " sec")
    
    zoom_out_slider = obs.obs_properties_add_float_slider(props, "zoom_out_duration", 
                                                   "Zoom Out Transition Duration", 
                                                   0.0, 1.0, 0.1)
    obs.obs_property_float_set_suffix(zoom_out_slider, " sec")
    
    # Add update FPS slider
    fps_slider = obs.obs_properties_add_int_slider(props, "update_fps", "Update Frequency", 
                                           30, 240, 10)
    obs.obs_property_int_set_suffix(fps_slider, " FPS")
    
    # Debug group
    debug_group = obs.obs_properties_create()
    obs.obs_properties_add_bool(debug_group, "debug_mode", "Enable Debug Logging")
    obs.obs_properties_add_bool(debug_group, "file_logging", "Log to File")
    obs.obs_properties_add_button(debug_group, "open_log_button", "Open Log File", open_log_file_clicked)
    obs.obs_properties_add_group(props, "debug_group", "Advanced & Logging", obs.OBS_GROUP_NORMAL, debug_group)
    
    obs.obs_properties_add_text(props, "info_text", 
                             "Set hotkeys for 'Toggle Mouse Panning' and 'Toggle Mouse Zooming' in OBS Settings > Hotkeys.", 
                             obs.OBS_TEXT_INFO)
    return props

def script_defaults(settings_obj):
    """Set default values for script settings"""
    obs.obs_data_set_default_bool(settings_obj, "master_enabled", False)
    obs.obs_data_set_default_string(settings_obj, "monitor_id_string", "0:All Monitors (Virtual Screen)")
    obs.obs_data_set_default_double(settings_obj, "zoom_level", 1.0)
    obs.obs_data_set_default_int(settings_obj, "update_fps", 60)
    obs.obs_data_set_default_double(settings_obj, "zoom_in_duration", 0.3)
    obs.obs_data_set_default_double(settings_obj, "zoom_out_duration", 0.3)
    
    # Use our global variable to initialize the monitor ID if it's not 0
    global g_selected_monitor_id
    if g_selected_monitor_id > 0:
        # Find the monitor name from the ID
        monitors = get_monitor_info()
        for monitor in monitors:
            if monitor['id'] == g_selected_monitor_id:
                default_value = f"{g_selected_monitor_id}:{monitor['name']}"
                obs.obs_data_set_string(settings_obj, "monitor_id_string", default_value)
                break

def script_update(settings_obj):
    """Update script settings when changed in the properties dialog"""
    global g_selected_monitor_id
    
    # Store previous value of monitor_id before updating
    previous_monitor_id = settings["monitor_id"]
    
    # Update all settings from the object
    settings["master_enabled"] = obs.obs_data_get_bool(settings_obj, "master_enabled")
    settings["source_name"] = obs.obs_data_get_string(settings_obj, "source_name")
    settings["viewport_color_source_name"] = obs.obs_data_get_string(settings_obj, "viewport_color_source_name")
    settings["debug_mode"] = obs.obs_data_get_bool(settings_obj, "debug_mode")
    
    # Update zoom level - ensure it's between 1.0 and 5.0
    zoom_level = obs.obs_data_get_double(settings_obj, "zoom_level")
    if zoom_level < 1.0:
        zoom_level = 1.0
    elif zoom_level > 5.0:
        zoom_level = 5.0
    settings["zoom_level"] = zoom_level
    
    # Update FPS setting - ensure it's between 30 and 240
    update_fps = obs.obs_data_get_int(settings_obj, "update_fps")
    if update_fps < 30:
        update_fps = 30
    elif update_fps > 240:
        update_fps = 240
    settings["update_fps"] = update_fps
    
    # Update zoom transition durations - ensure they're between 0 and 1
    zoom_in_duration = obs.obs_data_get_double(settings_obj, "zoom_in_duration")
    if zoom_in_duration < 0.0:
        zoom_in_duration = 0.0
    elif zoom_in_duration > 1.0:
        zoom_in_duration = 1.0
    settings["zoom_in_duration"] = zoom_in_duration
    
    zoom_out_duration = obs.obs_data_get_double(settings_obj, "zoom_out_duration")
    if zoom_out_duration < 0.0:
        zoom_out_duration = 0.0
    elif zoom_out_duration > 1.0:
        zoom_out_duration = 1.0
    settings["zoom_out_duration"] = zoom_out_duration
    
    # Extract monitor ID from the composite string value
    monitor_id_string = obs.obs_data_get_string(settings_obj, "monitor_id_string")
    monitor_id = 0  # Default to all monitors (virtual screen)
    
    if monitor_id_string:
        # Parse monitor ID from the string (format: "id:name")
        try:
            monitor_id = int(monitor_id_string.split(":")[0])
            settings["monitor_id"] = monitor_id
            
            # Store in our global variable for persistence
            g_selected_monitor_id = monitor_id
            
        except Exception as e:
            log_error(f"Error parsing monitor ID from '{monitor_id_string}': {e}")
            # Keep using previous_monitor_id in case of error
            settings["monitor_id"] = previous_monitor_id
    else:
        # If no string in settings, use previous monitor ID
        settings["monitor_id"] = previous_monitor_id
        log_warning(f"No monitor ID string found, using previous value: {previous_monitor_id}")
            
    # Debug logging for settings changes
    if settings["debug_mode"]:
        log(f"Settings updated: Master={settings['master_enabled']}, " +
            f"Target={settings['source_name']}, " +
            f"Viewport={settings['viewport_color_source_name']}, " +
            f"Monitor={settings['monitor_id']} (from '{monitor_id_string}'), " +
            f"Zoom={settings['zoom_level']}x, " +
            f"Update Rate={settings['update_fps']} FPS, " +
            f"Zoom In={settings['zoom_in_duration']}s, Zoom Out={settings['zoom_out_duration']}s")
    
    # Handle monitor selection change
    if previous_monitor_id != settings["monitor_id"]:
        log(f"Monitor ID change detected: {previous_monitor_id} -> {settings['monitor_id']}")
        update_selected_monitor()

def script_load(settings_obj):
    """Called when the script is loaded in OBS"""
    global toggle_pan_hotkey_id, toggle_zoom_hotkey_id, g_current_scene_item, g_selected_monitor_id
    
    # Clear any existing references
    g_current_scene_item = None
    
    # Initialize logging
    log("Script loaded (Mouse Pan & Zoom v5.2.1)")
    init_log_file()
    
    # Load basic settings from OBS config
    settings["source_name"] = obs.obs_data_get_string(settings_obj, "source_name")
    settings["viewport_color_source_name"] = obs.obs_data_get_string(settings_obj, "viewport_color_source_name")
    settings["master_enabled"] = obs.obs_data_get_bool(settings_obj, "master_enabled")
    settings["debug_mode"] = obs.obs_data_get_bool(settings_obj, "debug_mode")
    settings["file_logging"] = obs.obs_data_get_bool(settings_obj, "file_logging")
    
    # Load zoom level
    settings["zoom_level"] = obs.obs_data_get_double(settings_obj, "zoom_level")
    if settings["zoom_level"] < 1.0:
        settings["zoom_level"] = 1.0
    elif settings["zoom_level"] > 5.0:
        settings["zoom_level"] = 5.0
    
    # Load update FPS setting
    settings["update_fps"] = obs.obs_data_get_int(settings_obj, "update_fps")
    if settings["update_fps"] < 30:
        settings["update_fps"] = 30
    elif settings["update_fps"] > 240:
        settings["update_fps"] = 240
        
    # Load transition duration settings
    settings["zoom_in_duration"] = obs.obs_data_get_double(settings_obj, "zoom_in_duration")
    if settings["zoom_in_duration"] < 0.0:
        settings["zoom_in_duration"] = 0.0
    elif settings["zoom_in_duration"] > 1.0:
        settings["zoom_in_duration"] = 1.0
        
    settings["zoom_out_duration"] = obs.obs_data_get_double(settings_obj, "zoom_out_duration")
    if settings["zoom_out_duration"] < 0.0:
        settings["zoom_out_duration"] = 0.0
    elif settings["zoom_out_duration"] > 1.0:
        settings["zoom_out_duration"] = 1.0
    
    # Load monitor ID
    monitor_id = g_selected_monitor_id
    
    # Update both our settings and global variable
    settings["monitor_id"] = monitor_id
    g_selected_monitor_id = monitor_id
    log(f"Using monitor ID: {monitor_id}")
    
    # Make sure the monitor ID string in settings matches the actual ID
    if monitor_id > 0:
        monitors = get_monitor_info()
        for monitor in monitors:
            if monitor['id'] == monitor_id:
                monitor_id_string = f"{monitor_id}:{monitor['name']}"
                obs.obs_data_set_string(settings_obj, "monitor_id_string", monitor_id_string)
                log(f"Updated settings string to '{monitor_id_string}'")
                break
    
    # Initialize monitors based on loaded settings
    update_selected_monitor()
    
    # Register hotkeys
    toggle_pan_hotkey_id = obs.obs_hotkey_register_frontend("mouse_pan_zoom_toggle_pan", "Toggle ToxMox's Pan Zoomer - Panning", toggle_panning)
    toggle_zoom_hotkey_id = obs.obs_hotkey_register_frontend("mouse_pan_zoom_toggle_zoom", "Toggle ToxMox's Pan Zoomer - Zooming", toggle_zooming)
    
    # Load pan hotkey bindings
    pan_hotkey_save_array = obs.obs_data_get_array(settings_obj, "toggle_pan_hotkey")
    if pan_hotkey_save_array:
        obs.obs_hotkey_load(toggle_pan_hotkey_id, pan_hotkey_save_array)
        obs.obs_data_array_release(pan_hotkey_save_array)
    
    # Load zoom hotkey bindings
    zoom_hotkey_save_array = obs.obs_data_get_array(settings_obj, "toggle_zoom_hotkey")
    if zoom_hotkey_save_array:
        obs.obs_hotkey_load(toggle_zoom_hotkey_id, zoom_hotkey_save_array)
        obs.obs_data_array_release(zoom_hotkey_save_array)
    
    # Calculate timer interval from FPS setting
    # Formula: interval_ms = 1000 / fps
    update_interval_ms = int(1000 / settings["update_fps"])
    log(f"Setting update interval to {update_interval_ms}ms ({settings['update_fps']} FPS)")
    
    # Start timer with the user-defined update frequency
    obs.timer_add(update_pan_and_zoom, update_interval_ms)

def script_save(settings_obj):
    """Save script settings and hotkey bindings"""
    global toggle_pan_hotkey_id, toggle_zoom_hotkey_id, g_selected_monitor_id
    
    # Save all current settings to the settings object
    obs.obs_data_set_bool(settings_obj, "master_enabled", settings["master_enabled"])
    obs.obs_data_set_string(settings_obj, "source_name", settings["source_name"])
    obs.obs_data_set_string(settings_obj, "viewport_color_source_name", settings["viewport_color_source_name"])
    obs.obs_data_set_bool(settings_obj, "debug_mode", settings["debug_mode"])
    obs.obs_data_set_bool(settings_obj, "file_logging", settings["file_logging"])
    obs.obs_data_set_double(settings_obj, "zoom_level", settings["zoom_level"])
    obs.obs_data_set_int(settings_obj, "update_fps", settings["update_fps"])
    obs.obs_data_set_double(settings_obj, "zoom_in_duration", settings["zoom_in_duration"])
    obs.obs_data_set_double(settings_obj, "zoom_out_duration", settings["zoom_out_duration"])
    
    # Save current monitor ID and update global variable
    monitor_id = settings["monitor_id"]
    g_selected_monitor_id = monitor_id
    
    # For monitor ID, find the correct monitor and create the composite string
    monitors = get_monitor_info()
    for monitor in monitors:
        if monitor['id'] == monitor_id:
            # Create composite string value
            monitor_id_string = f"{monitor_id}:{monitor['name']}"
            obs.obs_data_set_string(settings_obj, "monitor_id_string", monitor_id_string)
            log(f"Saved monitor ID {monitor_id} as '{monitor_id_string}'")
            break
    
    # Save pan hotkey bindings
    pan_hotkey_save_array = obs.obs_hotkey_save(toggle_pan_hotkey_id)
    obs.obs_data_set_array(settings_obj, "toggle_pan_hotkey", pan_hotkey_save_array)
    obs.obs_data_array_release(pan_hotkey_save_array)
    
    # Save zoom hotkey bindings
    zoom_hotkey_save_array = obs.obs_hotkey_save(toggle_zoom_hotkey_id)
    obs.obs_data_set_array(settings_obj, "toggle_zoom_hotkey", zoom_hotkey_save_array)
    obs.obs_data_array_release(zoom_hotkey_save_array)
    
    log("Settings saved")

def script_unload():
    """Clean up when script is unloaded"""
    global g_current_scene_item
    
    # Stop timer
    obs.timer_remove(update_pan_and_zoom)
    
    # Clear cached references
    g_current_scene_item = None
    
    # Release any direct source references
    if settings["direct_source_cache"]:
        obs.obs_source_release(settings["direct_source_cache"])
        settings["direct_source_cache"] = None
    
    log("Script unloaded (Mouse Pan & Zoom v5.2.1)")

# Button callbacks
def open_log_file_clicked(props, prop):
    try:
        if platform.system() == "Windows":
            os.startfile(log_file_path)
        elif platform.system() == "Darwin":
            os.system(f"open '{log_file_path}'")
        else:
            os.system(f"xdg-open '{log_file_path}'")
        return True
    except Exception as e:
        log_error(f"Failed to open log file: {e}")
        return False

# Callback for refresh sources button
def refresh_sources_clicked(props, prop):
    """Refresh the source lists in the settings dialog"""
    try:
        # Get the source list properties
        target_source_list = obs.obs_properties_get(props, "source_name")
        viewport_list = obs.obs_properties_get(props, "viewport_color_source_name")
        
        # Clear current lists
        obs.obs_property_list_clear(target_source_list)
        obs.obs_property_list_clear(viewport_list)
        
        # Re-populate with current sources
        sources = obs.obs_enum_sources()
        if sources:
            for source in sources:
                name = obs.obs_source_get_name(source)
                obs.obs_property_list_add_string(target_source_list, name, name)
                obs.obs_property_list_add_string(viewport_list, name, name)
            obs.source_list_release(sources)
        
        log("Source lists refreshed")
        return True
    except Exception as e:
        log_error(f"Failed to refresh sources: {e}")
        return False 