; Windows installer for the PyInstaller build (statement-visualizer.spec): StatementVisualizer-Setup.exe. Per-user, no
; admin: the program goes to %LOCALAPPDATA%\Programs\Statement Visualizer by default, with a Start Menu shortcut, and
; Settings > Apps can remove it. Your data (Statement\, workspace\, .env) is written next to the .exe as before, so it
; stays in that folder: the uninstaller removes only the files it installed, and an update keeps your data.
; Build it after pyinstaller, on Windows (Inno Setup 6; .github/workflows/windows-build.yml does this):
;   "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DAppVersion=1.2.3 statement-visualizer.iss
; -> dist\StatementVisualizer-Setup.exe

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; Never change AppId: it is how a newer Setup finds the installed copy to update.
AppId={{6B0E2F4C-5D7A-4E2B-9C1F-3A8D7E5B4C21}
AppName=Statement Visualizer
AppVersion={#AppVersion}
AppPublisher=Statement Visualizer
AppPublisherURL=https://github.com/Nine14282/Income-and-Expenses-Dashboard
DefaultDirName={userpf}\Statement Visualizer
DefaultGroupName=Statement Visualizer
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\StatementVisualizer.exe
OutputDir=dist
OutputBaseFilename=StatementVisualizer-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; An update replaces the whole program part: files a newer build dropped would otherwise linger in _internal.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\StatementVisualizer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Statement Visualizer"; Filename: "{app}\StatementVisualizer.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Statement Visualizer"; Filename: "{app}\StatementVisualizer.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\StatementVisualizer.exe"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,Statement Visualizer}"; Flags: nowait postinstall skipifsilent
