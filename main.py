import sys
import os
import shutil
import re
import datetime
import time

from send2trash import send2trash

from pathlib import Path

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, \
                            QInputDialog, QTreeView, QWidget, QVBoxLayout, \
                            QLabel, QLineEdit, QHBoxLayout, QListWidget
from PyQt5.QtCore import QDir, Qt, QThread, pyqtSignal

from ui import main


class SearchResults(QWidget):
    clicked = pyqtSignal(str)

    def __init__(self, filename, rootpath):
        super().__init__()

        self.list_view = QListWidget()

        self.list_view.itemClicked.connect(self.selected)
        self.setMinimumWidth(1000)
        vbox = QVBoxLayout()
        vbox.addWidget(self.list_view)
        self.setLayout(vbox)

        self.search_worker = Searcher(filename, rootpath)
        self.search_worker.found.connect(self.add)
        self.search_worker.finished.connect(self.finished)
        self.search_worker.start()

    def add(self, item):
        self.list_view.addItem(item.replace('\\', '/'))

    def selected(self, item):
        self.clicked.emit(item.text())

    def finished(self):
        info = QMessageBox(self)
        info.setIcon(QMessageBox.Information)
        info.setWindowTitle("Error")
        info.setText("Search ended")
        info.show()

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.search_worker.terminate()


class AttributeWindow(QWidget):
    def __init__(self, file, filesize):
        super().__init__()
        self.filename = file.name
        self.filepath = file
        self.filesize = filesize
        self.init_vars()
        self.init_ui()

    def init_vars(self):
        stats = self.filepath.stat()
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

        modification_date_string = datetime.datetime. \
            fromtimestamp(self.modification_date).strftime("%Y-%m-%d %H:%M:%S")
        access_date_string = datetime.datetime. \
            fromtimestamp(self.access_date).strftime("%Y-%m-%d %H:%M:%S")

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
            for f in files:
                if str(f).startswith(self.name):
                    self.found.emit(path)
        self.finished.emit()


def get_size(filepath):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(filepath):
        for f in filenames:
            fp = Path(dirpath) / Path(f)
            if not fp.is_symlink():
                try:
                    total_size += fp.stat().st_size
                except FileNotFoundError:
                    continue
    return total_size


class MyWidget(QMainWindow, main.Ui_MainWindow):

    def __init__(self):
        super().__init__()
        self.cut_flag = False
        self.size_worker = None
        self.setupUi(self)
        self.hidden = False
        self.copy_this = set()
        self.setAcceptDrops(True)
        self.actionBack.triggered.connect(self.go_back)
        self.actionHome.triggered.connect(self.home_dir)
        self.actionShowHidden.triggered.connect(self.show_hid)
        self.actionSearch.triggered.connect(self.file_search)
        self.lineEdit.returnPressed.connect(self.goto)
        self.treeView.setAcceptDrops(True)
        self.treeView.setDropIndicatorShown(True)

        self.model = QtWidgets.QFileSystemModel()
        self.model.setRootPath((QtCore.QDir.rootPath()))
        self.model.setReadOnly(False)

        self.treeView.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.treeView.customContextMenuRequested.connect(self.cont_menu)
        self.treeView.doubleClicked.connect(self.open_file)
        self.treeView.viewport().installEventFilter(self)
        self.treeView.setModel(self.model)
        self.treeView. \
            setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.treeView.setDragDropMode(QTreeView.InternalMove)
        self.treeView.setSelectionMode(QTreeView.ExtendedSelection)
        self.treeView.sortByColumn(0, QtCore.Qt.SortOrder(0))
        self.treeView.setColumnWidth(0, 200)
        self.treeView.setSortingEnabled(True)

        self.comboBox.activated.connect(self.path_changer)

    def click(self, file):
        self.treeView.setRootIndex(self.model.index(file))
        self.lineEdit.setText(file)
        self.set_path(file)
        self.search_results.close()

    def file_search(self):
        index = self.treeView.rootIndex()
        rootpath = self.model.filePath(index)
        if rootpath == "":
            self.show_msg("Warning", "Choose disk to look for file!").show()
            return
        s, search = QInputDialog.getText(self, "Search", "Input", text="")
        if search:
            self.search_results = SearchResults(s, rootpath)
            self.search_results.show()
            self.search_results.clicked.connect(self.click)

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
        elif Path(self.model.filePath(index[0])).name == "":
            change = menu.addAction("Change name")
            _open = menu.addAction("Open")
            attributes = menu.addAction("Attributes")
            change.triggered.connect(self.change_name)
            _open.triggered.connect(self.open_file)
            attributes.triggered.connect(self.show_atts)
        else:
            file = Path(self.model.filePath(index[0]))
            _open = menu.addAction("Open")
            change = menu.addAction("Change name")
            delete = menu.addAction("Delete")
            recycle = menu.addAction("Add to bin")
            copy = menu.addAction("Copy")
            cut = menu.addAction("Cut")
            attributes = menu.addAction("Attributes")
            arc = menu.addAction("Archive")
            if file.suffix == ".zip":
                unpack = menu.addAction("Unpack")
                unpack.triggered.connect(self.unpack)
            recycle.triggered.connect(self.add_to_bin)
            cut.triggered.connect(self.cut)
            arc.triggered.connect(self.archive)
            copy.triggered.connect(self.copy)
            attributes.triggered.connect(self.show_atts)
            delete.triggered.connect(self.delete_selected)
            _open.triggered.connect(self.open_file)
            change.triggered.connect(self.change_name)
        cursor = QtGui.QCursor()
        menu.exec_(cursor.pos())

    def open_file(self):
        index = self.treeView.selectedIndexes()
        file_path = self.model.filePath(index[0])
        self.treeView.clearSelection()
        if Path(file_path).is_file():
            os.startfile(file_path)
        if Path(file_path).is_dir():
            self.treeView.setRootIndex(index[0])
            self.lineEdit.setText(file_path)
            self.set_path(file_path)

    def set_path(self, path):
        self.treeView.clearSelection()
        path_list = [x for x in path.split("/") if x != ""]
        self.comboBox.clear()
        self.comboBox.addItems(path_list)
        self.comboBox.setCurrentText(path_list[len(path_list) - 1])

    def goto(self):
        path = self.lineEdit.text()
        if Path(path).exists():
            self.treeView.setRootIndex(self.model.index(path))
            self.set_path(path)
        else:
            self.show_msg("Error", "Wrong path!").show()

    def path_changer(self):
        self.treeView.clearSelection()
        path_l = [self.comboBox.itemText(i)
                  for i in range(self.comboBox.currentIndex() + 1)]
        path = '/'.join(path_l)
        self.lineEdit.setText(path)
        self.treeView.setRootIndex(self.model.index(path))

    def go_back(self):
        self.treeView.clearSelection()
        index = self.model.parent(self.treeView.rootIndex())
        self.treeView.setRootIndex(index)
        self.lineEdit.setText(self.model.filePath(index))
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
            self.show_msg("Error", "Choose one item").show()
            return
        self.treeView.edit(index[0])

    def new_dir(self):
        index = self.treeView.rootIndex()
        path = Path(self.model.filePath(index))
        i, filled = QInputDialog. \
            getText(self, "Input name", "Input", text="New folder")
        if filled:
            if i == "" or i == "." or \
                    i == ".." or re.match(r'.*[<>:"/\\|?*].*', str(i)):
                self.show_msg("Error", "Invalid name!").show()
            else:
                (path / Path(i)).mkdir(exist_ok=True)

    def new_file(self):
        index = self.treeView.rootIndex()
        path = Path(self.model.filePath(index))
        i, filled = QInputDialog. \
            getText(self, "Input name", "Input", text="New file")
        if filled:
            if i == "" or i == "." or \
                    i == ".." or re.match(r'.*[<>:"/\\|?*].*', str(i)):
                self.show_msg("Error", "Invalid name!").show()
            elif str(path) == "C:\\":
                self.show_msg("Error", "Can't create file here!").show()
            else:
                (path / Path(i)).touch(exist_ok=True)

    def delete_selected(self):
        index = self.treeView.selectedIndexes()
        for i in index:
            self.model.remove(i)

    def show_hid(self):
        if not self.hidden:
            self.model.setFilter(QDir.NoDot | QDir.NoDotDot |
                                 QDir.Hidden | QDir.AllDirs | QDir.Files)
            self.hidden = True
        else:
            self.model.setFilter(QDir.NoDot | QDir.NoDotDot |
                                 QDir.AllDirs | QDir.Files)
            self.hidden = False

    def copy(self):
        self.copy_this.clear()
        indexes = self.treeView.selectedIndexes()
        for i in indexes:
            self.copy_this.add(self.model.filePath(i))

    def cut(self):
        self.copy()
        self.cut_flag = True

    def add_to_bin(self):
        index = self.treeView.selectedIndexes()
        files_to_delete = set(self.model.filePath(x) for x in index)
        for i in files_to_delete:
            send2trash(Path(i))

    def paste(self):
        index = self.treeView.rootIndex()
        try:
            for i in self.copy_this:
                file_to_copy = Path(i)
                if not file_to_copy.exists():
                    self.show_msg("Error", "File not exists!").show()
                    continue
                path = self.model.filePath(index)
                if file_to_copy.is_dir():
                    path = path + f"/{file_to_copy.name}"
                    if Path(path).exists():
                        path += " - copy at " + str(round(time.time() * 1000))
                    shutil.copytree(file_to_copy, path)
                else:
                    if Path(path + '/' + file_to_copy.name).exists():
                        path = path \
                               + '/' + file_to_copy.stem + " - copy" \
                               + file_to_copy.suffix
                    shutil.copy2(file_to_copy, path)
                if self.cut_flag:
                    if file_to_copy.is_dir():
                        shutil.rmtree(file_to_copy)
                    else:
                        file_to_copy.unlink()
            self.cut_flag = False
        except PermissionError:
            self.show_msg("Warning", "Run as admin to do that").show()

    def show_msg(self, title, text):
        msg = QMessageBox(self)
        if title == "Warning":
            msg.setIcon(QMessageBox.Warning)
        elif title == "Error":
            msg.setIcon(QMessageBox.Critical)
        elif title == "Info":
            msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle(title)
        msg.setText(text)
        return msg

    def show_atts(self):
        if self.size_worker is not None:
            self.size_worker.terminate()
        index = self.treeView.selectedIndexes()
        self.file = Path(self.model.filePath(index[0]))
        self.size_worker = SizeWorker(self.file)
        self.size_worker.finished.connect(self.report)
        self.size_worker.start()
        self.atts_win = self.show_msg("Info", "Calculating size...")
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
            file = file.parent / Path("zip")
            for i in index:
                files_set.add(self.model.filePath(i))
            for i in files_set:
                if Path(i).is_dir():
                    shutil.copytree(i, file / Path(i).name)
                else:
                    shutil.copy2(i, file)
        os.chdir(file.parent)
        i, filled = QInputDialog. \
            getText(self, "Input name", "Input", text=file.stem)
        if filled:
            if i == "" or i == "." or \
                    i == ".." or re.match(r'.*[<>:"/\\|?*].*', str(i)):
                self.show_msg("Error", "Invalid name").show()
            elif (file.parent / Path(i + ".zip")).exists():
                self.show_msg("Error", "Already exists!").show()
            else:
                shutil.make_archive(i, "zip", file.parent, file.name)
        if len(index) > 4:
            shutil.rmtree(file)

    def unpack(self):
        index = self.treeView.selectedIndexes()
        file = Path(self.model.filePath(index[0]))
        os.chdir(file.parent)
        i, filled = QInputDialog. \
            getText(self, "Input name", "Input", text=file.stem)
        if filled:
            if i == "" or i == "." or i == ".." or \
                    re.match(r'.*[<>:"/\\|?*].*', str(i)):
                self.show_msg("Error", "Invalid name").show()
            elif (file.parent / Path(i)).exists():
                self.show_msg("Error", "Already exists!").show()
            else:
                shutil.unpack_archive(file, i)

    def eventFilter(self, obj, event):
        if (
                obj is self.treeView.viewport() and
                event.type() == QtCore.QEvent.MouseButtonPress
        ):
            ix = self.treeView.indexAt(event.pos())
            if not ix.isValid():
                self.treeView.clearSelection()
        return super(MyWidget, self).eventFilter(obj, event)

    def keyPressEvent(self, event):
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

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            self.copy_this.add(url.toLocalFile())
            self.paste()
        return super().dropEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = MyWidget()
    ex.show()
    sys.exit(app.exec_())
