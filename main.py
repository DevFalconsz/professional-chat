import sys
import socket
import threading
import random
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLineEdit, QPushButton, QWidget, QDialog, QLabel, QMessageBox,
    QCheckBox, QListWidget, QListWidgetItem, QInputDialog, QToolBar, QAction
)
from PyQt5.QtGui import QTextCursor
from PyQt5.QtCore import Qt, pyqtSignal, QObject

DIRECTORY_HOST = '127.0.0.1'
DIRECTORY_PORT = 5000

def register_directory(room_name, host_ip, host_port, password):
    payload = {
        "action": "register",
        "room_name": room_name,
        "host_ip": host_ip,
        "host_port": host_port,
        "password": password
    }
    try:
        with socket.create_connection((DIRECTORY_HOST, DIRECTORY_PORT), timeout=2) as s:
            s.send(json.dumps(payload).encode())
    except Exception as e:
        print(f"[register_directory] Erro: {e}")

def unregister_directory(room_name):
    payload = {"action": "unregister", "room_name": room_name}
    try:
        with socket.create_connection((DIRECTORY_HOST, DIRECTORY_PORT), timeout=2) as s:
            s.send(json.dumps(payload).encode())
    except Exception as e:
        print(f"[unregister_directory] Erro: {e}")

class DirectoryServer:
    def __init__(self):
        self.rooms = {}
        self.lock = threading.Lock()

    def start(self):
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((DIRECTORY_HOST, DIRECTORY_PORT))
        sock.listen(5)
        while True:
            client, _ = sock.accept()
            threading.Thread(target=self.handle, args=(client,), daemon=True).start()

    def handle(self, c):
        try:
            data = c.recv(4096).decode()
            req = json.loads(data)
            resp = {}
            with self.lock:
                if req["action"] == "register":
                    self.rooms[req["room_name"]] = {
                        "host_ip": req["host_ip"],
                        "host_port": req["host_port"],
                        "password": req.get("password")
                    }
                    resp["status"] = "ok"
                elif req["action"] == "unregister":
                    self.rooms.pop(req["room_name"], None)
                    resp["status"] = "ok"
                elif req["action"] == "list":
                    resp["rooms"] = self.rooms
            c.send(json.dumps(resp).encode())
        except Exception as e:
            print(f"[DirectoryServer] Erro: {e}")
        finally:
            c.close()

class ChatServerThread(threading.Thread):
    def __init__(self, ip, port, cb):
        super().__init__()
        self.ip, self.port, self.cb = ip, port, cb
        self.clients = []
        self.running = True
        self.sock = None

    def safe(self, msg):
        try:
            self.cb(str(msg))
        except:
            pass

    def run(self):
        try:
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.ip, self.port))
            s.listen(5)
            self.sock = s
            self.safe(f"[Sistema] Servidor em {self.ip}:{self.port}")
        except Exception as e:
            self.safe(f"[Erro] Servidor falhou: {e}")
            return

        while self.running:
            try:
                c, _ = s.accept()
                self.clients.append(c)
                threading.Thread(target=self.handle, args=(c,), daemon=True).start()
            except:
                break

    def handle(self, c):
        while self.running:
            try:
                d = c.recv(4096)
                if not d:
                    break
                m = d.decode()
                self.broadcast(m)
            except:
                break
        if c in self.clients:
            self.clients.remove(c)
        c.close()

    def broadcast(self, m):
        for c in list(self.clients):
            try:
                c.send(m.encode())
            except:
                self.clients.remove(c)
        if self.running:
            self.safe(m)

    def stop(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass

class ChatClientThread(threading.Thread):
    def __init__(self, ip, port, cb):
        super().__init__()
        self.ip, self.port, self.cb = ip, port, cb
        self.running = True
        self.sock = None

    def safe(self, msg):
        try:
            self.cb(str(msg))
        except:
            pass

    def run(self):
        try:
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.connect((self.ip, self.port))
            self.sock = s
            self.safe(f"[Sistema] Conectado em {self.ip}:{self.port}")
            while self.running:
                d = s.recv(4096)
                if not d:
                    break
                self.safe(d.decode())
        except Exception as e:
            self.safe(f"[Erro] Conexão falhou: {e}")
        finally:
            if self.sock:
                try:
                    self.sock.close()
                except:
                    pass

    def send(self, m):
        if self.sock:
            try:
                self.sock.send(m.encode())
            except:
                pass

    def stop(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass

class Communicator(QObject):
    updateChatSignal = pyqtSignal(str)

class LoginWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login")
        self.setFixedSize(400, 250)
        l = QVBoxLayout()
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(15)
        l.addWidget(QLabel("Usuário:"))
        self.user = QLineEdit()
        self.user.setMinimumHeight(35)
        l.addWidget(self.user)
        l.addWidget(QLabel("Senha:"))
        self.pwd = QLineEdit()
        self.pwd.setEchoMode(QLineEdit.Password)
        self.pwd.setMinimumHeight(35)
        l.addWidget(self.pwd)
        btn = QPushButton("Entrar")
        btn.setMinimumHeight(35)
        l.addWidget(btn, alignment=Qt.AlignCenter)
        self.setLayout(l)
        btn.clicked.connect(self.h)
        self.pwd.returnPressed.connect(self.h)
        self.setStyleSheet("""
            QDialog{background:#5865F2;}
            QLabel,QLineEdit,QPushButton{font:16px Arial;color:white;}
            QLineEdit{background:#404EED;border:2px solid #23272A;border-radius:5px;padding:5px;}
            QPushButton{background:#1E1F2B;border:2px solid #2A2D3E;border-radius:5px;padding:8px 15px;font-weight:bold;}
            QPushButton:hover{background:#2A2D3E;}
        """)

    def h(self):
        if not self.user.text().strip():
            QMessageBox.warning(self, "Erro", "Usuário vazio")
            return
        self.accept()

class RoomSelectionWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Seleção de Sala")
        self.setFixedSize(450, 300)
        self.details = None
        l = QVBoxLayout()
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(15)
        l.addWidget(QLabel("Escolha:"))
        b1 = QPushButton("Criar Sala")
        b2 = QPushButton("Entrar em Sala")
        l.addWidget(b1)
        l.addWidget(b2)
        b1.clicked.connect(self.c)
        b2.clicked.connect(self.j)
        self.setLayout(l)
        self.setStyleSheet("""
            QDialog{background:#5865F2;}
            QLabel,QPushButton{font:16px Arial;color:white;}
            QPushButton{background:#1E1F2B;border:2px solid #2A2D3E;border-radius:5px;padding:10px 15px;font-weight:bold;}
            QPushButton:hover{background:#2A2D3E;}
        """)

    def c(self):
        d = CreateRoomDialog()
        if d.exec() == QDialog.Accepted:
            self.details = d.get_details()
            self.accept()

    def j(self):
        d = ListRoomsDialog()
        if d.exec() == QDialog.Accepted:
            self.details = d.get_details()
            self.accept()

    def get_details(self):
        return self.details

class CreateRoomDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Criar Sala")
        self.setFixedSize(400, 250)
        l = QVBoxLayout()
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(15)
        l.addWidget(QLabel("Nome da Sala:"))
        self.room = QLineEdit()
        self.room.setMinimumHeight(35)
        l.addWidget(self.room)
        self.chk = QCheckBox("Exigir senha")
        l.addWidget(self.chk)
        self.pwd = QLineEdit()
        self.pwd.setEchoMode(QLineEdit.Password)
        self.pwd.setMinimumHeight(35)
        self.pwd.setVisible(False)
        l.addWidget(self.pwd)
        self.chk.stateChanged.connect(lambda s: self.pwd.setVisible(s == Qt.Checked))
        btn = QPushButton("Criar Sala")
        btn.setMinimumHeight(35)
        l.addWidget(btn, alignment=Qt.AlignCenter)
        btn.clicked.connect(self.h)
        self.setLayout(l)
        self.setStyleSheet("""
            QDialog{background:#5865F2;}
            QLabel,QLineEdit,QCheckBox,QPushButton{font:16px Arial;color:white;}
            QLineEdit{background:#404EED;border:2px solid #23272A;border-radius:5px;padding:5px;}
            QPushButton{background:#1E1F2B;border:2px solid #2A2D3E;border-radius:5px;padding:8px 15px;font-weight:bold;}
            QPushButton:hover{background:#2A2D3E;}
        """)

    def h(self):
        name = self.room.text().strip()
        if not name:
            QMessageBox.warning(self, "Erro", "Nome vazio")
            return
        if self.chk.isChecked() and not self.pwd.text().strip():
            QMessageBox.warning(self, "Erro", "Senha vazia")
            return
        port = random.randint(6000,7000)
        ip = socket.gethostbyname(socket.gethostname())
        pwd = self.pwd.text().strip() if self.chk.isChecked() else None
        register_directory(name, ip, port, pwd)
        self.out = {"room_name": name, "role": "host", "password": pwd, "host_ip": ip, "host_port": port}
        self.accept()

    def get_details(self):
        return self.out

class ListRoomsDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lista de Salas")
        self.setFixedSize(400, 300)
        self.sel = None
        l = QVBoxLayout()
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(15)
        self.lst = QListWidget()
        l.addWidget(self.lst)
        btn = QPushButton("Entrar")
        btn.setMinimumHeight(35)
        l.addWidget(btn, alignment=Qt.AlignCenter)
        btn.clicked.connect(self.h)
        self.setLayout(l)
        self.setStyleSheet("""
            QDialog{background:#5865F2;}
            QListWidget,QPushButton{font:16px Arial;color:white;}
            QListWidget{background:#404EED;border:2px solid #23272A;border-radius:5px;}
            QPushButton{background:#1E1F2B;border:2px solid #2A2D3E;border-radius:5px;padding:8px 15px;font-weight:bold;}
            QPushButton:hover{background:#2A2D3E;}
        """)
        self.populate()

    def populate(self):
        try:
            req = {"action": "list"}
            with socket.create_connection((DIRECTORY_HOST, DIRECTORY_PORT), timeout=2) as s:
                s.send(json.dumps(req).encode())
                data = json.loads(s.recv(4096).decode())
            for name, info in data.get("rooms", {}).items():
                disp = f"{name} - {info['host_ip']}:{info['host_port']}"
                if info.get("password"): disp += " (Senha)"
                it = QListWidgetItem(disp)
                it.setData(Qt.UserRole, {"room_name": name, **info})
                self.lst.addItem(it)
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Listagem falhou: {e}")

    def h(self):
        it = self.lst.currentItem()
        if not it:
            QMessageBox.warning(self, "Erro", "Selecione sala")
            return
        r = it.data(Qt.UserRole)
        if r.get("password"):
            txt, ok = QInputDialog.getText(self, "Senha", "Senha:", QLineEdit.Password)
            if not ok or txt != r["password"]:
                QMessageBox.warning(self, "Erro", "Senha incorreta")
                return
        r["role"] = "cliente"
        self.sel = r
        self.accept()

    def get_details(self):
        return self.sel

class MainWindow(QMainWindow):
    def __init__(self, user, room):
        super().__init__()
        self.user, self.room = user, room
        rn, role = room["room_name"], room["role"]
        self.setWindowTitle(f"{rn} ({role})")
        self.setGeometry(200, 100, 800, 600)
        self.comm = Communicator()
        self.comm.updateChatSignal.connect(self.update_chat)
        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Digite sua mensagem...")
        btn = QPushButton("Enviar")
        h = QHBoxLayout()
        h.addWidget(self.inp)
        h.addWidget(btn)
        m = QVBoxLayout()
        m.addWidget(self.chat)
        m.addLayout(h)
        c = QWidget()
        c.setLayout(m)
        self.setCentralWidget(c)
        btn.clicked.connect(self.send)
        self.inp.returnPressed.connect(self.send)
        self.create_toolbar()
        if role == "host":
            self.start_host()
        else:
            self.start_client()

    def create_toolbar(self):
        tb = QToolBar()
        self.addToolBar(tb)
        act = QAction("Sair da Sala", self)
        act.triggered.connect(self.go_back)
        tb.addAction(act)

    def update_chat(self, msg):
        self.chat.append(msg)
        self.chat.moveCursor(QTextCursor.End)

    def send(self):
        txt = self.inp.text().strip()
        if not txt:
            return
        msg = f"<b>{self.user}:</b> {txt}"
        self.inp.clear()
        if hasattr(self, "server"):
            self.server.broadcast(msg)
        else:
            self.client.send(msg)

    def start_host(self):
        ip, port = self.room["host_ip"], self.room["host_port"]
        self.server = ChatServerThread(ip, port, self.comm.updateChatSignal.emit)
        self.server.start()

    def start_client(self):
        ip, port = self.room["host_ip"], self.room["host_port"]
        self.client = ChatClientThread(ip, port, self.comm.updateChatSignal.emit)
        self.client.start()

    def go_back(self):
        if hasattr(self, "server"):
            self.server.stop()
            self.server.join()
        if hasattr(self, "client"):
            self.client.stop()
            self.client.join()
        self.close()
        dlg = RoomSelectionWindow()
        if dlg.exec() == QDialog.Accepted:
            details = dlg.get_details()
            new = MainWindow(self.user, details)
            new.show()

    def closeEvent(self, e):
        if hasattr(self, "server"):
            unregister_directory(self.room["room_name"])
            self.server.stop()
            self.server.join()
        if hasattr(self, "client"):
            self.client.stop()
            self.client.join()
        e.accept()

def start_directory_bg():
    ds = DirectoryServer()
    threading.Thread(target=ds.start, daemon=True).start()

if __name__ == "__main__":
    start_directory_bg()
    app = QApplication(sys.argv)
    lw = LoginWindow()
    if lw.exec() == QDialog.Accepted:
        user = lw.user.text().strip()
        sel = RoomSelectionWindow()
        if sel.exec() == QDialog.Accepted:
            details = sel.get_details()
            w = MainWindow(user, details)
            w.show()
            sys.exit(app.exec())
