#!/usr/bin/python3

import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

class TestContainer(Gtk.Container):
    __gtype_name__ = "TestContainer"

    def __init__(self, *args, **kwargs):
        self.children = []
        super().__init__()

    def do_add(self, widget):
        self.children.append(widget)
        widget.set_parent(self)

    def do_forall(self, include_internals, callback, *callback_parameters):
        print(f"do_forall({include_internals}, {callback}, {callback_parameters})) self = {id(self):x}")
        for widget in self.children:
            callback(widget, *callback_parameters)

    def do_get_request_mode(self):
        print("do_get_request_mode()")
        return(Gtk.SizeRequestMode.CONSTANT_SIZE)

    def do_get_preferred_height(self):
        print("do_get_preferred_height()")
        result = (50, 50)
        return(result)

    def do_get_preferred_width(self):
        print("do_get_preferred_width()")
        min_width = 0
        nat_width = 0

        for widget in self.children:
            child_min_width, child_nat_width = widget.get_preferred_width()
            min_width += child_min_width
            nat_width += child_nat_width

        return (min_width, nat_width)

    def do_size_allocate(self, allocation):
        print("do_size_allocate()")
        child_allocation = Gdk.Rectangle()

        self.set_allocation(allocation)
        print('get_has_window()', self.get_has_window())

        if self.get_has_window():
            if self.get_realized():
                self.get_window().move_resize(allocation.x, allocation.y, allocation.width, allocation.height)

        for widget in self.children:
            if widget.get_visible():
                min_size, nat_size = widget.get_preferred_size()

                child_allocation.x = 0
                child_allocation.y = 0

                if not widget.get_has_window():
                    child_allocation.x = child_allocation.x + allocation.x
                    child_allocation.y = child_allocation.x + allocation.x

                child_allocation.width = min_size.width
                child_allocation.height = min_size.height

                widget.size_allocate(child_allocation)

    def do_realize(self):
        print("do_realize()")
        allocation = self.get_allocation()
        
        attr = Gdk.WindowAttr()
        attr.window_type = Gdk.WindowType.CHILD
        attr.x = allocation.x
        attr.y = allocation.y
        attr.width = allocation.width
        attr.height = allocation.height
        attr.visual = self.get_visual()
        attr.event_mask = self.get_events() | Gdk.EventMask.EXPOSURE_MASK
        
        WAT = Gdk.WindowAttributesType
        mask = WAT.X | WAT.Y | WAT.VISUAL
        
        window = Gdk.Window(self.get_parent_window(), attr, mask);
        window.set_decorations(0)
        self.set_window(window)
        self.register_window(window)
        self.set_realized(True)

    def do_draw(self, cr):
        allocation = self.get_allocation()
        Gtk.render_background(self.get_style_context(), cr, 0, 0, allocation.width, allocation.height)

        for widget in self.children:
            self.propagate_draw(widget, cr)

class TestWindow(Gtk.Window):
    __gtype_name__ = "TestWindow"
    def __init__(self):
        Gtk.Window.__init__(self, title="GTK3 PyGObject Custom Container Test")

        label = Gtk.Label(label = "Text1")

        print('test_window.get_has_window():', self.get_has_window())
        self.area = TestContainer()
        print('test_container.get_has_window():', self.area.get_has_window())
        self.area.add(label)
        self.area.add(Gtk.Label(label='Text2'))
        self.add(self.area)
        print('test_container.get_has_window() [added]:', self.area.get_has_window())
        self.show_all()

    def _on_quit(self, widget, event):
        Gtk.main_quit()


MainWindow = TestWindow()
MainWindow.connect("delete-event", MainWindow._on_quit)
MainWindow.show_all()
print(MainWindow.area.child_type())
Gtk.main()
