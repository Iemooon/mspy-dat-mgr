# mspy-dat-mgr

A Windows desktop manager for two Microsoft Pinyin dictionary formats:

- `ChsPinyinUDL.dat` — self-study words
- `UserDefinedPhrase.dat` — custom phrases

The application provides separate workspaces for the two formats. It can import, edit, search, generate pinyin codes, deduplicate, save local workspaces, and export a new DAT file.

> This project is not affiliated with or endorsed by Microsoft.

## Download and use

For regular Windows users, download the ZIP package from the repository's **Releases** page, extract the entire archive, and run `mspy-dat-mgr.exe`. Python installation is not required.

A Chinese quick-start and safety reminder opens on launch. It remains available from the **使用说明** button in the lower-right corner of the main window.

## Features

- Separate tabs for self-study words and custom phrases
- Create a new dictionary, import an existing DAT, or reopen a local workspace
- Add, delete, clear, search, bulk-paste, deduplicate, undo, and redo entries
- Double-click to edit table cells; custom-phrase rank is editable
- Generate full pinyin; custom phrases can also use initials
- Export a new DAT and re-read it before reporting success
- Never overwrites the imported DAT file

## Safety boundary

- Source DAT files are read only.
- The program does not write to Windows IME directories.
- The program does not automate Microsoft Pinyin import.
- Export is explicitly triggered by the user and writes a new file.
- Local workspaces and exported DAT files may contain personal vocabulary. They are excluded from Git by default.

## Compatibility

The standard-generation path for both supported DAT formats was manually imported successfully into Microsoft Pinyin on the developer's Windows environment. Other Windows or Microsoft Pinyin versions may behave differently.

Always back up your existing dictionary before importing any exported file. Use this project at your own risk.

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or later with Tkinter

Install the Python dependency:

```cmd
python -m pip install -r requirements.txt
```

## Run

```cmd
git clone https://github.com/Iemooon/mspy-dat-mgr.git
cd mspy-dat-mgr
python -m pip install -r requirements.txt
python main.py
```

## Test

The repository contains synthetic, non-personal regression fixtures only. It does not include a real exported dictionary, imported DAT, or cached workspace.

```cmd
python run_regression.py
python -m gui.app --smoke-test
```

## Packaging (optional)

To make a Windows executable locally:

```cmd
python -m venv .release-venv
.release-venv\Scripts\python -m pip install -r requirements.txt pyinstaller
.release-venv\Scripts\python -m PyInstaller --noconfirm --clean --windowed --name "mspy-dat-mgr" --paths . main.py
copy README.txt dist\mspy-dat-mgr\README.txt
```

The generated files are placed under `dist/` and are ignored by Git.

## License

[MIT](LICENSE)
