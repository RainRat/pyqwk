import tkinter as tk
from pyqwk.gui import QwkGuiApp
import os

def verify():
    root = tk.Tk()
    app = QwkGuiApp(root)
    # Give it some time to render
    root.update()

    # Verify the checkbutton exists in the toolbar
    # We can search through the children of the toolbar
    found = False
    for child in root.winfo_children():
        if isinstance(child, tk.Frame) or 'frame' in str(child).lower():
            for grandchild in child.winfo_children():
                 if 'Redact PII' in str(grandchild):
                     found = True
                     break

    print(f"Redact PII found: {hasattr(app, 'redact_pii_var')}")
    root.destroy()

if __name__ == "__main__":
    verify()
