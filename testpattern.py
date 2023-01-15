#!/usr/bin/python3

import gi
import trio
import trio_gtk

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, Gdk

from ddcci import ddcci

class TestPattern(Gtk.Bin):
    def __init__(self, *args, **kwargs):
        super().__init__()

    # avoids error:
    # Gtk-CRITICAL gtk_widget_get_preferred_width_for_height:
    #  assertion 'height >= 0' failed
    def do_get_preferred_height(self):
        return 300, 500

    def do_size_allocate(self, allocation):
        self.set_allocation(allocation)
        width, height = allocation.width, allocation.height
        #print("do_size_allocate() FUNCTION, width:", width)
        smaller_dim = min(width, height)
        if smaller_dim > 800:
            self.square_size = 80
            self.margin = 20
        else:
            self.square_size = max(40, smaller_dim/10)
            self.margin = 10
        def step_amount(dim_size):
            nr = round((dim_size - 2 * self.margin) / self.square_size)
            return max(min(20, nr), 7)
        self.steps4x = step_amount(width)
        self.steps4y = step_amount(height)
        def step_size(dim, steps):
            return (dim - 2*self.margin - 2*self.square_size) / (steps - 2)
        self.xstep = step_size(width, self.steps4x)
        self.ystep = step_size(height, self.steps4y)

        r = Gdk.Rectangle()
        r.x = r.y = 2 * self.margin + self.square_size
        r.width = width - 2 * r.x
        r.height = height - 2 * r.y
        self.get_child().size_allocate(r)

    def draw_square(self, c, x0, y0, x1, y1, color):
        c.set_source_rgb(color, color, color)
        x0 = round(x0)
        x1 = round(x1)
        y0 = round(y0)
        y1 = round(y1)
        c.move_to(x0, y0)
        c.line_to(x1, y0)
        c.line_to(x1, y1)
        c.line_to(x0, y1)
        c.fill()

    def draw_segment(self, c, x0, y0, xdir, ydir, start_color):
        assert 0 in (xdir, ydir)
        steps = self.steps4x if xdir else self.steps4y
        color_step = 1 / (steps - 1)
        if start_color == 1:
            color_step *= -1
        # as we draw overlapping segments, I can skip the last one...
        for i in range(steps):
            if i in (0, steps-1):
                xstep = ystep = self.square_size
            elif xdir:
                xstep = self.xstep
            else:
                ystep = self.ystep
            self.draw_square(c, x0, y0, x0+xstep, y0+ystep, start_color+color_step*i)
            x0 += xdir * xstep
            y0 += ydir * ystep

    def draw_segments(self, c):
        x0 = y0 = self.margin
        def xy1(xy0, step_amount, step_size):
            return xy0 + self.square_size + (step_amount-2) * step_size
        x1 = xy1(x0, self.steps4x, self.xstep)
        y1 = xy1(y0, self.steps4y, self.ystep)
        draw = lambda *args, **kwargs: self.draw_segment(c, *args, **kwargs)
        draw(x0, y0, 1, 0, 0)
        draw(x0, y0, 0, 1, 0)
        draw(x1, y0, 0, 1, 1)
        draw(x0, y1, 1, 0, 1)

    def do_draw(self, c):
        allocation = self.get_allocation()
        w, h = allocation.width, allocation.height
        # print('draw():', w, h)
        Gtk.render_background(self.get_style_context(), c, 0, 0, w, h)

        c.set_source_rgb(1, 1, 1)
        c.paint()
        self.draw_segments(c)
        self.propagate_draw(self.get_child(), c)

class MonitorSettings(Gtk.VBox):
    def __init__(self, mc):
        super().__init__()
        for register, label in (
                (0x10, 'Brightness'),
                (0x12, 'Contrast'),
            ):
            self.pack_start(MonitorScale(mc, register, label), False, False, 0)

class MonitorScale(Gtk.HBox):
    def __init__(self, mc, register, text):
        super().__init__()
        label = Gtk.Label(label=text)
        scale = Gtk.Scale()
        scale.set_size_request(100, -1)
        scale.set_digits(0)
        scale.set_increments(-5, 5)
        scale.connect('value-changed',
                lambda scale: mc.write(register, round(scale.get_value()))
            )
        mc.add_listeners(register,
                lambda val: scale.set_value(val),
                lambda max: scale.set_range(0, max),
            )
        self.pack_start(scale, False, False, 0)
        self.pack_start(label, False, False, 0)


class PatternWindow(Gtk.Window):
    def __init__(self, monitor_controllers, desktop_index):
        super().__init__(title='d2see test pattern')
        self.desktop_index = desktop_index
        self.connect('delete-event', Gtk.main_quit)
        self.connect('map-event', self.mapped)
        label_hello = Gtk.Label(label='Hello!')
        button_close = Gtk.Button(label='Close')
        button_close.connect('clicked', Gtk.main_quit)
        button_box = Gtk.HButtonBox()
        button_box.pack_start(button_close, False, False, 0)
        hbox_bottom = Gtk.HBox()
        for mc in monitor_controllers:
            hbox_bottom.pack_start(MonitorSettings(mc), False, False, 0)
        hbox_bottom.pack_start(button_box, False, False, 0)
        vbox_main = Gtk.VBox()
        vbox_main.pack_start(label_hello, False, False, 0)
        vbox_main.pack_start(hbox_bottom, False, False, 0)
        pattern = TestPattern()
        pattern.add(vbox_main)
        self.add(pattern)
        # style_provider = Gtk.CssProvider()
        # style_provider.load_from_data(b'''
        #     * { color: #ff0077;
        #     background-color: #ffffff }
        # ''')
        # self.get_style_context().add_provider(style_provider,
        #     Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.show_all()

    def mapped(self, self2, event):
        # other move ops don’t work on i3 window manager
        self.get_window().move_to_desktop(self.desktop_index)
        self.fullscreen()

async def main():
    pass

if __name__ == '__main__':
    trio_gtk.run(main)