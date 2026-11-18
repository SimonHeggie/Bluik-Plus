# <pep8 compliant>

import bpy # pylint: disable=import-error
from .debug import Logger # pylint: disable=import-error # DuPYF

def redraw():
    """Forces a redraw of controls by moving the current frame"""
    try:
        frame_current = bpy.context.scene.frame_current
        bpy.context.scene.frame_set(frame_current-1)
        bpy.context.scene.frame_set(frame_current)
    except:
        pass

def showMessageBox( message = "", title = "Message Box", icon = 'INFO'):
    """Displays a simple message box"""
    def draw(self, context):
        self.layout.alert = True
        self.layout.label(text = message)
    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

def debugLog (log = "", time_start = 0):
    """Logs a message to the console and show it as a popup"""
    showMessageBox( log, "Debug Info")
    logger = Logger()
    logger.log(log)
