# TokNGauge — Windows tray assets

Resources for a future Windows tray wrapper (WinForms / WPF / WinUI 3
NotifyIcon). The web app itself runs on http://localhost:8770; the tray
icon is meant to launch / focus that page.

## Files

| File              | Purpose                                  |
|-------------------|------------------------------------------|
| `gauge.svg`       | Master vector logo                       |
| `AppIcon.ico`     | Multi-resolution Windows icon (16…256)   |
| `TrayIcon.png`    | 32×32 PNG for HiDPI tray rendering       |

## Regenerating

```powershell
python scripts/build_icons.py
Copy-Item static/icons/icon.ico    apps/menubar-windows/Resources/AppIcon.ico
Copy-Item static/icons/icon-32.png apps/menubar-windows/Resources/TrayIcon.png
```
