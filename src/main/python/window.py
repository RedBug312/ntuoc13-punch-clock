#!/usr/bin/env python3
import re
import pypugjs
from datetime import date, datetime
from inspect import cleandoc
from PyQt5 import uic
from PyQt5.QtCore import Qt, QTime, pyqtSlot as slot
from PyQt5.QtGui import QColor, QFont, QPalette, QFocusEvent
from PyQt5.QtWidgets import QMainWindow, QFileDialog, QAbstractItemView, QTableView, QFrame


LATEST_COLOR  = QColor(240, 198, 116, 50)
BARCODE_COLOR = QColor(178, 148, 187, 50)
NFCCODE_COLOR = QColor(138, 190, 183, 50)
UNFOCUS_COLOR = QColor(204, 102, 102, 50)


class MainWindow(QMainWindow):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context

        placeholder, tableview = QFrame(), QTableView()
        uic.loadUi(context.ui, self)
        uic.loadUi(context.uiPlaceholder, placeholder)

        placeholder.uiIconLbl.setPixmap(context.pixmapExcel)
        placeholder.uiTextLbl.setText('尚未開啟簽到名單')
        tableview.setModel(context.timesheet)
        tableview.setTabKeyNavigation(False)
        tableview.setSelectionMode(QAbstractItemView.NoSelection)

        self.uiDeadlineTime.setTime(QTime.currentTime())
        self.uiTimesheetFrame.setPlaceholder(placeholder)
        self.uiTimesheetFrame.setView(tableview)
        self.uiTimesheetFrame.overlay()

        self.connects = [sig.connect(slt) for sig, slt in {
            self.uiFileOpenBtn.clicked:         self.openXlsx,
            self.uiFileSaveBtn.clicked:         self.saveXlsx,
            self.uiInputEdit.returnPressed:     self.scanCard,
            self.uiBarColumnSpn.valueChanged:   lambda: self.updateSpreadSheet(4),
            self.uiNfcColumnSpn.valueChanged:   lambda: self.updateSpreadSheet(4),
            self.uiInputEdit.focus:             lambda x: self.focusWarn(x),
            self.uiPanelChk.stateChanged:       lambda x: context.panel.setVisible(x == Qt.Checked),
            self.uiTimesheetFrame.dropped:      lambda x: self.openXlsx(x),
            self.uiTotalSpn.valueChanged:       lambda x: self.uiPunchStatProg.setMaximum(x),
        }.items()]

    @slot(QFocusEvent)
    def focusWarn(self, focus):
        panel = self.context.panel
        palette = self.uiInputEdit.style().standardPalette()
        if focus.gotFocus():
            panel.setFailMsg('回到焦點', focus.reason())
        else:
            panel.setFailMsg('失去焦點', focus.reason())
            palette.setColor(QPalette.Base, UNFOCUS_COLOR.lighter())
        self.uiInputEdit.setPalette(palette)

    @slot()
    @slot(str)
    def openXlsx(self, xlsx=None):
        timesheet = self.context.timesheet
        if xlsx is None:
            dialog = QFileDialog()
            dialog.setAcceptMode(QFileDialog.AcceptOpen)
            dialog.setFileMode(QFileDialog.ExistingFile)
            dialog.setNameFilter('Spreadsheets (*.xlsx)')
            if not dialog.exec_():
                return False
            xlsx = dialog.selectedFiles()[0]
            # xlsx = 'oc13.xlsx'
        timesheet.open(xlsx)
        # View
        self.uiTimesheetFrame.display()
        self.uiInputEdit.setDisabled(False)
        self.uiInputEdit.setFocus()
        self.uiDeadlineTime.setDisabled(False)
        self.uiFileSaveBtn.setDisabled(False)
        self.updateSpreadSheet()
        # Spinbox backgrounds
        palette = self.uiBarColumnSpn.palette()
        palette.setColor(QPalette.Base, BARCODE_COLOR.lighter())
        self.uiBarColumnSpn.setPalette(palette)
        palette = self.uiNfcColumnSpn.palette()
        palette.setColor(QPalette.Base, NFCCODE_COLOR.lighter())
        self.uiNfcColumnSpn.setPalette(palette)
        self.statusbar.showMessage('載入 %d 列資料。' % timesheet.rowCount())

    @slot()
    @slot(str)
    def saveXlsx(self, xlsx=None):
        timesheet = self.context.timesheet
        if xlsx is None:
            dialog = QFileDialog()
            dialog.setAcceptMode(QFileDialog.AcceptSave)
            dialog.setFileMode(QFileDialog.AnyFile)
            dialog.setNameFilter('Spreadsheets (*.xlsx)')
            if not dialog.exec_():
                return False
            xlsx = dialog.selectedFiles()[0]
            # xlsx = 'output.xlsx'
        if not xlsx.endswith('.xlsx'):
            xlsx += '.xlsx'
        timesheet.save(xlsx)

    @slot()
    def scanCard(self):
        timesheet = self.context.timesheet
        panel = self.context.panel
        scan = self.uiInputEdit.text()
        self.uiInputEdit.clear()
        # Update spreadsheet by scanned
        deadline_time = self.uiDeadlineTime.time().toPyTime()
        deadline = datetime.combine(date.today(), deadline_time)
        if re.fullmatch(r'[A-Za-z]\d{2}\w\d{5}', scan):  # manually inputed
            matches = timesheet.punch(self.uiBarColumnSpn.value(), scan.upper(), deadline)
        elif re.fullmatch(r'[A-Za-z]\d{2}\w\d{6}', scan):  # scan barcode
            matches = timesheet.punch(self.uiBarColumnSpn.value(), scan[:-1].upper(), deadline)
        elif re.fullmatch(r'\d{10}', scan):  # scan rfc code
            if self.uiOverwriteChk.isChecked():
                timesheet.fillCard(self.uiNfcColumnSpn.value(), scan)
            else:
                matches = timesheet.punch(self.uiNfcColumnSpn.value(), scan, deadline)
        else:
            panel.setFailMsg(scan, '號碼格式錯誤')
            timesheet.latest_person = None
            return
        # Highlight latest checked-in one
        # self.lateTimeEdit.setDisabled(True)
        self.uiPunchStatProg.setValue(sum(timesheet.df.iloc[1:].checked))
        print(matches)
        if not matches.empty:
            row = matches.index[0] + 1
            timesheet.updateRange('latest', (row, row), (1, timesheet.columnCount()), LATEST_COLOR)
            focus = timesheet.index(row, 0)
            self.uiTimesheetFrame.view().scrollTo(focus, QAbstractItemView.PositionAtCenter)
            panel.setOkayMsg(matches, deadline)
        else:
            panel.setFailMsg(scan, '號碼不存在')
            timesheet.latest_person = None

    @slot(int)
    def updateSpreadSheet(self, flags=0b1111):
        timesheet = self.context.timesheet
        # Update order determined by the spinboxes read/write operations
        if flags & 0b0001:  # shape of spreadsheet
            cols = timesheet.columnCount()
            self.uiBarColumnSpn.setMaximum(cols)
            self.uiNfcColumnSpn.setMaximum(cols)
            rows = timesheet.rowCount()
            self.uiTotalSpn.setMaximum(rows - 1)
            self.uiTotalSpn.setValue(rows - 1)
        if flags & 0b0010:  # columnhead of spreadsheet
            pass
        if flags & 0b0100:  # ranges in spreadsheet
            rows = 2, timesheet.rowCount()
            cols_bar = (self.uiBarColumnSpn.value(), ) * 2
            cols_nfc = (self.uiNfcColumnSpn.value(), ) * 2
            timesheet.updateRange('barcode', rows, cols_bar, BARCODE_COLOR)
            timesheet.updateRange('nfccode', rows, cols_nfc, NFCCODE_COLOR)


class PanelWindow(QMainWindow):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        uic.loadUi(context.uiPanel, self)

        sans = QFont('IPAexGothic')
        sans.insertSubstitutions('sans', ['Noto Sans CJK TC', 'Microsoft YaHei'])
        sans.setStyleStrategy(QFont.PreferAntialias)
        self.setFont(sans)

    def setFailMsg(self, scan, reason):
        pug = cleandoc(f"""
            div(align='center' style='font-size:36pt; color:#2E3436;')
              p 掃描條碼失敗
              p(style='font-size:18pt; color:#888A85;') {reason}：{scan}
        """)
        html = pypugjs.simple_convert(pug)
        self.uiInfoLbl.setText(html)

    def setOkayMsg(self, matches, deadline):
        late_mins = int((matches.iloc[0, 2] - deadline).total_seconds() / 60)
        informs = matches.iloc[0, 3:6].to_dict()
        pug = cleandoc(f"""
            div(align='center' style='font-size:36pt; color:#2E3436;')
              table
                each key, val in {list(informs.items())}
                  tr
                    td(align='right')= key + '：'
                    td= val
              if {late_mins} <= 5
                p(style='color:#4E9A06') 準時簽到
              else
                p(style='color:#A40000') 遲到 {late_mins} 分鐘
        """)
        html = pypugjs.simple_convert(pug)
        self.uiInfoLbl.setText(html)
