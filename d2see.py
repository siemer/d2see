#!/usr/bin/python3

import inspect
import re
import gi

from ddcci import ddcci

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

def gtext(text):
    return gtext.single_nl.sub(' ', inspect.cleandoc(text))
gtext.single_nl = re.compile(r'(?<!\n)\n(?!\n)')

class Assistant(Gtk.Assistant):
    def __init__(self):
        super().__init__(title='Deedeecee')
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
            monitors = ddcci.Edid.scan()
            self.append_page(Gtk.Label(wrap=True, label=gtext(f'''
                I found {len(monitors)} monitor(s). If that number is higher
                than expected, please tell the author. If it is lower (apart
                from laptop screens), are you sure that the i2c bus of that
                monitor is accessible to me?

                In any case: those detected monitors I can probably control.

                For the next steps allow me to go fullscreen on all desktops/workspaces.
                ''')))

        return page_nr + 1




win = Assistant()
win.connect('destroy', Gtk.main_quit)
win.show_all()
Gtk.main()