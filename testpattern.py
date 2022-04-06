#!/usr/bin/python3

from curses.textpad import rectangle
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

class TestPattern(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.box = box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.da = da = Gtk.DrawingArea()
        self.label = label = Gtk.Label(label='Hello!')
        self.bb = bb = Gtk.ButtonBox()
        self.b_close = b_close = Gtk.Button(label='Close')
        self.add(box)
        box.pack_start(da, True, True, 0)
        box.add(label)
        box.add(bb)
        bb.add(b_close)
        da.connect('draw', self.draw)
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(b'''
        * { color: #ff0077;
        background-color: #ffffff }
        ''')
        style_context = self.get_style_context().add_provider(style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.show_all()

        self.inner_label = Gtk.Label(label='I’m inside!')

    def draw(self, widget, context):
        # il = self.inner_label
        # rectangle = Gdk.Rectangle()
        # rectangle.height = 100
        # rectangle.width = 100
        # il.size_allocate(rectangle)
        # il.do_draw(self, context)
        # return
        c = context
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        c.set_source_rgb(1, 1, 1)
        c.paint()
        step = (w - 20) / 10
        for i in range(10):
            startx = 10 + i*step
            endx = startx + step
            color = (1/9) * i
            c.set_source_rgb(color, color, color)
            c.move_to(startx, 10)
            c.line_to(endx, 10)
            c.line_to(endx, 100)
            c.line_to(startx, 100)
            c.fill()

w = TestPattern()
Gtk.main()