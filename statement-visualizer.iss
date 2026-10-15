; Windows installer for the PyInstaller build (statement-visualizer.spec): StatementVisualizer-Setup.exe. Per-user, no
; admin: the program goes to %LOCALAPPDATA%\Programs\Statement Visualizer by default, with a Start Menu shortcut, and
; Settings > Apps can remove it. Your data (Statement\, workspace\, .env) is written next to the .exe as before, so it
; stays in that folder: an update keeps it, and the uninstaller removes the files it installed, then asks whether to
; delete your data too ([Code] below). Both only ever delete names of their own: Setup installs only into a new or
; empty folder (or over an earlier install), so nothing of anyone else's is ever in there.
; Build it after pyinstaller, on Windows (Inno Setup 6; .github/workflows/windows-build.yml does this):
;   "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DAppVersion=1.2.3 statement-visualizer.iss
; -> dist\StatementVisualizer-Setup.exe

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
; Numbers only (1.0.0-beta -> 1.0.0), for Setup's own file version info; CI passes /DFileVersion= with /DAppVersion=.
#ifndef FileVersion
  #define FileVersion "0.0.0"
#endif

[Setup]
; Never change AppId: it is how a newer Setup finds the installed copy to update.
AppId={{6B0E2F4C-5D7A-4E2B-9C1F-3A8D7E5B4C21}
AppName=Statement Visualizer
AppVersion={#AppVersion}
VersionInfoVersion={#FileVersion}
AppPublisher=Statement Visualizer
AppPublisherURL=https://github.com/Nine14282/Bank-Statement-Visualizer
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
; An update while the app is open: Setup asks to close it (CloseApplications, on by default) but doesn't restart it
; itself; the Finish page's "Launch" does, once.
RestartApplications=no
; The program holds this mutex while it runs (launcher.py): Setup and the uninstaller ask to close it first, instead of
; failing on its locked files (an uninstall would otherwise leave them until a restart).
AppMutex=StatementVisualizer
; Signing: CI has SignPath sign StatementVisualizer.exe before this script runs and Setup after it (README,
; "Releasing the Windows program"). ponytail: the uninstaller (unins000.exe) stays unsigned, since SignPath's GitHub
; action can't act as Inno's SignTool; it is made on the user's PC and never downloaded, so SmartScreen doesn't check
; it. Sign it too (SignedUninstaller=yes) if SignPath's command-line signing becomes an option.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; An update replaces the whole program part: files a newer build dropped would otherwise linger in _internal. Safe:
; NextButtonClick below lets Setup into a folder only when it is new, empty, or an earlier install of this program.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\StatementVisualizer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; The app window needs Microsoft's WebView2 runtime: part of Windows 11, missing on a few Windows 10 PCs. Microsoft's
; small bootstrapper (CI downloads it into dist\) installs it then; without it the program uses the browser instead.
#if FileExists(AddBackslash(SourcePath) + "dist\MicrosoftEdgeWebview2Setup.exe")
Source: "dist\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: WebView2Missing
#endif

[Icons]
Name: "{group}\Statement Visualizer"; Filename: "{app}\StatementVisualizer.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Statement Visualizer"; Filename: "{app}\StatementVisualizer.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
#if FileExists(AddBackslash(SourcePath) + "dist\MicrosoftEdgeWebview2Setup.exe")
; Not elevated, it installs the runtime for this account only. Offline it fails quietly: the browser pages still work.
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft Edge WebView2 Runtime..."; Flags: waituntilterminated; Check: WebView2Missing
#endif
Filename: "{app}\StatementVisualizer.exe"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,Statement Visualizer}"; Flags: nowait postinstall skipifsilent

[Code]
// Microsoft's check for an installed WebView2 runtime: a "pv" version under its EdgeUpdate client key, per machine
// (32-bit registry view) or per user.
const
  WebView2Key = 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasVersion(RootKey: Integer): Boolean;
var
  V: String;
begin
  Result := RegQueryStringValue(RootKey, WebView2Key, 'pv', V) and (V <> '') and (V <> '0.0.0.0');
end;

function WebView2Missing: Boolean;
begin
  Result := not (HasVersion(HKLM32) or HasVersion(HKCU));
end;

// --- the install folder: only one of its own ---------------------------------------------------------------------

function SameDir(A, B: String): Boolean;
begin
  Result := (B <> '') and (CompareText(RemoveBackslashUnlessRoot(A), RemoveBackslashUnlessRoot(B)) = 0);
end;

function IsEmptyDir(Dir: String): Boolean;
var
  F: TFindRec;
begin
  Result := True;
  if FindFirst(AddBackslash(Dir) + '*', F) then
    try
      repeat
        if (F.Name <> '.') and (F.Name <> '..') then
        begin
          Result := False;
          Break;
        end;
      until not FindNext(F);
    finally
      FindClose(F);
    end;
end;

// The program writes its data next to itself, and the uninstaller deletes there (only names of its own, below), as
// does the [InstallDelete] of _internal on an update. So refuse a drive's root, your own folders, and any folder that
// already holds other files: picking one with Browse gets "\Statement Visualizer" added to it (AppendDefaultDirName),
// typing one in comes here. Allowed: an earlier install (its .exe), and the data an uninstall kept (its workspace\ and
// Statement\ without the .exe), which installing again picks up.
function NextButtonClick(CurPageID: Integer): Boolean;
var
  Dir, Home: String;
begin
  Result := True;
  if CurPageID <> wpSelectDir then
    Exit;
  Dir := RemoveBackslashUnlessRoot(WizardDirValue);
  Home := GetEnv('USERPROFILE');
  if SameDir(Dir, ExtractFileDrive(Dir) + '\') or SameDir(Dir, Home) or SameDir(Dir, Home + '\Downloads') or
     SameDir(Dir, ExpandConstant('{userdocs}')) or SameDir(Dir, ExpandConstant('{userdesktop}')) or
     SameDir(Dir, ExpandConstant('{userpf}')) or SameDir(Dir, ExpandConstant('{localappdata}')) or
     SameDir(Dir, ExpandConstant('{userappdata}')) or SameDir(Dir, GetEnv('OneDrive')) or
     (DirExists(Dir) and not IsEmptyDir(Dir) and not FileExists(AddBackslash(Dir) + 'StatementVisualizer.exe') and
      not (DirExists(AddBackslash(Dir) + 'workspace') and DirExists(AddBackslash(Dir) + 'Statement'))) then
  begin
    SuppressibleMsgBox(Dir + ' holds other files. Statement Visualizer keeps your statements next to itself and ' +
      'its uninstaller deletes there, so it needs a folder of its own: pick a new or empty folder (the suggested ' +
      'one is fine).', mbError, MB_OK, IDOK);
    Result := False;
  end;
end;

// --- uninstall: the program's own data, by name only ---------------------------------------------------------------

procedure DeleteNamed(Path: String; IsDir: Boolean);
begin
  if IsDir then
    DelTree(Path, True, True, True)
  else
    DeleteFile(Path);
end;

// Before Inno removes the installed files (and then {app} itself, if that leaves it empty): the generated dashboard
// (it holds your transactions; the program builds it again), then, if you say so, your data. The same names as
// launcher.py's data_files() and uninstall --all; never a whole folder that could hold anything else. Statement\ loses
// only its PDFs. A silent uninstall (/SUPPRESSMSGBOXES) keeps the data.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  App: String;
begin
  if CurUninstallStep <> usUninstall then
    Exit;
  App := ExpandConstant('{app}');
  DeleteNamed(App + '\web\dist', True);
  DeleteNamed(App + '\Dashboard.html', False);
  RemoveDir(App + '\web');
  if SuppressibleMsgBox('Also delete your data in ' + App + '?' + #13#10#13#10 +
       'Your statement PDFs, the ledger, your expected spending, the saved Gmail login and the settings file with any ' +
       'saved passwords. This cannot be undone.' + #13#10#13#10 +
       'Choose No to keep them: installing again picks them up.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2,
       IDNO) <> IDYES then
    Exit;
  DelTree(App + '\Statement\*.pdf', False, True, False);
  DelTree(App + '\workspace\*.csv', False, True, False);
  DeleteNamed(App + '\workspace\expected.json', False);
  DeleteNamed(App + '\workspace\token.json', False);
  DeleteNamed(App + '\workspace\credentials.json', False);
  DeleteNamed(App + '\workspace\.gmail_seen.json', False);
  DeleteNamed(App + '\workspace\.gmail.lock', False);
  DeleteNamed(App + '\workspace\.gmail-listen.lock', False);
  DeleteNamed(App + '\workspace\.cache', True);
  DeleteNamed(App + '\workspace\.app', True);
  DeleteNamed(App + '\.env', False);
  RemoveDir(App + '\Statement');   // only if that left them empty
  RemoveDir(App + '\workspace');
end;
