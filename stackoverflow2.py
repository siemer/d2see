
import Xlib

d = Xlib.display.Display()  # an obj, should refer to X11’s :0
s = d.screen()  # s._data.keys() → s.<key_name>
  # on my multi-monitor i3 sessions screen spans the combined w/h of that L-shaped space
r = s.root  # a Window obj; seems to be exactly 1 root per screen...
sres = r.xrandr_get_screen_resources()  # same _data.keys() trick shows attributes
  # there is also a get_screen_resources_current() variant available
print('crtcs:', sres.crtcs)
for output in sres.outputs:
    info = d.xrandr_get_output_info(output, 0)
    print('output:', output, 'crtcs:', info.crtcs, 'crtc:', info.crtc,
        'name:', info.name)
    for atom in d.xrandr_list_output_properties(output).atoms:
        print(d.get_atom_name(atom), d.xrandr_query_output_property(output, atom))
        property = d.xrandr_get_output_property(output, atom, 0, 0, 4)
        print(property.property_type)
        print(bytes(property.value))

for monitor in r.xrandr_get_monitors().monitors:
    print('name:', monitor.name, 'crtcs:', monitor.crtcs)

for crtc in sres.crtcs:
    print(crtc, d.xrandr_get_crtc_info(crtc, 0).outputs)