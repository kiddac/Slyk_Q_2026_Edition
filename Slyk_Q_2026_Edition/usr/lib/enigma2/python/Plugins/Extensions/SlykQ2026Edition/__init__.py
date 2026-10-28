from Components.Language import language
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
import gettext


PLUGIN_DOMAIN = "SlykQ2026Edition"
PLUGIN_PATH = "Extensions/SlykQ2026Edition"


def localeInit():
	gettext.bindtextdomain(PLUGIN_DOMAIN, resolveFilename(SCOPE_PLUGINS, PLUGIN_PATH + "/locale"))


def _(text):
	translated = gettext.dgettext(PLUGIN_DOMAIN, text)
	return translated if translated != text else gettext.gettext(text)


localeInit()
language.addCallback(localeInit)
