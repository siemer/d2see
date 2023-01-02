
import sys
import gi
gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, Gdk
from Xlib import display



d = display.Display()  # an obj, should refer to X11’s :0
s = d.screen()  # s._data.keys() → s.<key_name>
  # on my multi-monitor i3 sessions screen spans the combined w/h of that L-shaped space
  # d.screen_count() is 1 on my setup and screen() can take an int
  # but Gtk3 deprecated all int related screen functions saying: there is always only one
r = s.root  # a Window obj; seems to be exactly 1 root per screen...
sres = r.xrandr_get_screen_resources()  # same _data.keys() trick shows attributes
  # there is also a get_screen_resources_current() variant available
print('crtcs:', sres.crtcs)
for output in sres.outputs:
    info = d.xrandr_get_output_info(output, 0)
    print('output:', output, 'crtc:', info.crtc,
        'name:', info.name)
    edid_int = d.get_atom('EDID')
    if edid_int in d.xrandr_list_output_properties(output).atoms:
        property = d.xrandr_get_output_property(output, edid_int, 0, 0, 4).value

print('MONITORS')
for monitor in r.xrandr_get_monitors().monitors:
    print('name:', d.get_atom_name(monitor.name), 'crtcs:', monitor.crtcs)

print('CRTCS')
for crtc in sres.crtcs:
    print(crtc, d.xrandr_get_crtc_info(crtc, 0).outputs)


gr = Gdk.get_default_root_window()
gd = gr.get_display()
gs = gd.get_default_screen()