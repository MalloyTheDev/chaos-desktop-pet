from __future__ import annotations

import logging
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

LOGGER = logging.getLogger(__name__)


class PetStatusDialog(QDialog):
    """A premium dark-themed status dashboard for the pet's needs and settings."""

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.parent_win = parent

        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowTitle(f"Status - {parent.settings.pet_name}")
        self.setFixedSize(300, 440)

        # Style sheet for premium appearance
        self.setStyleSheet(
            "QDialog {"
            " background-color: #1e1e24;"
            " color: #f0f0f5;"
            " font-family: 'Segoe UI', Arial, sans-serif;"
            "}"
            "QLabel {"
            " color: #d0d0d5;"
            " font-size: 11px;"
            " font-weight: bold;"
            "}"
            "QLineEdit {"
            " background-color: #2e2e38;"
            " color: #ffffff;"
            " border: 1px solid #4a4a5a;"
            " border-radius: 6px;"
            " padding: 5px;"
            " font-size: 12px;"
            "}"
            "QComboBox {"
            " background-color: #2e2e38;"
            " color: #ffffff;"
            " border: 1px solid #4a4a5a;"
            " border-radius: 6px;"
            " padding: 5px;"
            " font-size: 12px;"
            "}"
            "QProgressBar {"
            " border: none;"
            " background-color: #2e2e38;"
            " border-radius: 4px;"
            " text-align: center;"
            " color: #ffffff;"
            " font-weight: bold;"
            " font-size: 10px;"
            "}"
            "QProgressBar::chunk {"
            " background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff8a00, stop:1 #e52e71);"
            " border-radius: 4px;"
            "}"
            "QPushButton {"
            " background-color: #e52e71;"
            " color: #ffffff;"
            " border: none;"
            " border-radius: 6px;"
            " padding: 8px;"
            " font-size: 12px;"
            " font-weight: bold;"
            "}"
            "QPushButton:hover {"
            " background-color: #ff4a85;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Header Info (Name & Personality)
        name_layout = QHBoxLayout()
        name_label = QLabel("NAME:", self)
        self.name_edit = QLineEdit(self)
        self.name_edit.setText(parent.settings.pet_name)
        self.name_edit.editingFinished.connect(self._on_name_changed)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        p_layout = QHBoxLayout()
        p_label = QLabel("PERSONALITY:", self)
        self.p_combo = QComboBox(self)
        self.p_combo.addItems(["playful", "lazy", "grumpy", "affectionate"])
        self.p_combo.setCurrentText(parent.settings.personality_id)
        self.p_combo.currentTextChanged.connect(self._on_personality_changed)
        p_layout.addWidget(p_label)
        p_layout.addWidget(self.p_combo)
        layout.addLayout(p_layout)

        # Separator Line
        line = QWidget(self)
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #4a4a5a;")
        layout.addWidget(line)

        # Stats progress bars
        self.bars = {}
        stats_list = [
            ("Hunger", "hunger"),
            ("Energy", "energy"),
            ("Happiness", "happiness"),
            ("Annoyance", "annoyance"),
            ("Curiosity", "curiosity"),
            ("Trust", "trust"),
        ]

        for label_text, key in stats_list:
            lbl = QLabel(label_text.upper() + ":", self)
            bar = QProgressBar(self)
            bar.setRange(0, 100)
            bar.setValue(int(getattr(parent.stats, key)))
            self.bars[key] = bar
            layout.addWidget(lbl)
            layout.addWidget(bar)

        # Bottom Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close", self)
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # Live Update Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_stats)
        self.timer.start(500)

    def _on_name_changed(self) -> None:
        name = self.name_edit.text().strip()
        if name:
            self.parent_win.settings.pet_name = name
            self.parent_win.settings.save()
            self.parent_win.save_data.pet_name = name
            self.parent_win.save_data.write()
            LOGGER.info("Pet name updated in dialog to %s", name)

    def _on_personality_changed(self, text: str) -> None:
        self.parent_win.settings.personality_id = text
        self.parent_win.settings.save()
        self.parent_win.save_data.personality_id = text
        self.parent_win.save_data.write()
        LOGGER.info("Pet personality updated in dialog to %s", text)

    def _update_stats(self) -> None:
        for key, bar in self.bars.items():
            val = getattr(self.parent_win.stats, key)
            bar.setValue(max(0, min(100, int(val))))
