"""
ToxMox's Pan Zoomer for OBS
Pans a selected source based on mouse position (1:1 mapping).
Features smooth transitions and customizable zoom controls.

For OBS Studio 31.0+
Tested with Windows 11 and Python version 3.12.10 x64 installed

MIT License
Copyright (c) 2025
"""

# Global version number - increment after every change
SCRIPT_VERSION = "10.1.2"

import obspython as obs
import ctypes
import platform
import time
import math
import traceback

# Special value for scene dimensions option
USE_SCENE_DIMENSIONS = "::USE_SCENE_DIMENSIONS::"

# Try to import wintypes separately to avoid attribute error
try:
    from ctypes import wintypes
    WINTYPES_AVAILABLE = True
except ImportError:
    WINTYPES_AVAILABLE = False

# Global settings
global_settings = {
    "update_fps": 60,     # Default update rate (FPS)
}

# Config 1 settings
config1 = {
    "enabled": False,           # Master switch for this config
    "source_name": "",          # Name of the target source
    "source_uuid": "",          # UUID of the target source
    "viewport_color_source_name": "", # Name of the viewport source
    "viewport_color_source_uuid": "", # UUID of the viewport source
    "target_scene_name": "",    # Name of the scene to search for sources
    "target_scene_uuid": "",    # UUID of the scene
    "pan_enabled": False,       # Whether panning is enabled
    "zoom_enabled": False,      # Whether zooming is enabled
    "zoom_level": 1.0,          # Zoom level (1.0 to 5.0)
    "scene_name": "",           # Current scene where the source lives
    "monitor_id": 0,            # Target monitor for mouse tracking
    "direct_source_cache": None,      # Cache for direct source reference
    "direct_mode": False,            # Flag for direct plugin mode
    "direct_property_names": {"x": None, "y": None}, # Cache for plugin property names
    "zoom_in_duration": 0.3,    # Zoom IN transition duration in seconds
    "zoom_out_duration": 0.3,   # Zoom OUT transition duration in seconds
    "source_cache": [],         # Cache for source items
    "viewport_cache": [],       # Cache for viewport items
    "offset_x": 0,              # Offset X for panning (in pixels)
    "offset_y": 0,              # Offset Y for panning (in pixels)
    "viewport_alignment_correct": True, # Whether viewport alignment is correct (Top Left)
}

# Config 2 settings (initially a copy of config1)
config2 = config1.copy()
config2["enabled"] = False
config2["viewport_alignment_correct"] = True # Whether viewport alignment is correct (Top Left)

# Source information cache for config1
source_settings1 = {
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
    "crop_left": 0,
    "crop_top": 0,
    "crop_right": 0,
    "crop_bottom": 0,
    "scene_item": None, # To store the current scene item
    # Zoom transition states
    "is_transitioning": False,  # Whether a zoom transition is in progress
    "transition_start_time": 0,  # When the transition started
    "transition_start_zoom": 1.0,  # Starting zoom level
    "transition_target_zoom": 1.0,  # Target zoom level
    "transition_duration": 0.3,   # Current transition duration (set dynamically)
    "is_zooming_in": False,       # Whether we're zooming in or out
}

# Source information cache for config2 (copy)
source_settings2 = source_settings1.copy()

# For backward compatibility - these variables point to the appropriate configs
settings = config1
source_settings = source_settings1

# Screen info cache by monitor ID for reuse
monitor_cache = {}

# Default monitor info
default_monitor_info = {
    "screen_width": 1920,
    "screen_height": 1080,
    "screen_x_offset": 0,
    "screen_y_offset": 0,
}

# Current monitor info (global variable)
monitor_info = default_monitor_info.copy()

# Add global variables for hotkeys
toggle_pan_hotkey1_id = None
toggle_zoom_hotkey1_id = None
toggle_pan_hotkey2_id = None
toggle_zoom_hotkey2_id = None

# Current scene items for each config
g_current_scene_item1 = None
g_current_scene_item2 = None

# Global reference to OBS settings
script_settings = None

# Add flags to indicate script state
g_script_unloading = False
g_obs_shutting_down = False  # Special flag to detect OBS shutdown
g_exit_handler_registered = False  # Flag to track if exit handler is registered
g_in_exit_handler = False  # Flag to prevent recursive cleanup
g_is_obs_loaded = False  # Flag to track if OBS is fully loaded
g_emergency_cleanup_done = False  # Flag to track if emergency cleanup has been done

# Store OBS version information
g_obs_version_major = 0
g_obs_version_minor = 0

# Global variables for monitor selection by config
g_selected_monitor_id1 = 0
g_selected_monitor_id2 = 0


# Helper for logging warnings only once per interval
g_last_warning_time = {}
def log_warning_throttle(message, key="default", interval=1.0):
    """Log warning messages, but only once per interval to avoid spam"""
    now = time.time()
    last_time = g_last_warning_time.get(key, 0)
    if now - last_time > interval:
        log_warning(message)
        g_last_warning_time[key] = now


# Logging functions
def log(message):
    print(f"[Mouse Pan & Zoom] {message}")

def log_error(message):
    print(f"[Mouse Pan & Zoom] ERROR: {message}")

def log_warning(message):
    print(f"[Mouse Pan & Zoom] WARNING: {message}")

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
                            # Monitor info is already logged via regular logging
                            
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
    global monitor_info
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
def get_source_scene_item(source_name, source_uuid, target_config):
    """Get the scene item for a source either in the current scene or any scene, for a specific config"""
    try:
        # If we're already in direct mode for this config and have a valid direct source, use it
        if target_config.get("direct_mode") and target_config.get("direct_source_cache"):
            cached_source = target_config["direct_source_cache"]
            if cached_source:
                try:
                    # Verify by UUID first if available
                    if source_uuid:
                        cached_uuid = get_source_uuid(cached_source)
                        if cached_uuid == source_uuid:
                            dummy_item = {
                                "is_direct_source": True,
                                "source": cached_source,
                                "pos_x": 0, "pos_y": 0, "scale_x": 1.0, "scale_y": 1.0
                            }
                            return dummy_item
                    
                    current_name = obs.obs_source_get_name(cached_source)
                    if current_name == source_name:
                        dummy_item = {
                            "is_direct_source": True,
                            "source": cached_source,
                            "pos_x": 0, "pos_y": 0, "scale_x": 1.0, "scale_y": 1.0
                        }
                        return dummy_item
                except Exception as e:
                    log_error(f"Error accessing cached source for config: {e}")
                    try:
                        obs.obs_source_release(cached_source)
                    except Exception as e2:
                        log_error(f"Error releasing invalid cached source for config: {e2}")
                    target_config["direct_source_cache"] = None
        
        # Try to find source by UUID first if provided
        if source_uuid:
            if target_config.get("target_scene_name"):
                scene_source = None
                if target_config.get("target_scene_uuid"):
                    scene_source = find_source_by_uuid(target_config["target_scene_uuid"])
                if not scene_source:
                    scene_source = obs.obs_get_source_by_name(target_config["target_scene_name"])
                
                if scene_source:
                    scene = obs.obs_scene_from_source(scene_source)
                    if scene:
                        items = obs.obs_scene_enum_items(scene)
                        if items:
                            for item in items:
                                if not item: continue
                                source = obs.obs_sceneitem_get_source(item)
                                if not source: continue
                                item_uuid = get_source_uuid(source)
                                if item_uuid == source_uuid:
                                    scene_item = item
                                    items[items.index(item)] = None # Prevent release
                                    obs.sceneitem_list_release(items)
                                    obs.obs_source_release(scene_source)
                                    return scene_item
                            obs.sceneitem_list_release(items)
                    obs.obs_source_release(scene_source)
            
            direct_source = find_source_by_uuid(source_uuid)
            if direct_source:
                target_config["direct_mode"] = True
                target_config["direct_source_cache"] = direct_source
                try:
                    discover_direct_properties(direct_source, target_config)
                except Exception as e:
                    log_error(f"Error discovering properties for config: {e}")
                dummy_item = {
                    "is_direct_source": True,
                    "source": direct_source,
                    "pos_x": 0, "pos_y": 0, "scale_x": 1.0, "scale_y": 1.0
                }
                return dummy_item
        
        # Fall back to name-based search
        current_scene_name_for_config = target_config.get("scene_name", "")
        if current_scene_name_for_config:
            scene_source = obs.obs_get_source_by_name(current_scene_name_for_config)
            if scene_source:
                scene_item = find_scene_item(scene_source, source_name)
                obs.obs_source_release(scene_source)
                if scene_item:
                    return scene_item
        
        target_scene_name_for_config = target_config.get("target_scene_name", "")
        if target_scene_name_for_config:
            scene_source = obs.obs_get_source_by_name(target_scene_name_for_config)
            if scene_source:
                scene_item = find_scene_item(scene_source, source_name)
                current_scene_name = obs.obs_source_get_name(scene_source)
                target_config["scene_name"] = current_scene_name # Update current scene for this config
                obs.obs_source_release(scene_source)
                if scene_item:
                    log(f"Found source '{source_name}' in target scene '{current_scene_name}' for config")
                    return scene_item
        
        current_program_scene = obs.obs_frontend_get_current_scene()
        if current_program_scene:
            scene_item = find_scene_item(current_program_scene, source_name)
            if scene_item:
                scene_name = obs.obs_source_get_name(current_program_scene)
                target_config["scene_name"] = scene_name
                log(f"Found source '{source_name}' in current scene '{scene_name}' for config")
                obs.obs_source_release(current_program_scene)
                return scene_item
            obs.obs_source_release(current_program_scene)
        
        scenes = obs.obs_frontend_get_scenes()
        if scenes:
            for scene_source_iter in scenes:
                scene_name_iter = obs.obs_source_get_name(scene_source_iter)
                if scene_name_iter == target_config.get("scene_name") or scene_name_iter == target_config.get("target_scene_name"):
                    continue
                try:
                    scene_item = find_scene_item(scene_source_iter, source_name)
                    if scene_item:
                        target_config["scene_name"] = scene_name_iter
                        log(f"Found source '{source_name}' in scene '{scene_name_iter}' for config")
                        obs.source_list_release(scenes)
                        return scene_item
                except Exception as e:
                    log_error(f"Error searching scene {scene_name_iter} for config: {e}")
            obs.source_list_release(scenes)
        
        # Direct source access fallback for config
        source = obs.obs_get_source_by_name(source_name)
        if source:
            if target_config.get("direct_mode") and target_config.get("direct_source_cache"):
                try:
                    obs.obs_source_release(target_config["direct_source_cache"])
                except Exception as e:
                    log_error(f"Error releasing previous direct source for config: {e}")
            
            target_config["direct_mode"] = True
            target_config["direct_source_cache"] = source
            log(f"Source '{source_name}' found but not in any standard scene for config - using direct source mode")
            
            try:
                discover_direct_properties(source, target_config)
            except Exception as e:
                log_error(f"Error discovering properties for config: {e}")
            
            dummy_item = {
                "is_direct_source": True,
                "source": source,
                "pos_x": 0, "pos_y": 0, "scale_x": 1.0, "scale_y": 1.0
            }
            return dummy_item
            
        log_error(f"Could not find source '{source_name}' in any scene or directly for config")
        return None
    except Exception as e:
        log_error(f"Error getting scene item for config: {e}")
        return None

# Discover property names used by some plugins
def discover_direct_properties(source, target_config):
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
        
        # Store the property names for use later in the target_config
        target_config["direct_property_names"]["x"] = found_x
        target_config["direct_property_names"]["y"] = found_y
        
        # If we found neither, use default fallbacks that might work
        if not found_x and not found_y:
            log_warning("Could not find position properties, using 'x' and 'y' as fallbacks")
            target_config["direct_property_names"]["x"] = "x"
            target_config["direct_property_names"]["y"] = "y"
            
        log(f"Plugin position properties for config - X: {target_config['direct_property_names']['x']}, Y: {target_config['direct_property_names']['y']}")
        
        # Release settings object
        obs.obs_data_release(settings_obj)
    except Exception as e:
        log_error(f"Error discovering plugin properties: {e}")
        # Use fallbacks in the target_config
        target_config["direct_property_names"]["x"] = "x"
        target_config["direct_property_names"]["y"] = "y"


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
    else:
        # For real scene items, release them properly
        try:
            # Make a local copy of the reference before releasing
            item_to_release = scene_item
            obs.obs_sceneitem_release(item_to_release)
        except Exception as e:
            log_error(f"Error releasing scene item: {e}")
# Helper function for interpolation during transitions
def ease_in_out_quad(t):
    """Quadratic easing for smooth transitions"""
    if t < 0.5:
        return 2 * t * t
    else:
        t = t * 2 - 1
        return -0.5 * (t * (t - 2) - 1)

# Special function to detect OBS shutdown and perform emergency cleanup
def emergency_cleanup():
    """Perform emergency cleanup when OBS is detected to be shutting down"""
    # Access necessary globals
    global g_script_unloading, g_obs_shutting_down, g_emergency_cleanup_done
    global config1, config2, source_settings1, source_settings2 # For disabling features
    global g_current_scene_item1, g_current_scene_item2 # For releasing scene items

    if g_emergency_cleanup_done:
        return
        
    g_script_unloading = True
    g_obs_shutting_down = True
    g_emergency_cleanup_done = True
    
    log("EMERGENCY CLEANUP: OBS appears to be shutting down")
    
    try:
        obs.timer_remove(update_pan_and_zoom)
        log("Emergency: Removed update timer")
    except Exception as e:
        log_error(f"Emergency: Error removing timer: {e}")
    
    # Immediately disable panning and zooming for both configs
    if 'config1' in globals():
        config1["pan_enabled"] = False
        config1["zoom_enabled"] = False
    if 'source_settings1' in globals():
        source_settings1["is_transitioning"] = False

    if 'config2' in globals():
        config2["pan_enabled"] = False
        config2["zoom_enabled"] = False
    if 'source_settings2' in globals():
        source_settings2["is_transitioning"] = False
    
    # Release all references to OBS objects
    try:
        # Config 1 resources
        scene_item_to_release1 = g_current_scene_item1
        direct_source_to_release1 = config1.get("direct_source_cache") if 'config1' in globals() else None
        
        g_current_scene_item1 = None
        if 'config1' in globals():
            config1["direct_source_cache"] = None
            config1["direct_mode"] = False
        if 'source_settings1' in globals():
             source_settings1["is_initial_state_captured"] = False
        
        if scene_item_to_release1 and not isinstance(scene_item_to_release1, dict):
            try:
                obs.obs_sceneitem_release(scene_item_to_release1)
                log("Emergency: Released scene item 1")
            except Exception as e:
                log_error(f"Emergency: Error releasing scene item 1: {e}")
        
        if direct_source_to_release1:
            try:
                obs.obs_source_release(direct_source_to_release1)
                log("Emergency: Released direct source 1")
            except Exception as e:
                log_error(f"Emergency: Error releasing direct source 1: {e}")

        # Config 2 resources
        scene_item_to_release2 = g_current_scene_item2
        direct_source_to_release2 = config2.get("direct_source_cache") if 'config2' in globals() else None

        g_current_scene_item2 = None
        if 'config2' in globals():
            config2["direct_source_cache"] = None
            config2["direct_mode"] = False
        if 'source_settings2' in globals():
            source_settings2["is_initial_state_captured"] = False

        if scene_item_to_release2 and not isinstance(scene_item_to_release2, dict):
            try:
                obs.obs_sceneitem_release(scene_item_to_release2)
                log("Emergency: Released scene item 2")
            except Exception as e:
                log_error(f"Emergency: Error releasing scene item 2: {e}")
        
        if direct_source_to_release2:
            try:
                obs.obs_source_release(direct_source_to_release2)
                log("Emergency: Released direct source 2")
            except Exception as e:
                log_error(f"Emergency: Error releasing direct source 2: {e}")

    except Exception as e:
        log_error(f"Emergency cleanup error during resource release: {e}")

    # Force garbage collection
    try:
        import gc
        gc.collect()
        gc.collect()
    except Exception as e:
        log_error(f"Emergency: GC error: {e}")
    
    log("EMERGENCY CLEANUP COMPLETED")

# Helper function to check if a string value represents the "Use Scene Dimensions" option
def is_use_scene_dimensions(value):
    """Check if a string value represents the 'Use Scene Dimensions' option"""
    try:
        if not value:
            return False
        
        # Convert to string in case we get a non-string value
        str_value = str(value).strip()
        
        # Direct equality check with our constant
        if str_value == USE_SCENE_DIMENSIONS:
            return True
        
        # Check for case-insensitive match on the visible text
        if str_value.lower() == "use scene dimensions":
            return True
        
        # Check if string contains our special markers
        if "::" in str_value and "scene" in str_value.lower() and "dimension" in str_value.lower():
            return True
        
        return False
    except Exception as e:
        log_error(f"Error in is_use_scene_dimensions: {e}")
        return False

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
        source_settings["crop_left"] = 0 # Reset crop
        source_settings["crop_top"] = 0
        source_settings["crop_right"] = 0
        source_settings["crop_bottom"] = 0
        
        # Enable panning - verify we have required sources first
        target_source_name = settings["source_name"]
        target_source_uuid = settings["source_uuid"]
        viewport_source_name = settings["viewport_color_source_name"]
        viewport_source_uuid = settings["viewport_color_source_uuid"]
        
        # First check: should we be using scene dimensions?
        is_using_scene_dims = is_use_scene_dimensions(viewport_source_name)
        
        # Second check: empty viewport but we have a scene - use scene dimensions as fallback
        if not viewport_source_name and settings["target_scene_name"]:
            log_warning("No viewport source selected, but scene exists - using scene dimensions as fallback")
            is_using_scene_dims = True
            # Update settings to reflect this change
            settings["viewport_color_source_name"] = USE_SCENE_DIMENSIONS
            
        # Basic Checks
        if not target_source_name:
            log_error("Cannot enable panning: No Target Source selected.")
            settings["pan_enabled"] = False
            return
        
        # Check for viewport source - empty is valid if we're using scene dimensions
        if not viewport_source_name and not is_using_scene_dims:
            log_error(f"Cannot enable panning: No Viewport Source selected. viewport_source_name='{viewport_source_name}', is_using_scene_dims={is_using_scene_dims}")
            settings["pan_enabled"] = False
            return
        
        # Special handling for "Use Scene Dimensions" option
        if is_using_scene_dims:
            log(f"Using scene dimensions for viewport")
            
            # Get target scene
            scene_source = None
            if settings["target_scene_uuid"]:
                scene_source = find_source_by_uuid(settings["target_scene_uuid"])
            
            if not scene_source:
                scene_source = obs.obs_get_source_by_name(settings["target_scene_name"])
            
            if not scene_source:
                log_error(f"Cannot enable panning: Target Scene '{settings['target_scene_name']}' not found.")
                settings["pan_enabled"] = False
                return
                
            # Get scene dimensions
            scene_width, scene_height = get_scene_dimensions(scene_source)
            
            if scene_width <= 0 or scene_height <= 0:
                log_error(f"Cannot enable panning: Could not determine scene dimensions.")
                obs.obs_source_release(scene_source)
                settings["pan_enabled"] = False
                return
                
            # Get scene center position (0, 0) is top-left
            scene_center_x = scene_width / 2
            scene_center_y = scene_height / 2
            
            log(f"Using scene dimensions: {scene_width}x{scene_height}, Center: ({scene_center_x},{scene_center_y})")
            
            # Store viewport dimensions
            source_settings["viewport_width"] = scene_width
            source_settings["viewport_height"] = scene_height
            source_settings["viewport_scene_center_x"] = scene_center_x
            source_settings["viewport_scene_center_y"] = scene_center_y
            
            # Release scene source
            obs.obs_source_release(scene_source)
        else:
            # Regular viewport source handling
            log(f"Capturing viewport dimensions for: {viewport_source_name}")
            
            # Find the viewport source in any scene to get its bounds
            viewport_scene_item = None
            viewport_found_in_scene = False
            
            # Try to find viewport source by UUID first if available
            if viewport_source_uuid:
                viewport_source = find_source_by_uuid(viewport_source_uuid)
                if viewport_source:
                    log(f"Found viewport source '{viewport_source_name}' by UUID")
                    
                    # Now look for this source's scene item in the target scene
                    if settings["target_scene_name"]:
                        scene_source = None
                        if settings["target_scene_uuid"]:
                            scene_source = find_source_by_uuid(settings["target_scene_uuid"])
                        if not scene_source:
                            scene_source = obs.obs_get_source_by_name(settings["target_scene_name"])
                            
                        if scene_source:
                            scene = obs.obs_scene_from_source(scene_source)
                            if scene:
                                # Enumerate items to find the one with matching source
                                items = obs.obs_scene_enum_items(scene)
                                if items:
                                    for item in items:
                                        if not item:
                                            continue
                                            
                                        item_source = obs.obs_sceneitem_get_source(item)
                                        if not item_source:
                                            continue
                                            
                                        item_uuid = get_source_uuid(item_source)
                                        if item_uuid == viewport_source_uuid:
                                            viewport_scene_item = item
                                            viewport_found_in_scene = True
                                            # Don't release this specific item
                                            items[items.index(item)] = None
                                            break
                                            
                                    obs.sceneitem_list_release(items)
                            
                            obs.obs_source_release(scene_source)
                    
                    obs.obs_source_release(viewport_source)
            
            # If not found by UUID, try traditional methods
            if not viewport_found_in_scene:
                # Check current scene first
                current_scene = obs.obs_frontend_get_current_scene()
                if current_scene:
                    scene_obj = obs.obs_scene_from_source(current_scene)
                    if scene_obj:
                        viewport_scene_item = find_scene_item(current_scene, viewport_source_name)
                        if viewport_scene_item:
                            viewport_found_in_scene = True
                    obs.obs_source_release(current_scene)
                
                # If not found in current scene, search target scene
                if not viewport_found_in_scene and settings["target_scene_name"]:
                    scene_source = obs.obs_get_source_by_name(settings["target_scene_name"])
                    if scene_source:
                        scene_obj = obs.obs_scene_from_source(scene_source)
                        if scene_obj:
                            viewport_scene_item = find_scene_item(scene_source, viewport_source_name)
                            if viewport_scene_item:
                                viewport_found_in_scene = True
                        obs.obs_source_release(scene_source)
                
                # If still not found, search all scenes
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
                
                # Release the viewport scene item
                if viewport_scene_item:
                    try:
                        obs.obs_sceneitem_release(viewport_scene_item)
                    except Exception as e:
                        log_error(f"Error releasing viewport scene item: {e}")
            else:
                log_error(f"Viewport source '{viewport_source_name}' not found as an item in any scene. Panning cannot be enabled.")
                log_error("Please add the viewport source to a scene and ensure it's spelled correctly.")
                settings["pan_enabled"] = False # Crucial: Prevent enabling panning
                return
        
        # Now find and store the source item
        scene_item = get_source_scene_item(target_source_name, target_source_uuid, settings)
        if not scene_item:
            log_error(f"Cannot enable panning: Target Source '{target_source_name}' not found in any scene.")
            settings["pan_enabled"] = False
            return
        
        # IMPORTANT: Check and set alignment to CENTER
        if isinstance(scene_item, dict) and scene_item.get("is_direct_source"):
            # For direct sources, we may not be able to set alignment
            log_warning("Direct source mode does not support changing alignment. Please set Center alignment manually.")
        else:
            # For standard scene items, check and set alignment
            current_alignment = obs.obs_sceneitem_get_alignment(scene_item)
            
            # Define OBS alignment constants
            OBS_ALIGN_CENTER = 0  # This appears to be incorrect in our implementation
            
            # Try to get the constants from the obs module if available
            try:
                # These constants may be directly available in the obs module
                if hasattr(obs, "OBS_ALIGN_CENTER"):
                    OBS_ALIGN_CENTER = obs.OBS_ALIGN_CENTER
                else:
                    # If not directly available, these are the typical values
                    # OBS_ALIGN_LEFT = 0x0001
                    # OBS_ALIGN_RIGHT = 0x0002
                    # OBS_ALIGN_TOP = 0x0004
                    # OBS_ALIGN_BOTTOM = 0x0008
                    # OBS_ALIGN_CENTER = 0x0010
                    OBS_ALIGN_CENTER = 0x0010
                log(f"Using OBS_ALIGN_CENTER value: {OBS_ALIGN_CENTER}")
            except Exception as e:
                log_error(f"Error getting alignment constants: {e}, using default value 0x0010")
                OBS_ALIGN_CENTER = 0x0010  # Center alignment value
            
            # Check if alignment needs to be changed to CENTER
            if current_alignment != OBS_ALIGN_CENTER:
                log(f"Setting alignment to CENTER (was {current_alignment}, using value {OBS_ALIGN_CENTER})")
                obs.obs_sceneitem_set_alignment(scene_item, OBS_ALIGN_CENTER)
        
        # IMPORTANT: Make a copy of the scene item properties instead of storing a reference
        # This avoids keeping references to OBS objects that might cause crashes on exit
        if isinstance(scene_item, dict) and scene_item.get("is_direct_source"):
            # For direct sources, store a copy of the properties
            source = scene_item.get("source")
            if source:
                source_width = obs.obs_source_get_width(source)
                source_height = obs.obs_source_get_height(source)
                
                # Store source dimensions
                source_settings["source_base_width"] = source_width
                source_settings["source_base_height"] = source_height
                
                # Get current position and scale
                pos_x, pos_y, scale_x, scale_y = get_item_transform(scene_item)
                if pos_x is not None and scale_x is not None:
                    source_settings["initial_pos_x"] = pos_x
                    source_settings["initial_pos_y"] = pos_y
                    source_settings["initial_scale_x"] = scale_x
                    source_settings["initial_scale_y"] = scale_y
                    source_settings["is_initial_state_captured"] = True
                    log(f"Initial state captured: Pos=({pos_x:.1f},{pos_y:.1f}), Scale=({scale_x:.2f},{scale_y:.2f})")
                else:
                    source_settings["initial_pos_x"] = 0
                    source_settings["initial_pos_y"] = 0
                    source_settings["initial_scale_x"] = 1.0
                    source_settings["initial_scale_y"] = 1.0
                    source_settings["is_initial_state_captured"] = True
                    log_warning("Could not get initial transform values. Using defaults.")
                
                # Get crop values if it's a standard scene item
                crop = obs.obs_sceneitem_crop()
                obs.obs_sceneitem_get_crop(scene_item, crop)
                source_settings["crop_left"] = crop.left
                source_settings["crop_top"] = crop.top
                source_settings["crop_right"] = crop.right
                source_settings["crop_bottom"] = crop.bottom
                log(f"Captured crop: L{crop.left} T{crop.top} R{crop.right} B{crop.bottom}")
            else:
                source_settings["source_base_width"] = 1920  # Fallback
                source_settings["source_base_height"] = 1080  # Fallback
                source_settings["initial_pos_x"] = 0
                source_settings["initial_pos_y"] = 0
                source_settings["initial_scale_x"] = 1.0
                source_settings["initial_scale_y"] = 1.0
                source_settings["is_initial_state_captured"] = True
        else:
            # For standard scene items
            source = obs.obs_sceneitem_get_source(scene_item)
            if source:
                source_width = obs.obs_source_get_width(source)
                source_height = obs.obs_source_get_height(source)
                
                # Store source dimensions
                source_settings["source_base_width"] = source_width
                source_settings["source_base_height"] = source_height
                
                # Get current position and scale
                pos_x, pos_y, scale_x, scale_y = get_item_transform(scene_item)
                if pos_x is not None and scale_x is not None:
                    source_settings["initial_pos_x"] = pos_x
                    source_settings["initial_pos_y"] = pos_y
                    source_settings["initial_scale_x"] = scale_x
                    source_settings["initial_scale_y"] = scale_y
                    source_settings["is_initial_state_captured"] = True
                    log(f"Initial state captured: Pos=({pos_x:.1f},{pos_y:.1f}), Scale=({scale_x:.2f},{scale_y:.2f})")
                else:
                    source_settings["initial_pos_x"] = 0
                    source_settings["initial_pos_y"] = 0
                    source_settings["initial_scale_x"] = 1.0
                    source_settings["initial_scale_y"] = 1.0
                    source_settings["is_initial_state_captured"] = True
                    log_warning("Could not get initial transform values. Using defaults.")
                
                # Get crop values if it's a standard scene item
                crop = obs.obs_sceneitem_crop()
                obs.obs_sceneitem_get_crop(scene_item, crop)
                source_settings["crop_left"] = crop.left
                source_settings["crop_top"] = crop.top
                source_settings["crop_right"] = crop.right
                source_settings["crop_bottom"] = crop.bottom
                log(f"Captured crop: L{crop.left} T{crop.top} R{crop.right} B{crop.bottom}")
            else:
                source_settings["source_base_width"] = 1920  # Fallback
                source_settings["source_base_height"] = 1080  # Fallback
                source_settings["initial_pos_x"] = 0
                source_settings["initial_pos_y"] = 0
                source_settings["initial_scale_x"] = 1.0
                source_settings["initial_scale_y"] = 1.0
                source_settings["is_initial_state_captured"] = True
            
            # Store the scene item reference
            g_current_scene_item = scene_item
        
        log(f"Panning ENABLED for: {target_source_name}")
    else:
        log("Disabling panning...")
        
        # Disable any ongoing zoom transition
        source_settings["is_transitioning"] = False
        settings["zoom_enabled"] = False
        
        # Restore original position if we have the data and a valid scene item
        if source_settings["is_initial_state_captured"] and g_current_scene_item:
            try:
                # Restore original position and scale
                set_item_transform(
                    g_current_scene_item,
                    source_settings["initial_pos_x"],
                    source_settings["initial_pos_y"],
                    source_settings["initial_scale_x"],
                    source_settings["initial_scale_y"]
                )
                log(f"Restored position and scale to initial values")
                
                # Ensure CENTER alignment is maintained when panning is turned off
                if not isinstance(g_current_scene_item, dict):  # If it's a standard scene item
                    # Define OBS alignment constants
                    OBS_ALIGN_CENTER = 0  # This appears to be incorrect in our implementation
                    
                    # Try to get the constants from the obs module if available
                    try:
                        # These constants may be directly available in the obs module
                        if hasattr(obs, "OBS_ALIGN_CENTER"):
                            OBS_ALIGN_CENTER = obs.OBS_ALIGN_CENTER
                        else:
                            # If not directly available, these are the typical values
                            OBS_ALIGN_CENTER = 0x0010
                        log(f"Using OBS_ALIGN_CENTER value: {OBS_ALIGN_CENTER}")
                    except Exception as e:
                        log_error(f"Error getting alignment constants: {e}, using default value 0x0010")
                        OBS_ALIGN_CENTER = 0x0010  # Center alignment value
                    
                    current_alignment = obs.obs_sceneitem_get_alignment(g_current_scene_item)
                    if current_alignment != OBS_ALIGN_CENTER:
                        log(f"Maintaining CENTER alignment (was {current_alignment}, using value {OBS_ALIGN_CENTER})")
                        obs.obs_sceneitem_set_alignment(g_current_scene_item, OBS_ALIGN_CENTER)
                    
                    # Center the source on screen (center to viewport)
                    if source_settings["viewport_width"] > 0 and source_settings["viewport_height"] > 0:
                        center_x = source_settings["viewport_scene_center_x"]
                        center_y = source_settings["viewport_scene_center_y"]
                        set_item_transform(g_current_scene_item, center_x, center_y)
                        log(f"Centered source on screen at ({center_x:.1f}, {center_y:.1f})")
            except Exception as e:
                log_error(f"Error restoring position: {e}")
        
        # Make local copies of references before clearing them
        scene_item_to_release = None
        if g_current_scene_item and not isinstance(g_current_scene_item, dict):
            scene_item_to_release = g_current_scene_item
        
        direct_source_to_release = settings.get("direct_source_cache")
        
        # Clear all references BEFORE releasing them
        g_current_scene_item = None
        settings["direct_source_cache"] = None
        settings["direct_mode"] = False
        
        # Now release the resources from our local copies
        if scene_item_to_release:
            try:
                obs.obs_sceneitem_release(scene_item_to_release)
                log("Released scene item")
            except Exception as e:
                log_error(f"Error releasing scene item: {e}")
        
        if direct_source_to_release:
            try:
                obs.obs_source_release(direct_source_to_release)
                log("Released direct source")
            except Exception as e:
                log_error(f"Error releasing direct source: {e}")
        
        # Reset all state variables to defaults
        source_settings["viewport_width"] = 0
        source_settings["viewport_height"] = 0
        source_settings["viewport_scene_center_x"] = 0
        source_settings["viewport_scene_center_y"] = 0
        source_settings["source_base_width"] = 0
        source_settings["source_base_height"] = 0
        source_settings["initial_pos_x"] = 0
        source_settings["initial_pos_y"] = 0
        source_settings["initial_scale_x"] = 1.0
        source_settings["initial_scale_y"] = 1.0
        source_settings["is_initial_state_captured"] = False
        source_settings["crop_left"] = 0 # Reset crop
        source_settings["crop_top"] = 0
        source_settings["crop_right"] = 0
        source_settings["crop_bottom"] = 0
        
        # Force garbage collection
        try:
            import gc
            gc.collect()
        except Exception as e:
            log_error(f"Error during garbage collection: {e}")
        
        log("Panning DISABLED - All resources released")

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


# OBS Script Hooks
def script_description():
    return f"""<h2>ToxMox's Pan Zoomer</h2>
Pans and zooms a selected Display Capture source to be anchored to the Viewport Source based on mouse position with direct 1:1 mapping. Cropped Display Capture sources supported. The Display Capture source must be scaled to the same size or larger than the Viewport.<br>
<small>Version {SCRIPT_VERSION}</small>
"""

# Add global variables
g_selected_monitor_id = 0
g_show_instructions = False  # Track if instructions are visible

# Store setup instructions text
SETUP_INSTRUCTIONS = """<div style="margin-top: 8px; margin-bottom: 10px; padding-bottom: 5px;">
<b>1.</b> Select <b>Target Scene</b>, <b>Target Source</b> to Pan/Zoom, <b>Viewport Source</b> from dropdowns.<br>
<b>2.</b> The script will set target source's <b>Positional Alignment</b> to <b>Center</b> (via Edit Transform)<br>
<b>3.</b> Viewport Source needs Top Left setting for Positional Alignment, this is default when adding sources)<br>
<b>4.</b> Select the <b>Target Monitor</b> to track the mouse on.<br>
<b>5.</b> Adjust offset values to shift from center the Target Source panning if desired.<br>
<b>6.</b> Enable <b>Config 1 and/or Config 2</b> and set <b>Zoom Level</b> (1x-5x)<br>
<b>7.</b> Configure <b>Transition Durations</b> and <b>Update Frequency</b><br>
<b>8.</b> Use hotkeys to toggle panning/zooming (configure in OBS Settings - Hotkeys)<br>
&nbsp;&nbsp;&nbsp;&nbsp;(Hotkey Names: <b>Toggle ToxMox Pan Zoomer - Config # - Panning</b> and<br>&nbsp;&nbsp;&nbsp;&nbsp;<b>Toggle ToxMox Pan Zoomer - Config # - Zooming</b>)<br>
<b>9.</b> Panning must be activated with hotkey before Zooming hotkey works</div>
"""

def toggle_instructions_visibility(props, prop):
    """Toggle the visibility of setup instructions"""
    global g_show_instructions, script_settings
    
    # Toggle the state
    g_show_instructions = not g_show_instructions
    
    # Get the button and instruction text properties
    button = obs.obs_properties_get(props, "toggle_instructions")
    instructions_text = obs.obs_properties_get(props, "setup_instructions")
    
    # Update button text
    if g_show_instructions:
        obs.obs_property_set_description(button, "Hide Instructions")
    else:
        obs.obs_property_set_description(button, "Show Instructions")
    
    # Update text visibility
    obs.obs_property_set_visible(instructions_text, g_show_instructions)
    
    # Update the settings if available
    if script_settings:
        obs.obs_data_set_bool(script_settings, "show_instructions", g_show_instructions)
    
    # Return true to trigger UI refresh
    return True

def script_properties():
    props = obs.obs_properties_create()
    
    # Add toggle instructions button at the top
    toggle_button = obs.obs_properties_add_button(props, "toggle_instructions",
                                          "Show Instructions", toggle_instructions_visibility)
    
    # Add instructions text (hidden by default)
    instructions_text = obs.obs_properties_add_text(props, "setup_instructions",
                                            SETUP_INSTRUCTIONS, obs.OBS_TEXT_INFO)
    # Set initial visibility based on global state
    obs.obs_property_set_visible(instructions_text, g_show_instructions)
    
    # Global Settings Group
    global_group = obs.obs_properties_create()
    
    # Add update FPS slider to global settings
    fps_slider = obs.obs_properties_add_int_slider(global_group, "update_fps", "Update Frequency",
                                           30, 240, 10)
    obs.obs_property_int_set_suffix(fps_slider, " FPS")
    
    # Debug group
    # Add refresh button with improved name
    obs.obs_properties_add_button(global_group, "refresh_sources", "Refresh Scenes and Sources", refresh_sources_clicked)
    
    # Add the global group to the main properties
    obs.obs_properties_add_group(props, "global_settings", "Global Settings", obs.OBS_GROUP_NORMAL, global_group)
    
    # Create Config 1 Properties Group
    config1_props = create_config_properties(1)
    obs.obs_properties_add_group(props, "config1", "Configuration 1", obs.OBS_GROUP_NORMAL, config1_props)
    
    # Create Config 2 Properties Group
    config2_props = create_config_properties(2)
    obs.obs_properties_add_group(props, "config2", "Configuration 2", obs.OBS_GROUP_NORMAL, config2_props)
    
    obs.obs_properties_add_text(props, "info_text",
                             "Visit <a href='https://github.com/ToxMox/ToxMoxPanZoomer'>https://github.com/ToxMox/ToxMoxPanZoomer</a> for latest version of the script.",
                             obs.OBS_TEXT_INFO)
    return props

# Helper function to create config-specific properties
def create_config_properties(config_num):
    props = obs.obs_properties_create()
    
    # Use the correct config prefix for property names
    config_prefix = f"config{config_num}_"
    
    # Enable checkbox for this config
    obs.obs_properties_add_bool(props, f"{config_prefix}enabled", f"Enable Config {config_num}")
    
    # Target Scene dropdown
    scene_list = obs.obs_properties_add_list(props, f"{config_prefix}target_scene", "Target Scene",
                                     obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    
    # Add "Select Scene" as first option
    obs.obs_property_list_add_string(scene_list, "Select Scene", "")
    
    # Populate with available scenes
    scenes = obs.obs_frontend_get_scenes()
    if scenes:
        for scene in scenes:
            scene_name = obs.obs_source_get_name(scene)
            scene_uuid = get_source_uuid(scene)
            
            # Store as composite value
            composite_value = f"{scene_name}:{scene_uuid}"
            obs.obs_property_list_add_string(scene_list, scene_name, composite_value)
        obs.source_list_release(scenes)
    
    # NOTE: We'll need to modify the callback implementation later
    obs.obs_property_set_modified_callback(scene_list, on_target_scene_changed)
    
    # Target Source
    target_source_list = obs.obs_properties_add_list(props, f"{config_prefix}source_name", "Target Source Name",
                                           obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    
    # Viewport Source
    viewport_list = obs.obs_properties_add_list(props, f"{config_prefix}viewport_color_source_name", "Viewport Source Name",
                                           obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    
    # Get current config to check if we should show the lists
    current_config = config1 if config_num == 1 else config2
    has_scene_selected = current_config.get("target_scene_name", "") != ""
    
    # Populate with cached values if available
    source_cache_key = "source_cache"
    viewport_cache_key = "viewport_cache"
    
    if source_cache_key in current_config and current_config[source_cache_key]:
        # Add "Select Source" as first option for target source
        obs.obs_property_list_add_string(target_source_list, "Select Source", "")
        
        # Add cached source items
        for source_item in current_config[source_cache_key]:
            obs.obs_property_list_add_string(target_source_list, source_item["name"], source_item["value"])
        
        # Make the list visible if scene is selected
        obs.obs_property_set_visible(target_source_list, has_scene_selected)
    else:
        # Set initially to invisible if no cache
        obs.obs_property_set_visible(target_source_list, False)
    
    # Populate viewport dropdown with cached values if available
    if viewport_cache_key in current_config and current_config[viewport_cache_key]:
        # Add cached viewport items
        for viewport_item in current_config[viewport_cache_key]:
            obs.obs_property_list_add_string(viewport_list, viewport_item["name"], viewport_item["value"])
        
        # Make the list visible if scene is selected
        obs.obs_property_set_visible(viewport_list, has_scene_selected)
    else:
        # Set initially to invisible if no cache
        obs.obs_property_set_visible(viewport_list, False)
    
    # Add callbacks for selection changes - we'll need to implement the proper versions later
    obs.obs_property_set_modified_callback(target_source_list, on_target_source_changed)
    obs.obs_property_set_modified_callback(viewport_list, on_viewport_source_changed)
    
    # Monitor list - using a string property for better persistence
    monitor_list = obs.obs_properties_add_list(props, f"{config_prefix}monitor_id_string", "Target Monitor (for mouse tracking)",
                                         obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    
    # Enumerate monitors and add them to the list
    monitors = get_monitor_info()
    
    for monitor in monitors:
        # Store both ID and name in a composite string value
        value = f"{monitor['id']}:{monitor['name']}"
        # Display just the name
        obs.obs_property_list_add_string(monitor_list, monitor["name"], value)
    
    # Add offset x and y text boxes
    obs.obs_properties_add_int(props, f"{config_prefix}offset_x", "Offset X (pixels)", -2000, 2000, 1)
    obs.obs_properties_add_int(props, f"{config_prefix}offset_y", "Offset Y (pixels)", -2000, 2000, 1)
    
    # Add zoom level slider
    zoom_slider = obs.obs_properties_add_float_slider(props, f"{config_prefix}zoom_level", "Zoom Level",
                                               1.0, 5.0, 0.1)
    obs.obs_property_float_set_suffix(zoom_slider, "x")
    
    # Add zoom transition sliders
    zoom_in_slider = obs.obs_properties_add_float_slider(props, f"{config_prefix}zoom_in_duration",
                                                  "Zoom In Transition Duration",
                                                  0.0, 1.0, 0.1)
    obs.obs_property_float_set_suffix(zoom_in_slider, " sec")
    
    zoom_out_slider = obs.obs_properties_add_float_slider(props, f"{config_prefix}zoom_out_duration",
                                                   "Zoom Out Transition Duration",
                                                   0.0, 1.0, 0.1)
    obs.obs_property_float_set_suffix(zoom_out_slider, " sec")
    
    # Add viewport alignment status indicator
    current_config = config1 if config_num == 1 else config2
    alignment_status = current_config.get("viewport_alignment_correct", True)
    alignment_text = "✓ Viewport alignment correct (Top Left)" if alignment_status else "⚠ VIEWPORT ALIGNMENT INCORRECT! Set to Top Left in Edit Transform"
    alignment_style = "color: green; font-weight: bold;" if alignment_status else "color: red; font-weight: bold; background-color: #fff3cd; padding: 3px;"
    
    obs.obs_properties_add_text(props, f"{config_prefix}alignment_status",
                             f"<span style='{alignment_style}'>{alignment_text}</span>",
                             obs.OBS_TEXT_INFO)
    
    return props

def script_defaults(settings_obj):
    """Set default values for script settings"""
    # Global Settings
    obs.obs_data_set_default_int(settings_obj, "update_fps", 60)
    obs.obs_data_set_default_bool(settings_obj, "show_instructions", False)
    
    # Config 1 Defaults
    obs.obs_data_set_default_bool(settings_obj, "config1_enabled", False)
    obs.obs_data_set_default_string(settings_obj, "config1_monitor_id_string", "0:All Monitors (Virtual Screen)")
    obs.obs_data_set_default_double(settings_obj, "config1_zoom_level", 1.0)
    obs.obs_data_set_default_double(settings_obj, "config1_zoom_in_duration", 0.3)
    obs.obs_data_set_default_double(settings_obj, "config1_zoom_out_duration", 0.3)
    obs.obs_data_set_default_string(settings_obj, "config1_viewport_color_source_name", USE_SCENE_DIMENSIONS)
    obs.obs_data_set_default_int(settings_obj, "config1_offset_x", 0)
    obs.obs_data_set_default_int(settings_obj, "config1_offset_y", 0)
    
    # Config 2 Defaults
    obs.obs_data_set_default_bool(settings_obj, "config2_enabled", False)
    obs.obs_data_set_default_string(settings_obj, "config2_monitor_id_string", "0:All Monitors (Virtual Screen)")
    obs.obs_data_set_default_double(settings_obj, "config2_zoom_level", 1.0)
    obs.obs_data_set_default_double(settings_obj, "config2_zoom_in_duration", 0.3)
    obs.obs_data_set_default_double(settings_obj, "config2_zoom_out_duration", 0.3)
    obs.obs_data_set_default_string(settings_obj, "config2_viewport_color_source_name", USE_SCENE_DIMENSIONS)
    obs.obs_data_set_default_int(settings_obj, "config2_offset_x", 0)
    obs.obs_data_set_default_int(settings_obj, "config2_offset_y", 0)
    
    # Use our global variable to initialize config 1 monitor ID if it's not 0
    global g_selected_monitor_id1
    if g_selected_monitor_id1 > 0:
        # Find the monitor name from the ID
        monitors = get_monitor_info()
        for monitor in monitors:
            if monitor['id'] == g_selected_monitor_id1:
                default_value = f"{g_selected_monitor_id1}:{monitor['name']}"
                obs.obs_data_set_string(settings_obj, "config1_monitor_id_string", default_value)
                break
                
    # Do the same for config 2
    global g_selected_monitor_id2
    if g_selected_monitor_id2 > 0:
        # Find the monitor name from the ID
        monitors = get_monitor_info()
        for monitor in monitors:
            if monitor['id'] == g_selected_monitor_id2:
                default_value = f"{g_selected_monitor_id2}:{monitor['name']}"
                obs.obs_data_set_string(settings_obj, "config2_monitor_id_string", default_value)
                break

def script_update(settings_obj):
    """Update script settings when changed in the properties dialog"""
    global g_selected_monitor_id, script_settings, g_show_instructions
    
    # Store the settings object for use throughout the script
    script_settings = settings_obj
    
    # Update instructions visibility state
    g_show_instructions = obs.obs_data_get_bool(settings_obj, "show_instructions")
    
    # Store previous value of monitor_id before updating
    previous_monitor_id = settings["monitor_id"]
    
    # Update all settings from the object
    settings["master_enabled"] = obs.obs_data_get_bool(settings_obj, "master_enabled")
    
    # Update config1 settings
    config1["enabled"] = obs.obs_data_get_bool(settings_obj, "config1_enabled")
    
    # Get source and viewport settings for config1
    source_value1 = obs.obs_data_get_string(settings_obj, "config1_source_name")
    viewport_value1 = obs.obs_data_get_string(settings_obj, "config1_viewport_color_source_name")
    
    # Update config1 target source
    if ":" in source_value1:
        source_name, source_uuid = source_value1.split(":", 1)
        config1["source_name"] = source_name
        config1["source_uuid"] = source_uuid
    else:
        config1["source_name"] = source_value1
        config1["source_uuid"] = ""
    
    # Update config1 viewport source
    if is_use_scene_dimensions(viewport_value1):
        config1["viewport_color_source_name"] = USE_SCENE_DIMENSIONS
        config1["viewport_color_source_uuid"] = ""
    elif ":" in viewport_value1:
        viewport_name, viewport_uuid = viewport_value1.split(":", 1)
        config1["viewport_color_source_name"] = viewport_name
        config1["viewport_color_source_uuid"] = viewport_uuid
    else:
        config1["viewport_color_source_name"] = viewport_value1
        config1["viewport_color_source_uuid"] = ""
    
    
    # Update config2 settings
    config2["enabled"] = obs.obs_data_get_bool(settings_obj, "config2_enabled")
    
    # Get source and viewport settings for config2
    source_value2 = obs.obs_data_get_string(settings_obj, "config2_source_name")
    viewport_value2 = obs.obs_data_get_string(settings_obj, "config2_viewport_color_source_name")
    
    # Update config2 target source
    if ":" in source_value2:
        source_name, source_uuid = source_value2.split(":", 1)
        config2["source_name"] = source_name
        config2["source_uuid"] = source_uuid
    else:
        config2["source_name"] = source_value2
        config2["source_uuid"] = ""
    
    # Update config2 viewport source
    if is_use_scene_dimensions(viewport_value2):
        config2["viewport_color_source_name"] = USE_SCENE_DIMENSIONS
        config2["viewport_color_source_uuid"] = ""
    elif ":" in viewport_value2:
        viewport_name, viewport_uuid = viewport_value2.split(":", 1)
        config2["viewport_color_source_name"] = viewport_name
        config2["viewport_color_source_uuid"] = viewport_uuid
    else:
        config2["viewport_color_source_name"] = viewport_value2
        config2["viewport_color_source_uuid"] = ""
    
    # Handle target scene selection for both configs
    # Config 1 scene
    scene_value1 = obs.obs_data_get_string(settings_obj, "config1_target_scene")
    if ":" in scene_value1:
        scene_name, scene_uuid = scene_value1.split(":", 1)
        config1["target_scene_name"] = scene_name
        config1["target_scene_uuid"] = scene_uuid
    else:
        config1["target_scene_name"] = scene_value1
        config1["target_scene_uuid"] = ""
        
    # Config 2 scene
    scene_value2 = obs.obs_data_get_string(settings_obj, "config2_target_scene")
    if ":" in scene_value2:
        scene_name, scene_uuid = scene_value2.split(":", 1)
        config2["target_scene_name"] = scene_name
        config2["target_scene_uuid"] = scene_uuid
    else:
        config2["target_scene_name"] = scene_value2
        config2["target_scene_uuid"] = ""
        
    # For backwards compatibility
    settings["target_scene_name"] = config1["target_scene_name"]
    settings["target_scene_uuid"] = config1["target_scene_uuid"]
    
    # Handle global settings
    # Update FPS setting - ensure it's between 30 and 240
    update_fps = obs.obs_data_get_int(settings_obj, "update_fps")
    if update_fps < 30:
        update_fps = 30
    elif update_fps > 240:
        update_fps = 240
    global_settings["update_fps"] = update_fps
    
    # Update config1 zoom settings
    # Update zoom level - ensure it's between 1.0 and 5.0
    zoom_level1 = obs.obs_data_get_double(settings_obj, "config1_zoom_level")
    if zoom_level1 < 1.0:
        zoom_level1 = 1.0
    elif zoom_level1 > 5.0:
        zoom_level1 = 5.0
    config1["zoom_level"] = zoom_level1
    
    # Update zoom transition durations - ensure they're between 0 and 1
    zoom_in_duration1 = obs.obs_data_get_double(settings_obj, "config1_zoom_in_duration")
    if zoom_in_duration1 < 0.0:
        zoom_in_duration1 = 0.0
    elif zoom_in_duration1 > 1.0:
        zoom_in_duration1 = 1.0
    config1["zoom_in_duration"] = zoom_in_duration1
    
    zoom_out_duration1 = obs.obs_data_get_double(settings_obj, "config1_zoom_out_duration")
    if zoom_out_duration1 < 0.0:
        zoom_out_duration1 = 0.0
    elif zoom_out_duration1 > 1.0:
        zoom_out_duration1 = 1.0
    config1["zoom_out_duration"] = zoom_out_duration1
    
    # Update offset values
    config1["offset_x"] = obs.obs_data_get_int(settings_obj, "config1_offset_x")
    config1["offset_y"] = obs.obs_data_get_int(settings_obj, "config1_offset_y")
    
    # Update config2 zoom settings
    zoom_level2 = obs.obs_data_get_double(settings_obj, "config2_zoom_level")
    if zoom_level2 < 1.0:
        zoom_level2 = 1.0
    elif zoom_level2 > 5.0:
        zoom_level2 = 5.0
    config2["zoom_level"] = zoom_level2
    
    zoom_in_duration2 = obs.obs_data_get_double(settings_obj, "config2_zoom_in_duration")
    if zoom_in_duration2 < 0.0:
        zoom_in_duration2 = 0.0
    elif zoom_in_duration2 > 1.0:
        zoom_in_duration2 = 1.0
    config2["zoom_in_duration"] = zoom_in_duration2
    
    zoom_out_duration2 = obs.obs_data_get_double(settings_obj, "config2_zoom_out_duration")
    if zoom_out_duration2 < 0.0:
        zoom_out_duration2 = 0.0
    elif zoom_out_duration2 > 1.0:
        zoom_out_duration2 = 1.0
    config2["zoom_out_duration"] = zoom_out_duration2
    
    # Update offset values
    config2["offset_x"] = obs.obs_data_get_int(settings_obj, "config2_offset_x")
    config2["offset_y"] = obs.obs_data_get_int(settings_obj, "config2_offset_y")
    
    # For backwards compatibility - use values from config1
    settings["source_name"] = config1["source_name"]
    settings["source_uuid"] = config1["source_uuid"]
    settings["viewport_color_source_name"] = config1["viewport_color_source_name"]
    settings["viewport_color_source_uuid"] = config1["viewport_color_source_uuid"]
    settings["zoom_level"] = config1["zoom_level"]
    settings["update_fps"] = global_settings["update_fps"]
    settings["zoom_in_duration"] = config1["zoom_in_duration"]
    settings["zoom_out_duration"] = config1["zoom_out_duration"]
    
    # Extract monitor ID from the composite string values for both configs
    # Config 1 monitor
    monitor_id_string1 = obs.obs_data_get_string(settings_obj, "config1_monitor_id_string")
    monitor_id1 = 0  # Default to all monitors (virtual screen)
    
    if monitor_id_string1:
        # Parse monitor ID from the string (format: "id:name")
        try:
            monitor_id1 = int(monitor_id_string1.split(":")[0])
            config1["monitor_id"] = monitor_id1
            
            # Store in our global variable for persistence
            g_selected_monitor_id1 = monitor_id1
            
        except Exception as e:
            log_error(f"Error parsing monitor ID 1 from '{monitor_id_string1}': {e}")
            # Keep using previous value
            config1["monitor_id"] = previous_monitor_id if previous_monitor_id > 0 else 0
    else:
        # If no string in settings, use previous monitor ID or default
        config1["monitor_id"] = previous_monitor_id if previous_monitor_id > 0 else 0
    
    # Config 2 monitor
    monitor_id_string2 = obs.obs_data_get_string(settings_obj, "config2_monitor_id_string")
    monitor_id2 = 0  # Default to all monitors (virtual screen)
    
    if monitor_id_string2:
        # Parse monitor ID from the string (format: "id:name")
        try:
            monitor_id2 = int(monitor_id_string2.split(":")[0])
            config2["monitor_id"] = monitor_id2
            
            # Store in our global variable for persistence
            g_selected_monitor_id2 = monitor_id2
            
        except Exception as e:
            log_error(f"Error parsing monitor ID 2 from '{monitor_id_string2}': {e}")
            # Default to 0
            config2["monitor_id"] = 0
    else:
        # If no string in settings, default to 0
        config2["monitor_id"] = 0
    
    # For backwards compatibility
    settings["monitor_id"] = config1["monitor_id"]
    g_selected_monitor_id = config1["monitor_id"]
            
    # Update alignment status for both configs if viewport source is set
    # This ensures the UI shows correct alignment status even before panning is toggled
    if config1.get("viewport_color_source_name") and not is_use_scene_dimensions(config1.get("viewport_color_source_name")):
        try:
            viewport_source_name = config1.get("viewport_color_source_name")
            viewport_source_uuid = config1.get("viewport_color_source_uuid")
            viewport_found = False
            viewport_scene_item = None
            
            # Try to find viewport by UUID first
            if viewport_source_uuid:
                viewport_source = find_source_by_uuid(viewport_source_uuid)
                if viewport_source:
                    # Now search for this source in scenes
                    scenes = obs.obs_frontend_get_scenes()
                    if scenes:
                        for scene in scenes:
                            viewport_scene_item = find_scene_item(scene, viewport_source_name)
                            if viewport_scene_item:
                                viewport_found = True
                                config1["viewport_alignment_correct"] = check_viewport_alignment(
                                    viewport_scene_item, viewport_source_name, 1
                                )
                                obs.obs_sceneitem_release(viewport_scene_item)
                                break
                        obs.source_list_release(scenes)
                    obs.obs_source_release(viewport_source)
            
            # If not found by UUID, try by name
            if not viewport_found and viewport_source_name:
                scenes = obs.obs_frontend_get_scenes()
                if scenes:
                    for scene in scenes:
                        viewport_scene_item = find_scene_item(scene, viewport_source_name)
                        if viewport_scene_item:
                            config1["viewport_alignment_correct"] = check_viewport_alignment(
                                viewport_scene_item, viewport_source_name, 1
                            )
                            obs.obs_sceneitem_release(viewport_scene_item)
                            break
                    obs.source_list_release(scenes)
        except Exception as e:
            log_error(f"Error checking viewport alignment for Config 1 during update: {e}")
    
    # Same for config 2
    if config2.get("viewport_color_source_name") and not is_use_scene_dimensions(config2.get("viewport_color_source_name")):
        try:
            viewport_source_name = config2.get("viewport_color_source_name")
            viewport_source_uuid = config2.get("viewport_color_source_uuid")
            viewport_found = False
            viewport_scene_item = None
            
            # Try to find viewport by UUID first
            if viewport_source_uuid:
                viewport_source = find_source_by_uuid(viewport_source_uuid)
                if viewport_source:
                    # Now search for this source in scenes
                    scenes = obs.obs_frontend_get_scenes()
                    if scenes:
                        for scene in scenes:
                            viewport_scene_item = find_scene_item(scene, viewport_source_name)
                            if viewport_scene_item:
                                viewport_found = True
                                config2["viewport_alignment_correct"] = check_viewport_alignment(
                                    viewport_scene_item, viewport_source_name, 2
                                )
                                obs.obs_sceneitem_release(viewport_scene_item)
                                break
                        obs.source_list_release(scenes)
                    obs.obs_source_release(viewport_source)
            
            # If not found by UUID, try by name
            if not viewport_found and viewport_source_name:
                scenes = obs.obs_frontend_get_scenes()
                if scenes:
                    for scene in scenes:
                        viewport_scene_item = find_scene_item(scene, viewport_source_name)
                        if viewport_scene_item:
                            config2["viewport_alignment_correct"] = check_viewport_alignment(
                                viewport_scene_item, viewport_source_name, 2
                            )
                            obs.obs_sceneitem_release(viewport_scene_item)
                            break
                    obs.source_list_release(scenes)
        except Exception as e:
            log_error(f"Error checking viewport alignment for Config 2 during update: {e}")
    
    # Handle monitor selection change for backward compatibility
    if previous_monitor_id != config1["monitor_id"]:
        log(f"Monitor ID change detected: {previous_monitor_id} -> {config1['monitor_id']}")
        update_selected_monitor()

# Function to get OBS version
def get_obs_version():
    """Get the OBS version as major and minor numbers"""
    global g_obs_version_major, g_obs_version_minor
    
    version_string = obs.obs_get_version_string()
    log(f"OBS Version: {version_string}")
    
    # Parse version string (format like "28.0.1" or "29.1.3")
    parts = version_string.split('.')
    if len(parts) >= 2:
        try:
            g_obs_version_major = float(f"{parts[0]}.{parts[1]}")
            g_obs_version_minor = int(parts[2]) if len(parts) > 2 else 0
            log(f"Parsed OBS version: Major={g_obs_version_major}, Minor={g_obs_version_minor}")
        except Exception as e:
            log_error(f"Error parsing OBS version: {e}")
            g_obs_version_major = 0
            g_obs_version_minor = 0

# Function to thoroughly release resources
def release_all_resources():
    """Thoroughly release all resources to prevent crashes on exit"""
    global g_current_scene_item, g_in_exit_handler, g_emergency_cleanup_done
    
    if g_in_exit_handler:
        log_warning("Already in resource release process, skipping duplicate call")
        return
    
    g_in_exit_handler = True
    g_emergency_cleanup_done = True  # Mark that we've done emergency cleanup
    log("Starting thorough resource cleanup")
    
    # Stop timer first - this is critical to prevent callbacks during shutdown
    try:
        obs.timer_remove(update_pan_and_zoom)
        log("Timer removed")
    except Exception as e:
        log_error(f"Error removing timer: {e}")
    
    # Make local copies of references before clearing them
    scene_item_to_release = g_current_scene_item
    direct_source_to_release = settings.get("direct_source_cache")
    
    # Clear all references BEFORE releasing them
    g_current_scene_item = None
    if "direct_source_cache" in settings:
        settings["direct_source_cache"] = None
    
    # Clear all state
    if "direct_mode" in settings:
        settings["direct_mode"] = False
    if "pan_enabled" in settings:
        settings["pan_enabled"] = False
    if "zoom_enabled" in settings:
        settings["zoom_enabled"] = False
    if "is_transitioning" in source_settings:
        source_settings["is_transitioning"] = False
    if "is_initial_state_captured" in source_settings:
        source_settings["is_initial_state_captured"] = False
    
    # Release scene item if it's a real OBS scene item
    if scene_item_to_release and not isinstance(scene_item_to_release, dict):
        try:
            # If there are any filters attached to the source, remove them first
            if direct_source_to_release:
                try:
                    # Get all filters on the source
                    filters = obs.obs_source_enum_filters(direct_source_to_release)
                    if filters:
                        for filter in filters:
                            filter_name = obs.obs_source_get_name(filter)
                            if filter_name and "pan_zoom" in filter_name.lower():
                                obs.obs_source_filter_remove(direct_source_to_release, filter)
                        obs.source_list_release(filters)
                except Exception as e:
                    log_error(f"Error removing filters: {e}")
            
            # Reset transform info if needed
            try:
                # Check if we need to reset transform info
                if hasattr(source_settings, "initial_pos_x") and hasattr(source_settings, "initial_pos_y"):
                    pos = obs.vec2()
                    pos.x = source_settings.initial_pos_x
                    pos.y = source_settings.initial_pos_y
                    obs.obs_sceneitem_set_pos(scene_item_to_release, pos)
                    
                    if hasattr(source_settings, "initial_scale_x") and hasattr(source_settings, "initial_scale_y"):
                        scale = obs.vec2()
                        scale.x = source_settings.initial_scale_x
                        scale.y = source_settings.initial_scale_y
                        obs.obs_sceneitem_set_scale(scene_item_to_release, scale)
                    
                    log("Reset transform info to original")
            except Exception as e:
                log_error(f"Error resetting transform: {e}")
            
            # Finally release the scene item
            try:
                obs.obs_sceneitem_release(scene_item_to_release)
                log("Released scene item")
            except Exception as e:
                log_error(f"Error releasing scene item: {e}")
        except Exception as e:
            log_error(f"Error during scene item cleanup: {e}")
    
    # Release direct source if we have one
    if direct_source_to_release:
        try:
            obs.obs_source_release(direct_source_to_release)
            log("Released direct source")
        except Exception as e:
            log_error(f"Error releasing direct source: {e}")
    
    # Force garbage collection
    try:
        import gc
        log("Running garbage collection...")
        gc.collect(2)  # Full collection
        gc.collect(2)
    except Exception as e:
        log_error(f"Error during garbage collection: {e}")
    
    g_in_exit_handler = False
    log("Resource cleanup completed")

# Function to handle OBS frontend events
def on_frontend_event(event):
    """Handle OBS frontend events"""
    global g_is_obs_loaded
    
    if event == obs.OBS_FRONTEND_EVENT_SCRIPTING_SHUTDOWN:
        log_warning("OBS_FRONTEND_EVENT_SCRIPTING_SHUTDOWN received")
        # Call script_unload to ensure proper cleanup
        script_unload()
            
    elif event == obs.OBS_FRONTEND_EVENT_EXIT:
        log_warning("OBS_FRONTEND_EVENT_EXIT received")
        # Call script_unload to ensure proper cleanup
        script_unload()
            
    elif event == obs.OBS_FRONTEND_EVENT_FINISHED_LOADING:
        log("OBS_FRONTEND_EVENT_FINISHED_LOADING received")
        g_is_obs_loaded = True

def script_load(settings_obj):
    """Called when the script is loaded in OBS"""
    # Ensure global variables are accessible
    global toggle_pan_hotkey1_id, toggle_zoom_hotkey1_id, toggle_pan_hotkey2_id, toggle_zoom_hotkey2_id
    global g_current_scene_item1, g_current_scene_item2, g_is_obs_loaded, script_settings
    global global_settings, config1, config2, source_settings1, source_settings2 
    global settings, source_settings # For legacy compatibility
    global g_selected_monitor_id1, g_selected_monitor_id2

    try:
        # Store settings object for use throughout the script
        script_settings = settings_obj
        
        # Clear dynamic references/state
        g_current_scene_item1 = None
        g_current_scene_item2 = None
        g_is_obs_loaded = False
        
        # Load script
        log(f"Script loaded (Mouse Pan & Zoom v{SCRIPT_VERSION})")

        # Load Global Settings
        global_settings["update_fps"] = obs.obs_data_get_int(settings_obj, "update_fps")
        if global_settings["update_fps"] == 0 and not obs.obs_data_has_user_value(settings_obj, "update_fps"):
            global_settings["update_fps"] = 60

        # Load Config 1 Settings
        config1["enabled"] = obs.obs_data_get_bool(settings_obj, "config1_enabled")
        scene_value1 = obs.obs_data_get_string(settings_obj, "config1_target_scene")
        if ":" in scene_value1: config1["target_scene_name"], config1["target_scene_uuid"] = scene_value1.split(":", 1)
        else: config1["target_scene_name"], config1["target_scene_uuid"] = scene_value1, ""
        source_value1 = obs.obs_data_get_string(settings_obj, "config1_source_name")
        if ":" in source_value1: config1["source_name"], config1["source_uuid"] = source_value1.split(":", 1)
        else: config1["source_name"], config1["source_uuid"] = source_value1, ""
        viewport_value1 = obs.obs_data_get_string(settings_obj, "config1_viewport_color_source_name")
        if is_use_scene_dimensions(viewport_value1): config1["viewport_color_source_name"], config1["viewport_color_source_uuid"] = USE_SCENE_DIMENSIONS, ""
        elif ":" in viewport_value1: config1["viewport_color_source_name"], config1["viewport_color_source_uuid"] = viewport_value1.split(":", 1)
        else: config1["viewport_color_source_name"], config1["viewport_color_source_uuid"] = viewport_value1, ""
        config1["zoom_level"] = obs.obs_data_get_double(settings_obj, "config1_zoom_level")
        if not obs.obs_data_has_user_value(settings_obj, "config1_zoom_level"): config1["zoom_level"] = 1.0
        elif config1["zoom_level"] < 1.0: config1["zoom_level"] = 1.0
        config1["zoom_in_duration"] = obs.obs_data_get_double(settings_obj, "config1_zoom_in_duration")
        if not obs.obs_data_has_user_value(settings_obj, "config1_zoom_in_duration"): config1["zoom_in_duration"] = 0.3
        config1["zoom_out_duration"] = obs.obs_data_get_double(settings_obj, "config1_zoom_out_duration")
        if not obs.obs_data_has_user_value(settings_obj, "config1_zoom_out_duration"): config1["zoom_out_duration"] = 0.3
        monitor_id_string1 = obs.obs_data_get_string(settings_obj, "config1_monitor_id_string")
        if monitor_id_string1 and ":" in monitor_id_string1: 
            try: config1["monitor_id"] = int(monitor_id_string1.split(":")[0]); g_selected_monitor_id1 = config1["monitor_id"]
            except ValueError: config1["monitor_id"], g_selected_monitor_id1 = 0, 0
        else: config1["monitor_id"], g_selected_monitor_id1 = 0, 0

        # Load Config 2 Settings
        config2["enabled"] = obs.obs_data_get_bool(settings_obj, "config2_enabled")
        scene_value2 = obs.obs_data_get_string(settings_obj, "config2_target_scene")
        if ":" in scene_value2: config2["target_scene_name"], config2["target_scene_uuid"] = scene_value2.split(":", 1)
        else: config2["target_scene_name"], config2["target_scene_uuid"] = scene_value2, ""
        source_value2 = obs.obs_data_get_string(settings_obj, "config2_source_name")
        if ":" in source_value2: config2["source_name"], config2["source_uuid"] = source_value2.split(":", 1)
        else: config2["source_name"], config2["source_uuid"] = source_value2, ""
        viewport_value2 = obs.obs_data_get_string(settings_obj, "config2_viewport_color_source_name")
        if is_use_scene_dimensions(viewport_value2): config2["viewport_color_source_name"], config2["viewport_color_source_uuid"] = USE_SCENE_DIMENSIONS, ""
        elif ":" in viewport_value2: config2["viewport_color_source_name"], config2["viewport_color_source_uuid"] = viewport_value2.split(":", 1)
        else: config2["viewport_color_source_name"], config2["viewport_color_source_uuid"] = viewport_value2, ""
        config2["zoom_level"] = obs.obs_data_get_double(settings_obj, "config2_zoom_level")
        if not obs.obs_data_has_user_value(settings_obj, "config2_zoom_level"): config2["zoom_level"] = 1.0
        elif config2["zoom_level"] < 1.0: config2["zoom_level"] = 1.0
        config2["zoom_in_duration"] = obs.obs_data_get_double(settings_obj, "config2_zoom_in_duration")
        if not obs.obs_data_has_user_value(settings_obj, "config2_zoom_in_duration"): config2["zoom_in_duration"] = 0.3
        config2["zoom_out_duration"] = obs.obs_data_get_double(settings_obj, "config2_zoom_out_duration")
        if not obs.obs_data_has_user_value(settings_obj, "config2_zoom_out_duration"): config2["zoom_out_duration"] = 0.3
        monitor_id_string2 = obs.obs_data_get_string(settings_obj, "config2_monitor_id_string")
        if monitor_id_string2 and ":" in monitor_id_string2: 
            try: config2["monitor_id"] = int(monitor_id_string2.split(":")[0]); g_selected_monitor_id2 = config2["monitor_id"]
            except ValueError: config2["monitor_id"], g_selected_monitor_id2 = 0, 0
        else: config2["monitor_id"], g_selected_monitor_id2 = 0, 0

        # Initialize/reset dynamic source_settings
        default_ss_values = {
            "viewport_width": 0, "viewport_height": 0, "viewport_scene_center_x": 0.0,
            "viewport_scene_center_y": 0.0, "source_base_width": 0, "source_base_height": 0,
            "is_initial_state_captured": False, "initial_pos_x": 0.0, "initial_pos_y": 0.0,
            "initial_scale_x": 1.0, "initial_scale_y": 1.0, "crop_left": 0, "crop_top": 0,
            "crop_right": 0, "crop_bottom": 0, "scene_item": None,
            "is_transitioning": False, "transition_start_time": 0, "transition_start_zoom": 1.0,
            "transition_target_zoom": 1.0, "transition_duration": 0.3, "is_zooming_in": False
        }
        source_settings1.clear(); source_settings1.update(default_ss_values)
        source_settings2.clear(); source_settings2.update(default_ss_values)
        
        settings = config1 # Legacy alias
        source_settings = source_settings1 # Legacy alias

        # Register for OBS frontend events 
        obs.obs_frontend_add_event_callback(on_frontend_event)

        # Initialize hotkey IDs to None
        toggle_pan_hotkey1_id, toggle_zoom_hotkey1_id = None, None
        toggle_pan_hotkey2_id, toggle_zoom_hotkey2_id = None, None

        # Register hotkeys
        toggle_pan_hotkey1_id = obs.obs_hotkey_register_frontend("mouse_pan_zoom_toggle_pan1", "Toggle ToxMox Pan Zoomer - Config 1 - Panning", toggle_panning1)
        toggle_zoom_hotkey1_id = obs.obs_hotkey_register_frontend("mouse_pan_zoom_toggle_zoom1", "Toggle ToxMox Pan Zoomer - Config 1 - Zooming", toggle_zooming1)
        toggle_pan_hotkey2_id = obs.obs_hotkey_register_frontend("mouse_pan_zoom_toggle_pan2", "Toggle ToxMox Pan Zoomer - Config 2 - Panning", toggle_panning2)
        toggle_zoom_hotkey2_id = obs.obs_hotkey_register_frontend("mouse_pan_zoom_toggle_zoom2", "Toggle ToxMox Pan Zoomer - Config 2 - Zooming", toggle_zooming2)

        # Load hotkey bindings from saved settings
        if toggle_pan_hotkey1_id: 
            arr = obs.obs_data_get_array(settings_obj, "toggle_pan_hotkey1"); obs.obs_hotkey_load(toggle_pan_hotkey1_id, arr); obs.obs_data_array_release(arr)
        if toggle_zoom_hotkey1_id: 
            arr = obs.obs_data_get_array(settings_obj, "toggle_zoom_hotkey1"); obs.obs_hotkey_load(toggle_zoom_hotkey1_id, arr); obs.obs_data_array_release(arr)
        if toggle_pan_hotkey2_id: 
            arr = obs.obs_data_get_array(settings_obj, "toggle_pan_hotkey2"); obs.obs_hotkey_load(toggle_pan_hotkey2_id, arr); obs.obs_data_array_release(arr)
        if toggle_zoom_hotkey2_id:
            arr = obs.obs_data_get_array(settings_obj, "toggle_zoom_hotkey2"); obs.obs_hotkey_load(toggle_zoom_hotkey2_id, arr); obs.obs_data_array_release(arr)

        # Defer these UI/state update calls until after critical setup and hotkey registration
        update_selected_monitor() # Uses legacy `settings` (config1)
        
        # Refresh caches for both configurations based on loaded settings
        refresh_caches_for_config(config1)
        refresh_caches_for_config(config2)

        # Calculate timer interval and start timer
        update_interval_ms = int(1000 / global_settings.get("update_fps", 60))
        obs.timer_add(update_pan_and_zoom, update_interval_ms)
        log(f"Update timer started with interval {update_interval_ms}ms.")

    except Exception as e:
        log_error(f"CRITICAL ERROR IN SCRIPT_LOAD: {e}\n{traceback.format_exc()}")
        # Ensure hotkey IDs are None if registration failed catastrophically
        toggle_pan_hotkey1_id, toggle_zoom_hotkey1_id = None, None
        toggle_pan_hotkey2_id, toggle_zoom_hotkey2_id = None, None

def script_save(settings_obj):
    """Save script settings and hotkey bindings"""
    # Ensure global hotkey IDs are accessible
    global toggle_pan_hotkey1_id, toggle_zoom_hotkey1_id, toggle_pan_hotkey2_id, toggle_zoom_hotkey2_id
    # Ensure global config settings are accessible for saving
    global global_settings, config1, config2, g_selected_monitor_id1, g_selected_monitor_id2, g_show_instructions


    # Save Global Settings
    obs.obs_data_set_int(settings_obj, "update_fps", global_settings.get("update_fps", 60))
    obs.obs_data_set_bool(settings_obj, "show_instructions", g_show_instructions)

    # Save Config 1 Settings
    obs.obs_data_set_bool(settings_obj, "config1_enabled", config1.get("enabled", False))
    
    # Scene (name:uuid)
    scene1_name = config1.get("target_scene_name", "")
    scene1_uuid = config1.get("target_scene_uuid", "")
    if scene1_uuid:
        obs.obs_data_set_string(settings_obj, "config1_target_scene", f"{scene1_name}:{scene1_uuid}")
    else:
        obs.obs_data_set_string(settings_obj, "config1_target_scene", scene1_name)

    # Source (name:uuid)
    source1_name = config1.get("source_name", "")
    source1_uuid = config1.get("source_uuid", "")
    if source1_uuid:
        obs.obs_data_set_string(settings_obj, "config1_source_name", f"{source1_name}:{source1_uuid}")
    else:
        obs.obs_data_set_string(settings_obj, "config1_source_name", source1_name)

    # Viewport (name:uuid or special value)
    viewport1_val = config1.get("viewport_color_source_name", "")
    viewport1_uuid = config1.get("viewport_color_source_uuid", "")
    if viewport1_val == USE_SCENE_DIMENSIONS:
        obs.obs_data_set_string(settings_obj, "config1_viewport_color_source_name", USE_SCENE_DIMENSIONS)
    elif viewport1_uuid:
        obs.obs_data_set_string(settings_obj, "config1_viewport_color_source_name", f"{viewport1_val}:{viewport1_uuid}")
    else:
        obs.obs_data_set_string(settings_obj, "config1_viewport_color_source_name", viewport1_val)

    obs.obs_data_set_double(settings_obj, "config1_zoom_level", config1.get("zoom_level", 1.0))
    obs.obs_data_set_double(settings_obj, "config1_zoom_in_duration", config1.get("zoom_in_duration", 0.3))
    obs.obs_data_set_double(settings_obj, "config1_zoom_out_duration", config1.get("zoom_out_duration", 0.3))
    obs.obs_data_set_int(settings_obj, "config1_offset_x", config1.get("offset_x", 0))
    obs.obs_data_set_int(settings_obj, "config1_offset_y", config1.get("offset_y", 0))
    
    monitor_id1 = config1.get("monitor_id", 0)
    monitors = get_monitor_info() # Re-fetch to ensure names are current
    monitor_name1 = "All Monitors (Virtual Screen)" # Default
    for monitor in monitors:
        if monitor['id'] == monitor_id1:
            monitor_name1 = monitor['name']
            break
    obs.obs_data_set_string(settings_obj, "config1_monitor_id_string", f"{monitor_id1}:{monitor_name1}")


    # Save Config 2 Settings
    obs.obs_data_set_bool(settings_obj, "config2_enabled", config2.get("enabled", False))

    scene2_name = config2.get("target_scene_name", "")
    scene2_uuid = config2.get("target_scene_uuid", "")
    if scene2_uuid:
        obs.obs_data_set_string(settings_obj, "config2_target_scene", f"{scene2_name}:{scene2_uuid}")
    else:
        obs.obs_data_set_string(settings_obj, "config2_target_scene", scene2_name)

    source2_name = config2.get("source_name", "")
    source2_uuid = config2.get("source_uuid", "")
    if source2_uuid:
        obs.obs_data_set_string(settings_obj, "config2_source_name", f"{source2_name}:{source2_uuid}")
    else:
        obs.obs_data_set_string(settings_obj, "config2_source_name", source2_name)

    viewport2_val = config2.get("viewport_color_source_name", "")
    viewport2_uuid = config2.get("viewport_color_source_uuid", "")
    if viewport2_val == USE_SCENE_DIMENSIONS:
        obs.obs_data_set_string(settings_obj, "config2_viewport_color_source_name", USE_SCENE_DIMENSIONS)
    elif viewport2_uuid:
        obs.obs_data_set_string(settings_obj, "config2_viewport_color_source_name", f"{viewport2_val}:{viewport2_uuid}")
    else:
        obs.obs_data_set_string(settings_obj, "config2_viewport_color_source_name", viewport2_val)

    obs.obs_data_set_double(settings_obj, "config2_zoom_level", config2.get("zoom_level", 1.0))
    obs.obs_data_set_double(settings_obj, "config2_zoom_in_duration", config2.get("zoom_in_duration", 0.3))
    obs.obs_data_set_double(settings_obj, "config2_zoom_out_duration", config2.get("zoom_out_duration", 0.3))
    obs.obs_data_set_int(settings_obj, "config2_offset_x", config2.get("offset_x", 0))
    obs.obs_data_set_int(settings_obj, "config2_offset_y", config2.get("offset_y", 0))

    monitor_id2 = config2.get("monitor_id", 0)
    monitor_name2 = "All Monitors (Virtual Screen)" # Default
    for monitor in monitors: # Reuse fetched monitors
        if monitor['id'] == monitor_id2:
            monitor_name2 = monitor['name']
            break
    obs.obs_data_set_string(settings_obj, "config2_monitor_id_string", f"{monitor_id2}:{monitor_name2}")

    # Save Hotkey Bindings
    try:
        if toggle_pan_hotkey1_id is not None:
            pan_hotkey1_save_array = obs.obs_hotkey_save(toggle_pan_hotkey1_id)
            if pan_hotkey1_save_array:
                obs.obs_data_set_array(settings_obj, "toggle_pan_hotkey1", pan_hotkey1_save_array)
                obs.obs_data_array_release(pan_hotkey1_save_array)
        
        if toggle_zoom_hotkey1_id is not None:
            zoom_hotkey1_save_array = obs.obs_hotkey_save(toggle_zoom_hotkey1_id)
            if zoom_hotkey1_save_array:
                obs.obs_data_set_array(settings_obj, "toggle_zoom_hotkey1", zoom_hotkey1_save_array)
                obs.obs_data_array_release(zoom_hotkey1_save_array)
        
        if toggle_pan_hotkey2_id is not None:
            pan_hotkey2_save_array = obs.obs_hotkey_save(toggle_pan_hotkey2_id)
            if pan_hotkey2_save_array:
                obs.obs_data_set_array(settings_obj, "toggle_pan_hotkey2", pan_hotkey2_save_array)
                obs.obs_data_array_release(pan_hotkey2_save_array)
        
        if toggle_zoom_hotkey2_id is not None:
            zoom_hotkey2_save_array = obs.obs_hotkey_save(toggle_zoom_hotkey2_id)
            if zoom_hotkey2_save_array:
                obs.obs_data_set_array(settings_obj, "toggle_zoom_hotkey2", zoom_hotkey2_save_array)
                obs.obs_data_array_release(zoom_hotkey2_save_array)
    except Exception as e:
        log_error(f"Error saving hotkeys: {e}")
    
    log("Settings saved successfully by script_save")

# Python exit handler - will be called when Python is exiting
def python_exit_handler():
    """Special handler that runs when Python is exiting"""
    global g_in_exit_handler, g_script_unloading, g_obs_shutting_down, g_emergency_cleanup_done
    
    # Prevent recursive calls
    if g_in_exit_handler:
        return
        
    g_in_exit_handler = True
    g_script_unloading = True
    g_obs_shutting_down = True
    
    log_warning(f"PYTHON EXIT HANDLER ACTIVATED (Mouse Pan & Zoom v{SCRIPT_VERSION})")
    
    # If we haven't done emergency cleanup yet, do it now
    if not g_emergency_cleanup_done:
        try:
            emergency_cleanup()
        except Exception as e:
            log_error(f"Error in emergency cleanup during exit handler: {e}")
    
    try:
        # Perform ultra-aggressive cleanup
        perform_ultra_aggressive_cleanup()
    except Exception as e:
        log_error(f"Error in exit handler: {e}")
    
    log_warning("PYTHON EXIT HANDLER COMPLETED")
    g_in_exit_handler = False

# Ultra-aggressive cleanup function
def perform_ultra_aggressive_cleanup():
    """Perform the most aggressive cleanup possible"""
    global g_current_scene_item, g_emergency_cleanup_done
    
    # Mark that we've done emergency cleanup
    g_emergency_cleanup_done = True
    
    log_warning("Performing ultra-aggressive cleanup")
    
    # First, remove the timer to prevent any further callbacks
    try:
        obs.timer_remove(update_pan_and_zoom)
        log_warning("Ultra: Removed update timer")
    except Exception as e:
        log_error(f"Ultra: Error removing timer: {e}")
    
    # 1. Clear all global references that might hold OBS objects
    scene_item_to_release = g_current_scene_item
    direct_source_to_release = settings.get("direct_source_cache")
    
    # Clear references immediately
    g_current_scene_item = None
    if "direct_source_cache" in settings:
        settings["direct_source_cache"] = None
    
    # Clear all state variables
    if "direct_mode" in settings:
        settings["direct_mode"] = False
    if "pan_enabled" in settings:
        settings["pan_enabled"] = False
    if "zoom_enabled" in settings:
        settings["zoom_enabled"] = False
    
    if "is_transitioning" in source_settings:
        source_settings["is_transitioning"] = False
    if "is_initial_state_captured" in source_settings:
        source_settings["is_initial_state_captured"] = False
    
    # 2. Try to release resources
    try:
        # Release scene item if it's a real OBS scene item
        if scene_item_to_release and not isinstance(scene_item_to_release, dict):
            try:
                obs.obs_sceneitem_release(scene_item_to_release)
                log("Released scene item in ultra cleanup")
            except Exception as e:
                log_error(f"Error releasing scene item in ultra cleanup: {e}")
        
        # Release direct source if we have one
        if direct_source_to_release:
            try:
                obs.obs_source_release(direct_source_to_release)
                log("Released direct source in ultra cleanup")
            except Exception as e:
                log_error(f"Error releasing direct source in ultra cleanup: {e}")
    except Exception as e:
        log_error(f"Error during ultra resource cleanup: {e}")
    
    # 3. Force multiple garbage collections
    try:
        import gc
        log("Running ultra garbage collection...")
        gc.collect(2)  # Full collection
        gc.collect(2)
        gc.collect(2)
    except Exception as e:
        log_error(f"Error during ultra garbage collection: {e}")
    
    # 4. Try to clear any remaining references in the module
    try:
        # Clear any module-level references that might be holding OBS objects
        import sys
        this_module = sys.modules.get(__name__)
        if this_module:
            for attr_name in dir(this_module):
                if attr_name.startswith('__'):
                    continue
                try:
                    if hasattr(this_module, attr_name):
                        setattr(this_module, attr_name, None)
                except Exception:
                    pass
    except Exception as e:
        log_error(f"Error clearing module references: {e}")

def script_unload():
    """Clean up when script is unloaded"""
    # Access all necessary globals for cleanup
    global g_current_scene_item1, g_current_scene_item2, script_settings # script_settings might be None if load failed
    global toggle_pan_hotkey1_id, toggle_zoom_hotkey1_id, toggle_pan_hotkey2_id, toggle_zoom_hotkey2_id
    global config1, config2, source_settings1, source_settings2, global_settings

    log("Script unload started")

    # Stop timer first to prevent any further callbacks
    try:
        obs.timer_remove(update_pan_and_zoom) # update_pan_and_zoom is the correct timer function name
        log("Timer removed")
    except Exception as e:
        log_error(f"Error removing timer: {e}")
        
    # Clean up hotkeys properly
    try:
        if toggle_pan_hotkey1_id is not None:
            obs.obs_hotkey_unregister(toggle_pan_hotkey1_id)
            toggle_pan_hotkey1_id = None
        if toggle_zoom_hotkey1_id is not None:
            obs.obs_hotkey_unregister(toggle_zoom_hotkey1_id)
            toggle_zoom_hotkey1_id = None
        if toggle_pan_hotkey2_id is not None:
            obs.obs_hotkey_unregister(toggle_pan_hotkey2_id)
            toggle_pan_hotkey2_id = None
        if toggle_zoom_hotkey2_id is not None:
            obs.obs_hotkey_unregister(toggle_zoom_hotkey2_id)
            toggle_zoom_hotkey2_id = None
        log("Hotkeys unregistered")
    except Exception as e:
        log_error(f"Error unregistering hotkeys: {e}")

    # Helper function to reset a specific config's state and release its resources
    def cleanup_config_resources(cfg, src_settings, scene_item_global_name):
        # Check if cfg and src_settings are valid dictionaries before proceeding
        if not isinstance(cfg, dict) or not isinstance(src_settings, dict):
            log_warning(f"Skipping cleanup for {scene_item_global_name} due to invalid config/source_settings.")
            return
            
        current_scene_item_val = globals().get(scene_item_global_name)

        if cfg.get("pan_enabled", False):
            log(f"Disabling panning for {scene_item_global_name} during unload")
            src_settings["is_transitioning"] = False
            cfg["zoom_enabled"] = False
            cfg["pan_enabled"] = False

            if src_settings.get("is_initial_state_captured") and current_scene_item_val:
                try:
                    set_item_transform(
                        current_scene_item_val,
                        src_settings["initial_pos_x"],
                        src_settings["initial_pos_y"],
                        src_settings["initial_scale_x"],
                        src_settings["initial_scale_y"]
                    )
                    log(f"Restored original position/scale for {scene_item_global_name}")
                except Exception as e:
                    log_error(f"Error restoring position for {scene_item_global_name}: {e}")
        
        scene_item_to_release = None
        if current_scene_item_val and not isinstance(current_scene_item_val, dict):
            scene_item_to_release = current_scene_item_val
        
        direct_source_to_release = cfg.get("direct_source_cache")

        # Use a try-except block for globals().set to handle potential issues if the global doesn't exist
        try:
            globals()[scene_item_global_name] = None # Clear the global scene item reference
        except KeyError:
            log_warning(f"Global variable {scene_item_global_name} not found for clearing.")

        if "direct_source_cache" in cfg: cfg["direct_source_cache"] = None
        if "direct_mode" in cfg: cfg["direct_mode"] = False

        if scene_item_to_release:
            try:
                obs.obs_sceneitem_release(scene_item_to_release)
                log(f"Released scene item for {scene_item_global_name}")
            except Exception as e:
                log_error(f"Error releasing scene item for {scene_item_global_name}: {e}")
        
        if direct_source_to_release:
            try:
                obs.obs_source_release(direct_source_to_release)
                log(f"Released direct source for {scene_item_global_name}")
            except Exception as e:
                log_error(f"Error releasing direct source for {scene_item_global_name}: {e}")

        # Reset all state variables to defaults for this config's source_settings
        default_source_settings_values = {
            "viewport_width": 0, "viewport_height": 0, "viewport_scene_center_x": 0.0,
            "viewport_scene_center_y": 0.0, "source_base_width": 0, "source_base_height": 0,
            "is_initial_state_captured": False, "initial_pos_x": 0.0, "initial_pos_y": 0.0,
            "initial_scale_x": 1.0, "initial_scale_y": 1.0, "crop_left": 0, "crop_top": 0,
            "crop_right": 0, "crop_bottom": 0, "scene_item": None,
            "is_transitioning": False, "transition_start_time": 0, "transition_start_zoom": 1.0,
            "transition_target_zoom": 1.0, "transition_duration": 0.3, "is_zooming_in": False
        }
        src_settings.clear()
        src_settings.update(default_source_settings_values)

    # Cleanup resources for Config 1
    # Ensure config1 and source_settings1 exist before calling cleanup to prevent errors during early/failed script load
    if isinstance(config1, dict) and isinstance(source_settings1, dict):
        cleanup_config_resources(config1, source_settings1, "g_current_scene_item1")
    else:
        log_warning("Config1 or source_settings1 not properly initialized for unload cleanup.")

    # Cleanup resources for Config 2
    if isinstance(config2, dict) and isinstance(source_settings2, dict):
        cleanup_config_resources(config2, source_settings2, "g_current_scene_item2")
    else:
        log_warning("Config2 or source_settings2 not properly initialized for unload cleanup.")
    
    # Force garbage collection
    try:
        import gc
        gc.collect()
        log("Garbage collection performed")
    except Exception as e:
        log_error(f"Error during garbage collection: {e}")
    
    log(f"Script unload completed (Mouse Pan & Zoom v{SCRIPT_VERSION})")

# Button callbacks

# Callback for refresh sources button
def refresh_sources_clicked(props, prop):
    """Refresh the scene and source lists in the settings dialog for both configs"""
    try:
        # First, update the internal caches for both configurations
        # This will use the currently selected scenes in config1 and config2 settings dicts
        refresh_caches_for_config(config1)
        refresh_caches_for_config(config2)

        # Helper to repopulate UI lists for a given config number
        def repopulate_ui_for_config(p, config_num_str, current_cfg):
            prefix = f"config{config_num_str}_"
            target_scene_list_prop = obs.obs_properties_get(p, f"{prefix}target_scene")
            target_source_list_prop = obs.obs_properties_get(p, f"{prefix}source_name")
            viewport_list_prop = obs.obs_properties_get(p, f"{prefix}viewport_color_source_name")

            # --- Repopulate Scene List (already up-to-date by OBS, but good to ensure selection)
            # We still clear and repopulate to manage our specific name:uuid format and "Select Scene" option.
            obs.obs_property_list_clear(target_scene_list_prop) 
            obs.obs_property_list_add_string(target_scene_list_prop, "Select Scene", "") # Default empty option
            scenes = obs.obs_frontend_get_scenes()
            if scenes:
                for scene_obj in scenes:
                    s_name = obs.obs_source_get_name(scene_obj)
                    s_uuid = get_source_uuid(scene_obj)
                    val = f"{s_name}:{s_uuid}"
                    obs.obs_property_list_add_string(target_scene_list_prop, s_name, val)
                obs.source_list_release(scenes)
            
            # --- Repopulate Target Source List from its cache
            obs.obs_property_list_clear(target_source_list_prop)
            obs.obs_property_list_add_string(target_source_list_prop, "Select Source", "") # Blank option
            if current_cfg.get("source_cache"):
                for source_item in current_cfg["source_cache"]:
                    obs.obs_property_list_add_string(target_source_list_prop, source_item["name"], source_item["value"])
            
            # --- Repopulate Viewport Source List from its cache
            obs.obs_property_list_clear(viewport_list_prop)
            # The viewport_cache (populated by refresh_caches_for_config) 
            # should have "Use Scene Dimensions" as the first item if a scene is selected.
            # If no scene is selected for the config, its viewport_cache will be empty (or just have "Select Source").
            if not current_cfg.get("target_scene_name"):
                 obs.obs_property_list_add_string(viewport_list_prop, "Select Source", "") # Blank if no scene for this config
            
            if current_cfg.get("viewport_cache"):
                for viewport_item in current_cfg["viewport_cache"]:
                    obs.obs_property_list_add_string(viewport_list_prop, viewport_item["name"], viewport_item["value"])

            # Set visibility based on whether a scene is selected for this config
            has_scene_selected = bool(current_cfg.get("target_scene_name"))
            obs.obs_property_set_visible(target_source_list_prop, has_scene_selected)
            obs.obs_property_set_visible(viewport_list_prop, has_scene_selected)

        # Repopulate UI for both configs
        repopulate_ui_for_config(props, "1", config1)
        repopulate_ui_for_config(props, "2", config2)
        
        log("Scene and source lists UI refreshed manually.")
        return True # Important: must return True for OBS to update properties UI
    except Exception as e:
        log_error(f"Failed to refresh scenes and sources UI: {e}\n{traceback.format_exc()}")
        return False

# Helper function to get a source's UUID
def get_source_uuid(source):
    """Get the UUID of a source as a string, or the source name if UUID functions are unavailable"""
    try:
        # Check if OBS UUID functions are available (OBS 31.0+)
        if hasattr(obs, "obs_source_get_uuid") and hasattr(obs, "obs_source_get_uuid_str"):
            uuid = obs.obs_source_get_uuid(source)
            if uuid:
                uuid_str = obs.obs_source_get_uuid_str(uuid)
                return uuid_str
        
        # Fallback to using source name with a unique identifier
        # This provides compatibility while still allowing unique identification
        if source:
            source_name = obs.obs_source_get_name(source)
            source_id = obs.obs_source_get_id(source)
            if source_name and source_id:
                return f"{source_name}:{source_id}"
            elif source_name:
                return source_name
    
    except Exception as e:
        log_error(f"Error getting source UUID: {e}")
    
    return ""

# Helper function to find a source by UUID
def find_source_by_uuid(uuid_str):
    """Find a source by its UUID or name:id string"""
    if not uuid_str:
        return None
    
    # Check if this looks like our fallback format (name:id)
    is_fallback_format = ":" in uuid_str and not uuid_str.startswith(":")
    
    sources = obs.obs_enum_sources()
    found_source = None
    
    if sources:
        for source in sources:
            if is_fallback_format:
                # If using fallback format, check source_name:source_id
                source_name = obs.obs_source_get_name(source)
                source_id = obs.obs_source_get_id(source)
                if source_name and source_id:
                    current_id = f"{source_name}:{source_id}"
                    if current_id == uuid_str:
                        found_source = source
                        # Don't release this specific source - caller is responsible
                        break
            else:
                # Try using real UUID if available
                try:
                    if hasattr(obs, "obs_source_get_uuid") and hasattr(obs, "obs_source_get_uuid_str"):
                        source_uuid = obs.obs_source_get_uuid(source)
                        if source_uuid:
                            current_uuid = obs.obs_source_get_uuid_str(source_uuid)
                            if current_uuid == uuid_str:
                                found_source = source
                                # Don't release this specific source - caller is responsible
                                break
                except Exception:
                    pass
                
                # Also check source name as a fallback
                source_name = obs.obs_source_get_name(source)
                if source_name == uuid_str:
                    found_source = source
                    # Don't release this specific source - caller is responsible
                    break
        
        # Release all sources except the one we found
        for source in sources:
            if source != found_source:
                obs.obs_source_release(source)
    
    return found_source

# Callback function for when the Target Scene is changed
def on_target_scene_changed(props, prop, settings_obj):
    """Callback when the target scene is changed - updates source lists"""
    try:
        # Determine which configuration we're working with based on the property name
        prop_name = obs.obs_property_name(prop)
        config_num = 1
        config_prefix = "config1_"
        
        if "config2_" in prop_name:
            config_num = 2
            config_prefix = "config2_"
        
        # Get the appropriate config dictionary
        current_config = config1 if config_num == 1 else config2
        
        # Get the scene value - using the correct property ID with prefix
        scene_value = obs.obs_data_get_string(settings_obj, f"{config_prefix}target_scene")
        
        # Parse the scene name and UUID
        if ":" in scene_value:
            scene_name, scene_uuid = scene_value.split(":", 1)
        else:
            scene_name = scene_value
            scene_uuid = ""
        
        # Update config settings
        current_config["target_scene_name"] = scene_name
        current_config["target_scene_uuid"] = scene_uuid
        
        # Get the source lists to update - use the correct property IDs with prefix
        target_source_list = obs.obs_properties_get(props, f"{config_prefix}source_name")
        viewport_list = obs.obs_properties_get(props, f"{config_prefix}viewport_color_source_name")
        
        # Clear current lists
        obs.obs_property_list_clear(target_source_list)
        obs.obs_property_list_clear(viewport_list)
        
        # Add a blank option at the top of the target source list
        obs.obs_property_list_add_string(target_source_list, "Select Source", "")
        
        # For viewport source list
        if scene_name:
            # Add 'Use Scene Dimensions' option for viewport list
            obs.obs_property_list_add_string(viewport_list, "Use Scene Dimensions", USE_SCENE_DIMENSIONS)
            
            # Pre-select "Use Scene Dimensions" as the active option
            current_viewport = obs.obs_data_get_string(settings_obj, f"{config_prefix}viewport_color_source_name")
            if not current_viewport or is_use_scene_dimensions(current_viewport):
                obs.obs_data_set_string(settings_obj, f"{config_prefix}viewport_color_source_name", USE_SCENE_DIMENSIONS)
            
            # No need for a blank "Select Source" option when "Use Scene Dimensions" is available
        else:
            # Add blank option only if no scene is selected
            obs.obs_property_list_add_string(viewport_list, "Select Source", "")
        
        # If a scene is selected, populate the dropdowns with its sources
        if scene_name:
            # Find the scene
            scene_source = None
            if scene_uuid:
                scene_source = find_source_by_uuid(scene_uuid)
            
            if not scene_source and scene_name:
                # Fallback to finding by name if UUID doesn't work
                scene_source = obs.obs_get_source_by_name(scene_name)
            
            if scene_source:
                # Get scene object
                scene = obs.obs_scene_from_source(scene_source)
                if scene:
                    # Enumerate all items in the scene
                    items = obs.obs_scene_enum_items(scene)
                    if items:
                        for item in items:
                            if not item:
                                continue
                                
                            source = obs.obs_sceneitem_get_source(item)
                            if not source:
                                continue
                                
                            source_name = obs.obs_source_get_name(source)
                            source_uuid = get_source_uuid(source)
                            
                            # Create a composite value with name and UUID
                            composite_value = f"{source_name}:{source_uuid}"
                            
                            # Add to both lists
                            obs.obs_property_list_add_string(target_source_list, source_name, composite_value)
                            obs.obs_property_list_add_string(viewport_list, source_name, composite_value)
                            
                        obs.sceneitem_list_release(items)
                
                # Release the scene source
                obs.obs_source_release(scene_source)
            
            # Make the source lists visible
            obs.obs_property_set_visible(target_source_list, True)
            obs.obs_property_set_visible(viewport_list, True)
            
        else:
            # Hide the source lists if no scene is selected
            obs.obs_property_set_visible(target_source_list, False)
            obs.obs_property_set_visible(viewport_list, False)
        
        # Return true to trigger a refresh of the properties
        return True
    except Exception as e:
        log_error(f"Error in scene change callback for config {config_num}: {e}")
        return False

# Callback for when target source is changed
def on_target_source_changed(props, prop, settings_obj):
    """Callback when the target source is changed"""
    try:
        # Determine which configuration we're working with based on the property name
        prop_name = obs.obs_property_name(prop)
        config_num = 1
        config_prefix = "config1_"
        
        if "config2_" in prop_name:
            config_num = 2
            config_prefix = "config2_"
        
        # Get the appropriate config dictionary
        current_config = config1 if config_num == 1 else config2
        
        source_value = obs.obs_data_get_string(settings_obj, f"{config_prefix}source_name")
        
        # Parse the source name and UUID
        if ":" in source_value:
            source_name, source_uuid = source_value.split(":", 1)
        else:
            source_name = source_value
            source_uuid = ""
        
        # Update config settings
        current_config["source_name"] = source_name
        current_config["source_uuid"] = source_uuid
        
        return True
    except Exception as e:
        log_error(f"Error in target source change callback for config {config_num}: {e}")
        return False

# Callback for when viewport source is changed
def on_viewport_source_changed(props, prop, settings_obj):
    """Callback when the viewport source is changed"""
    try:
        # Determine which configuration we're working with based on the property name
        prop_name = obs.obs_property_name(prop)
        config_num = 1
        config_prefix = "config1_"
        
        if "config2_" in prop_name:
            config_num = 2
            config_prefix = "config2_"
        
        # Get the appropriate config dictionary
        current_config = config1 if config_num == 1 else config2
        
        # Get the appropriate source settings
        src_settings = source_settings1 if config_num == 1 else source_settings2
        
        source_value = obs.obs_data_get_string(settings_obj, f"{config_prefix}viewport_color_source_name")
        
        # Check if special "Use Scene Dimensions" option is selected using the helper
        if is_use_scene_dimensions(source_value):
            current_config["viewport_color_source_name"] = USE_SCENE_DIMENSIONS
            current_config["viewport_color_source_uuid"] = ""
            log(f"Config {config_num}: Using scene dimensions for viewport")
            
            # When switching to scene dimensions, clear any previous viewport dimensions
            src_settings["viewport_width"] = 0
            src_settings["viewport_height"] = 0
            src_settings["viewport_scene_center_x"] = 0
            src_settings["viewport_scene_center_y"] = 0
            
            # For scene dimensions, alignment is always considered correct (not applicable)
            current_config["viewport_alignment_correct"] = True
            
            # Update the alignment status indicator in UI
            alignment_text_prop = obs.obs_properties_get(props, f"{config_prefix}alignment_status")
            if alignment_text_prop:
                alignment_style = "color: green; font-weight: bold;"
                alignment_text = "✓ Viewport alignment correct (Top Left)"
                obs.obs_property_set_description(
                    alignment_text_prop,
                    f"<span style='{alignment_style}'>{alignment_text}</span>"
                )
            
            return True
        
        # Parse the source name and UUID
        if ":" in source_value:
            source_name, source_uuid = source_value.split(":", 1)
        else:
            source_name = source_value
            source_uuid = ""
        
        # Update config settings
        current_config["viewport_color_source_name"] = source_name
        current_config["viewport_color_source_uuid"] = source_uuid
        
        # Check the viewport alignment immediately when source is selected
        viewport_scene_item = None
        viewport_found = False
        
        # Try to find source by UUID first if available
        if source_uuid:
            viewport_source = find_source_by_uuid(source_uuid)
            if viewport_source:
                # Now look for this in scenes
                scenes = obs.obs_frontend_get_scenes()
                if scenes:
                    for scene in scenes:
                        viewport_scene_item = find_scene_item(scene, source_name)
                        if viewport_scene_item:
                            viewport_found = True
                            # Check alignment and store result
                            current_config["viewport_alignment_correct"] = check_viewport_alignment(
                                viewport_scene_item, source_name, config_num
                            )
                            obs.obs_sceneitem_release(viewport_scene_item)
                            break
                    obs.source_list_release(scenes)
                obs.obs_source_release(viewport_source)
        
        # If not found by UUID, try by name
        if not viewport_found and source_name:
            scenes = obs.obs_frontend_get_scenes()
            if scenes:
                for scene in scenes:
                    viewport_scene_item = find_scene_item(scene, source_name)
                    if viewport_scene_item:
                        # Check alignment and store result
                        current_config["viewport_alignment_correct"] = check_viewport_alignment(
                            viewport_scene_item, source_name, config_num
                        )
                        obs.obs_sceneitem_release(viewport_scene_item)
                        break
                obs.source_list_release(scenes)
        
        # Update the alignment status indicator in UI
        alignment_text_prop = obs.obs_properties_get(props, f"{config_prefix}alignment_status")
        if alignment_text_prop:
            alignment_status = current_config.get("viewport_alignment_correct", True)
            alignment_text = "✓ Viewport alignment correct (Top Left)" if alignment_status else "⚠ VIEWPORT ALIGNMENT INCORRECT! Set to Top Left in Edit Transform"
            alignment_style = "color: green; font-weight: bold;" if alignment_status else "color: red; font-weight: bold; background-color: #fff3cd; padding: 3px;"
            
            obs.obs_property_set_description(
                alignment_text_prop,
                f"<span style='{alignment_style}'>{alignment_text}</span>"
            )
        
        return True
    except Exception as e:
        log_error(f"Error in viewport source change callback for config {config_num}: {e}")
        return False

# Helper function to get scene dimensions
def get_scene_dimensions(scene_source):
    """Get the dimensions of a scene"""
    try:
        if not scene_source:
            return 0, 0
            
        # Get base width and height from scene source
        base_width = obs.obs_source_get_width(scene_source)
        base_height = obs.obs_source_get_height(scene_source)
        
        # If the dimensions are valid, return them
        if base_width > 0 and base_height > 0:
            return base_width, base_height
            
        # If dimensions are zero, try to get them from scene items bounds
        scene = obs.obs_scene_from_source(scene_source)
        if not scene:
            return 0, 0
            
        # Try to calculate bounds from all scene items
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')
        
        items = obs.obs_scene_enum_items(scene)
        has_items = False
        
        if items:
            for item in items:
                if not item:
                    continue
                
                has_items = True
                
                # Get item transform
                pos = obs.vec2()
                scale = obs.vec2()
                
                obs.obs_sceneitem_get_pos(item, pos)
                obs.obs_sceneitem_get_scale(item, scale)
                
                # Get source dimensions
                source = obs.obs_sceneitem_get_source(item)
                if source:
                    source_width = obs.obs_source_get_width(source)
                    source_height = obs.obs_source_get_height(source)
                    
                    # Calculate bounds
                    item_left = pos.x - (source_width * scale.x / 2)
                    item_top = pos.y - (source_height * scale.y / 2)
                    item_right = pos.x + (source_width * scale.x / 2)
                    item_bottom = pos.y + (source_height * scale.y / 2)
                    
                    # Update min/max
                    min_x = min(min_x, item_left)
                    min_y = min(min_y, item_top)
                    max_x = max(max_x, item_right)
                    max_y = max(max_y, item_bottom)
            
            # Release items
            obs.sceneitem_list_release(items)
            
        # If we found items, calculate scene dimensions from bounds
        if has_items and min_x != float('inf') and max_x != float('-inf'):
            width = max_x - min_x
            height = max_y - min_y
            return width, height
        
        # If all else fails, try to get the base canvas resolution
        canvas_width = 1920  # Default width
        canvas_height = 1080  # Default height
        
        # Try to get canvas resolution using OBS API
        try:
            video_info = obs.obs_video_info()
            if obs.obs_get_video_info(video_info):
                canvas_width = video_info.base_width
                canvas_height = video_info.base_height
        except Exception as e:
            log_error(f"Error getting canvas resolution: {e}")
            
        return canvas_width, canvas_height
            
    except Exception as e:
        log_error(f"Error getting scene dimensions: {e}")
        return 1920, 1080  # Return default dimensions on error

# Helper function to refresh scenes and sources programmatically
def refresh_scenes_and_sources():
    """Refresh scenes and sources programmatically without UI interaction"""
    try:
        # Get scenes
        scenes = obs.obs_frontend_get_scenes()
        if not scenes:
            return
            
        # Update scene lists
        selected_scene_name = settings.get("target_scene_name", "")
        selected_scene_uuid = settings.get("target_scene_uuid", "")
        
        # If we don't have a selected scene but OBS is running, try to get the current scene
        if not selected_scene_name:
            try:
                current_scene = obs.obs_frontend_get_current_scene()
                if current_scene:
                    current_scene_name = obs.obs_source_get_name(current_scene)
                    current_scene_uuid = get_source_uuid(current_scene)
                    obs.obs_source_release(current_scene)
                    
                    # Update settings with current scene
                    selected_scene_name = current_scene_name
                    selected_scene_uuid = current_scene_uuid
                    settings["target_scene_name"] = selected_scene_name
                    settings["target_scene_uuid"] = selected_scene_uuid
                    
                    # Debug logging removed
            except Exception as e:
                log_error(f"Error getting current scene: {e}")
        
        # If a target scene is set, refresh sources for that scene
        if selected_scene_name:
            scene_source = None
            if selected_scene_uuid:
                scene_source = find_source_by_uuid(selected_scene_uuid)
            
            if not scene_source:
                scene_source = obs.obs_get_source_by_name(selected_scene_name)
                
            if scene_source:
                # Update sources for this scene
                scene = obs.obs_scene_from_source(scene_source)
                if scene:
                    # Cache sources to repopulate after settings load
                    source_cache = []
                    viewport_cache = []
                    
                    # Add the "Use Scene Dimensions" option as the first item
                    viewport_cache.append({"name": "Use Scene Dimensions", "value": USE_SCENE_DIMENSIONS})
                    
                    # Enumerate items in the scene
                    items = obs.obs_scene_enum_items(scene)
                    if items:
                        for item in items:
                            if not item:
                                continue
                                
                            source = obs.obs_sceneitem_get_source(item)
                            if not source:
                                continue
                                
                            source_name = obs.obs_source_get_name(source)
                            source_uuid = get_source_uuid(source)
                            
                            # Create a composite value with name and UUID
                            composite_value = f"{source_name}:{source_uuid}"
                            
                            # Add to both caches
                            source_cache.append({"name": source_name, "value": composite_value})
                            viewport_cache.append({"name": source_name, "value": composite_value})
                            
                        obs.sceneitem_list_release(items)
                    
                    # Store these caches in global settings for later use in UI
                    settings["source_cache"] = source_cache
                    settings["viewport_cache"] = viewport_cache
                    
                    # Debug logging removed
                
                # Release the scene source
                obs.obs_source_release(scene_source)
        
        # Release scenes
        obs.source_list_release(scenes)
        log("Refreshed scenes and sources programmatically")
        
    except Exception as e:
        log_error(f"Error refreshing scenes and sources: {e}")

# Get monitor information for a specific config
def get_monitor_info_for_config(config):
    """Get monitor information for a specific config"""
    monitor_id = config.get("monitor_id", 0)
    
    # Try to get from cache first
    if monitor_id in monitor_cache:
        return monitor_cache[monitor_id]
    
    # Get all monitors
    monitors = get_monitor_info()
    
    # Find the selected monitor
    for monitor in monitors:
        if monitor["id"] == monitor_id:
            # Cache it for future use
            monitor_cache[monitor_id] = {
                "screen_width": monitor["width"],
                "screen_height": monitor["height"],
                "screen_x_offset": monitor["x"],
                "screen_y_offset": monitor["y"]
            }
            return monitor_cache[monitor_id]
    
    # If monitor not found, use default
    log_warning(f"Monitor ID {monitor_id} not found, using default")
    return default_monitor_info.copy()

# Get mouse position adjusted for the monitor in a config
def get_adjusted_mouse_pos(config):
    """Get mouse position adjusted for the monitor in a config"""
    # Get global mouse position
    global_mouse = get_mouse_pos()
    
    # Get monitor info for this config
    monitor_info = get_monitor_info_for_config(config)
    
    # Calculate relative position
    relative_mouse_x = global_mouse["x"] - monitor_info["screen_x_offset"]
    relative_mouse_y = global_mouse["y"] - monitor_info["screen_y_offset"]
    
    # Calculate percentage position
    mouse_x_pct = relative_mouse_x / monitor_info["screen_width"]
    mouse_y_pct = relative_mouse_y / monitor_info["screen_height"]
    
    # Ensure mouse_pct is within 0-1
    mouse_x_pct = max(0.0, min(1.0, mouse_x_pct))
    mouse_y_pct = max(0.0, min(1.0, mouse_y_pct))
    
    # Check if inside monitor bounds for specific monitors
    is_inside_monitor = True
    if config["monitor_id"] != 0:  # Only check if not using "All Monitors"
        is_inside_monitor = (
            relative_mouse_x >= 0 and 
            relative_mouse_x < monitor_info["screen_width"] and
            relative_mouse_y >= 0 and 
            relative_mouse_y < monitor_info["screen_height"]
        )
    
    return {
        "x_pct": mouse_x_pct,
        "y_pct": mouse_y_pct,
        "is_inside_monitor": is_inside_monitor,
        "monitor_info": monitor_info
    }

# Main update function for a single config
def update_pan_and_zoom_for_config(config, src_settings, current_scene_item):
    """Update panning and zooming for a single configuration"""
    # Skip if this config is not enabled or panning is disabled
    if not config.get("enabled", False) or not config.get("pan_enabled", False):
        # If we were transitioning, stop the transition
        if src_settings["is_transitioning"]:
            src_settings["is_transitioning"] = False
        return
    
    # Check if we have viewport dimensions and a valid cached scene item
    if src_settings["viewport_width"] <= 0 or src_settings["viewport_height"] <= 0:
        return
        
    if current_scene_item is None:
        return
    
    # Use the cached scene item reference
    scene_item = current_scene_item
    
    # Get viewport's scene center (captured when panning was enabled)
    actual_viewport_center_x = src_settings.get("viewport_scene_center_x")
    actual_viewport_center_y = src_settings.get("viewport_scene_center_y")

    if actual_viewport_center_x is None or actual_viewport_center_y is None:
        # This should ideally not happen if toggle_panning ensures these are set
        log_error("Viewport center not captured. Please re-toggle panning.")
        return
    
    # --- Zoom transition handling ---
    current_zoom_level = 1.0  # Default to 1.0 when no zoom
    
    # Only apply zoom if zoom is enabled or we're in a zoom transition
    if config["zoom_enabled"] or src_settings["is_transitioning"]:
        current_zoom_level = config["zoom_level"]
        
        # Check if we're in a zoom transition
        if src_settings["is_transitioning"]:
            # Calculate how far we are in the transition
            elapsed_time = time.time() - src_settings["transition_start_time"]
            transition_duration = src_settings["transition_duration"]
            
            # Calculate progress (0.0 to 1.0)
            progress = min(1.0, elapsed_time / transition_duration)
            
            # Apply easing for a smooth transition
            eased_progress = ease_in_out_quad(progress)
            
            # Interpolate between start and target zoom
            start_zoom = src_settings["transition_start_zoom"]
            target_zoom = src_settings["transition_target_zoom"]
            current_zoom_level = start_zoom + (target_zoom - start_zoom) * eased_progress
            
            # Debug logging removed
            
            # Check if transition is complete
            if progress >= 1.0:
                src_settings["is_transitioning"] = False
                current_zoom_level = target_zoom  # Ensure we land exactly on target
    
    # --- Get mouse position and monitor bounds --- 
    mouse_data = get_adjusted_mouse_pos(config)
    
    # Skip if mouse is outside the selected monitor
    if not mouse_data["is_inside_monitor"]:
        return
    
    mouse_x_pct = mouse_data["x_pct"]
    mouse_y_pct = mouse_data["y_pct"]
    
    # --- Source information ---
    
    # Get dimensions
    S_w_native = src_settings["source_base_width"]   # Native width of full source
    S_h_native = src_settings["source_base_height"]  # Native height of full source

    # Get crop values
    crop_left = src_settings["crop_left"]
    crop_top = src_settings["crop_top"]
    crop_right = src_settings["crop_right"]
    crop_bottom = src_settings["crop_bottom"]

    # Calculate visible dimensions (after cropping)
    S_w_visible = S_w_native - crop_left - crop_right
    S_h_visible = S_h_native - crop_top - crop_bottom
    
    # Viewport dimensions
    V_w = src_settings["viewport_width"]
    V_h = src_settings["viewport_height"]
    
    # Scale factors
    base_scale_x = src_settings["initial_scale_x"] 
    base_scale_y = src_settings["initial_scale_y"]
    zoom_scale = current_zoom_level
    scale_x = base_scale_x * zoom_scale
    scale_y = base_scale_y * zoom_scale
    
    # === EXTREMELY SIMPLIFIED DIRECT APPROACH ===
    
    # Default position (if no panning)
    new_pos_x = 0.0 
    new_pos_y = 0.0

    if config["pan_enabled"]:
        # STEP 1: Simple center-based calculation (without crop)
        # First calculate the precise source point that should be at viewport center
        
        # STEP 1: Account for crop in mouse coordinate mapping
        # When a source is cropped, we need to adjust how mouse coordinates map to the source
        
        # STEP 1: Map mouse position to the uncropped source coordinates
        # First, we need to map the mouse percentage to the full source dimensions
        # This gives us the position in the original, uncropped source
        full_source_x = mouse_x_pct * S_w_native
        full_source_y = mouse_y_pct * S_h_native
        
        # STEP 2: Adjust for cropping
        # We need to account for the crop by adjusting the coordinates
        # The crop effectively shifts the visible area within the source
        # We need to adjust our coordinates to account for this shift
        
        # Calculate the center of the visible (cropped) area in the original source coordinates
        visible_center_x_in_source = crop_left + (S_w_visible / 2)
        visible_center_y_in_source = crop_top + (S_h_visible / 2)
        
        # Calculate the offset from the center of the visible area
        # This is how far the mouse is from the center of the visible area
        offset_from_visible_center_x = full_source_x - visible_center_x_in_source
        offset_from_visible_center_y = full_source_y - visible_center_y_in_source
        
        # Scale the offset for scene coordinates
        scene_offset_x = offset_from_visible_center_x * scale_x
        scene_offset_y = offset_from_visible_center_y * scale_y
        
        # Calculate the position that would place this point at viewport center
        adjusted_pos_x = actual_viewport_center_x - scene_offset_x
        adjusted_pos_y = actual_viewport_center_y - scene_offset_y
        
        # Apply user-defined pixel offsets (not affected by zoom)
        adjusted_pos_x += config.get("offset_x", 0)
        adjusted_pos_y += config.get("offset_y", 0)
        
        # STEP 3: Calculate visible bounds for clamping
        # Calculate scaled visible dimensions
        visible_width_scene = S_w_visible * scale_x
        visible_height_scene = S_h_visible * scale_y
        
        # Calculate visible area bounds
        visible_center_x = adjusted_pos_x
        visible_center_y = adjusted_pos_y
        
        # Calculate visible area edges
        visible_left = visible_center_x - (visible_width_scene / 2)
        visible_right = visible_left + visible_width_scene
        visible_top = visible_center_y - (visible_height_scene / 2)
        visible_bottom = visible_top + visible_height_scene
        
        # Calculate viewport edges
        viewport_left = actual_viewport_center_x - (V_w / 2)
        viewport_right = actual_viewport_center_x + (V_w / 2)
        viewport_top = actual_viewport_center_y - (V_h / 2)
        viewport_bottom = actual_viewport_center_y + (V_h / 2)
        
        # STEP 4: Apply clamping
        # Only apply if visible area is larger than viewport
        if visible_width_scene > V_w:
            # Horizontal clamping
            if visible_left > viewport_left:
                # Left edge is inside viewport (too far right)
                adjust = visible_left - viewport_left
                adjusted_pos_x -= adjust
            elif visible_right < viewport_right:
                # Right edge is inside viewport (too far left)
                adjust = viewport_right - visible_right
                adjusted_pos_x += adjust
        else:
            # Center horizontally
            center_adjust_x = ((viewport_left + viewport_right) / 2) - ((visible_left + visible_right) / 2)
            adjusted_pos_x += center_adjust_x
        
        if visible_height_scene > V_h:
            # Vertical clamping
            if visible_top > viewport_top:
                # Top edge is inside viewport (too far down)
                adjust = visible_top - viewport_top
                adjusted_pos_y -= adjust
            elif visible_bottom < viewport_bottom:
                # Bottom edge is inside viewport (too far up)
                adjust = viewport_bottom - visible_bottom
                adjusted_pos_y += adjust
        else:
            # Center vertically
            center_adjust_y = ((viewport_top + viewport_bottom) / 2) - ((visible_top + visible_bottom) / 2)
            adjusted_pos_y += center_adjust_y
        
        # Apply final position
        new_pos_x = adjusted_pos_x
        new_pos_y = adjusted_pos_y
        
    
    else: # Panning not enabled
        if src_settings["is_initial_state_captured"]:
            new_pos_x = src_settings["initial_pos_x"]
            new_pos_y = src_settings["initial_pos_y"]
        else: 
            pass # new_pos_x/y are already 0.0
            
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
            source = config.get("direct_source_cache")
            if source:
                # For direct source manipulation, try multiple approaches to find what works
                success = False
                
                # First try: Use the cached property names if available
                x_prop = config["direct_property_names"]["x"]
                y_prop = config["direct_property_names"]["y"]
                
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
                        if config["zoom_enabled"]:
                            transform.scale.x = scale_x
                            transform.scale.y = scale_y
                        obs.obs_source_set_transform_info(source, transform)
                        success = True
                    except Exception as e:
                        pass
                
                # If still failed, try manually creating and setting new settings
                if not success:
                    pass
                    try:
                        # Try creating brand new settings and applying common property names
                        settings_obj = obs.obs_data_create()
                        
                        # Try all common property names for position
                        for x_name in ["x", "position_x", "positionX"]:
                            obs.obs_data_set_double(settings_obj, x_name, new_pos_x)
                            
                        for y_name in ["y", "position_y", "positionY"]:
                            obs.obs_data_set_double(settings_obj, y_name, new_pos_y)
                        
                        # Try common property names for scale if zooming is enabled
                        if config["zoom_enabled"]:
                            for scale_x_name in ["scale_x", "scaleX", "width_scale"]:
                                obs.obs_data_set_double(settings_obj, scale_x_name, scale_x)
                                
                            for scale_y_name in ["scale_y", "scaleY", "height_scale"]:
                                obs.obs_data_set_double(settings_obj, scale_y_name, scale_y)
                            
                        # Update the source
                        obs.obs_source_update(source, settings_obj)
                        obs.obs_data_release(settings_obj)
                        
                        # Check if we should update our property names for next time
                        if not config["direct_property_names"]["x"] or not config["direct_property_names"]["y"]:
                            discover_direct_properties(source, config)
                    except Exception as e:
                        log_error(f"Error with fallback property setting: {e}")
                
                # Update the dictionary with new values
                scene_item["pos_x"] = new_pos_x
                scene_item["pos_y"] = new_pos_y
                if config["zoom_enabled"] or src_settings["is_transitioning"]:
                    scene_item["scale_x"] = scale_x
                    scene_item["scale_y"] = scale_y
        else:
            # For normal OBS scene items
            # Set position if we've calculated a new position
            current_pos = obs.vec2()
            current_pos.x = new_pos_x
            current_pos.y = new_pos_y
            obs.obs_sceneitem_set_pos(scene_item, current_pos)
            
            # Set scale if zooming is enabled
            if config["zoom_enabled"] or src_settings["is_transitioning"]:
                current_scale = obs.vec2()
                current_scale.x = scale_x
                current_scale.y = scale_y
                obs.obs_sceneitem_set_scale(scene_item, current_scale)
    except Exception as e:
        log_error(f"Error applying new position/scale: {e}")
    
    # Debug logging removed

# Toggle panning on/off for config 1
def toggle_panning1(pressed):
    """Toggle panning on or off for config 1"""
    toggle_panning_for_config(pressed, config1, source_settings1, g_current_scene_item1, 1)

# Toggle panning on/off for config 2
def toggle_panning2(pressed):
    """Toggle panning on or off for config 2"""
    toggle_panning_for_config(pressed, config2, source_settings2, g_current_scene_item2, 2)

# Toggle zooming on/off for config 1
def toggle_zooming1(pressed):
    """Toggle zooming on or off for config 1"""
    toggle_zooming_for_config(pressed, config1, source_settings1, g_current_scene_item1, 1)

# Toggle zooming on/off for config 2
def toggle_zooming2(pressed):
    """Toggle zooming on or off for config 2"""
    toggle_zooming_for_config(pressed, config2, source_settings2, g_current_scene_item2, 2)

# Helper function to check viewport alignment (Top Left)
def check_viewport_alignment(viewport_scene_item, source_name, config_num):
    """Check if viewport source has correct Top Left (0x0005) alignment"""
    if not viewport_scene_item:
        return False
        
    try:
        # Get alignment of the viewport scene item
        alignment = obs.obs_sceneitem_get_alignment(viewport_scene_item)
        
        # Define alignment constants
        OBS_ALIGN_LEFT = 0x0001
        OBS_ALIGN_TOP = 0x0004
        expected_alignment = OBS_ALIGN_LEFT | OBS_ALIGN_TOP  # Top Left = 0x0005
        
        # Check if alignment matches expected Top Left (0x0005)
        is_correct = (alignment == expected_alignment)
        
        if not is_correct:
            # Display a prominent warning message
            log_error(f"▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓")
            log_error(f"▓ VIEWPORT ALIGNMENT ERROR - Config {config_num}")
            log_error(f"▓ Viewport source '{source_name}' alignment incorrect!")
            log_error(f"▓ Current alignment: 0x{alignment:x}, Expected: 0x0005")
            log_error(f"▓ Please set Positional Alignment to TOP LEFT")
            log_error(f"▓ (Edit Transform > Positional Alignment > Top Left")
            log_error(f"▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓")
        
        return is_correct
    except Exception as e:
        log_error(f"Error checking viewport alignment: {e}")
        return False

# Generic toggle_panning function that works with any config
def toggle_panning_for_config(pressed, config, src_settings, current_scene_item, config_num):
    """Toggle panning on or off for a specific config"""
    global g_current_scene_item1, g_current_scene_item2, script_settings
    
    # Immediate bail if not pressed
    if not pressed:
        return
    
    # Ensure we have valid settings
    if script_settings is None:
        log_error(f"Toggle panning failed: No valid settings available")
        return
        
    # Refresh all critical settings from the UI
    # This ensures we're always using the latest values
    
    # Check if this config is enabled
    config_enabled = obs.obs_data_get_bool(script_settings, f"config{config_num}_enabled")
    config["enabled"] = config_enabled  # Update in-memory config
    
    if not config_enabled:
        log(f"Cannot toggle: Config {config_num} is disabled")
        return
        
    # Refresh scene, source and viewport settings
    scene_value = obs.obs_data_get_string(script_settings, f"config{config_num}_target_scene")
    source_value = obs.obs_data_get_string(script_settings, f"config{config_num}_source_name")
    viewport_value = obs.obs_data_get_string(script_settings, f"config{config_num}_viewport_color_source_name")
    
    # Update scene info
    if ":" in scene_value:
        scene_name, scene_uuid = scene_value.split(":", 1)
        config["target_scene_name"] = scene_name
        config["target_scene_uuid"] = scene_uuid
    else:
        config["target_scene_name"] = scene_value
        config["target_scene_uuid"] = ""
        
    # Update source info
    if ":" in source_value:
        source_name, source_uuid = source_value.split(":", 1)
        config["source_name"] = source_name
        config["source_uuid"] = source_uuid
    else:
        config["source_name"] = source_value
        config["source_uuid"] = ""
        
    # Update viewport info
    if is_use_scene_dimensions(viewport_value):
        config["viewport_color_source_name"] = USE_SCENE_DIMENSIONS
        config["viewport_color_source_uuid"] = ""
    elif ":" in viewport_value:
        viewport_name, viewport_uuid = viewport_value.split(":", 1)
        config["viewport_color_source_name"] = viewport_name
        config["viewport_color_source_uuid"] = viewport_uuid
    else:
        config["viewport_color_source_name"] = viewport_value
        config["viewport_color_source_uuid"] = ""
        
    # Update zoom settings
    zoom_level = obs.obs_data_get_double(script_settings, f"config{config_num}_zoom_level")
    config["zoom_level"] = max(1.0, min(5.0, zoom_level))
    
    # Update transition durations
    zoom_in_duration = obs.obs_data_get_double(script_settings, f"config{config_num}_zoom_in_duration")
    config["zoom_in_duration"] = max(0.0, min(1.0, zoom_in_duration))
    
    zoom_out_duration = obs.obs_data_get_double(script_settings, f"config{config_num}_zoom_out_duration")
    config["zoom_out_duration"] = max(0.0, min(1.0, zoom_out_duration))
    
    # Update offset values
    config["offset_x"] = obs.obs_data_get_int(script_settings, f"config{config_num}_offset_x")
    config["offset_y"] = obs.obs_data_get_int(script_settings, f"config{config_num}_offset_y")
    
    # Monitor settings
    monitor_id_string = obs.obs_data_get_string(script_settings, f"config{config_num}_monitor_id_string")
    if monitor_id_string:
        try:
            monitor_id = int(monitor_id_string.split(":")[0])
            config["monitor_id"] = monitor_id
        except Exception:
            # Keep current value if parsing fails
            pass
    
    # === ADD DETAILED LOGGING FOR CONFIG 2 ===
    if config_num == 2:
        log(f"[CONFIG 2 HOTKEY DEBUG] Refreshed settings for Config 2:")
        log(f"    Target Scene: '{config.get('target_scene_name', 'Not Set')}' (UUID: '{config.get('target_scene_uuid', 'Not Set')}')")
        log(f"    Target Source: '{config.get('source_name', 'Not Set')}' (UUID: '{config.get('source_uuid', 'Not Set')}')")
        log(f"    Viewport Source: '{config.get('viewport_color_source_name', 'Not Set')}' (UUID: '{config.get('viewport_color_source_uuid', 'Not Set')}')")
        log(f"    Zoom Level: {config.get('zoom_level', 'Not Set')}")
        log(f"    Monitor ID: {config.get('monitor_id', 'Not Set')}")
    # === END DETAILED LOGGING ===

    # Toggle state
    config["pan_enabled"] = not config["pan_enabled"]
    
    if config["pan_enabled"]:
        # Always clear cached values first to ensure fresh capture
        src_settings["viewport_width"] = 0
        src_settings["viewport_height"] = 0
        src_settings["viewport_scene_center_x"] = 0
        src_settings["viewport_scene_center_y"] = 0
        src_settings["is_initial_state_captured"] = False
        src_settings["crop_left"] = 0 # Reset crop
        src_settings["crop_top"] = 0
        src_settings["crop_right"] = 0
        src_settings["crop_bottom"] = 0
        
        # Enable panning - verify we have required sources first
        target_source_name = config["source_name"]
        target_source_uuid = config["source_uuid"]
        viewport_source_name = config["viewport_color_source_name"]
        viewport_source_uuid = config["viewport_color_source_uuid"]
        
        # First check: should we be using scene dimensions?
        is_using_scene_dims = is_use_scene_dimensions(viewport_source_name)
        
        # Second check: empty viewport but we have a scene - use scene dimensions as fallback
        if not viewport_source_name and config["target_scene_name"]:
            log_warning(f"Config {config_num}: No viewport source selected, but scene exists - using scene dimensions as fallback")
            is_using_scene_dims = True
            # Update settings to reflect this change
            config["viewport_color_source_name"] = USE_SCENE_DIMENSIONS
            
        # Basic Checks
        if not target_source_name:
            log_error(f"Config {config_num}: Cannot enable panning: No Target Source selected.")
            config["pan_enabled"] = False
            return
        
        # Check for viewport source - empty is valid if we're using scene dimensions
        if not viewport_source_name and not is_using_scene_dims:
            log_error(f"Config {config_num}: Cannot enable panning: No Viewport Source selected. viewport_source_name='{viewport_source_name}', is_using_scene_dims={is_using_scene_dims}")
            config["pan_enabled"] = False
            return
            
        # Special handling for "Use Scene Dimensions" option
        if is_using_scene_dims:
            log(f"Config {config_num}: Using scene dimensions for viewport")
            
            # Get target scene
            scene_source = None
            if config["target_scene_uuid"]:
                scene_source = find_source_by_uuid(config["target_scene_uuid"])
            
            if not scene_source:
                scene_source = obs.obs_get_source_by_name(config["target_scene_name"])
            
            if not scene_source:
                log_error(f"Config {config_num}: Cannot enable panning: Target Scene '{config['target_scene_name']}' not found.")
                config["pan_enabled"] = False
                return
                
            # Get scene dimensions
            scene_width, scene_height = get_scene_dimensions(scene_source)
            
            if scene_width <= 0 or scene_height <= 0:
                log_error(f"Config {config_num}: Cannot enable panning: Could not determine scene dimensions.")
                obs.obs_source_release(scene_source)
                config["pan_enabled"] = False
                return
                
            # Get scene center position (0, 0) is top-left
            scene_center_x = scene_width / 2
            scene_center_y = scene_height / 2
            
            log(f"Config {config_num} using scene dimensions: {scene_width}x{scene_height}, Center: ({scene_center_x},{scene_center_y})")
            
            # Store viewport dimensions
            src_settings["viewport_width"] = scene_width
            src_settings["viewport_height"] = scene_height
            src_settings["viewport_scene_center_x"] = scene_center_x
            src_settings["viewport_scene_center_y"] = scene_center_y
            
            # Release scene source
            obs.obs_source_release(scene_source)
        else:
            # Regular viewport source handling
            log(f"Config {config_num}: Capturing viewport dimensions for: {viewport_source_name}")
            
            # Find the viewport source in any scene to get its bounds
            viewport_scene_item = None
            viewport_found_in_scene = False
            
            # Try to find viewport source by UUID first if available
            if viewport_source_uuid:
                viewport_source = find_source_by_uuid(viewport_source_uuid)
                if viewport_source:
                    log(f"Config {config_num}: Found viewport source '{viewport_source_name}' by UUID")
                    
                    # Now look for this source's scene item in the target scene
                    if config["target_scene_name"]:
                        scene_source = None
                        if config["target_scene_uuid"]:
                            scene_source = find_source_by_uuid(config["target_scene_uuid"])
                        if not scene_source:
                            scene_source = obs.obs_get_source_by_name(config["target_scene_name"])
                            
                        if scene_source:
                            scene = obs.obs_scene_from_source(scene_source)
                            if scene:
                                # Enumerate items to find the one with matching source
                                items = obs.obs_scene_enum_items(scene)
                                if items:
                                    for item in items:
                                        if not item:
                                            continue
                                            
                                        item_source = obs.obs_sceneitem_get_source(item)
                                        if not item_source:
                                            continue
                                            
                                        item_uuid = get_source_uuid(item_source)
                                        if item_uuid == viewport_source_uuid:
                                            viewport_scene_item = item
                                            viewport_found_in_scene = True
                                            # Don't release this specific item
                                            items[items.index(item)] = None
                                            break
                                            
                                    obs.sceneitem_list_release(items)
                            
                            obs.obs_source_release(scene_source)
                    
                    obs.obs_source_release(viewport_source)
            
            # If not found by UUID, try traditional methods
            if not viewport_found_in_scene:
                # Check current scene first
                current_scene = obs.obs_frontend_get_current_scene()
                if current_scene:
                    scene_obj = obs.obs_scene_from_source(current_scene)
                    if scene_obj:
                        viewport_scene_item = find_scene_item(current_scene, viewport_source_name)
                        if viewport_scene_item:
                            viewport_found_in_scene = True
                    obs.obs_source_release(current_scene)
                
                # If not found in current scene, search target scene
                if not viewport_found_in_scene and config["target_scene_name"]:
                    scene_source = obs.obs_get_source_by_name(config["target_scene_name"])
                    if scene_source:
                        scene_obj = obs.obs_scene_from_source(scene_source)
                        if scene_obj:
                            viewport_scene_item = find_scene_item(scene_source, viewport_source_name)
                            if viewport_scene_item:
                                viewport_found_in_scene = True
                        obs.obs_source_release(scene_source)
                
                # If still not found, search all scenes
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
                # Check the viewport alignment and store the result in the config
                config["viewport_alignment_correct"] = check_viewport_alignment(viewport_scene_item, viewport_source_name, config_num)
                
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
                            log(f"Config {config_num}: Using bounds values: {viewport_width}x{viewport_height}")
                except Exception as e:
                    log_warning(f"Config {config_num}: Could not get precise bounds, using scaled dimensions: {e}")
                
                # Calculate viewport's center in the scene
                src_settings["viewport_scene_center_x"] = pos.x + (viewport_width / 2.0)
                src_settings["viewport_scene_center_y"] = pos.y + (viewport_height / 2.0)
                
                log(f"Config {config_num}: Found viewport source in scene with bounds: {viewport_width:.0f}x{viewport_height:.0f}, Pos: ({pos.x:.1f},{pos.y:.1f})")
                log(f"Config {config_num}: Viewport scene center calculated: ({src_settings['viewport_scene_center_x']:.1f},{src_settings['viewport_scene_center_y']:.1f})")
                
                # Store viewport dimensions
                src_settings["viewport_width"] = viewport_width
                src_settings["viewport_height"] = viewport_height
                
                # Release the viewport scene item
                if viewport_scene_item:
                    try:
                        obs.obs_sceneitem_release(viewport_scene_item)
                    except Exception as e:
                        log_error(f"Config {config_num}: Error releasing viewport scene item: {e}")
            else:
                log_error(f"Config {config_num}: Viewport source '{viewport_source_name}' not found as an item in any scene. Panning cannot be enabled.")
                log_error(f"Config {config_num}: Please add the viewport source to a scene and ensure it's spelled correctly.")
                config["pan_enabled"] = False # Crucial: Prevent enabling panning
                return
        
        # Now find and store the source item
        scene_item = get_source_scene_item(target_source_name, target_source_uuid, config)
        if not scene_item:
            log_error(f"Config {config_num}: Cannot enable panning: Target Source '{target_source_name}' not found in any scene.")
            config["pan_enabled"] = False
            return
        
        # IMPORTANT: Check and set alignment to CENTER
        if isinstance(scene_item, dict) and scene_item.get("is_direct_source"):
            # For direct sources, we may not be able to set alignment
            log_warning(f"Config {config_num}: Direct source mode does not support changing alignment. Please set Center alignment manually.")
        else:
            # For standard scene items, check and set alignment
            current_alignment = obs.obs_sceneitem_get_alignment(scene_item)
            
            # Define OBS alignment constants
            OBS_ALIGN_CENTER = 0  # This appears to be incorrect in our implementation
            
            # Try to get the constants from the obs module if available
            try:
                # These constants may be directly available in the obs module
                if hasattr(obs, "OBS_ALIGN_CENTER"):
                    OBS_ALIGN_CENTER = obs.OBS_ALIGN_CENTER
                else:
                    # If not directly available, these are the typical values
                    # OBS_ALIGN_LEFT = 0x0001
                    # OBS_ALIGN_RIGHT = 0x0002
                    # OBS_ALIGN_TOP = 0x0004
                    # OBS_ALIGN_BOTTOM = 0x0008
                    # OBS_ALIGN_CENTER = 0x0010
                    OBS_ALIGN_CENTER = 0x0010
                log(f"Config {config_num}: Using OBS_ALIGN_CENTER value: {OBS_ALIGN_CENTER}")
            except Exception as e:
                log_error(f"Config {config_num}: Error getting alignment constants: {e}, using default value 0x0010")
                OBS_ALIGN_CENTER = 0x0010  # Center alignment value
            
            # Check if alignment needs to be changed to CENTER
            if current_alignment != OBS_ALIGN_CENTER:
                log(f"Config {config_num}: Setting alignment to CENTER (was {current_alignment}, using value {OBS_ALIGN_CENTER})")
                obs.obs_sceneitem_set_alignment(scene_item, OBS_ALIGN_CENTER)
        
        # IMPORTANT: Make a copy of the scene item properties instead of storing a reference
        # This avoids keeping references to OBS objects that might cause crashes on exit
        if isinstance(scene_item, dict) and scene_item.get("is_direct_source"):
            # For direct sources, store a copy of the properties
            source = scene_item.get("source")
            if source:
                source_width = obs.obs_source_get_width(source)
                source_height = obs.obs_source_get_height(source)
                
                # Store source dimensions
                src_settings["source_base_width"] = source_width
                src_settings["source_base_height"] = source_height
                
                # Get current position and scale
                pos_x, pos_y, scale_x, scale_y = get_item_transform(scene_item)
                if pos_x is not None and scale_x is not None:
                    src_settings["initial_pos_x"] = pos_x
                    src_settings["initial_pos_y"] = pos_y
                    src_settings["initial_scale_x"] = scale_x
                    src_settings["initial_scale_y"] = scale_y
                    src_settings["is_initial_state_captured"] = True
                    log(f"Config {config_num}: Initial state captured: Pos=({pos_x:.1f},{pos_y:.1f}), Scale=({scale_x:.2f},{scale_y:.2f})")
                else:
                    src_settings["initial_pos_x"] = 0
                    src_settings["initial_pos_y"] = 0
                    src_settings["initial_scale_x"] = 1.0
                    src_settings["initial_scale_y"] = 1.0
                    src_settings["is_initial_state_captured"] = True
                    log_warning(f"Config {config_num}: Could not get initial transform values. Using defaults.")
                
                # For direct sources, crop is not applicable, so crop values remain 0
                log(f"Config {config_num}: Direct source mode, crop values will be 0.")
            else:
                src_settings["source_base_width"] = 1920  # Fallback
                src_settings["source_base_height"] = 1080  # Fallback
                src_settings["initial_pos_x"] = 0
                src_settings["initial_pos_y"] = 0
                src_settings["initial_scale_x"] = 1.0
                src_settings["initial_scale_y"] = 1.0
                src_settings["is_initial_state_captured"] = True
        else:
            # For standard scene items
            source = obs.obs_sceneitem_get_source(scene_item)
            if source:
                source_width = obs.obs_source_get_width(source)
                source_height = obs.obs_source_get_height(source)
                
                # Store source dimensions
                src_settings["source_base_width"] = source_width
                src_settings["source_base_height"] = source_height
                
                # Get current position and scale
                pos_x, pos_y, scale_x, scale_y = get_item_transform(scene_item)
                if pos_x is not None and scale_x is not None:
                    src_settings["initial_pos_x"] = pos_x
                    src_settings["initial_pos_y"] = pos_y
                    src_settings["initial_scale_x"] = scale_x
                    src_settings["initial_scale_y"] = scale_y
                    src_settings["is_initial_state_captured"] = True
                    log(f"Config {config_num}: Initial state captured: Pos=({pos_x:.1f},{pos_y:.1f}), Scale=({scale_x:.2f},{scale_y:.2f})")
                else:
                    src_settings["initial_pos_x"] = 0
                    src_settings["initial_pos_y"] = 0
                    src_settings["initial_scale_x"] = 1.0
                    src_settings["initial_scale_y"] = 1.0
                    src_settings["is_initial_state_captured"] = True
                    log_warning(f"Config {config_num}: Could not get initial transform values. Using defaults.")
                
                # Get crop values if it's a standard scene item
                crop = obs.obs_sceneitem_crop()
                obs.obs_sceneitem_get_crop(scene_item, crop)
                src_settings["crop_left"] = crop.left
                src_settings["crop_top"] = crop.top
                src_settings["crop_right"] = crop.right
                src_settings["crop_bottom"] = crop.bottom
                log(f"Config {config_num}: Captured crop: L{crop.left} T{crop.top} R{crop.right} B{crop.bottom}")
            else:
                src_settings["source_base_width"] = 1920  # Fallback
                src_settings["source_base_height"] = 1080  # Fallback
                src_settings["initial_pos_x"] = 0
                src_settings["initial_pos_y"] = 0
                src_settings["initial_scale_x"] = 1.0
                src_settings["initial_scale_y"] = 1.0
                src_settings["is_initial_state_captured"] = True
            
            # Store the scene item reference based on config number
            if config_num == 1:
                g_current_scene_item1 = scene_item
            else:
                g_current_scene_item2 = scene_item
        
        log(f"Config {config_num}: Panning ENABLED for: {target_source_name}")
    else:
        log(f"Config {config_num}: Disabling panning...")
        
        # Disable any ongoing zoom transition
        src_settings["is_transitioning"] = False
        config["zoom_enabled"] = False
        
        # Restore original position if we have the data and a valid scene item
        current_scene_item = g_current_scene_item1 if config_num == 1 else g_current_scene_item2
        if src_settings["is_initial_state_captured"] and current_scene_item:
            try:
                # Restore original position and scale
                set_item_transform(
                    current_scene_item,
                    src_settings["initial_pos_x"],
                    src_settings["initial_pos_y"],
                    src_settings["initial_scale_x"],
                    src_settings["initial_scale_y"]
                )
                log(f"Config {config_num}: Restored position and scale to initial values")
                
                # Ensure CENTER alignment is maintained when panning is turned off
                if not isinstance(current_scene_item, dict):  # If it's a standard scene item
                    # Define OBS alignment constants
                    OBS_ALIGN_CENTER = 0  # This appears to be incorrect in our implementation
                    
                    # Try to get the constants from the obs module if available
                    try:
                        # These constants may be directly available in the obs module
                        if hasattr(obs, "OBS_ALIGN_CENTER"):
                            OBS_ALIGN_CENTER = obs.OBS_ALIGN_CENTER
                        else:
                            # If not directly available, these are the typical values
                            OBS_ALIGN_CENTER = 0x0010
                        log(f"Config {config_num}: Using OBS_ALIGN_CENTER value: {OBS_ALIGN_CENTER}")
                    except Exception as e:
                        log_error(f"Config {config_num}: Error getting alignment constants: {e}, using default value 0x0010")
                        OBS_ALIGN_CENTER = 0x0010
                    
                    current_alignment = obs.obs_sceneitem_get_alignment(current_scene_item)
                    if current_alignment != OBS_ALIGN_CENTER:
                        log(f"Config {config_num}: Maintaining CENTER alignment (was {current_alignment}, using value {OBS_ALIGN_CENTER})")
                        obs.obs_sceneitem_set_alignment(current_scene_item, OBS_ALIGN_CENTER)
                    
                    # Center the source on screen (center to viewport)
                    if src_settings["viewport_width"] > 0 and src_settings["viewport_height"] > 0:
                        center_x = src_settings["viewport_scene_center_x"]
                        center_y = src_settings["viewport_scene_center_y"]
                        set_item_transform(current_scene_item, center_x, center_y)
                        log(f"Config {config_num}: Centered source on screen at ({center_x:.1f}, {center_y:.1f})")
            except Exception as e:
                log_error(f"Config {config_num}: Error restoring position: {e}")
        
        # Make local copies of references before clearing them
        scene_item_to_release = None
        if current_scene_item and not isinstance(current_scene_item, dict):
            scene_item_to_release = current_scene_item
        
        direct_source_to_release = config.get("direct_source_cache")
        
        # Clear all references BEFORE releasing them
        if config_num == 1:
            g_current_scene_item1 = None
        else:
            g_current_scene_item2 = None
            
        config["direct_source_cache"] = None
        config["direct_mode"] = False
        
        # Now release the resources from our local copies
        if scene_item_to_release:
            try:
                obs.obs_sceneitem_release(scene_item_to_release)
                log(f"Config {config_num}: Released scene item")
            except Exception as e:
                log_error(f"Config {config_num}: Error releasing scene item: {e}")
        
        if direct_source_to_release:
            try:
                obs.obs_source_release(direct_source_to_release)
                log(f"Config {config_num}: Released direct source")
            except Exception as e:
                log_error(f"Config {config_num}: Error releasing direct source: {e}")
        
        # Reset all state variables to defaults
        src_settings["viewport_width"] = 0
        src_settings["viewport_height"] = 0
        src_settings["viewport_scene_center_x"] = 0
        src_settings["viewport_scene_center_y"] = 0
        src_settings["source_base_width"] = 0
        src_settings["source_base_height"] = 0
        src_settings["initial_pos_x"] = 0
        src_settings["initial_pos_y"] = 0
        src_settings["initial_scale_x"] = 1.0
        src_settings["initial_scale_y"] = 1.0
        src_settings["is_initial_state_captured"] = False
        src_settings["crop_left"] = 0 # Reset crop
        src_settings["crop_top"] = 0
        src_settings["crop_right"] = 0
        src_settings["crop_bottom"] = 0
        
        # Force garbage collection
        try:
            import gc
            gc.collect()
        except Exception as e:
            log_error(f"Config {config_num}: Error during garbage collection: {e}")
        
        log(f"Config {config_num}: Panning DISABLED - All resources released")

# Generic toggle_zooming function that works with any config
def toggle_zooming_for_config(pressed, config, src_settings, current_scene_item, config_num):
    """Toggle zooming on or off for a specific config"""
    global script_settings
    
    # Bail if not pressed
    if not pressed:
        return
    
    # Ensure we have valid settings
    if script_settings is None:
        log_error(f"Toggle zooming failed: No valid settings available")
        return
        
    # Refresh all critical settings from the UI
    # This ensures we're always using the latest values
    
    # Check if this config is enabled
    config_enabled = obs.obs_data_get_bool(script_settings, f"config{config_num}_enabled")
    config["enabled"] = config_enabled  # Update in-memory config
    
    if not config_enabled:
        log(f"Config {config_num}: Cannot toggle zooming: Config is disabled")
        return
        
    # Update zoom settings
    zoom_level = obs.obs_data_get_double(script_settings, f"config{config_num}_zoom_level")
    config["zoom_level"] = max(1.0, min(5.0, zoom_level))
    
    # Update transition durations
    zoom_in_duration = obs.obs_data_get_double(script_settings, f"config{config_num}_zoom_in_duration")
    config["zoom_in_duration"] = max(0.0, min(1.0, zoom_in_duration))
    
    zoom_out_duration = obs.obs_data_get_double(script_settings, f"config{config_num}_zoom_out_duration")
    config["zoom_out_duration"] = max(0.0, min(1.0, zoom_out_duration))
    
    # Update offset values
    config["offset_x"] = obs.obs_data_get_int(script_settings, f"config{config_num}_offset_x")
    config["offset_y"] = obs.obs_data_get_int(script_settings, f"config{config_num}_offset_y")
    
    # Check if panning is enabled (required for zooming)
    if not config.get("pan_enabled", False):
        log(f"Config {config_num}: Cannot toggle zooming: Panning must be enabled first")
        return
    
    if src_settings["viewport_width"] <= 0 or src_settings["viewport_height"] <= 0:
        log(f"Config {config_num}: Cannot toggle zooming: Viewport not set properly.")
        return
    
    # Toggle zoom state
    new_zoom_enabled = not config.get("zoom_enabled", False)
    config["zoom_enabled"] = new_zoom_enabled
    
    # Get current scene item based on config number
    scene_item = current_scene_item
    
    # Only start a transition if we have a valid scene item
    if scene_item:
        # Determine current actual zoom level (might be mid-transition)
        current_zoom = config["zoom_level"]
        
        # If we're in the middle of a transition, calculate the actual current zoom level
        if src_settings["is_transitioning"]:
            elapsed_time = time.time() - src_settings["transition_start_time"]
            progress = min(1.0, elapsed_time / src_settings["transition_duration"])
            eased_progress = ease_in_out_quad(progress)
            
            # Get the actual current interpolated zoom level
            start_zoom = src_settings["transition_start_zoom"]
            target_zoom = src_settings["transition_target_zoom"]
            current_zoom = start_zoom + (target_zoom - start_zoom) * eased_progress
            
        # Set up the transition
        src_settings["is_transitioning"] = True
        src_settings["transition_start_time"] = time.time()
        
        if new_zoom_enabled:
            # Transitioning from 1.0 to zoom_level (zoom IN)
            src_settings["transition_start_zoom"] = 1.0
            src_settings["transition_target_zoom"] = config["zoom_level"]
            src_settings["transition_duration"] = config["zoom_in_duration"]
            src_settings["is_zooming_in"] = True
            log(f"Config {config_num}: Zooming IN to {config['zoom_level']}x over {config['zoom_in_duration']}s")
        else:
            # Transitioning from current zoom level to 1.0 (zoom OUT)
            src_settings["transition_start_zoom"] = current_zoom
            src_settings["transition_target_zoom"] = 1.0
            src_settings["transition_duration"] = config["zoom_out_duration"] 
            src_settings["is_zooming_in"] = False
            log(f"Config {config_num}: Zooming OUT to 1.0x over {config['zoom_out_duration']}s from current zoom {current_zoom:.2f}")
    else:
        log_warning(f"Config {config_num}: Cannot perform zoom transition: No valid scene item")

# Main update function called by OBS timer
def update_pan_and_zoom():
    """Master update function that updates both configs"""
    global g_current_scene_item1, g_current_scene_item2
    
    # Update config 1 if enabled
    if config1.get("enabled", False):
        update_pan_and_zoom_for_config(config1, source_settings1, g_current_scene_item1)
    
    # Update config 2 if enabled
    if config2.get("enabled", False):
        update_pan_and_zoom_for_config(config2, source_settings2, g_current_scene_item2)


# Helper function to refresh source/viewport caches for a specific config
def refresh_caches_for_config(target_config):
    """Refresh source and viewport caches for a given configuration object"""
    try:
        target_config["source_cache"] = [] # Initialize/clear caches
        target_config["viewport_cache"] = []

        selected_scene_name = target_config.get("target_scene_name", "")
        selected_scene_uuid = target_config.get("target_scene_uuid", "")
        config_id_for_log = "Config1" if target_config is config1 else "Config2"

        if not selected_scene_name:
            return # Nothing to cache if no scene is selected

        scene_source = None
        if selected_scene_uuid:
            scene_source = find_source_by_uuid(selected_scene_uuid)
        
        if not scene_source and selected_scene_name: # Fallback to name if UUID fails or not present
            scene_source = obs.obs_get_source_by_name(selected_scene_name)
            
        if not scene_source:
            log_warning(f"Scene '{selected_scene_name}' not found for {config_id_for_log}. Caches will be empty.")
            return

        # Successfully found scene_source, now populate caches
        scene = obs.obs_scene_from_source(scene_source)
        if scene:
            source_cache = []
            viewport_cache = []
            
            # For viewport list, always add "Use Scene Dimensions" first if a scene is selected
            viewport_cache.append({"name": "Use Scene Dimensions", "value": USE_SCENE_DIMENSIONS})
            
            items = obs.obs_scene_enum_items(scene)
            if items:
                for item in items:
                    if not item: continue
                    source_from_item = obs.obs_sceneitem_get_source(item)
                    if not source_from_item: continue
                        
                    source_name = obs.obs_source_get_name(source_from_item)
                    source_uuid = get_source_uuid(source_from_item)
                    composite_value = f"{source_name}:{source_uuid}"
                    
                    source_cache.append({"name": source_name, "value": composite_value})
                    viewport_cache.append({"name": source_name, "value": composite_value})
                obs.sceneitem_list_release(items)
            
            target_config["source_cache"] = source_cache
            target_config["viewport_cache"] = viewport_cache
        else:
            log_warning(f"Could not get scene object from source '{selected_scene_name}' for {config_id_for_log}.")
        
        obs.obs_source_release(scene_source)

    except Exception as e:
        config_id_for_log_exc = "Config1" if target_config is config1 else "Config2"
        log_error(f"Error in refresh_caches_for_config for {config_id_for_log_exc}: {e}\n{traceback.format_exc()}")
        # Ensure caches are at least empty lists on error
        target_config["source_cache"] = [] 
        target_config["viewport_cache"] = []