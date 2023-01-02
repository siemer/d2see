#!/usr/bin/python3

import gi

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk

class MyBin(Gtk.Bin):
    def __init__(self):
        super().__init__()

    def do_size_allocate(self, allocation):
        print('PARENT METHOD do_size_allocate', allocation.width)
        # if not called, `get_allocation()` in `do_draw()` will return a 1x1 rectangle
        self.set_allocation(allocation)
        # strangely required so that `do_draw()` will be called even on this class!
        self.get_child().size_allocate(allocation)

    def do_draw(self, c):
        allocation = self.get_allocation()
        print('PARENT do_draw()', allocation.width)
        self.propagate_draw(self.get_child(), c)

class MyChild(Gtk.Button):
    def __init__(self):
        super().__init__()
        self.connect('size-allocate', self.size_allocate_handler)
        self.connect('draw', self.draw_handler)

    def size_allocate_handler(self, self2, allocation):
        print('CHILD signal size-allocate', allocation.width)

    def draw_handler(self, self2, c):
        allocation = self.get_allocation()
        print('CHILD signal draw', allocation.width)

class MainWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title='d2see test pattern')
        the_child = MyChild()
        my_container = MyBin()
        my_container.add(the_child)
        self.add(my_container)
        self.show_all()

if __name__ == '__main__':
    MainWindow()
    Gtk.main()