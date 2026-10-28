from Components.ActionMap import ActionMap
from Components.config import ConfigSelection, ConfigSubsection, config, configfile, getConfigListEntry
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop
from enigma import getDesktop
from os.path import dirname

from . import _
from .SkinBuilder import SkinBuildError, build_skin


if not hasattr(config.plugins, "SlykQ2026Edition"):
	config.plugins.SlykQ2026Edition = ConfigSubsection()
	config.plugins.SlykQ2026Edition.resolution = ConfigSelection(
		default="FHD",
		choices=[("FHD", _("Full HD (1920x1080)")), ("WQHD", _("WQHD (2560x1440)"))],
	)
	config.plugins.SlykQ2026Edition.theme = ConfigSelection(
		default="Default",
		choices=[("Default", _("Default")), ("Black", _("Black")), ("Glass", _("Glass"))],
	)
	config.plugins.SlykQ2026Edition.imageFamily = ConfigSelection(
		default="openatv_openvix",
		choices=[("openatv_openvix", _("OpenATV / OpenVIX")), ("openbh", _("OpenBH"))],
	)


def settings_skin():
	width = getDesktop(0).size().width()
	factor = 2560.0 / 1920.0 if width >= 2560 else 1.0
	def scaled(value):
		return int(round(value * factor))
	return """
	<screen name="SlykQ2026EditionSetup" position="center,center" size="%d,%d" title="Slyk Q 2026 Edition">
		<widget name="config" position="%d,%d" size="%d,%d" font="Regular;%d" valueFont="Regular;%d" itemHeight="%d" scrollbarMode="showOnDemand" />
		<eLabel position="%d,%d" size="%d,%d" backgroundColor="#00aa0000" />
		<widget name="key_red" position="%d,%d" size="%d,%d" font="Regular;%d" valign="center" />
		<eLabel position="%d,%d" size="%d,%d" backgroundColor="#0000aa00" />
		<widget name="key_green" position="%d,%d" size="%d,%d" font="Regular;%d" valign="center" />
	</screen>""" % (
		scaled(1000), scaled(550),
		scaled(30), scaled(30), scaled(940), scaled(390), scaled(30), scaled(30), scaled(60),
		scaled(30), scaled(465), scaled(8), scaled(45),
		scaled(50), scaled(465), scaled(300), scaled(45), scaled(28),
		scaled(510), scaled(465), scaled(8), scaled(45),
		scaled(530), scaled(465), scaled(400), scaled(45), scaled(28),
	)


class SlykQ2026EditionSetup(Screen, ConfigListScreen):
	def __init__(self, session):
		self.skin = settings_skin()
		Screen.__init__(self, session)
		self.setTitle(_("Slyk Q 2026 Edition Settings"))
		entries = [
			getConfigListEntry(_("Skin resolution"), config.plugins.SlykQ2026Edition.resolution),
			getConfigListEntry(_("Theme"), config.plugins.SlykQ2026Edition.theme),
			getConfigListEntry(_("Receiver image"), config.plugins.SlykQ2026Edition.imageFamily),
		]
		ConfigListScreen.__init__(self, entries, session=session)
		self["key_red"] = Label(_("Cancel"))
		self["key_green"] = Label(_("Apply and restart"))
		self["actions"] = ActionMap(
			["OkCancelActions", "ColorActions"],
			{"cancel": self.cancel, "red": self.cancel, "green": self.apply, "ok": self.apply},
			-2,
		)

	def cancel(self):
		for item in self["config"].list:
			item[1].cancel()
		self.close()

	def apply(self):
		try:
			build_skin(
				config.plugins.SlykQ2026Edition.resolution.value,
				config.plugins.SlykQ2026Edition.theme.value,
				config.plugins.SlykQ2026Edition.imageFamily.value,
			)
		except (OSError, SkinBuildError) as error:
			self.session.open(MessageBox, _("Unable to build the skin:\n%s") % error, MessageBox.TYPE_ERROR)
			return

		for item in self["config"].list:
			item[1].save()
		configfile.save()
		self.session.openWithCallback(
			self.restart_answer,
			MessageBox,
			_("The skin was rebuilt successfully. Restart the Enigma2 GUI now?"),
			MessageBox.TYPE_YESNO,
			default=True,
		)

	def restart_answer(self, answer):
		if answer:
			self.session.open(TryQuitMainloop, 3)
		else:
			self.close()


def main(session, **kwargs):
	session.open(SlykQ2026EditionSetup)


def skin_active():
	primary_skin = config.skin.primary_skin.value.replace("\\", "/").lower()
	return primary_skin == "slyk-q-2026-edition/skin.xml"


def menu_descriptor():
	return PluginDescriptor(
		name=_("KiddaC Slyk Q 2026 Edition"),
		description=_("Select the Slyk Q resolution, theme and receiver image"),
		where=PluginDescriptor.WHERE_PLUGINMENU,
		fnc=main,
		needsRestart=False,
	)


def refresh_plugin_visibility(session=None, **kwargs):
	# Keep the menu in sync when Enigma2 changes skin without restarting.
	from Components.PluginComponent import plugins
	entries = [
		entry for entry in plugins.getPlugins(PluginDescriptor.WHERE_PLUGINMENU)
		if entry.function == main
	]
	if skin_active():
		if not entries:
			plugins.addPlugin(menu_descriptor(), path=dirname(__file__))
	else:
		for entry in entries:
			plugins.removePlugin(entry)


def autostart(reason, **kwargs):
	if reason == 0:
		refresh_plugin_visibility()


def Plugins(**kwargs):
	# The hooks remain registered under other skins so a live skin change can
	# add the menu without requiring a full receiver restart.
	entries = [menu_descriptor()] if skin_active() else []
	entries.extend((
		PluginDescriptor(where=PluginDescriptor.WHERE_SKINCHANGE, needsRestart=False, fnc=refresh_plugin_visibility),
		PluginDescriptor(where=PluginDescriptor.WHERE_AUTOSTART, needsRestart=False, fnc=autostart),
	))
	return entries
