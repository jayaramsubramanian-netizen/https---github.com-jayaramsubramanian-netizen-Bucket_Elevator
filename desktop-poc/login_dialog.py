"""
login_dialog.py — VECTOMEC™ Login & First-Launch Account Setup
═══════════════════════════════════════════════════════════════════════════
Two dialogs:

LoginDialog
    Standard username/password form. Returned user is set as the
    session-level current user via auth.set_current_user(). The dialog
    cannot be dismissed without a valid login -- no guest/anonymous mode.

FirstLaunchWizard
    Shown only when auth.AuthDB.has_any_users() returns False (first run
    ever, or the users database was wiped). Creates the initial approver
    account that can then create additional users via the user manager.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QFrame, QFormLayout,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from theme import PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, PRIMARY, DANGER, SUCCESS
from auth import AuthDB, UserRecord, set_current_user, ROLES


def _input_style():
    return (
        f"background-color:{PANEL2};color:{TEXT};border:1px solid {BORDER};"
        f"border-radius:5px;padding:6px 10px;font-size:12px;"
    )


def _btn_style(primary=False):
    if primary:
        return (
            f"QPushButton{{background:{PRIMARY};color:#fff;border:none;border-radius:5px;"
            f"padding:8px 20px;font-size:12px;font-weight:700;}}"
            f"QPushButton:hover{{background:#4a9cf5;}}"
            f"QPushButton:disabled{{background:{PANEL2};color:{TEXT3};}}"
        )
    return (
        f"QPushButton{{background:transparent;color:{TEXT2};border:1px solid {BORDER};"
        f"border-radius:5px;padding:8px 20px;font-size:12px;}}"
        f"QPushButton:hover{{background:{PANEL2};}}"
    )


class LoginDialog(QDialog):
    """Standard login form. Exec()s and returns the authenticated
    UserRecord via self.authenticated_user if accepted."""

    def __init__(self, auth_db: AuthDB, parent=None):
        super().__init__(parent)
        self.auth_db = auth_db
        self.authenticated_user: UserRecord | None = None
        self.setWindowTitle("VECTOMEC™ — Sign In")
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setStyleSheet(f"background-color:{PANEL};color:{TEXT};")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(18)

        # Header
        brand = QLabel("VECTOMEC™")
        brand.setStyleSheet(f"color:{PRIMARY};font-size:20px;font-weight:700;")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand)
        sub = QLabel("Bucket Elevator Design System")
        sub.setStyleSheet(f"color:{TEXT2};font-size:11px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{BORDER};")
        layout.addWidget(sep)

        # Form
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Username")
        self.username_edit.setStyleSheet(_input_style())
        _lbl_u = QLabel("Username:"); _lbl_u.setStyleSheet(f"color:{TEXT2};font-size:11px;")
        form.addRow(_lbl_u, self.username_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Password")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setStyleSheet(_input_style())
        self.password_edit.returnPressed.connect(self._attempt_login)
        _lbl_p = QLabel("Password:"); _lbl_p.setStyleSheet(f"color:{TEXT2};font-size:11px;")
        form.addRow(_lbl_p, self.password_edit)
        layout.addLayout(form)

        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet(f"color:{DANGER};font-size:10.5px;")
        self.error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_lbl.hide()
        layout.addWidget(self.error_lbl)

        self.login_btn = QPushButton("Sign In")
        self.login_btn.setStyleSheet(_btn_style(primary=True))
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.clicked.connect(self._attempt_login)
        layout.addWidget(self.login_btn)

    def _attempt_login(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        if not username or not password:
            self._show_error("Please enter your username and password.")
            return
        user = self.auth_db.authenticate(username, password)
        if user is None:
            self._show_error("Incorrect username or password.")
            self.password_edit.clear()
            self.password_edit.setFocus()
            return
        self.authenticated_user = user
        set_current_user(user)
        self.accept()

    def _show_error(self, msg: str):
        self.error_lbl.setText(msg)
        self.error_lbl.show()


class FirstLaunchWizard(QDialog):
    """Shown on the very first launch (no users exist yet).
    Creates the initial approver account."""

    def __init__(self, auth_db: AuthDB, parent=None):
        super().__init__(parent)
        self.auth_db = auth_db
        self.created_user: UserRecord | None = None
        self.setWindowTitle("VECTOMEC™ — Initial Setup")
        self.setModal(True)
        self.setMinimumWidth(440)
        self.setStyleSheet(f"background-color:{PANEL};color:{TEXT};")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        brand = QLabel("VECTOMEC™")
        brand.setStyleSheet(f"color:{PRIMARY};font-size:20px;font-weight:700;")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand)

        title = QLabel("First-Launch Setup — Create Administrator Account")
        title.setWordWrap(True)
        title.setStyleSheet(f"color:{TEXT};font-size:12px;font-weight:700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "This account will have Approver permissions — the highest role level. "
            "It will be able to create additional users and release designs. "
            "You can create further accounts after signing in."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{TEXT2};font-size:10.5px;")
        layout.addWidget(desc)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{BORDER};")
        layout.addWidget(sep)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def row(placeholder, echo=False):
            w = QLineEdit()
            w.setPlaceholderText(placeholder)
            w.setStyleSheet(_input_style())
            if echo:
                w.setEchoMode(QLineEdit.EchoMode.Password)
            return w

        self.username_edit    = row("e.g. jsmith")
        self.display_edit     = row("e.g. Jay Smith")
        self.title_edit       = row("e.g. Lead Engineer")
        self.company_edit     = row("e.g. Akshayvipra Engineering")
        self.password_edit    = row("Choose a password", echo=True)
        self.confirm_edit     = row("Confirm password", echo=True)

        for label, widget in [
            ("Username:",        self.username_edit),
            ("Full name:",       self.display_edit),
            ("Job title:",       self.title_edit),
            ("Company:",         self.company_edit),
            ("Password:",        self.password_edit),
            ("Confirm password:", self.confirm_edit),
        ]:
            _fl = QLabel(label); _fl.setStyleSheet(f"color:{TEXT2};font-size:11px;")
            form.addRow(_fl, widget)
        layout.addLayout(form)

        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet(f"color:{DANGER};font-size:10.5px;")
        self.error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_lbl.hide()
        layout.addWidget(self.error_lbl)

        create_btn = QPushButton("Create Account & Continue")
        create_btn.setStyleSheet(_btn_style(primary=True))
        create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        create_btn.clicked.connect(self._create)
        layout.addWidget(create_btn)

    def _create(self):
        username = self.username_edit.text().strip()
        display  = self.display_edit.text().strip()
        title    = self.title_edit.text().strip()
        company  = self.company_edit.text().strip()
        password = self.password_edit.text()
        confirm  = self.confirm_edit.text()

        if not all([username, display, password]):
            self._show_error("Username, full name and password are required.")
            return
        if len(password) < 8:
            self._show_error("Password must be at least 8 characters.")
            return
        if password != confirm:
            self._show_error("Passwords do not match.")
            return
        if self.auth_db.get_by_username(username):
            self._show_error("That username is already taken.")
            return

        user = self.auth_db.create_user(
            username=username, password=password, display_name=display,
            title=title, company=company, role="approver"
        )
        self.created_user = user
        set_current_user(user)
        self.accept()

    def _show_error(self, msg: str):
        self.error_lbl.setText(msg)
        self.error_lbl.show()


class UserManagerDialog(QDialog):
    """List, create, edit, and deactivate users. Approver-only."""

    def __init__(self, auth_db: AuthDB, parent=None):
        super().__init__(parent)
        self.auth_db = auth_db
        self.setWindowTitle("VECTOMEC™ — User Management")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setMinimumHeight(420)
        self.setStyleSheet(f"background-color:{PANEL};color:{TEXT};")
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header = QLabel("User Management")
        header.setStyleSheet(f"color:{TEXT};font-size:14px;font-weight:700;")
        layout.addWidget(header)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Username", "Full Name", "Title", "Role", "Status"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setStyleSheet(
            f"QTableWidget{{background:{PANEL2};color:{TEXT};border:none;gridline-color:{BORDER};}}"
            f"QHeaderView::section{{background:{PANEL};color:{TEXT2};border:none;"
            f"border-bottom:1px solid {BORDER};padding:6px;font-size:9.5px;font-weight:700;}}"
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.new_btn = QPushButton("+ New User")
        self.new_btn.setStyleSheet(_btn_style(primary=True))
        self.new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_btn.clicked.connect(self._new_user)
        btn_row.addWidget(self.new_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(_btn_style())
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _refresh(self):
        from PySide6.QtWidgets import QTableWidgetItem
        users = self.auth_db.list_users()
        self.table.setRowCount(len(users))
        role_colors = {"approver": PRIMARY, "reviewer": "#22c55e", "designer": TEXT2}
        for i, u in enumerate(users):
            for j, val in enumerate([u.username, u.display_name, u.title,
                                       u.role.upper(), "Active" if u.active else "Inactive"]):
                item = QTableWidgetItem(val)
                if j == 3:
                    from PySide6.QtGui import QColor
                    item.setForeground(QColor(role_colors.get(u.role, TEXT2)))
                self.table.setItem(i, j, item)

    def _new_user(self):
        dlg = _CreateUserDialog(self.auth_db, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh()


class _CreateUserDialog(QDialog):
    def __init__(self, auth_db: AuthDB, parent=None):
        super().__init__(parent)
        self.auth_db = auth_db
        self.setWindowTitle("Create User")
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setStyleSheet(f"background-color:{PANEL};color:{TEXT};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def row(ph, echo=False):
            w = QLineEdit()
            w.setPlaceholderText(ph)
            w.setStyleSheet(_input_style())
            if echo:
                w.setEchoMode(QLineEdit.EchoMode.Password)
            return w

        self.username_edit = row("Username")
        self.display_edit  = row("Full name")
        self.title_edit    = row("Job title")
        self.company_edit  = row("Company")
        self.pw_edit       = row("Password", echo=True)
        self.role_combo    = QComboBox()
        self.role_combo.setStyleSheet(_input_style())
        for r in ROLES:
            self.role_combo.addItem(r.capitalize(), r)

        for label, widget in [
            ("Username:", self.username_edit), ("Full name:", self.display_edit),
            ("Job title:", self.title_edit), ("Company:", self.company_edit),
            ("Password:", self.pw_edit), ("Role:", self.role_combo),
        ]:
            _fl = QLabel(label); _fl.setStyleSheet(f"color:{TEXT2};font-size:11px;")
            form.addRow(_fl, widget)
        layout.addLayout(form)

        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet(f"color:{DANGER};font-size:10px;")
        self.error_lbl.hide()
        layout.addWidget(self.error_lbl)

        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(_btn_style())
        cancel.clicked.connect(self.reject)
        create = QPushButton("Create")
        create.setStyleSheet(_btn_style(primary=True))
        create.clicked.connect(self._create)
        btns.addWidget(cancel)
        btns.addWidget(create)
        layout.addLayout(btns)

    def _create(self):
        username = self.username_edit.text().strip()
        display  = self.display_edit.text().strip()
        pw       = self.pw_edit.text()
        role     = self.role_combo.currentData()
        if not all([username, display, pw]):
            self.error_lbl.setText("Username, name and password required.")
            self.error_lbl.show()
            return
        if len(pw) < 8:
            self.error_lbl.setText("Password must be at least 8 characters.")
            self.error_lbl.show()
            return
        if self.auth_db.get_by_username(username):
            self.error_lbl.setText("Username already exists.")
            self.error_lbl.show()
            return
        self.auth_db.create_user(
            username=username, password=pw, display_name=display,
            title=self.title_edit.text().strip(),
            company=self.company_edit.text().strip(), role=role
        )
        self.accept()