#!/usr/bin/python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

class TestPattern(Gtk.Bin):
    def __init__(self, *args, **kwargs):
        super().__init__()

    def do_size_allocate(self, allocation):
        print("do_size_allocate()")
        self.set_allocation(allocation)
        self.margin = 10
        self.steps4x = 20
        self.steps4y = 8
        calc_step = lambda total, steps: (total - 2*self.margin) // steps
        self.xstep = calc_step(allocation.width, self.steps4x)
        self.ystep = calc_step(allocation.height, self.steps4y)

        r = Gdk.Rectangle()
        r.x = 2 * self.margin + self.xstep
        r.y = 2 * self.margin + self.ystep
        r.width = allocation.width - 2 * r.x
        r.height = allocation.height - 2 * r.y
        self.get_child().size_allocate(r)

    def draw_square(self, c, x0, y0, xstep, ystep, color):
        c.set_source_rgb(color, color, color)
        x1 = x0 + xstep
        y1 = y0 + ystep
        c.move_to(x0, y0)
        c.line_to(x1, y0)
        c.line_to(x1, y1)
        c.line_to(x0, y1)
        c.fill()

    def draw_segment(self, c, x0, y0, xstep, ystep, xdir, ydir, start_color):
        assert 0 in (xdir, ydir)
        steps = self.steps4x if xdir else self.steps4y
        color_step = 1 / (steps - 1)
        if start_color == 1:
            color_step *= -1
        # as we draw overlapping segments, I can skip the last one...
        for i in range(steps - 1):
            self.draw_square(c, x0, y0, xstep, ystep, start_color+color_step*i)
            x0 += xdir * xstep
            y0 += ydir * ystep

    def draw_segments(self, c, w, h):
        x0 = y0 = self.margin
        def draw(x, y, xdir, ydir, start_color):
            self.draw_segment(c, x, y, self.xstep, self.ystep, xdir, ydir, start_color)
        x1 = x0 + (self.steps4x - 1) * self.xstep
        y1 = y0 + (self.steps4y - 1) * self.ystep
        draw(x0, y0, 1, 0, 0)
        draw(x1, y0, 0, 1, 1)
        draw(x1, y1, -1, 0, 0)
        draw(x0, y1, 0, -1, 1)

    def do_draw(self, c):
        allocation = self.get_allocation()
        w, h = allocation.width, allocation.height
        print('draw():', w, h)
        Gtk.render_background(self.get_style_context(), c, 0, 0, w, h)

        c.set_source_rgb(1, 1, 1)
        c.paint()
        self.draw_segments(c, w, h)
        self.propagate_draw(self.get_child(), c)


class PatternWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title='d2see test pattern')
        main = TestPattern()
        box = Gtk.VBox()
        label = Gtk.Label(label='Hello!')
        bb = Gtk.ButtonBox()
        b_close = Gtk.Button(label='Close')
        self.add(main)
        main.add(box)
        box.pack_start(label, True, True, 0)
        box.add(bb)
        bb.add(b_close)
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(b'''
            * { color: #ff0077;
            background-color: #ffffff }
        ''')
        self.get_style_context().add_provider(style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        b_close.connect('clicked', lambda w: self.hide())

if __name__ == '__main__':
    w = PatternWindow()
    w.show_all()
    Gtk.main()