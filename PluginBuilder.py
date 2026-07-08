import json
import re
import sys
import zipfile
from pathlib import Path

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
        QLabel, QLineEdit, QTextEdit, QPushButton, QFileDialog, QMessageBox,
        QCheckBox, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView
    )
except Exception as exc:
    print('PySide6 import failed:', exc)
    raise

APP_TITLE = 'File Type Plugin Builder'


def read_lines(path: Path):
    for enc in ('utf-8-sig','utf-8','cp932','shift_jis','latin-1'):
        try:
            return path.read_text(encoding=enc, errors='strict').splitlines()
        except Exception:
            pass
    return path.read_text(encoding='utf-8', errors='replace').splitlines()


def safe_id(text: str) -> str:
    s = re.sub(r'[^A-Za-z0-9_.-]+', '_', text.strip())
    return s or 'new_plugin'


class PluginBuilder(QWidget):
    def __init__(self):
        super().__init__()
        self.sample_path = None
        self.setWindowTitle(APP_TITLE)
        self.resize(900, 700)
        self.build_ui()

    def build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel(APP_TITLE)
        title.setStyleSheet('font-size:20px;font-weight:bold;')
        root.addWidget(title)
        note = QLabel('Build an Update File Type ZIP. This builder creates manifest.json and parser.json. Install the ZIP from LogMergeTool > Update File Type.')
        note.setWordWrap(True)
        root.addWidget(note)

        form_box = QGroupBox('Plugin Information')
        form = QFormLayout(form_box)
        self.id_edit = QLineEdit('newlog')
        self.name_edit = QLineEdit('New Log Type')
        self.version_edit = QLineEdit('1.0.0')
        self.patterns_edit = QLineEdit('*.log;*.txt')
        self.merge_chk = QCheckBox('Allow Merge')
        self.merge_chk.setChecked(True)
        self.import_chk = QCheckBox('Allow Import Only')
        self.import_chk.setChecked(True)
        form.addRow('Plugin ID', self.id_edit)
        form.addRow('Display Name', self.name_edit)
        form.addRow('Version', self.version_edit)
        form.addRow('File Patterns', self.patterns_edit)
        form.addRow('Mode', self._h(self.merge_chk, self.import_chk))
        root.addWidget(form_box)

        parser_box = QGroupBox('Parser Definition')
        parser_form = QFormLayout(parser_box)
        self.timestamp_mode = QComboBox()
        self.timestamp_mode.addItems(['auto_content_timestamp', 'filename_date_plus_line_time', 'section_date_plus_line_time', 'full_datetime_in_line', 'inherit_previous'])
        self.timestamp_regex = QLineEdit('')
        self.message_regex = QLineEdit('')
        self.level_regex = QLineEdit('')
        parser_form.addRow('Timestamp Mode', self.timestamp_mode)
        parser_form.addRow('Timestamp Regex (optional)', self.timestamp_regex)
        parser_form.addRow('Message Regex (optional)', self.message_regex)
        parser_form.addRow('Level Regex (optional)', self.level_regex)
        root.addWidget(parser_box)

        sample_box = QGroupBox('Sample / Preview')
        sample_layout = QVBoxLayout(sample_box)
        row = QHBoxLayout()
        self.open_sample_btn = QPushButton('Open Sample Log')
        self.test_btn = QPushButton('Test Parser Preview')
        row.addWidget(self.open_sample_btn); row.addWidget(self.test_btn); row.addStretch(1)
        sample_layout.addLayout(row)
        self.preview = QTableWidget(0, 4)
        self.preview.setHorizontalHeaderLabels(['Line', 'Timestamp Candidate', 'Level', 'Message Preview'])
        self.preview.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        sample_layout.addWidget(self.preview)
        root.addWidget(sample_box, stretch=1)

        buttons = QHBoxLayout()
        self.build_btn = QPushButton('Build Plugin ZIP')
        self.close_btn = QPushButton('Close')
        buttons.addStretch(1); buttons.addWidget(self.build_btn); buttons.addWidget(self.close_btn)
        root.addLayout(buttons)

        self.open_sample_btn.clicked.connect(self.open_sample)
        self.test_btn.clicked.connect(self.test_preview)
        self.build_btn.clicked.connect(self.build_zip)
        self.close_btn.clicked.connect(self.close)

        for w in [self.id_edit,self.name_edit,self.version_edit,self.patterns_edit,self.timestamp_mode,self.timestamp_regex,self.message_regex,self.level_regex,self.open_sample_btn,self.test_btn,self.build_btn]:
            w.setToolTip('Create a File Type plugin ZIP that can be installed into LogMergeTool without rebuilding the EXE.')

    def _h(self, *widgets):
        box = QWidget(); lay = QHBoxLayout(box); lay.setContentsMargins(0,0,0,0)
        for w in widgets: lay.addWidget(w)
        lay.addStretch(1)
        return box

    def open_sample(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Select sample log', str(Path.home()), 'Log files (*.log *.txt *.out *.ar);;All files (*.*)')
        if path:
            self.sample_path = Path(path)
            self.test_preview()

    def test_preview(self):
        if not self.sample_path:
            QMessageBox.information(self, 'Sample', 'Select a sample log first.')
            return
        lines = read_lines(self.sample_path)[:200]
        ts_re = self.timestamp_regex.text().strip()
        lvl_re = self.level_regex.text().strip()
        msg_re = self.message_regex.text().strip()
        ts_pat = re.compile(ts_re) if ts_re else None
        lvl_pat = re.compile(lvl_re) if lvl_re else None
        msg_pat = re.compile(msg_re) if msg_re else None
        self.preview.setRowCount(min(len(lines), 100))
        for row, line in enumerate(lines[:100]):
            ts = ''
            lvl = ''
            msg = line.strip()
            if ts_pat:
                m = ts_pat.search(line)
                ts = m.group(0) if m else ''
            else:
                m = re.search(r'(20\d{2}[-/]\d{1,2}[-/]\d{1,2}[^0-9]+\d{1,2}:\d{2}:\d{2}(?:[.:]\d+)?)|(\d{1,2}:\d{2}:\d{2}(?:[.:]\d+)?)', line)
                ts = m.group(0) if m else ''
            if lvl_pat:
                m = lvl_pat.search(line)
                lvl = m.group(0) if m else ''
            else:
                m = re.search(r'\b(ERROR|WARN|WARNING|INFO|DBG|DEBUG|FATAL)\b', line, re.I)
                lvl = m.group(0) if m else ''
            if msg_pat:
                m = msg_pat.search(line)
                if m:
                    msg = m.group(1) if m.groups() else m.group(0)
            for col, val in enumerate([row+1, ts, lvl, msg]):
                self.preview.setItem(row, col, QTableWidgetItem(str(val)))

    def build_zip(self):
        pid = safe_id(self.id_edit.text())
        patterns = [p.strip() for p in re.split(r'[;,]', self.patterns_edit.text()) if p.strip()]
        modes = []
        if self.merge_chk.isChecked(): modes.append('merge')
        if self.import_chk.isChecked(): modes.append('import')
        manifest = {
            'id': pid,
            'display_name': self.name_edit.text().strip() or pid,
            'version': self.version_edit.text().strip() or '1.0.0',
            'mode': modes or ['import'],
            'patterns': patterns or ['*.log'],
            'enabled': True,
            'plugin_api': '2.0',
            'description': 'Generated by File Type Plugin Builder'
        }
        parser = {
            'timestamp_mode': self.timestamp_mode.currentText(),
            'timestamp_regex': self.timestamp_regex.text().strip(),
            'message_regex': self.message_regex.text().strip(),
            'level_regex': self.level_regex.text().strip(),
            'columns': ['Timestamp','SourceType','File','Line','Level','Category','Message','Raw']
        }
        out, _ = QFileDialog.getSaveFileName(self, 'Save plugin ZIP', str(Path.home() / f'{pid}.plugin.zip'), 'Plugin ZIP (*.zip)')
        if not out:
            return
        outp = Path(out)
        if outp.suffix.lower() != '.zip':
            outp = outp.with_suffix('.zip')
        with zipfile.ZipFile(outp, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))
            zf.writestr('parser.json', json.dumps(parser, indent=2, ensure_ascii=False))
            zf.writestr('README.txt', 'Install this ZIP from LogMergeTool > Update File Type.\n')
            if self.sample_path and self.sample_path.exists():
                zf.write(self.sample_path, 'sample/' + self.sample_path.name)
        QMessageBox.information(self, 'Build Plugin ZIP', f'Created:\n{outp}')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = PluginBuilder(); w.show()
    sys.exit(app.exec())
