#!/usr/bin/python3

import argparse
import inspect
import logging
import re
import sys

import ewmh
import gi
import trio
import trio_gtk
import Xlib.display
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from ddcci import ddcci
import testpattern

def log(frequency, category, msg):
  logging.getLogger(category).log(frequency, msg)

def gtext(text):
    return gtext.single_nl.sub(' ', inspect.cleandoc(text))
gtext.single_nl = re.compile(r'(?<!\n)\n(?!\n)')

class TestScreen(Gtk.Window):
    def __init__(self):
        super().__init__(title='D2see Testscreen')

class Assistant(Gtk.Assistant):
    def __init__(self):
        super().__init__(title='D2see')
        page_allow_scan = Gtk.Label(wrap=True, label=gtext('''
            This assistent will help you to setup a joint monitor brightness control
            on multi-screen computers with d2see.
            The goal is to enable you to quickly adjust all screens at once, e.g.
            according to the current environmental lighting situation in your work place.

            Note: right now now now, laptop screens are not supported—they use a
            different interface.

            First allow me to check all i2c busses for attached monitors (/dev/i2c-*).
            Even though I only do a read operation on a well known EEPROM address (0x50),
            in theory some unusual device on an i2c bus unrelated to monitors might
            do something unexpected. In theory. In practise, if you’re so lucky to
            encounter something magic, please do not wait and tell the author of this
            tool!
            '''))
        self.append_page(page_allow_scan)
        self.set_page_complete(page_allow_scan, True)
        self.set_forward_page_func(self.forward)
        '''In the next step every screen will, one by one, change its brightness.
        Select the screen which does so.'''
        '''Continue this assistent on the “blinking” screen.

        If no screen is changing brightness (or it is a repeated screen), skip
        this one.

        If you can’t continue, then this assistent turned out to be useless... ;-)'''
        '''Now let’s see how fast the monitors can react. Continue on every screen.'''
        '''Continue on the other screens.'''
        '''Does the brightness change smothly? (If not '''

    def do_cancel(self):
        Gtk.main_quit()

    def forward(self, page_nr):
        print(f'forward({page_nr}) called with {self.get_n_pages()} pages.')
        if page_nr == 0 and not self.get_nth_page(1):
            print('page 0 is empty')
            self.monitors = ddcci.Edid.scan()
            self.append_page(Gtk.Label(wrap=True, label=gtext(f'''
                I found {len(self.monitors)} monitor(s). If that number is higher
                than expected, please tell the author. If it is lower (apart
                from laptop screens), are you sure that the i2c bus of that
                monitor is accessible to me?

                In any case: those detected monitors I can probably control.

                For the next steps allow me to go fullscreen on all desktops/workspaces.
                ''')))
            self.show_all()

        return page_nr + 1

def create_windows(monitor_controllers, main_cancel_scope):
    monitor_controllers = monitor_controllers.copy()
    display = Xlib.display.Display()
    root = display.screen().root
    edid_atom = display.get_atom('EDID')
    windows = []
    for randr_monitor in root.xrandr_get_monitors().monitors:
        # sth like 'HDMI-0' or self-selected name on virtual monitors
        connector_name = display.get_atom_name(randr_monitor.name)
        matching_controllers = []
        # output and crtcs are different, but here it seems we get the outputs
        for output in randr_monitor.crtcs:  # virtual mons might span more than one
            assert edid_atom in display.xrandr_list_output_properties(output).atoms
            randr_edid = bytes(display.xrandr_get_output_property(output, edid_atom, 0, 0, 64).value)
            edid_match = lambda mc, re: mc.edid_device.edid256.startswith(re)
            mc = next(mc for mc in monitor_controllers if edid_match(mc, randr_edid))
            monitor_controllers.remove(mc)
            matching_controllers.append(mc)
        monitor_names = list(map(lambda mc: mc.edid_device.edid_id, matching_controllers))
        log(27, 'hw_enum', f'Xrandr {connector_name} is {monitor_names}')
        viewports = ewmh.EWMH().getDesktopViewPort()
        for desktop_index, (x, y) in enumerate(zip(viewports[0::2], viewports[1::2])):
            if (randr_monitor.x, randr_monitor.y) == (x, y):
                log(27, 'hw_enum', f'...with desktop {desktop_index}')
                windows.append(testpattern.PatternWindow(matching_controllers, desktop_index, main_cancel_scope))
    return windows

async def main():
    parser = argparse.ArgumentParser(description=
        'Adjust screen brightness and contrast of multiple monitors all at once.')
    a = parser.add_argument
    a('--debug-levels', nargs=2, default=[20, 10], metavar=('DEF', 'CAT'), type=int,
        help='sets default log level to DEF and categories mentioned with --debug to level CAT')
    a('-d', '--debug', nargs='+', default=[],
        help='e.g. `--debug hw_comm sleep=25`, which sets sleep to level 25 '
        'and hw_comm’s level to the second number of the `--debug-levels` option')
    args = parser.parse_args()

    logging.basicConfig(level=args.debug_levels[0])
    for debug_arg in args.debug:
        category, *level = debug_arg.rsplit('=', 1)
        level = int(level[0]) if level else args.debug_levels[1]
        logging.getLogger(category).setLevel(level)

    async with trio.open_nursery() as nursery:
        mcs = ddcci.MonitorController.coldplug(nursery)
        create_windows(mcs, nursery.cancel_scope)

def trio_gtk_run(trio_main, *trio_main_args):
    """Run Trio and PyGTK together."""
    outcome = None

    def done_callback(outcome_trio_main):
        nonlocal outcome
        outcome = outcome_trio_main
        Gtk.main_quit()

    trio.lowlevel.start_guest_run(
        trio_main, *trio_main_args,
        run_sync_soon_threadsafe=GLib.idle_add,
        done_callback=done_callback,
        host_uses_signal_set_wakeup_fd=True,
    )

    Gtk.main()
    return outcome.unwrap()

if __name__ == '__main__':
    sys.exit(trio_gtk_run(main))
