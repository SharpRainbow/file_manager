import os
import shutil
import sys
import re
import time
from pathlib import Path

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QInputDialog, QTreeView
from PyQt5.QtCore import QDir

from ui import main


class MyWidget(QMainWindow, main.Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.hidden = False
        self.copy_this = set()
        self.setAcceptDrops(True)
        self.actionBack.triggered.connect(self.go_back)
        self.actionHome.triggered.connect(self.home_dir)
        self.actionShowHidden.triggered.connect(self.show_hid)

        self.model = QtWidgets.QFileSystemModel()
        self.model.setRootPath((QtCore.QDir.rootPath()))
        self.model.setReadOnly(False)

        self.treeView.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.treeView.customContextMenuRequested.connect(self.cont_menu)
        self.treeView.doubleClicked.connect(self.open_file)
        self.treeView.viewport().installEventFilter(self)
        self.treeView.setModel(self.model)
        self.treeView.setDragDropMode(QTreeView.InternalMove)
        self.treeView.setSelectionMode(QTreeView.ExtendedSelection)
        self.treeView.sortByColumn(0, QtCore.Qt.SortOrder(0))
        self.treeView.setColumnWidth(0, 200)
        self.treeView.setSortingEnabled(True)

        self.lineEdit.returnPressed.connect(self.goto)
        self.comboBox.activated.connect(self.path_changer)

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
            _open = menu.addAction("Open")
            change = menu.addAction("Change name")
            delete = menu.addAction("Delete")
            copy = menu.addAction("Copy")
            arc = menu.addAction("Archive")
            unpack = menu.addAction("Unpack")
            unpack.triggered.connect(self.unpack)
            arc.triggered.connect(self.archive)
            copy.triggered.connect(self.copy)
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
        file = Path(self.model.filePath(index[0]))
        i, edited = QInputDialog.getText(self, "Change name", "Input", text=file.name)
        if edited:
            if i == "" or i == "." or i == ".." or re.match(r'.*[<>:"/\\|?*].*', str(i)):
                self.show_msg("Error", "Invalid name!")
            elif os.path.exists(str(file.parent) + '/' + i):
                self.show_msg("Error", "Already exists!")
            else:
                file.rename(self.lineEdit.text() + "/" + i)

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
