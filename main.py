import sys
import os
import cv2
import requests
import yt_dlp
import threading
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QPoint
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

search_term = input("What category of porn do you desire?  ")
download_index = 0
next_video_path = None

global windowSizeRatio, windowOpacity
windowSizeRatio = 7
windowOpacity = 75


class VideoThread(QThread):
    change_frame = pyqtSignal(QImage)
    halfway_signal = pyqtSignal()
    finished_signal = pyqtSignal()

    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path
        self._run_flag = True

    def run(self):
        cap = cv2.VideoCapture(self.video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30  # Get actual FPS, default to 30 if not found
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        halfway_frame = frame_count // 2
        frame_counter = 0

        while self._run_flag and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_counter += 1
            if frame_counter == halfway_frame:
                self.halfway_signal.emit()

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            height, width, channels = rgb_frame.shape
            bytes_per_line = channels * width
            qt_image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)

            self.change_frame.emit(qt_image)
            self.msleep(int(1000 / fps))  # Adjust sleep time based on FPS

        cap.release()
        self.finished_signal.emit()

    def stop(self):
        self._run_flag = False
        self.wait()

class VideoPlayer(QWidget):
    def __init__(self, video_path):
        super().__init__()
        self.setWindowTitle("Video Player")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(windowOpacity/100)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(50, 50, screen.width() // windowSizeRatio, screen.height() // windowSizeRatio)

        self.video_label = QLabel(self)
        self.video_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.video_label)
        self.setLayout(layout)

        self.drag_position = None

        self.thread = VideoThread(video_path)
        self.thread.change_frame.connect(self.update_image)
        self.thread.halfway_signal.connect(self.pre_download_next_video)
        self.thread.finished_signal.connect(self.play_next_video)
        self.thread.start()

    def update_image(self, image):
        scaled_pixmap = QPixmap.fromImage(image).scaled(
            self.video_label.width(), self.video_label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video_label.setPixmap(scaled_pixmap)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_position is not None:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self.drag_position is not None:
            self.drag_position = None
            if QApplication.keyboardModifiers() == Qt.ControlModifier:
                screen = QApplication.primaryScreen().geometry()
                window_size = self.frameGeometry()
                corners = [
                    QPoint(0, 0),
                    QPoint(screen.width() - window_size.width(), 0),
                    QPoint(0, screen.height() - window_size.height()),
                    QPoint(screen.width() - window_size.width(), screen.height() - window_size.height())
                ]
                nearest_corner = min(corners, key=lambda corner: (corner - self.pos()).manhattanLength())
                self.move(nearest_corner)

    def pre_download_next_video(self):
        global next_video_path, download_index
        if next_video_path is None:
            download_index += 1
            threading.Thread(target=self.download_next_video, daemon=True).start()

    def download_next_video(self):
        global next_video_path
        video_url = fetch_video_url(search_term)
        next_video_path = download_video(video_url)
        print(f"Pre-downloaded next video to: {next_video_path}")

    def play_next_video(self):
        global next_video_path
        if next_video_path:
            os.remove(self.thread.video_path)  # Remove current video
            self.thread = VideoThread(next_video_path)
            self.thread.change_frame.connect(self.update_image)
            self.thread.halfway_signal.connect(self.pre_download_next_video)
            self.thread.finished_signal.connect(self.play_next_video)
            self.thread.start()
            next_video_path = None

def fetch_video_url(search_term):
    api_url = f"https://www.pornhub.com/webmasters/search?search={search_term}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(api_url, headers=headers)
    if response.status_code != 200:
        raise Exception("Failed to fetch search results")
    data = response.json()
    if "videos" not in data or not data["videos"]:
        raise Exception("No video found for the search term")
    return data["videos"][download_index].get("url", "No URL found")

def download_video(video_url):
    save_path = os.path.join(os.getcwd(), f"video_{download_index}.mp4")
    if os.path.exists(save_path):
        os.remove(save_path)
    ydl_opts = {'outtmpl': save_path, 'quiet': True, 'no_warnings': True, 'format': 'worst.2'}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    return save_path

def run():
    try:
        video_url = fetch_video_url(search_term)
        print(f"Found video URL: {video_url}")
    except Exception as e:
        print(f"Error fetching video URL: {e}")
        return

    try:
        video_path = download_video(video_url)
        print(f"Video downloaded to: {video_path}")
    except Exception as e:
        print(f"Error downloading video: {e}")
        return

    app = QApplication(sys.argv)
    player = VideoPlayer(video_path)
    player.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    run()
