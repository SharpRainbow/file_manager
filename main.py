import os
import sys
from pathlib import Path

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QInputDialog
from PyQt5.QtCore import QFile

from ui import main


class MyWidget(QMainWindow, main.Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.comboBox.activated.connect(self.path_changer)
        self.treeView.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.treeView.customContextMenuRequested.connect(self.cont_menu)
        self.treeView.doubleClicked.connect(self.open_file)
        self.actionBack.triggered.connect(self.go_back)
        self.actionHome.triggered.connect(self.home_dir)
        self.lineEdit.returnPressed.connect(self.goto)
        self.info()

    def info(self):
        self.model = QtWidgets.QFileSystemModel()
        self.model.setRootPath((QtCore.QDir.rootPath()))
        self.treeView.setModel(self.model)
        self.treeView.setSortingEnabled(True)

    def cont_menu(self):
        menu = QtWidgets.QMenu()
        _open = menu.addAction("Open")
        change = menu.addAction("Change name")
        _open.triggered.connect(self.open_file)
        change.triggered.connect(self.change_name)
        cursor = QtGui.QCursor()
        menu.exec_(cursor.pos())

    def open_file(self):
        index = self.treeView.currentIndex()
        file_path = self.model.filePath(index)
        if os.path.isfile(file_path):
            os.startfile(file_path)
        if os.path.isdir(file_path):
            self.treeView.setRootIndex(self.model.index(file_path))
            self.lineEdit.setText(file_path)
            path_list = [x for x in file_path.split("/") if x != ""]
            self.comboBox.clear()
            self.comboBox.addItems(path_list)
            self.comboBox.setCurrentText(path_list[len(path_list) - 1])

    def goto(self):
        path = self.lineEdit.text()
        if os.path.exists(path):
            self.treeView.setRootIndex(self.model.index(path))
        else:
            err = QMessageBox(self)
            err.setIcon(QMessageBox.Critical)
            err.setText("Wrong path!")
            err.setWindowTitle("Error")
            err.show()

    def path_changer(self):
        path_l = [self.comboBox.itemText(i) for i in range(self.comboBox.currentIndex() + 1)]
        path = '/'.join(path_l)
        self.lineEdit.setText(path)
        self.treeView.setRootIndex(self.model.index(path))

    def go_back(self):
        path = str(Path(self.lineEdit.text()).parent)
        self.treeView.setRootIndex(self.model.index(path))

    def home_dir(self):
        self.lineEdit.clear()
        self.comboBox.clear()
        self.model = QtWidgets.QFileSystemModel()
        self.model.setRootPath((QtCore.QDir.rootPath()))
        self.treeView.setModel(self.model)

    def change_name(self):
        extension = ""
        index = self.treeView.currentIndex()
        file = QFile(self.model.filePath(index))
        pos = file.fileName()[::-1].find('/')
        filename = file.fileName()[::-1][:pos]
        i, edited = QInputDialog.getText(self, "Change name", "Input", text=filename[::-1])
        if edited:
            file.rename(self.lineEdit.text() + "/" + i)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MyWidget()
    ex.show()
    sys.exit(app.exec_())
