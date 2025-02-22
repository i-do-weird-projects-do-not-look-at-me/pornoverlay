import sys
import os
import cv2
import requests
import tempfile
import yt_dlp
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QPoint
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

search_term = input("What category of porn do you desire?  ")
download_index = 2
next_video_path = None

class VideoThread(QThread):
    change_frame = pyqtSignal(QImage)
    halfway_signal = pyqtSignal()

    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path
        self._run_flag = True

    def run(self):
        cap = cv2.VideoCapture(self.video_path)
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
            self.msleep(33)

        cap.release()

    def stop(self):
        self._run_flag = False
        self.wait()

class VideoPlayer(QWidget):
    def __init__(self, video_path):
        super().__init__()
        self.setWindowTitle("Video Player")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.5)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(50, 50, screen.width() // 8, screen.height() // 8)

        self.video_label = QLabel(self)
        self.video_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.video_label)
        self.setLayout(layout)

        self.drag_position = None

        self.thread = VideoThread(video_path)
        self.thread.change_frame.connect(self.update_image)
        self.thread.halfway_signal.connect(self.pre_download_next_video)
        self.thread.finished.connect(self.play_next_video)
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

                # Get the current position of the window
                window_pos = self.pos()

                # Define the four corners
                corners = [
                    QPoint(0, 0),  # Top-left corner
                    QPoint(screen.width() - self.width(), 0),  # Top-right corner
                    QPoint(0, screen.height() - self.height()),  # Bottom-left corner
                    QPoint(screen.width() - self.width(), screen.height() - self.height())  # Bottom-right corner
                ]

                # Find the nearest corner
                nearest_corner = min(corners, key=lambda corner: (corner - window_pos).manhattanLength())

                # Move window to the nearest corner
                self.move(nearest_corner)

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.ShiftModifier and event.key() == Qt.Key_N:
            self.skip_current_video_and_delete_next()

    def skip_current_video_and_delete_next(self):
        global next_video_path
        # Delete the next video if it exists
        if next_video_path and os.path.exists(next_video_path):
            os.remove(next_video_path)
            print(f"Next video deleted: {next_video_path}")

        # Delete the current video if it exists
        if os.path.exists(self.thread.video_path):
            os.remove(self.thread.video_path)
            print(f"Current video deleted: {self.thread.video_path}")

        # Pre-download next video
        self.pre_download_next_video()

        # Skip to next video (simulate video end)
        self.play_next_video()

    def pre_download_next_video(self):
        global next_video_path, download_index
        download_index += 1
        video_url = fetch_video_url(search_term)
        next_video_path = download_video(video_url)
        print(f"Pre-downloaded next video to: {next_video_path}")

    def play_next_video(self):
        global next_video_path
        if next_video_path:
            os.remove(self.thread.video_path)  # Clean up current video
            self.thread = VideoThread(next_video_path)  # Start the next video
            self.thread.change_frame.connect(self.update_image)
            self.thread.halfway_signal.connect(self.pre_download_next_video)
            self.thread.finished.connect(self.play_next_video)
            self.thread.start()

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

    # If video with same name exists, delete it
    if os.path.exists(save_path):
        os.remove(save_path)
        print(f"Deleted existing video: {save_path}")

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
