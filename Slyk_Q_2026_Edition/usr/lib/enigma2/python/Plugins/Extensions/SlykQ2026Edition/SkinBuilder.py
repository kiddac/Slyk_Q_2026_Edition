from __future__ import annotations

import json
import os
import re

from decimal import Decimal, ROUND_CEILING


SKIN_NAME = "slyk-q-2026-edition"
DEFAULT_SKIN_ROOT = "/usr/share/enigma2/%s" % SKIN_NAME

RESOLUTIONS = {
    "FHD": (1920, 1080, Decimal("1")),
    "WQHD": (2560, 1440, Decimal("1.333333333333333333")),
}

THEME_FILE = "themes.json"
SOURCE_DIRECTORY = "source"
ASSET_DIRECTORY = "assets"

# Numeric attributes that describe screen geometry. This list mirrors the
# Enigma2SkinConverter rules rather than trying to scale every numeric XML
# attribute (which would corrupt booleans, indexes, colours and zPosition).
VECTOR_ATTRIBUTES = (
    "position", "size", "offset", "textOffset", "padding", "textPadding",
    "itemSpacing", "shadowOffset", "selectionZoomSize", "separatorLineSize",
    "fontScale", "entryFontScale",
)
SINGLE_ATTRIBUTES = (
    "beginMargin", "borderWidth", "ChannelOffset", "ChannelWidth",
    "cornerRadius", "dividerHeight", "endMargin", "entryLeftOffset",
    "EventBorderWidth", "EventNameOffset", "EventNamePadding", "EventNameWidth",
    "eventNowHeight", "fieldMargins", "fillerCount", "gfxX",
    "gfxY", "headerLeftOffset", "iconHeight", "iconHPos",
    "iconMargin", "iconWidth", "iconXOffset", "iconYOffset",
    "indentSize", "itemCornerRadius", "itemCornerRadiusMarked",
    "itemCornerRadiusMarkedAndSelected", "itemCornerRadiusSelected",
    "itemHeight", "itemMargin", "itemsDistances", "itemWidth",
    "keyIconHeight", "keyIconWidth", "keyIconXOffset", "keyIconYOffset",
    "nonplayableMargins", "piconOffset", "piconWidth", "piconWidthBig",
    "pixmap2Height", "pixmap2Width", "pixmapHeight", "pixmapWidth",
    "progressbarBorderWidth", "progressbarHeight", "progressBarMargin",
    "progressBarWidth", "RecIconSize", "RecOffset", "RemainingTimeWidth",
    "rowHeight", "rowSplit", "rowSplit1", "rowSplit2",
    "satPosLeft", "scrollbarBorderWidth", "scrollbarLength",
    "scrollbarOffset", "scrollbarRadius", "scrollbarSliderBorderWidth",
    "scrollbarWidth", "secondFont", "secondfont", "seperation", "ServiceBorderWidth",
    "serviceInfoHeightAdd", "serviceItemHeight", "serviceItemHeightLarge",
    "ServiceNamePadding", "serviceNumberWidth", "spacing", "split",
    "startMargin", "tabWidth", "text2Height", "text2Width",
    "text2X", "text2Y", "textBorderWidth", "textHeight",
    "textWidth", "textX", "textXOffset", "textY",
    "textYOffset", "TimeFutureIndicatorWidth", "TimeOffset",
    "TimeWidth", "widgetBorderWidth",
)


class SkinBuildError(Exception):
    pass


def _scaled_number(value: str, factor: Decimal) -> str:
    # The desktop converter uses Math.Ceiling while enlarging a skin. Apply the
    # ceiling to the magnitude so negative offsets grow away from zero too.
    number = Decimal(value)
    sign = -1 if number < 0 else 1
    scaled = (abs(number) * factor).quantize(Decimal("1"), rounding=ROUND_CEILING)
    return str(sign * int(scaled))


def _scale_numbers(value: str, factor: Decimal) -> str:
    return re.sub(r"-?\d+", lambda match: _scaled_number(match.group(0), factor), value)


def _scale_attribute(text: str, attribute: str, factor: Decimal) -> str:
    # The leading boundary is essential: without it, padding also matches
    # textPadding and itemHeight also matches serviceItemHeight, causing a second
    # scaling pass on the same value.
    pattern = re.compile(r"((?<![\w-])%s\s*=\s*\")([^\"]*)(\")" % re.escape(attribute), re.IGNORECASE)
    return pattern.sub(lambda match: match.group(1) + _scale_numbers(match.group(2), factor) + match.group(3), text)


def _scale_font_attributes(text: str, factor: Decimal) -> str:
    # Handles font="Regular;30" as well as comma-separated font lists.
    pattern = re.compile(r"((?:\w*[Ff]ont\w*|fonts)\s*=\s*\")([^\"]+)(\")")

    def replace(match):
        value = re.sub(
            r"(?<=;)\s*(-?\d+)",
            lambda number: _scaled_number(number.group(1), factor),
            match.group(2),
        )
        return match.group(1) + value + match.group(3)

    return pattern.sub(replace, text)


def _scale_aliases(text: str, factor: Decimal) -> str:
    pattern = re.compile(r"<alias\b[^>]*>", re.IGNORECASE)

    def replace_alias(match):
        alias = match.group(0)
        # Alias size has already been handled by the general size pass.
        for attribute in ("height", "width"):
            alias = _scale_attribute(alias, attribute, factor)
        return alias

    return pattern.sub(replace_alias, text)


def _scale_margin_elements(text: str, factor: Decimal) -> str:
    pattern = re.compile(r"<margin\b[^>]*>", re.IGNORECASE)

    def replace_margin(match):
        margin = match.group(0)
        for attribute in ("left", "top", "right", "bottom"):
            margin = _scale_attribute(margin, attribute, factor)
        return margin

    return pattern.sub(replace_margin, text)


def _scale_resource_offsets(text: str, factor: Decimal) -> str:
    # Pixmaps can carry an origin after the filename, for example
    # pointer="position_arrow.png:5,8".
    png_offset = re.compile(r"(\.png\s*:\s*)(-?\d+)(\s*,\s*)(-?\d+)", re.IGNORECASE)
    text = png_offset.sub(
        lambda match: match.group(1) + _scaled_number(match.group(2), factor)
        + match.group(3) + _scaled_number(match.group(4), factor),
        text,
    )

    # Also support pointer resources that do not use a PNG extension.
    pointer = re.compile(
        r"((?:seekPointer|seek_pointer|pointer)\s*=\s*\"(?![^\"]*\.png\s*:)[^\"]*?:\s*)(-?\d+)(\s*,\s*)(-?\d+)",
        re.IGNORECASE,
    )
    return pointer.sub(
        lambda match: match.group(1) + _scaled_number(match.group(2), factor)
        + match.group(3) + _scaled_number(match.group(4), factor),
        text,
    )


def _scale_embedded_code(text: str, factor: Decimal) -> str:
    # MultiContent templates embed Python geometry directly inside XML text.
    tuple_pattern = re.compile(r"(\b(?:pos|size)\s*=\s*\(\s*)([^)]*)(\))")
    text = tuple_pattern.sub(
        lambda match: match.group(1) + _scale_numbers(match.group(2), factor) + match.group(3),
        text,
    )

    # Both gFont("Regular", 30) and parseFont("Regular;30") occur in templates
    # and applets, independently of normal XML font attributes.
    gfont_pattern = re.compile(r"(\bgFont\s*\(\s*[\"'][^\"']+[\"']\s*,\s*)(-?\d+)")
    text = gfont_pattern.sub(
        lambda match: match.group(1) + _scaled_number(match.group(2), factor), text
    )
    parse_font_pattern = re.compile(r"(\bparseFont\s*\(\s*[\"'][^\"';]+\s*;\s*)(-?\d+)")
    text = parse_font_pattern.sub(
        lambda match: match.group(1) + _scaled_number(match.group(2), factor), text
    )

    # Template dictionaries and the common (height, [entries]) template form.
    dict_dimension = re.compile(r"([\"'](?:itemHeight|itemWidth)[\"']\s*:\s*)(-?\d+)", re.IGNORECASE)
    text = dict_dimension.sub(
        lambda match: match.group(1) + _scaled_number(match.group(2), factor), text
    )
    template_height = re.compile(r"([\"'][^\"']+[\"']\s*:\s*\(\s*)(-?\d+)(?=\s*,\s*\[)")
    text = template_height.sub(
        lambda match: match.group(1) + _scaled_number(match.group(2), factor), text
    )

    # Geometry set from applets rather than declared in XML attributes.
    code_number_patterns = (
        r"(\bsetItemHeight\s*\(\s*)(-?\d+)",
        r"(\.bouquetNamePadding\s*=\s*)(-?\d+)",
        r"(\bpagelength\s*=\s*)(-?\d+)",
    )
    for expression in code_number_patterns:
        text = re.sub(
            expression,
            lambda match: match.group(1) + _scaled_number(match.group(2), factor),
            text,
        )

    # Preserve runtime expressions such as width - 10 while scaling their fixed
    # pixel offset. Tuple expressions were already converted above, so exclude
    # those lines to avoid scaling the same offset twice.
    lines = []
    for line in text.splitlines(True):
        if not re.search(r"\b(?:pos|size)\s*=\s*\(", line):
            line = re.sub(
                r"(\bwidth\s*-\s*)(\d+)",
                lambda match: match.group(1) + _scaled_number(match.group(2), factor),
                line,
            )
        lines.append(line)
    return "".join(lines)


def _scale_scrolltext_step(text: str, factor: Decimal) -> str:
    pattern = re.compile(r"(scrollText\s*=\s*\"[^\"]*?\bstepSize\s*=\s*)(-?\d+)", re.IGNORECASE)
    return pattern.sub(
        lambda match: match.group(1) + _scaled_number(match.group(2), factor), text
    )


def scale_xml(text: str, resolution: str) -> str:
    try:
        xres, yres, factor = RESOLUTIONS[resolution]
    except KeyError as error:
        raise SkinBuildError("Unsupported resolution: %s" % resolution) from error

    if factor != 1:
        for attribute in VECTOR_ATTRIBUTES:
            text = _scale_attribute(text, attribute, factor)
        for attribute in SINGLE_ATTRIBUTES:
            text = _scale_attribute(text, attribute, factor)

        # Parameter values in this skin contain positions, sizes and font metrics.
        parameter_pattern = re.compile(r"(<parameter\b[^>]*\bvalue=\")([^\"]+)(\"[^>]*>)", re.IGNORECASE)
        text = parameter_pattern.sub(
            lambda match: match.group(1) + _scale_numbers(match.group(2), factor) + match.group(3),
            text,
        )
        text = _scale_font_attributes(text, factor)
        text = _scale_aliases(text, factor)
        text = _scale_margin_elements(text, factor)
        text = _scale_resource_offsets(text, factor)
        text = _scale_embedded_code(text, factor)
        text = _scale_scrolltext_step(text, factor)

    # Always write the exact selected desktop size, including when rebuilding FHD.
    text = re.sub(r'(xres=")\d+("\s+yres=")\d+', r'\g<1>%d\g<2>%d' % (xres, yres), text, count=1)
    return text


def load_themes(skin_root: str = DEFAULT_SKIN_ROOT) -> dict:
    path = os.path.join(skin_root, THEME_FILE)
    try:
        with open(path, "r", encoding="utf-8") as theme_file:
            data = json.load(theme_file)
    except (OSError, ValueError) as error:
        raise SkinBuildError("Unable to read %s: %s" % (path, error)) from error
    if not isinstance(data.get("themes"), dict):
        raise SkinBuildError("themes.json does not contain a themes object")
    return data


def apply_theme_colors(text: str, theme: str, themes: dict) -> str:
    try:
        colors = themes["themes"][theme].get("colors", {})
    except KeyError as error:
        raise SkinBuildError("Unknown theme: %s" % theme) from error

    for name, value in colors.items():
        pattern = re.compile(r'(<color\s+name="%s"\s+value=")[^"]+("\s*/>)' % re.escape(name))
        text = pattern.sub(lambda match: match.group(1) + value + match.group(2), text)
    return text


def apply_image_includes(text: str, image_family: str) -> str:
    if image_family not in ("openatv_openvix", "openbh"):
        raise SkinBuildError("Unknown image family: %s" % image_family)

    lines = text.splitlines(True)
    filtered = []
    last_include = None
    for line in lines:
        if 'filename="q-obh4u.xml"' in line:
            continue
        filtered.append(line)
        if "<include " in line:
            last_include = len(filtered)

    if image_family == "openbh":
        indent = "\t"
        filtered.insert(last_include or 0, '%s<include filename="q-obh4u.xml" />\n' % indent)
    return "".join(filtered)


def _atomic_write(path: str, content: str) -> None:
    temporary = path + ".new"
    with open(temporary, "w", encoding="utf-8", newline="") as output:
        output.write(content)
    os.replace(temporary, path)


def build_skin(resolution: str, theme: str, image_family: str, skin_root: str = DEFAULT_SKIN_ROOT) -> None:
    if resolution not in RESOLUTIONS:
        raise SkinBuildError("Unsupported resolution: %s" % resolution)

    themes = load_themes(skin_root)
    source_root = os.path.join(skin_root, SOURCE_DIRECTORY)
    if not os.path.isdir(source_root):
        raise SkinBuildError("Skin source directory is missing: %s" % source_root)

    for filename in sorted(os.listdir(source_root)):
        if not filename.endswith(".xml"):
            continue
        source_path = os.path.join(source_root, filename)
        with open(source_path, "r", encoding="utf-8") as source_file:
            content = source_file.read()
        content = scale_xml(content, resolution)
        if filename == "skin.xml":
            content = apply_theme_colors(content, theme, themes)
            content = apply_image_includes(content, image_family)
        _atomic_write(os.path.join(skin_root, filename), content)

    activate_assets(resolution, theme, skin_root, themes)


def activate_assets(resolution: str, theme: str, skin_root: str, themes: dict | None = None) -> None:
    themes = themes or load_themes(skin_root)

    try:
        asset_theme = themes["themes"][theme].get("assetTheme", theme)
    except KeyError as error:
        raise SkinBuildError("Unknown theme: %s" % theme) from error

    resolution_root = os.path.join(skin_root, ASSET_DIRECTORY, resolution)
    common_root = os.path.join(resolution_root, "common")
    theme_root = os.path.join(resolution_root, asset_theme)
    manifest_path = os.path.join(skin_root, ".skinbuilder-links.json")

    if not os.path.isdir(common_root):
        raise SkinBuildError("Common graphics directory is missing: %s" % common_root)

    if not os.path.isdir(theme_root):
        raise SkinBuildError("Theme graphics directory is missing: %s" % theme_root)

    graphics = {}

    for root in (common_root, theme_root):
        for directory, folders, filenames in os.walk(root):
            for filename in filenames:
                source = os.path.join(directory, filename)
                relative = os.path.relpath(source, root)

                graphics[relative] = source

    previous_links = []
    previous_directories = []

    if os.path.isfile(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as manifest:
            data = json.load(manifest)

        previous_links = data.get("links", [])
        previous_directories = data.get("directories", [])

    for relative in previous_links:
        destination = os.path.join(skin_root, relative)

        if os.path.islink(destination):
            os.unlink(destination)

    for relative in sorted(previous_directories, key=len, reverse=True):
        destination = os.path.join(skin_root, relative)

        if os.path.isdir(destination) and not os.path.islink(destination):
            try:
                os.rmdir(destination)
            except OSError:
                pass

    created_links = []
    created_directories = set()

    for relative, source in sorted(graphics.items()):
        destination = os.path.join(skin_root, relative)
        directory = os.path.dirname(destination)

        if not os.path.isdir(directory):
            missing = []
            current = directory

            while not os.path.exists(current):
                missing.append(current)
                current = os.path.dirname(current)

            for path in reversed(missing):
                os.mkdir(path)
                created_directories.add(os.path.relpath(path, skin_root))

        if os.path.islink(destination):
            target = os.path.realpath(destination)
            asset_root = os.path.realpath(
                os.path.join(skin_root, ASSET_DIRECTORY)
            )

            if os.path.commonpath((target, asset_root)) == asset_root:
                os.unlink(destination)
            else:
                raise SkinBuildError("Unmanaged symbolic link: %s" % destination)

        elif os.path.lexists(destination):
            raise SkinBuildError("Asset destination already exists: %s" % destination)

        os.symlink(os.path.relpath(source, directory), destination)
        created_links.append(relative)

    directory_names = set(previous_directories)
    directory_names.update(created_directories)

    data = {
        "links": created_links,
        "directories": sorted(directory_names),
    }

    _atomic_write(manifest_path, json.dumps(data, indent=4))
