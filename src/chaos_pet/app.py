from __future__ import annotations

import logging
import logging.handlers
import random
import sys
import time

from PyQt6.QtCore import QPoint, QPointF, Qt, QTimer
from PyQt6.QtGui import QAction, QCursor, QIcon, QKeyEvent, QKeySequence, QMouseEvent, QShortcut
from PyQt6.QtWidgets import QApplication, QLabel, QMenu, QSystemTrayIcon, QWidget

from . import config
from .animation import AnimationController
from .asset_loader import MissingIdleError, load_sprite_assets, require_idle
from .behavior import ClickTracker, PetBehavior
from .save import PetSave
from .settings import load_settings
from .speech import SpeechBubble, VoiceLines


LOGGER = logging.getLogger(__name__)


def monotonic_ms() -> int:
    return int(time.monotonic() * 1000)


def quit_app() -> None:
    app = QApplication.instance()
    if app is not None:
        app.quit()


class PetWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.settings = load_settings()
        self.movement_paused = self.settings.movement_paused
        self._drag_start_global: QPoint | None = None
        self._drag_start_window: QPoint | None = None
        self._dragging = False
        self._sleep_transition_started = False
        self._woke_on_press = False
        self.tray_icon: QSystemTrayIcon | None = None
        self.tray_menu: QMenu | None = None
        self.context_menu: QMenu | None = None
        self.visibility_action: QAction | None = None
        self.pause_action: QAction | None = None
        self.ctx_pause_action: QAction | None = None
        self.speech_action: QAction | None = None
        self._last_speech_ms = 0
        self._last_evasive_ms = 0

        # Persistent, project-local save (position, mood stats, identity).
        self.save_data = PetSave.load()
        self.stats = self.save_data.stats

        # Local, offline speech (no AI/network). Bubble exists only when enabled.
        self.voice_lines = VoiceLines.load()
        self.speech_bubble = SpeechBubble() if self.settings.speech_enabled else None

        self.click_tracker = ClickTracker()

        self.setWindowTitle("Chaos Desktop Pet")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        # Without a focus policy the frameless Tool window never receives key
        # events, so Esc-to-quit would be dead. (Also backed by an app shortcut.)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.pet_size = self.settings.display_sprite_size
        self.setFixedSize(*self.pet_size)

        self.label = QLabel(self)
        self.label.setFixedSize(*self.pet_size)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.assets = load_sprite_assets(target_size=self.pet_size)
        require_idle(self.assets)  # fail clearly if the mandatory idle state is missing
        self.animation = AnimationController(self.assets)
        if self.save_data.last_state in self.assets.states:
            self.animation.set_state(self.save_data.last_state)
        self.behavior = PetBehavior(
            walk_speed_px=self.settings.walk_speed_px * self.settings.movement_speed_multiplier,
            sleep_after_ms=self.settings.sleep_after_ms,
        )
        self.behavior.notice(monotonic_ms())

        # Esc quits regardless of widget focus.
        self._quit_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._quit_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._quit_shortcut.activated.connect(quit_app)

        self._build_context_menu()
        self._restore_or_place()

        frame_interval = max(1, round(config.FRAME_INTERVAL_MS / self.settings.animation_speed_multiplier))
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._on_animation_tick)
        self.animation_timer.start(frame_interval)

        self.behavior_timer = QTimer(self)
        self.behavior_timer.timeout.connect(self._on_behavior_tick)
        self.behavior_timer.start(config.BEHAVIOR_INTERVAL_MS)

        self._last_stats_ms = monotonic_ms()
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self._on_stats_tick)
        self.stats_timer.start(config.STATS_TICK_MS)

        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._autosave)
        self.autosave_timer.start(config.AUTOSAVE_INTERVAL_MS)

        self._on_animation_tick()
        self._create_tray_icon()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            quit_app()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        now = monotonic_ms()
        self.behavior.notice(now)
        self._sleep_transition_started = False
        self._woke_on_press = self._wake_from_sleep(now)

        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_global = event.globalPosition().toPoint()
            self._drag_start_window = self.pos()
            self._dragging = False
            event.accept()
            return

        if event.button() == Qt.MouseButton.RightButton:
            if not self._woke_on_press and self.context_menu is not None:
                self.context_menu.exec(event.globalPosition().toPoint())
            self._woke_on_press = False
            event.accept()
            return

        self._woke_on_press = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_start_global is not None
            and self._drag_start_window is not None
        ):
            current_global = event.globalPosition().toPoint()
            delta = current_global - self._drag_start_global
            if self._dragging or delta.manhattanLength() >= config.DRAG_START_DISTANCE_PX:
                self._dragging = True
                self.behavior.notice(monotonic_ms())
                self.behavior.cancel_motion()
                target = self._drag_start_window + delta
                self.move(self._clamp_to_screen(target, current_global))
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._dragging and not self._woke_on_press:
                self._handle_click_combo(monotonic_ms())

            self._drag_start_global = None
            self._drag_start_window = None
            self._dragging = False
            self._woke_on_press = False
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def _handle_click_combo(self, now_ms: int) -> None:
        """Escalating left-click reaction: 1 = happy/curious, 3 = angry, 5 = jump."""
        count = self.click_tracker.register(now_ms)
        rapid = count >= 2
        self.stats.register_click(rapid=rapid)

        if count >= config.CLICK_JUMP_COUNT:
            self._do_jump_knockback(now_ms)
            self.click_tracker.reset()
            self._say("angry", force=True)
        elif count >= config.CLICK_ANGRY_COUNT:
            self._do_angry(now_ms)
            self._say("angry", force=True)
        elif count == 1:
            self._do_happy_or_curious(now_ms)
            self._say("click")
        else:
            self._say("click")

    def _begin_knockback_from_cursor(self) -> None:
        if self.movement_paused:
            return
        cursor = QPointF(QCursor.pos())
        center = QPointF(self.x() + self.width() / 2, self.y() + self.height() / 2)
        self.behavior.begin_knockback(self.pos(), center, cursor)

    def _do_angry(self, now_ms: int) -> None:
        self._begin_knockback_from_cursor()
        self.animation.play_sequence(
            [
                ("angry", config.ANGRY_BUMP_DURATION_MS),
                ("fall", config.FALL_DURATION_MS),
                ("land", config.LAND_DURATION_MS),
            ],
            now_ms,
            then=config.DEFAULT_STATE,
        )

    def _do_jump_knockback(self, now_ms: int) -> None:
        self._begin_knockback_from_cursor()
        # jump outranks angry, so a 5-click escalation interrupts an in-progress angry.
        self.animation.play_sequence(
            [("jump", config.JUMP_DURATION_MS)],
            now_ms,
            then=config.DEFAULT_STATE,
            force=True,
        )

    def _do_happy_or_curious(self, now_ms: int) -> None:
        if self.stats.curiosity >= 60.0 and "look_around" in self.assets.states:
            self.animation.play_sequence([("look_around", config.LOOK_AROUND_DURATION_MS)], now_ms)
        else:
            self.animation.play_sequence([("happy", config.HAPPY_DURATION_MS)], now_ms, then=config.DEFAULT_STATE)

    def _feed(self) -> None:
        """Feed -> eat one-shot -> happy -> idle, plus stat/speech effects."""
        now = monotonic_ms()
        self.behavior.notice(now)
        self._wake_from_sleep(now)
        self.stats.feed()
        started = self.animation.play_sequence(
            [("eat", config.EAT_DURATION_MS), ("happy", config.HAPPY_DURATION_MS)],
            now,
            then=config.DEFAULT_STATE,
        )
        if started:
            self._say("feed", force=True)
        LOGGER.info("Fed the pet (stats=%s).", self.stats.to_dict())

    def _say(self, trigger: str, *, force: bool = False) -> None:
        if self.speech_bubble is None or not self.settings.speech_enabled:
            return
        now = monotonic_ms()
        if not force and (now - self._last_speech_ms) < 1500:
            return
        line = self.voice_lines.get(trigger)
        if not line:
            return
        self._last_speech_ms = now
        self.speech_bubble.say(line, self.frameGeometry())

    def _set_movement_paused(self, paused: bool) -> None:
        self.movement_paused = paused
        for action in (self.pause_action, self.ctx_pause_action):
            if action is not None and action.isChecked() != paused:
                action.setChecked(paused)
        if paused:
            self.behavior.cancel_motion()
            if self.animation.state in {"walk", "run", "fall"}:
                self.animation.set_state(config.DEFAULT_STATE)
        LOGGER.info("Movement %s.", "paused" if paused else "resumed")

    def _set_speech_enabled(self, enabled: bool) -> None:
        self.settings.speech_enabled = enabled
        if enabled and self.speech_bubble is None:
            self.speech_bubble = SpeechBubble()
        elif not enabled and self.speech_bubble is not None:
            self.speech_bubble.stop()
        if self.speech_action is not None and self.speech_action.isChecked() != enabled:
            self.speech_action.setChecked(enabled)
        self.settings.save()
        LOGGER.info("Speech bubbles %s.", "enabled" if enabled else "disabled")

    def _toggle_size(self) -> None:
        cycle = config.SCALE_CYCLE
        try:
            index = cycle.index(self.settings.scale)
        except ValueError:
            index = -1
        new_scale = cycle[(index + 1) % len(cycle)]
        self.settings.scale = new_scale
        self.settings.save()

        current_state = self.animation.state
        self.pet_size = self.settings.display_sprite_size
        self.setFixedSize(*self.pet_size)
        self.label.setFixedSize(*self.pet_size)
        self.assets = load_sprite_assets(target_size=self.pet_size)
        self.animation = AnimationController(self.assets)
        self.animation.set_state(
            current_state if current_state in self.assets.states else config.DEFAULT_STATE
        )
        self.move(self._clamp_to_screen(self.pos(), self._pet_center()))
        self._on_animation_tick()
        LOGGER.info("Toggled size to scale=%d (%dpx).", new_scale, self.pet_size[0])

    def _build_context_menu(self) -> None:
        menu = QMenu(self)
        feed_action = QAction("Feed banana", self)
        feed_action.triggered.connect(self._feed)
        menu.addAction(feed_action)

        size_action = QAction("Toggle size", self)
        size_action.triggered.connect(self._toggle_size)
        menu.addAction(size_action)
        menu.addSeparator()

        self.ctx_pause_action = QAction("Pause movement", self)
        self.ctx_pause_action.setCheckable(True)
        self.ctx_pause_action.setChecked(self.movement_paused)
        self.ctx_pause_action.triggered.connect(self._set_movement_paused)
        menu.addAction(self.ctx_pause_action)

        self.speech_action = QAction("Speech bubbles", self)
        self.speech_action.setCheckable(True)
        self.speech_action.setChecked(self.settings.speech_enabled)
        self.speech_action.triggered.connect(self._set_speech_enabled)
        menu.addAction(self.speech_action)
        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(quit_app)
        menu.addAction(quit_action)
        self.context_menu = menu

    def _set_pet_visible(self, visible: bool) -> None:
        if visible:
            self.show()
            self.raise_()
            self.behavior.notice(monotonic_ms())
            self._sleep_transition_started = False
            if not self.animation_timer.isActive():
                self.animation_timer.start(config.FRAME_INTERVAL_MS)
            if not self.behavior_timer.isActive():
                self.behavior_timer.start(config.BEHAVIOR_INTERVAL_MS)
            if self.animation.state == "sleep":
                self.animation.set_state(config.DEFAULT_STATE)
            self._on_animation_tick()
            LOGGER.info("Pet shown.")
        else:
            self.behavior.cancel_motion()
            self.animation_timer.stop()
            self.behavior_timer.stop()
            self.hide()
            LOGGER.info("Pet hidden. Use the tray icon to show it again.")

        if self.visibility_action is not None:
            self.visibility_action.setText("Hide pet" if visible else "Show pet")

    def _toggle_pet_visibility(self) -> None:
        self._set_pet_visible(not self.isVisible())

    def _create_tray_icon(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            LOGGER.warning("System tray is not available; use Esc to quit.")
            return

        self.tray_menu = QMenu(self)
        self.visibility_action = QAction("Hide pet", self)
        self.visibility_action.triggered.connect(self._toggle_pet_visibility)
        self.tray_menu.addAction(self.visibility_action)
        self.tray_menu.addSeparator()

        feed_action = QAction("Feed banana", self)
        feed_action.triggered.connect(self._feed)
        self.tray_menu.addAction(feed_action)
        self.tray_menu.addSeparator()

        self.pause_action = QAction("Pause movement", self)
        self.pause_action.setCheckable(True)
        self.pause_action.setChecked(self.movement_paused)
        self.pause_action.triggered.connect(self._set_movement_paused)
        self.tray_menu.addAction(self.pause_action)
        self.tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(quit_app)
        self.tray_menu.addAction(quit_action)

        icon_frame = self.assets.frames_for(config.DEFAULT_STATE)[0]
        self.tray_icon = QSystemTrayIcon(QIcon(icon_frame), self)
        self.tray_icon.setToolTip("Chaos Desktop Pet")
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_pet_visibility()

    def _on_animation_tick(self) -> None:
        self.label.setPixmap(self.animation.update(monotonic_ms()))

    def _on_stats_tick(self) -> None:
        now = monotonic_ms()
        dt_s = max(0.0, (now - self._last_stats_ms) / 1000.0)
        self._last_stats_ms = now

        asleep = self.animation.state == "sleep"
        self.stats.update(dt_s, asleep=asleep)

        if self.movement_paused or self.animation.is_temporary or not self.isVisible():
            return

        # Low energy nudges the pet toward sleep sooner than the idle timeout.
        if self.stats.is_tired and not asleep and self.animation.state in {"idle", "sit"}:
            if not self._sleep_transition_started:
                self._sleep_transition_started = True
                if self.animation.play_sequence([("yawn", config.YAWN_DURATION_MS)], now, then="sleep"):
                    self._say("sleep")
            return

        # High annoyance occasionally triggers an evasive angry flash.
        if self.stats.is_irritated and self.animation.state in {"idle", "walk"}:
            if (now - self._last_evasive_ms) > 4000 and random.random() < 0.25:
                self._last_evasive_ms = now
                self._do_angry(now)
                self._say("angry")

    def _autosave(self) -> None:
        self._save_now()

    def _save_now(self) -> None:
        self.save_data.position = (self.x(), self.y())
        self.save_data.last_state = self.animation.state
        self.save_data.stats = self.stats
        self.save_data.pet_name = self.settings.pet_name
        self.save_data.personality_id = self.settings.personality_id
        self.save_data.write()

    def _pet_center(self) -> QPoint:
        return QPoint(self.x() + self.width() // 2, self.y() + self.height() // 2)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._save_now()
        super().closeEvent(event)

    def _on_behavior_tick(self) -> None:
        if not self.isVisible():
            return

        now = monotonic_ms()
        cursor = QPointF(QCursor.pos())
        # Clamp against the screen the PET occupies (not the cursor's screen), so
        # cross-monitor following can't snap the pet onto the wrong display.
        screen = QApplication.screenAt(self._pet_center()) or QApplication.primaryScreen()
        if screen is None:
            return  # no displays right now (e.g. RDP disconnect); skip this tick
        screen_rect = screen.availableGeometry()
        allow_motion = not self.movement_paused

        if self.animation.is_temporary:
            self._apply_motion_step(
                cursor,
                screen_rect,
                allow_motion=allow_motion,
                allow_follow=False,
            )
            return

        # Recover a displaced window (e.g. a monitor was unplugged while the pet
        # sat idle): re-clamp the current position onto the pet's screen even when
        # it isn't actively moving.
        recovered = self._clamp_to_screen(self.pos(), self._pet_center())
        if recovered != self.pos():
            self.move(recovered)

        allow_follow = allow_motion and self.animation.state != "sleep"

        step = self._apply_motion_step(
            cursor,
            screen_rect,
            allow_motion=allow_motion,
            allow_follow=allow_follow,
        )

        cursor_has_attention = self.behavior.cursor_counts_as_attention(step.distance_to_cursor)
        if self.animation.state == "sleep" and cursor_has_attention:
            self._wake_from_sleep(now)
            return

        if cursor_has_attention:
            self.behavior.notice(now)
            self._sleep_transition_started = False

        if not step.moving and self.behavior.should_sleep(now):
            if self.animation.state != "sleep" and not self._sleep_transition_started:
                self._sleep_transition_started = True
                if self.animation.play_sequence([("yawn", config.YAWN_DURATION_MS)], now, then="sleep"):
                    self._say("sleep")
            else:
                self.animation.set_state("sleep")
            return

        if step.moving:
            self._sleep_transition_started = False
            self.animation.set_state(step.motion_state)
            return

        if self.animation.state != config.DEFAULT_STATE:
            self.animation.set_state(config.DEFAULT_STATE)

        idle_variation = self.behavior.next_idle_variation(now)
        if idle_variation == "look_around":
            self.animation.play_sequence(
                [("look_around", config.LOOK_AROUND_DURATION_MS)],
                now,
                then=config.DEFAULT_STATE,
            )
            self._say("idle")
            return
        if idle_variation == "sit":
            self.animation.play_sequence(
                [("sit", config.SIT_DURATION_MS)],
                now,
                then=config.DEFAULT_STATE,
            )
            self._say("idle")
            return

        if self.behavior.should_blink(now):
            self.animation.play_sequence(
                [("blink", config.BLINK_DURATION_MS)],
                now,
                then=config.DEFAULT_STATE,
            )

    def _apply_motion_step(self, cursor: QPointF, screen_rect, *, allow_motion: bool, allow_follow: bool):
        step = self.behavior.step(
            self.pos(),
            cursor,
            self.pet_size,
            screen_rect,
            allow_motion=allow_motion,
            allow_follow=allow_follow,
        )
        if step.position != self.pos():
            self.move(step.position)
        return step

    def _wake_from_sleep(self, now_ms: int) -> bool:
        if self.animation.state != "sleep":
            return False
        self.behavior.notice(now_ms)
        self._sleep_transition_started = False
        self.stats.on_wake()
        if self.animation.play_sequence([("wake", config.WAKE_DURATION_MS)], now_ms, then=config.DEFAULT_STATE):
            self._say("wake")
        return True

    def _restore_or_place(self) -> None:
        """Restore the saved position if present (clamped on-screen), else place by corner."""
        pos = self.save_data.position
        if pos is not None:
            candidate = QPoint(pos[0], pos[1])
            self.move(self._clamp_to_screen(candidate, candidate))
            return
        self._place_initially()

    def _place_initially(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            self.move(200, 200)
            return

        rect = screen.availableGeometry()
        self.move(self._initial_position(rect))

    def _initial_position(self, rect) -> QPoint:
        margin = self.settings.start_margin_px
        left = rect.left() + margin
        right = rect.right() - self.width() - margin + 1
        top = rect.top() + margin
        bottom = rect.bottom() - self.height() - margin + 1

        positions = {
            "top_left": QPoint(left, top),
            "top_right": QPoint(right, top),
            "bottom_left": QPoint(left, bottom),
            "bottom_right": QPoint(right, bottom),
            "center": QPoint(
                rect.left() + (rect.width() - self.width()) // 2,
                rect.top() + (rect.height() - self.height()) // 2,
            ),
        }
        return self._clamp_to_screen(positions[self.settings.starting_corner], rect.center())

    def _clamp_to_screen(self, position: QPoint, screen_hint: QPoint) -> QPoint:
        screen = QApplication.screenAt(screen_hint) or QApplication.primaryScreen()
        if screen is None:
            return position
        rect = screen.availableGeometry()
        max_x = rect.right() - self.width() + 1
        max_y = rect.bottom() - self.height() + 1
        x = min(max(position.x(), rect.left()), max_x)
        y = min(max(position.y(), rect.top()), max_y)
        return QPoint(x, y)


def _configure_logging() -> None:
    """Console + rotating project-local file log. Never logs private/system data."""
    try:
        config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        # If we cannot make the dirs, fall back to console-only logging.
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
        logging.getLogger(__name__).warning("Could not create data/logs dirs: %s", exc)
        return

    root = logging.getLogger()
    if root.handlers:
        return  # already configured (e.g. when imported by a test)
    root.setLevel(logging.INFO)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root.addHandler(console)

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            config.LOG_PATH, maxBytes=512 * 1024, backupCount=2, encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(file_handler)
    except OSError as exc:
        root.warning("Could not open log file %s: %s", config.LOG_PATH, exc)


def run(argv: list[str] | None = None) -> int:
    _configure_logging()
    LOGGER.info("Chaos Desktop Pet starting up.")

    app = QApplication(argv if argv is not None else sys.argv)
    app.setQuitOnLastWindowClosed(True)

    try:
        window = PetWindow()
    except MissingIdleError as exc:
        LOGGER.error("Fatal: %s", exc)
        return 2

    app.aboutToQuit.connect(window._save_now)
    window.show()
    window.raise_()
    window.activateWindow()

    LOGGER.info("Available animation states: %s", ", ".join(window.assets.states) or "none")
    code = app.exec()
    LOGGER.info("Chaos Desktop Pet shutting down.")
    return code
