#!/usr/bin/python3

import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

class TestContainer(Gtk.Container):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.children = []
        self.set_has_window(False)

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
        self.set_allocation(allocation)

        child_allocation = Gdk.Rectangle()
        child_allocation.x = allocation.x
        child_allocation.y = allocation.y + 30

        for widget in self.children:
            if widget.get_visible():
                min_size, nat_size = widget.get_preferred_size()
                child_allocation.width = min_size.width
                child_allocation.height = min_size.height

                widget.size_allocate(child_allocation)
                child_allocation.x += child_allocation.width - 10

    def do_draw(self, cr):
        print('draw()')
        allocation = self.get_allocation()
        Gtk.render_background(self.get_style_context(), cr, 0, 0, allocation.width, allocation.height)

        for widget in self.children:
            self.propagate_draw(widget, cr)

class TestWindow(Gtk.Window):
    __gtype_name__ = "TestWindow"
    def __init__(self):
        Gtk.Window.__init__(self, title="GTK3 PyGObject Custom Container Test")
        self.area = TestContainer()
        self.area.add(Gtk.Label(label = "Text1"))
        self.area.add(Gtk.Label(label='Text2'))
        self.add(self.area)
        self.show_all()

    def _on_quit(self, widget, event):
        Gtk.main_quit()


if __name__ == '__main__':
    MainWindow = TestWindow()
    MainWindow.connect("delete-event", MainWindow._on_quit)
    MainWindow.show_all()
    Gtk.main()
