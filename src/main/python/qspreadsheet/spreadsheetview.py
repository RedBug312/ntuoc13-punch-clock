#!/usr/bin/env python3
from PyQt5.QtWidgets import QTableView, QFrame, QHBoxLayout

from .mixins import DropableWidget


class SpreadSheetView(QTableView, DropableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

    def isFileDropable(self, url):
        return url.endswith('.xlsx')


class SpreadSheetFrame(QFrame, DropableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.placeholder = QFrame()
        self.view = QTableView()

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.placeholder)
        layout.addWidget(self.view)
        self.setLayout(layout)
        self.overlay()

    def overlay(self):
        self.placeholder.show()
        self.view.hide()

    def display(self):
        self.placeholder.hide()
        self.view.show()

    def isFileDropable(self, url):
        return url.endswith('.xlsx')
