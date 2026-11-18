# <pep8 compliant>

import platform
import sys
import urllib.parse
import webbrowser

import bpy  # pylint: disable=import-error


class DUBLF_OT_ReportIssue(bpy.types.Operator):
    bl_idname = "dublf.reportIssue"
    bl_label = "Bug Report / Feature Request"
    bl_icon = "ERROR"

    addonName = ""
    toolName = "Tool"
    toolVersion = "0.0.0"
    osName = ""
    osVersion = ""
    hostName = "Blender"
    hostVersion = ""
    # Use /issues/new so GitHub can prefill title/body.
    reportURL = "https://github.com/SimonHeggie/Bluik-Community-Edition/issues/new"

    def execute(self, context):
        tool_name = self.__class__.toolName
        tool_version = self.__class__.toolVersion

        # Get tool name and version (from bl_info) if addonName was set by subclass.
        if self.__class__.addonName:
            addon = context.preferences.addons.get(self.__class__.addonName)
            if addon:
                mod = sys.modules.get(addon.module)
                addon_info = getattr(mod, "bl_info", None) if mod else None
                if addon_info:
                    tool_name = addon_info.get("name", tool_name)
                    version = addon_info.get("version", (0, 0, 0))
                    if isinstance(version, (tuple, list)) and len(version) >= 3:
                        tool_version = f"{version[0]}.{version[1]}.{version[2]}"
                    else:
                        tool_version = str(version)

        # Environment info.
        host_version = bpy.app.version_string
        os_name = platform.system()
        if os_name == "Darwin":
            os_name = "mac"
        os_version = platform.version()

        # Store on class too (keeps original pattern).
        self.__class__.toolName = tool_name
        self.__class__.toolVersion = tool_version
        self.__class__.hostVersion = host_version
        self.__class__.osName = os_name
        self.__class__.osVersion = os_version

        title = "Bug report: <short summary>"

        body = (
            "## Summary\n"
            "<what happened>\n\n"
            "## Steps to reproduce\n"
            "1.\n"
            "2.\n"
            "3.\n\n"
            "## Expected result\n"
            "<what you expected>\n\n"
            "## Actual result\n"
            "<what happened instead>\n\n"
            "## Environment\n"
            f"- Add-on: {tool_name} {tool_version}\n"
            f"- Blender: {host_version}\n"
            f"- OS: {os_name} {os_version}\n"
        )

        query = urllib.parse.urlencode({"title": title, "body": body})
        webbrowser.open(f"{self.reportURL}?{query}")

        return {"FINISHED"}


class OpenURL(bpy.types.Operator):
    bl_idname = "dublf.openurl"
    bl_label = ""

    url: bpy.props.StringProperty(default="")

    def execute(self, context):
        del context
        if self.url:
            webbrowser.open(self.url)
        return {"FINISHED"}
