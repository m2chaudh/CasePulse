; CasePulse Windows Installer — Inno Setup Script
; Download Inno Setup from: https://jrsoftware.org/isinfo.php
;
; Build steps:
;   1. Run build_win.bat first (creates dist\CasePulse\)
;   2. Open this file in Inno Setup Compiler
;   3. Click Build > Compile
;   4. Output: dist\CasePulse_Setup.exe

[Setup]
AppName=CasePulse
AppVersion=1.0.0
AppPublisher=CasePulse
AppPublisherURL=https://github.com/m2chaudh/CasePulse
DefaultDirName={autopf}\CasePulse
DefaultGroupName=CasePulse
OutputDir=dist
OutputBaseFilename=CasePulse_Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\CasePulse.exe
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startmenu"; Description: "Create a Start Menu shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Files]
Source: "dist\CasePulse\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\CasePulse"; Filename: "{app}\CasePulse.exe"; Tasks: startmenu
Name: "{group}\Uninstall CasePulse"; Filename: "{uninstallexe}"; Tasks: startmenu
Name: "{autodesktop}\CasePulse"; Filename: "{app}\CasePulse.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CasePulse.exe"; Description: "Launch CasePulse"; Flags: nowait postinstall skipifsilent
