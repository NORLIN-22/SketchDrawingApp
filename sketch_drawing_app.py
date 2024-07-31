import sys
import os
import ctypes
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QVBoxLayout, QPushButton, QWidget, QLabel, QHBoxLayout, QLineEdit, QSizePolicy, QSpacerItem
from PyQt5.QtGui import QPixmap, QImage, QTransform
from PyQt5.QtCore import QTimer, QTime, Qt, QThread, pyqtSignal

# Define ctypes constants for window placement
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010

class MonitorThread(QThread):
    window_state_changed = pyqtSignal(bool)  # Signal to notify state changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_window = None
        self.app_window = parent

    def run(self):
        while True:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd != self.active_window:
                self.active_window = hwnd
                is_minimized = ctypes.windll.user32.IsIconic(hwnd)
                self.window_state_changed.emit(is_minimized)
            self.msleep(500)  # Check every 0.5 seconds

class CustomTitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.initUI()
        self.monitor_thread = MonitorThread(self)
        self.monitor_thread.window_state_changed.connect(self.handle_window_state_change)
        self.monitor_thread.start()
        self.current_app_window = None

    def initUI(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.sticky_button = QPushButton("置顶")
        self.sticky_button.clicked.connect(self.toggle_always_on_top)
        layout.addWidget(self.sticky_button)

        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        self.setLayout(layout)

    def toggle_always_on_top(self):
        flags = self.parent_window.windowFlags()
        if flags & Qt.WindowStaysOnTopHint:
            self.parent_window.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        else:
            self.parent_window.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        self.parent_window.show()  # Update the window to apply the new flags

    def handle_window_state_change(self, is_minimized):
        if self.current_app_window:
            try:
                # Minimize or restore the SketchDrawingApp based on the state of the current active window
                if is_minimized:
                    ctypes.windll.user32.ShowWindow(self.parent_window.winId(), 6)  # Minimize
                else:
                    ctypes.windll.user32.ShowWindow(self.parent_window.winId(), 9)  # Restore
            except Exception as e:
                print(f"Error in handling window state change: {e}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Sketch Drawing App - Main')
        self.setGeometry(100, 100, 800, 600)

        self.image_paths = []
        self.timer_interval = 30000  # Default 30 seconds

        self.initUI()

    def initUI(self):
        self.setMenuWidget(CustomTitleBar(self))

        main_layout = QVBoxLayout()
        
        self.select_folder_button = QPushButton('选择文件夹')
        self.select_folder_button.clicked.connect(self.select_folder)
        main_layout.addWidget(self.select_folder_button, alignment=Qt.AlignTop)
        
        # Timer settings with buttons
        timer_layout = QHBoxLayout()
        self.timer_buttons = {
            '30s': QPushButton('30秒'),
            '45s': QPushButton('45秒'),
            '1m': QPushButton('1分钟'),
            '2m': QPushButton('2分钟'),
            '5m': QPushButton('5分钟'),
            '10m': QPushButton('10分钟')
        }

        for label, button in self.timer_buttons.items():
            button.clicked.connect(lambda _, l=label: self.set_timer_interval(l))
            timer_layout.addWidget(button)

        # Custom timer input
        self.custom_timer_input = QLineEdit()
        self.custom_timer_input.setPlaceholderText('自定义时间 (秒)')
        self.custom_timer_input.returnPressed.connect(self.set_custom_timer_interval)
        timer_layout.addWidget(self.custom_timer_input)

        main_layout.addLayout(timer_layout)
        
        self.start_button = QPushButton('开始')
        self.start_button.clicked.connect(self.start_sketch_app)
        main_layout.addWidget(self.start_button, alignment=Qt.AlignBottom)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def select_folder(self):
        print("Select folder button clicked")
        folder_path = QFileDialog.getExistingDirectory(self, '选择文件夹')
        if folder_path:
            self.image_paths = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if self.image_paths:
                self.current_index = 0

    def set_timer_interval(self, label):
        intervals = {
            '30s': 30000,
            '45s': 45000,
            '1m': 60000,
            '2m': 120000,
            '5m': 300000,
            '10m': 600000
        }
        self.timer_interval = intervals[label]
        print(f"Timer interval set to: {self.timer_interval} ms")

    def set_custom_timer_interval(self):
        text = self.custom_timer_input.text()
        try:
            seconds = int(text)
            if 0 < seconds <= 3600:  # Limit to 1 hour
                self.timer_interval = seconds * 1000
                print(f"Custom timer interval set to: {self.timer_interval} ms")
            else:
                print("请输入1到3600秒之间的有效数字。")
        except ValueError:
            print("无效输入。请输入一个数字。")

    def start_sketch_app(self):
        if self.image_paths:
            print("Starting sketch app...")
            self.sketch_app = SketchDrawingApp(self.image_paths, self.timer_interval, self)
            self.sketch_app.show()
            self.hide()
        else:
            print("请先选择包含图片的文件夹。")

class SketchDrawingApp(QMainWindow):
    def __init__(self, image_paths, timer_interval, parent):
        super().__init__()
        self.setWindowTitle('Sketch Drawing App')
        self.setGeometry(100, 100, 1000, 600)

        self.image_paths = image_paths
        self.current_index = 0
        self.timer_interval = timer_interval
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_image)
        
        self.start_time = QTime.currentTime()  # Initialize start_time

        self.parent = parent

        self.initUI()
        
        if self.image_paths:
            self.display_image(self.image_paths[self.current_index])
            self.timer.start(self.timer_interval)

    def initUI(self):
        self.setMenuWidget(CustomTitleBar(self))

        main_layout = QVBoxLayout()

        # Image display
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.image_label)

        # Timer display
        self.timer_display = QLabel()
        self.timer_display.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.timer_display)

        # Control buttons
        control_layout = QHBoxLayout()
        self.prev_button = QPushButton("上一张")
        self.prev_button.clicked.connect(self.prev_image)
        control_layout.addWidget(self.prev_button)

        self.next_button = QPushButton("下一张")
        self.next_button.clicked.connect(self.next_image)
        control_layout.addWidget(self.next_button)

        self.flip_button = QPushButton("翻转")
        self.flip_button.clicked.connect(self.flip_image)
        control_layout.addWidget(self.flip_button)

        self.rotate_button = QPushButton("旋转")
        self.rotate_button.clicked.connect(self.rotate_image)
        control_layout.addWidget(self.rotate_button)

        self.return_button = QPushButton("返回")
        self.return_button.clicked.connect(self.return_to_main)
        control_layout.addWidget(self.return_button)

        main_layout.addLayout(control_layout)
        
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.update_timer_display()

    def display_image(self, image_path):
        pixmap = QPixmap(image_path)
        self.image_label.setPixmap(pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio))

    def next_image(self):
        print("下一张图片")
        if self.image_paths:
            self.current_index = (self.current_index + 1) % len(self.image_paths)
            self.display_image(self.image_paths[self.current_index])
            self.start_time = QTime.currentTime()  # Reset start time

    def prev_image(self):
        print("上一张图片")
        if self.image_paths:
            self.current_index = (self.current_index - 1) % len(self.image_paths)
            self.display_image(self.image_paths[self.current_index])
            self.start_time = QTime.currentTime()  # Reset start time

    def flip_image(self):
        print("翻转图片")
        pixmap = self.image_label.pixmap()
        if pixmap:
            transform = QTransform().scale(-1, 1)
            flipped_pixmap = pixmap.transformed(transform)
            self.image_label.setPixmap(flipped_pixmap)

    def rotate_image(self):
        print("旋转图片")
        pixmap = self.image_label.pixmap()
        if pixmap:
            transform = QTransform().rotate(90)
            rotated_pixmap = pixmap.transformed(transform)
            self.image_label.setPixmap(rotated_pixmap)

    def update_timer_display(self):
        elapsed_time = self.start_time.msecsTo(QTime.currentTime())
        remaining_time = max(0, self.timer_interval - elapsed_time)
        minutes, seconds = divmod(remaining_time // 1000, 60)
        self.timer_display.setText(f"{minutes:02}:{seconds:02}")
        QTimer.singleShot(1000, self.update_timer_display)  # Update every second

    def return_to_main(self):
        self.parent.show()
        self.close()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
