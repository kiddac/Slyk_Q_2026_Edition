# Slyk_Q_2026_Edition
Sky Q Style Enigma2 Skin 2026 Edition

/usr/share/enigma2/slyk-q-2026-edition/skin.xml

## SlykQ2026Edition selector

The package includes a small Enigma2 extension named **SlykQ2026Edition**.
The extension is shown in the plugin menu only while this skin is selected;
its skin-change hook adds or removes the entry during live skin changes.
It currently provides only these settings:

- Skin resolution: Full HD (1920x1080) or WQHD (2560x1440).
- Theme: Default, Black or Glass.
- Receiver image: OpenATV/OpenVIX or OpenBH.

Applying the settings rebuilds the XML files from the untouched files in the
`source` directory, activates graphics from `assets/<resolution>/<theme>`, and
then offers to restart the Enigma2 GUI.

The WQHD conversion covers normal XML geometry and fonts as well as Enigma2
template details such as aliases, margins, component dimensions, pointer
offsets, MultiContent `pos`/`size` tuples, `gFont`/`parseFont`, template item
dimensions, and geometry set from embedded applets.

The OpenBH choice keeps the normal OpenATV/OpenVIX definitions and appends
`q-obh4u.xml` as the final include. Theme colour overrides are stored in
`themes.json`.


