from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout

class NewPresetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("New Preset")

        message = QLabel("Name of new preset:")

        standard_buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        self.buttonBox = QDialogButtonBox(standard_buttons)
        self.buttonBox.accepted.connect(self.submitclose)
        self.buttonBox.rejected.connect(self.reject)

        self.new_preset_name = ""
        self.preset_name_input = QLineEdit()

        self.layout = QVBoxLayout()
        self.layout.addWidget(message)
        self.layout.addWidget(self.preset_name_input)
        self.layout.addWidget(self.buttonBox)

        self.setLayout(self.layout)

    def submitclose(self):
        self.new_preset_name = self.preset_name_input.text()
        self.accept()