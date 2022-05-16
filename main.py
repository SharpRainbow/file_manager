import sys
import os
import shutil
import re

import datetime
import time
from pathlib import Path

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QInputDialog, QTreeView, QWidget, QVBoxLayout, \
    QLabel, QLineEdit, QHBoxLayout, QListWidget
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtCore import QThread, pyqtSignal

from ui import main


class SearchResults(QWidget):
    clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.list_view = QListWidget()

        self.list_view.itemClicked.connect(self.selected)
        self.setMinimumWidth(1000)
        vbox = QVBoxLayout()
        vbox.addWidget(self.list_view)
        self.setLayout(vbox)

    def add(self, item):
        self.list_view.addItem(item)

    def selected(self, item):
        self.clicked.emit(item.text())

    def finished(self):
        info = QMessageBox(self)
        info.setIcon(QMessageBox.Information)
        info.setWindowTitle("Error")
        info.setText("Search ended")
        info.show()


class AttributeWindow(QWidget):
    def __init__(self, file, filesize):
        super().__init__()
        self.filename = file.name
        self.filepath = file
        self.filesize = filesize
        self.init_vars()
        self.init_ui()

    def init_vars(self):
        stats = os.stat(self.filepath)
        self.modification_date = stats.st_mtime
        self.access_date = stats.st_atime

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.setWindowTitle(self.filename)
        filesize_label = QLabel("Size:")
        filesize_real = format(self.filesize / 1024, '.2f') + " KB"
        if self.filesize > 1048576:
            filesize_real = format(self.filesize / 1048576, '.2f') + " MB"
        if self.filesize < 1024:
            filesize_real = str(self.filesize) + " B"
        filesize_value = QLineEdit(filesize_real)
        filesize_value.setEnabled(False)
        first_row = QHBoxLayout()
        first_row.addWidget(filesize_label)
        first_row.addWidget(filesize_value)
        self.layout.addLayout(first_row)

        modification_date_string = datetime.datetime.fromtimestamp(self.modification_date).strftime('%Y-%m-%d %H:%M:%S')
        access_date_string = datetime.datetime.fromtimestamp(self.access_date).strftime('%Y-%m-%d %H:%M:%S')

        modification_date_label = QLabel("Last Modified:")
        modification_date_value = QLineEdit(modification_date_string)
        modification_date_value.setEnabled(False)
        second_row = QHBoxLayout()
        second_row.addWidget(modification_date_label)
        second_row.addWidget(modification_date_value)
        self.layout.addLayout(second_row)

        access_date_label = QLabel("Last Accessed:")
        access_date_value = QLineEdit(access_date_string)
        access_date_value.setEnabled(False)
        third_row = QHBoxLayout()
        third_row.addWidget(access_date_label)
        third_row.addWidget(access_date_value)
        self.layout.addLayout(third_row)


class SizeWorker(QThread):
    finished = pyqtSignal(float)

    def __init__(self, file):
        super(SizeWorker, self).__init__()
        self.file = file

    def run(self) -> None:
        size = 0
        if self.file.is_file():
            size = self.file.stat().st_size
        elif self.file.is_dir():
            size = round(get_size(self.file), 3)
        self.finished.emit(size)


class Searcher(QThread):
    found = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, name, root):
        super(Searcher, self).__init__()
        self.name = name
        self.root = root

    def run(self) -> None:
        for path, dirs, files in os.walk(self.root):
            for d in dirs:
                if self.name == d:
                    self.found.emit(path)
                    print(path)
            for f in files:
                if str(f).startswith(self.name):
                    self.found.emit(path)
                    print(path)
        self.finished.emit()


def get_size(filepath):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(filepath):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                try:
                    total_size += os.path.getsize(fp)
                except FileNotFoundError:
                    continue
    return total_size


class MyWidget(QMainWindow, main.Ui_MainWindow):
    keyPressed = QtCore.pyqtSignal(QtCore.QEvent)

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.hidden = False
        self.copy_this = set()
        self.setAcceptDrops(True)
        self.actionBack.triggered.connect(self.go_back)
        self.actionHome.triggered.connect(self.home_dir)
        self.actionShowHidden.triggered.connect(self.show_hid)
        self.actionSearch.triggered.connect(self.file_search)
        self.lineEdit.returnPressed.connect(self.goto)
        self.keyPressed.connect(self.on_key)
        self.treeView.setAcceptDrops(True)
        self.treeView.setDropIndicatorShown(True)
        self.info()

        self.model = QtWidgets.QFileSystemModel()
        self.model.setRootPath((QtCore.QDir.rootPath()))
        self.model.setReadOnly(False)

        self.treeView.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.treeView.customContextMenuRequested.connect(self.cont_menu)
        self.treeView.doubleClicked.connect(self.open_file)
        self.treeView.viewport().installEventFilter(self)
        self.treeView.setModel(self.model)
        self.treeView.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.treeView.setDragDropMode(QTreeView.InternalMove)
        self.treeView.setSelectionMode(QTreeView.ExtendedSelection)
        self.treeView.sortByColumn(0, QtCore.Qt.SortOrder(0))
        self.treeView.setColumnWidth(0, 200)
        self.treeView.setSortingEnabled(True)

        self.lineEdit.returnPressed.connect(self.goto)
        self.comboBox.activated.connect(self.path_changer)

    def finish(self):
        self.win.finished()

    def show_res(self, file):
        self.win.add(file)

    def click(self, file):
        self.treeView.setRootIndex(self.model.index(file))
        self.win.close()

    def file_search(self):
        index = self.treeView.rootIndex()
        filepath = self.model.filePath(index)
        s, search = QInputDialog.getText(self, "Search", "Input", text="")
        if search:
            self.search_worker = Searcher(s, filepath)
            self.search_worker.found.connect(self.show_res)
            self.search_worker.finished.connect(self.finish)
            self.search_worker.start()
            self.win = SearchResults()
            self.win.show()
            self.win.clicked.connect(self.click)

    def keyPressEvent(self, event):
        super(MyWidget, self).keyPressEvent(event)
        self.keyPressed.emit(event)

    def on_key(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_H:
                self.home_dir()
            if event.key() == Qt.Key_C:
                self.copy()
            if event.key() == Qt.Key_V:
                self.paste()
            if event.key() == Qt.Key_R:
                self.change_name()
            if event.key() == Qt.Key_S:
                self.file_search()
            if event.key() == Qt.Key_Left:
                self.go_back()
        if event.key() == Qt.Key_Delete:
            self.delete_selected()

    def cont_menu(self):
        menu = QtWidgets.QMenu()
        index = self.treeView.selectedIndexes()
        if len(index) == 0:
            new_dir = menu.addAction("New dir")
            new_file = menu.addAction("New file")
            paste = menu.addAction("Paste")
            new_dir.triggered.connect(self.new_dir)
            new_file.triggered.connect(self.new_file)
            paste.triggered.connect(self.paste)
        else:
            file = Path(self.model.filePath(index[0]))
            _open = menu.addAction("Open")
            change = menu.addAction("Change name")
            delete = menu.addAction("Delete")
            copy = menu.addAction("Copy")
            attributes = menu.addAction("Attributes")
            arc = menu.addAction("Archive")
            if file.suffix == '.zip':
                unpack = menu.addAction("Unpack")
                unpack.triggered.connect(self.unpack)
            arc.triggered.connect(self.archive)
            copy.triggered.connect(self.copy)
            attributes.triggered.connect(self.show_atts)
            delete.triggered.connect(self.delete_selected)
            _open.triggered.connect(self.open_file)
            change.triggered.connect(self.change_name)
        cursor = QtGui.QCursor()
        menu.exec_(cursor.pos())

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            self.copy_this.add(url.toLocalFile())
            self.paste()
        return super().dropEvent(event)

    def open_file(self):
        index = self.treeView.currentIndex()
        file_path = self.model.filePath(index)
        self.treeView.clearSelection()
        if os.path.isfile(file_path):
            os.startfile(file_path)
        if os.path.isdir(file_path):
            self.treeView.setRootIndex(self.model.index(file_path))
            self.lineEdit.setText(file_path)
            self.set_path(file_path)

    def set_path(self, path):
        path_list = [x for x in path.split("/") if x != ""]
        self.comboBox.clear()
        self.comboBox.addItems(path_list)
        self.comboBox.setCurrentText(path_list[len(path_list) - 1])

    def goto(self):
        path = self.lineEdit.text()
        if os.path.exists(path):
            self.treeView.setRootIndex(self.model.index(path))
            self.set_path(path)
        else:
            self.show_msg("Error", "Wrong path!")

    def search_goto(self, path):
        self.treeView.setRootIndex(self.model.index(path))

    def path_changer(self):
        path_l = [self.comboBox.itemText(i) for i in range(self.comboBox.currentIndex() + 1)]
        path = '/'.join(path_l)
        self.lineEdit.setText(path)
        self.treeView.setRootIndex(self.model.index(path))

    def go_back(self):
        index = self.treeView.rootIndex()
        path = self.model.filePath(self.model.parent(index))
        self.treeView.setRootIndex(self.model.index(path))
        self.lineEdit.setText(path.replace("\\", "/"))
        if self.comboBox.currentIndex() != 0:
            self.comboBox.setCurrentIndex(self.comboBox.currentIndex() - 1)

    def home_dir(self):
        self.lineEdit.clear()
        self.comboBox.clear()
        self.model = QtWidgets.QFileSystemModel()
        self.model.setRootPath((QtCore.QDir.rootPath()))
        self.treeView.setModel(self.model)

    def change_name(self):
        index = self.treeView.selectedIndexes()
        if len(index) > 4 or len(index) <= 0:
            self.show_msg("Error", "Choose one item")
            return
        self.treeView.edit(index[0])

    def new_dir(self):
        index = self.treeView.rootIndex()
        path = self.model.filePath(index)
        i, filled = QInputDialog.getText(self, "Input name", "Input", text="New folder")
        if filled:
            if i == "" or i == "." or i == ".." or re.match(r'.*[<>:"/\\|?*].*', str(i)):
                self.show_msg("Error", "Invalid name!")
            else:
                Path(path + '/' + i).mkdir(exist_ok=True)

    def new_file(self):
        index = self.treeView.rootIndex()
        path = self.model.filePath(index)
        i, filled = QInputDialog.getText(self, "Input name", "Input", text="New file")
        if filled:
            if i == "" or i == "." or i == ".." or re.match(r'.*[<>:"/\\|?*].*', str(i)):
                self.show_msg("Error", "Invalid name!")
            elif path == "C:/":
                self.show_msg("Error", "Can't create file here!")
            else:
                Path(path + '/' + i).touch(exist_ok=True)

    def delete_selected(self):
        index = self.treeView.selectedIndexes()
        for i in index:
            self.model.remove(i)
        self.treeView.clearSelection()

    def show_hid(self):
        if not self.hidden:
            self.model.setFilter(QDir.NoDot | QDir.NoDotDot | QDir.Hidden | QDir.AllDirs | QDir.Files)
            self.hidden = True
        else:
            self.model.setFilter(QDir.NoDot | QDir.NoDotDot | QDir.AllDirs | QDir.Files)
            self.hidden = False

    def copy(self):
        self.copy_this.clear()
        indexes = self.treeView.selectedIndexes()
        for i in indexes:
            self.copy_this.add(self.model.filePath(i))
        print(self.copy_this)

    def paste(self):
        index = self.treeView.rootIndex()
        try:
            for i in self.copy_this:
                file_to_copy = Path(i)
                if not file_to_copy.exists():
                    self.show_msg("Error", "File not exists!")
                    continue
                path = self.model.filePath(index)
                if os.path.isdir(i):
                    path = path + f'/{file_to_copy.name}'
                    if os.path.exists(path):
                        path += " - copy at " + str(round(time.time() * 1000))
                    shutil.copytree(i, path)
                else:
                    if os.path.exists(path + "/" + file_to_copy.name):
                        path = path \
                            + '/' + file_to_copy.stem + " - copy" \
                            + file_to_copy.suffix
                    shutil.copy2(i, path)
        except PermissionError:
            self.show_msg("Warning", "Run as admin to do that")

    def show_msg(self, title, text):
        msg = QMessageBox(self)
        if title == "Warning":
            msg.setIcon(QMessageBox.Warning)
        elif title == "Error":
            msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.show()

    def show_atts(self):
        index = self.treeView.selectedIndexes()
        self.file = Path(self.model.filePath(index[0]))
        self.size_worker = SizeWorker(self.file)
        self.size_worker.finished.connect(self.report)
        self.size_worker.start()
        self.atts_win = QMessageBox(self)
        self.atts_win.setIcon(QMessageBox.Information)
        self.atts_win.setWindowTitle("Please wait")
        self.atts_win.setText("Calculating size...")
        self.atts_win.show()

    def report(self, n):
        self.atts_win.close()
        self.atts_win = AttributeWindow(self.file, n)
        self.atts_win.show()

    def archive(self):
        index = self.treeView.selectedIndexes()
        file = Path(self.model.filePath(index[0]))
        if len(index) > 4:
            self.model.mkdir(self.treeView.rootIndex(), "zip")
            files_set = set()
            file = Path(str(file.parent) + "/zip")
            for i in index:
                files_set.add(self.model.filePath(i))
            for i in files_set:
                if os.path.isdir(i):
                    shutil.copytree(i, str(file) + "/" + Path(i).name)
                else:
                    shutil.copy2(i, file)
        os.chdir(os.path.dirname(str(file.parent) + '/'))
        i, filled = QInputDialog.getText(self, "Input name", "Input", text=file.stem)
        if filled:
            if i == "" or i == "." or i == ".." or re.match(r'.*[<>:"/\\|?*].*', str(i)):
                self.show_msg("Error", "Invalid name")
            elif os.path.exists(str(file.parent) + '/' + i + '.zip'):
                self.show_msg("Error", "Already exists!")
            else:
                shutil.make_archive(i, 'zip', file.parent, file.name)
        if len(index) > 4:
            shutil.rmtree(file)

    def unpack(self):
        index = self.treeView.selectedIndexes()
        file = Path(self.model.filePath(index[0]))
        os.chdir(os.path.dirname(str(file.parent) + '/'))
        i, filled = QInputDialog.getText(self, "Input name", "Input", text=file.stem)
        if filled:
            if i == "" or i == "." or i == ".." or re.match(r'.*[<>:"/\\|?*].*', str(i)):
                self.show_msg("Error", "Invalid name")
            elif os.path.exists(str(file.parent) + '/' + i):
                self.show_msg("Error", "Already exists!")
            else:
                shutil.unpack_archive(file, i)

    def eventFilter(self, obj, event):
        if (
                obj is self.treeView.viewport()
                and event.type() == QtCore.QEvent.MouseButtonPress
        ):
            ix = self.treeView.indexAt(event.pos())
            if not ix.isValid():
                self.treeView.clearSelection()
        return super(MyWidget, self).eventFilter(obj, event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MyWidget()
    ex.show()
    sys.exit(app.exec_())
